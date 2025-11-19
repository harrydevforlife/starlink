# Aggregation với IPC Stream - Implementation Guide

## 📋 Tổng quan

Aggregation với IPC cần 2 phases:
1. **Phase 1: Partial Aggregation** (Parallel) - Mỗi process aggregate một phần data
2. **Phase 2: Merge** (Sequential) - Merge partial results từ tất cả processes

---

## 🏗️ Architecture

### Sequential Aggregation (Current)

```python
# HashAggregateExec.execute()
groups = {}  # Dict[group_key, List[Accumulator]]

for batch in input_batches:
    for row in batch:
        key = get_group_key(row)
        if key not in groups:
            groups[key] = [create_accumulator() for each agg_expr]
        
        for acc, value in zip(groups[key], get_agg_values(row)):
            acc.accumulate(value)

# Build output from final accumulator values
return build_result_batch(groups)
```

### Aggregation với IPC (Proposed)

```python
# Phase 1: Partial Aggregation (Parallel)
def worker_process(filepath):
    # Process file and aggregate
    groups = {}  # Partial aggregation
    for batch in read_file(filepath):
        for row in batch:
            key = get_group_key(row)
            if key not in groups:
                groups[key] = [create_accumulator() for each agg_expr]
            for acc, value in zip(groups[key], get_agg_values(row)):
                acc.accumulate(value)
    
    # Serialize accumulator states (not final values!)
    return serialize_partial_result(groups)

# Phase 2: Merge (Sequential)
def merge_partial_results(partial_results):
    merged_groups = {}
    for partial in partial_results:
        for key, acc_states in partial.items():
            if key not in merged_groups:
                merged_groups[key] = acc_states
            else:
                # Merge accumulator states
                for existing_acc, new_acc_state in zip(merged_groups[key], acc_states):
                    existing_acc.merge(new_acc_state)
    
    return merged_groups
```

---

## 🔑 Key Components

### 1. AccumulatorState

**Vấn đề**: Cần serialize accumulator state (không phải final value) để merge.

**Solution**: Extract state từ accumulator, serialize, recreate accumulator từ state.

```python
class AccumulatorState:
    """Serializable state of an accumulator."""
    
    @staticmethod
    def from_accumulator(acc, acc_type: str) -> Dict[str, Any]:
        """Extract state from accumulator for serialization."""
        if acc_type == 'sum':
            return {'type': 'sum', 'value': acc.value}
        elif acc_type == 'max':
            return {'type': 'max', 'value': acc.value}
        elif acc_type == 'min':
            return {'type': 'min', 'value': acc.value}
        elif acc_type == 'count':
            return {'type': 'count', 'value': acc.value}
    
    @staticmethod
    def to_accumulator(state: Dict[str, Any]) -> Accumulator:
        """Recreate accumulator from serialized state."""
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
        # ... similar for min, count
```

### 2. PartialAggregationResult

**Vấn đề**: Cần transfer partial results giữa processes.

**Solution**: Serialize groups dict với accumulator states.

```python
class PartialAggregationResult:
    """Represents partial aggregation results from a single process."""
    
    def __init__(self, groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]]):
        """
        Args:
            groups: Dict mapping group_key -> list of accumulator states
                    Each accumulator state is a serializable representation
        """
        self.groups = groups
    
    def serialize(self) -> bytes:
        """Serialize for IPC transfer."""
        return pickle.dumps(self.groups)
    
    @staticmethod
    def deserialize(data: bytes) -> 'PartialAggregationResult':
        """Deserialize from IPC transfer."""
        groups = pickle.loads(data)
        return PartialAggregationResult(groups)
```

### 3. Merge Logic

**Vấn đề**: Cần merge accumulator states từ multiple processes.

**Solution**: Implement merge logic cho từng accumulator type.

```python
def merge_accumulator_states(state1: Dict[str, Any], state2: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two accumulator states.
    
    This implements the merge logic for different accumulator types.
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
```

### 4. Merge Partial Results

**Vấn đề**: Cần merge multiple partial results.

**Solution**: Iterate through partial results và merge accumulator states.

```python
def merge_partial_results(partial_results: List[PartialAggregationResult]) -> Dict[Tuple[Any, ...], List[Dict[str, Any]]]:
    """Merge multiple partial aggregation results.
    
    This is the key function for aggregation with IPC.
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
```

---

## 🔄 Implementation Flow

### Step 1: Worker Process (Partial Aggregation)

```python
def aggregate_batch_worker_ipc(
    filepath: str,
    group_cols: List[str],
    agg_exprs: List[Tuple[str, str]]  # (agg_type, col_name)
) -> bytes:
    """Worker function: Aggregate a file and return partial results."""
    
    # 1. Read and process file
    ctx = ExecutionContext({})
    df = ctx.csv(filepath)
    df = df.aggregate(group_exprs, agg_exprs_list)
    batches = list(ctx.execute(df))
    
    # 2. Extract accumulator states (not final values!)
    # In real implementation, this would extract from HashAggregateExec
    groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    
    for batch in batches:
        for i in range(batch.rowCount()):
            # Extract group key
            group_key = tuple(
                batch.fields[j].getValue(i) for j in range(num_group_cols)
            )
            
            # Extract accumulator states
            acc_states = []
            for j in range(num_agg_exprs):
                agg_idx = num_group_cols + j
                value = batch.fields[agg_idx].getValue(i)
                agg_type = agg_exprs[j][0]
                
                # Create accumulator state from value
                acc_states.append({
                    'type': agg_type,
                    'value': value
                })
            
            groups[group_key] = acc_states
    
    # 3. Serialize partial result
    partial_result = PartialAggregationResult(groups)
    return partial_result.serialize()
```

