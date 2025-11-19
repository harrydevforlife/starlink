# Optimization #2: SelectionExec Filtering Vectorization

## 📋 Overview

**Goal**: Replace row-by-row filtering in `SelectionExec` with PyArrow's vectorized filter operations to achieve 5-20x performance improvement.

**Current Problem**: 
- Builds boolean mask as Python list: `mask = [bool(sel_vec.getValue(i)) for i in range(sel_vec.size())]`
- Iterates over mask twice (once to count `sum(mask)`, once to filter)
- Row-by-row filtering for each column using `ArrowVectorBuilder`
- High overhead from Python loops and list operations

**Solution**: 
- Use PyArrow's `filter()` method directly on RecordBatch/Table
- Or use `pc.filter()` for individual arrays
- Expression evaluation already returns `ArrowFieldVector` with boolean array, so we can use it directly
- Eliminate Python list building and double iteration

---

## 🎯 Scope

### Files to Modify

1. **`src/starlink/physicalplan/selectionexec.py`**
   - `SelectionExec.execute()` - replace row-by-row filtering with vectorized operations
   - Remove Python list mask building
   - Remove double iteration (count + filter)
   - Use PyArrow filter operations

### Files to Test

1. `tests/starlink/execution/test_execution_context.py` (contains filter tests)
2. All existing tests that use `filter()` or `SelectionExec`
3. All integration tests

---

## 📐 Implementation Plan

### Phase 1: Understand Current Implementation

#### Step 1.1: Analyze Current Code
- **File**: `selectionexec.py:79-104`
- **Current Flow**:
  1. Evaluate expression to get `sel_vec` (ColumnVector)
  2. Build Python list mask: `mask = [bool(sel_vec.getValue(i)) for i in range(sel_vec.size())]`
  3. Count true values: `true_count = sum(mask)`
  4. For each column:
     - Create `ArrowVectorBuilder`
     - Iterate over mask and copy values row-by-row
     - Build filtered column vector

#### Step 1.2: Identify Optimization Points
- **Issue 1**: Python list building (`mask = [...]`) - O(n) with Python overhead
- **Issue 2**: Double iteration (`sum(mask)` + filtering loop) - O(2n)
- **Issue 3**: Row-by-row value extraction (`col.getValue(row_index)`) - O(n*m) where m = columns
- **Issue 4**: ArrowVectorBuilder overhead for each column

### Phase 2: Vectorized Implementation (Priority: HIGH)

#### Step 2.1: Extract Boolean Array from Expression Result
- **Change**: Get PyArrow boolean array directly from `sel_vec`
- **Strategy**:
  - `sel_vec` is already an `ArrowFieldVector` (from boolean expression evaluation)
  - Extract `sel_vec.field` which is a PyArrow boolean Array
  - No need to build Python list

#### Step 2.2: Convert RecordBatch to PyArrow RecordBatch
- **Change**: Convert our `RecordBatch` to PyArrow `RecordBatch` for filtering
- **Strategy**:
  - Extract arrays from `batch.fields`: `arrays = [vec.field for vec in batch.fields]`
  - Create PyArrow schema: `pa_schema = pa.schema([pa.field(f.name, f.dataType) for f in batch.schema.fields])`
  - Create PyArrow RecordBatch: `pa_batch = pa.RecordBatch.from_arrays(arrays, schema=pa_schema)`

#### Step 2.3: Apply Vectorized Filter
- **Change**: Use PyArrow's `filter()` method
- **Strategy**:
  - `filtered_pa_batch = pa_batch.filter(bool_array)`
  - PyArrow handles all columns at once, efficiently
  - Returns filtered RecordBatch with all columns already filtered

#### Step 2.4: Convert Back to Our RecordBatch
- **Change**: Convert filtered PyArrow RecordBatch back to our RecordBatch
- **Strategy**:
  - Extract columns: `filtered_columns = filtered_pa_batch.columns`
  - Wrap in ArrowFieldVector: `vectors = [ArrowFieldVector(col) for col in filtered_columns]`
  - Create RecordBatch: `RecordBatch(batch.schema, vectors)`

