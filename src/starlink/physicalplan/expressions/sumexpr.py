from typing import Any

from starlink.physicalplan.expressions.expr import Expression, Accumulator
from starlink.physicalplan.expressions.aggexpr import AggregateExpression


class SumExpression(AggregateExpression):
    def __init__(self, expr: Expression):
        self._expr = expr

    def input_expression(self) -> Expression:
        return self._expr

    def create_accumulator(self) -> Accumulator:
        return SumAccumulator()

    def __str__(self) -> str:
        return f"SUM({self._expr})"


class SumAccumulator(Accumulator):
    def __init__(self):
        self.value: Any = None

    def accumulate(self, value: Any):
        if value is None:
            return
        # Initialize on first value
        if self.value is None:
            if isinstance(value, (int, float)):
                self.value = value
                return
            raise NotImplementedError(f"SUM is not implemented for type: {type(value)}")

        # Numeric-only accumulation; support mixed int/float by promoting to float
        if isinstance(self.value, (int, float)) and isinstance(value, (int, float)):
            self.value = (float(self.value) if isinstance(self.value, float) or isinstance(value, float) else self.value) + value
            return

        raise NotImplementedError(
            f"SUM is not implemented for types: {type(self.value)} and {type(value)}"
        )

    def final_value(self) -> Any:
        return self.value

