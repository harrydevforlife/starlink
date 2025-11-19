# #

from abc import ABC, abstractmethod

from starlink.physicalplan.expressions.expr import Expression
from starlink.physicalplan.expressions.expr import Accumulator

class AggregateExpression(ABC):
    """Aggregate expression.

    An aggregate expression is an expression that aggregates data over a group of rows.
    """

    @abstractmethod
    def input_expression(self) -> Expression:
        pass

    @abstractmethod
    def create_accumulator(self) -> Accumulator:
        pass
