"""Tests for Aggregate Expressions

Tests evaluating aggregate expressions (Min, Max, Sum) with accumulators.
"""

import pytest

from starlink.physicalplan.expressions.colexpr import ColumnExpression
from starlink.physicalplan.expressions.minexpr import MinExpression
from starlink.physicalplan.expressions.maxexpr import MaxExpression
from starlink.physicalplan.expressions.sumexpr import SumExpression


class TestAggregate:
    def test_min_accumulator(self):
        """Test MinExpression accumulator."""
        a = MinExpression(ColumnExpression(0)).create_accumulator()
        values = [10, 14, 4]
        
        for value in values:
            a.accumulate(value)
        
        assert a.final_value() == 4

    def test_max_accumulator(self):
        """Test MaxExpression accumulator."""
        a = MaxExpression(ColumnExpression(0)).create_accumulator()
        values = [10, 14, 4]
        
        for value in values:
            a.accumulate(value)
        
        assert a.final_value() == 14

    def test_sum_accumulator(self):
        """Test SumExpression accumulator."""
        a = SumExpression(ColumnExpression(0)).create_accumulator()
        values = [10, 14, 4]
        
        for value in values:
            a.accumulate(value)
        
        assert a.final_value() == 28
