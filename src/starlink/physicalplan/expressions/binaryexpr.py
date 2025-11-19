

from abc import ABC, abstractmethod

import pyarrow as pa

from starlink.datatypes.column_vector import ColumnVector
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.literal_value_vector import LiteralValueVector
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.physicalplan.expressions.expr import Expression
from starlink.physicalplan.expressions.castexpr import CastExpression


class BinaryExpression(Expression, ABC):
    """Base class for physical binary expressions.

    Evaluates left and right child expressions for an input RecordBatch,
    validates shape and type compatibility, then delegates to evaluate_pair.
    
    Automatically coerces compatible numeric types (int to float when needed).
    """

    def __init__(self, l: Expression, r: Expression):
        self.l = l
        self.r = r

    def evaluate(self, input: RecordBatch) -> ColumnVector:
        left_vec = self.l.evaluate(input)
        right_vec = self.r.evaluate(input)
        assert left_vec.size() == right_vec.size()
        
        left_type = left_vec.get_type()
        right_type = right_vec.get_type()
        
        # Type coercion: if types don't match but are both numeric, coerce to compatible type
        if left_type != right_type:
            # Check if both are numeric types (integer or floating point)
            left_is_numeric = (pa.types.is_integer(left_type) or pa.types.is_floating(left_type))
            right_is_numeric = (pa.types.is_integer(right_type) or pa.types.is_floating(right_type))
            
            if left_is_numeric and right_is_numeric:
                # Coerce to the "wider" type (float64 > int64 > int32, etc.)
                if pa.types.is_floating(left_type) or pa.types.is_floating(right_type):
                    # At least one is floating point, coerce both to float64
                    target_type = pa.float64()
                    if left_type != target_type:
                        left_vec = self._coerce_type(left_vec, target_type, input.row_count())
                    if right_type != target_type:
                        right_vec = self._coerce_type(right_vec, target_type, input.row_count())
                elif pa.types.is_integer(left_type) and pa.types.is_integer(right_type):
                    # Both are integers, coerce to the wider integer type
                    if pa.types.is_int64(left_type) or pa.types.is_int64(right_type):
                        target_type = pa.int64()
                        if left_type != target_type:
                            left_vec = self._coerce_type(left_vec, target_type, input.row_count())
                        if right_type != target_type:
                            right_vec = self._coerce_type(right_vec, target_type, input.row_count())
                    else:
                        # Both are smaller integers, coerce to int32
                        target_type = pa.int32()
                        if left_type != target_type:
                            left_vec = self._coerce_type(left_vec, target_type, input.row_count())
                        if right_type != target_type:
                            right_vec = self._coerce_type(right_vec, target_type, input.row_count())
                else:
                    raise ValueError(
                        f"Binary expression operands do not have compatible numeric types: "
                        f"{left_type} != {right_type}"
                    )
            else:
                raise ValueError(
                    f"Binary expression operands do not have the same type: "
                    f"{left_type} != {right_type}"
                )
        
        return self.evaluate_pair(left_vec, right_vec)
    
    def _coerce_type(self, vec: ColumnVector, target_type: pa.DataType, row_count: int) -> ColumnVector:
        """Coerce a column vector to a target type.
        
        This is a helper for type coercion in binary expressions.
        For literals, we can create a new literal with the target type.
        For other vectors, we use CastExpression.
        """
        if isinstance(vec, LiteralValueVector):
            # For literals, create a new literal with the coerced type
            value = vec.value
            if pa.types.is_floating(target_type):
                coerced_value = float(value)
            elif pa.types.is_integer(target_type):
                coerced_value = int(value)
            else:
                coerced_value = value
            return LiteralValueVector(target_type, coerced_value, row_count)
        else:
            # For non-literals, use CastExpression to do the coercion
            # We need to create a temporary expression that evaluates to the cast
            from starlink.physicalplan.expressions.colexpr import ColumnExpression
            # This is a bit tricky - we need to cast the vector
            # For now, let's use a simple approach: if it's an ArrowFieldVector, cast it
            if isinstance(vec, ArrowFieldVector):
                import pyarrow.compute as pc
                source_array = vec.field
                if isinstance(source_array, pa.ChunkedArray):
                    source_array = source_array.combine_chunks()
                result = pc.cast(source_array, target_type)
                return ArrowFieldVector(result)
            else:
                # Fallback: try to cast
                import pyarrow.compute as pc
                # This is a simplified coercion - in practice we might need more
                raise ValueError(f"Cannot coerce {type(vec)} to {target_type}")

    @abstractmethod
    def evaluate_pair(self, l: ColumnVector, r: ColumnVector) -> ColumnVector:
        pass