#### Step 2.5: Handle Edge Cases
- **Null handling**: PyArrow filter treats nulls in mask as False (correct behavior)
- **Empty results**: PyArrow filter handles empty results correctly
- **ChunkedArray**: Ensure boolean array is not ChunkedArray (combine if needed)

### Phase 3: Alternative Approach (If Needed)

#### Step 3.1: Column-by-Column Filtering
- **Fallback**: If RecordBatch.filter() doesn't work as expected
- **Strategy**: Use `pc.filter()` for each column individually
- **Code**:
  ```python
  filtered_columns = []
  for col_index in range(batch.columnCount()):
      col_array = batch.field(col_index).field
      filtered = pc.filter(col_array, bool_array)
      filtered_columns.append(ArrowFieldVector(filtered))
  ```

---

## ✅ Implementation Checklist

### Pre-Implementation
- [ ] Review PyArrow filter documentation
- [ ] Test PyArrow filter with RecordBatch and Table
- [ ] Test filter with nulls in mask
- [ ] Test filter with empty results
- [ ] Identify all test files that use filtering

### Phase 1: Analysis
- [ ] **1.1** Review current `SelectionExec.execute()` implementation
- [ ] **1.2** Identify all performance bottlenecks
- [ ] **1.3** Document current behavior for reference

### Phase 2: Vectorized Implementation
- [ ] **2.1** Import `pyarrow` and `pyarrow.compute` if needed
- [ ] **2.2** Extract boolean array from `sel_vec.field`
- [ ] **2.3** Handle ChunkedArray (combine chunks if needed)
- [ ] **2.4** Convert RecordBatch to PyArrow RecordBatch
- [ ] **2.5** Apply `pa_batch.filter(bool_array)`
- [ ] **2.6** Convert filtered PyArrow RecordBatch back to our RecordBatch
- [ ] **2.7** Remove old row-by-row filtering code
- [ ] **2.8** Remove Python list mask building
- [ ] **2.9** Remove double iteration (sum + loop)

### Phase 3: Testing
- [ ] **3.1** Run: `pytest tests/starlink/execution/test_execution_context.py -v`
- [ ] **3.2** Test with simple filter (e.g., `state == 'CO'`)
- [ ] **3.3** Test with complex filter (e.g., `state == 'CO' AND salary > 10000`)
- [ ] **3.4** Test with null values in data
- [ ] **3.5** Test with null values in filter result (should be treated as False)
- [ ] **3.6** Test with empty filter result (all False)
- [ ] **3.7** Test with all True filter (no filtering)
- [ ] **3.8** Test with different data types (int, float, string, bool)
- [ ] **3.9** Test with large datasets (performance validation)
- [ ] **3.10** Run all starlink tests: `pytest tests/starlink/ -v`

### Code Quality
- [ ] **C.1** Add docstrings explaining vectorized approach
- [ ] **C.2** Add comments for non-obvious PyArrow operations
- [ ] **C.3** Remove old row-by-row code (or mark as deprecated)
- [ ] **C.4** Ensure code follows existing style
- [ ] **C.5** Update type hints if needed

### Documentation
- [ ] **D.1** Update `PERFORMANCE_OPTIMIZATION.md` with completion status
- [ ] **D.2** Document any limitations or edge cases
- [ ] **D.3** Add performance benchmarks/results

---

## 🔍 Technical Details

### PyArrow Filter API

**RecordBatch.filter()**:
```python
import pyarrow as pa

# Create RecordBatch
arrays = [pa.array([1, 2, 3]), pa.array(['a', 'b', 'c'])]
schema = pa.schema([pa.field('col1', pa.int64()), pa.field('col2', pa.string())])
batch = pa.RecordBatch.from_arrays(arrays, schema=schema)

# Create boolean mask
mask = pa.array([True, False, True])

# Filter
filtered = batch.filter(mask)
# Result: RecordBatch with filtered columns
```

**Table.filter()**:
```python
table = pa.table({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
mask = pa.array([True, False, True])
filtered = table.filter(mask)
```

