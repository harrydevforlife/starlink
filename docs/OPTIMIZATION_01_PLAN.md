# Optimization #1: Expression Evaluation Vectorization

## 📋 Overview

**Goal**: Replace row-by-row expression evaluation with PyArrow's vectorized compute functions to achieve 10-100x performance improvement.

**Current Problem**: 
- Expressions iterate row-by-row, building Python lists before converting to Arrow arrays
- High overhead from Python loops and list operations
- Not leveraging PyArrow's optimized C++ compute kernels

**Solution**: 
- Use `pyarrow.compute` functions for vectorized operations
- Direct array-to-array operations without Python loops
- Maintain backward compatibility with existing interface

---

## 🎯 Scope

### Files to Modify

1. **`src/starlink/physicalplan/expressions/booleanexpr.py`**
   - `BooleanExpression.evaluate_pair()` - vectorize comparison operations
   - `EqExpression`, `NeqExpression`, `LtExpression`, `LtEqExpression`, `GtExpression`, `GtEqExpression`
   - `AndExpression`, `OrExpression` - vectorize logical operations

2. **`src/starlink/physicalplan/expressions/mathexpr.py`**
   - `MathExpression.evaluate_pair()` - vectorize math operations
   - `AddExpression`, `SubtractExpression`, `MultiplyExpression`, `DivideExpression`

3. **`src/starlink/physicalplan/expressions/castexpr.py`**
   - `CastExpression.evaluate()` - vectorize type casting

### Files to Test

1. `tests/starlink/physicalplan/test_boolean_expr.py`
2. `tests/starlink/physicalplan/test_cast_expr.py`
3. `tests/starlink/execution/test_execution_context.py` (contains math and boolean tests)
4. All existing tests should continue to pass

---

## 📐 Implementation Plan

### Phase 1: Boolean Expressions (Priority: HIGH)

#### Step 1.1: Update BooleanExpression Base Class
- **File**: `booleanexpr.py`
- **Change**: Modify `evaluate_pair()` to use PyArrow compute functions
- **Strategy**: 
  - Extract PyArrow arrays from `ColumnVector.field`
  - Use `pc.equal()`, `pc.not_equal()`, `pc.less()`, `pc.less_equal()`, `pc.greater()`, `pc.greater_equal()`
  - Handle type compatibility (ensure both arrays have same type)
  - Return `ArrowFieldVector` wrapping the result

#### Step 1.2: Update Comparison Expressions
- **Expressions**: `EqExpression`, `NeqExpression`, `LtExpression`, `LtEqExpression`, `GtExpression`, `GtEqExpression`
- **Change**: Override `evaluate_pair()` to use vectorized operations
- **Mapping**:
  - `EqExpression` → `pc.equal()`
  - `NeqExpression` → `pc.not_equal()`
  - `LtExpression` → `pc.less()`
  - `LtEqExpression` → `pc.less_equal()`
  - `GtExpression` → `pc.greater()`
  - `GtEqExpression` → `pc.greater_equal()`

#### Step 1.3: Update Logical Expressions
- **Expressions**: `AndExpression`, `OrExpression`
- **Change**: Use `pc.and_kleene()` and `pc.or_kleene()` for vectorized logical operations
- **Note**: Kleene logic handles nulls correctly (null AND true = null, null OR false = null)

#### Step 1.4: Handle Edge Cases
- **String comparisons**: PyArrow compute handles strings natively
- **Null handling**: PyArrow compute functions handle nulls automatically
- **Type mismatches**: Add validation before compute operations
- **ChunkedArray**: Ensure we handle both Array and ChunkedArray

### Phase 2: Math Expressions (Priority: HIGH)

#### Step 2.1: Update MathExpression Base Class
- **File**: `mathexpr.py`
- **Change**: Modify `evaluate_pair()` to use PyArrow compute functions
- **Strategy**:
  - Extract PyArrow arrays from `ColumnVector.field`
  - Use `pc.add()`, `pc.subtract()`, `pc.multiply()`, `pc.divide()`
  - Handle nulls (PyArrow compute handles nulls automatically)
  - Handle division by zero (PyArrow returns null for divide by zero)

#### Step 2.2: Update Math Expression Classes
- **Expressions**: `AddExpression`, `SubtractExpression`, `MultiplyExpression`, `DivideExpression`
- **Mapping**:
  - `AddExpression` → `pc.add()`
  - `SubtractExpression` → `pc.subtract()`
  - `MultiplyExpression` → `pc.multiply()`
  - `DivideExpression` → `pc.divide()` (handles divide-by-zero automatically)

#### Step 2.3: Handle Edge Cases
- **Null handling**: PyArrow compute handles nulls (null + 5 = null)
- **Division by zero**: PyArrow returns null (5 / 0 = null)
- **Type promotion**: PyArrow handles type promotion automatically (int + float = float)
- **Overflow**: PyArrow handles overflow according to Arrow spec

