#!/usr/bin/env python3
"""
POC: Starlink với PyArrow IPC Stream - Large Files Scenario

Test IPC với nhiều files lớn để đánh giá:
1. Performance với multiple files (folder scenario)
2. Multiprocessing với IPC cho independent files
3. Memory usage với large datasets
4. Real-world performance với large files
"""

import time
import sys
import pickle
import shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
import random

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pyarrow as pa
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.schema import Schema, Field
from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, lit, Sum, Max, cast, Gt, Eq
from starlink.datasources.csv import CsvDataSource


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
    """Serialize RecordBatch using PyArrow IPC stream format."""
    pa_batch = record_batch_to_pyarrow_batch(batch)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, pa_batch.schema) as writer:
        writer.write_batch(pa_batch)
    return sink.getvalue().to_pybytes()


def deserialize_batch_ipc(data: bytes) -> RecordBatch:
    """Deserialize RecordBatch from PyArrow IPC stream format."""
    reader = pa.ipc.open_stream(data)
    pa_batch = reader.read_next_batch()
    return pyarrow_batch_to_record_batch(pa_batch)


# ============================================================================
# Test Data Generation
# ============================================================================

def generate_large_csv_file(filepath: Path, num_rows: int, file_id: int):
    """Generate a large CSV file with test data.
    
    Args:
        filepath: Path to CSV file
        num_rows: Number of rows to generate
        file_id: ID of the file (for unique data)
    """
    with open(filepath, 'w') as f:
        # Header
        f.write("id,value,name,category,region\n")
        
        # Generate data
        for i in range(num_rows):
            row_id = file_id * 1000000 + i
            value = random.uniform(100.0, 10000.0)
            name = f"name_{row_id}"
            category = f"cat_{i % 20}"
            region = f"region_{i % 10}"
            f.write(f"{row_id},{value:.2f},{name},{category},{region}\n")


