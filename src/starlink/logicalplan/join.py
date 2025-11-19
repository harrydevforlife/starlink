from typing import List

from starlink.datatypes.schema import Schema, Field
from starlink.logicalplan.logical import LogicalPlan


class Join(LogicalPlan):
    """Logical plan node representing a join."""

    def __init__(
        self,
        left: LogicalPlan,
        right: LogicalPlan,
        left_on: List[str],
        right_on: List[str],
        join_type: str = "inner",
    ):
        if len(left_on) != len(right_on):
            raise ValueError("left_on and right_on must have the same length")
        self.left = left
        self.right = right
        self.left_on = left_on
        self.right_on = right_on
        self.join_type = join_type.lower()

        if self.join_type != "inner":
            raise ValueError(f"Unsupported join type: {join_type}")

        self._schema = self._build_schema()

    def _build_schema(self) -> Schema:
        fields: List[Field] = []
        existing_names = set()

        for field in self.left.schema().fields:
            fields.append(Field(field.name, field.dataType))
            existing_names.add(field.name)

        for field in self.right.schema().fields:
            name = field.name
            if name in existing_names:
                suffix = 1
                new_name = f"{name}_right"
                while new_name in existing_names:
                    suffix += 1
                    new_name = f"{name}_right{suffix}"
                name = new_name
            fields.append(Field(name, field.dataType))
            existing_names.add(name)

        return Schema(fields)

    def schema(self) -> Schema:
        return self._schema

    def children(self) -> List[LogicalPlan]:
        return [self.left, self.right]

    def __str__(self) -> str:
        return f"Join: type={self.join_type}, left_on={self.left_on}, right_on={self.right_on}"

