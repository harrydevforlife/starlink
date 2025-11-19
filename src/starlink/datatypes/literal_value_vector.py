

from typing import Any

from starlink.datatypes.column_vector import ColumnVector
from pyarrow import DataType

class LiteralValueVector(ColumnVector):
    def __init__(self, dataType: DataType, value: Any, size: int):
        self.dataType = dataType
        self.value = value
        self._size = size  # Use _size to avoid shadowing size() method

    def get_type(self) -> DataType:
        return self.dataType

    def get_value(self, i: int) -> Any:
        if i < 0 or i >= self._size:
            raise IndexError(f"Index out of range: {i}")
        return self.value

    def size(self) -> int:
        return self._size
