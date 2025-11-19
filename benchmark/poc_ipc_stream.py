#!/usr/bin/env python3
"""
POC: Starlink với PyArrow IPC Stream

Test PyArrow IPC stream với Starlink operations để đánh giá:
1. Serialization/deserialization performance
2. Multiprocessing với IPC
3. Real-world operations (filter, projection, aggregation)
4. Memory usage
"""

import time
import sys
import pickle
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pyarrow as pa
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.schema import Schema, Field
from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, lit, Sum, Max, cast, Gt, Eq


# ============================================================================
# IPC Stream Utilities
# ============================================================================

def record_batch_to_pyarrow_batch(rb: RecordBatch) -> pa.RecordBatch:
    """Convert Starlink RecordBatch to PyArrow RecordBatch for IPC."""
    arrays = [vec.field for vec in rb.fields]
    pa_schema = pa.schema([pa.field(f.name, f.dataType) for f in rb.schema.fields])
    return pa.RecordBatch.from_arrays(arrays, schema=pa_schema)


def pyarrow_batch_to_record_batch(pa_batch: pa.RecordBatch) -> RecordBatch:
    """Convert PyArrow RecordBatch back to Starlink RecordBatch."""
    schema = Schema([Field(f.name, f.type) for f in pa_batch.schema])
    vectors = [ArrowFieldVector(col) for col in pa_batch.columns]
    return RecordBatch(schema, vectors)


def serialize_batch_ipc(batch: RecordBatch) -> bytes:
    """Serialize RecordBatch using PyArrow IPC stream format.
    
    Returns:
        bytes: Serialized batch in IPC format
    """
    pa_batch = record_batch_to_pyarrow_batch(batch)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, pa_batch.schema) as writer:
        writer.write_batch(pa_batch)
    return sink.getvalue().to_pybytes()


def deserialize_batch_ipc(data: bytes) -> RecordBatch:
    """Deserialize RecordBatch from PyArrow IPC stream format.
    
    Args:
        data: Serialized batch in IPC format
        
    Returns:
        RecordBatch: Deserialized batch
    """
    reader = pa.ipc.open_stream(data)
    pa_batch = reader.read_next_batch()
    return pyarrow_batch_to_record_batch(pa_batch)


def serialize_batch_pickle(batch: RecordBatch) -> bytes:
    """Serialize RecordBatch using pickle (for comparison)."""
    return pickle.dumps(batch)


def deserialize_batch_pickle(data: bytes) -> RecordBatch:
    """Deserialize RecordBatch using pickle (for comparison)."""
    return pickle.loads(data)


# ============================================================================
# Test Data Creation
# ============================================================================

def create_test_batch(size: int = 10000) -> RecordBatch:
    """Create a test RecordBatch with sample data."""
    schema = Schema([
        Field("id", pa.int64()),
        Field("value", pa.float64()),
        Field("name", pa.string()),
        Field("category", pa.string())
    ])
    
    vectors = [
        ArrowFieldVector(pa.array(range(size), type=pa.int64())),
        ArrowFieldVector(pa.array([float(i) * 1.5 for i in range(size)], type=pa.float64())),
        ArrowFieldVector(pa.array([f"name_{i}" for i in range(size)], type=pa.string())),
        ArrowFieldVector(pa.array([f"cat_{i % 10}" for i in range(size)], type=pa.string()))
    ]
    
    return RecordBatch(schema, vectors)


# ============================================================================
# Worker Functions for Multiprocessing
# ============================================================================

def filter_batch_worker_ipc(ipc_data: bytes, filter_value: int) -> bytes:
    """Worker function: Filter batch using IPC.
    
    Args:
        ipc_data: Serialized batch in IPC format
        filter_value: Value to filter by (id > filter_value)
        
    Returns:
        bytes: Serialized filtered batch in IPC format
    """
    # Deserialize
    batch = deserialize_batch_ipc(ipc_data)
    
    # Filter (simulate filtering logic)
    # In real implementation, this would use SelectionExec
    filtered_rows = []
    for i in range(batch.rowCount()):
        id_val = batch.fields[0].getValue(i)
        if id_val and id_val > filter_value:
            filtered_rows.append(i)
    
    # Create filtered batch (simplified - in real code would use vectorized operations)
    if not filtered_rows:
        # Return empty batch
        return serialize_batch_ipc(batch)  # Simplified
    
    # For POC, just return original batch (real filtering would create new batch)
    return ipc_data


