# Optimization #4: HashAggregateExec Batch Processing - Checklist

## 📋 Quick Reference

**Goal**: Optimize HashAggregateExec to process rows in batches  
**Expected Impact**: 5-50x speedup for aggregate queries  
**Files**: `hashaggexec.py`

---

## ✅ Implementation Checklist

### Pre-Implementation Setup
- [ ] Create feature branch: `git checkout -b optimize/hash-aggregate-batch`
- [ ] Review HashAggregateExec implementation
- [ ] Understand Accumulator interface
- [ ] Test batch value extraction in Python REPL
- [ ] Identify all test files that use aggregation

### Phase 1: Analysis & Understanding
- [ ] **1.1** Read current `HashAggregateExec.execute()` implementation
- [ ] **1.2** Identify performance bottlenecks:
  - [ ] Row-by-row value extraction
  - [ ] Tuple key creation in loop
  - [ ] Bytes-to-string conversion in loop
  - [ ] Dictionary lookups for each row
  - [ ] Accumulator.accumulate() called row-by-row
- [ ] **1.3** Document current behavior for reference

### Phase 2: Batch Value Extraction ⚡ HIGH PRIORITY

#### Extract Values from Grouping Columns
- [ ] **2.1** Extract all values from each grouping column at once
- [ ] **2.2** Use ArrowFieldVector.field to get PyArrow arrays
- [ ] **2.3** Handle ChunkedArray (combine chunks if needed)
- [ ] **2.4** Extract values: `values = [arr[i].as_py() for i in range(len(arr))]`
- [ ] **2.5** Fallback to getValue() for non-ArrowFieldVector columns

#### Batch Convert Bytes to Strings
- [ ] **2.6** Batch convert bytes to strings for all values
- [ ] **2.7** Use list comprehension: `[v.decode('utf-8') if isinstance(v, bytes) else v for v in values]`
- [ ] **2.8** Test bytes conversion correctness

#### Batch Create Grouping Keys
- [ ] **2.9** Use zip to create all keys at once: `keys = list(zip(*group_values))`
- [ ] **2.10** Verify keys match row-by-row approach
- [ ] **2.11** Test key creation correctness

#### Extract Aggregate Input Values
- [ ] **2.12** Extract all values from aggregate input columns at once
- [ ] **2.13** Use same batch extraction approach
- [ ] **2.14** Store values in list of lists: `aggr_values[i][row_index]`

### Phase 3: Optimize Accumulator Processing ⚡ HIGH PRIORITY

#### Group Rows by Key
- [ ] **3.1** Use defaultdict to group row indices by key
- [ ] **3.2** Create: `key_to_indices = defaultdict(list)`
- [ ] **3.3** Populate: `for row_index, key in enumerate(keys): key_to_indices[key].append(row_index)`
- [ ] **3.4** Verify grouping correctness

#### Pre-allocate Accumulators
- [ ] **3.5** Create accumulators for all unique keys upfront
- [ ] **3.6** Iterate over unique keys: `for key in key_to_indices:`
- [ ] **3.7** Create accumulators: `groups[key] = [ae.createAccumulator() for ae in self.aggregateExpr]`
- [ ] **3.8** Verify accumulator creation

#### Batch Accumulate Values
- [ ] **3.9** Accumulate values in batches per group
- [ ] **3.10** For each key: `for key, row_indices in key_to_indices.items()`
- [ ] **3.11** For each accumulator: `for i, acc in enumerate(accs)`
- [ ] **3.12** Accumulate all values: `for row_index in row_indices: acc.accumulate(aggr_values[i][row_index])`
- [ ] **3.13** Verify accumulation correctness

#### Cleanup
- [ ] **3.14** Remove old row-by-row processing code
- [ ] **3.15** Remove old tuple key creation in loop
- [ ] **3.16** Remove old bytes conversion in loop

### Phase 4: Testing 🔗

#### Basic Functionality Tests
- [ ] **4.1** Run: `pytest tests/starlink/physicalplan/test_aggregate.py -v`
- [ ] **4.2** Test with single grouping column
- [ ] **4.3** Test with multiple grouping columns (2, 3 columns)
- [ ] **4.4** Test with single aggregate function
- [ ] **4.5** Test with multiple aggregate functions (SUM, MIN, MAX together)

#### Aggregate Function Tests
- [ ] **4.6** Test SUM aggregation
- [ ] **4.7** Test MIN aggregation
- [ ] **4.8** Test MAX aggregation
- [ ] **4.9** Test COUNT aggregation (if available)
- [ ] **4.10** Test AVG aggregation (if available)

#### Edge Case Tests
- [ ] **4.11** Test with null values in grouping keys
- [ ] **4.12** Test with null values in aggregate inputs
- [ ] **4.13** Test with empty input (no rows)
- [ ] **4.14** Test with single row input
- [ ] **4.15** Test with single group (all rows same key)
- [ ] **4.16** Test with many groups (each row different key)
- [ ] **4.17** Test with large groups (many rows per key)

#### Data Type Tests
- [ ] **4.18** Test with integer grouping keys
- [ ] **4.19** Test with string grouping keys
- [ ] **4.20** Test with mixed type grouping keys
- [ ] **4.21** Test with bytes in grouping keys (should convert to string)