**pc.filter()** (for individual arrays):
```python
import pyarrow.compute as pc

array = pa.array([1, 2, 3, 4, 5])
mask = pa.array([True, False, True, False, True])
filtered = pc.filter(array, mask)
```

### Conversion Pattern

**Our RecordBatch → PyArrow RecordBatch**:
```python
# Extract arrays from our RecordBatch
arrays = [vec.field for vec in batch.fields]

# Create PyArrow schema
pa_schema = pa.schema([
    pa.field(f.name, f.dataType) 
    for f in batch.schema.fields
])

# Create PyArrow RecordBatch
pa_batch = pa.RecordBatch.from_arrays(arrays, schema=pa_schema)
```

**PyArrow RecordBatch → Our RecordBatch**:
```python
# Extract columns from filtered PyArrow RecordBatch
filtered_columns = filtered_pa_batch.columns

# Wrap in ArrowFieldVector
vectors = [ArrowFieldVector(col) for col in filtered_columns]

# Create our RecordBatch
filtered_batch = RecordBatch(batch.schema, vectors)
```

### Error Handling

1. **ChunkedArray in boolean mask**: Convert to Array using `combine_chunks()`
2. **Size mismatch**: PyArrow will raise error automatically
3. **Type mismatch**: Ensure boolean array is boolean type
4. **Empty results**: PyArrow handles correctly (returns empty RecordBatch)

### Backward Compatibility

- Keep interface unchanged (return `Sequence[RecordBatch]`)
- Maintain same filtering behavior
- Maintain same null handling (nulls in mask = False)
- Maintain same error messages where possible

---

## 🧪 Testing Strategy

### Unit Tests
- Test `SelectionExec` with simple filters
- Test with complex filters (AND, OR)
- Test with null values
- Test with empty results
- Test with all True/False masks

### Integration Tests
- Test filters in DataFrame API
- Test filters in SQL queries
- Test filters with projections
- Test filters with aggregations

### Performance Tests
- Benchmark before/after
- Test with large datasets (10K, 100K, 1M rows)
- Measure speedup achieved

### Edge Case Tests
- Null handling
- Empty batches
- Single row batches
- All rows filtered out
- No rows filtered (all True)

---

## 📊 Success Criteria

1. ✅ All existing tests pass
2. ✅ Performance improvement: 5-20x faster for filtering operations
3. ✅ No regression in functionality
4. ✅ Correct null handling
5. ✅ Correct filtering behavior
6. ✅ Code is maintainable and well-documented

---

## 🚨 Risks & Mitigation

### Risk 1: PyArrow filter behavior differences
- **Mitigation**: Test thoroughly, document differences
- **Detection**: Unit tests will catch issues

### Risk 2: Schema conversion issues
- **Mitigation**: Test schema conversion, handle edge cases
- **Detection**: Schema validation tests

### Risk 3: Performance not as expected
- **Mitigation**: Profile and benchmark, identify bottlenecks
- **Detection**: Performance benchmarks

### Risk 4: Memory overhead from conversions
- **Mitigation**: Profile memory usage, optimize if needed
- **Detection**: Memory profiling

---

## 📝 Notes

- PyArrow's `filter()` is highly optimized C++ operation
- Vectorization eliminates Python loop overhead
- Filtering all columns at once is more efficient than column-by-column
- Null handling is automatic and correct in PyArrow
- RecordBatch.filter() is preferred over column-by-column pc.filter()

---

## 🔄 Rollback Plan

If issues arise:
1. Revert changes to `selectionexec.py`
2. Run all tests to ensure system is stable
3. Investigate issues in isolation
4. Re-implement with fixes

---

## 📅 Estimated Timeline

- **Phase 1 (Analysis)**: 0.5 hours
- **Phase 2 (Implementation)**: 1-2 hours
- **Phase 3 (Testing)**: 1-2 hours
- **Total**: 2.5-4.5 hours

---

## 🎓 Learning Resources

- PyArrow RecordBatch API: https://arrow.apache.org/docs/python/generated/pyarrow.RecordBatch.html
- PyArrow Filter: https://arrow.apache.org/docs/python/compute.html#filtering
- PyArrow Compute Functions: https://arrow.apache.org/docs/python/compute.html

