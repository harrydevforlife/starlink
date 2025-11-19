#!/usr/bin/env python3
"""Test PyArrow IPC stream cho multiprocessing - so sánh với pickle."""

import time
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import pickle

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pyarrow as pa
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.schema import Schema, Field


def create_test_batch(size: int = 10000) -> RecordBatch:
    """Create a test RecordBatch."""
    schema = Schema([
        Field("id", pa.int64()),
        Field("value", pa.float64()),
        Field("name", pa.string())
    ])
    
    vectors = [
        ArrowFieldVector(pa.array(range(size), type=pa.int64())),
        ArrowFieldVector(pa.array([float(i) * 1.5 for i in range(size)], type=pa.float64())),
        ArrowFieldVector(pa.array([f"name_{i}" for i in range(size)], type=pa.string()))
    ]
    
    return RecordBatch(schema, vectors)


def record_batch_to_pyarrow_batch(rb: RecordBatch) -> pa.RecordBatch:
    """Convert Starlink RecordBatch to PyArrow RecordBatch."""
    arrays = [vec.field for vec in rb.fields]
    pa_schema = pa.schema([pa.field(f.name, f.dataType) for f in rb.schema.fields])
    return pa.RecordBatch.from_arrays(arrays, schema=pa_schema)


def pyarrow_batch_to_record_batch(pa_batch: pa.RecordBatch) -> RecordBatch:
    """Convert PyArrow RecordBatch to Starlink RecordBatch."""
    schema = Schema([Field(f.name, f.type) for f in pa_batch.schema])
    vectors = [ArrowFieldVector(col) for col in pa_batch.columns]
    return RecordBatch(schema, vectors)


def serialize_with_pickle(batch: RecordBatch) -> bytes:
    """Serialize RecordBatch using pickle."""
    return pickle.dumps(batch)


def deserialize_with_pickle(data: bytes) -> RecordBatch:
    """Deserialize RecordBatch using pickle."""
    return pickle.loads(data)


def serialize_with_ipc(batch: RecordBatch) -> bytes:
    """Serialize RecordBatch using PyArrow IPC format."""
    pa_batch = record_batch_to_pyarrow_batch(batch)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, pa_batch.schema) as writer:
        writer.write_batch(pa_batch)
    return sink.getvalue().to_pybytes()


def deserialize_with_ipc(data: bytes) -> RecordBatch:
    """Deserialize RecordBatch using PyArrow IPC format."""
    reader = pa.ipc.open_stream(data)
    pa_batch = reader.read_next_batch()
    return pyarrow_batch_to_record_batch(pa_batch)


def process_batch_sequential(batch: RecordBatch) -> int:
    """Process a batch sequentially."""
    total = 0
    for i in range(batch.rowCount()):
        id_val = batch.fields[0].getValue(i)
        value_val = batch.fields[1].getValue(i)
        if id_val and value_val:
            total += int(id_val) + int(value_val)
    return total


def process_batch_worker_pickle(batch_data: bytes) -> int:
    """Worker function using pickle."""
    batch = deserialize_with_pickle(batch_data)
    return process_batch_sequential(batch)


def process_batch_worker_ipc(batch_data: bytes) -> int:
    """Worker function using PyArrow IPC."""
    batch = deserialize_with_ipc(batch_data)
    return process_batch_sequential(batch)


def test_serialization_comparison():
    """Compare pickle vs PyArrow IPC serialization."""
    print("\n" + "="*80)
    print("Test 1: Serialization Comparison (Pickle vs PyArrow IPC)")
    print("="*80)
    
    batch = create_test_batch(10000)
    
    # Test pickle
    print("\n📦 Pickle:")
    start = time.perf_counter()
    pickle_data = serialize_with_pickle(batch)
    pickle_serialize_time = time.perf_counter() - start
    
    start = time.perf_counter()
    pickle_batch = deserialize_with_pickle(pickle_data)
    pickle_deserialize_time = time.perf_counter() - start
    
    print(f"  Serialize time: {pickle_serialize_time*1000:.2f}ms")
    print(f"  Deserialize time: {pickle_deserialize_time*1000:.2f}ms")
    print(f"  Total time: {(pickle_serialize_time + pickle_deserialize_time)*1000:.2f}ms")
    print(f"  Size: {len(pickle_data) / 1024 / 1024:.2f} MB")
    
    # Test PyArrow IPC
    print("\n🚀 PyArrow IPC:")
    start = time.perf_counter()
    ipc_data = serialize_with_ipc(batch)
    ipc_serialize_time = time.perf_counter() - start
    
    start = time.perf_counter()
    ipc_batch = deserialize_with_ipc(ipc_data)
    ipc_deserialize_time = time.perf_counter() - start
    
    print(f"  Serialize time: {ipc_serialize_time*1000:.2f}ms")
    print(f"  Deserialize time: {ipc_deserialize_time*1000:.2f}ms")
    print(f"  Total time: {(ipc_serialize_time + ipc_deserialize_time)*1000:.2f}ms")
    print(f"  Size: {len(ipc_data) / 1024 / 1024:.2f} MB")
    
    # Comparison
    print("\n📊 Comparison:")
    pickle_total = pickle_serialize_time + pickle_deserialize_time
    ipc_total = ipc_serialize_time + ipc_deserialize_time
    speedup = pickle_total / ipc_total if ipc_total > 0 else 0
    
    print(f"  Pickle total: {pickle_total*1000:.2f}ms")
    print(f"  IPC total: {ipc_total*1000:.2f}ms")
    print(f"  IPC speedup: {speedup:.2f}x")
    print(f"  Size ratio: {len(pickle_data) / len(ipc_data) if len(ipc_data) > 0 else 0:.2f}x")
    
    return pickle_total, ipc_total, speedup


