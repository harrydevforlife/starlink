# Optimization #4: HashAggregateExec Batch Processing

## 📋 Overview

**Goal**: Optimize HashAggregateExec to process rows in batches rather than one-by-one, reducing Python loop overhead and improving aggregation performance.

**Current Problem**: 
- Processes rows one-by-one: `for row_index in range(row_count)`
- Creates tuple keys for each row individually
- Converts bytes to strings for each key element in a loop
- Calls `getValue()` for each row and column
- High overhead from Python loops and repeated method calls

**Solution**: 
- Extract all values from grouping columns at once (batch extraction)
- Create grouping keys in batch using list comprehensions or zip
- Process accumulators in batches where possible
- Reduce Python loop overhead
- Optimize key creation and lookup

---

## 🎯 Scope

### Files to Modify

1. **`src/starlink/physicalplan/hashaggexec.py`**
   - `HashAggregateExec.execute()` - optimize row processing
   - Batch extract values from grouping columns
   - Batch create grouping keys
   - Optimize accumulator access pattern

### Files to Test

1. `tests/starlink/physicalplan/test_aggregate.py`
2. `tests/starlink/execution/test_execution_context.py` (contains aggregate tests)
3. All existing tests that use aggregation

---

## 📐 Implementation Plan

### Phase 1: Understand Current Implementation

#### Step 1.1: Analyze Current Code
- **File**: `hashaggexec.py:136-191`
- **Current Flow**:
  1. Evaluate grouping expressions: `group_keys_columns = [expr.evaluate(batch) for expr in self.groupExpr]`
  2. Evaluate aggregate input expressions: `aggr_input_columns = [ae.inputExpression().evaluate(batch) for ae in self.aggregateExpr]`
  3. For each row:
     - Extract values from grouping columns: `col.getValue(row_index)`
     - Convert bytes to strings
     - Create tuple key
     - Get/create accumulators
     - Accumulate values row-by-row

#### Step 1.2: Identify Optimization Points
- **Issue 1**: Row-by-row value extraction (`col.getValue(row_index)`) - O(n*m) where n=rows, m=columns
- **Issue 2**: Tuple key creation in loop - O(n) with Python overhead
- **Issue 3**: Bytes-to-string conversion in loop - O(n)
- **Issue 4**: Dictionary lookup for each row - O(n) with Python overhead
- **Issue 5**: Accumulator.accumulate() called row-by-row

### Phase 2: Batch Value Extraction (Priority: HIGH)

#### Step 2.1: Extract All Values from Grouping Columns at Once
- **Change**: Extract all values from each grouping column in one pass
- **Strategy**:
  - For each grouping column, extract all values: `values = [col.getValue(i) for i in range(row_count)]`
  - Or use ArrowFieldVector.field to get PyArrow array and extract values
  - This avoids repeated `getValue()` calls

#### Step 2.2: Batch Convert Bytes to Strings
- **Change**: Convert bytes to strings in batch
- **Strategy**:
  - After extracting values, convert all bytes at once
  - `converted_values = [v.decode('utf-8') if isinstance(v, bytes) else v for v in values]`
  - This avoids repeated isinstance checks and conversions

#### Step 2.3: Batch Create Grouping Keys
- **Change**: Create all grouping keys at once using zip
- **Strategy**:
  - Extract values from all grouping columns
  - Use `zip()` to create keys: `keys = list(zip(*group_values))`
  - This is more efficient than creating tuples in a loop

#### Step 2.4: Batch Process Accumulators
- **Change**: Process accumulators in batches where possible
- **Strategy**:
  - Group rows by key first (using a temporary structure)
  - Then accumulate values for each group in batch
  - This reduces dictionary lookups

### Phase 3: Optimize Accumulator Access (Priority: MEDIUM)

#### Step 3.1: Pre-allocate Accumulators
- **Change**: Create accumulators for all unique keys upfront
- **Strategy**:
  - First pass: collect all unique keys
  - Second pass: create accumulators for all keys
  - Third pass: accumulate values
  - This reduces dictionary lookups during accumulation

#### Step 3.2: Use List-Based Grouping
- **Change**: Use list-based grouping instead of dictionary lookups
- **Strategy**:
  - Create a list of (key, row_indices) pairs
  - Group by key using a temporary structure
  - Accumulate values for each group
  - This may be more efficient for large datasets

### Phase 4: Alternative Approach (If Needed)

