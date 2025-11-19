# Optimization #1: Expression Evaluation Vectorization - Checklist

## 📋 Quick Reference

**Goal**: Vectorize expression evaluation using PyArrow compute functions  
**Expected Impact**: 10-100x performance improvement  
**Files**: `booleanexpr.py`, `mathexpr.py`, `castexpr.py`

---

## ✅ Implementation Checklist

### Pre-Implementation Setup
- [ ] Create feature branch: `git checkout -b optimize/expression-vectorization`
- [ ] Review PyArrow compute documentation
- [ ] Test PyArrow compute functions in Python REPL
- [ ] Identify all test files that need to pass

### Phase 1: Boolean Expressions ⚡ HIGH PRIORITY

#### BooleanExpression Base Class
- [ ] Import `pyarrow.compute as pc` in `booleanexpr.py`
- [ ] Update `evaluate_pair()` to extract PyArrow arrays from ColumnVector
- [ ] Handle ChunkedArray (convert to Array if needed)
- [ ] Add type validation before compute operations

#### Comparison Expressions
- [ ] **EqExpression**: Replace row-by-row with `pc.equal()`
- [ ] **NeqExpression**: Replace row-by-row with `pc.not_equal()`
- [ ] **LtExpression**: Replace row-by-row with `pc.less()`
- [ ] **LtEqExpression**: Replace row-by-row with `pc.less_equal()`
- [ ] **GtExpression**: Replace row-by-row with `pc.greater()`
- [ ] **GtEqExpression**: Replace row-by-row with `pc.greater_equal()`

#### Logical Expressions
- [ ] **AndExpression**: Replace row-by-row with `pc.and_kleene()`
- [ ] **OrExpression**: Replace row-by-row with `pc.or_kleene()`

#### Phase 1 Testing
- [ ] Run: `pytest tests/starlink/physicalplan/test_boolean_expr.py -v`
- [ ] Test with integers
- [ ] Test with floats
- [ ] Test with strings
- [ ] Test with booleans
- [ ] Test with null values
- [ ] Test with empty arrays
- [ ] Test with single element arrays

### Phase 2: Math Expressions ⚡ HIGH PRIORITY

#### MathExpression Base Class
- [ ] Import `pyarrow.compute as pc` in `mathexpr.py`
- [ ] Update `evaluate_pair()` to extract PyArrow arrays
- [ ] Handle ChunkedArray (convert to Array if needed)
- [ ] Add type validation

#### Math Expression Classes
- [ ] **AddExpression**: Replace row-by-row with `pc.add()`
- [ ] **SubtractExpression**: Replace row-by-row with `pc.subtract()`
- [ ] **MultiplyExpression**: Replace row-by-row with `pc.multiply()`
- [ ] **DivideExpression**: Replace row-by-row with `pc.divide()`

#### Phase 2 Testing
- [ ] Run: `pytest tests/starlink/execution/test_execution_context.py::TestExecutionContext::test_float_math -v`
- [ ] Test addition with integers
- [ ] Test addition with floats
- [ ] Test subtraction
- [ ] Test multiplication
- [ ] Test division (including divide-by-zero → should return null)
- [ ] Test with null values (null + 5 = null)
- [ ] Test type promotion (int + float = float)
- [ ] Test with different numeric types (int8, int16, int32, int64, float32, float64)

### Phase 3: Cast Expression ⚠️ MEDIUM PRIORITY

#### CastExpression
- [ ] Import `pyarrow.compute as pc` in `castexpr.py`
- [ ] Update `evaluate()` to use `pc.cast()`
- [ ] Handle string-to-number conversions
- [ ] Handle number-to-string conversions
- [ ] Handle null preservation

#### Phase 3 Testing
- [ ] Run: `pytest tests/starlink/physicalplan/test_cast_expr.py -v`
- [ ] Test casting between numeric types (int8→int32, float32→float64, etc.)
- [ ] Test casting from string to number
- [ ] Test casting from number to string
- [ ] Test null preservation during cast
- [ ] Test invalid cast (should raise error)

### Integration Testing 🔗

#### Full Test Suite
- [ ] Run all physical plan tests: `pytest tests/starlink/physicalplan/ -v`
- [ ] Run execution context tests: `pytest tests/starlink/execution/ -v`
- [ ] Run all starlink tests: `pytest tests/starlink/ -v`
- [ ] Verify no test failures

#### Specific Integration Tests
- [ ] `test_employees_in_co_using_dataframe` (uses Eq expression)
- [ ] `test_boolean_expressions` (uses And, Or)
- [ ] `test_float_math` (uses Add, Subtract, Multiply, Divide)
- [ ] `test_aggregate_query` (uses Max, Cast)

