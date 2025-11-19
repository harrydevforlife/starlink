#!/usr/bin/env python3
"""
POC: Aggregation với IPC Stream

Implement aggregation với multiprocessing và IPC:
1. Partial aggregation trong mỗi process
2. Merge partial results từ multiple processes
3. Accumulator merge logic
4. Performance comparison
"""

import time
import sys
import pickle
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pyarrow as pa
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.schema import Schema, Field
from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, lit, Sum, Max, Min, cast, Gt
from starlink.physicalplan.expressions.sumexpr import SumAccumulator
from starlink.physicalplan.expressions.maxexpr import MaxAccumulator
from starlink.physicalplan.expressions.minexpr import MinAccumulator
from starlink.physicalplan.expressions.countexpr import CountAccumulator


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
# Aggregation với IPC - Implementation
# ============================================================================

class PartialAggregationResult:
    """Represents partial aggregation results from a single process.
    
    This is what gets returned from each worker process and needs to be merged.
    """
    def __init__(self, groups: Dict[Tuple[Any, ...], List[Any]]):
        """
        Args:
            groups: Dict mapping group key -> list of accumulator states
                    Each accumulator state is a serializable representation
        """
        self.groups = groups
    
    def serialize(self) -> bytes:
        """Serialize partial results for IPC transfer."""
        return pickle.dumps(self.groups)
    
    @staticmethod
    def deserialize(data: bytes) -> 'PartialAggregationResult':
        """Deserialize partial results from IPC transfer."""
        groups = pickle.loads(data)
        return PartialAggregationResult(groups)


class AccumulatorState:
    """Serializable state of an accumulator for IPC transfer.
    
    Different accumulator types have different state representations.
    """
    
    @staticmethod
    def from_accumulator(acc, acc_type: str) -> Dict[str, Any]:
        """Extract state from accumulator for serialization.
        
        Args:
            acc: Accumulator instance
            acc_type: Type of accumulator ('sum', 'max', 'min', 'count')
            
        Returns:
            Dict with serializable state
        """
        if acc_type == 'sum':
            return {'type': 'sum', 'value': acc.value}
        elif acc_type == 'max':
            return {'type': 'max', 'value': acc.value}
        elif acc_type == 'min':
            return {'type': 'min', 'value': acc.value}
        elif acc_type == 'count':
            return {'type': 'count', 'value': acc.value}
        else:
            raise ValueError(f"Unknown accumulator type: {acc_type}")
    
    @staticmethod
    def to_accumulator(state: Dict[str, Any]):
        """Recreate accumulator from serialized state.
        
        Args:
            state: Serialized accumulator state
            
        Returns:
            Accumulator instance
        """
        acc_type = state['type']
        value = state['value']
        
        if acc_type == 'sum':
            acc = SumAccumulator()
            acc.value = value
            return acc
        elif acc_type == 'max':
            acc = MaxAccumulator()
            acc.value = value
            return acc
        elif acc_type == 'min':
            acc = MinAccumulator()
            acc.value = value
            return acc
        elif acc_type == 'count':
            acc = CountAccumulator()
            acc.value = value
            return acc
        else:
            raise ValueError(f"Unknown accumulator type: {acc_type}")


