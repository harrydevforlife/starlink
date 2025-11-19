# Optimization #3: CSV Batch Accumulation Optimization

## 📋 Overview

**Goal**: Optimize CSV batch accumulation to reduce memory overhead and improve batch processing performance by eliminating unnecessary Table conversions.

**Current Problem**: 
- Converts batches to Table multiple times: `pa.Table.from_batches(accumulated_batches)`
- Slices table and converts back to batches
- Creates intermediate Table objects that consume memory
- Multiple conversions between Table and RecordBatch

**Solution**: 
- Use `pa.concat_arrays()` to concatenate arrays directly for each column
- Avoid Table conversion overhead
- Slice arrays directly instead of slicing Table
- More efficient memory usage

---

## 🎯 Scope

### Files to Modify

1. **`src/starlink/datasources/csv.py`**
   - `CsvDataSource.scan()` method - optimize batch accumulation logic
   - Replace Table-based accumulation with array-based accumulation

### Files to Test

1. `tests/starlink/datasources/test_csv_datasource.py`
2. `tests/starlink/execution/test_execution_context.py` (uses CSV)
3. All existing tests that use CSV data source

---

## 📐 Implementation Plan

### Phase 1: Understand Current Implementation

#### Step 1.1: Analyze Current Code
- **File**: `csv.py:214-250`
- **Current Flow**:
  1. Accumulate PyArrow batches in list: `accumulated_batches.append(pyarrow_batch)`
  2. When reaching `batchSize`: Convert to Table: `table = pa.Table.from_batches(accumulated_batches)`
  3. Slice Table: `table.slice(i, end_idx - i)`
  4. Convert back to batch: `batch = table.slice(...).to_batches()[0]`
  5. Wrap in ArrowFieldVector and yield

#### Step 1.2: Identify Optimization Points
- **Issue 1**: Table conversion overhead - `pa.Table.from_batches()` creates intermediate Table object
- **Issue 2**: Table slicing - Creates new Table object for each slice
- **Issue 3**: Batch conversion - `to_batches()[0]` converts Table back to RecordBatch
- **Issue 4**: Multiple conversions - Table → slice → batch → vectors

### Phase 2: Array-Based Accumulation (Priority: MEDIUM)

#### Step 2.1: Accumulate Arrays Instead of Batches
- **Change**: Instead of accumulating batches, accumulate arrays per column
- **Strategy**:
  - For each batch, extract column arrays
  - Accumulate arrays per column: `accumulated_arrays[col_idx].append(batch.columns[col_idx])`
  - Track total row count

#### Step 2.2: Concatenate Arrays Efficiently
- **Change**: Use `pa.concat_arrays()` to concatenate arrays for each column
- **Strategy**:
  - When reaching `batchSize`: Concatenate arrays for each column
  - `concat_col = pa.concat_arrays(accumulated_arrays[col_idx])`
  - This avoids Table conversion

#### Step 2.3: Slice Arrays Directly
- **Change**: Slice concatenated arrays instead of slicing Table
- **Strategy**:
  - Slice each concatenated array: `sliced_col = concat_col.slice(start, length)`
  - Create RecordBatch from sliced arrays: `pa.RecordBatch.from_arrays(sliced_arrays, schema)`
  - This avoids Table → batch conversion

#### Step 2.4: Handle Remaining Rows
- **Change**: Apply same logic for remaining rows
- **Strategy**:
  - Concatenate remaining arrays
  - Create RecordBatch directly
  - Yield without Table conversion

#### Step 2.5: Handle Edge Cases
- **Empty batches**: Handle gracefully
- **Single batch**: Direct yield without concatenation
- **Projection**: Apply projection before accumulation (already done)

### Phase 3: Alternative Approach (If Needed)

#### Step 3.1: Stream Batches Directly
- **Fallback**: If array concatenation has issues
- **Strategy**: Yield PyArrow batches directly and let downstream handle batching
- **Note**: This may not match desired batch size exactly

---

## ✅ Implementation Checklist

### Pre-Implementation
- [ ] Review PyArrow concat_arrays documentation
- [ ] Test pa.concat_arrays() with different array types
- [ ] Test array slicing performance
- [ ] Identify all test files that use CSV

### Phase 1: Analysis
- [ ] **1.1** Review current `CsvDataSource.scan()` implementation
- [ ] **1.2** Identify all Table conversion points
- [ ] **1.3** Document current behavior for reference

### Phase 2: Array-Based Implementation
- [ ] **2.1** Change accumulation to collect arrays per column
- [ ] **2.2** Implement array concatenation using `pa.concat_arrays()`
- [ ] **2.3** Implement array slicing instead of Table slicing
- [ ] **2.4** Create RecordBatch directly from sliced arrays
- [ ] **2.5** Handle remaining rows with array concatenation
- [ ] **2.6** Remove Table conversion code
- [ ] **2.7** Remove Table slicing code
- [ ] **2.8** Remove Table.to_batches() conversion

### Phase 3: Testing
- [ ] **3.1** Run: `pytest tests/starlink/datasources/test_csv_datasource.py -v`
- [ ] **3.2** Test with small batches (batchSize < PyArrow batch size)
- [ ] **3.3** Test with large batches (batchSize > PyArrow batch size)
- [ ] **3.4** Test with exact batch size match
- [ ] **3.5** Test with projection
- [ ] **3.6** Test with no headers
- [ ] **3.7** Test with TSV files
- [ ] **3.8** Test with empty files
- [ ] **3.9** Test with single row files
- [ ] **3.10** Test with large files (performance validation)
- [ ] **3.11** Run all execution context tests: `pytest tests/starlink/execution/ -v`
- [ ] **3.12** Run all starlink tests: `pytest tests/starlink/ -v`