def test_multiprocessing_with_ipc():
    """Test multiprocessing with PyArrow IPC."""
    print("\n" + "="*80)
    print("Test 2: Multiprocessing với PyArrow IPC")
    print("="*80)
    
    num_batches = 10
    batch_size = 10000
    batches = [create_test_batch(batch_size) for _ in range(num_batches)]
    
    # Test with pickle
    print("\n📦 Multiprocessing với Pickle:")
    serialize_start = time.perf_counter()
    pickle_data = [serialize_with_pickle(batch) for batch in batches]
    pickle_serialize_time = time.perf_counter() - serialize_start
    
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_batch_worker_pickle, data) for data in pickle_data]
        pickle_results = [f.result() for f in futures]
    pickle_process_time = time.perf_counter() - start
    
    pickle_total = pickle_serialize_time + pickle_process_time
    
    print(f"  Serialize time: {pickle_serialize_time:.2f}s")
    print(f"  Process time: {pickle_process_time:.2f}s")
    print(f"  Total time: {pickle_total:.2f}s")
    
    # Test with IPC
    print("\n🚀 Multiprocessing với PyArrow IPC:")
    serialize_start = time.perf_counter()
    ipc_data = [serialize_with_ipc(batch) for batch in batches]
    ipc_serialize_time = time.perf_counter() - serialize_start
    
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_batch_worker_ipc, data) for data in ipc_data]
        ipc_results = [f.result() for f in futures]
    ipc_process_time = time.perf_counter() - start
    
    ipc_total = ipc_serialize_time + ipc_process_time
    
    print(f"  Serialize time: {ipc_serialize_time:.2f}s")
    print(f"  Process time: {ipc_process_time:.2f}s")
    print(f"  Total time: {ipc_total:.2f}s")
    
    # Comparison
    print("\n📊 Comparison:")
    speedup = pickle_total / ipc_total if ipc_total > 0 else 0
    print(f"  Pickle total: {pickle_total:.2f}s")
    print(f"  IPC total: {ipc_total:.2f}s")
    print(f"  IPC speedup: {speedup:.2f}x")
    
    assert pickle_results == ipc_results, "Results should match!"
    print(f"  ✅ Results match: {pickle_results == ipc_results}")
    
    return pickle_total, ipc_total, speedup


def main():
    """Run all tests."""
    print("🔬 PyArrow IPC Analysis for Multiprocessing")
    print("="*80)
    
    # Test 1: Serialization comparison
    pickle_total, ipc_total, speedup = test_serialization_comparison()
    
    # Test 2: Multiprocessing comparison
    pickle_mp_total, ipc_mp_total, mp_speedup = test_multiprocessing_with_ipc()
    
    # Summary
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    print(f"Serialization speedup: {speedup:.2f}x")
    print(f"Multiprocessing speedup: {mp_speedup:.2f}x")
    
    print("\n" + "="*80)
    print("Key Findings")
    print("="*80)
    if speedup > 2:
        print("✅ PyArrow IPC nhanh hơn đáng kể so với pickle!")
        print("✅ Có thể làm multiprocessing khả thi hơn")
    else:
        print("⚠️ PyArrow IPC nhanh hơn nhưng cần đánh giá thêm")
    
    print("\n💡 Considerations:")
    print("1. IPC format được thiết kế cho Arrow data (zero-copy trong nhiều cases)")
    print("2. Vẫn cần convert Starlink RecordBatch ↔ PyArrow RecordBatch")
    print("3. Aggregation vẫn phức tạp (cần merge logic)")
    print("4. Memory overhead vẫn tồn tại (multiple copies)")
    print("5. Complexity vẫn cao (error handling, resource management)")


if __name__ == "__main__":
    main()

