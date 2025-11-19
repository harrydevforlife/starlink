from typing import Any, List

import pyarrow as pa
import pyarrow.compute as pc

from starlink.datatypes.column_vector import ColumnVector
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.literal_value_vector import LiteralValueVector
from starlink.physicalplan.expressions.expr import Expression
from starlink.physicalplan.expressions.binaryexpr import BinaryExpression


class MathExpression(BinaryExpression):
    """Base class for math expressions using vectorized PyArrow compute operations.

    This class provides vectorized evaluation using PyArrow compute functions,
    which are highly optimized C++ kernels that eliminate Python loop overhead.
    """

    def evaluate_pair(self, l: ColumnVector, r: ColumnVector) -> ColumnVector:
        """Evaluate math expression using vectorized PyArrow compute operations.

        This method extracts PyArrow arrays from ColumnVectors and uses
        PyArrow compute functions for efficient vectorized evaluation.
        """
        # Extract PyArrow arrays from ColumnVector
        # Handle both ArrowFieldVector and LiteralValueVector
        # Convert LiteralValueVector to ArrowFieldVector for vectorized operations
        if isinstance(l, LiteralValueVector):
            # Convert literal to PyArrow array (broadcast value to match size)
            left_array = pa.array([l.value] * l.size(), type=l.dataType)
        elif isinstance(l, ArrowFieldVector):
            left_array = l.field
        else:
            raise ValueError(f"MathExpression requires ArrowFieldVector or LiteralValueVector, got {type(l)}")

        if isinstance(r, LiteralValueVector):
            # Convert literal to PyArrow array (broadcast value to match size)
            right_array = pa.array([r.value] * r.size(), type=r.dataType)
        elif isinstance(r, ArrowFieldVector):
            right_array = r.field
        else:
            raise ValueError(f"MathExpression requires ArrowFieldVector or LiteralValueVector, got {type(r)}")

        # Handle ChunkedArray by combining chunks into a single Array
        if isinstance(left_array, pa.ChunkedArray):
            left_array = left_array.combine_chunks()
        if isinstance(right_array, pa.ChunkedArray):
            right_array = right_array.combine_chunks()

        # Type validation - PyArrow compute requires compatible types
        # Note: PyArrow will handle type promotion automatically (int + float = float)
        # But we should ensure they're both numeric types
        if not (pa.types.is_integer(left_array.type) or pa.types.is_floating(left_array.type)):
            raise ValueError(f"MathExpression requires numeric operands, got {left_array.type}")
        if not (pa.types.is_integer(right_array.type) or pa.types.is_floating(right_array.type)):
            raise ValueError(f"MathExpression requires numeric operands, got {right_array.type}")

        # Delegate to subclass-specific vectorized operation
        result = self._evaluate_vectorized(left_array, right_array)

        # Return wrapped result
        # Result type follows left operand type (PyArrow handles type promotion automatically)
        return ArrowFieldVector(result)

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Perform vectorized evaluation using PyArrow compute.

        Subclasses must implement this method to use the appropriate compute function.

        Args:
            left_array: PyArrow Array from left operand
            right_array: PyArrow Array from right operand

        Returns:
            PyArrow Array with math operation results
        """
        raise NotImplementedError("Subclasses must implement _evaluate_vectorized")

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> Any:
        raise NotImplementedError()


class AddExpression(MathExpression):
    """Vectorized addition using PyArrow compute."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized addition: left + right.

        PyArrow compute handles nulls automatically (null + 5 = null).
        Type promotion is handled automatically (int + float = float).
        """
        return pc.add(left_array, right_array)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> Any:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        if pa.types.is_integer(dtype) or pa.types.is_floating(dtype):
            return (0 if lv is None else lv) + (0 if rv is None else rv)
        raise ValueError(f"Unsupported data type in math expression: {dtype}")

    def __str__(self) -> str:
        return f"{self.l}+{self.r}"


class SubtractExpression(MathExpression):
    """Vectorized subtraction using PyArrow compute."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized subtraction: left - right.

        PyArrow compute handles nulls automatically (null - 5 = null).
        Type promotion is handled automatically.
        """
        return pc.subtract(left_array, right_array)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> Any:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        if pa.types.is_integer(dtype) or pa.types.is_floating(dtype):
            return (0 if lv is None else lv) - (0 if rv is None else rv)
        raise ValueError(f"Unsupported data type in math expression: {dtype}")

    def __str__(self) -> str:
        return f"{self.l}-{self.r}"


class MultiplyExpression(MathExpression):
    """Vectorized multiplication using PyArrow compute."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized multiplication: left * right.

        PyArrow compute handles nulls automatically (null * 5 = null).
        Type promotion is handled automatically.
        """
        return pc.multiply(left_array, right_array)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> Any:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        if pa.types.is_integer(dtype) or pa.types.is_floating(dtype):
            return (0 if lv is None else lv) * (0 if rv is None else rv)
        raise ValueError(f"Unsupported data type in math expression: {dtype}")

    def __str__(self) -> str:
        return f"{self.l}*{self.r}"


class DivideExpression(MathExpression):
    """Vectorized division using PyArrow compute."""

    def _evaluate_vectorized(self, left_array: pa.Array, right_array: pa.Array) -> pa.Array:
        """Vectorized division: left / right.

        PyArrow compute handles nulls automatically (null / 5 = null, 5 / null = null).
        For division by zero, we convert zeros to nulls before dividing, which results in null.
        Type promotion is handled automatically.
        """
        # Handle division by zero: convert zeros in right_array to nulls
        # This matches the behavior of the legacy implementation (5 / 0 = null)
        zero_mask = pc.equal(right_array, pa.scalar(0, type=right_array.type))
        # Use if_else to set zeros to null
        right_array_safe = pc.if_else(
            zero_mask,
            pa.scalar(None, type=right_array.type),
            right_array
        )
        return pc.divide(left_array, right_array_safe)

    def _evaluate_value(self, lv: Any, rv: Any, dtype: pa.DataType) -> Any:
        """Legacy row-by-row evaluation (kept for backward compatibility)."""
        if pa.types.is_integer(dtype) or pa.types.is_floating(dtype):
            # Avoid division by None; treat None as 0 similar to others; protect divide-by-zero
            left = 0 if lv is None else lv
            right = 0 if rv is None else rv
            if right == 0:
                return None
            return left / right
        raise ValueError(f"Unsupported data type in math expression: {dtype}")

    def __str__(self) -> str:
        return f"{self.l}/{self.r}"