### Performance Validation
- [ ] **P.1** Create benchmark script for CSV reading
- [ ] **P.2** Benchmark before implementation (baseline)
- [ ] **P.3** Benchmark after implementation
- [ ] **P.4** Measure memory usage (should be lower)
- [ ] **P.5** Calculate speedup achieved (target: 2-5x reduction in overhead)
- [ ] **P.6** Test with large CSV files (10K, 100K, 1M rows)

### Code Quality
- [ ] **C.1** Remove old Table conversion code
- [ ] **C.2** Add docstrings explaining array-based approach
- [ ] **C.3** Add inline comments for array operations
- [ ] **C.4** Ensure consistent code style
- [ ] **C.5** Update type hints if needed

### Documentation
- [ ] **D.1** Update `PERFORMANCE_OPTIMIZATION.md` with completion status
- [ ] **D.2** Document any limitations or edge cases
- [ ] **D.3** Add performance benchmark results

---

## 🔍 Technical Details

### Array Concatenation Pattern

**Current Approach (Table-based)**:
```python
# Accumulate batches
accumulated_batches.append(pyarrow_batch)

# Convert to Table
table = pa.Table.from_batches(accumulated_batches)

# Slice Table
sliced = table.slice(start, length)

# Convert back to batch
batch = sliced.to_batches()[0]
```

**Optimized Approach (Array-based)**:
```python
# Accumulate arrays per column
for col_idx in range(num_cols):
    accumulated_arrays[col_idx].append(batch.columns[col_idx])

# Concatenate arrays for each column
concat_arrays = [
    pa.concat_arrays(accumulated_arrays[col_idx])
    for col_idx in range(num_cols)
]

# Slice arrays directly
sliced_arrays = [
    concat_arrays[col_idx].slice(start, length)
    for col_idx in range(num_cols)
]

# Create RecordBatch directly
batch = pa.RecordBatch.from_arrays(sliced_arrays, schema=schema)
```

### Implementation Details

**Accumulation Structure**:
```python
# Instead of: accumulated_batches = []
# Use: accumulated_arrays = [[] for _ in range(num_cols)]
# Where accumulated_arrays[col_idx] is a list of arrays for that column
```

**Batch Splitting**:
```python
# When accumulated_row_count >= batchSize:
# Split into multiple batches of batchSize
for i in range(0, accumulated_row_count, self.batchSize):
    end_idx = min(i + self.batchSize, accumulated_row_count)
    length = end_idx - i
    
    # Slice each concatenated array
    sliced_arrays = [
        concat_arrays[col_idx].slice(i, length)
        for col_idx in range(num_cols)
    ]
    
    # Create RecordBatch
    batch = pa.RecordBatch.from_arrays(sliced_arrays, schema=schema)
    yield RecordBatch(output_schema, [ArrowFieldVector(col) for col in batch.columns])
```

### Error Handling

1. **Empty arrays**: Handle gracefully (shouldn't happen, but check)
2. **Type mismatches**: PyArrow concat_arrays will raise error automatically
3. **Size mismatches**: Ensure all arrays have same length before concatenation
4. **Schema consistency**: Ensure schema is consistent across batches

### Backward Compatibility

- Keep interface unchanged (return `Sequence[RecordBatch]`)
- Maintain same batch size behavior
- Maintain same projection behavior
- Maintain same schema behavior

---

## 🧪 Testing Strategy

### Unit Tests
- Test CSV reading with different batch sizes
- Test with projection
- Test with no headers
- Test with TSV files
- Test edge cases (empty, single row)

### Integration Tests
- Test CSV in DataFrame API
- Test CSV in SQL queries
- Test CSV with filters
- Test CSV with aggregations

### Performance Tests
- Benchmark before/after
- Test with large files
- Measure memory usage
- Measure processing time

### Edge Case Tests
- Empty files
- Single row files
- Files with exact batch size
- Files with remainder rows
- Files with many small PyArrow batches

---

## 📊 Success Criteria

1. ✅ All existing tests pass
2. ✅ Performance improvement: 2-5x reduction in memory overhead
3. ✅ Faster batch processing
4. ✅ No regression in functionality
5. ✅ Correct batch size behavior
6. ✅ Code is maintainable and well-documented

---

## 🚨 Risks & Mitigation

### Risk 1: Array concatenation performance
- **Mitigation**: Test with large arrays, profile if needed
- **Detection**: Performance benchmarks

### Risk 2: Memory usage not improved
- **Mitigation**: Profile memory usage, compare before/after
- **Detection**: Memory profiling

### Risk 3: Schema consistency issues
- **Mitigation**: Validate schema consistency, test thoroughly
- **Detection**: Schema validation tests

### Risk 4: Edge cases not handled
- **Mitigation**: Test edge cases extensively
- **Detection**: Edge case tests

---

## 📝 Notes

- `pa.concat_arrays()` is efficient for concatenating arrays
- Array slicing is more efficient than Table slicing
- Direct RecordBatch creation avoids Table conversion overhead
- This optimization reduces memory overhead rather than CPU time
- PyArrow CSV reader doesn't support batch_size parameter, so accumulation is necessary

---

## 🔄 Rollback Plan

If issues arise:
1. Revert changes to `csv.py`
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

- PyArrow Array Operations: https://arrow.apache.org/docs/python/generated/pyarrow.concat_arrays.html
- PyArrow RecordBatch: https://arrow.apache.org/docs/python/generated/pyarrow.RecordBatch.html
- PyArrow CSV Reading: https://arrow.apache.org/docs/python/csv.html

