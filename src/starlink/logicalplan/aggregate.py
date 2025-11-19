from typing import List

from starlink.datatypes.schema import Schema
from starlink.logicalplan.expr import LogicalExpr
from starlink.logicalplan.expressions import AggregateExpr
from starlink.logicalplan.logical import LogicalPlan


class Aggregate(LogicalPlan):
    """Logical plan representing an aggregate query over an input."""

    def __init__(
        self,
        input: LogicalPlan,
        group_expr: List[LogicalExpr],
        aggregate_expr: List[AggregateExpr],
    ):
        self.input = input
        self.group_expr = group_expr
        self.aggregate_expr = aggregate_expr

    def schema(self) -> Schema:
        group_fields = [e.to_field(self.input) for e in self.group_expr]
        agg_fields = [e.to_field(self.input) for e in self.aggregate_expr]
        return Schema(group_fields + agg_fields)

    def children(self) -> List[LogicalPlan]:
        return [self.input]

    def __str__(self) -> str:
        group_str = "[" + ", ".join(str(e) for e in self.group_expr) + "]"
        agg_str = "[" + ", ".join(str(e) for e in self.aggregate_expr) + "]"
        return f"Aggregate: groupExpr={group_str}, aggregateExpr={agg_str}"
