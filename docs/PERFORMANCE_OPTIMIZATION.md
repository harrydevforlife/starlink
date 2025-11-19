# Performance Optimization Opportunities for Starlink

## Executive Summary

This document identifies key performance optimization opportunities in the Starlink query engine. The analysis focuses on bottlenecks in expression evaluation, data processing, and memory management.

---

## 1. **Expression Evaluation: Row-by-Row Processing** 🔴 HIGH IMPACT

### Current Implementation
- **Location**: `booleanexpr.py`, `mathexpr.py`
- **Issue**: Expressions iterate row-by-row, building Python lists before converting to Arrow arrays
- **Example**:
  ```python
  # booleanexpr.py:59-61
  out: List[bool] = []
  for i in range(size):
      out.append(self._evaluate_value(l.getValue(i), r.getValue(i), dtype))
  return ArrowFieldVector(pa.array(out, type=pa.bool_()))
  ```

### Optimization
**Use PyArrow Compute Functions** for vectorized operations:
```python
import pyarrow.compute as pc

# Instead of row-by-row iteration:
# Use vectorized operations
result = pc.equal(left_vec.field, right_vec.field)  # For EqExpression
result = pc.add(left_vec.field, right_vec.field)   # For AddExpression
return ArrowFieldVector(result)
```

**Expected Impact**: 10-100x speedup for expression evaluation

**Files to Modify**:
- `src/starlink/physicalplan/expressions/booleanexpr.py`
- `src/starlink/physicalplan/expressions/mathexpr.py`
- `src/starlink/physicalplan/expressions/castexpr.py`

---

## 2. **SelectionExec: Inefficient Filtering** 🔴 HIGH IMPACT

### Current Implementation
- **Location**: `selectionexec.py:79-104`
- **Issues**:
  1. Builds boolean mask as Python list: `mask = [bool(sel_vec.getValue(i)) for i in range(sel_vec.size())]`
  2. Iterates over mask twice (once to count, once to filter)
  3. Row-by-row filtering for each column

### Optimization
**Use PyArrow Filter Operations**:
```python
# Get boolean array directly from expression
bool_array = sel_vec.field  # Already a PyArrow boolean array

# Use PyArrow's filter function for each column
filtered_columns = []
for col_index in range(batch.columnCount()):
    col_array = batch.field(col_index).field
    filtered = pc.filter(col_array, bool_array)
    filtered_columns.append(ArrowFieldVector(filtered))
```

**Expected Impact**: 5-20x speedup for filtering operations

---

## 3. **CSV Data Source: Batch Accumulation Overhead** 🟡 MEDIUM IMPACT

### Current Implementation
- **Location**: `csv.py:214-250`
- **Issues**:
  1. Converts batches to Table multiple times: `pa.Table.from_batches(accumulated_batches)`
  2. Slices table and converts back to batches
  3. Creates ArrowFieldVector wrappers for each column

### Optimization
**Stream batches directly without accumulation**:
```python
# Let PyArrow handle batching natively
reader = pacsv.open_csv(
    self.filename,
    read_options=read_options,
    parse_options=parse_options,
    convert_options=convert_options,
)

# Use PyArrow's batch_size parameter if available
# Or accumulate more efficiently using pa.concat_arrays
```

**Alternative**: Use PyArrow's `read_csv` with `batch_size` parameter and stream results.

**Expected Impact**: 2-5x reduction in memory overhead, faster batch processing

---

## 4. **HashAggregateExec: Row-by-Row Processing** 🔴 HIGH IMPACT

### Current Implementation
- **Location**: `hashaggexec.py:136-191`
- **Issues**:
  1. Processes rows one-by-one: `for row_index in range(row_count)`
  2. Creates tuple keys for each row
  3. Converts bytes to strings for each key element

### Optimization
**Batch Processing with Vectorized Grouping**:
```python
# Evaluate all grouping expressions at once
group_keys_columns = [expr.evaluate(batch) for expr in self.groupExpr]

# Use PyArrow's group_by or hash_aggregate functions
# Or use pandas groupby on Arrow data (if available)

# Process in chunks rather than row-by-row
```

**Alternative**: Use PyArrow's compute functions for grouping and aggregation when possible.

**Expected Impact**: 5-50x speedup for aggregate queries

---

## 5. **Memory: Unnecessary ArrowFieldVector Wrappers** 🟡 MEDIUM IMPACT

