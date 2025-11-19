
import pyarrow as pa

class ArrowTypes:
    BooleanType = pa.bool_()
    Int8Type = pa.int8()
    Int16Type = pa.int16()
    Int32Type = pa.int32()
    Int64Type = pa.int64()
    UInt8Type = pa.uint8()
    UInt16Type = pa.uint16()
    UInt32Type = pa.uint32()
    UInt64Type = pa.uint64()
    FloatType = pa.float32()
    DoubleType = pa.float64()
    StringType = pa.string()
