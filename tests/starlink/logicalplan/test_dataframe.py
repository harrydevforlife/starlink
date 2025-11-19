"""Tests for DataFrame

Tests building DataFrames using the fluent API and verifying their logical plans.
"""

import pytest

from starlink.datasources.csv import CsvDataSource
from starlink.logicalplan.scan import Scan
from starlink.logicalplan.dataframe import DataFrameImpl
from starlink.logicalplan.expressions import (
    col,
    lit,
    Eq,
    Gt,
    Multiply,
    Alias,
    Min,
    Max,
    Count,
)
from starlink.logicalplan.logical import format_plan


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


class TestDataFrame:
    def test_build_dataframe(self, employee_csv):
        """Test building DataFrame with filter and project."""
        df = (
            csv(employee_csv)
            .filter(Eq(col("state"), lit("CO")))
            .project([col("id"), col("first_name"), col("last_name")])
        )

        expected = (
            "Projection: #id, #first_name, #last_name\n"
            "\tSelection: #state = 'CO'\n"
            "\t\tScan: employee; projection=None\n"
        )

        assert format_plan(df.logicalPlan()) == expected

    def test_multiplier_and_alias(self, employee_csv):
        """Test DataFrame with multiplier expression and alias."""
        df = (
            csv(employee_csv)
            .filter(Eq(col("state"), lit("CO")))
            .project([
                col("id"),
                col("first_name"),
                col("last_name"),
                col("salary"),
                Alias(Multiply(col("salary"), lit(0.1)), "bonus"),
            ])
            .filter(Gt(col("bonus"), lit(1000)))
        )

        expected = (
            "Selection: #bonus > 1000\n"
            "\tProjection: #id, #first_name, #last_name, #salary, #salary * 0.1 as bonus\n"
            "\t\tSelection: #state = 'CO'\n"
            "\t\t\tScan: employee; projection=None\n"
        )

        actual = format_plan(df.logicalPlan())
        assert actual == expected

    def test_aggregate_query(self, employee_csv):
        """Test DataFrame with aggregate query."""
        df = (
            csv(employee_csv)
            .aggregate(
                [col("state")],
                [Min(col("salary")), Max(col("salary")), Count(col("salary"))]
            )
        )

        expected = (
            "Aggregate: groupExpr=[#state], aggregateExpr=[MIN(#salary), MAX(#salary), COUNT(#salary)]\n"
            "\tScan: employee; projection=None\n"
        )

        assert format_plan(df.logicalPlan()) == expected
