
from typing import List, Optional, OrderedDict, Set

from starlink.logicalplan.logical import LogicalPlan
from starlink.logicalplan.select import Selection
from starlink.logicalplan.scan import Scan
from starlink.logicalplan.projection import Projection
from starlink.logicalplan.aggregate import Aggregate
from starlink.logicalplan.join import Join
from starlink.logicalplan.expr import LogicalExpr
from starlink.logicalplan.expressions import And
from starlink.optimizer.optimizer import OptimizerRule, extractColumns


class FilterPushDownRule(OptimizerRule):
    """Filter Push Down Rule (Predicate Pushdown).
    
    Pushes filter predicates down to the scan level, allowing data sources
    to apply filters during reading. This is especially beneficial for:
    - Parquet files: Can skip row groups using statistics
    - CSV files: Can filter rows during reading
    
    The rule pushes Selection nodes down through Projection and Aggregate nodes
    until it reaches a Scan node, where the filter is applied.
    """

    def optimize(self, plan: LogicalPlan) -> LogicalPlan:
        """Optimize the logical plan by pushing filters down to scans."""
        return self._push_down(plan, None)

    def _push_down(self, plan: LogicalPlan, filter_expr: Optional[Selection]) -> LogicalPlan:
        """Recursively push filters down the plan tree.
        
        Args:
            plan: Current logical plan node
            filter_expr: Selection node with filter to push down (if any)
            
        Returns:
            Optimized logical plan with filters pushed down
        """
        if isinstance(plan, Scan):
            # Reached a Scan node - apply the pushed filter
            if filter_expr is not None:
                # Create a new Scan with the filter pushed down
                return Scan(plan.path, plan.data_source, plan.projection, filter_expr.expr)
            else:
                # No filter to push, return scan as-is
                return plan

        if isinstance(plan, Selection):
            # Found a Selection node - extract filter and push it down
            # The filter should be pushed to the input
            input_opt = self._push_down(plan.input, plan)
            # Check if filter was successfully pushed down
            # We need to check recursively if any Scan in the tree has the filter
            if self._has_filter_pushed_down(input_opt):
                # Filter was pushed down, remove this Selection
                return input_opt
            else:
                # Filter couldn't be pushed down (e.g., through Aggregate), keep Selection
                return Selection(input_opt, plan.expr)

        if isinstance(plan, Projection):
            # Projection doesn't block filter pushdown
            # Push filter through projection to the input
            input_opt = self._push_down(plan.input, filter_expr)
            return Projection(input_opt, plan.expr)

        if isinstance(plan, Aggregate):
            # Aggregate blocks filter pushdown for aggregate expressions
            # But we can still push filters that only reference grouping columns
            # For now, we don't push filters through aggregates (they stay above)
            # This is a simplification - in practice, we'd need to analyze
            # which filters can be pushed (those only referencing group columns)
            input_opt = self._push_down(plan.input, None)  # Don't push through aggregate
            return Aggregate(input_opt, plan.group_expr, plan.aggregate_expr)

        if isinstance(plan, Join):
            return self._push_down_join(plan, filter_expr)

        # For other plan types, don't push filters (they might transform data)
        # Just recursively optimize children
        raise ValueError(f"FilterPushDownRule does not support plan: {plan}")
    
    def _has_filter_pushed_down(self, plan: LogicalPlan) -> bool:
        """Check if a filter has been pushed down to any Scan in the plan tree.
        
        Args:
            plan: Logical plan to check
            
        Returns:
            True if any Scan in the tree has a filter
        """
        if isinstance(plan, Scan):
            return plan.filter is not None
        elif isinstance(plan, Projection):
            return self._has_filter_pushed_down(plan.input)
        elif isinstance(plan, Selection):
            return self._has_filter_pushed_down(plan.input)
        elif isinstance(plan, Aggregate):
            return self._has_filter_pushed_down(plan.input)
        elif isinstance(plan, Join):
            return self._has_filter_pushed_down(plan.left) or self._has_filter_pushed_down(plan.right)
        else:
            return False

    def _push_down_join(self, plan: Join, filter_expr: Optional[Selection]) -> LogicalPlan:
        """Handle pushing filters through join nodes.

        A filter above a join can be pushed to one or both sides when its
        predicates reference columns from only that side. Residual predicates
        referencing both sides remain above the join.
        """
        left_filters: List[LogicalExpr] = []
        right_filters: List[LogicalExpr] = []
        residual_filters: List[LogicalExpr] = []

        if filter_expr is not None:
            conjuncts = self._split_conjuncts(filter_expr.expr)
            left_columns = {field.name for field in plan.left.schema().fields}
            right_columns = {field.name for field in plan.right.schema().fields}

            for predicate in conjuncts:
                predicate_columns = self._collect_columns(predicate, plan)
                if predicate_columns and predicate_columns.issubset(left_columns):
                    left_filters.append(predicate)
                elif predicate_columns and predicate_columns.issubset(right_columns):
                    right_filters.append(predicate)
                else:
                    residual_filters.append(predicate)

        left_selection = self._combine_conjuncts(left_filters)
        right_selection = self._combine_conjuncts(right_filters)
        residual_selection = self._combine_conjuncts(residual_filters)

        left_plan = plan.left
        right_plan = plan.right

        left_plan = self._push_down(
            left_plan,
            Selection(left_plan, left_selection) if left_selection is not None else None,
        )
        right_plan = self._push_down(
            right_plan,
            Selection(right_plan, right_selection) if right_selection is not None else None,
        )

        new_join = Join(left_plan, right_plan, plan.left_on, plan.right_on, plan.join_type)

        if residual_selection is not None:
            return Selection(new_join, residual_selection)
        return new_join

    def _split_conjuncts(self, expr: LogicalExpr) -> List[LogicalExpr]:
        """Split a predicate into a list of conjunctive predicates."""
        if isinstance(expr, And):
            return self._split_conjuncts(expr.left) + self._split_conjuncts(expr.right)
        return [expr]

    def _combine_conjuncts(self, predicates: List[LogicalExpr]) -> Optional[LogicalExpr]:
        """Combine predicates into a single AND expression."""
        if not predicates:
            return None
        expr = predicates[0]
        for predicate in predicates[1:]:
            expr = And(expr, predicate)
        return expr

    def _collect_columns(self, expr: LogicalExpr, plan: LogicalPlan) -> Set[str]:
        """Collect column names referenced by an expression."""
        accum: OrderedDict[str, None] = OrderedDict()
        extractColumns([expr], plan, accum)
        return set(accum.keys())

