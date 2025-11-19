

from abc import ABC, abstractmethod

import pyarrow as pa

from starlink.datatypes.column_vector import ColumnVector
from starlink.datatypes.literal_value_vector import LiteralValueVector
from starlink.datatypes.record_batch import RecordBatch


class Expression(ABC):
    """Physical representation of an expression."""

    @abstractmethod
    def evaluate(self, input: RecordBatch) -> ColumnVector:
        """Evaluate this expression against an input record batch and produce a column."""
        pass


class LiteralLongExpression(Expression):
    def __init__(self, value: int):
        self.value = value

    def evaluate(self, input: RecordBatch) -> ColumnVector:
        return LiteralValueVector(pa.int64(), self.value, input.row_count())


class LiteralDoubleExpression(Expression):
    def __init__(self, value: float):
        self.value = value

    def evaluate(self, input: RecordBatch) -> ColumnVector:
        return LiteralValueVector(pa.float64(), self.value, input.row_count())


class LiteralStringExpression(Expression):
    def __init__(self, value: str):
        self.value = value

    def evaluate(self, input: RecordBatch) -> ColumnVector:
        return LiteralValueVector(pa.string(), self.value, input.row_count())


class Accumulator(ABC):
    @abstractmethod
    def accumulate(self, value):
        pass

    @abstractmethod
    def final_value(self):
        pass

