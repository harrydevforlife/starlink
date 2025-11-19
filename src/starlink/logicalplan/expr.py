from abc import ABC, abstractmethod

from starlink.datatypes.schema import Field
from starlink.logicalplan.logical import LogicalPlan


class LogicalExpr(ABC):
    """Logical Expression for use in logical query plans. The logical expression provides information
    needed during the planning phase such as the name and data type of the expression."""

    @abstractmethod
    def to_field(self, input: LogicalPlan) -> Field:
        """Return meta-data about the value that will be produced by this expression when evaluated
        against a particular input."""
        pass