#### Integration Tests
- [ ] **4.22** Test aggregation in DataFrame API: `df.aggregate(...)`
- [ ] **4.23** Test aggregation in SQL queries: `SELECT ... GROUP BY ...`
- [ ] **4.24** Test aggregation with filter: `df.filter(...).aggregate(...)`
- [ ] **4.25** Test aggregation with projection: `df.project(...).aggregate(...)`
- [ ] **4.26** Test nested aggregations (if any)

#### Full Test Suite
- [ ] **4.27** Run all physical plan tests: `pytest tests/starlink/physicalplan/ -v`
- [ ] **4.28** Run all execution tests: `pytest tests/starlink/execution/ -v`
- [ ] **4.29** Run all starlink tests: `pytest tests/starlink/ -v`
- [ ] **4.30** Verify no test failures

### Performance Validation 📊

#### Benchmarking
- [ ] **P.1** Create benchmark script for aggregation
- [ ] **P.2** Benchmark before implementation (baseline)
- [ ] **P.3** Benchmark after implementation
- [ ] **P.4** Calculate speedup achieved (target: 5-50x)
- [ ] **P.5** Document performance results

#### Large Dataset Testing
- [ ] **P.6** Test with 10K rows
- [ ] **P.7** Test with 100K rows
- [ ] **P.8** Test with 1M rows
- [ ] **P.9** Test with few groups (10 groups)
- [ ] **P.10** Test with many groups (10K groups)
- [ ] **P.11** Verify performance scales well

### Code Quality ✨

#### Code Review
- [ ] **C.1** Remove old row-by-row processing code
- [ ] **C.2** Add docstrings explaining batch approach
- [ ] **C.3** Add inline comments for batch operations
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

1. **ChunkedArray in Grouping Columns**
   - [ ] Check if grouping column arrays are ChunkedArray
   - [ ] Convert to Array using `combine_chunks()` if needed
   - [ ] Test with ChunkedArray inputs

2. **Null Handling**
   - [ ] Verify nulls in grouping keys work correctly
   - [ ] Verify nulls in aggregate inputs work correctly
   - [ ] Test null handling scenarios
   - [ ] Document behavior

3. **Bytes to String Conversion**
   - [ ] Verify bytes conversion works for all cases
   - [ ] Test with different byte encodings
   - [ ] Handle edge cases (empty bytes, etc.)

4. **Key Uniqueness**
   - [ ] Verify tuple keys maintain uniqueness
   - [ ] Test with duplicate keys
   - [ ] Test with hash collisions (if any)

5. **Accumulator Interface**
   - [ ] Verify accumulator interface is maintained
   - [ ] Test with different accumulator types
   - [ ] Ensure finalValue() works correctly

---

## 📝 Implementation Notes

### Code Pattern Template

```python
def execute(self) -> Sequence[RecordBatch]:
    groups: Dict[Tuple[Any, ...], List[Accumulator]] = {}
    
    for batch in self.input.execute():
        # Evaluate expressions
        group_keys_columns = [expr.evaluate(batch) for expr in self.groupExpr]
        aggr_input_columns = [ae.inputExpression().evaluate(batch) for ae in self.aggregateExpr]
        
        row_count = batch.rowCount()
        
        # Batch extract values from grouping columns
        group_values = []
        for col in group_keys_columns:
            if isinstance(col, ArrowFieldVector):
                arr = col.field
                if isinstance(arr, pa.ChunkedArray):
                    arr = arr.combine_chunks()
                values = [arr[i].as_py() for i in range(len(arr))]
            else:
                values = [col.getValue(i) for i in range(row_count)]
            
            # Batch convert bytes to strings
            converted_values = [
                v.decode('utf-8') if isinstance(v, (bytes, bytearray)) else v
                for v in values
            ]
            group_values.append(converted_values)
        
        # Batch create grouping keys
        keys = list(zip(*group_values))
        
        # Batch extract aggregate input values
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
        
        # Group rows by key
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
                for row_index in row_indices:
                    value = aggr_values[i][row_index]
                    acc.accumulate(value)
    
    # Build output (same as before)
    # ...
```

### Key Optimization Points

1. **Batch Value Extraction**: Extract all values at once instead of row-by-row
2. **Batch Key Creation**: Use zip to create all keys at once
3. **Grouped Accumulation**: Group rows by key first, then accumulate in batches
4. **Reduced Lookups**: Pre-allocate accumulators to reduce dictionary lookups

### Error Handling

1. **ChunkedArray**: Convert to Array if needed
2. **Type Mismatches**: Handle different value types correctly
3. **Null Values**: Ensure null handling is correct
4. **Empty Batches**: Handle gracefully

### Backward Compatibility

- Keep interface unchanged (return `Sequence[RecordBatch]`)
- Maintain same aggregation behavior
- Maintain same null handling
- Maintain same accumulator interface

---

## 🎯 Success Metrics

- [ ] **Functionality**: All existing tests pass (100%)
- [ ] **Performance**: 5-50x speedup for aggregate queries
- [ ] **Correctness**: No regressions in behavior
- [ ] **Code Quality**: Well-documented, maintainable code

---

## 📅 Progress Tracking

**Start Date**: _______________  
**Phase 1 Complete**: _______________  
**Phase 2 Complete**: _______________  
**Phase 3 Complete**: _______________  
**Phase 4 Complete**: _______________  
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

