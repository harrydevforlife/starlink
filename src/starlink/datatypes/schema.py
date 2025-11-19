

from typing import List

import pyarrow as pa
from pyarrow import DataType


def _format_arrow_type(dtype: DataType) -> str:
    """Map a PyArrow type to the corresponding ArrowTypes constant."""
    if pa.types.is_float64(dtype):
        return "FloatingPoint(DOUBLE)"
    elif pa.types.is_float32(dtype):
        return "FloatingPoint(SINGLE)"
    elif pa.types.is_int8(dtype):
        return f"Int(8, {not pa.types.is_unsigned_integer(dtype)})"
    elif pa.types.is_int16(dtype):
        return f"Int(16, {not pa.types.is_unsigned_integer(dtype)})"
    elif pa.types.is_int32(dtype):
        return f"Int(32, {not pa.types.is_unsigned_integer(dtype)})"
    elif pa.types.is_int64(dtype):
        return f"Int(64, {not pa.types.is_unsigned_integer(dtype)})"
    elif pa.types.is_uint8(dtype):
        return "Int(8, false)"
    elif pa.types.is_uint16(dtype):
        return "Int(16, false)"
    elif pa.types.is_uint32(dtype):
        return "Int(32, false)"
    elif pa.types.is_uint64(dtype):
        return "Int(64, false)"
    elif pa.types.is_boolean(dtype):
        return "Bool()"
    elif pa.types.is_string(dtype):
        return "Utf8()"
    else:
        return str(dtype)


class Field:
    def __init__(self, name: str, dataType: DataType):
        self.name = name
        self.dataType = dataType

    def toArrow(self) -> pa.Field:
        return pa.field(self.name, self.dataType)

    def __str__(self) -> str:
        return f"Field(name={self.name}, dataType={self.dataType})"

class Schema:
    def __init__(self, fields: List[Field]):
        self.fields = fields

    def toArrow(self) -> pa.Schema:
        return pa.schema([field.toArrow() for field in self.fields])

    def project(self, indices: List[int]) -> "Schema":
        return Schema([field for i, field in enumerate(self.fields) if i in indices])

    def select(self, names: List[str]) -> "Schema":
        return Schema([field for field in self.fields if field.name in names])

    def __str__(self) -> str:
        fields_str = ", ".join(str(field) for field in self.fields)
        return f"Schema(fields=[{fields_str}])"

    def __repr__(self) -> str:
        return f"Schema(fields={self.fields})"


def fromArrow(arrow_schema: pa.Schema) -> Schema:
    return Schema([Field(field.name, field.type) for field in arrow_schema])
