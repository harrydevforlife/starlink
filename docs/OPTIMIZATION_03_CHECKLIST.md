# Optimization #3: CSV Batch Accumulation Optimization - Checklist

## 📋 Quick Reference

**Goal**: Optimize CSV batch accumulation to reduce memory overhead  
**Expected Impact**: 2-5x reduction in memory overhead, faster batch processing  
**Files**: `csv.py`

---

## ✅ Implementation Checklist

### Pre-Implementation Setup
- [ ] Create feature branch: `git checkout -b optimize/csv-batch-accumulation`
- [ ] Review PyArrow concat_arrays documentation
- [ ] Test pa.concat_arrays() in Python REPL
- [ ] Test array slicing performance
- [ ] Identify all test files that use CSV

### Phase 1: Analysis & Understanding
- [ ] **1.1** Read current `CsvDataSource.scan()` implementation
- [ ] **1.2** Identify Table conversion points:
  - [ ] `pa.Table.from_batches()` calls
  - [ ] `table.slice()` calls
  - [ ] `table.to_batches()` calls
- [ ] **1.3** Document current behavior for reference

### Phase 2: Array-Based Implementation ⚡ MEDIUM PRIORITY

#### Change Accumulation Strategy
- [ ] **2.1** Replace `accumulated_batches = []` with per-column array accumulation
- [ ] **2.2** Initialize: `accumulated_arrays = [[] for _ in range(num_cols)]`
- [ ] **2.3** Extract arrays from each batch: `batch.columns[col_idx]`
- [ ] **2.4** Accumulate arrays per column: `accumulated_arrays[col_idx].append(array)`
- [ ] **2.5** Track total row count: `accumulated_row_count`

#### Implement Array Concatenation
- [ ] **2.6** When reaching `batchSize`, concatenate arrays for each column
- [ ] **2.7** Use `pa.concat_arrays()` for each column
- [ ] **2.8** Verify concatenated arrays have correct length
- [ ] **2.9** Store concatenated arrays: `concat_arrays = [...]`

#### Implement Array Slicing
- [ ] **2.10** Slice concatenated arrays instead of Table
- [ ] **2.11** For each batch split: `sliced_arrays = [concat_arrays[col_idx].slice(start, length) for col_idx in range(num_cols)]`
- [ ] **2.12** Create RecordBatch from sliced arrays: `pa.RecordBatch.from_arrays(sliced_arrays, schema)`
- [ ] **2.13** Verify sliced arrays have correct length

#### Handle Remaining Rows
- [ ] **2.14** Apply same logic for remaining rows
- [ ] **2.15** Concatenate remaining arrays
- [ ] **2.16** Create RecordBatch directly (no slicing needed)
- [ ] **2.17** Yield remaining batch

#### Cleanup
- [ ] **2.18** Remove `pa.Table.from_batches()` calls
- [ ] **2.19** Remove `table.slice()` calls
- [ ] **2.20** Remove `table.to_batches()` calls
- [ ] **2.21** Remove `accumulated_batches` list

### Phase 3: Testing 🔗

#### Basic Functionality Tests
- [ ] **3.1** Run: `pytest tests/starlink/datasources/test_csv_datasource.py -v`
- [ ] **3.2** Test with small batch size (e.g., batchSize=10)
- [ ] **3.3** Test with large batch size (e.g., batchSize=10000)
- [ ] **3.4** Test with exact batch size match
- [ ] **3.5** Test with remainder rows (not exact multiple)

#### CSV Feature Tests
- [ ] **3.6** Test with headers
- [ ] **3.7** Test with no headers
- [ ] **3.8** Test with projection
- [ ] **3.9** Test with TSV files (tab delimiter)
- [ ] **3.10** Test with CSV files (comma delimiter)

#### Edge Case Tests
- [ ] **3.11** Test with empty CSV file
- [ ] **3.12** Test with single row CSV file
- [ ] **3.13** Test with single column CSV file
- [ ] **3.14** Test with many columns CSV file
- [ ] **3.15** Test with null values in CSV