### Phase 3: Cast Expression (Priority: MEDIUM)

#### Step 3.1: Update CastExpression
- **File**: `castexpr.py`
- **Change**: Use `pc.cast()` for vectorized type casting
- **Strategy**:
  - Extract PyArrow array from `ColumnVector.field`
  - Use `pc.cast(array, target_type)` with appropriate options
  - Handle string-to-number conversions (may need custom logic)
  - Handle number-to-string conversions

#### Step 3.2: Handle Special Cases
- **String to number**: May need to use `pc.cast()` with `CastOptions` or custom logic
- **Number to string**: Use `pc.cast()` or `pc.binary_join_element_wise()`
- **Null handling**: PyArrow cast preserves nulls

---

## ✅ Implementation Checklist

### Pre-Implementation
- [ ] Review PyArrow compute function documentation
- [ ] Test PyArrow compute functions with various data types
- [ ] Identify all edge cases (nulls, type mismatches, etc.)
- [ ] Create backup branch for rollback if needed

### Phase 1: Boolean Expressions
- [ ] **1.1** Update `BooleanExpression.evaluate_pair()` to extract arrays
- [ ] **1.2** Implement `EqExpression` with `pc.equal()`
- [ ] **1.3** Implement `NeqExpression` with `pc.not_equal()`
- [ ] **1.4** Implement `LtExpression` with `pc.less()`
- [ ] **1.5** Implement `LtEqExpression` with `pc.less_equal()`
- [ ] **1.6** Implement `GtExpression` with `pc.greater()`
- [ ] **1.7** Implement `GtEqExpression` with `pc.greater_equal()`
- [ ] **1.8** Implement `AndExpression` with `pc.and_kleene()`
- [ ] **1.9** Implement `OrExpression` with `pc.or_kleene()`
- [ ] **1.10** Add type validation before compute operations
- [ ] **1.11** Handle ChunkedArray if needed (convert to Array or handle directly)
- [ ] **1.12** Test all boolean expressions with existing tests
- [ ] **1.13** Test with null values
- [ ] **1.14** Test with different data types (int, float, string, bool)

### Phase 2: Math Expressions
- [ ] **2.1** Update `MathExpression.evaluate_pair()` to extract arrays
- [ ] **2.2** Implement `AddExpression` with `pc.add()`
- [ ] **2.3** Implement `SubtractExpression` with `pc.subtract()`
- [ ] **2.4** Implement `MultiplyExpression` with `pc.multiply()`
- [ ] **2.5** Implement `DivideExpression` with `pc.divide()`
- [ ] **2.6** Test division by zero (should return null)
- [ ] **2.7** Test null handling (null + 5 = null)
- [ ] **2.8** Test type promotion (int + float = float)
- [ ] **2.9** Test all math expressions with existing tests
- [ ] **2.10** Test with different numeric types (int8, int16, int32, int64, float32, float64)

### Phase 3: Cast Expression
- [ ] **3.1** Update `CastExpression.evaluate()` to use `pc.cast()`
- [ ] **3.2** Test casting between numeric types
- [ ] **3.3** Test casting from string to number
- [ ] **3.4** Test casting from number to string
- [ ] **3.5** Test null preservation during cast
- [ ] **3.6** Test all cast expressions with existing tests

### Testing & Validation
- [ ] **T.1** Run all existing tests: `pytest tests/starlink/physicalplan/`
- [ ] **T.2** Run execution context tests: `pytest tests/starlink/execution/`
- [ ] **T.3** Run integration tests: `pytest tests/starlink/`
- [ ] **T.4** Test with large datasets (performance validation)
- [ ] **T.5** Compare performance before/after (benchmark)
- [ ] **T.6** Verify correctness matches old implementation
- [ ] **T.7** Test edge cases (nulls, empty arrays, single element arrays)

### Code Quality
- [ ] **C.1** Add docstrings explaining vectorized approach
- [ ] **C.2** Add comments for non-obvious PyArrow compute usage
- [ ] **C.3** Remove old row-by-row code (or mark as deprecated)
- [ ] **C.4** Update type hints if needed
- [ ] **C.5** Ensure code follows existing style

### Documentation
- [ ] **D.1** Update PERFORMANCE_OPTIMIZATION.md with completion status
- [ ] **D.2** Document any limitations or known issues
- [ ] **D.3** Add performance benchmarks/results

---

## 🔍 Technical Details

### PyArrow Compute Function Mapping

