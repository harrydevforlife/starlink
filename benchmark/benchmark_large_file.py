#!/usr/bin/env python3
"""
Performance Benchmark với file lớn: yellow_tripdata_2019-01.csv (~7.6M rows)

This script benchmarks Starlink operations với file CSV thực tế lớn.

Usage:
    python benchmark_large_file.py [--iterations N] [--warmup N]
"""

import argparse
import time
import statistics
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pyarrow as pa

from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, lit, Sum, Max, Min, cast, Eq, Gt, And, Lt


class BenchmarkResult:
    """Store benchmark results for large file."""
    
    def __init__(self, name: str):
        self.name = name
        self.times: list[float] = []
        self.mean: float = 0.0
        self.median: float = 0.0
        self.stdev: float = 0.0
        self.min: float = 0.0
        self.max: float = 0.0
    
    def add_time(self, elapsed: float):
        """Add a timing measurement."""
        self.times.append(elapsed)
    
    def compute_stats(self):
        """Compute statistics from collected times."""
        if not self.times:
            return
        
        self.mean = statistics.mean(self.times)
        self.median = statistics.median(self.times)
        if len(self.times) > 1:
            self.stdev = statistics.stdev(self.times)
        self.min = min(self.times)
        self.max = max(self.times)
    
    def __str__(self) -> str:
        return (
            f"{self.name:60s} | "
            f"Mean: {self.mean:8.2f}s | "
            f"Median: {self.median:8.2f}s | "
            f"Min: {self.min:8.2f}s | "
            f"Max: {self.max:8.2f}s"
        )


class LargeFileBenchmark:
    """Benchmark suite for large CSV file."""
    
    def __init__(self, iterations: int = 3, warmup: int = 1):
        self.iterations = iterations
        self.warmup = warmup
        self.results: dict[str, BenchmarkResult] = {}
        self.csv_file = Path(__file__).parent / "data" / "yellow_tripdata_2019-01.csv"
    
    def run(self, name: str, func, *args, **kwargs):
        """Run a benchmark function multiple times."""
        # Warmup
        print(f"  Warming up: {name}...")
        for _ in range(self.warmup):
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"    Warning: {e}")
        
        # Actual benchmark
        print(f"  Benchmarking: {name}...")
        result = BenchmarkResult(name)
        for i in range(self.iterations):
            print(f"    Iteration {i+1}/{self.iterations}...")
            start = time.perf_counter()
            try:
                func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                result.add_time(elapsed)
                print(f"      Completed in {elapsed:.2f}s")
            except Exception as e:
                print(f"      Error: {e}")
                import traceback
                traceback.print_exc()
        
        result.compute_stats()
        self.results[name] = result
        return result
    
    def print_results(self):
        """Print all benchmark results."""
        print("\n" + "="*140)
        print("LARGE FILE BENCHMARK RESULTS (~7.6M rows)")
        print("="*140)
        print(f"{'Operation':60s} | {'Mean (s)':>12s} | {'Median (s)':>12s} | {'Min (s)':>12s} | {'Max (s)':>12s}")
        print("-"*140)
        
        for result in sorted(self.results.values(), key=lambda x: x.name):
            print(result)
        
        print("="*140)
    
    def save_results(self, filename: str):
        """Save results to a file."""
        with open(filename, 'w') as f:
            f.write("Large File Benchmark Results (~7.6M rows)\n")
            f.write("="*140 + "\n")
            for result in sorted(self.results.values(), key=lambda x: x.name):
                f.write(str(result) + "\n")


def benchmark_csv_reading(bench: LargeFileBenchmark):
    """Benchmark CSV reading operations."""
    print("\n📊 Benchmarking CSV Reading Operations...")
    
    ctx = ExecutionContext({})
    
    # Test 1: Read all columns
    def read_all():
        df = ctx.csv(str(bench.csv_file))
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("CSV: Read all columns (no projection)", read_all)
    
    # Test 2: Read with projection (few columns)
    def read_projection():
        df = ctx.csv(str(bench.csv_file))
        df = df.project([col("VendorID"), col("passenger_count"), col("fare_amount")])
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("CSV: Read with projection (3 cols)", read_projection)
    
    # Test 3: Read with projection (more columns)
    def read_projection_more():
        df = ctx.csv(str(bench.csv_file))
        df = df.project([
            col("VendorID"), 
            col("passenger_count"), 
            col("fare_amount"),
            col("trip_distance"),
            col("total_amount")
        ])
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("CSV: Read with projection (5 cols)", read_projection_more)


def benchmark_filtering(bench: LargeFileBenchmark):
    """Benchmark filtering operations."""
    print("\n📊 Benchmarking Filtering Operations...")
    
    ctx = ExecutionContext({})
    
    # Test 1: Simple filter on numeric column
    def filter_numeric():
        df = ctx.csv(str(bench.csv_file))
        # Filter passenger_count > 0 (most rows should pass)
        df = df.filter(Gt(cast(col("passenger_count"), pa.int64()), lit(0)))
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("Filter: passenger_count > 0", filter_numeric)
    
    # Test 2: Tight filter
    def filter_tight():
        df = ctx.csv(str(bench.csv_file))
        # Filter passenger_count == 5 (fewer rows)
        df = df.filter(Eq(cast(col("passenger_count"), pa.int64()), lit(5)))
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("Filter: passenger_count == 5", filter_tight)
    
    # Test 3: Filter on fare_amount
    def filter_fare():
        df = ctx.csv(str(bench.csv_file))
        # Filter fare_amount > 50
        df = df.filter(Gt(cast(col("fare_amount"), pa.float64()), lit(50.0)))
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("Filter: fare_amount > 50", filter_fare)


