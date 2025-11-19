from typing import List

from starlink.datatypes.column_vector import ColumnVector
from starlink.datatypes.schema import Schema


class RecordBatch:
    def __init__(self, schema: Schema, fields: List[ColumnVector]):
        self.schema = schema
        self.fields = fields

    def row_count(self) -> int:
        return self.fields[0].size()

    def column_count(self) -> int:
        return len(self.fields)

    def field(self, i: int) -> ColumnVector:
        return self.fields[i]

    def to_csv(self) -> str:
        """Convert RecordBatch to CSV format."""
        lines = []
        row_count = self.row_count()
        column_count = self.column_count()

        for row_index in range(row_count):
            row_values = []
            for column_index in range(column_count):
                v = self.fields[column_index]
                value = v.get_value(row_index)
                if value is None:
                    row_values.append("null")
                elif isinstance(value, bytes):
                    row_values.append(value.decode("utf-8"))
                else:
                    row_values.append(str(value))
            lines.append(",".join(row_values))

        return "\n".join(lines) + "\n" if lines else ""

    def __str__(self) -> str:
        return self.to_csv()

    def __repr__(self) -> str:
        return f"RecordBatch(schema={self.schema}, fields={self.fields})"
