# Benchmark Results: Starlink vs Pandas vs DuckDB

## Overview

This document shows benchmark results comparing Starlink query engine with pandas and DuckDB on common query operations using the NYC Taxi Trip Data (yellow_tripdata_2019-01.csv).

## Test Environment

- **Dataset**: NYC Taxi Trip Data (January 2019)
- **File Format**: CSV
- **Iterations**: 5 runs per benchmark
- **System**: [Your system specs]

## Benchmark Results Summary

uv run python benchmark_comparison_parquet.py --parquet data/tripdata/parquet --iterations 5
====================================================================================================
STARLINK vs PANDAS vs DUCKDB BENCHMARK
====================================================================================================
Parquet File: .../data/tripdata/parquet
Iterations: 5

### Simple SELECT (2 columns)

| Engine    | Mean (ms) | Median (ms) | Min (ms) | Max (ms) | Stdev (ms) |
|-----------|-----------|-------------|----------|----------|------------|
| Starlink  | 254.85    | 219.27      | 214.74   | 395.66   | 78.88      |
| Pandas    | 449.21    | 413.31      | 383.54   | 614.46   | 95.75      |
| DuckDB    | 4056.91   | 4055.55     | 3671.07  | 4443.26  | 274.23     |

---

### SELECT with WHERE (passenger_count > 3)

| Engine    | Mean (ms) | Median (ms) | Min (ms) | Max (ms) | Stdev (ms) |
|-----------|-----------|-------------|----------|----------|------------|
| Starlink  | 331.83    | 316.07      | 228.29   | 522.36   | 114.31     |
| Pandas    | 584.25    | 508.52      | 477.47   | 799.10   | 136.53     |
| DuckDB    | 2520.74   | 2423.81     | 2408.67  | 2739.87  | 149.42     |

---

### GROUP BY with MAX/MIN/COUNT

| Engine    | Mean (ms) | Median (ms) | Min (ms) | Max (ms)   | Stdev (ms) |
|-----------|-----------|-------------|----------|------------|------------|
| Starlink  | 8693.61   | 8353.93     | 8117.14  | 10078.81   | 797.65     |
| Pandas    | 662.48    | 534.05      | 525.59   | 919.62     | 186.65     |
| DuckDB    | 2393.25   | 2347.26     | 2318.65  | 2495.48    | 82.09      |

---

### COUNT(*) - Total rows

| Engine    | Mean (ms) | Median (ms) | Min (ms) | Max (ms) | Stdev (ms) |
|-----------|-----------|-------------|----------|----------|------------|
| Starlink  | 2086.74   | 2050.94     | 1984.98  | 2241.24  | 101.46     |
| Pandas    | 379.20    | 370.83      | 360.85   | 421.91   | 24.35      |
| DuckDB    | 2360.32   | 2429.75     | 2229.64  | 2470.45  | 115.23     |

---

### Complex: Filter + GROUP BY + MAX

| Engine    | Mean (ms) | Median (ms) | Min (ms) | Max (ms) | Stdev (ms) |
|-----------|-----------|-------------|----------|----------|------------|
| Starlink  | 400.22    | 399.47      | 395.67   | 404.75   | 3.76       |
| Pandas    | 512.83    | 465.54      | 463.90   | 649.48   | 80.20      |
| DuckDB    | 2298.54   | 2246.94     | 2227.46  | 2534.73  | 132.29     |

---

### Benchmark Summary Table

| Benchmark                                 | Starlink (ms) | Pandas (ms) | DuckDB (ms) | Winner   |
|--------------------------------------------|---------------|-------------|-------------|----------|
| COUNT(*) - Total rows                      | 2086.74       | 379.20      | 2360.32     | Pandas   |
| Complex: Filter + GROUP BY + MAX           | 400.22        | 512.83      | 2298.54     | Starlink |
| GROUP BY with MAX/MIN/COUNT                | 8693.61       | 662.48      | 2393.25     | Pandas   |
| SELECT with WHERE (passenger_count > 3)    | 331.83        | 584.25      | 2520.74     | Starlink |
| Simple SELECT (2 columns)                  | 254.85        | 449.21      | 4056.91     | Starlink |

---

### Speedup Ratios (relative to Starlink)

| Benchmark                                 | Pandas/Starlink | DuckDB/Starlink |
|--------------------------------------------|-----------------|-----------------|
| COUNT(*) - Total rows                      | 0.18x           | 1.13x           |
| Complex: Filter + GROUP BY + MAX           | 1.28x           | 5.74x           |
| GROUP BY with MAX/MIN/COUNT                | 0.08x           | 0.28x           |
| SELECT with WHERE (passenger_count > 3)    | 1.76x           | 7.60x           |
| Simple SELECT (2 columns)                  | 1.76x           | 15.92x          |


## Observations

1. **Starlink Performance**: 
   - Starlink is designed for educational purposes and focuses on clarity over performance
   - Performance is expected to be slower than production-grade engines like DuckDB
   - The columnar format and projection pushdown optimization help, but there's room for improvement

2. **Expected Results**:
   - **DuckDB** is expected to be fastest for most queries (optimized C++ engine)
   - **Pandas** is expected to be faster than Starlink for simple operations (mature, optimized)
   - **Starlink** demonstrates the query engine concepts but prioritizes educational value

3. **Performance Characteristics**:
   - Simple SELECT operations are relatively fast
   - Aggregations are slower due to hash aggregation implementation
   - COUNT(*) is efficient as it only needs to count rows

## Running Your Own Benchmarks

To run benchmarks and generate results:

```bash
# Install dependencies
uv sync

# Run benchmark
PYTHONPATH=src python benchmark_comparison.py --iterations 5

# The script will output a summary table automatically
```

## Notes

- Results are highly dependent on system resources, data size, and Python version
- Starlink is not optimized for production use - it's an educational implementation
- For production workloads, consider DuckDB, Polars, or Apache Arrow DataFusion
- The benchmark helps understand the performance characteristics of different query execution strategies

## Future Improvements

Potential optimizations for Starlink:
- Vectorized operations
- Better memory management
- Parallel processing
- Query result caching
- More efficient hash aggregation
- Predicate pushdown optimization

