from abc import ABC, abstractmethod
from typing import List, Set, OrderedDict

from starlink.logicalplan.logical import LogicalPlan
from starlink.logicalplan.expr import LogicalExpr
from starlink.logicalplan.expressions import (
    ColumnIndex,
    Column,
    BinaryExpr,
    Alias,
    CastExpr,
    LiteralString,
    LiteralLong,
    LiteralDouble,
)


class Optimizer:
    def optimize(self, plan: LogicalPlan) -> LogicalPlan:
        """Apply optimization rules to the logical plan.
        
        Currently applies:
        1. FilterPushDownRule - Push filters down to scans
        2. ProjectionPushDownRule - Push projections down to scans
        """
        # Apply filter pushdown first (filters should be pushed before projections)
        try:
            filter_rule_cls = __import__(
                "starlink.optimizer.filter_pushdown",
                fromlist=["FilterPushDownRule"],
            ).FilterPushDownRule
            filter_rule: OptimizerRule = filter_rule_cls()
            plan = filter_rule.optimize(plan)
        except Exception:
            # Filter pushdown rule not available; continue
            pass
        
        # Apply projection pushdown
        try:
            projection_rule_cls = __import__(
                "starlink.optimizer.projection_pushdown",
                fromlist=["ProjectionPushDownRule"],
            ).ProjectionPushDownRule
            projection_rule: OptimizerRule = projection_rule_cls()
            plan = projection_rule.optimize(plan)
        except Exception:
            # Projection pushdown rule not available; continue
            pass
        
        return plan


class OptimizerRule(ABC):
    @abstractmethod
    def optimize(self, plan: LogicalPlan) -> LogicalPlan:
        pass


def extractColumns(expr_list: List[LogicalExpr], input: LogicalPlan, accum: OrderedDict) -> None:
    for e in expr_list:
        extractColumn(e, input, accum)


def extractColumn(expr: LogicalExpr, input: LogicalPlan, accum: OrderedDict) -> None:
    if isinstance(expr, ColumnIndex):
        name = input.schema().fields[expr.i].name
        if name not in accum:
            accum[name] = None  # Use OrderedDict to preserve insertion order
    elif isinstance(expr, Column):
        if expr.name not in accum:
            accum[expr.name] = None  # Use OrderedDict to preserve insertion order
    elif isinstance(expr, BinaryExpr):
        extractColumn(expr.l, input, accum)
        extractColumn(expr.r, input, accum)
    elif isinstance(expr, Alias):
        extractColumn(expr.expr, input, accum)
    elif isinstance(expr, CastExpr):
        extractColumn(expr.expr, input, accum)
    elif isinstance(expr, (LiteralString, LiteralLong, LiteralDouble)):
        return
    else:
        raise ValueError(f"extractColumns does not support expression: {expr}")
