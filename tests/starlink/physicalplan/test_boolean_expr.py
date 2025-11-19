"""Tests for Boolean Expressions

Tests evaluating boolean expressions (GtEqExpression) with various data types.
"""

import pytest
import math
import sys

import pyarrow as pa

from starlink.datatypes.schema import Schema, Field
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.arrow_types import ArrowTypes
from starlink.physicalplan.expressions.colexpr import ColumnExpression
from starlink.physicalplan.expressions.booleanexpr import GtEqExpression


def create_record_batch(schema: Schema, columns: list) -> RecordBatch:
    """Helper function to create a RecordBatch from schema and column data."""
    if len(columns) != len(schema.fields):
        raise ValueError(f"Number of columns ({len(columns)}) must match schema fields ({len(schema.fields)})")
    
    vectors = []
    for field, column_data in zip(schema.fields, columns):
        # Create PyArrow array from column data
        arr = pa.array(column_data, type=field.dataType)
        vectors.append(ArrowFieldVector(arr))
    
    return RecordBatch(schema, vectors)


class TestBooleanExpression:
    def test_gteq_bytes(self):
        """Test GtEqExpression with Int8 (byte) type."""
        schema = Schema([
            Field("a", ArrowTypes.Int8Type),
            Field("b", ArrowTypes.Int8Type)
        ])
        
        a = [10, 20, 30, -128, 127]  # Byte.MIN_VALUE = -128, Byte.MAX_VALUE = 127
        b = [10, 30, 20, 127, -128]
        
        batch = create_record_batch(schema, [a, b])
        
        expr = GtEqExpression(ColumnExpression(0), ColumnExpression(1))
        result = expr.evaluate(batch)
        
        assert result.size() == len(a)
        for i in range(result.size()):
            assert result.get_value(i) == (a[i] >= b[i])

    def test_gteq_shorts(self):
        """Test GtEqExpression with Int16 (short) type."""
        schema = Schema([
            Field("a", ArrowTypes.Int16Type),
            Field("b", ArrowTypes.Int16Type)
        ])
        
        a = [111, 222, 333, -32768, 32767]  # Short.MIN_VALUE = -32768, Short.MAX_VALUE = 32767
        b = [111, 333, 222, 32767, -32768]
        
        batch = create_record_batch(schema, [a, b])
        
        expr = GtEqExpression(ColumnExpression(0), ColumnExpression(1))
        result = expr.evaluate(batch)
        
        assert result.size() == len(a)
        for i in range(result.size()):
            assert result.get_value(i) == (a[i] >= b[i])

    def test_gteq_ints(self):
        """Test GtEqExpression with Int32 (int) type."""
        schema = Schema([
            Field("a", ArrowTypes.Int32Type),
            Field("b", ArrowTypes.Int32Type)
        ])
        
        a = [111, 222, 333, -2147483648, 2147483647]  # Int.MIN_VALUE, Int.MAX_VALUE
        b = [111, 333, 222, 2147483647, -2147483648]
        
        batch = create_record_batch(schema, [a, b])
        
        expr = GtEqExpression(ColumnExpression(0), ColumnExpression(1))
        result = expr.evaluate(batch)
        
        assert result.size() == len(a)
        for i in range(result.size()):
            assert result.get_value(i) == (a[i] >= b[i])

    def test_gteq_longs(self):
        """Test GtEqExpression with Int64 (long) type."""
        schema = Schema([
            Field("a", ArrowTypes.Int64Type),
            Field("b", ArrowTypes.Int64Type)
        ])
        
        a = [111, 222, 333, -9223372036854775808, 9223372036854775807]  # Long.MIN_VALUE, Long.MAX_VALUE
        b = [111, 333, 222, 9223372036854775807, -9223372036854775808]
        
        batch = create_record_batch(schema, [a, b])
        
        expr = GtEqExpression(ColumnExpression(0), ColumnExpression(1))
        result = expr.evaluate(batch)
        
        assert result.size() == len(a)
        for i in range(result.size()):
            assert result.get_value(i) == (a[i] >= b[i])

    def test_gteq_doubles(self):
        """Test GtEqExpression with Float64 (double) type."""
        schema = Schema([
            Field("a", ArrowTypes.DoubleType),
            Field("b", ArrowTypes.DoubleType)
        ])
        
        a = [0.0, 1.0, sys.float_info.min, sys.float_info.max, float('nan')]
        b = list(reversed(a))
        
        batch = create_record_batch(schema, [a, b])
        
        expr = GtEqExpression(ColumnExpression(0), ColumnExpression(1))
        result = expr.evaluate(batch)
        
        assert result.size() == len(a)
        for i in range(result.size()):
            # Handle NaN comparison: NaN >= anything is False, anything >= NaN is False
            if math.isnan(a[i]) or math.isnan(b[i]):
                expected = False
            else:
                expected = a[i] >= b[i]
            assert result.get_value(i) == expected

    def test_gteq_strings(self):
        """Test GtEqExpression with String type."""
        schema = Schema([
            Field("a", ArrowTypes.StringType),
            Field("b", ArrowTypes.StringType)
        ])
        
        a = ["aaa", "bbb", "ccc"]
        b = ["aaa", "ccc", "bbb"]
        
        batch = create_record_batch(schema, [a, b])
        
        expr = GtEqExpression(ColumnExpression(0), ColumnExpression(1))
        result = expr.evaluate(batch)
        
        assert result.size() == len(a)
        for i in range(result.size()):
            assert result.get_value(i) == (a[i] >= b[i])