def project_batch_worker_ipc(ipc_data: bytes, columns: List[str]) -> bytes:
    """Worker function: Project columns using IPC.
    
    Args:
        ipc_data: Serialized batch in IPC format
        columns: List of column names to project
        
    Returns:
        bytes: Serialized projected batch in IPC format
    """
    # Deserialize
    batch = deserialize_batch_ipc(ipc_data)
    
    # Project columns (simplified - in real code would use ProjectionExec)
    # For POC, just return original batch
    return ipc_data


def aggregate_batch_worker_ipc(ipc_data: bytes, group_col: str) -> Dict[Any, Dict[str, Any]]:
    """Worker function: Aggregate batch using IPC.
    
    Args:
        ipc_data: Serialized batch in IPC format
        group_col: Column name to group by
        
    Returns:
        Dict: Partial aggregation results
    """
    # Deserialize
    batch = deserialize_batch_ipc(ipc_data)
    
    # Aggregate (simplified - in real code would use HashAggregateExec)
    groups = {}
    group_col_idx = None
    
    # Find group column index
    for i, field in enumerate(batch.schema.fields):
        if field.name == group_col:
            group_col_idx = i
            break
    
    if group_col_idx is None:
        return {}
    
    # Aggregate
    for i in range(batch.rowCount()):
        key = batch.fields[group_col_idx].getValue(i)
        value = batch.fields[1].getValue(i)  # Assume value column is index 1
        
        if key not in groups:
            groups[key] = {"sum": 0.0, "count": 0, "max": float('-inf')}
        
        if value is not None:
            groups[key]["sum"] += float(value)
            groups[key]["count"] += 1
            groups[key]["max"] = max(groups[key]["max"], float(value))
    
    return groups


# ============================================================================
# POC Tests
# ============================================================================

def test_serialization_performance():
    """Test serialization performance: IPC vs Pickle."""
    print("\n" + "="*80)
    print("Test 1: Serialization Performance (IPC vs Pickle)")
    print("="*80)
    
    batch = create_test_batch(10000)
    
    # Test IPC
    print("\n🚀 PyArrow IPC:")
    times_ipc = []
    sizes_ipc = []
    for _ in range(5):
        start = time.perf_counter()
        ipc_data = serialize_batch_ipc(batch)
        serialize_time = time.perf_counter() - start
        
        start = time.perf_counter()
        deserialized = deserialize_batch_ipc(ipc_data)
        deserialize_time = time.perf_counter() - start
        
        times_ipc.append(serialize_time + deserialize_time)
        sizes_ipc.append(len(ipc_data))
    
    avg_time_ipc = sum(times_ipc) / len(times_ipc)
    avg_size_ipc = sum(sizes_ipc) / len(sizes_ipc)
    
    print(f"  Avg serialize+deserialize: {avg_time_ipc*1000:.2f}ms")
    print(f"  Avg size: {avg_size_ipc / 1024 / 1024:.2f} MB")
    
    # Test Pickle
    print("\n📦 Pickle:")
    times_pickle = []
    sizes_pickle = []
    for _ in range(5):
        start = time.perf_counter()
        pickle_data = serialize_batch_pickle(batch)
        serialize_time = time.perf_counter() - start
        
        start = time.perf_counter()
        deserialized = deserialize_batch_pickle(pickle_data)
        deserialize_time = time.perf_counter() - start
        
        times_pickle.append(serialize_time + deserialize_time)
        sizes_pickle.append(len(pickle_data))
    
    avg_time_pickle = sum(times_pickle) / len(times_pickle)
    avg_size_pickle = sum(sizes_pickle) / len(sizes_pickle)
    
    print(f"  Avg serialize+deserialize: {avg_time_pickle*1000:.2f}ms")
    print(f"  Avg size: {avg_size_pickle / 1024 / 1024:.2f} MB")
    
    # Comparison
    print("\n📊 Comparison:")
    speedup = avg_time_pickle / avg_time_ipc if avg_time_ipc > 0 else 0
    size_ratio = avg_size_pickle / avg_size_ipc if avg_size_ipc > 0 else 0
    print(f"  IPC vs Pickle speedup: {speedup:.2f}x")
    print(f"  Size ratio: {size_ratio:.2f}x")
    
    return avg_time_ipc, avg_time_pickle, speedup


