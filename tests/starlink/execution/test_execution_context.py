"""Tests for Execution Context

Tests executing queries using the ExecutionContext API.
"""

import pytest

import pyarrow as pa

from starlink.datasources.memory import InMemoryDataSource
from starlink.datatypes.schema import Schema, Field
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.arrow_types import ArrowTypes
from starlink.execution.context import ExecutionContext
from starlink.execution.result import QueryResult
from starlink.logicalplan.dataframe import DataFrameImpl
from starlink.logicalplan.scan import Scan
from starlink.logicalplan.expressions import (
    col,
    lit,
    Eq,
    And,
    Or,
    Add,
    Subtract,
    Multiply,
    Divide,
    Min,
    Max,
    Sum,
    cast,
)


def create_record_batch(schema: Schema, columns: list) -> RecordBatch:
    """Helper function to create a RecordBatch from schema and column data.

    Args:
        schema: Schema with field definitions
        columns: List of lists, where each inner list is data for one column

    Returns:
        RecordBatch with the given schema and data
    """
    if len(columns) != len(schema.fields):
        raise ValueError(
            f"Number of columns ({len(columns)}) must match schema fields ({len(schema.fields)})"
        )

    vectors = []
    for field, column_data in zip(schema.fields, columns):
        # Create PyArrow array from column data
        arr = pa.array(column_data, type=field.dataType)
        vectors.append(ArrowFieldVector(arr))

    return RecordBatch(schema, vectors)


def dataframe_from_arrays(schema: Schema, columns: list) -> DataFrameImpl:
    """Create DataFrameImpl backed by InMemoryDataSource."""
    batch = create_record_batch(schema, columns)
    source = InMemoryDataSource(schema, [batch])
    return DataFrameImpl(Scan("", source, []))


@pytest.fixture
def employee_csv(tmp_path):
    """Create employee.csv fixture data."""
    csv_file = tmp_path / "employee.csv"
    csv_content = """id,first_name,last_name,state,job_title,salary
1,Bill,Hopkins,CA,Engineer,12000
2,Gregg,Langford,CO,Manager,11500
3,John,Travis,CO,Engineer,11500
"""
    csv_file.write_text(csv_content)
    return str(csv_file)


@pytest.fixture
def state_csv(tmp_path):
    """Simple state metadata."""
    csv_file = tmp_path / "state.csv"
    csv_content = """state_code,state_name
CA,California
CO,Colorado
"""
    csv_file.write_text(csv_content)
    return str(csv_file)


