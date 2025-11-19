# Filter Pushdown Analysis: Starlink vs Spark

## Current State

**Starlink does NOT currently support filter pushdown** (also called predicate pushdown), unlike Spark.

### What Starlink Has

✅ **Projection Pushdown**: Columns are pushed down to the scan level
- Example: `Scan: ...; projection=[passenger_count, fare_amount]`
- Reduces I/O by only reading needed columns

❌ **Filter Pushdown**: Filters are applied AFTER reading all data
- Example: `Selection: #passenger_count > 3` is above the `Scan`
- All rows are read from disk, then filtered in memory

### Current Query Execution Flow

```
SQL: SELECT passenger_count, fare_amount FROM tripdata WHERE passenger_count > 3

Logical Plan:
  Selection: #passenger_count > 3          ← Filter applied AFTER reading
    Projection: #passenger_count, #fare_amount
      Scan: tripdata; projection=None

Optimized Plan:
  Selection: #passenger_count > 3          ← Still above Scan!
    Projection: #passenger_count, #fare_amount
      Scan: tripdata; projection=[passenger_count, fare_amount]  ← Only columns pushed
```

## What Filter Pushdown Would Do

### In Spark

Spark pushes filters down to data sources:

```python
# Spark automatically pushes filters
df.filter(col("passenger_count") > 3).select("passenger_count", "fare_amount")

# For Parquet:
# - Uses row group statistics to skip entire row groups
# - Only reads row groups that might contain matching rows
# - Dramatically reduces I/O for selective filters

# For CSV:
# - Filters during reading (less effective, but still helps)
# - Can skip entire files in partitioned datasets
```

### What Starlink Would Need

1. **Extend DataSource Interface**:
   ```python
   class DataSource:
       def scan(self, projection: List[str], filter: Optional[LogicalExpr] = None) -> Sequence[RecordBatch]:
           # Apply filter during reading
   ```

2. **Extend Scan Logical Plan**:
   ```python
   class Scan(LogicalPlan):
       def __init__(self, path: str, data_source: DataSource, 
                    projection: List[str], filter: Optional[LogicalExpr] = None):
           self.filter = filter  # Add filter support
   ```

3. **Create FilterPushDownRule Optimizer**:
   ```python
   class FilterPushDownRule(OptimizerRule):
       def optimize(self, plan: LogicalPlan) -> LogicalPlan:
           # Push Selection filters down to Scan
   ```

4. **Implement Filter Evaluation in Data Sources**:
   - **Parquet**: Use row group statistics to skip row groups
   - **CSV**: Filter rows during reading (less effective)

## Benefits of Filter Pushdown

### For Parquet Files

**Massive I/O Reduction**:
- Parquet files have row group statistics (min/max values per column)
- Can skip entire row groups that don't match the filter
- Example: If `passenger_count > 3` and a row group has `max(passenger_count) = 2`, skip it entirely
- **Potential speedup**: 10-100x for selective filters on large files

### For CSV Files

**Moderate Benefit**:
- Can filter rows during reading instead of after
- Reduces memory usage
- **Potential speedup**: 2-5x depending on selectivity

## Implementation Complexity

### Easy Parts
- Extending interfaces (DataSource, Scan)
- Creating FilterPushDownRule optimizer
- CSV filter implementation (filter during reading)

### Hard Parts
- **Parquet row group statistics**: Need to read metadata and evaluate filters
- **Filter expression evaluation at scan level**: Need to evaluate logical expressions on statistics
- **Type handling**: Ensure filter expressions work with data source types

## Comparison with Spark

| Feature | Spark | Starlink (Current) | Starlink (With Filter Pushdown) |
|--------|-------|-------------------|--------------------------------|
| Projection Pushdown | ✅ | ✅ | ✅ |
| Filter Pushdown | ✅ | ❌ | ✅ (if implemented) |
| Parquet Row Group Skipping | ✅ | ❌ | ✅ (if implemented) |
| CSV Filter During Read | ✅ | ❌ | ✅ (if implemented) |

## Recommendation

Filter pushdown is a **high-value optimization**, especially for:
- Large Parquet files with selective filters
- Partitioned datasets
- Queries with high selectivity (few rows match)

**Priority**: Medium-High
- High impact for Parquet files
- Moderate complexity
- Significant performance gains for selective queries

## Next Steps (If Implementing)

1. Extend `DataSource` interface to accept optional filter
2. Extend `Scan` logical plan to include filter
3. Create `FilterPushDownRule` optimizer
4. Implement filter evaluation in `CsvDataSource`
5. Implement row group statistics evaluation in `ParquetDataSource`
6. Update `QueryPlanner` to handle filters in Scan
7. Add tests for filter pushdown