### Step 2: Main Process (Merge)

```python
def aggregate_multiprocessing_ipc(
    file_paths: List[Path],
    group_cols: List[str],
    agg_exprs: List[Tuple[str, str]],
    num_workers: int = 4
):
    """Aggregate multiple files với IPC."""
    
    # Phase 1: Process files in parallel
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(aggregate_batch_worker_ipc, str(fp), group_cols, agg_exprs): fp
            for fp in file_paths
        }
        
        partial_results = []
        for future in as_completed(futures):
            serialized = future.result()
            partial_result = PartialAggregationResult.deserialize(serialized)
            partial_results.append(partial_result)
    
    # Phase 2: Merge partial results
    merged_groups = merge_partial_results(partial_results)
    
    # Phase 3: Build final result batch
    return build_result_batch(merged_groups)
```

---

## ⚠️ Challenges & Solutions

### Challenge 1: Extract Accumulator State

**Vấn đề**: HashAggregateExec trả về final values, không phải accumulator states.

**Solution**: 
- Option 1: Modify HashAggregateExec để expose accumulator states
- Option 2: Recreate accumulators từ final values (simplified, nhưng không chính xác)
- Option 3: Extract accumulator states trước khi finalize

**Recommended**: Option 1 - Modify HashAggregateExec để có method `getPartialResults()`.

### Challenge 2: Merge Logic Complexity

**Vấn đề**: Mỗi accumulator type có merge logic khác nhau.

**Solution**: Implement `merge_accumulator_states()` với switch case cho từng type.

### Challenge 3: Memory Overhead

**Vấn đề**: Partial results có thể lớn, memory overhead khi merge.

**Solution**: 
- Stream merge nếu có thể
- Process files in batches
- Use efficient serialization (IPC format)

### Challenge 4: Error Handling

**Vấn đề**: Merge failures, type mismatches, null handling.

**Solution**: 
- Validate accumulator types before merge
- Handle null values correctly
- Error recovery strategies

---

## 📊 Performance Considerations

### Serialization Overhead

- **Pickle**: Simple nhưng chậm với large data
- **IPC**: Nhanh hơn nhưng cần conversion (Starlink ↔ PyArrow)
- **Custom format**: Fastest nhưng phức tạp

### Merge Overhead

- **Time complexity**: O(n * m) với n = number of partial results, m = number of groups
- **Memory complexity**: O(m) với m = total unique groups

### Optimization Strategies

1. **Batch merge**: Merge partial results in batches
2. **Parallel merge**: Merge có thể parallelize nếu groups độc lập
3. **Early merge**: Merge ngay khi có partial results (streaming)

---

## 🎯 Implementation Checklist

### Phase 1: Core Components
- [ ] Implement `AccumulatorState` class
- [ ] Implement `PartialAggregationResult` class
- [ ] Implement `merge_accumulator_states()` function
- [ ] Implement `merge_partial_results()` function

### Phase 2: Worker Functions
- [ ] Implement `aggregate_batch_worker_ipc()` function
- [ ] Extract accumulator states from HashAggregateExec
- [ ] Serialize partial results

### Phase 3: Main Process
- [ ] Implement `aggregate_multiprocessing_ipc()` function
- [ ] Process files in parallel
- [ ] Merge partial results
- [ ] Build final result batch

### Phase 4: Integration
- [ ] Integrate với ExecutionContext
- [ ] Add configuration options
- [ ] Error handling
- [ ] Testing

### Phase 5: Optimization
- [ ] Optimize serialization
- [ ] Optimize merge logic
- [ ] Memory optimization
- [ ] Performance benchmarking

---

## 💡 Example Usage

```python
# Sequential (current)
ctx = ExecutionContext({})
df = ctx.csv("data.csv")
df = df.aggregate([col("category")], [Sum(col("value"))])
results = list(ctx.execute(df))

# Multiprocessing với IPC (proposed)
file_paths = [Path("data1.csv"), Path("data2.csv"), ...]
merged_groups = aggregate_multiprocessing_ipc(
    file_paths,
    group_cols=["category"],
    agg_exprs=[("sum", "value")],
    num_workers=4
)
results = build_result_batch(merged_groups)
```

---

## 📝 Notes

1. **Accumulator State vs Final Value**: 
   - State: Intermediate value trong accumulator (có thể merge)
   - Final Value: Final result sau khi accumulate xong (không thể merge)

2. **Merge Order**: 
   - Merge order không quan trọng cho commutative operations (sum, count)
   - Merge order quan trọng cho non-commutative operations (nếu có)

3. **Null Handling**:
   - Null values cần được handle correctly trong merge
   - Max/Min với null: null không được merge

4. **Type Safety**:
   - Validate accumulator types trước khi merge
   - Handle type mismatches gracefully

---

**Date**: 2024
**Status**: Design Document
**Priority**: MEDIUM (depends on use case)

