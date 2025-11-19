#!/usr/bin/env python3
"""
Benchmark Comparison: Starlink vs Pandas vs DuckDB

This script compares the performance of Starlink query engine
against pandas and DuckDB on common query operations.
"""

import time
import statistics
from pathlib import Path
from typing import Dict, List, Tuple, Callable
from dataclasses import dataclass
import sys

# Starlink imports
sys.path.insert(0, str(Path(__file__).parent / "src"))
from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, Max, Min, Sum, Count, Gt, Eq, cast
import pyarrow as pa

# External libraries
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: pandas not available")

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    print("Warning: duckdb not available")


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    name: str
    engine: str
    mean_time_ms: float
    median_time_ms: float
    min_time_ms: float
    max_time_ms: float
    stddev_ms: float
    iterations: int


class BenchmarkSuite:
    """Benchmark suite for comparing query engines."""
    
    def __init__(self, csv_file: str, iterations: int = 5):
        self.csv_file = csv_file
        self.iterations = iterations
        self.results: List[BenchmarkResult] = []
        
    def run_benchmark(
        self, 
        name: str, 
        starlink_fn: Callable = None,
        pandas_fn: Callable = None,
        duckdb_fn: Callable = None
    ):
        """Run a benchmark across all available engines."""
        print(f"\n📊 Benchmarking: {name}")
        print("-" * 80)
        
        if starlink_fn:
            self._run_engine("Starlink", name, starlink_fn)
        
        if pandas_fn and PANDAS_AVAILABLE:
            self._run_engine("Pandas", name, pandas_fn)
        
        if duckdb_fn and DUCKDB_AVAILABLE:
            self._run_engine("DuckDB", name, duckdb_fn)
    
    def _run_engine(self, engine: str, benchmark_name: str, func: Callable):
        """Run a benchmark for a specific engine."""
        times = []
        
        for i in range(self.iterations):
            try:
                start = time.perf_counter()
                result = func()
                elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
                times.append(elapsed)
                
                # Verify result is not None
                if result is None:
                    print(f"  ⚠️  {engine}: Function returned None")
                    return
                    
            except Exception as e:
                print(f"  ❌ {engine}: Error - {e}")
                return
        
        if times:
            mean = statistics.mean(times)
            median = statistics.median(times)
            min_time = min(times)
            max_time = max(times)
            stddev = statistics.stdev(times) if len(times) > 1 else 0.0
            
            result = BenchmarkResult(
                name=benchmark_name,
                engine=engine,
                mean_time_ms=mean,
                median_time_ms=median,
                min_time_ms=min_time,
                max_time_ms=max_time,
                stddev_ms=stddev,
                iterations=self.iterations
            )
            self.results.append(result)
            
            print(f"  ✅ {engine:10s} | Mean: {mean:8.2f}ms | Median: {median:8.2f}ms | "
                  f"Min: {min_time:8.2f}ms | Max: {max_time:8.2f}ms | Stdev: {stddev:6.2f}ms")
    
    def print_summary_table(self):
        """Print a summary table comparing all engines."""
        print("\n" + "=" * 100)
        print("BENCHMARK SUMMARY TABLE")
        print("=" * 100)
        
        # Group results by benchmark name
        benchmarks = {}
        for result in self.results:
            if result.name not in benchmarks:
                benchmarks[result.name] = {}
            benchmarks[result.name][result.engine] = result
        
        # Print header
        print(f"\n{'Benchmark':<50} | {'Starlink (ms)':<15} | {'Pandas (ms)':<15} | {'DuckDB (ms)':<15} | {'Winner':<10}")
        print("-" * 100)
        
        # Print each benchmark
        for benchmark_name in sorted(benchmarks.keys()):
            engines = benchmarks[benchmark_name]
            
            starlink_time = engines.get("Starlink", None)
            pandas_time = engines.get("Pandas", None)
            duckdb_time = engines.get("DuckDB", None)
            
            # Find winner (lowest mean time)
            times = {}
            if starlink_time:
                times["Starlink"] = starlink_time.mean_time_ms
            if pandas_time:
                times["Pandas"] = pandas_time.mean_time_ms
            if duckdb_time:
                times["DuckDB"] = duckdb_time.mean_time_ms
            
            winner = min(times.items(), key=lambda x: x[1])[0] if times else "N/A"
            
            starlink_str = f"{starlink_time.mean_time_ms:.2f}" if starlink_time else "N/A"
            pandas_str = f"{pandas_time.mean_time_ms:.2f}" if pandas_time else "N/A"
            duckdb_str = f"{duckdb_time.mean_time_ms:.2f}" if duckdb_time else "N/A"
            
            print(f"{benchmark_name:<50} | {starlink_str:>15} | {pandas_str:>15} | {duckdb_str:>15} | {winner:<10}")
        
        print("=" * 100)
        
        # Calculate speedup ratios
        print("\n📈 SPEEDUP RATIOS (relative to Starlink)")
        print("-" * 100)
        print(f"{'Benchmark':<50} | {'Pandas/Starlink':<15} | {'DuckDB/Starlink':<15}")
        print("-" * 100)
        
        for benchmark_name in sorted(benchmarks.keys()):
            engines = benchmarks[benchmark_name]
            starlink_time = engines.get("Starlink", None)
            pandas_time = engines.get("Pandas", None)
            duckdb_time = engines.get("DuckDB", None)
            
            if starlink_time:
                pandas_ratio = f"{pandas_time.mean_time_ms / starlink_time.mean_time_ms:.2f}x" if pandas_time else "N/A"
                duckdb_ratio = f"{duckdb_time.mean_time_ms / starlink_time.mean_time_ms:.2f}x" if duckdb_time else "N/A"
                print(f"{benchmark_name:<50} | {pandas_ratio:>15} | {duckdb_ratio:>15}")
        
        print("=" * 100)


