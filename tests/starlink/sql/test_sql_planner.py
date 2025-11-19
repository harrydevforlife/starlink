"""Tests for SQL Planner

Tests the conversion of SQL statements to logical plans.
"""

import os
import tempfile
from pathlib import Path

import pytest

from starlink.datasources.csv import CsvDataSource
from starlink.logicalplan.dataframe import DataFrameImpl
from starlink.logicalplan.logical import LogicalPlan, format_plan
from starlink.logicalplan.scan import Scan
from starlink.sql.sql_parser import SqlParser
from starlink.sql.sql_planner import SqlPlanner
from starlink.sql.sql_tokenizer import SqlTokenizer


@pytest.fixture
def employee_csv(tmp_path):
    """Create a temporary CSV file with employee data for testing."""
    csv_file = tmp_path / "employee.csv"
    csv_content = """id,first_name,last_name,state,salary
1,John,Doe,CA,50000
2,Jane,Smith,NY,60000
3,Bob,Einstein,CA,70000
4,Alice,Johnson,TX,55000
5,Charlie,Brown,CA,80000
"""
    csv_file.write_text(csv_content)
    return str(csv_file)


@pytest.fixture
def employee_table(employee_csv):
    """Create a DataFrame for the employee table."""
    csv_ds = CsvDataSource(employee_csv, None, True, 1024)
    scan = Scan("", csv_ds, [])
    return DataFrameImpl(scan)


def plan(sql: str, tables: dict) -> LogicalPlan:
    """Helper function to parse SQL and create a logical plan.

    Args:
        sql: SQL query string
        tables: Dictionary mapping table names to DataFrame instances

    Returns:
        LogicalPlan representing the query
    """
    # Tokenize
    tokens = SqlTokenizer(sql).tokenize()

    # Parse
    parsed_query = SqlParser(tokens).parse()
    if parsed_query is None:
        raise ValueError(f"Failed to parse SQL: {sql}")

    # Plan
    planner = SqlPlanner()
    df = planner.create_data_frame(parsed_query, tables)

    return df.logicalPlan()


class TestSqlPlanner:
    def test_simple_select(self, employee_table):
        tables = {"employee": employee_table}
        plan_result = plan("SELECT state FROM employee", tables)
        expected = "Projection: #state\n\tScan: ; projection=None\n"
        assert format_plan(plan_result) == expected

    def test_select_with_filter(self, employee_table):
        tables = {"employee": employee_table}
        plan_result = plan("SELECT state FROM employee WHERE state = 'CA'", tables)
        expected = (
            "Selection: #state = 'CA'\n"
            "\tProjection: #state\n"
            "\t\tScan: ; projection=None\n"
        )
        assert format_plan(plan_result) == expected

    def test_select_with_filter_not_in_projection(self, employee_table):
        tables = {"employee": employee_table}
        plan_result = plan("SELECT last_name FROM employee WHERE state = 'CA'", tables)
        expected = (
            "Projection: #last_name\n"
            "\tSelection: #state = 'CA'\n"
            "\t\tProjection: #last_name, #state\n"
            "\t\t\tScan: ; projection=None\n"
        )
        assert format_plan(plan_result) == expected

    def test_select_filter_on_projection(self, employee_table):
        tables = {"employee": employee_table}
        plan_result = plan(
            "SELECT last_name AS foo FROM employee WHERE foo = 'Einstein'", tables
        )
        expected = (
            "Selection: #foo = 'Einstein'\n"
            "\tProjection: #last_name as foo\n"
            "\t\tScan: ; projection=None\n"
        )
        assert format_plan(plan_result) == expected

    def test_select_filter_on_projection_and_not(self, employee_table):
        tables = {"employee": employee_table}
        plan_result = plan(
            "SELECT last_name AS foo FROM employee WHERE foo = 'Einstein' AND state = 'CA'",
            tables,
        )
        expected = (
            "Projection: #foo\n"
            "\tSelection: #foo = 'Einstein' AND #state = 'CA'\n"
            "\t\tProjection: #last_name as foo, #state\n"
            "\t\t\tScan: ; projection=None\n"
        )
        assert format_plan(plan_result) == expected

    def test_plan_aggregate_query(self, employee_table):
        tables = {"employee": employee_table}
        plan_result = plan("SELECT state, MAX(salary) FROM employee GROUP BY state", tables)
        expected = (
            "Projection: #0, #1\n"
            "\tAggregate: groupExpr=[#state], aggregateExpr=[MAX(#salary)]\n"
            "\t\tScan: ; projection=None\n"
        )
        assert format_plan(plan_result) == expected

    def test_plan_aggregate_query_with_having(self, employee_table):
        tables = {"employee": employee_table}
        plan_result = plan(
            "SELECT state, MAX(salary) FROM employee GROUP BY state HAVING MAX(salary) > 10",
            tables,
        )
        expected = (
            "Selection: MAX(#salary) > 10\n"
            "\tProjection: #0, #1\n"
            "\t\tAggregate: groupExpr=[#state], aggregateExpr=[MAX(#salary)]\n"
            "\t\t\tScan: ; projection=None\n"
        )
        assert format_plan(plan_result) == expected

    def test_plan_aggregate_query_aggr_first(self, employee_table):
        tables = {"employee": employee_table}
        plan_result = plan("SELECT MAX(salary), state FROM employee GROUP BY state", tables)
        expected = (
            "Projection: #1, #0\n"
            "\tAggregate: groupExpr=[#state], aggregateExpr=[MAX(#salary)]\n"
            "\t\tScan: ; projection=None\n"
        )
        assert format_plan(plan_result) == expected

    def test_plan_aggregate_query_with_filter(self, employee_table):
        tables = {"employee": employee_table}
        plan_result = plan(
            "SELECT state, MAX(salary) FROM employee WHERE salary > 50000 GROUP BY state",
            tables,
        )
        expected = (
            "Projection: #0, #1\n"
            "\tAggregate: groupExpr=[#state], aggregateExpr=[MAX(#salary)]\n"
            "\t\tSelection: #salary > 50000\n"
            "\t\t\tProjection: #state, #salary\n"
            "\t\t\t\tScan: ; projection=None\n"
        )
        assert format_plan(plan_result) == expected

    def test_plan_aggregate_query_with_cast(self, employee_table):
        tables = {"employee": employee_table}
        plan_result = plan(
            "SELECT state, MAX(CAST(salary AS double)) FROM employee GROUP BY state",
            tables,
        )
        # Note: The cast type representation may differ, so we check for key parts
        result_str = format_plan(plan_result)
        assert "Projection: #0, #1" in result_str
        assert "Aggregate: groupExpr=[#state]" in result_str
        assert "MAX(CAST(#salary AS" in result_str or "MAX(CAST(#salary AS double" in result_str
        assert "Scan: ; projection=None" in result_str

    def test_table_not_found(self, employee_table):
        """Test that missing table raises an error."""
        tables = {"employee": employee_table}
        planner = SqlPlanner()
        tokens = SqlTokenizer("SELECT id FROM nonexistent").tokenize()
        parsed = SqlParser(tokens).parse()
        
        with pytest.raises(ValueError, match="No table named 'nonexistent'"):
            planner.create_data_frame(parsed, tables)

    def test_group_by_without_aggregate(self, employee_table):
        """Test that GROUP BY without aggregates raises an error."""
        tables = {"employee": employee_table}
        
        with pytest.raises(ValueError, match="GROUP BY without aggregate expressions"):
            plan("SELECT state FROM employee GROUP BY state", tables)