class TestExecutionContext:
    def test_employees_in_co_using_dataframe(self, employee_csv):
        """Test employees in CO using DataFrame API."""
        # Create a context
        ctx = ExecutionContext({})

        # Construct a query using the DataFrame API
        df = (
            ctx.csv(employee_csv)
            .filter(Eq(col("state"), lit("CO")))
            .project([col("id"), col("first_name"), col("last_name")])
        )

        batches = list(ctx.execute_batches(df))
        assert len(batches) == 1

        batch = batches[0]
        expected = "2,Gregg,Langford\n3,John,Travis\n"
        assert batch.to_csv() == expected

    def test_employees_in_ca_using_sql(self, employee_csv):
        """Test employees in CA using SQL."""
        # Create a context
        ctx = ExecutionContext({})

        employee = ctx.csv(employee_csv)
        ctx.register("employee", employee)

        # Construct a query using SQL
        df = ctx.sql("SELECT id, first_name, last_name FROM employee WHERE state = 'CA'")

        batches = list(ctx.execute_batches(df))
        assert len(batches) == 1

        batch = batches[0]
        expected = "1,Bill,Hopkins\n"
        assert batch.to_csv() == expected

    def test_employees_with_table_alias(self, employee_csv):
        """Ensure table aliases and qualified columns work in SQL."""
        ctx = ExecutionContext({})
        ctx.register("employee", ctx.csv(employee_csv))

        df = ctx.sql("SELECT e.id FROM employee e WHERE e.state = 'CA'")
        rows = ctx.execute(df).collect()
        assert rows == [{"id": "1"}]

    def test_aggregate_query(self, employee_csv):
        """Test aggregate query with cast."""
        # Create a context
        ctx = ExecutionContext({})

        # Construct a query using the DataFrame API
        df = (
            ctx.csv(employee_csv)
            .aggregate([col("state")], [Max(cast(col("salary"), pa.int32()))])
        )

        batches = list(ctx.execute_batches(df))
        assert len(batches) == 1

        batch = batches[0]
        # Note: The order might vary, so we check for all expected rows
        result = batch.to_csv()
        assert "CO,11500" in result
        assert "CA,12000" in result
        # Check that we have 3 lines (2 states + empty/null state)
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) >= 2  # At least CO and CA

    def test_bonuses_in_ca_using_sql_and_dataframe(self, employee_csv):
        """Test bonuses in CA using SQL and DataFrame."""
        # Create a context
        ctx = ExecutionContext({})

        # Construct a query using the DataFrame API
        ca_employees = (
            ctx.csv(employee_csv)
            .filter(Eq(col("state"), lit("CA")))
            .project([col("id"), col("first_name"), col("last_name"), col("salary")])
        )

        # Register the DataFrame as a table
        ctx.register("ca_employees", ca_employees)

        # Construct a query using SQL
        df = ctx.sql("SELECT id, first_name, last_name, salary FROM ca_employees")

        batches = list(ctx.execute_batches(df))
        assert len(batches) == 1

        batch = batches[0]
        expected = "1,Bill,Hopkins,12000\n"
        assert batch.to_csv() == expected

    def test_min_max_sum_float(self):
        """Test Min, Max, Sum aggregate functions with float type."""
        schema = Schema([
            Field("a", ArrowTypes.StringType),
            Field("b", ArrowTypes.FloatType)
        ])

        input_batch = create_record_batch(
            schema,
            [["a", "a", "b", "b"], [1.0, 2.0, 4.0, 3.0]]
        )

        data_source = InMemoryDataSource(schema, [input_batch])

        ctx = ExecutionContext({})
        logical_plan = (
            DataFrameImpl(Scan("", data_source, []))
            .aggregate([col("a")], [Min(col("b")), Max(col("b")), Sum(col("b"))])
            .logicalPlan()
        )

        batches = list(ctx.execute_batches(logical_plan))
        assert len(batches) == 1

        batch = batches[0]
        expected = "a,1.0,2.0,3.0\nb,3.0,4.0,7.0\n"
        assert batch.to_csv() == expected

    def test_float_math(self):
        """Test float math expressions (Add, Subtract, Multiply, Divide)."""
        schema = Schema([
            Field("a", ArrowTypes.FloatType),
            Field("b", ArrowTypes.FloatType)
        ])

        input_batch = create_record_batch(
            schema,
            [[1.0, 2.0, 4.0, 3.0], [11.0, 22.0, 44.0, 33.0]]
        )

        data_source = InMemoryDataSource(schema, [input_batch])

        ctx = ExecutionContext({})
        logical_plan = (
            DataFrameImpl(Scan("", data_source, []))
            .project([
                Add(col("a"), col("b")),
                Subtract(col("a"), col("b")),
                Multiply(col("a"), col("b")),
                Divide(col("a"), col("b"))
            ])
            .logicalPlan()
        )

        batches = list(ctx.execute_batches(logical_plan))
        assert len(batches) == 1

        batch = batches[0]
        # Check each line (allowing for floating point precision)
        result = batch.to_csv()
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 4
        
        # Check first line: 1.0 + 11.0 = 12.0, 1.0 - 11.0 = -10.0, etc.
        first_line = lines[0]
        assert "12.0" in first_line
        assert "-10.0" in first_line
        assert "11.0" in first_line
        assert "0.09090909" in first_line or "0.090909" in first_line

    def test_boolean_expressions(self):
        """Test boolean expressions (And, Or)."""
        schema = Schema([
            Field("a", ArrowTypes.BooleanType),
            Field("b", ArrowTypes.BooleanType)
        ])

        input_batch = create_record_batch(
            schema,
            [[False, False, True, True], [False, True, False, True]]
        )

        data_source = InMemoryDataSource(schema, [input_batch])

        ctx = ExecutionContext({})
        logical_plan = (
            DataFrameImpl(Scan("", data_source, []))
            .project([And(col("a"), col("b")), Or(col("a"), col("b"))])
            .logicalPlan()
        )

        batches = list(ctx.execute_batches(logical_plan))
        assert len(batches) == 1

        batch = batches[0]
        result = batch.to_csv().lower()
        expected = "false,false\nfalse,true\nfalse,true\ntrue,true\n"
        assert result == expected

    def test_sql_inner_join(self, employee_csv, state_csv):
        """End-to-end SQL join query."""
        ctx = ExecutionContext({})
        ctx.register("employee", ctx.csv(employee_csv))
        ctx.register("state_info", ctx.csv(state_csv))

        df = ctx.sql(
            "SELECT id, state_name FROM employee JOIN state_info ON state = state_code"
        )
        rows = ctx.execute(df).collect()
        assert rows == [
            {"id": "1", "state_name": "California"},
            {"id": "2", "state_name": "Colorado"},
            {"id": "3", "state_name": "Colorado"},
        ]

    def test_sql_join_with_aliases(self, employee_csv, state_csv):
        """SQL join referencing tables via aliases."""
        ctx = ExecutionContext({})
        ctx.register("employee", ctx.csv(employee_csv))
        ctx.register("state_info", ctx.csv(state_csv))

        df = ctx.sql(
            """
            SELECT e.id, s.state_name
            FROM employee e
            JOIN state_info s
                ON e.state = s.state_code
            WHERE s.state_name = 'California'
            """
        )
        rows = ctx.execute(df).collect()
        assert rows == [{"id": "1", "state_name": "California"}]

    def test_dataframe_join(self, employee_csv, state_csv):
        """DataFrame API join."""
        ctx = ExecutionContext({})
        employee_df = ctx.csv(employee_csv)
        state_df = ctx.csv(state_csv)

        joined = (
            employee_df.join(state_df, ["state"], ["state_code"])
            .project([col("id"), col("state_name")])
        )

        rows = ctx.execute(joined).collect()
        assert rows == [
            {"id": "1", "state_name": "California"},
            {"id": "2", "state_name": "Colorado"},
            {"id": "3", "state_name": "Colorado"},
        ]

    def test_dataframe_join_multiple_keys(self):
        """Join on multiple columns."""
        left_schema = Schema(
            [
                Field("k1", ArrowTypes.StringType),
                Field("k2", ArrowTypes.StringType),
                Field("value_left", ArrowTypes.Int64Type),
            ]
        )
        right_schema = Schema(
            [
                Field("k1", ArrowTypes.StringType),
                Field("k2", ArrowTypes.StringType),
                Field("value_right", ArrowTypes.Int64Type),
            ]
        )

        left_df = dataframe_from_arrays(
            left_schema,
            [["A", "A", "B"], ["X", "Y", "Z"], [10, 20, 30]],
        )
        right_df = dataframe_from_arrays(
            right_schema,
            [["A", "A"], ["Y", "X"], [1, 2]],
        )

        ctx = ExecutionContext({})
        rows = ctx.execute(
            left_df.join(right_df, ["k1", "k2"], ["k1", "k2"])
        ).collect()
        assert rows == [
            {
                "k1": "A",
                "k2": "Y",
                "value_left": 20,
                "k1_right": "A",
                "k2_right": "Y",
                "value_right": 1,
            },
            {
                "k1": "A",
                "k2": "X",
                "value_left": 10,
                "k1_right": "A",
                "k2_right": "X",
                "value_right": 2,
            },
        ]

    def test_join_duplicate_column_names(self):
        """Ensure duplicate right column names are suffixed."""
        schema = Schema(
            [
                Field("id", ArrowTypes.StringType),
                Field("value", ArrowTypes.Int64Type),
            ]
        )
        left_df = dataframe_from_arrays(schema, [["1"], [10]])
        right_df = dataframe_from_arrays(schema, [["1"], [99]])

        ctx = ExecutionContext({})
        joined = left_df.join(right_df, ["id"], ["id"])
        schema_fields = [field.name for field in joined.schema().fields]
        assert "value" in schema_fields
        assert any(name.startswith("value_right") for name in schema_fields)

    def test_join_no_matches(self):
        """Join resulting in no matches should return empty result."""
        left_schema = Schema([Field("id", ArrowTypes.StringType)])
        right_schema = Schema([Field("id", ArrowTypes.StringType)])
        left_df = dataframe_from_arrays(left_schema, [["1", "2"]])
        right_df = dataframe_from_arrays(right_schema, [["3"]])

        ctx = ExecutionContext({})
        result = ctx.execute(left_df.join(right_df, ["id"], ["id"]))
        assert result.collect() == []

    def test_execute_returns_query_result(self, employee_csv):
        """Ensure execute() returns QueryResult with working helpers."""
        ctx = ExecutionContext({})

        df = (
            ctx.csv(employee_csv)
            .project([col("id"), col("first_name")])
        )

        result = ctx.execute(df)
        assert isinstance(result, QueryResult)

        # collect() should return all rows as list of dicts
        rows = result.collect()
        assert rows == [
            {"id": "1", "first_name": "Bill"},
            {"id": "2", "first_name": "Gregg"},
            {"id": "3", "first_name": "John"},
        ]

        # len() should match collected rows
        assert len(result) == len(rows)

        # Markdown output should include column headers and sample value
        markdown = result.to_markdown(limit=2)
        assert "id" in markdown and "Bill" in markdown

        # __repr__ should mention QueryResult and columns
        repr_str = repr(result)
        assert "QueryResult" in repr_str
        assert "id" in repr_str and "first_name" in repr_str
