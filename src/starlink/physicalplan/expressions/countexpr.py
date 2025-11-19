from typing import Any

from starlink.physicalplan.expressions.expr import Expression, Accumulator
from starlink.physicalplan.expressions.aggexpr import AggregateExpression


class CountExpression(AggregateExpression):
    """Count expression.

    A count expression is an expression that counts the number of rows in a group.
    """

    def __init__(self, expr: Expression):
        self._expr = expr

    def input_expression(self) -> Expression:
        return self._expr

    def create_accumulator(self) -> Accumulator:
        return CountAccumulator()

    def __str__(self) -> str:
        return f"COUNT({self._expr})"


class CountAccumulator(Accumulator):
    """Accumulator for count expression.

    An accumulator for a count expression is a counter that counts the number of rows in a group.
    """

    def __init__(self):
        self.value: int = 0

    def accumulate(self, value: Any):
        self.value += 1

    def final_value(self) -> int:
        return self.value