#### Step 4.1: Use PyArrow Compute for Simple Aggregations
- **Fallback**: For simple aggregations (SUM, MIN, MAX), use PyArrow compute if possible
- **Strategy**: 
  - Check if aggregation can be done with PyArrow compute
  - Use vectorized operations where applicable
  - Fall back to accumulator approach for complex aggregations

---

## ✅ Implementation Checklist

### Pre-Implementation
- [ ] Review HashAggregateExec implementation thoroughly
- [ ] Understand Accumulator interface
- [ ] Test batch value extraction performance
- [ ] Identify all test files that use aggregation

### Phase 1: Analysis
- [ ] **1.1** Review current `HashAggregateExec.execute()` implementation
- [ ] **1.2** Identify all performance bottlenecks
- [ ] **1.3** Document current behavior for reference

### Phase 2: Batch Value Extraction
- [ ] **2.1** Extract all values from grouping columns at once
- [ ] **2.2** Handle ArrowFieldVector.field to get arrays directly
- [ ] **2.3** Batch convert bytes to strings
- [ ] **2.4** Batch create grouping keys using zip
- [ ] **2.5** Test batch extraction correctness

### Phase 3: Optimize Accumulator Processing
- [ ] **3.1** Group rows by key first (collect row indices per key)
- [ ] **3.2** Create accumulators for all unique keys upfront
- [ ] **3.3** Accumulate values in batches per group
- [ ] **3.4** Optimize dictionary lookups

### Phase 4: Testing
- [ ] **4.1** Run: `pytest tests/starlink/physicalplan/test_aggregate.py -v`
- [ ] **4.2** Test with single grouping column
- [ ] **4.3** Test with multiple grouping columns
- [ ] **4.4** Test with single aggregate function
- [ ] **4.5** Test with multiple aggregate functions
- [ ] **4.6** Test with SUM aggregation
- [ ] **4.7** Test with MIN aggregation
- [ ] **4.8** Test with MAX aggregation
- [ ] **4.9** Test with COUNT aggregation (if available)
- [ ] **4.10** Test with null values in grouping keys
- [ ] **4.11** Test with null values in aggregate inputs
- [ ] **4.12** Test with empty input
- [ ] **4.13** Test with single row input
- [ ] **4.14** Test with large datasets (performance validation)
- [ ] **4.15** Run all execution context tests: `pytest tests/starlink/execution/ -v`
- [ ] **4.16** Run all starlink tests: `pytest tests/starlink/ -v`

### Performance Validation
- [ ] **P.1** Create benchmark script for aggregation
- [ ] **P.2** Benchmark before implementation (baseline)
- [ ] **P.3** Benchmark after implementation
- [ ] **P.4** Calculate speedup achieved (target: 5-50x)
- [ ] **P.5** Test with different group sizes
- [ ] **P.6** Test with different data sizes (10K, 100K, 1M rows)

### Code Quality
- [ ] **C.1** Remove or optimize old row-by-row code
- [ ] **C.2** Add docstrings explaining batch approach
- [ ] **C.3** Add inline comments for batch operations
- [ ] **C.4** Ensure consistent code style
- [ ] **C.5** Update type hints if needed

### Documentation
- [ ] **D.1** Update `PERFORMANCE_OPTIMIZATION.md` with completion status
- [ ] **D.2** Document any limitations or edge cases
- [ ] **D.3** Add performance benchmark results

---

## 🔍 Technical Details

### Batch Value Extraction Pattern

**Current Approach (Row-by-row)**:
```python
for row_index in range(row_count):
    key_elems = []
    for col in group_keys_columns:
        v = col.getValue(row_index)  # Repeated getValue() calls
        if isinstance(v, (bytes, bytearray)):
            v = bytes(v).decode("utf-8")  # Repeated conversions
        key_elems.append(v)
    key = tuple(key_elems)
```

**Optimized Approach (Batch extraction)**:
```python
# Extract all values from grouping columns at once
group_values = []
for col in group_keys_columns:
    # Extract all values in one pass
    if isinstance(col, ArrowFieldVector):
        # Get PyArrow array and extract values
        arr = col.field
        if isinstance(arr, pa.ChunkedArray):
            arr = arr.combine_chunks()
        # Extract all values
        values = [arr[i].as_py() for i in range(len(arr))]
    else:
        # Fallback to getValue for each row
        values = [col.getValue(i) for i in range(row_count)]
    
    # Batch convert bytes to strings
    converted_values = [
        v.decode('utf-8') if isinstance(v, (bytes, bytearray)) else v
        for v in values
    ]
    group_values.append(converted_values)

# Batch create grouping keys using zip
keys = list(zip(*group_values))
```

### Optimized Accumulator Processing

