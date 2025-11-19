#!/usr/bin/env python3
"""
Performance Benchmark: Starlink vs PyArrow Native Operations

This script benchmarks Starlink operations against native PyArrow operations
to measure the overhead and performance characteristics.

Usage:
    python benchmark_arrow.py [--iterations N] [--warmup N] [--rows N]
"""

import argparse
import time
import statistics
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv

from starlink.datasources.csv import CsvDataSource
from starlink.datasources.memory import InMemoryDataSource
from starlink.datatypes.schema import Schema, Field
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, lit, Sum, Max, Min, Eq, Gt, Add, Multiply, And, Lt, cast
from starlink.logicalplan.dataframe import DataFrameImpl
from starlink.logicalplan.scan import Scan


class ComparisonResult:
    """Store comparison results between Starlink and PyArrow."""
    
    def __init__(self, name: str):
        self.name = name
        self.starlink_times: List[float] = []
        self.arrow_times: List[float] = []
        self.starlink_mean: float = 0.0
        self.arrow_mean: float = 0.0
        self.speedup: float = 0.0
        self.overhead: float = 0.0
    
    def add_starlink_time(self, elapsed: float):
        """Add a Starlink timing measurement."""
        self.starlink_times.append(elapsed)
    
    def add_arrow_time(self, elapsed: float):
        """Add a PyArrow timing measurement."""
        self.arrow_times.append(elapsed)
    
    def compute_stats(self):
        """Compute statistics from collected times."""
        if self.starlink_times:
            self.starlink_mean = statistics.mean(self.starlink_times)
        if self.arrow_times:
            self.arrow_mean = statistics.mean(self.arrow_times)
        
        if self.arrow_mean > 0:
            self.speedup = self.arrow_mean / self.starlink_mean if self.starlink_mean > 0 else 0
            self.overhead = ((self.starlink_mean - self.arrow_mean) / self.arrow_mean * 100) if self.arrow_mean > 0 else 0
    
    def __str__(self) -> str:
        starlink_str = f"{self.starlink_mean*1000:8.2f}ms" if self.starlink_mean > 0 else "N/A"
        arrow_str = f"{self.arrow_mean*1000:8.2f}ms" if self.arrow_mean > 0 else "N/A"
        speedup_str = f"{self.speedup:.2f}x" if self.speedup > 0 else "N/A"
        overhead_str = f"{self.overhead:+.1f}%" if self.overhead != 0 else "N/A"
        
        return (
            f"{self.name:50s} | "
            f"Starlink: {starlink_str:>12s} | "
            f"PyArrow: {arrow_str:>12s} | "
            f"Speedup: {speedup_str:>8s} | "
            f"Overhead: {overhead_str:>10s}"
        )


class ArrowBenchmarkSuite:
    """Benchmark suite comparing Starlink vs PyArrow."""
    
    def __init__(self, iterations: int = 5, warmup: int = 2):
        self.iterations = iterations
        self.warmup = warmup
        self.results: Dict[str, ComparisonResult] = {}
    
    def run_comparison(self, name: str, starlink_func, arrow_func, *args, **kwargs):
        """Run a comparison between Starlink and PyArrow functions."""
        result = ComparisonResult(name)
        
        # Warmup
        for _ in range(self.warmup):
            if starlink_func:
                starlink_func(*args, **kwargs)
            if arrow_func:
                arrow_func(*args, **kwargs)
        
        # Benchmark Starlink
        if starlink_func:
            for _ in range(self.iterations):
                start = time.perf_counter()
                starlink_func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                result.add_starlink_time(elapsed)
        
        # Benchmark PyArrow
        if arrow_func:
            for _ in range(self.iterations):
                start = time.perf_counter()
                arrow_func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                result.add_arrow_time(elapsed)
        
        result.compute_stats()
        self.results[name] = result
        return result
    
    def print_results(self):
        """Print all comparison results."""
        print("\n" + "="*140)
        print("STARLINK vs PYARROW BENCHMARK RESULTS")
        print("="*140)
        print(f"{'Operation':50s} | {'Starlink':>12s} | {'PyArrow':>12s} | {'Speedup':>8s} | {'Overhead':>10s}")
        print("-"*140)
        
        for result in sorted(self.results.values(), key=lambda x: x.name):
            print(result)
        
        print("="*140)
    
    def save_results(self, filename: str):
        """Save results to a file."""
        with open(filename, 'w') as f:
            f.write("Starlink vs PyArrow Benchmark Results\n")
            f.write("="*140 + "\n")
            for result in sorted(self.results.values(), key=lambda x: x.name):
                f.write(str(result) + "\n")