def benchmark_aggregation(bench: LargeFileBenchmark):
    """Benchmark aggregation operations."""
    print("\n📊 Benchmarking Aggregation Operations...")
    
    ctx = ExecutionContext({})
    
    # Test 1: Group by passenger_count, aggregate fare_amount
    def agg_passenger_count():
        df = ctx.csv(str(bench.csv_file))
        fare_col = cast(col("fare_amount"), pa.float64())
        df = df.aggregate(
            [cast(col("passenger_count"), pa.int64())],
            [Sum(fare_col), Max(fare_col), Min(fare_col)]
        )
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("Aggregate: GROUP BY passenger_count (SUM, MAX, MIN fare_amount)", agg_passenger_count)
    
    # Test 2: Group by VendorID
    def agg_vendor():
        df = ctx.csv(str(bench.csv_file))
        fare_col = cast(col("fare_amount"), pa.float64())
        df = df.aggregate(
            [col("VendorID")],
            [Sum(fare_col), Max(fare_col)]
        )
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("Aggregate: GROUP BY VendorID (SUM, MAX fare_amount)", agg_vendor)
    
    # Test 3: Single group aggregation
    def agg_single():
        df = ctx.csv(str(bench.csv_file))
        fare_col = cast(col("fare_amount"), pa.float64())
        df = df.aggregate(
            [],
            [Sum(fare_col), Max(fare_col), Min(fare_col)]
        )
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("Aggregate: Single group (SUM, MAX, MIN fare_amount)", agg_single)


def benchmark_end_to_end(bench: LargeFileBenchmark):
    """Benchmark end-to-end queries."""
    print("\n📊 Benchmarking End-to-End Queries...")
    
    ctx = ExecutionContext({})
    
    # Test 1: Filter + Project
    def filter_project():
        df = ctx.csv(str(bench.csv_file))
        df = df.filter(Gt(cast(col("passenger_count"), pa.int64()), lit(2)))
        df = df.project([
            col("VendorID"),
            col("passenger_count"),
            col("fare_amount"),
            col("trip_distance")
        ])
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("E2E: Filter (passenger_count > 2) + Project", filter_project)
    
    # Test 2: Filter + Aggregate
    def filter_aggregate():
        df = ctx.csv(str(bench.csv_file))
        df = df.filter(Gt(cast(col("fare_amount"), pa.float64()), lit(20.0)))
        fare_col = cast(col("fare_amount"), pa.float64())
        df = df.aggregate(
            [cast(col("passenger_count"), pa.int64())],
            [Sum(fare_col), Max(fare_col)]
        )
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("E2E: Filter (fare_amount > 20) + Aggregate", filter_aggregate)
    
    # Test 3: Complex query
    def complex_query():
        df = ctx.csv(str(bench.csv_file))
        # Filter
        df = df.filter(
            And(
                Gt(cast(col("passenger_count"), pa.int64()), lit(1)),
                Gt(cast(col("fare_amount"), pa.float64()), lit(10.0))
            )
        )
        # Project
        df = df.project([
            col("VendorID"),
            col("passenger_count"),
            col("fare_amount")
        ])
        # Aggregate
        fare_col = cast(col("fare_amount"), pa.float64())
        df = df.aggregate(
            [cast(col("passenger_count"), pa.int64())],
            [Sum(fare_col), Max(fare_col)]
        )
        result = list(ctx.execute(df))
        total_rows = sum(batch.rowCount() for batch in result)
        return total_rows
    
    bench.run("E2E: Complex (Filter + Project + Aggregate)", complex_query)


def main():
    parser = argparse.ArgumentParser(description="Benchmark Starlink with large CSV file")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations per benchmark")
    parser.add_argument("--warmup", type=int, default=1, help="Number of warmup iterations")
    parser.add_argument("--output", type=str, help="Output file for results")
    args = parser.parse_args()
    
    csv_file = Path(__file__).parent / "data" / "yellow_tripdata_2019-01.csv"
    
    if not csv_file.exists():
        print(f"❌ Error: CSV file not found: {csv_file}")
        return 1
    
    # Count rows
    try:
        import subprocess
        result = subprocess.run(['wc', '-l', str(csv_file)], capture_output=True, text=True)
        num_rows = int(result.stdout.split()[0]) - 1  # Subtract header
        print(f"📁 File: {csv_file}")
        print(f"📊 Rows: ~{num_rows:,} (excluding header)")
    except Exception:
        num_rows = 0
    
    print("\n🚀 Starlink Large File Benchmark Suite")
    print("="*140)
    print(f"File: {csv_file}")
    print(f"Estimated rows: ~{num_rows:,}")
    print(f"Iterations: {args.iterations}")
    print(f"Warmup: {args.warmup}")
    print("="*140)
    
    bench = LargeFileBenchmark(iterations=args.iterations, warmup=args.warmup)
    
    # Run benchmarks
    try:
        benchmark_csv_reading(bench)
        benchmark_filtering(bench)
        benchmark_aggregation(bench)
        benchmark_end_to_end(bench)
    except Exception as e:
        print(f"\n❌ Error during benchmarking: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Print results
    bench.print_results()
    
    # Save results if requested
    if args.output:
        bench.save_results(args.output)
        print(f"\n💾 Results saved to {args.output}")
    
    print("\n✅ Benchmark completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

