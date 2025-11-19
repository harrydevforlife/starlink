from typing import Any

from starlink.physicalplan.expressions.expr import Expression, Accumulator
from starlink.physicalplan.expressions.aggexpr import AggregateExpression


class MaxExpression(AggregateExpression):
    def __init__(self, expr: Expression):
        self._expr = expr

    def input_expression(self) -> Expression:
        return self._expr

    def create_accumulator(self) -> Accumulator:
        return MaxAccumulator()

    def __str__(self) -> str:
        return f"MAX({self._expr})"


class MaxAccumulator(Accumulator):
    def __init__(self):
        self.value: Any = None

    def accumulate(self, value: Any):
        if value is None:
            return
        if self.value is None:
            self.value = value
            return
        # Compare supported scalar types
        if isinstance(value, (int, float)) and isinstance(self.value, (int, float)):
            if value > self.value:
                self.value = value
            return
        if isinstance(value, str) and isinstance(self.value, str):
            if value > self.value:
                self.value = value
            return
        # For mixed numeric types (e.g., int vs float), compare numerically
        if isinstance(value, (int, float)) and isinstance(self.value, (int, float)):
            if float(value) > float(self.value):
                self.value = value
            return
        raise NotImplementedError(
            f"MAX is not implemented for types: {type(value)} and {type(self.value)}"
        )

    def final_value(self) -> Any:
        return self.value