def test_multiprocessing_filtering():
    """Test multiprocessing filtering với IPC."""
    print("\n" + "="*80)
    print("Test 2: Multiprocessing Filtering với IPC")
    print("="*80)
    
    num_batches = 20
    batch_size = 5000
    batches = [create_test_batch(batch_size) for _ in range(num_batches)]
    filter_value = 1000
    
    # Sequential
    print("\n📊 Sequential Processing:")
    start = time.perf_counter()
    sequential_results = []
    for batch in batches:
        # Simulate filtering
        count = 0
        for i in range(batch.rowCount()):
            id_val = batch.fields[0].getValue(i)
            if id_val and id_val > filter_value:
                count += 1
        sequential_results.append(count)
    sequential_time = time.perf_counter() - start
    print(f"  Time: {sequential_time:.2f}s")
    print(f"  Total filtered rows: {sum(sequential_results)}")
    
    # Multiprocessing với IPC
    print("\n🚀 Multiprocessing với IPC:")
    serialize_start = time.perf_counter()
    ipc_batches = [serialize_batch_ipc(batch) for batch in batches]
    serialize_time = time.perf_counter() - serialize_start
    
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(filter_batch_worker_ipc, ipc_data, filter_value) 
                  for ipc_data in ipc_batches]
        mp_results = [f.result() for f in futures]
    process_time = time.perf_counter() - start
    
    total_time = serialize_time + process_time
    
    print(f"  Serialize time: {serialize_time:.2f}s")
    print(f"  Process time: {process_time:.2f}s")
    print(f"  Total time: {total_time:.2f}s")
    
    # Comparison
    print("\n📊 Comparison:")
    speedup = sequential_time / total_time if total_time > 0 else 0
    print(f"  Sequential: {sequential_time:.2f}s")
    print(f"  Multiprocessing: {total_time:.2f}s")
    print(f"  Speedup: {speedup:.2f}x")
    
    return sequential_time, total_time, speedup


def test_multiprocessing_aggregation():
    """Test multiprocessing aggregation với IPC."""
    print("\n" + "="*80)
    print("Test 3: Multiprocessing Aggregation với IPC")
    print("="*80)
    
    num_batches = 20
    batch_size = 5000
    batches = [create_test_batch(batch_size) for _ in range(num_batches)]
    group_col = "category"
    
    # Sequential
    print("\n📊 Sequential Aggregation:")
    start = time.perf_counter()
    sequential_groups = {}
    for batch in batches:
        # Aggregate
        for i in range(batch.rowCount()):
            key = batch.fields[3].getValue(i)  # category column
            value = batch.fields[1].getValue(i)  # value column
            
            if key not in sequential_groups:
                sequential_groups[key] = {"sum": 0.0, "count": 0, "max": float('-inf')}
            
            if value is not None:
                sequential_groups[key]["sum"] += float(value)
                sequential_groups[key]["count"] += 1
                sequential_groups[key]["max"] = max(sequential_groups[key]["max"], float(value))
    sequential_time = time.perf_counter() - start
    print(f"  Time: {sequential_time:.2f}s")
    print(f"  Groups: {len(sequential_groups)}")
    
    # Multiprocessing với IPC
    print("\n🚀 Multiprocessing Aggregation với IPC:")
    serialize_start = time.perf_counter()
    ipc_batches = [serialize_batch_ipc(batch) for batch in batches]
    serialize_time = time.perf_counter() - serialize_start
    
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(aggregate_batch_worker_ipc, ipc_data, group_col) 
                  for ipc_data in ipc_batches]
        partial_results = [f.result() for f in futures]
    
    # Merge partial results
    mp_groups = {}
    for partial in partial_results:
        for key, values in partial.items():
            if key not in mp_groups:
                mp_groups[key] = {"sum": 0.0, "count": 0, "max": float('-inf')}
            mp_groups[key]["sum"] += values["sum"]
            mp_groups[key]["count"] += values["count"]
            mp_groups[key]["max"] = max(mp_groups[key]["max"], values["max"])
    
    process_time = time.perf_counter() - start
    total_time = serialize_time + process_time
    
    print(f"  Serialize time: {serialize_time:.2f}s")
    print(f"  Process + merge time: {process_time:.2f}s")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Groups: {len(mp_groups)}")
    
    # Comparison
    print("\n📊 Comparison:")
    speedup = sequential_time / total_time if total_time > 0 else 0
    print(f"  Sequential: {sequential_time:.2f}s")
    print(f"  Multiprocessing: {total_time:.2f}s")
    print(f"  Speedup: {speedup:.2f}x")
    
    # Verify results match
    print("\n✅ Verification:")
    keys_match = set(sequential_groups.keys()) == set(mp_groups.keys())
    print(f"  Keys match: {keys_match}")
    if keys_match:
        values_match = all(
            abs(sequential_groups[k]["sum"] - mp_groups[k]["sum"]) < 0.01
            for k in sequential_groups.keys()
        )
        print(f"  Values match: {values_match}")
    
    return sequential_time, total_time, speedup