| Expression | PyArrow Compute Function | Notes |
|------------|-------------------------|-------|
| `EqExpression` | `pc.equal(left, right)` | Handles all types including strings |
| `NeqExpression` | `pc.not_equal(left, right)` | Handles all types |
| `LtExpression` | `pc.less(left, right)` | Numeric and string comparison |
| `LtEqExpression` | `pc.less_equal(left, right)` | Numeric and string comparison |
| `GtExpression` | `pc.greater(left, right)` | Numeric and string comparison |
| `GtEqExpression` | `pc.greater_equal(left, right)` | Numeric and string comparison |
| `AndExpression` | `pc.and_kleene(left, right)` | Kleene logic for nulls |
| `OrExpression` | `pc.or_kleene(left, right)` | Kleene logic for nulls |
| `AddExpression` | `pc.add(left, right)` | Handles nulls, type promotion |
| `SubtractExpression` | `pc.subtract(left, right)` | Handles nulls, type promotion |
| `MultiplyExpression` | `pc.multiply(left, right)` | Handles nulls, type promotion |
| `DivideExpression` | `pc.divide(left, right)` | Returns null for divide-by-zero |
| `CastExpression` | `pc.cast(array, target_type)` | May need options for some casts |

### Array Extraction Pattern

```python
def evaluate_pair(self, l: ColumnVector, r: ColumnVector) -> ColumnVector:
    # Extract PyArrow arrays from ColumnVector
    left_array = l.field if isinstance(l, ArrowFieldVector) else l.field
    right_array = r.field if isinstance(r, ArrowFieldVector) else r.field
    
    # Ensure both are Arrays (not ChunkedArray)
    if isinstance(left_array, pa.ChunkedArray):
        left_array = left_array.combine_chunks()
    if isinstance(right_array, pa.ChunkedArray):
        right_array = right_array.combine_chunks()
    
    # Perform vectorized operation
    result = pc.equal(left_array, right_array)  # Example
    
    # Return wrapped result
    return ArrowFieldVector(result)
```

### Error Handling

1. **Type Mismatch**: Validate types before compute operations
2. **ChunkedArray**: Convert to Array using `combine_chunks()` if needed
3. **Size Mismatch**: PyArrow will raise error automatically
4. **Unsupported Types**: PyArrow will raise error, catch and provide helpful message

### Backward Compatibility

- Keep `_evaluate_value()` methods for now (may be used elsewhere)
- Keep interface unchanged (return `ColumnVector`)
- Maintain same null handling behavior
- Maintain same error messages where possible

---

## 🧪 Testing Strategy

### Unit Tests
- Test each expression type individually
- Test with different data types
- Test with null values
- Test with empty arrays
- Test with single element arrays

### Integration Tests
- Test expressions in projection
- Test expressions in selection (filter)
- Test expressions in aggregation
- Test complex expressions (nested)

### Performance Tests
- Benchmark before/after
- Test with large arrays (10K, 100K, 1M elements)
- Measure speedup achieved

### Edge Case Tests
- Null handling
- Type mismatches
- Empty arrays
- Division by zero
- Overflow conditions

---

## 📊 Success Criteria

1. ✅ All existing tests pass
2. ✅ Performance improvement: 10-100x faster for expression evaluation
3. ✅ No regression in functionality
4. ✅ Correct null handling
5. ✅ Correct type handling
6. ✅ Code is maintainable and well-documented

---

## 🚨 Risks & Mitigation

### Risk 1: PyArrow compute function limitations
- **Mitigation**: Test thoroughly, fallback to row-by-row if needed
- **Detection**: Unit tests will catch issues

### Risk 2: Behavior differences with nulls
- **Mitigation**: Test null handling extensively, document differences
- **Detection**: Null handling tests

### Risk 3: Type promotion differences
- **Mitigation**: Test type promotion, document behavior
- **Detection**: Type-specific tests

### Risk 4: Performance not as expected
- **Mitigation**: Profile and benchmark, identify bottlenecks
- **Detection**: Performance benchmarks

---

## 📝 Notes

- PyArrow compute functions are highly optimized C++ kernels
- Vectorization eliminates Python loop overhead
- Null handling is automatic and correct in PyArrow
- Type promotion is handled automatically
- Some operations may need special handling (e.g., string-to-number cast)

---

## 🔄 Rollback Plan

If issues arise:
1. Revert changes to affected files
2. Run all tests to ensure system is stable
3. Investigate issues in isolation
4. Re-implement with fixes

---

## 📅 Estimated Timeline

- **Phase 1 (Boolean)**: 2-3 hours
- **Phase 2 (Math)**: 1-2 hours
- **Phase 3 (Cast)**: 1-2 hours
- **Testing**: 2-3 hours
- **Total**: 6-10 hours

---

## 🎓 Learning Resources

- PyArrow Compute Functions: https://arrow.apache.org/docs/python/compute.html
- PyArrow API Reference: https://arrow.apache.org/docs/python/api/compute.html
- Arrow Compute Kernels: https://arrow.apache.org/docs/cpp/compute.html

