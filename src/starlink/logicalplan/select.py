from typing import List

from starlink.datatypes.schema import Schema
from starlink.logicalplan.expr import LogicalExpr
from starlink.logicalplan.logical import LogicalPlan


class Selection(LogicalPlan):
    """Logical plan representing a selection (a.k.a. filter) against an input."""

    def __init__(self, input: LogicalPlan, expr: LogicalExpr):
        self.input = input
        self.expr = expr

    def schema(self) -> Schema:
        return self.input.schema()

    def children(self) -> List[LogicalPlan]:
        return [self.input]

    def __str__(self) -> str:
        return f"Selection: {self.expr}"