def create_test_files_folder(base_dir: Path, num_files: int, rows_per_file: int) -> List[Path]:
    """Create a folder with multiple large CSV files.
    
    Args:
        base_dir: Base directory for test files
        num_files: Number of files to create
        rows_per_file: Number of rows per file
        
    Returns:
        List of file paths
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    
    file_paths = []
    print(f"Creating {num_files} files with {rows_per_file:,} rows each...")
    
    for i in range(num_files):
        filepath = base_dir / f"data_{i:03d}.csv"
        generate_large_csv_file(filepath, rows_per_file, i)
        file_paths.append(filepath)
        
        if (i + 1) % 5 == 0:
            file_size_mb = filepath.stat().st_size / 1024 / 1024
            print(f"  Created {i+1}/{num_files} files (latest: {file_size_mb:.1f} MB)")
    
    total_size = sum(f.stat().st_size for f in file_paths) / 1024 / 1024
    print(f"✅ Created {num_files} files, total size: {total_size:.1f} MB")
    
    return file_paths


# ============================================================================
# Worker Functions for Multiprocessing
# ============================================================================

def process_file_sequential(filepath: str, filter_value: float) -> Dict[str, Any]:
    """Process a single file sequentially (simulate Starlink operations).
    
    Args:
        filepath: Path to CSV file
        filter_value: Value to filter by (value > filter_value)
        
    Returns:
        Dict with processing results
    """
    ctx = ExecutionContext({})
    
    # Read and filter
    df = ctx.csv(filepath)
    df = df.filter(Gt(cast(col("value"), pa.float64()), lit(filter_value)))
    
    # Aggregate
    df = df.aggregate(
        [col("category")],
        [Sum(cast(col("value"), pa.float64())), Max(cast(col("value"), pa.float64()))]
    )
    
    # Execute
    results = list(ctx.execute(df))
    
    # Collect stats
    total_rows = sum(batch.rowCount() for batch in results)
    
    return {
        "file": filepath,
        "batches": len(results),
        "rows": total_rows,
        "results": results
    }


def process_file_worker_ipc(filepath: str, filter_value: float) -> Tuple[str, int, int, bytes]:
    """Worker function: Process file and return results as IPC.
    
    Args:
        filepath: Path to CSV file
        filter_value: Value to filter by
        
    Returns:
        Tuple of (filepath, num_batches, total_rows, serialized_results)
    """
    ctx = ExecutionContext({})
    
    # Read and filter
    df = ctx.csv(filepath)
    df = df.filter(Gt(cast(col("value"), pa.float64()), lit(filter_value)))
    
    # Aggregate
    df = df.aggregate(
        [col("category")],
        [Sum(cast(col("value"), pa.float64())), Max(cast(col("value"), pa.float64()))]
    )
    
    # Execute
    results = list(ctx.execute(df))
    
    # Serialize results with IPC
    serialized_batches = [serialize_batch_ipc(batch) for batch in results]
    
    total_rows = sum(batch.rowCount() for batch in results)
    
    # Return serialized data (simplified - in real code would use proper serialization)
    return (filepath, len(results), total_rows, pickle.dumps(serialized_batches))


# ============================================================================
# POC Tests
# ============================================================================

def test_sequential_processing(file_paths: List[Path], filter_value: float):
    """Test sequential processing of multiple files."""
    print("\n" + "="*80)
    print("Test 1: Sequential Processing (Multiple Files)")
    print("="*80)
    
    start = time.perf_counter()
    results = []
    
    for i, filepath in enumerate(file_paths):
        file_start = time.perf_counter()
        result = process_file_sequential(str(filepath), filter_value)
        file_time = time.perf_counter() - file_start
        
        results.append(result)
        print(f"  File {i+1}/{len(file_paths)}: {filepath.name} - {file_time:.2f}s ({result['rows']} rows)")
    
    total_time = time.perf_counter() - start
    
    total_rows = sum(r['rows'] for r in results)
    total_batches = sum(r['batches'] for r in results)
    
    print(f"\n📊 Summary:")
    print(f"  Files processed: {len(file_paths)}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Avg time per file: {total_time/len(file_paths):.2f}s")
    print(f"  Total rows: {total_rows:,}")
    print(f"  Total batches: {total_batches}")
    print(f"  Throughput: {total_rows/total_time:,.0f} rows/sec")
    
    return total_time, results


def test_multiprocessing_processing(file_paths: List[Path], filter_value: float, num_workers: int = 4):
    """Test multiprocessing processing of multiple files với IPC."""
    print("\n" + "="*80)
    print(f"Test 2: Multiprocessing Processing với IPC ({num_workers} workers)")
    print("="*80)
    
    start = time.perf_counter()
    results = []
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(process_file_worker_ipc, str(fp), filter_value): fp
            for fp in file_paths
        }
        
        # Collect results as they complete
        completed = 0
        for future in as_completed(futures):
            filepath = futures[future]
            try:
                filepath_str, num_batches, total_rows, serialized = future.result()
                results.append({
                    "file": filepath_str,
                    "batches": num_batches,
                    "rows": total_rows
                })
                completed += 1
                print(f"  File {completed}/{len(file_paths)}: {Path(filepath_str).name} - {total_rows} rows")
            except Exception as e:
                print(f"  ❌ Error processing {filepath.name}: {e}")
    
    total_time = time.perf_counter() - start
    
    total_rows = sum(r['rows'] for r in results)
    total_batches = sum(r['batches'] for r in results)
    
    print(f"\n📊 Summary:")
    print(f"  Files processed: {len(file_paths)}")
    print(f"  Workers: {num_workers}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Avg time per file: {total_time/len(file_paths):.2f}s")
    print(f"  Total rows: {total_rows:,}")
    print(f"  Total batches: {total_batches}")
    print(f"  Throughput: {total_rows/total_time:,.0f} rows/sec")
    
    return total_time, results


def test_memory_usage(file_paths: List[Path]):
    """Test memory usage với large files."""
    print("\n" + "="*80)
    print("Test 3: Memory Usage Analysis")
    print("="*80)
    
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    # Baseline memory
    baseline_memory = process.memory_info().rss / 1024 / 1024
    print(f"Baseline memory: {baseline_memory:.1f} MB")
    
    # Test sequential processing memory
    max_memory_seq = baseline_memory
    for filepath in file_paths[:5]:  # Test first 5 files
        mem_before = process.memory_info().rss / 1024 / 1024
        result = process_file_sequential(str(filepath), 1000.0)
        mem_after = process.memory_info().rss / 1024 / 1024
        max_memory_seq = max(max_memory_seq, mem_after)
        print(f"  {filepath.name}: {mem_before:.1f} MB → {mem_after:.1f} MB")
    
    print(f"\n📊 Sequential max memory: {max_memory_seq:.1f} MB")
    print(f"  Memory increase: {max_memory_seq - baseline_memory:.1f} MB")
    
    # Note: Multiprocessing memory is harder to measure accurately
    # as it's spread across processes
    print(f"\n💡 Note: Multiprocessing memory is spread across {4} processes")
    print(f"  Each process may use similar memory as sequential")


def test_large_single_file():
    """Test với một file rất lớn."""
    print("\n" + "="*80)
    print("Test 4: Large Single File")
    print("="*80)
    
    test_dir = Path(__file__).parent / "data" / "large_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Create one very large file
    large_file = test_dir / "large_data.csv"
    print(f"Creating large file: {large_file}")
    print("This may take a while...")
    
    num_rows = 500000  # 500K rows
    generate_large_csv_file(large_file, num_rows, 0)
    file_size_mb = large_file.stat().st_size / 1024 / 1024
    print(f"✅ Created file: {file_size_mb:.1f} MB ({num_rows:,} rows)")
    
    # Test sequential
    print("\n📊 Sequential Processing:")
    start = time.perf_counter()
    result = process_file_sequential(str(large_file), 1000.0)
    sequential_time = time.perf_counter() - start
    
    print(f"  Time: {sequential_time:.2f}s")
    print(f"  Rows: {result['rows']:,}")
    print(f"  Batches: {result['batches']}")
    print(f"  Throughput: {num_rows/sequential_time:,.0f} rows/sec")
    
    # Test multiprocessing (split file processing)
    # Note: For single file, we'd need to split it or process in chunks
    # This is a simplified test
    print("\n💡 Note: Single file multiprocessing would require:")
    print("  1. Splitting file into chunks")
    print("  2. Processing chunks in parallel")
    print("  3. Merging results")
    print("  This is more complex than multiple files scenario")
    
    return sequential_time


def main():
    """Run all POC tests với large files."""
    print("🔬 POC: Starlink với PyArrow IPC Stream - Large Files")
    print("="*80)
    print("Testing IPC với nhiều files lớn (folder scenario)")
    print("="*80)
    
    # Configuration
    test_dir = Path(__file__).parent / "data" / "large_test"
    num_files = 20  # Number of files
    rows_per_file = 50000  # Rows per file (50K)
    filter_value = 1000.0  # Filter value
    
    # Cleanup old test files
    if test_dir.exists():
        print(f"Cleaning up old test files in {test_dir}...")
        shutil.rmtree(test_dir)
    
    try:
        # Create test files
        print(f"\n📁 Creating test files in {test_dir}...")
        file_paths = create_test_files_folder(test_dir, num_files, rows_per_file)
        
        total_rows = num_files * rows_per_file
        total_size_mb = sum(f.stat().st_size for f in file_paths) / 1024 / 1024
        print(f"\n📊 Test Configuration:")
        print(f"  Files: {num_files}")
        print(f"  Rows per file: {rows_per_file:,}")
        print(f"  Total rows: {total_rows:,}")
        print(f"  Total size: {total_size_mb:.1f} MB")
        print(f"  Filter value: {filter_value}")
        
        # Test 1: Sequential processing
        seq_time, seq_results = test_sequential_processing(file_paths, filter_value)
        
        # Test 2: Multiprocessing với IPC
        mp_time, mp_results = test_multiprocessing_processing(file_paths, filter_value, num_workers=4)
        
        # Test 3: Memory usage
        try:
            test_memory_usage(file_paths)
        except ImportError:
            print("\n⚠️ psutil not available, skipping memory test")
        
        # Test 4: Large single file
        large_file_time = test_large_single_file()
        
        # Summary
        print("\n" + "="*80)
        print("Summary")
        print("="*80)
        print(f"Sequential processing: {seq_time:.2f}s")
        print(f"Multiprocessing với IPC: {mp_time:.2f}s")
        print(f"Speedup: {seq_time/mp_time:.2f}x")
        print(f"Large single file: {large_file_time:.2f}s")
        
        # Verify results match
        print("\n✅ Verification:")
        seq_total_rows = sum(r['rows'] for r in seq_results)
        mp_total_rows = sum(r['rows'] for r in mp_results)
        rows_match = seq_total_rows == mp_total_rows
        print(f"  Total rows match: {rows_match} ({seq_total_rows:,} vs {mp_total_rows:,})")
        
        print("\n" + "="*80)
        print("Key Findings")
        print("="*80)
        if seq_time / mp_time > 1.5:
            print(f"✅ Multiprocessing với IPC nhanh hơn đáng kể ({seq_time/mp_time:.2f}x)")
            print("✅ IPC có thể hữu ích cho multiple files scenario")
        elif seq_time / mp_time > 1.0:
            print(f"✅ Multiprocessing với IPC nhanh hơn ({seq_time/mp_time:.2f}x)")
            print("⚠️ Benefit không đáng kể, cần đánh giá thêm")
        else:
            print(f"⚠️ Multiprocessing chậm hơn ({seq_time/mp_time:.2f}x)")
            print("⚠️ Overhead lớn hơn benefit")
        
        print("\n💡 Conclusion:")
        print("1. Multiple files scenario = independent tasks = good for multiprocessing")
        print("2. IPC có thể giúp transfer results giữa processes")
        print("3. Serialization overhead vẫn tồn tại nhưng có thể acceptable")
        print("4. Memory usage spread across processes")
        print("5. Real-world performance phụ thuộc vào:")
        print("   - Number of files")
        print("   - File sizes")
        print("   - Number of workers")
        print("   - I/O vs CPU bound operations")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # Cleanup (skip interactive input in automated runs)
        # cleanup = input("\n🧹 Cleanup test files? (y/n): ").strip().lower()
        # if cleanup == 'y':
        #     if test_dir.exists():
        #         shutil.rmtree(test_dir)
        #         print(f"✅ Cleaned up {test_dir}")
        pass  # Keep test files for inspection
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