def setup_starlink(csv_file: str) -> ExecutionContext:
    """Setup Starlink execution context."""
    ctx = ExecutionContext({})
    ctx.register_csv("tripdata", csv_file)
    return ctx


def setup_pandas(csv_file: str):
    """Setup pandas - read CSV into memory."""
    if not PANDAS_AVAILABLE:
        return None
    return pd.read_csv(csv_file, low_memory=False)


def setup_duckdb(csv_file: str):
    """Setup DuckDB connection."""
    if not DUCKDB_AVAILABLE:
        return None
    conn = duckdb.connect()
    conn.execute(f"CREATE TABLE tripdata AS SELECT * FROM read_csv_auto('{csv_file}')")
    return conn


def benchmark_simple_select(bench: BenchmarkSuite, csv_file: str):
    """Benchmark: Simple SELECT with projection."""
    
    # Starlink
    def starlink_select():
        ctx = setup_starlink(csv_file)
        df = ctx.sql("SELECT passenger_count, fare_amount FROM tripdata")
        results = list(ctx.execute(df))
        return sum(batch.row_count() for batch in results)
    
    # Pandas
    def pandas_select():
        df = setup_pandas(csv_file)
        result = df[["passenger_count", "fare_amount"]]
        return len(result)
    
    # DuckDB
    def duckdb_select():
        conn = setup_duckdb(csv_file)
        result = conn.execute("SELECT passenger_count, fare_amount FROM tripdata").fetchall()
        conn.close()
        return len(result)
    
    bench.run_benchmark(
        "Simple SELECT (2 columns)",
        starlink_fn=starlink_select,
        pandas_fn=pandas_select,
        duckdb_fn=duckdb_select
    )


def benchmark_filter(bench: BenchmarkSuite, csv_file: str):
    """Benchmark: SELECT with WHERE clause."""
    
    # Starlink - CSV columns are strings, need to cast
    def starlink_filter():
        ctx = setup_starlink(csv_file)
        # Use CAST to convert string to int for comparison
        df = ctx.sql("""
            SELECT passenger_count, fare_amount 
            FROM tripdata 
            WHERE CAST(passenger_count AS INT64) > 3
        """)
        results = list(ctx.execute(df))
        return sum(batch.row_count() for batch in results)
    
    # Pandas
    def pandas_filter():
        df = setup_pandas(csv_file)
        # Convert to numeric for comparison
        df["passenger_count"] = pd.to_numeric(df["passenger_count"], errors="coerce")
        result = df[df["passenger_count"] > 3][["passenger_count", "fare_amount"]]
        return len(result)
    
    # DuckDB
    def duckdb_filter():
        conn = setup_duckdb(csv_file)
        result = conn.execute(
            "SELECT passenger_count, fare_amount FROM tripdata WHERE CAST(passenger_count AS INTEGER) > 3"
        ).fetchall()
        conn.close()
        return len(result)
    
    bench.run_benchmark(
        "SELECT with WHERE (passenger_count > 3)",
        starlink_fn=starlink_filter,
        pandas_fn=pandas_filter,
        duckdb_fn=duckdb_filter
    )