**Current Approach**:
```python
for row_index in range(row_count):
    key = tuple(key_elems)
    if key not in groups:
        groups[key] = [ae.createAccumulator() for ae in self.aggregateExpr]
    accs = groups[key]
    for i, acc in enumerate(accs):
        value = aggr_input_columns[i].getValue(row_index)
        acc.accumulate(value)
```

**Optimized Approach**:
```python
# Extract all aggregate input values at once
aggr_values = []
for col in aggr_input_columns:
    if isinstance(col, ArrowFieldVector):
        arr = col.field
        if isinstance(arr, pa.ChunkedArray):
            arr = arr.combine_chunks()
        values = [arr[i].as_py() for i in range(len(arr))]
    else:
        values = [col.getValue(i) for i in range(row_count)]
    aggr_values.append(values)

# Group rows by key and accumulate in batches
from collections import defaultdict
key_to_indices = defaultdict(list)
for row_index, key in enumerate(keys):
    key_to_indices[key].append(row_index)

# Create accumulators for all unique keys
for key in key_to_indices:
    if key not in groups:
        groups[key] = [ae.createAccumulator() for ae in self.aggregateExpr]

# Accumulate values in batches per group
for key, row_indices in key_to_indices.items():
    accs = groups[key]
    for i, acc in enumerate(accs):
        # Accumulate all values for this group at once
        for row_index in row_indices:
            value = aggr_values[i][row_index]
            acc.accumulate(value)
```

### Error Handling

1. **ChunkedArray**: Convert to Array using `combine_chunks()` if needed
2. **Type mismatches**: Handle different value types correctly
3. **Null values**: Ensure null handling is correct
4. **Empty batches**: Handle gracefully

### Backward Compatibility

- Keep interface unchanged (return `Sequence[RecordBatch]`)
- Maintain same aggregation behavior
- Maintain same null handling
- Maintain same accumulator interface

---

## 🧪 Testing Strategy

### Unit Tests
- Test HashAggregateExec with different grouping columns
- Test with different aggregate functions
- Test with null values
- Test with empty results
- Test with single group

### Integration Tests
- Test aggregation in DataFrame API
- Test aggregation in SQL queries
- Test aggregation with filters
- Test aggregation with projections

### Performance Tests
- Benchmark before/after
- Test with large datasets
- Test with many groups
- Test with few groups
- Measure speedup achieved

### Edge Case Tests
- Null handling
- Empty batches
- Single row batches
- Single group
- Many groups
- Large groups

---

## 📊 Success Criteria

1. ✅ All existing tests pass
2. ✅ Performance improvement: 5-50x faster for aggregate queries
3. ✅ No regression in functionality
4. ✅ Correct null handling
5. ✅ Correct aggregation behavior
6. ✅ Code is maintainable and well-documented

---

## 🚨 Risks & Mitigation

### Risk 1: Batch extraction memory overhead
- **Mitigation**: Process in chunks if memory is a concern
- **Detection**: Memory profiling

### Risk 2: Key creation performance not improved
- **Mitigation**: Profile and optimize further
- **Detection**: Performance benchmarks

### Risk 3: Accumulator interface limitations
- **Mitigation**: Keep accumulator interface, optimize around it
- **Detection**: Unit tests

### Risk 4: Null handling differences
- **Mitigation**: Test null handling extensively
- **Detection**: Null handling tests

---

## 📝 Notes

- PyArrow doesn't have direct group_by support
- pandas groupby could be used but adds dependency
- Focus on optimizing Python loops and reducing overhead
- Batch extraction reduces repeated method calls
- Batch key creation is more efficient than tuple creation in loop
- Accumulator interface may limit full vectorization, but we can optimize around it

---

## 🔄 Rollback Plan

If issues arise:
1. Revert changes to `hashaggexec.py`
2. Run all tests to ensure system is stable
3. Investigate issues in isolation
4. Re-implement with fixes

---

## 📅 Estimated Timeline

- **Phase 1 (Analysis)**: 0.5 hours
- **Phase 2 (Batch Extraction)**: 2-3 hours
- **Phase 3 (Accumulator Optimization)**: 1-2 hours
- **Phase 4 (Testing)**: 2-3 hours
- **Total**: 5.5-8.5 hours

---

## 🎓 Learning Resources

- PyArrow Array Operations: https://arrow.apache.org/docs/python/generated/pyarrow.Array.html
- Python Performance Optimization: https://docs.python.org/3/library/profile.html
- Collections defaultdict: https://docs.python.org/3/library/collections.html#collections.defaultdict

