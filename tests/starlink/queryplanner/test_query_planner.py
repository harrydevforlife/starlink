"""Tests for Query Planner

Tests creating physical plans from logical plans, including optimization.
"""

import pytest

import pyarrow as pa

from starlink.datasources.memory import InMemoryDataSource
from starlink.datatypes.schema import Schema, Field
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.arrow_types import ArrowTypes
from starlink.logicalplan.dataframe import DataFrameImpl
from starlink.logicalplan.scan import Scan
from starlink.logicalplan.expressions import col, Max
from starlink.logicalplan.logical import format_plan
from starlink.optimizer.optimizer import Optimizer
from starlink.queryplanner.queryplanner import QueryPlanner


class TestQueryPlanner:
    def test_plan_aggregate_query(self):
        """Test planning an aggregate query with optimization."""
        schema = Schema([
            Field("passenger_count", ArrowTypes.UInt32Type),
            Field("max_fare", ArrowTypes.DoubleType)
        ])
        
        # Create empty data source (just for testing the plan structure)
        data_source = InMemoryDataSource(schema, [])
        
        df = DataFrameImpl(Scan("", data_source, []))
        
        plan = df.aggregate(
            [col("passenger_count")],
            [Max(col("max_fare"))]
        ).logicalPlan()
        
        expected_logical = (
            "Aggregate: groupExpr=[#passenger_count], aggregateExpr=[MAX(#max_fare)]\n"
            "\tScan: ; projection=None\n"
        )
        
        assert format_plan(plan) == expected_logical
        
        # Test optimization
        optimizer = Optimizer()
        optimized_plan = optimizer.optimize(plan)
        
        expected_optimized = (
            "Aggregate: groupExpr=[#passenger_count], aggregateExpr=[MAX(#max_fare)]\n"
            "\tScan: ; projection=[passenger_count, max_fare]\n"
        )
        
        assert format_plan(optimized_plan) == expected_optimized
        
        # Test physical plan creation
        query_planner = QueryPlanner()
        physical_plan = query_planner.create_physical_plan(optimized_plan)
        
        # Check that physical plan is created (format may vary slightly)
        physical_str = physical_plan.pretty()

        expected_physical = (
            "HashAggregateExec: groupExpr=[#0], aggrExpr=[MAX(#1)]\n"
            "\tScanExec: schema=Schema(fields=[Field(name=passenger_count, dataType=uint32), Field(name=max_fare, dataType=double)]), projection=[passenger_count, max_fare]\n"
        )
        
        assert physical_str == expected_physical