def create_test_csv(tmp_path: Path, num_rows: int = 10000) -> str:
    """Create a test CSV file with sample data."""
    csv_file = tmp_path / "test_data.csv"
    
    with open(csv_file, 'w') as f:
        # Write header
        f.write("id,value1,value2,value3,group\n")
        
        # Write data
        groups = ["A", "B", "C", "D", "E"]
        for i in range(num_rows):
            group = groups[i % len(groups)]
            f.write(f"{i},{i*2},{i*3},{i*1.5},{group}\n")
    
    return str(csv_file)


def benchmark_csv_reading(bench: ArrowBenchmarkSuite, csv_file: str):
    """Benchmark CSV reading: Starlink vs PyArrow."""
    print("\n📊 Benchmarking CSV Reading Operations...")
    
    # Test 1: Read all columns
    def starlink_read_all():
        csv_ds = CsvDataSource(csv_file, None, True, 1024)
        batches = list(csv_ds.scan([]))
        total_rows = sum(batch.rowCount() for batch in batches)
        return total_rows
    
    def arrow_read_all():
        table = pacsv.read_csv(csv_file)
        return len(table)
    
    bench.run_comparison("CSV: Read all columns", starlink_read_all, arrow_read_all)
    
    # Test 2: Read with projection
    def starlink_read_projection():
        csv_ds = CsvDataSource(csv_file, None, True, 1024)
        batches = list(csv_ds.scan(["id", "value1"]))
        total_rows = sum(batch.rowCount() for batch in batches)
        return total_rows
    
    def arrow_read_projection():
        convert_opts = pacsv.ConvertOptions(include_columns=["id", "value1"])
        table = pacsv.read_csv(csv_file, convert_options=convert_opts)
        return len(table)
    
    bench.run_comparison("CSV: Read with projection (2 cols)", starlink_read_projection, arrow_read_projection)


def benchmark_filtering(bench: ArrowBenchmarkSuite):
    """Benchmark filtering: Starlink vs PyArrow."""
    print("\n📊 Benchmarking Filtering Operations...")
    
    # Create test data
    num_rows = 10000
    arr1 = pa.array([i for i in range(num_rows)])
    arr2 = pa.array([i % 100 for i in range(num_rows)])
    table = pa.table({"id": arr1, "value": arr2})
    
    # Starlink setup
    schema = Schema([
        Field("id", pa.int64()),
        Field("value", pa.int64()),
    ])
    batch = RecordBatch(schema, [
        ArrowFieldVector(arr1),
        ArrowFieldVector(arr2),
    ])
    data_source = InMemoryDataSource(schema, [batch])
    ctx = ExecutionContext({})
    
    # Test 1: Simple filter (50% selectivity)
    def starlink_filter():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.filter(Lt(col("value"), lit(50)))
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    def arrow_filter():
        mask = pc.less(table["value"], pa.scalar(50))
        filtered = table.filter(mask)
        return len(filtered)
    
    bench.run_comparison("Filter: Simple filter (50% selectivity)", starlink_filter, arrow_filter)
    
    # Test 2: Tight filter (10% selectivity)
    def starlink_tight():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.filter(Lt(col("value"), lit(10)))
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    def arrow_tight():
        mask = pc.less(table["value"], pa.scalar(10))
        filtered = table.filter(mask)
        return len(filtered)
    
    bench.run_comparison("Filter: Tight filter (10% selectivity)", starlink_tight, arrow_tight)


