from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

from starlink.datatypes.column_vector import ColumnVector
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.literal_value_vector import LiteralValueVector
from starlink.physicalplan.expressions.expr import Expression
from starlink.physicalplan.expressions.binaryexpr import BinaryExpression


class BooleanExpression(BinaryExpression):
    """Base class for boolean expressions using vectorized PyArrow compute operations.

    This class provides vectorized evaluation using PyArrow compute functions,
    which are highly optimized C++ kernels that eliminate Python loop overhead.
    """

    def __init__(self, left: Expression, right: Expression):
        super().__init__(left, right)

    def evaluate_pair(self, left: ColumnVector, right: ColumnVector) -> ColumnVector:
        """Evaluate boolean expression using vectorized PyArrow compute operations.

        This method extracts PyArrow arrays from ColumnVectors and uses
        PyArrow compute functions for efficient vectorized evaluation.

        Subclasses should override this method to use specific compute functions.
        """
        # Extract PyArrow arrays from ColumnVector
        # Handle both ArrowFieldVector and LiteralValueVector
        # Convert LiteralValueVector to ArrowFieldVector for vectorized operations
        if isinstance(left, LiteralValueVector):
            # Convert literal to PyArrow array (broadcast value to match size)
            left_array = pa.array([left.value] * left.size(), type=left.dataType)
        elif isinstance(left, ArrowFieldVector):
            left_array = left.field
        else:
            raise ValueError(f"BooleanExpression requires ArrowFieldVector or LiteralValueVector, got {type(left)}")

        if isinstance(right, LiteralValueVector):
            # Convert literal to PyArrow array (broadcast value to match size)
            right_array = pa.array([right.value] * right.size(), type=right.dataType)
        elif isinstance(right, ArrowFieldVector):
            right_array = right.field
        else:
            raise ValueError(f"BooleanExpression requires ArrowFieldVector or LiteralValueVector, got {type(right)}")

        # Handle ChunkedArray by combining chunks into a single Array
        if isinstance(left_array, pa.ChunkedArray):
            left_array = left_array.combine_chunks()
        if isinstance(right_array, pa.ChunkedArray):
            right_array = right_array.combine_chunks()

        # Type validation - PyArrow compute requires compatible types
        if left_array.type != right_array.type:
            raise ValueError(
                f"Cannot compare values of different type: {left_array.type} != {right_array.type}"
            )

        # Delegate to subclass-specific vectorized operation
        result = self._evaluate_vectorized(left_array, right_array)

        # Return wrapped result
        return ArrowFieldVector(result)

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Perform vectorized evaluation using PyArrow compute.

        Subclasses must implement this method to use the appropriate compute function.

        Args:
            left_array: PyArrow Array from left operand
            right_array: PyArrow Array from right operand

        Returns:
            PyArrow boolean Array with comparison results
        """
        raise NotImplementedError("Subclasses must implement _evaluate_vectorized")

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> bool:
        """Legacy row-by-row evaluation method (kept for backward compatibility).

        This method is no longer used in the vectorized implementation but
        is kept for potential fallback scenarios or testing.
        """
        raise NotImplementedError()

    @staticmethod
    def _to_string(v: Any) -> str:
        if isinstance(v, (bytes, bytearray)):
            return bytes(v).decode("utf-8")
        return "" if v is None else str(v)

    @staticmethod
    def _to_bool(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return int(v) == 1
        raise ValueError("Cannot convert to bool: unsupported type")


class AndExpression(BooleanExpression):
    """Vectorized logical AND using PyArrow compute (Kleene logic)."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized logical AND: left AND right.

        Uses Kleene logic which correctly handles nulls:
        - null AND true = null
        - null AND false = false
        - null AND null = null
        """
        # Ensure both arrays are boolean type
        if left_array.type != pa.bool_() or right_array.type != pa.bool_():
            raise ValueError(
                f"AndExpression requires boolean operands, got {left_array.type} and {right_array.type}"
            )
        return pc.and_kleene(left_array, right_array)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> bool:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        return self._to_bool(lv) and self._to_bool(rv)


class OrExpression(BooleanExpression):
    """Vectorized logical OR using PyArrow compute (Kleene logic)."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized logical OR: left OR right.

        Uses Kleene logic which correctly handles nulls:
        - null OR true = true
        - null OR false = null
        - null OR null = null
        """
        # Ensure both arrays are boolean type
        if left_array.type != pa.bool_() or right_array.type != pa.bool_():
            raise ValueError(
                f"OrExpression requires boolean operands, got {left_array.type} and {right_array.type}"
            )
        return pc.or_kleene(left_array, right_array)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> bool:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        return self._to_bool(lv) or self._to_bool(rv)


class EqExpression(BooleanExpression):
    """Vectorized equality comparison using PyArrow compute."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized equality comparison: left == right."""
        return pc.equal(left_array, right_array)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> bool:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        if pa.types.is_string(dtype):
            return self._to_string(lv) == self._to_string(rv)
        if pa.types.is_integer(dtype) or pa.types.is_floating(dtype) or pa.types.is_boolean(dtype):
            return lv == rv
        raise ValueError(f"Unsupported data type in comparison expression: {dtype}")


class NeqExpression(BooleanExpression):
    """Vectorized inequality comparison using PyArrow compute."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized inequality comparison: left != right."""
        return pc.not_equal(left_array, right_array)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> bool:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        if pa.types.is_string(dtype):
            return self._to_string(lv) != self._to_string(rv)
        if pa.types.is_integer(dtype) or pa.types.is_floating(dtype) or pa.types.is_boolean(dtype):
            return lv != rv
        raise ValueError(f"Unsupported data type in comparison expression: {dtype}")


class LtExpression(BooleanExpression):
    """Vectorized less-than comparison using PyArrow compute."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized less-than comparison: left < right."""
        return pc.less(left_array, right_array)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> bool:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        if pa.types.is_string(dtype):
            return self._to_string(lv) < self._to_string(rv)
        if pa.types.is_integer(dtype) or pa.types.is_floating(dtype):
            return lv < rv
        raise ValueError(f"Unsupported data type in comparison expression: {dtype}")


class LtEqExpression(BooleanExpression):
    """Vectorized less-than-or-equal comparison using PyArrow compute."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized less-than-or-equal comparison: left <= right."""
        return pc.less_equal(left_array, right_array)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> bool:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        if pa.types.is_string(dtype):
            return self._to_string(lv) <= self._to_string(rv)
        if pa.types.is_integer(dtype) or pa.types.is_floating(dtype):
            return lv <= rv
        raise ValueError(f"Unsupported data type in comparison expression: {dtype}")


class GtExpression(BooleanExpression):
    """Vectorized greater-than comparison using PyArrow compute."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized greater-than comparison: left > right."""
        return pc.greater(left_array, right_array)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> bool:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        if pa.types.is_string(dtype):
            return self._to_string(lv) > self._to_string(rv)
        if pa.types.is_integer(dtype) or pa.types.is_floating(dtype):
            return lv > rv
        raise ValueError(f"Unsupported data type in comparison expression: {dtype}")


class GtEqExpression(BooleanExpression):
    """Vectorized greater-than-or-equal comparison using PyArrow compute."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized greater-than-or-equal comparison: left >= right."""
        return pc.greater_equal(left_array, right_array)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> bool:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        if pa.types.is_string(dtype):
            return self._to_string(lv) >= self._to_string(rv)
        if pa.types.is_integer(dtype) or pa.types.is_floating(dtype):
            return lv >= rv
        raise ValueError(f"Unsupported data type in comparison expression: {dtype}")

