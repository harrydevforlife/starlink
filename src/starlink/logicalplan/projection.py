from typing import List

from starlink.datatypes.schema import Schema
from starlink.logicalplan.expr import LogicalExpr
from starlink.logicalplan.logical import LogicalPlan


class Projection(LogicalPlan):
    """Logical plan representing a projection (evaluate expressions over input)."""

    def __init__(self, input: LogicalPlan, expr: List[LogicalExpr]):
        self.input = input
        self.expr = expr

    def schema(self) -> Schema:
        return Schema([e.to_field(self.input) for e in self.expr])

    def children(self) -> List[LogicalPlan]:
        return [self.input]

    def __str__(self) -> str:
        expr_str = ", ".join(str(e) for e in self.expr)
        return f"Projection: {expr_str}"
