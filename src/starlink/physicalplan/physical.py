
from abc import ABC, abstractmethod
from typing import List, Sequence

from starlink.datatypes.schema import Schema
from starlink.datatypes.record_batch import RecordBatch


class PhysicalPlan(ABC):
    """Executable physical plan that produces data as a series of record batches."""

    @abstractmethod
    def schema(self) -> Schema:
        pass

    @abstractmethod
    def execute(self) -> Sequence[RecordBatch]:
        """Execute plan and produce a sequence (iterator/generator) of RecordBatch."""
        pass

    @abstractmethod
    def children(self) -> List["PhysicalPlan"]:
        pass

    def pretty(self) -> str:
        return format_physical(self)


def format_physical(plan: "PhysicalPlan", indent: int = 0) -> str:
    prefix = "\t" * indent
    s = f"{prefix}{plan}\n"
    for child in plan.children():
        s += format_physical(child, indent + 1)
    return s
