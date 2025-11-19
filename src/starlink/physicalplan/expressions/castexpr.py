

from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

from starlink.datatypes.column_vector import ColumnVector
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.arrow_vector_builder import ArrowVectorBuilder
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.literal_value_vector import LiteralValueVector
from starlink.physicalplan.expressions.expr import Expression


class CastExpression(Expression):
    def __init__(self, expr: Expression, dataType: pa.DataType):
        self.expr = expr
        self.dataType = dataType

    def __str__(self) -> str:
        return f"CAST({self.expr} AS {self.dataType})"

    def evaluate(self, input: RecordBatch) -> ColumnVector:
        """Evaluate cast expression using vectorized PyArrow compute operations.

        This method uses PyArrow's pc.cast() for efficient vectorized type casting,
        which is much faster than row-by-row conversion.
        
        Optimization: If source type equals target type, skip the cast (no-op).
        """
        value: ColumnVector = self.expr.evaluate(input)

        # Optimization: Check if cast is actually needed (no-op cast)
        # If source type equals target type, return the value directly without casting
        source_type = value.get_type()
        if source_type == self.dataType:
            # No-op cast: source type == target type
            # Return the original value to avoid unnecessary overhead
            return value

        # Extract PyArrow array from ColumnVector
        if isinstance(value, LiteralValueVector):
            # Convert literal to PyArrow array (broadcast value to match size)
            source_array = pa.array([value.value] * value.size(), type=value.dataType)
        elif isinstance(value, ArrowFieldVector):
            source_array = value.field
        else:
            raise ValueError(f"CastExpression requires ArrowFieldVector or LiteralValueVector, got {type(value)}")

        # Handle ChunkedArray by combining chunks into a single Array
        if isinstance(source_array, pa.ChunkedArray):
            source_array = source_array.combine_chunks()

        # Use PyArrow compute for vectorized casting
        # PyArrow cast handles most type conversions automatically
        try:
            # For numeric to numeric or numeric to string, use pc.cast()
            # Check if both are numeric (integer or floating point)
            source_is_numeric = pa.types.is_integer(source_array.type) or pa.types.is_floating(source_array.type)
            target_is_numeric = pa.types.is_integer(self.dataType) or pa.types.is_floating(self.dataType)
            source_is_string = pa.types.is_string(source_array.type)
            target_is_string = pa.types.is_string(self.dataType)
            
            if (source_is_numeric and target_is_numeric) or \
               (source_is_numeric and target_is_string) or \
               (source_is_string and target_is_numeric):
                # Determine if we need unsafe casting (e.g., double -> int truncation)
                # Unsafe casting is needed when:
                # 1. Casting from floating point to integer (truncation expected)
                # 2. Casting to smaller integer types (overflow possible)
                needs_unsafe = False
                if pa.types.is_floating(source_array.type) and pa.types.is_integer(self.dataType):
                    # Floating point -> integer: truncation is expected (e.g., 1.5 -> 1)
                    needs_unsafe = True
                elif pa.types.is_integer(source_array.type) and pa.types.is_integer(self.dataType):
                    # Integer -> integer: check if target is smaller (overflow possible)
                    source_size = self._get_integer_size(source_array.type)
                    target_size = self._get_integer_size(self.dataType)
                    if target_size < source_size:
                        # Casting to smaller integer type (e.g., int64 -> int32)
                        needs_unsafe = True
                
                if needs_unsafe:
                    # Use unsafe casting with appropriate options
                    # PyArrow CastOptions requires target_type and has:
                    # - allow_int_overflow: Allow integer overflow (e.g., int64 -> int32)
                    # - allow_float_truncate: Allow float truncation (e.g., double -> int)
                    cast_options = pc.CastOptions(
                        target_type=self.dataType,
                        allow_int_overflow=True,  # Allow integer overflow
                        allow_float_truncate=True,  # Allow float truncation
                    )
                    result = pc.cast(source_array, options=cast_options)
                else:
                    # Use safe casting (default)
                    result = pc.cast(source_array, self.dataType)
            else:
                # For other cases, fall back to row-by-row conversion
                # This handles edge cases that PyArrow cast might not support
                builder = ArrowVectorBuilder(self.dataType)
                n = value.size()
                builder.set_value_count(n)

                for i in range(n):
                    vv = value.get_value(i)
                    if vv is None:
                        builder.set(i, None)
                        continue

                    target = self.dataType
                    if pa.types.is_int8(target) or pa.types.is_int16(target) or \
                       pa.types.is_int32(target) or pa.types.is_int64(target):
                        builder.set(i, self._to_int(vv))
                    elif pa.types.is_float32(target) or pa.types.is_float64(target):
                        builder.set(i, self._to_float(vv))
                    elif pa.types.is_string(target):
                        builder.set(i, self._to_string(vv))
                    else:
                        raise ValueError(f"Cast to {self.dataType} is not supported")

                return builder.build()

            return ArrowFieldVector(result)
        except Exception as e:
            # If PyArrow cast fails, fall back to row-by-row conversion
            # This ensures backward compatibility
            builder = ArrowVectorBuilder(self.dataType)
            n = value.size()
            builder.set_value_count(n)

            for i in range(n):
                vv = value.get_value(i)
                if vv is None:
                    builder.set(i, None)
                    continue

                target = self.dataType
                if pa.types.is_int8(target) or pa.types.is_int16(target) or \
                   pa.types.is_int32(target) or pa.types.is_int64(target):
                    builder.set(i, self._to_int(vv))
                elif pa.types.is_float32(target) or pa.types.is_float64(target):
                    builder.set(i, self._to_float(vv))
                elif pa.types.is_string(target):
                    builder.set(i, self._to_string(vv))
                else:
                    raise ValueError(f"Cast to {self.dataType} is not supported")

            return builder.build()

    @staticmethod
    def _to_string(v: Any) -> str:
        if isinstance(v, (bytes, bytearray)):
            return bytes(v).decode("utf-8")
        return str(v)

    @staticmethod
    def _to_int(v: Any) -> int:
        if isinstance(v, (bytes, bytearray)):
            return int(bytes(v).decode("utf-8"))
        if isinstance(v, str):
            return int(v)
        if isinstance(v, (int, float, bool)):
            return int(v)
        raise ValueError(f"Cannot cast value to int: {v}")

    @staticmethod
    def _to_float(v: Any) -> float:
        if isinstance(v, (bytes, bytearray)):
            return float(bytes(v).decode("utf-8"))
        if isinstance(v, str):
            return float(v)
        if isinstance(v, (int, float, bool)):
            return float(v)
        raise ValueError(f"Cannot cast value to float: {v}")
    
    @staticmethod
    def _get_integer_size(dtype: pa.DataType) -> int:
        """Get the size (in bits) of an integer type for comparison purposes.
        
        Returns:
            Size in bits (8, 16, 32, or 64)
        """
        if pa.types.is_int8(dtype) or pa.types.is_uint8(dtype):
            return 8
        elif pa.types.is_int16(dtype) or pa.types.is_uint16(dtype):
            return 16
        elif pa.types.is_int32(dtype) or pa.types.is_uint32(dtype):
            return 32
        elif pa.types.is_int64(dtype) or pa.types.is_uint64(dtype):
            return 64
        else:
            raise ValueError(f"Not an integer type: {dtype}")
