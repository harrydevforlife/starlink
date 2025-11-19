

from typing import List, Set, OrderedDict

from starlink.logicalplan.logical import LogicalPlan
from starlink.logicalplan.projection import Projection
from starlink.logicalplan.select import Selection
from starlink.logicalplan.aggregate import Aggregate
from starlink.logicalplan.scan import Scan
from starlink.logicalplan.join import Join
from starlink.optimizer.optimizer import OptimizerRule, extractColumns


class ProjectionPushDownRule(OptimizerRule):
    """Projection Push Down Rule.

    Push down the projection to the scan automatically.
    This is a simple rule that does not consider the cost of the projection.
    It is used to optimize the query plan.
    """

    def optimize(self, plan: LogicalPlan) -> LogicalPlan:
        # Use OrderedDict to preserve insertion order of column names
        # This ensures projection order is maintained
        return self._push_down(plan, OrderedDict())

    def _push_down(self, plan: LogicalPlan, columnNames: OrderedDict) -> LogicalPlan:
        if isinstance(plan, Projection):
            extractColumns(plan.expr, plan.input, columnNames)
            input_opt = self._push_down(plan.input, columnNames)
            return Projection(input_opt, plan.expr)

        if isinstance(plan, Selection):
            extractColumns([plan.expr], plan.input, columnNames)
            input_opt = self._push_down(plan.input, columnNames)
            return Selection(input_opt, plan.expr)

        if isinstance(plan, Aggregate):
            extractColumns(plan.group_expr, plan.input, columnNames)
            # extract input expressions of aggregates
            aggr_inputs = [aggr.expr for aggr in plan.aggregate_expr]
            extractColumns(aggr_inputs, plan.input, columnNames)
            input_opt = self._push_down(plan.input, columnNames)
            return Aggregate(input_opt, plan.group_expr, plan.aggregate_expr)

        if isinstance(plan, Scan):
            # Extract columns from filter expression if filter exists (from filter pushdown)
            if plan.filter is not None:
                extractColumns([plan.filter], plan, columnNames)
            
            valid_names = {f.name for f in plan.data_source.schema().fields}
            # Preserve order of columnNames (don't sort) to maintain projection order
            # Use list(columnNames.keys()) to preserve insertion order
            pushdown = [name for name in columnNames.keys() if name in valid_names]
            # Preserve filter if it exists (from filter pushdown)
            return Scan(plan.path, plan.data_source, pushdown, plan.filter)

        if isinstance(plan, Join):
            return self._push_down_join(plan, columnNames)

        # if isinstance(plan, Scan):
        #     valid_names = {f.name for f in plan.dataSource.schema().fields}
        #     # Filter and sort inputs consistently
        #     # Note: Sorting is for optimization display only; execution still respects logical plan order
        #     pushdown = sorted([name for name in columnNames.keys() if name in valid_names])
        #     return Scan(plan.path, plan.dataSource, pushdown)



        raise ValueError(f"ProjectionPushDownRule does not support plan: {plan}")

    def _push_down_join(self, plan: Join, columnNames: OrderedDict) -> LogicalPlan:
        """Distribute required columns to the left and right sides of a join."""
        if len(columnNames) == 0:
            # Nothing to project from parent; keep both sides intact
            left_opt = self._push_down(plan.left, OrderedDict())
            right_opt = self._push_down(plan.right, OrderedDict())
            return Join(left_opt, right_opt, plan.left_on, plan.right_on, plan.join_type)

        left_required = OrderedDict()
        right_required = OrderedDict()

        left_fields = [field.name for field in plan.left.schema().fields]
        right_fields = [field.name for field in plan.right.schema().fields]
        final_fields = [field.name for field in plan.schema().fields]

        left_final_names = set(final_fields[: len(left_fields)])
        right_final_names = final_fields[len(left_fields) :]

        if len(right_fields) != len(right_final_names):
            raise ValueError("Join schema mismatch while distributing projection pushdown")

        right_final_to_original = dict(zip(right_final_names, right_fields))

        for name in columnNames.keys():
            if name in left_final_names and name not in left_required:
                left_required[name] = None
            elif name in right_final_to_original:
                original = right_final_to_original[name]
                if original not in right_required:
                    right_required[original] = None

        for key in plan.left_on:
            if key not in left_required:
                left_required[key] = None
        for key in plan.right_on:
            if key not in right_required:
                right_required[key] = None

        left_opt = self._push_down(plan.left, left_required)
        right_opt = self._push_down(plan.right, right_required)

        return Join(left_opt, right_opt, plan.left_on, plan.right_on, plan.join_type)
