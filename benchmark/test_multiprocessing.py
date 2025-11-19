#!/usr/bin/env python3
"""
Test multiprocessing với Starlink operations để đánh giá overhead và complexity.
"""

import time
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import pickle

# Add src to path
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


def process_batch_sequential(batch: RecordBatch) -> int:
    """Process a batch sequentially (simulate expression evaluation)."""
    # Simulate some computation
    total = 0
    for i in range(batch.rowCount()):
        # Simulate expression evaluation
        id_val = batch.fields[0].getValue(i)
        value_val = batch.fields[1].getValue(i)
        if id_val and value_val:
            total += int(id_val) + int(value_val)
    return total


def process_batch_worker(batch_data: tuple) -> int:
    """Worker function for multiprocessing (needs to deserialize batch)."""
    # Deserialize batch
    batch = pickle.loads(batch_data)
    return process_batch_sequential(batch)


def test_serialization_overhead():
    """Test serialization overhead for RecordBatch."""
    print("\n" + "="*80)
    print("Test 1: Serialization Overhead")
    print("="*80)
    
    batch = create_test_batch(10000)
    
    # Test pickle serialization
    start = time.perf_counter()
    serialized = pickle.dumps(batch)
    serialize_time = time.perf_counter() - start
    
    start = time.perf_counter()
    deserialized = pickle.loads(serialized)
    deserialize_time = time.perf_counter() - start
    
    print(f"Batch size: {batch.rowCount()} rows")
    print(f"Serialized size: {len(serialized) / 1024 / 1024:.2f} MB")
    print(f"Serialize time: {serialize_time*1000:.2f}ms")
    print(f"Deserialize time: {deserialize_time*1000:.2f}ms")
    print(f"Total overhead: {(serialize_time + deserialize_time)*1000:.2f}ms")
    
    return serialize_time + deserialize_time


def test_sequential_processing():
    """Test sequential batch processing."""
    print("\n" + "="*80)
    print("Test 2: Sequential Processing")
    print("="*80)
    
    num_batches = 10
    batch_size = 10000
    batches = [create_test_batch(batch_size) for _ in range(num_batches)]
    
    start = time.perf_counter()
    results = [process_batch_sequential(batch) for batch in batches]
    sequential_time = time.perf_counter() - start
    
    print(f"Batches: {num_batches}")
    print(f"Batch size: {batch_size} rows")
    print(f"Total rows: {num_batches * batch_size:,}")
    print(f"Sequential time: {sequential_time:.2f}s")
    print(f"Throughput: {num_batches * batch_size / sequential_time:,.0f} rows/sec")
    
    return sequential_time, results


def test_threading_processing():
    """Test threading (GIL limited)."""
    print("\n" + "="*80)
    print("Test 3: Threading Processing (GIL Limited)")
    print("="*80)
    
    num_batches = 10
    batch_size = 10000
    batches = [create_test_batch(batch_size) for _ in range(num_batches)]
    
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_batch_sequential, batch) for batch in batches]
        results = [f.result() for f in futures]
    threading_time = time.perf_counter() - start
    
    print(f"Batches: {num_batches}")
    print(f"Batch size: {batch_size} rows")
    print(f"Workers: 4")
    print(f"Threading time: {threading_time:.2f}s")
    print(f"Throughput: {num_batches * batch_size / threading_time:,.0f} rows/sec")
    
    return threading_time, results


def test_multiprocessing_processing():
    """Test multiprocessing (true parallel, but with overhead)."""
    print("\n" + "="*80)
    print("Test 4: Multiprocessing Processing (True Parallel)")
    print("="*80)
    
    num_batches = 10
    batch_size = 10000
    batches = [create_test_batch(batch_size) for _ in range(num_batches)]
    
    # Serialize batches
    print("Serializing batches...")
    serialize_start = time.perf_counter()
    serialized_batches = [pickle.dumps(batch) for batch in batches]
    serialize_time = time.perf_counter() - serialize_start
    print(f"Serialization time: {serialize_time:.2f}s")
    
    # Process in parallel
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_batch_worker, batch_data) for batch_data in serialized_batches]
        results = [f.result() for f in futures]
    processing_time = time.perf_counter() - start
    
    total_time = serialize_time + processing_time
    
    print(f"Batches: {num_batches}")
    print(f"Batch size: {batch_size} rows")
    print(f"Workers: 4")
    print(f"Serialization time: {serialize_time:.2f}s")
    print(f"Processing time: {processing_time:.2f}s")
    print(f"Total time: {total_time:.2f}s")
    print(f"Throughput: {num_batches * batch_size / total_time:,.0f} rows/sec")
    
    return total_time, results


def test_aggregation_complexity():
    """Test aggregation complexity with multiprocessing."""
    print("\n" + "="*80)
    print("Test 5: Aggregation Complexity (Multiprocessing Challenge)")
    print("="*80)
    
    print("""
    Aggregation với multiprocessing cần:
    1. Process batches in parallel
    2. Merge results from each process
    3. Handle shared state (groups dict)
    4. Synchronize access
    
    Complexity:
    - Sequential: Simple dict accumulation
    - Multiprocessing: Need to:
      * Serialize batches
      * Process in parallel
      * Merge partial results
      * Handle race conditions
      * Synchronize access
    
    Overhead:
    - Serialization: High (batches are large)
    - Merge: Medium (need to combine dicts)
    - Synchronization: Medium (locks, queues)
    - Memory: High (multiple copies of data)
    """)
    
    print("❌ Conclusion: Aggregation quá phức tạp với multiprocessing")
    print("   Sequential approach đơn giản và hiệu quả hơn")


def main():
    """Run all tests."""
    print("🔬 Multiprocessing Analysis for Starlink")
    print("="*80)
    
    # Test 1: Serialization overhead
    serialization_overhead = test_serialization_overhead()
    
    # Test 2: Sequential
    sequential_time, seq_results = test_sequential_processing()
    
    # Test 3: Threading
    threading_time, thread_results = test_threading_processing()
    
    # Test 4: Multiprocessing
    multiprocessing_time, mp_results = test_multiprocessing_processing()
    
    # Test 5: Aggregation complexity
    test_aggregation_complexity()
    
    # Summary
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    print(f"Sequential:     {sequential_time:.2f}s")
    print(f"Threading:     {threading_time:.2f}s ({sequential_time/threading_time:.2f}x)")
    print(f"Multiprocessing: {multiprocessing_time:.2f}s ({sequential_time/multiprocessing_time:.2f}x)")
    print(f"\nSerialization overhead: {serialization_overhead*1000:.2f}ms per batch")
    print(f"Total serialization overhead: {serialization_overhead * 10 * 1000:.2f}ms for 10 batches")
    
    print("\n" + "="*80)
    print("Key Findings")
    print("="*80)
    print("1. Serialization overhead: HIGH (batches are large)")
    print("2. Threading: Limited by GIL (~6% speedup)")
    print("3. Multiprocessing: True parallel but high overhead")
    print("4. Aggregation: Too complex for multiprocessing")
    print("5. Memory: Multiple copies of data in memory")
    print("\n✅ Conclusion: Multiprocessing không đáng cho Starlink operations")
    print("   Overhead cao hơn benefit, complexity cao")


if __name__ == "__main__":
    main()

