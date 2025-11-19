# Benchmark Comparison: Starlink vs Pandas vs DuckDB

This benchmark compares Starlink query engine with pandas and DuckDB on common query operations.

## Running the Benchmark

```bash
# Install dependencies
uv sync

# Run benchmark
PYTHONPATH=src python benchmark_comparison.py

# Run with custom CSV file
PYTHONPATH=src python benchmark_comparison.py --csv data/your_file.csv

# Run with more iterations for better accuracy
PYTHONPATH=src python benchmark_comparison.py --iterations 10
```

## Benchmark Queries

1. **Simple SELECT** - Project 2 columns from CSV
2. **SELECT with WHERE** - Filter rows based on condition
3. **GROUP BY with Aggregation** - Group by column and compute MAX/MIN/COUNT
4. **COUNT(*)** - Count total rows
5. **Complex Query** - Filter + Projection + Aggregation

## Results Format

The benchmark outputs:
- Mean, median, min, max execution times
- Standard deviation
- Summary table comparing all engines
- Speedup ratios relative to Starlink

## Notes

- CSV columns are read as strings, so type casting is required for numeric operations
- Results may vary based on system resources and data size
- Starlink is designed for educational purposes, not production performance
