# /** Abstraction over different implementations of a column vector. */
# interface ColumnVector {
#   fun getType(): ArrowType
#   fun getValue(i: Int): Any?
#   fun size(): Int
# }


from abc import ABC, abstractmethod
from typing import Any

from pyarrow import DataType


class ColumnVector(ABC):
    @abstractmethod
    def get_type(self) -> DataType:
        pass

    @abstractmethod
    def get_value(self, i: int) -> Any:
        pass

    @abstractmethod
    def size(self) -> int:
        pass