def benchmark_aggregation(bench: BenchmarkSuite, csv_file: str):
    """Benchmark: GROUP BY with aggregation."""
    
    # Starlink - CSV columns are strings, need to cast for aggregation
    def starlink_agg():
        ctx = setup_starlink(csv_file)
        df = ctx.sql("""
            SELECT passenger_count, 
                   MAX(CAST(fare_amount AS DOUBLE)) as max_fare,
                   MIN(CAST(fare_amount AS DOUBLE)) as min_fare,
                   COUNT(fare_amount) as count
            FROM tripdata 
            GROUP BY passenger_count
        """)
        results = list(ctx.execute(df))
        return sum(batch.row_count() for batch in results)
    
    # Pandas - Convert to numeric
    def pandas_agg():
        df = setup_pandas(csv_file)
        df["passenger_count"] = pd.to_numeric(df["passenger_count"], errors="coerce")
        df["fare_amount"] = pd.to_numeric(df["fare_amount"], errors="coerce")
        result = df.groupby("passenger_count").agg({
            "fare_amount": ["max", "min", "count"]
        })
        return len(result)
    
    # DuckDB
    def duckdb_agg():
        conn = setup_duckdb(csv_file)
        result = conn.execute("""
            SELECT passenger_count, 
                   MAX(fare_amount) as max_fare,
                   MIN(fare_amount) as min_fare,
                   COUNT(*) as count
            FROM tripdata 
            GROUP BY passenger_count
        """).fetchall()
        conn.close()
        return len(result)
    
    bench.run_benchmark(
        "GROUP BY with MAX/MIN/COUNT",
        starlink_fn=starlink_agg,
        pandas_fn=pandas_agg,
        duckdb_fn=duckdb_agg
    )


def benchmark_count(bench: BenchmarkSuite, csv_file: str):
    """Benchmark: COUNT(*) query."""
    
    # Starlink
    def starlink_count():
        ctx = setup_starlink(csv_file)
        df = ctx.sql("SELECT COUNT(*) FROM tripdata")
        results = list(ctx.execute(df))
        return sum(batch.row_count() for batch in results)
    
    # Pandas
    def pandas_count():
        df = setup_pandas(csv_file)
        return len(df)
    
    # DuckDB
    def duckdb_count():
        conn = setup_duckdb(csv_file)
        result = conn.execute("SELECT COUNT(*) FROM tripdata").fetchone()[0]
        conn.close()
        return result
    
    bench.run_benchmark(
        "COUNT(*) - Total rows",
        starlink_fn=starlink_count,
        pandas_fn=pandas_count,
        duckdb_fn=duckdb_count
    )


def benchmark_complex_query(bench: BenchmarkSuite, csv_file: str):
    """Benchmark: Complex query with filter, projection, and aggregation."""
    
    # Starlink - CSV columns are strings, need to cast
    def starlink_complex():
        ctx = setup_starlink(csv_file)
        df = ctx.sql("""
            SELECT passenger_count, 
                   MAX(CAST(fare_amount AS DOUBLE)) as max_fare
            FROM tripdata 
            WHERE CAST(passenger_count AS INT64) > 2 AND CAST(fare_amount AS DOUBLE) > 10
            GROUP BY passenger_count
        """)
        results = list(ctx.execute(df))
        return sum(batch.row_count() for batch in results)
    
    # Pandas - Convert to numeric
    def pandas_complex():
        df = setup_pandas(csv_file)
        df["passenger_count"] = pd.to_numeric(df["passenger_count"], errors="coerce")
        df["fare_amount"] = pd.to_numeric(df["fare_amount"], errors="coerce")
        filtered = df[(df["passenger_count"] > 2) & (df["fare_amount"] > 10)]
        result = filtered.groupby("passenger_count")["fare_amount"].max().reset_index()
        return len(result)
    
    # DuckDB
    def duckdb_complex():
        conn = setup_duckdb(csv_file)
        result = conn.execute("""
            SELECT passenger_count, 
                   MAX(fare_amount) as max_fare
            FROM tripdata 
            WHERE passenger_count > 2 AND fare_amount > 10
            GROUP BY passenger_count
        """).fetchall()
        conn.close()
        return len(result)
    
    bench.run_benchmark(
        "Complex: Filter + GROUP BY + MAX",
        starlink_fn=starlink_complex,
        pandas_fn=pandas_complex,
        duckdb_fn=duckdb_complex
    )


def main():
    """Run all benchmarks."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark Starlink vs Pandas vs DuckDB")
    parser.add_argument(
        "--csv",
        type=str,
        default="data/yellow_tripdata_2019-01.csv",
        help="Path to CSV file"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of iterations per benchmark"
    )
    
    args = parser.parse_args()
    
    csv_file = Path(__file__).parent / args.csv
    if not csv_file.exists():
        print(f"Error: CSV file not found: {csv_file}")
        return
    
    print("=" * 100)
    print("STARLINK vs PANDAS vs DUCKDB BENCHMARK")
    print("=" * 100)
    print(f"CSV File: {csv_file}")
    print(f"Iterations: {args.iterations}")
    print(f"Pandas Available: {PANDAS_AVAILABLE}")
    print(f"DuckDB Available: {DUCKDB_AVAILABLE}")
    
    bench = BenchmarkSuite(str(csv_file), iterations=args.iterations)
    
    # Run benchmarks
    benchmark_simple_select(bench, str(csv_file))
    benchmark_filter(bench, str(csv_file))
    benchmark_aggregation(bench, str(csv_file))
    benchmark_count(bench, str(csv_file))
    benchmark_complex_query(bench, str(csv_file))
    
    # Print summary
    bench.print_summary_table()
    
    print("\n✅ Benchmark complete!")


if __name__ == "__main__":
    main()

