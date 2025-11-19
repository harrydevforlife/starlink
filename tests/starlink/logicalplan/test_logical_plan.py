"""Tests for Logical Plan

Tests building logical plans manually and verifying their string representation.
"""

import pytest

from starlink.datasources.csv import CsvDataSource
from starlink.logicalplan.scan import Scan
from starlink.logicalplan.select import Selection
from starlink.logicalplan.projection import Projection
from starlink.logicalplan.aggregate import Aggregate
from starlink.logicalplan.expressions import (
    col,
    LiteralString,
    Eq,
    Max,
    cast,
)
from starlink.logicalplan.logical import format_plan
from starlink.datatypes.arrow_types import ArrowTypes


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


class TestLogicalPlan:
    def test_build_logical_plan_manually(self, employee_csv):
        """Test building logical plan manually (step by step)."""
        # Create a plan to represent the data source
        csv = CsvDataSource(employee_csv, None, True, 10)
        
        # Create a plan to represent the scan of the data source (FROM)
        scan = Scan("employee", csv, [])
        
        # Create a plan to represent the selection (WHERE)
        filter_expr = Eq(col("state"), LiteralString("CO"))
        selection = Selection(scan, filter_expr)
        
        # Create a plan to represent the projection (SELECT)
        plan = Projection(selection, [col("id"), col("first_name"), col("last_name")])
        
        expected = (
            "Projection: #id, #first_name, #last_name\n"
            "\tSelection: #state = 'CO'\n"
            "\t\tScan: employee; projection=None\n"
        )
        
        assert format_plan(plan) == expected

    def test_build_logical_plan_nested(self, employee_csv):
        """Test building logical plan using nested constructors."""
        plan = Projection(
            Selection(
                Scan("employee", CsvDataSource(employee_csv, None, True, 10), []),
                Eq(col("state"), LiteralString("CO"))
            ),
            [col("id"), col("first_name"), col("last_name")]
        )
        
        expected = (
            "Projection: #id, #first_name, #last_name\n"
            "\tSelection: #state = 'CO'\n"
            "\t\tScan: employee; projection=None\n"
        )
        
        assert format_plan(plan) == expected

    def test_build_aggregate_plan(self, employee_csv):
        """Test building aggregate logical plan."""
        # Create a plan to represent the data source
        csv = CsvDataSource(employee_csv, None, True, 10)
        
        # Create a plan to represent the scan of the data source (FROM)
        scan = Scan("employee", csv, [])
        
        # Create aggregate plan with GROUP BY and aggregate expressions
        group_expr = [col("state")]
        aggregate_expr = [Max(cast(col("salary"), ArrowTypes.Int32Type))]
        plan = Aggregate(scan, group_expr, aggregate_expr)
        
        expected = (
            "Aggregate: groupExpr=[#state], aggregateExpr=[MAX(CAST(#salary AS int32))]\n"
            "\tScan: employee; projection=None\n"
        )
        
        assert format_plan(plan) == expected
