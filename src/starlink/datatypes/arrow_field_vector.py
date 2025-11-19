from typing import Any, Protocol

import pyarrow as pa

from starlink.datatypes.arrow_types import ArrowTypes
from starlink.datatypes.column_vector import ColumnVector


class FieldVectorLike(Protocol):
    """Protocol for PyArrow array-like types."""

    @property
    def type(self) -> pa.DataType:
        """Return the data type of the array."""
        ...

    def is_null(self) -> pa.Array:
        """Return a boolean array indicating null values."""
        ...

    def __len__(self) -> int:
        """Return the length of the array."""
        ...

    def __getitem__(self, index: int) -> Any:
        """Get value at index."""
        ...


class FieldVectorFactory:
    @staticmethod
    def create(arrow_type: pa.DataType, initial_capacity: int = 0) -> pa.Array:
        """Create a pyarrow Array with the given type and optional initial capacity.

        Since pyarrow Arrays are immutable, we initialize an array of the
        requested length filled with nulls. If initial_capacity is 0, an empty
        array is returned.
        """
        if initial_capacity < 0:
            raise ValueError("initial_capacity must be >= 0")
        if initial_capacity == 0:
            return pa.array([], type=arrow_type)
        # Create a sequence of Nones of the requested length and cast to type
        return pa.array([None] * initial_capacity, type=arrow_type)


class ArrowFieldVector(ColumnVector):
    """Wrapper around Arrow FieldVector/Array."""

    def __init__(self, field: FieldVectorLike):
        """Initialize with a PyArrow Array or ChunkedArray."""
        self.field = field

    def get_type(self) -> pa.DataType:
        """Return the ArrowType based on the array type."""
        # Get the actual type from the field
        # For ChunkedArray, get type from first chunk
        if isinstance(self.field, pa.Array):
            array_type = self.field.type
        else:
            array_type = self.field.chunks[0].type

        # Map PyArrow types to ArrowTypes
        if pa.types.is_boolean(array_type):
            return ArrowTypes.BooleanType
        elif pa.types.is_int8(array_type):
            return ArrowTypes.Int8Type
        elif pa.types.is_int16(array_type):
            return ArrowTypes.Int16Type
        elif pa.types.is_int32(array_type):
            return ArrowTypes.Int32Type
        elif pa.types.is_int64(array_type):
            return ArrowTypes.Int64Type
        elif pa.types.is_float32(array_type):
            return ArrowTypes.FloatType
        elif pa.types.is_float64(array_type):
            return ArrowTypes.DoubleType
        elif pa.types.is_string(array_type):
            return ArrowTypes.StringType
        else:
            raise ValueError(f"Unsupported Arrow type: {array_type}")

    def get_value(self, i: int) -> Any:
        """Get value at index ``i``."""
        # Get the array and index (handle ChunkedArray)
        if isinstance(self.field, pa.ChunkedArray):
            index = i
            for chunk in self.field.chunks:
                if index < len(chunk):
                    array = chunk
                    break
                index -= len(chunk)
            else:
                raise IndexError(f"Index out of range: {i}")
        else:
            array = self.field
            index = i

        # Step 1: check for null values
        if array.is_null()[index]:
            return None

        # Step 2: convert the value based on type
        array_type = array.type

        if pa.types.is_boolean(array_type):
            # Boolean values can be read directly from the scalar
            scalar = array[index]
            value = scalar.as_py()
            # Ensure we return proper boolean (True/False, not 1/0)
            return bool(value) if value is not None else None
        elif pa.types.is_int8(array_type):
            # TinyIntVector -> field.get(i)
            return array[index].as_py()
        elif pa.types.is_int16(array_type):
            # SmallIntVector -> field.get(i)
            return array[index].as_py()
        elif pa.types.is_int32(array_type):
            # IntVector -> field.get(i)
            return array[index].as_py()
        elif pa.types.is_int64(array_type):
            # BigIntVector -> field.get(i)
            return array[index].as_py()
        elif pa.types.is_float32(array_type):
            # Float4Vector -> field.get(i)
            return array[index].as_py()
        elif pa.types.is_float64(array_type):
            # Float8Vector -> field.get(i)
            return array[index].as_py()
        elif pa.types.is_string(array_type):
            value = array[index].as_py()
            if value is None:
                return None
            # PyArrow already returns strings, but ensure it's a proper string
            return str(value)
        else:
            raise ValueError(f"Unsupported Arrow type: {array_type}")

    def size(self) -> int:
        """Return the number of elements in the array."""
        return len(self.field)