#### Integration Tests
- [ ] **3.16** Test CSV in DataFrame API: `ctx.csv(filename)`
- [ ] **3.17** Test CSV in SQL queries: `SELECT * FROM csv_file`
- [ ] **3.18** Test CSV with filter: `df.filter(...)`
- [ ] **3.19** Test CSV with projection: `df.project(...)`
- [ ] **3.20** Test CSV with aggregation: `df.aggregate(...)`

#### Full Test Suite
- [ ] **3.21** Run all datasource tests: `pytest tests/starlink/datasources/ -v`
- [ ] **3.22** Run all execution tests: `pytest tests/starlink/execution/ -v`
- [ ] **3.23** Run all starlink tests: `pytest tests/starlink/ -v`
- [ ] **3.24** Verify no test failures

### Performance Validation 📊

#### Benchmarking
- [ ] **P.1** Create benchmark script for CSV reading
- [ ] **P.2** Benchmark before implementation (baseline)
- [ ] **P.3** Benchmark after implementation
- [ ] **P.4** Measure memory usage (should be lower)
- [ ] **P.5** Measure processing time (should be faster)
- [ ] **P.6** Calculate improvement (target: 2-5x reduction in overhead)
- [ ] **P.7** Document performance results

#### Large Dataset Testing
- [ ] **P.8** Test with 10K row CSV file
- [ ] **P.9** Test with 100K row CSV file
- [ ] **P.10** Test with 1M row CSV file
- [ ] **P.11** Verify performance scales well
- [ ] **P.12** Profile memory usage (compare before/after)

### Code Quality ✨

#### Code Review
- [ ] **C.1** Remove old Table conversion code
- [ ] **C.2** Add docstrings explaining array-based approach
- [ ] **C.3** Add inline comments for array operations
- [ ] **C.4** Ensure consistent code style
- [ ] **C.5** Update type hints if needed
- [ ] **C.6** Verify no unused imports

#### Documentation
- [ ] **D.1** Update `PERFORMANCE_OPTIMIZATION.md` with completion status
- [ ] **D.2** Document any limitations or edge cases
- [ ] **D.3** Add performance benchmark results
- [ ] **D.4** Update this checklist with completion date

### Final Validation ✅

#### Pre-Commit Checklist
- [ ] **F.1** All tests pass
- [ ] **F.2** No linter errors
- [ ] **F.3** Code is well-documented
- [ ] **F.4** Performance benchmarks show improvement
- [ ] **F.5** Memory usage is reduced
- [ ] **F.6** No regressions in functionality

#### Commit & Merge
- [ ] **F.7** Commit changes with descriptive message
- [ ] **F.8** Create PR (if using PR workflow)
- [ ] **F.9** Get code review approval
- [ ] **F.10** Merge to main branch

---

## 🐛 Known Issues / Edge Cases

### To Handle During Implementation

1. **Schema Consistency**
   - [ ] Ensure schema is consistent across all batches
   - [ ] Verify schema when creating RecordBatch from arrays
   - [ ] Test with different column types

2. **Array Length Mismatch**
   - [ ] Verify all arrays have same length before concatenation
   - [ ] Handle edge cases where arrays might differ
   - [ ] Test with malformed CSV data

3. **Empty Accumulation**
   - [ ] Handle case where no batches accumulated
   - [ ] Handle case where accumulated arrays are empty
   - [ ] Test with very small CSV files

4. **Projection Order**
   - [ ] Ensure projection is applied before accumulation
   - [ ] Verify column order matches projection order
   - [ ] Test with different projection orders

5. **Memory Efficiency**
   - [ ] Verify arrays are released after use
   - [ ] Check for memory leaks
   - [ ] Profile memory usage

---

## 📝 Implementation Notes

### Code Pattern Template

