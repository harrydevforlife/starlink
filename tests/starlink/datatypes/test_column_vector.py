
import pyarrow as pa
import pytest

from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.arrow_vector_builder import ArrowVectorBuilder


def test_build_int_vector():
    size = 10
    builder = ArrowVectorBuilder(pa.int32())
    builder.set_value_count(size)
    for i in range(size):
        builder.set(i, int(i))
    v: ArrowFieldVector = builder.build()
    assert v.size() == size
    for i in range(v.size()):
        assert v.get_value(i) == int(i)
