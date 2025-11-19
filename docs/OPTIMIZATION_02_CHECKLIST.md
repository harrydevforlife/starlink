# Optimization #2: SelectionExec Filtering Vectorization - Checklist

## 📋 Quick Reference

**Goal**: Vectorize filtering operations using PyArrow filter functions  
**Expected Impact**: 5-20x performance improvement  
**Files**: `selectionexec.py`

---

## ✅ Implementation Checklist

### Pre-Implementation Setup
- [ ] Create feature branch: `git checkout -b optimize/selection-filtering`
- [ ] Review PyArrow filter documentation
- [ ] Test PyArrow filter with RecordBatch in Python REPL
- [ ] Identify all test files that use filtering

### Phase 1: Analysis & Understanding
- [ ] **1.1** Read current `SelectionExec.execute()` implementation
- [ ] **1.2** Identify performance bottlenecks:
  - [ ] Python list mask building
  - [ ] Double iteration (sum + filter loop)
  - [ ] Row-by-row value extraction
  - [ ] ArrowVectorBuilder overhead
- [ ] **1.3** Document current behavior for reference

### Phase 2: Vectorized Implementation ⚡ HIGH PRIORITY

#### Extract Boolean Array
- [ ] **2.1** Import `pyarrow` and `pyarrow.compute` if needed
- [ ] **2.2** Extract boolean array from `sel_vec.field`
- [ ] **2.3** Verify `sel_vec` is `ArrowFieldVector`
- [ ] **2.4** Handle ChunkedArray (combine chunks if needed)
- [ ] **2.5** Verify boolean array type is `pa.bool_()`

#### Convert RecordBatch
- [ ] **2.6** Extract arrays from `batch.fields`: `arrays = [vec.field for vec in batch.fields]`
- [ ] **2.7** Create PyArrow schema from `batch.schema`
- [ ] **2.8** Create PyArrow RecordBatch: `pa.RecordBatch.from_arrays(arrays, schema=pa_schema)`
- [ ] **2.9** Test conversion (ensure no data loss)

#### Apply Vectorized Filter
- [ ] **2.10** Apply filter: `filtered_pa_batch = pa_batch.filter(bool_array)`
- [ ] **2.11** Verify filtered batch has correct number of rows
- [ ] **2.12** Verify all columns are filtered correctly

#### Convert Back to Our RecordBatch
- [ ] **2.13** Extract columns from filtered PyArrow RecordBatch
- [ ] **2.14** Wrap columns in `ArrowFieldVector`
- [ ] **2.15** Create our `RecordBatch` with filtered vectors
- [ ] **2.16** Verify schema matches original

#### Cleanup
- [ ] **2.17** Remove Python list mask building: `mask = [...]`
- [ ] **2.18** Remove double iteration: `sum(mask)` and filter loop
- [ ] **2.19** Remove row-by-row filtering code
- [ ] **2.20** Remove `ArrowVectorBuilder` usage for filtering

### Phase 3: Testing 🔗

#### Basic Functionality Tests
- [ ] **3.1** Run: `pytest tests/starlink/execution/test_execution_context.py -v`
- [ ] **3.2** Test simple filter: `state == 'CO'`
- [ ] **3.3** Test complex filter: `state == 'CO' AND salary > 10000`
- [ ] **3.4** Test with boolean expressions (And, Or)
- [ ] **3.5** Test with comparison expressions (Eq, Gt, Lt, etc.)

#### Edge Case Tests
- [ ] **3.6** Test with null values in data
- [ ] **3.7** Test with null values in filter result (should be treated as False)
- [ ] **3.8** Test with empty filter result (all False - no rows match)
- [ ] **3.9** Test with all True filter (no filtering - all rows match)
- [ ] **3.10** Test with single row batch
- [ ] **3.11** Test with empty batch (0 rows)

#### Data Type Tests
- [ ] **3.12** Test filtering with integer columns
- [ ] **3.13** Test filtering with float columns
- [ ] **3.14** Test filtering with string columns
- [ ] **3.15** Test filtering with boolean columns
- [ ] **3.16** Test filtering with mixed data types

#### Integration Tests
- [ ] **3.17** Test filter in DataFrame API: `df.filter(...)`
- [ ] **3.18** Test filter in SQL queries: `SELECT ... WHERE ...`
- [ ] **3.19** Test filter with projection: `df.filter(...).project(...)`
- [ ] **3.20** Test filter with aggregation: `df.filter(...).aggregate(...)`
- [ ] **3.21** Test nested filters (filter after filter)

