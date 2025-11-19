

from typing import List, Sequence, Iterator

from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.schema import Schema
from starlink.physicalplan.expressions.expr import Expression
from starlink.physicalplan.physical import PhysicalPlan


class ProjectionExec(PhysicalPlan):
    """Execute a projection over the input physical plan."""

    def __init__(self, input: PhysicalPlan, schema: Schema, expr: List[Expression]):
        self.input = input
        self._schema = schema
        self.expr = expr

    def schema(self) -> Schema:
        return self._schema

    def children(self) -> List[PhysicalPlan]:
        return [self.input]

    def execute(self) -> Sequence[RecordBatch]:
        def generator() -> Iterator[RecordBatch]:
            for batch in self.input.execute():
                columns = [e.evaluate(batch) for e in self.expr]
                yield RecordBatch(self._schema, columns)

        return generator()

    def __str__(self) -> str:
        return f"ProjectionExec: {self.expr}"
