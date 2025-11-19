from typing import List

import pyarrow as pa

from starlink.datatypes.schema import Schema
from starlink.logicalplan.logical import LogicalPlan
from starlink.logicalplan.scan import Scan
from starlink.logicalplan.select import Selection
from starlink.logicalplan.projection import Projection
from starlink.logicalplan.aggregate import Aggregate
from starlink.logicalplan.join import Join
from starlink.logicalplan.expr import LogicalExpr
from starlink.logicalplan.expressions import (
    Column,
    ColumnIndex,
    Alias,
    CastExpr,
    BinaryExpr,
    And,
    Or,
    Eq,
    Neq,
    Gt,
    GtEq,
    Lt,
    LtEq,
    Add,
    Subtract,
    Multiply,
    Divide,
    LiteralLong,
    LiteralDouble,
    LiteralString,
    Sum,
    Min,
    Max,
    Count,
)
from starlink.physicalplan.physical import PhysicalPlan
from starlink.physicalplan.scanexec import ScanExec
from starlink.physicalplan.selectionexec import SelectionExec
from starlink.physicalplan.projectionexec import ProjectionExec
from starlink.physicalplan.hashaggexec import HashAggregateExec
from starlink.physicalplan.hashjoinexec import HashJoinExec
from starlink.physicalplan.expressions.expr import Expression
from starlink.physicalplan.expressions.colexpr import ColumnExpression
from starlink.physicalplan.expressions.castexpr import CastExpression
from starlink.physicalplan.expressions.booleanexpr import (
    AndExpression,
    OrExpression,
    EqExpression,
    NeqExpression,
    GtExpression,
    GtEqExpression,
    LtExpression,
    LtEqExpression,
)
from starlink.physicalplan.expressions.mathexpr import (
    AddExpression,
    SubtractExpression,
    MultiplyExpression,
    DivideExpression,
)
from starlink.physicalplan.expressions.expr import (
    LiteralLongExpression,
    LiteralDoubleExpression,
    LiteralStringExpression,
)
from starlink.physicalplan.expressions.countexpr import CountExpression
from starlink.physicalplan.expressions.sumexpr import SumExpression
from starlink.physicalplan.expressions.maxexpr import MaxExpression
from starlink.physicalplan.expressions.minexpr import MinExpression


class QueryPlanner:
    """Create a physical plan from a logical plan."""

    def create_physical_plan(self, plan: LogicalPlan) -> PhysicalPlan:
        if isinstance(plan, Scan):
            # Convert logical filter expression to physical expression if filter exists
            filter_expr = None
            if plan.filter is not None:
                filter_expr = self.create_physical_expr(plan.filter, plan)
            return ScanExec(plan.data_source, plan.projection, filter_expr)
        if isinstance(plan, Selection):
            input_phys = self.create_physical_plan(plan.input)
            filter_expr = self.create_physical_expr(plan.expr, plan.input)
            return SelectionExec(input_phys, filter_expr)
        if isinstance(plan, Projection):
            input_phys = self.create_physical_plan(plan.input)
            proj_exprs = [self.create_physical_expr(e, plan.input) for e in plan.expr]
            proj_schema = Schema([e.to_field(plan.input) for e in plan.expr])
            return ProjectionExec(input_phys, proj_schema, proj_exprs)
        if isinstance(plan, Aggregate):
            input_phys = self.create_physical_plan(plan.input)
            group_exprs = [self.create_physical_expr(e, plan.input) for e in plan.group_expr]
            aggr_exprs = []
            for aggr in plan.aggregate_expr:
                if isinstance(aggr, Max):
                    aggr_exprs.append(
                        MaxExpression(self.create_physical_expr(aggr.expr, plan.input))
                    )
                elif isinstance(aggr, Min):
                    aggr_exprs.append(
                        MinExpression(self.create_physical_expr(aggr.expr, plan.input))
                    )
                elif isinstance(aggr, Sum):
                    aggr_exprs.append(
                        SumExpression(self.create_physical_expr(aggr.expr, plan.input))
                    )
                elif isinstance(aggr, Count):
                    aggr_exprs.append(
                        CountExpression(self.create_physical_expr(aggr.expr, plan.input))
                    )
                else:
                    raise ValueError(f"Unsupported aggregate function: {aggr}")
            return HashAggregateExec(input_phys, group_exprs, aggr_exprs, plan.schema())
        if isinstance(plan, Join):
            left_phys = self.create_physical_plan(plan.left)
            right_phys = self.create_physical_plan(plan.right)
            return HashJoinExec(
                left_phys,
                right_phys,
                plan.left_on,
                plan.right_on,
                plan.schema(),
                plan.join_type,
            )

        raise ValueError(f"Unsupported logical plan: {type(plan)}")

    def create_physical_expr(self, expr: LogicalExpr, input: LogicalPlan) -> Expression:
        if isinstance(expr, LiteralLong):
            return LiteralLongExpression(expr.n)
        if isinstance(expr, LiteralDouble):
            return LiteralDoubleExpression(expr.n)
        if isinstance(expr, LiteralString):
            return LiteralStringExpression(expr.str)
        if isinstance(expr, ColumnIndex):
            return ColumnExpression(expr.i)
        if isinstance(expr, Alias):
            return self.create_physical_expr(expr.expr, input)
        if isinstance(expr, Column):
            # Find column index by name in the input schema
            names = [f.name for f in input.schema().fields]
            try:
                idx = names.index(expr.name)
            except ValueError:
                raise ValueError(f"No column named '{expr.name}'")
            return ColumnExpression(idx)
        if isinstance(expr, CastExpr):
            return CastExpression(self.create_physical_expr(expr.expr, input), expr.dataType)
        if isinstance(expr, BinaryExpr):
            l = self.create_physical_expr(expr.l, input)
            r = self.create_physical_expr(expr.r, input)
            if isinstance(expr, Eq):
                return EqExpression(l, r)
            if isinstance(expr, Neq):
                return NeqExpression(l, r)
            if isinstance(expr, Gt):
                return GtExpression(l, r)
            if isinstance(expr, GtEq):
                return GtEqExpression(l, r)
            if isinstance(expr, Lt):
                return LtExpression(l, r)
            if isinstance(expr, LtEq):
                return LtEqExpression(l, r)
            if isinstance(expr, And):
                return AndExpression(l, r)
            if isinstance(expr, Or):
                return OrExpression(l, r)
            if isinstance(expr, Add):
                return AddExpression(l, r)
            if isinstance(expr, Subtract):
                return SubtractExpression(l, r)
            if isinstance(expr, Multiply):
                return MultiplyExpression(l, r)
            if isinstance(expr, Divide):
                return DivideExpression(l, r)
            raise ValueError(f"Unsupported binary expression: {expr}")

        print(f"Unsupported logical expression: {expr}")
        raise ValueError(f"Unsupported logical expression: {expr}")