### Current Implementation
- **Location**: Multiple files
- **Issue**: Creates `ArrowFieldVector` wrappers around PyArrow arrays, adding indirection

### Optimization
**Use PyArrow Arrays Directly**:
- Consider using PyArrow arrays directly in RecordBatch
- Only wrap when necessary for interface compatibility
- Cache ArrowFieldVector instances when possible

**Expected Impact**: Reduced memory overhead, faster access

---

## 6. **Schema Creation Overhead** 🟢 LOW IMPACT

### Current Implementation
- **Location**: Multiple files (e.g., `parquet.py:79`, `csv.py:239`)
- **Issue**: Creates new Schema objects for each batch

### Optimization
**Cache Schemas**:
```python
# Cache schema per data source
self._cached_schema = None

def schema(self) -> Schema:
    if self._cached_schema is None:
        self._cached_schema = self._compute_schema()
    return self._cached_schema
```

**Expected Impact**: Minor reduction in object creation overhead

---

## 7. **Delimiter Detection: Multiple Calls** 🟢 LOW IMPACT

### Current Implementation
- **Location**: `csv.py:255-264`
- **Issue**: `_detectDelimiter()` may be called multiple times

### Optimization
**Cache Delimiter**:
```python
def __init__(self, ...):
    self._cached_delimiter = None

def _detectDelimiter(self) -> str:
    if self._cached_delimiter is None:
        # ... detection logic ...
        self._cached_delimiter = delimiter
    return self._cached_delimiter
```

**Expected Impact**: Minor improvement for CSV files

---

## 8. **Projection: Column Selection Overhead** 🟡 MEDIUM IMPACT

### Current Implementation
- **Location**: `csv.py:220-222`
- **Issue**: Calls `pyarrow_batch.select(projection)` for each batch

### Optimization
**Early Projection**:
- Apply projection at the PyArrow CSV reader level if possible
- Use `ReadOptions` to specify columns early
- Avoid reading unnecessary columns from disk

**Expected Impact**: Reduced I/O and memory for projected queries

---

## 9. **Type Conversions: String Operations** 🟡 MEDIUM IMPACT

### Current Implementation
- **Location**: `booleanexpr.py:67-70`, `hashaggexec.py:152-153`
- **Issue**: Converts bytes to strings for each comparison/key

### Optimization
**Use PyArrow String Operations**:
```python
# Use PyArrow's string functions instead of Python string operations
# pc.equal for string comparisons
# Avoid bytes.decode() in hot paths
```

**Expected Impact**: Faster string comparisons and key generation

---

## 10. **Parallel Processing** 🟡 MEDIUM IMPACT (Future)

### Opportunity
- Process multiple batches in parallel
- Use multiprocessing for independent operations
- Parallelize expression evaluation across batches

### Considerations
- GIL limitations in Python
- Memory overhead
- Complexity of implementation

---

## Priority Ranking

1. **🔴 HIGH PRIORITY**:
   - Expression evaluation vectorization (#1)
   - SelectionExec optimization (#2)
   - HashAggregateExec optimization (#4)

2. **🟡 MEDIUM PRIORITY**:
   - CSV batch accumulation (#3)
   - Projection optimization (#8)
   - Type conversion optimization (#9)

3. **🟢 LOW PRIORITY**:
   - Schema caching (#6)
   - Delimiter caching (#7)
   - Memory wrapper optimization (#5)

---

## Implementation Strategy

### Phase 1: Quick Wins (1-2 days)
- Cache schemas and delimiters
- Optimize SelectionExec with PyArrow filter

### Phase 2: Core Optimizations (1 week)
- Vectorize expression evaluation
- Optimize HashAggregateExec

### Phase 3: Advanced Optimizations (2 weeks)
- CSV batch processing improvements
- Projection pushdown at reader level
- Memory optimization

---

## Measurement

Before implementing optimizations:
1. Create benchmark suite with representative queries
2. Profile with `cProfile` or `py-spy`
3. Measure:
   - Expression evaluation time
   - Filter/selection time
   - Aggregate time
   - Memory usage
   - I/O throughput

After each optimization:
- Re-run benchmarks
- Compare performance metrics
- Ensure correctness (all tests pass)

---

## Notes

- PyArrow compute functions provide significant performance benefits
- Vectorization is key to performance in columnar systems
- Profile before optimizing to identify actual bottlenecks
- Maintain correctness - optimizations should not change behavior

