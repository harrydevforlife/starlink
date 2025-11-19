from abc import ABC, abstractmethod
from typing import List

from starlink.datatypes.schema import Schema


class LogicalPlan(ABC):
    """A logical plan represents a data transformation or action producing a relation."""

    @abstractmethod
    def schema(self) -> Schema:
        """Return the output schema of this logical plan."""
        pass

    @abstractmethod
    def children(self) -> List["LogicalPlan"]:
        """Return child plans (inputs) of this logical plan."""
        pass

    def pretty(self) -> str:
        return format_plan(self)


def format_plan(plan: "LogicalPlan", indent: int = 0) -> str:
    """Format a logical plan tree in human-readable form."""
    prefix = "\t" * indent
    s = f"{prefix}{plan}\n"
    for child in plan.children():
        s += format_plan(child, indent + 1)
    return s
