

from typing import List

from starlink.datatypes.schema import Schema
from starlink.logicalplan.logical import LogicalPlan
from starlink.logicalplan.expr import LogicalExpr
from starlink.logicalplan.expressions import AggregateExpr
from starlink.logicalplan.projection import Projection
from starlink.logicalplan.select import Selection
from starlink.logicalplan.aggregate import Aggregate
from starlink.logicalplan.join import Join


class DataFrame:
    def project(self, expr: List[LogicalExpr]) -> "DataFrame":
        pass

    def filter(self, expr: LogicalExpr) -> "DataFrame":
        pass

    def aggregate(self, groupBy: List[LogicalExpr], aggregateExpr: List[AggregateExpr]) -> "DataFrame":
        pass

    def join(
        self,
        right: "DataFrame",
        left_on: List[str],
        right_on: List[str],
        join_type: str = "inner",
    ) -> "DataFrame":
        pass

    def schema(self) -> Schema:
        pass

    def logicalPlan(self) -> LogicalPlan:
        pass

    def optimizedPlan(self) -> LogicalPlan:
        """Return the optimized logical plan.

        This applies the optimizer rules to the logical plan.
        """
        pass


class DataFrameImpl(DataFrame):
    def __init__(self, plan: LogicalPlan):
        self._plan = plan

    def project(self, expr: List[LogicalExpr]) -> "DataFrame":
        return DataFrameImpl(Projection(self._plan, expr))

    def filter(self, expr: LogicalExpr) -> "DataFrame":
        return DataFrameImpl(Selection(self._plan, expr))

    def aggregate(self, groupBy: List[LogicalExpr], aggregateExpr: List[AggregateExpr]) -> "DataFrame":
        return DataFrameImpl(Aggregate(self._plan, groupBy, aggregateExpr))

    def join(
        self,
        right: "DataFrame",
        left_on: List[str],
        right_on: List[str],
        join_type: str = "inner",
    ) -> "DataFrame":
        if not isinstance(right, DataFrameImpl):
            raise ValueError("Right side of join must be a DataFrameImpl")
        return DataFrameImpl(Join(self._plan, right.logicalPlan(), left_on, right_on, join_type))

    def schema(self) -> Schema:
        return self._plan.schema()

    def logicalPlan(self) -> LogicalPlan:
        return self._plan

    def optimizedPlan(self) -> LogicalPlan:
        """Return the optimized logical plan.

        This applies the optimizer rules to the logical plan.
        """
        from starlink.optimizer.optimizer import Optimizer
        return Optimizer().optimize(self._plan)