#### Full Test Suite
- [ ] **3.22** Run all physical plan tests: `pytest tests/starlink/physicalplan/ -v`
- [ ] **3.23** Run all execution tests: `pytest tests/starlink/execution/ -v`
- [ ] **3.24** Run all starlink tests: `pytest tests/starlink/ -v`
- [ ] **3.25** Verify no test failures

### Performance Validation 📊

#### Benchmarking
- [ ] **P.1** Create benchmark script for filtering operations
- [ ] **P.2** Benchmark before implementation (baseline)
- [ ] **P.3** Benchmark after implementation
- [ ] **P.4** Calculate speedup achieved (target: 5-20x)
- [ ] **P.5** Document performance results

#### Large Dataset Testing
- [ ] **P.6** Test with 10K rows
- [ ] **P.7** Test with 100K rows
- [ ] **P.8** Test with 1M rows
- [ ] **P.9** Verify performance scales well
- [ ] **P.10** Profile memory usage (should be similar or better)

### Code Quality ✨

#### Code Review
- [ ] **C.1** Remove old row-by-row filtering code
- [ ] **C.2** Add docstrings explaining vectorized approach
- [ ] **C.3** Add inline comments for PyArrow operations
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
- [ ] **F.5** No regressions in functionality

#### Commit & Merge
- [ ] **F.6** Commit changes with descriptive message
- [ ] **F.7** Create PR (if using PR workflow)
- [ ] **F.8** Get code review approval
- [ ] **F.9** Merge to main branch

---

## 🐛 Known Issues / Edge Cases

### To Handle During Implementation

1. **ChunkedArray in Boolean Mask**
   - [ ] Check if boolean array is ChunkedArray
   - [ ] Convert to Array using `combine_chunks()` if needed
   - [ ] Test with ChunkedArray inputs

2. **Null Handling**
   - [ ] Verify nulls in mask are treated as False
   - [ ] Test null handling scenarios
   - [ ] Document behavior

3. **Empty Results**
   - [ ] Verify empty filter results work correctly
   - [ ] Test with all False mask
   - [ ] Ensure empty RecordBatch is returned correctly

4. **Schema Conversion**
   - [ ] Verify schema conversion preserves field order
   - [ ] Test with different schema types
   - [ ] Ensure field names are preserved

5. **Type Compatibility**
   - [ ] Verify all data types work with filter
   - [ ] Test with nested types (if any)
   - [ ] Test with dictionary types (if any)

---

## 📝 Implementation Notes

### Code Pattern Template

```python
def execute(self) -> Sequence[RecordBatch]:
    def generator() -> Iterator[RecordBatch]:
        for batch in self.input.execute():
            # Evaluate filter expression
            sel_vec = self.expr.evaluate(batch)
            
            # Extract boolean array from ArrowFieldVector
            if not isinstance(sel_vec, ArrowFieldVector):
                raise ValueError(f"SelectionExec requires ArrowFieldVector, got {type(sel_vec)}")
            
            bool_array = sel_vec.field
            
            # Handle ChunkedArray
            if isinstance(bool_array, pa.ChunkedArray):
                bool_array = bool_array.combine_chunks()
            
            # Convert our RecordBatch to PyArrow RecordBatch
            arrays = [vec.field for vec in batch.fields]
            pa_schema = pa.schema([
                pa.field(f.name, f.dataType) 
                for f in batch.schema.fields
            ])
            pa_batch = pa.RecordBatch.from_arrays(arrays, schema=pa_schema)
            
            # Apply vectorized filter
            filtered_pa_batch = pa_batch.filter(bool_array)
            
            # Convert back to our RecordBatch
            filtered_columns = filtered_pa_batch.columns
            vectors = [ArrowFieldVector(col) for col in filtered_columns]
            
            yield RecordBatch(batch.schema, vectors)
    
    return generator()
```

### PyArrow Filter API Reference

| Operation | Method | Notes |
|-----------|--------|-------|
| Filter RecordBatch | `batch.filter(mask)` | Filters all columns at once |
| Filter Table | `table.filter(mask)` | Filters all columns at once |
| Filter Array | `pc.filter(array, mask)` | Filters single array |

### Error Handling

1. **Type Validation**: Ensure `sel_vec` is `ArrowFieldVector`
2. **ChunkedArray**: Convert to Array if needed
3. **Size Mismatch**: PyArrow will raise error automatically
4. **Empty Results**: PyArrow handles correctly

### Backward Compatibility

- Keep interface unchanged (return `Sequence[RecordBatch]`)
- Maintain same filtering behavior
- Maintain same null handling
- Maintain same error messages where possible

---

## 🎯 Success Metrics

- [ ] **Functionality**: All existing tests pass (100%)
- [ ] **Performance**: 5-20x speedup for filtering operations
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