def benchmark_expressions(bench: ArrowBenchmarkSuite):
    """Benchmark expression evaluation: Starlink vs PyArrow."""
    print("\n📊 Benchmarking Expression Evaluation...")
    
    # Create test data
    num_rows = 10000
    arr1 = pa.array([i for i in range(num_rows)])
    arr2 = pa.array([i * 2 for i in range(num_rows)])
    table = pa.table({"a": arr1, "b": arr2})
    
    # Starlink setup
    schema = Schema([
        Field("a", pa.int64()),
        Field("b", pa.int64()),
    ])
    batch = RecordBatch(schema, [
        ArrowFieldVector(arr1),
        ArrowFieldVector(arr2),
    ])
    data_source = InMemoryDataSource(schema, [batch])
    ctx = ExecutionContext({})
    
    # Test 1: Comparison
    def starlink_comparison():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.filter(Gt(col("a"), lit(5000)))
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    def arrow_comparison():
        mask = pc.greater(table["a"], pa.scalar(5000))
        filtered = table.filter(mask)
        return len(filtered)
    
    bench.run_comparison("Expression: Comparison (a > 5000)", starlink_comparison, arrow_comparison)
    
    # Test 2: Math expression
    def starlink_math():
        df = DataFrameImpl(Scan('', data_source, []))
        from starlink.logicalplan.expressions import Alias
        df = df.project([Alias(Add(col("a"), col("b")), "sum")])
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    def arrow_math():
        result = pc.add(table["a"], table["b"])
        return len(result)
    
    bench.run_comparison("Expression: Math (a + b)", starlink_math, arrow_math)
    
    # Test 3: Complex boolean
    def starlink_boolean():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.filter(And(Gt(col("a"), lit(1000)), Lt(col("b"), lit(15000))))
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    def arrow_boolean():
        mask1 = pc.greater(table["a"], pa.scalar(1000))
        mask2 = pc.less(table["b"], pa.scalar(15000))
        mask = pc.and_kleene(mask1, mask2)
        filtered = table.filter(mask)
        return len(filtered)
    
    bench.run_comparison("Expression: Complex boolean (a>1000 AND b<15000)", starlink_boolean, arrow_boolean)


def benchmark_aggregation(bench: ArrowBenchmarkSuite):
    """Benchmark aggregation: Starlink vs PyArrow (using pandas groupby)."""
    print("\n📊 Benchmarking Aggregation Operations...")
    
    # Create test data
    num_rows = 10000
    groups = ["A", "B", "C", "D", "E"]
    arr_group = pa.array([groups[i % len(groups)] for i in range(num_rows)])
    arr_value = pa.array([i for i in range(num_rows)])
    table = pa.table({"group": arr_group, "value": arr_value})
    
    # Starlink setup
    schema = Schema([
        Field("group", pa.string()),
        Field("value", pa.int64()),
    ])
    batch = RecordBatch(schema, [
        ArrowFieldVector(arr_group),
        ArrowFieldVector(arr_value),
    ])
    data_source = InMemoryDataSource(schema, [batch])
    ctx = ExecutionContext({})
    
    # Test 1: Simple aggregation
    def starlink_agg():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.aggregate([col("group")], [Sum(col("value")), Max(col("value")), Min(col("value"))])
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    def arrow_agg():
        # PyArrow doesn't have native group_by, use pandas
        import pandas as pd
        df = table.to_pandas()
        grouped = df.groupby("group")["value"].agg(["sum", "max", "min"])
        return len(grouped)
    
    bench.run_comparison("Aggregate: Simple aggregation (5 groups, 3 aggs)", starlink_agg, arrow_agg)
    
    # Test 2: Single group (no grouping)
    def starlink_single():
        schema2 = Schema([Field("value", pa.int64())])
        batch2 = RecordBatch(schema2, [ArrowFieldVector(arr_value)])
        data_source2 = InMemoryDataSource(schema2, [batch2])
        df = DataFrameImpl(Scan('', data_source2, []))
        df = df.aggregate([], [Sum(col("value")), Max(col("value")), Min(col("value"))])
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    def arrow_single():
        # Direct aggregation on array
        sum_val = pc.sum(arr_value).as_py()
        max_val = pc.max(arr_value).as_py()
        min_val = pc.min(arr_value).as_py()
        return 1  # Single result row
    
    bench.run_comparison("Aggregate: Single group (no grouping)", starlink_single, arrow_single)