```python
def scan(self, projection: List[str]) -> Sequence[RecordBatch]:
    def generator() -> Iterator[RecordBatch]:
        reader = pacsv.open_csv(...)
        
        # Initialize per-column array accumulation
        num_cols = len(output_schema.fields)
        accumulated_arrays = [[] for _ in range(num_cols)]
        accumulated_row_count = 0
        
        for pyarrow_batch in reader:
            # Apply projection if needed
            if projection:
                pyarrow_batch = pyarrow_batch.select(projection)
            
            # Accumulate arrays per column
            for col_idx in range(num_cols):
                accumulated_arrays[col_idx].append(pyarrow_batch.columns[col_idx])
            
            accumulated_row_count += len(pyarrow_batch)
            
            # Yield batches when reaching desired size
            if accumulated_row_count >= self.batchSize:
                # Concatenate arrays for each column
                concat_arrays = [
                    pa.concat_arrays(accumulated_arrays[col_idx])
                    for col_idx in range(num_cols)
                ]
                
                # Split into batches of batchSize
                for i in range(0, accumulated_row_count, self.batchSize):
                    end_idx = min(i + self.batchSize, accumulated_row_count)
                    length = end_idx - i
                    
                    # Slice arrays directly
                    sliced_arrays = [
                        concat_arrays[col_idx].slice(i, length)
                        for col_idx in range(num_cols)
                    ]
                    
                    # Create RecordBatch directly
                    batch = pa.RecordBatch.from_arrays(
                        sliced_arrays, 
                        schema=pa_schema
                    )
                    vectors = [ArrowFieldVector(col) for col in batch.columns]
                    yield RecordBatch(output_schema, vectors)
                
                # Reset accumulation
                accumulated_arrays = [[] for _ in range(num_cols)]
                accumulated_row_count = 0
        
        # Yield remaining rows
        if accumulated_arrays[0]:  # Check if any arrays accumulated
            concat_arrays = [
                pa.concat_arrays(accumulated_arrays[col_idx])
                for col_idx in range(num_cols)
            ]
            batch = pa.RecordBatch.from_arrays(concat_arrays, schema=pa_schema)
            vectors = [ArrowFieldVector(col) for col in batch.columns]
            yield RecordBatch(output_schema, vectors)
    
    return generator()
```

### PyArrow Array Operations Reference

| Operation | Function | Notes |
|-----------|----------|-------|
| Concatenate Arrays | `pa.concat_arrays([arr1, arr2, ...])` | Efficient array concatenation |
| Slice Array | `array.slice(start, length)` | Efficient array slicing |
| Create RecordBatch | `pa.RecordBatch.from_arrays(arrays, schema)` | Direct batch creation |

### Error Handling

1. **Empty Arrays**: Check before concatenation
2. **Type Mismatches**: PyArrow will raise error automatically
3. **Size Mismatches**: Verify all arrays have same length
4. **Schema Issues**: Ensure schema consistency

### Backward Compatibility

- Keep interface unchanged (return `Sequence[RecordBatch]`)
- Maintain same batch size behavior
- Maintain same projection behavior
- Maintain same schema behavior

---

## 🎯 Success Metrics

- [ ] **Functionality**: All existing tests pass (100%)
- [ ] **Performance**: 2-5x reduction in memory overhead
- [ ] **Performance**: Faster batch processing
- [ ] **Correctness**: No regressions in behavior
- [ ] **Code Quality**: Well-documented, maintainable code

---

## 📅 Progress Tracking

**Start Date**: _______________  
**Phase 1 Complete**: _______________  
**Phase 2 Complete**: _______________  
**Phase 3 Complete**: _______________  
**Final Completion**: _______________

---

## 🔄 Rollback Plan

If critical issues arise:
1. [ ] Revert to previous commit
2. [ ] Run full test suite to verify stability
3. [ ] Document issues encountered
4. [ ] Plan fixes for next iteration

---

**Last Updated**: _______________