def merge_accumulator_states(state1: Dict[str, Any], state2: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two accumulator states.
    
    This implements the merge logic for different accumulator types.
    
    Args:
        state1: First accumulator state
        state2: Second accumulator state to merge into first
        
    Returns:
        Merged accumulator state
    """
    acc_type = state1['type']
    assert state2['type'] == acc_type, "Cannot merge different accumulator types"
    
    if acc_type == 'sum':
        # Sum: add values
        return {'type': 'sum', 'value': state1['value'] + state2['value']}
    elif acc_type == 'max':
        # Max: take maximum
        if state1['value'] is None:
            return state2
        if state2['value'] is None:
            return state1
        return {'type': 'max', 'value': max(state1['value'], state2['value'])}
    elif acc_type == 'min':
        # Min: take minimum
        if state1['value'] is None:
            return state2
        if state2['value'] is None:
            return state1
        return {'type': 'min', 'value': min(state1['value'], state2['value'])}
    elif acc_type == 'count':
        # Count: add counts
        return {'type': 'count', 'value': state1['value'] + state2['value']}
    else:
        raise ValueError(f"Unknown accumulator type: {acc_type}")


def merge_partial_results(partial_results: List[PartialAggregationResult]) -> Dict[Tuple[Any, ...], List[Dict[str, Any]]]:
    """Merge multiple partial aggregation results.
    
    This is the key function for aggregation with IPC - it combines results
    from multiple processes.
    
    Args:
        partial_results: List of partial results from worker processes
        
    Returns:
        Merged groups dict: group_key -> list of merged accumulator states
    """
    merged_groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    
    for partial in partial_results:
        for group_key, acc_states in partial.groups.items():
            if group_key not in merged_groups:
                # First time seeing this key - just copy
                merged_groups[group_key] = acc_states.copy()
            else:
                # Merge with existing accumulators
                existing_states = merged_groups[group_key]
                assert len(existing_states) == len(acc_states), \
                    "Accumulator count mismatch"
                
                # Merge each accumulator
                merged_states = []
                for existing_state, new_state in zip(existing_states, acc_states):
                    merged_state = merge_accumulator_states(existing_state, new_state)
                    merged_states.append(merged_state)
                
                merged_groups[group_key] = merged_states
    
    return merged_groups


# ============================================================================
# Worker Functions
# ============================================================================

def aggregate_batch_worker_ipc(
    filepath: str,
    group_cols: List[str],
    agg_exprs: List[Tuple[str, str]]  # List of (agg_type, col_name)
) -> bytes:
    """Worker function: Aggregate a file and return partial results as IPC.
    
    This function:
    1. Reads and processes the file
    2. Performs partial aggregation
    3. Serializes results for IPC transfer
    
    Args:
        filepath: Path to CSV file
        group_cols: Column names to group by
        agg_exprs: List of (aggregation_type, column_name) tuples
                  e.g., [('sum', 'value'), ('max', 'value')]
        
    Returns:
        Serialized PartialAggregationResult
    """
    ctx = ExecutionContext({})
    
    # Read file
    df = ctx.csv(filepath)
    
    # Build aggregation expressions
    # For simplicity, we'll use cast for numeric columns
    group_exprs = [cast(col(c), pa.string()) for c in group_cols]
    agg_exprs_list = []
    
    for agg_type, col_name in agg_exprs:
        if agg_type == 'sum':
            agg_exprs_list.append(Sum(cast(col(col_name), pa.float64())))
        elif agg_type == 'max':
            agg_exprs_list.append(Max(cast(col(col_name), pa.float64())))
        elif agg_type == 'min':
            agg_exprs_list.append(Min(cast(col(col_name), pa.float64())))
        else:
            raise ValueError(f"Unsupported aggregation type: {agg_type}")
    
    # Aggregate
    df = df.aggregate(group_exprs, agg_exprs_list)
    
    # Execute
    batches = list(ctx.execute(df))
    
    # Extract partial aggregation results
    # In real implementation, this would extract from HashAggregateExec
    # For POC, we'll simulate by extracting from result batches
    groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    
    for batch in batches:
        # Extract group keys and values from batch
        # This is simplified - real implementation would extract from accumulators
        num_group_cols = len(group_cols)
        num_agg_exprs = len(agg_exprs)
        
        for i in range(batch.rowCount()):
            # Extract group key
            group_key = tuple(
                batch.fields[j].getValue(i) for j in range(num_group_cols)
            )
            
            # Extract aggregated values (these are the final results, not accumulator states)
            # In real implementation, we'd need to extract accumulator states
            # For POC, we'll create accumulator states from final values
            acc_states = []
            for j in range(num_agg_exprs):
                agg_idx = num_group_cols + j
                value = batch.fields[agg_idx].getValue(i)
                agg_type = agg_exprs[j][0]
                
                # Create accumulator state from final value
                # Note: This is simplified - real implementation would track accumulator state
                acc_states.append({
                    'type': agg_type,
                    'value': value
                })
            
            groups[group_key] = acc_states
    
    # Create partial result
    partial_result = PartialAggregationResult(groups)
    return partial_result.serialize()


# ============================================================================
# POC Tests
# ============================================================================

def test_sequential_aggregation(file_paths: List[Path], group_cols: List[str], agg_exprs: List[Tuple[str, str]]):
    """Test sequential aggregation (baseline)."""
    print("\n" + "="*80)
    print("Test 1: Sequential Aggregation (Baseline)")
    print("="*80)
    
    ctx = ExecutionContext({})
    
    start = time.perf_counter()
    all_results = []
    
    for i, filepath in enumerate(file_paths):
        df = ctx.csv(str(filepath))
        
        # Build aggregation
        group_exprs = [cast(col(c), pa.string()) for c in group_cols]
        agg_exprs_list = []
        for agg_type, col_name in agg_exprs:
            if agg_type == 'sum':
                agg_exprs_list.append(Sum(cast(col(col_name), pa.float64())))
            elif agg_type == 'max':
                agg_exprs_list.append(Max(cast(col(col_name), pa.float64())))
            elif agg_type == 'min':
                agg_exprs_list.append(Min(cast(col(col_name), pa.float64())))
        
        df = df.aggregate(group_exprs, agg_exprs_list)
        results = list(ctx.execute(df))
        all_results.extend(results)
        
        if (i + 1) % 5 == 0:
            print(f"  Processed {i+1}/{len(file_paths)} files...")
    
    # Merge results (simplified - in real code would merge accumulators)
    sequential_time = time.perf_counter() - start
    
    total_rows = sum(batch.rowCount() for batch in all_results)
    
    print(f"\n📊 Summary:")
    print(f"  Files processed: {len(file_paths)}")
    print(f"  Time: {sequential_time:.2f}s")
    print(f"  Total result rows: {total_rows}")
    
    return sequential_time, all_results


def test_multiprocessing_aggregation_ipc(
    file_paths: List[Path],
    group_cols: List[str],
    agg_exprs: List[Tuple[str, str]],
    num_workers: int = 4
):
    """Test multiprocessing aggregation với IPC."""
    print("\n" + "="*80)
    print(f"Test 2: Multiprocessing Aggregation với IPC ({num_workers} workers)")
    print("="*80)
    
    start = time.perf_counter()
    
    # Phase 1: Process files in parallel
    print("Phase 1: Processing files in parallel...")
    partial_results = []
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(aggregate_batch_worker_ipc, str(fp), group_cols, agg_exprs): fp
            for fp in file_paths
        }
        
        completed = 0
        for future in as_completed(futures):
            filepath = futures[future]
            try:
                serialized = future.result()
                partial_result = PartialAggregationResult.deserialize(serialized)
                partial_results.append(partial_result)
                completed += 1
                if completed % 5 == 0:
                    print(f"  Processed {completed}/{len(file_paths)} files...")
            except Exception as e:
                print(f"  ❌ Error processing {filepath.name}: {e}")
    
    phase1_time = time.perf_counter() - start
    
    # Phase 2: Merge partial results
    print("\nPhase 2: Merging partial results...")
    merge_start = time.perf_counter()
    merged_groups = merge_partial_results(partial_results)
    merge_time = time.perf_counter() - merge_start
    
    total_time = time.perf_counter() - start
    
    print(f"\n📊 Summary:")
    print(f"  Files processed: {len(file_paths)}")
    print(f"  Workers: {num_workers}")
    print(f"  Phase 1 (process): {phase1_time:.2f}s")
    print(f"  Phase 2 (merge): {merge_time:.2f}s")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Merged groups: {len(merged_groups)}")
    
    return total_time, merged_groups


def main():
    """Run aggregation POC tests."""
    print("🔬 POC: Aggregation với IPC Stream")
    print("="*80)
    print("Testing aggregation implementation với multiprocessing và IPC")
    print("="*80)
    
    # Use existing test files if available
    test_dir = Path(__file__).parent / "data" / "large_test"
    
    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        print("Please run poc_ipc_large_files.py first to create test files")
        return 1
    
    file_paths = sorted(test_dir.glob("data_*.csv"))
    if not file_paths:
        print(f"❌ No test files found in {test_dir}")
        return 1
    
    print(f"\n📁 Found {len(file_paths)} test files")
    
    # Configuration
    group_cols = ["category"]
    agg_exprs = [("sum", "value"), ("max", "value")]
    
    try:
        # Test 1: Sequential
        seq_time, seq_results = test_sequential_aggregation(file_paths, group_cols, agg_exprs)
        
        # Test 2: Multiprocessing với IPC
        mp_time, mp_results = test_multiprocessing_aggregation_ipc(
            file_paths, group_cols, agg_exprs, num_workers=4
        )
        
        # Summary
        print("\n" + "="*80)
        print("Summary")
        print("="*80)
        print(f"Sequential: {seq_time:.2f}s")
        print(f"Multiprocessing với IPC: {mp_time:.2f}s")
        print(f"Speedup: {seq_time/mp_time:.2f}x")
        
        print("\n" + "="*80)
        print("Implementation Notes")
        print("="*80)
        print("""
Aggregation với IPC cần 2 phases:

Phase 1: Partial Aggregation (Parallel)
- Mỗi process aggregate một phần data
- Trả về PartialAggregationResult với accumulator states
- Serialize với IPC để transfer về main process

Phase 2: Merge (Sequential)
- Merge partial results từ tất cả processes
- Merge accumulator states:
  * Sum: add values
  * Max: take maximum
  * Min: take minimum
  * Count: add counts

Key Implementation Points:
1. AccumulatorState: Serializable representation của accumulator
2. merge_accumulator_states(): Merge logic cho từng accumulator type
3. merge_partial_results(): Merge results từ multiple processes
4. IPC transfer: Serialize PartialAggregationResult giữa processes

Challenges:
- Cần extract accumulator state (không phải final value)
- Merge logic phức tạp cho different accumulator types
- Memory overhead khi merge large results
- Error handling cho merge failures
        """)
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