def benchmark_end_to_end(bench: ArrowBenchmarkSuite, csv_file: str):
    """Benchmark end-to-end queries: Starlink vs PyArrow."""
    print("\n📊 Benchmarking End-to-End Queries...")
    
    ctx = ExecutionContext({})
    
    # Test 1: Filter + Project
    def starlink_filter_project():
        df = ctx.csv(csv_file)
        df = df.filter(Gt(cast(col("id"), pa.int64()), lit(500)))
        df = df.project([col("id"), col("value1")])
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    def arrow_filter_project():
        table = pacsv.read_csv(csv_file)
        # Convert to numeric
        table = table.cast(pa.schema([
            pa.field("id", pa.int64()),
            pa.field("value1", pa.int64()),
            pa.field("value2", pa.int64()),
            pa.field("value3", pa.float64()),
            pa.field("group", pa.string()),
        ]))
        # Filter and project
        mask = pc.greater(table["id"], pa.scalar(500))
        filtered = table.filter(mask)
        projected = filtered.select(["id", "value1"])
        return len(projected)
    
    bench.run_comparison("E2E: Filter + Project", starlink_filter_project, arrow_filter_project)
    
    # Test 2: Aggregation
    def starlink_agg_e2e():
        df = ctx.csv(csv_file)
        value_col = cast(col("value1"), pa.int64())
        df = df.aggregate([col("group")], [Sum(value_col), Max(value_col)])
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    def arrow_agg_e2e():
        import pandas as pd
        table = pacsv.read_csv(csv_file)
        df = table.to_pandas()
        df["value1"] = df["value1"].astype(int)
        grouped = df.groupby("group")["value1"].agg(["sum", "max"])
        return len(grouped)
    
    bench.run_comparison("E2E: GROUP BY with aggregation", starlink_agg_e2e, arrow_agg_e2e)


def main():
    parser = argparse.ArgumentParser(description="Benchmark Starlink vs PyArrow")
    parser.add_argument("--iterations", type=int, default=5, help="Number of iterations per benchmark")
    parser.add_argument("--warmup", type=int, default=2, help="Number of warmup iterations")
    parser.add_argument("--output", type=str, help="Output file for results")
    parser.add_argument("--rows", type=int, default=10000, help="Number of rows in test data")
    args = parser.parse_args()
    
    print("🚀 Starlink vs PyArrow Benchmark Suite")
    print("="*140)
    print(f"Iterations: {args.iterations}")
    print(f"Warmup: {args.warmup}")
    print(f"Test data size: {args.rows} rows")
    print("="*140)
    
    bench = ArrowBenchmarkSuite(iterations=args.iterations, warmup=args.warmup)
    
    # Create temporary directory for test files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        csv_file = create_test_csv(tmp_path, num_rows=args.rows)
        
        # Run benchmarks
        try:
            benchmark_csv_reading(bench, csv_file)
            benchmark_filtering(bench)
            benchmark_expressions(bench)
            benchmark_aggregation(bench)
            benchmark_end_to_end(bench, csv_file)
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
    print("\n📝 Notes:")
    print("- Speedup > 1.0x means Starlink is faster")
    print("- Speedup < 1.0x means PyArrow is faster")
    print("- Overhead shows percentage difference (positive = Starlink slower)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