### Performance Validation 📊

#### Benchmarking
- [ ] Create benchmark script for expression evaluation
- [ ] Benchmark boolean expressions (before/after)
- [ ] Benchmark math expressions (before/after)
- [ ] Benchmark cast expressions (before/after)
- [ ] Document speedup achieved (target: 10-100x)

#### Large Dataset Testing
- [ ] Test with 10K elements
- [ ] Test with 100K elements
- [ ] Test with 1M elements
- [ ] Verify performance scales well

### Code Quality ✨

#### Code Review
- [ ] Remove or comment out old row-by-row code
- [ ] Add docstrings explaining vectorized approach
- [ ] Add inline comments for non-obvious PyArrow usage
- [ ] Ensure consistent code style
- [ ] Update type hints if needed

#### Documentation
- [ ] Update `PERFORMANCE_OPTIMIZATION.md` with completion status
- [ ] Document any limitations or edge cases
- [ ] Add performance benchmark results
- [ ] Update this checklist with completion date

### Final Validation ✅

#### Pre-Commit Checklist
- [ ] All tests pass
- [ ] No linter errors
- [ ] Code is well-documented
- [ ] Performance benchmarks show improvement
- [ ] No regressions in functionality

#### Commit & Merge
- [ ] Commit changes with descriptive message
- [ ] Create PR (if using PR workflow)
- [ ] Get code review approval
- [ ] Merge to main branch

---

## 🐛 Known Issues / Edge Cases

### To Handle During Implementation

1. **ChunkedArray Support**
   - [ ] Check if ColumnVector can contain ChunkedArray
   - [ ] Convert ChunkedArray to Array using `combine_chunks()` if needed
   - [ ] Test with ChunkedArray inputs

2. **Type Mismatches**
   - [ ] Validate types before compute operations
   - [ ] Provide helpful error messages
   - [ ] Test type mismatch scenarios

3. **Null Handling**
   - [ ] Verify PyArrow compute handles nulls correctly
   - [ ] Test null propagation (null + 5 = null)
   - [ ] Test null comparisons (null == null = null, not true)

4. **String Operations**
   - [ ] Verify string comparisons work with PyArrow compute
   - [ ] Test string-to-number casts
   - [ ] Test number-to-string casts

5. **Division by Zero**
   - [ ] Verify `pc.divide()` returns null for divide-by-zero
   - [ ] Test divide-by-zero scenarios
   - [ ] Document behavior

---

## 📝 Implementation Notes

### Code Pattern Template

```python
import pyarrow.compute as pc

def evaluate_pair(self, l: ColumnVector, r: ColumnVector) -> ColumnVector:
    # Extract PyArrow arrays
    left_array = l.field if isinstance(l, ArrowFieldVector) else l.field
    right_array = r.field if isinstance(r, ArrowFieldVector) else r.field
    
    # Handle ChunkedArray
    if isinstance(left_array, pa.ChunkedArray):
        left_array = left_array.combine_chunks()
    if isinstance(right_array, pa.ChunkedArray):
        right_array = right_array.combine_chunks()
    
    # Type validation
    if left_array.type != right_array.type:
        raise ValueError(f"Type mismatch: {left_array.type} != {right_array.type}")
    
    # Vectorized operation
    result = pc.equal(left_array, right_array)  # Example
    
    # Return wrapped result
    return ArrowFieldVector(result)
```

### PyArrow Compute Function Reference

| Operation | Function | Notes |
|-----------|----------|-------|
| Equal | `pc.equal(left, right)` | Works with all types |
| Not Equal | `pc.not_equal(left, right)` | Works with all types |
| Less | `pc.less(left, right)` | Numeric and string |
| Less Equal | `pc.less_equal(left, right)` | Numeric and string |
| Greater | `pc.greater(left, right)` | Numeric and string |
| Greater Equal | `pc.greater_equal(left, right)` | Numeric and string |
| And | `pc.and_kleene(left, right)` | Kleene logic for nulls |
| Or | `pc.or_kleene(left, right)` | Kleene logic for nulls |
| Add | `pc.add(left, right)` | Handles nulls, type promotion |
| Subtract | `pc.subtract(left, right)` | Handles nulls, type promotion |
| Multiply | `pc.multiply(left, right)` | Handles nulls, type promotion |
| Divide | `pc.divide(left, right)` | Returns null for divide-by-zero |
| Cast | `pc.cast(array, target_type)` | May need CastOptions |

---

## 🎯 Success Metrics

- [ ] **Functionality**: All existing tests pass (100%)
- [ ] **Performance**: 10-100x speedup for expression evaluation
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

