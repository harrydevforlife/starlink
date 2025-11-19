"""Helper to build PyArrow arrays using a pre-sized Python list."""

from typing import Any, List, Optional

import pyarrow as pa

from starlink.datatypes.arrow_field_vector import ArrowFieldVector


class ArrowVectorBuilder:
    def __init__(self, arrow_type: pa.DataType):
        self._type: pa.DataType = arrow_type
        self._values: Optional[List[Any]] = None

    def set(self, i: int, value: Any) -> None:
        if self._values is None:
            raise RuntimeError("Call set_value_count(n) before setting values")
        if i < 0 or i >= len(self._values):
            raise IndexError(f"Index out of range: {i}")

        t = self._type
        if pa.types.is_string(t):
            if value is None:
                coerced = None
            elif isinstance(value, (bytes, bytearray)):
                coerced = value.decode("utf-8")
            else:
                coerced = str(value)
        elif pa.types.is_int8(t):
            coerced = None if value is None else int(value)
        elif pa.types.is_int16(t):
            coerced = None if value is None else int(value)
        elif pa.types.is_int32(t):
            coerced = None if value is None else int(value)
        elif pa.types.is_int64(t):
            coerced = None if value is None else int(value)
        elif pa.types.is_uint8(t):
            coerced = None if value is None else int(value)
        elif pa.types.is_uint16(t):
            coerced = None if value is None else int(value)
        elif pa.types.is_uint32(t):
            coerced = None if value is None else int(value)
        elif pa.types.is_uint64(t):
            coerced = None if value is None else int(value)
        elif pa.types.is_float32(t):
            coerced = None if value is None else float(value)
        elif pa.types.is_float64(t):
            coerced = None if value is None else float(value)
        elif pa.types.is_boolean(t):
            coerced = None if value is None else bool(value)
        else:
            # Fallback: let pyarrow attempt conversion
            coerced = value

        self._values[i] = coerced

    def set_value_count(self, n: int) -> None:
        if n < 0:
            raise ValueError("n must be >= 0")
        self._values = [None] * n

    def build(self) -> ArrowFieldVector:
        if self._values is None:
            # If never sized, consider empty
            arr = pa.array([], type=self._type)
        else:
            arr = pa.array(self._values, type=self._type)
        return ArrowFieldVector(arr)
