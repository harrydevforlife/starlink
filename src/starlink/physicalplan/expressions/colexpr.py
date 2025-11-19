

from starlink.physicalplan.expressions.expr import Expression
from starlink.datatypes.column_vector import ColumnVector
from starlink.datatypes.record_batch import RecordBatch

class ColumnExpression(Expression):
    """Reference column in a batch by index.
    Cause of the cost of the column access by name is high, we use the index instead.
    """

    def __init__(self, i: int):
        self.i = i

    def evaluate(self, input: RecordBatch) -> ColumnVector:
        return input.field(self.i)

    def __str__(self) -> str:
        return f"#{self.i}"
