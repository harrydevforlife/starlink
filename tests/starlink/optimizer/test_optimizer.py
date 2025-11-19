"""Tests for Optimizer

Tests the projection push down optimization rule.
"""

from typing import List

import pytest

from starlink.datasources.csv import CsvDataSource
from starlink.datasources.memory import InMemoryDataSource
from starlink.datatypes.schema import Schema, Field
from starlink.datatypes.arrow_types import ArrowTypes
from starlink.logicalplan.scan import Scan
from starlink.logicalplan.dataframe import DataFrameImpl
from starlink.logicalplan.join import Join
from starlink.logicalplan.select import Selection
from starlink.logicalplan.projection import Projection
from starlink.logicalplan.expressions import col, lit, Eq, Min, Max, Count, Gt, And
from starlink.logicalplan.logical import format_plan
from starlink.optimizer.optimizer import Optimizer
from starlink.optimizer.projection_pushdown import ProjectionPushDownRule


@pytest.fixture
def employee_csv(tmp_path):
    """Create employee.csv with headers."""
    csv_file = tmp_path / "employee.csv"
    csv_content = """id,first_name,last_name,state,job_title,salary
1,John,Doe,CA,Engineer,50000
2,Jane,Smith,NY,Manager,60000
3,Bob,Einstein,CO,Scientist,70000
4,Alice,Johnson,TX,Engineer,55000
"""
    csv_file.write_text(csv_content)
    return str(csv_file)


def csv(employee_csv: str) -> DataFrameImpl:
    """Helper function to create a DataFrame from CSV."""
    return DataFrameImpl(
        Scan("employee", CsvDataSource(employee_csv, None, True, 1024), [])
    )


def build_in_memory_scan(name: str, fields: List[Field]) -> Scan:
    """Create a Scan node backed by an in-memory data source with the given schema."""
    schema = Schema(fields)
    datasource = InMemoryDataSource(schema, [])
    return Scan(name, datasource, [])


def build_customer_order_join() -> Join:
    """Construct a join logical plan used across tests."""
    customers = build_in_memory_scan(
        "customers",
        [
            Field("customer_id", ArrowTypes.Int64Type),
            Field("name", ArrowTypes.StringType),
            Field("city", ArrowTypes.StringType),
        ],
    )
    orders = build_in_memory_scan(
        "orders",
        [
            Field("order_customer_id", ArrowTypes.Int64Type),
            Field("order_id", ArrowTypes.Int64Type),
            Field("total", ArrowTypes.Int64Type),
        ],
    )
    return Join(customers, orders, ["customer_id"], ["order_customer_id"])


class TestOptimizer:
    def test_projection_push_down(self, employee_csv):
        """Test basic projection push down optimization."""
        df = csv(employee_csv).project([col("id"), col("first_name"), col("last_name")])

        rule = ProjectionPushDownRule()
        optimized_plan = rule.optimize(df.logicalPlan())

        expected = (
            "Projection: #id, #first_name, #last_name\n"
            "\tScan: employee; projection=[id, first_name, last_name]\n"
        )

        assert format_plan(optimized_plan) == expected

    def test_projection_push_down_with_selection(self, employee_csv):
        """Test projection push down with selection (filter)."""
        df = (
            csv(employee_csv)
            .filter(Eq(col("state"), lit("CO")))
            .project([col("id"), col("first_name"), col("last_name")])
        )

        rule = ProjectionPushDownRule()
        optimized_plan = rule.optimize(df.logicalPlan())

        expected = (
            "Projection: #id, #first_name, #last_name\n"
            "\tSelection: #state = 'CO'\n"
            "\t\tScan: employee; projection=[id, first_name, last_name, state]\n"
        )

        assert format_plan(optimized_plan) == expected

    def test_projection_push_down_with_aggregate_query(self, employee_csv):
        """Test projection push down with aggregate query."""
        df = (
            csv(employee_csv)
            .aggregate(
                [col("state")],
                [Min(col("salary")), Max(col("salary")), Count(col("salary"))]
            )
        )

        rule = ProjectionPushDownRule()
        optimized_plan = rule.optimize(df.logicalPlan())

        expected = (
            "Aggregate: groupExpr=[#state], aggregateExpr=[MIN(#salary), MAX(#salary), COUNT(#salary)]\n"
            "\tScan: employee; projection=[state, salary]\n"
        )

        assert format_plan(optimized_plan) == expected

    def test_filter_pushdown_targets_join_side(self):
        """Ensure predicates referencing a single join side push to that scan."""
        join_plan = build_customer_order_join()
        predicate = Gt(col("total"), lit(50000))
        plan = Selection(join_plan, predicate)

        optimized = Optimizer().optimize(plan)

        assert isinstance(optimized, Join)
        assert optimized.right.filter is not None
        assert optimized.left.filter is None
        # The pushed predicate should match the original
        assert str(optimized.right.filter) == str(predicate)

    def test_filter_pushdown_splits_conjuncts_for_join(self):
        """Conjunctive predicates split between join sides."""
        join_plan = build_customer_order_join()
        predicate = And(Gt(col("total"), lit(50000)), Eq(col("city"), lit("NY")))
        plan = Selection(join_plan, predicate)

        optimized = Optimizer().optimize(plan)

        join_op = optimized
        assert isinstance(join_op, Join)
        assert join_op.left.filter is not None
        assert join_op.right.filter is not None
        assert str(join_op.left.filter) == "#city = 'NY'"
        assert str(join_op.right.filter) == "#total > 50000"

    def test_projection_pushdown_over_join_preserves_keys(self):
        """Projection pushdown keeps join keys even if not in final output."""
        join_plan = build_customer_order_join()
        projection = Projection(join_plan, [col("name"), col("total")])

        optimized = Optimizer().optimize(projection)

        assert isinstance(optimized, Projection)
        join_node = optimized.input
        assert isinstance(join_node, Join)

        left_scan = join_node.left
        right_scan = join_node.right

        assert isinstance(left_scan, Scan)
        assert isinstance(right_scan, Scan)

        assert left_scan.projection == ["name", "customer_id"]
        assert right_scan.projection == ["total", "order_customer_id"]