def test_real_world_scenario():
    """Test real-world scenario với Starlink operations."""
    print("\n" + "="*80)
    print("Test 4: Real-World Scenario (Starlink Operations)")
    print("="*80)
    
    # Create test CSV file
    csv_file = Path(__file__).parent / "data" / "test_ipc.csv"
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate test data
    with open(csv_file, 'w') as f:
        f.write("id,value,name,category\n")
        for i in range(50000):
            f.write(f"{i},{i*1.5},name_{i},cat_{i%10}\n")
    
    print(f"Created test CSV: {csv_file} ({csv_file.stat().st_size / 1024:.1f} KB)")
    
    # Test với Starlink
    ctx = ExecutionContext({})
    
    # Sequential query
    print("\n📊 Sequential Query:")
    start = time.perf_counter()
    df = ctx.csv(str(csv_file))
    df = df.filter(Gt(cast(col("id"), pa.int64()), lit(1000)))
    df = df.aggregate(
        [col("category")],
        [Sum(cast(col("value"), pa.float64())), Max(cast(col("value"), pa.float64()))]
    )
    sequential_results = list(ctx.execute(df))
    sequential_time = time.perf_counter() - start
    
    print(f"  Time: {sequential_time:.2f}s")
    print(f"  Batches: {len(sequential_results)}")
    if sequential_results:
        print(f"  First batch rows: {sequential_results[0].rowCount()}")
        print(f"  First batch CSV:\n{sequential_results[0].toCSV()[:200]}...")
    
    # Cleanup
    csv_file.unlink()
    
    return sequential_time


def main():
    """Run all POC tests."""
    print("🔬 POC: Starlink với PyArrow IPC Stream")
    print("="*80)
    print("Testing IPC stream integration với Starlink operations")
    print("="*80)
    
    results = {}
    
    try:
        # Test 1: Serialization performance
        ipc_time, pickle_time, speedup = test_serialization_performance()
        results['serialization'] = {
            'ipc_time': ipc_time,
            'pickle_time': pickle_time,
            'speedup': speedup
        }
        
        # Test 2: Multiprocessing filtering
        seq_time, mp_time, mp_speedup = test_multiprocessing_filtering()
        results['filtering'] = {
            'sequential': seq_time,
            'multiprocessing': mp_time,
            'speedup': mp_speedup
        }
        
        # Test 3: Multiprocessing aggregation
        seq_time, mp_time, mp_speedup = test_multiprocessing_aggregation()
        results['aggregation'] = {
            'sequential': seq_time,
            'multiprocessing': mp_time,
            'speedup': mp_speedup
        }
        
        # Test 4: Real-world scenario
        real_time = test_real_world_scenario()
        results['real_world'] = {'time': real_time}
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Summary
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    print(f"Serialization: IPC {ipc_time*1000:.2f}ms vs Pickle {pickle_time*1000:.2f}ms ({speedup:.2f}x)")
    print(f"Filtering: Sequential {results['filtering']['sequential']:.2f}s vs MP {results['filtering']['multiprocessing']:.2f}s ({results['filtering']['speedup']:.2f}x)")
    print(f"Aggregation: Sequential {results['aggregation']['sequential']:.2f}s vs MP {results['aggregation']['multiprocessing']:.2f}s ({results['aggregation']['speedup']:.2f}x)")
    print(f"Real-world: {real_time:.2f}s")
    
    print("\n" + "="*80)
    print("Key Findings")
    print("="*80)
    if speedup < 1:
        print("⚠️ IPC serialization chậm hơn pickle")
    else:
        print("✅ IPC serialization nhanh hơn pickle")
    
    if results['filtering']['speedup'] > 1:
        print(f"✅ Multiprocessing filtering nhanh hơn ({results['filtering']['speedup']:.2f}x)")
    else:
        print(f"⚠️ Multiprocessing filtering chậm hơn ({results['filtering']['speedup']:.2f}x)")
    
    if results['aggregation']['speedup'] > 1:
        print(f"✅ Multiprocessing aggregation nhanh hơn ({results['aggregation']['speedup']:.2f}x)")
    else:
        print(f"⚠️ Multiprocessing aggregation chậm hơn ({results['aggregation']['speedup']:.2f}x)")
    
    print("\n💡 Conclusion:")
    print("IPC có thể giúp multiprocessing nhưng cần đánh giá kỹ:")
    print("1. Serialization overhead (IPC vs Pickle)")
    print("2. Conversion overhead (Starlink ↔ PyArrow)")
    print("3. Aggregation complexity (merge logic)")
    print("4. Memory overhead (multiple copies)")
    print("5. Real-world performance với large datasets")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

