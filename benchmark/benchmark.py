#!/usr/bin/env python3
"""
Performance Benchmark Suite for Starlink Query Engine

This script benchmarks various operations to measure the impact of optimizations:
- Expression evaluation (vectorized vs row-by-row)
- Selection/filtering operations
- CSV reading and batch processing
- Aggregation operations
- Projection operations

Usage:
    python benchmark.py [--iterations N] [--warmup N] [--output FILE]
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

from starlink.datasources.csv import CsvDataSource
from starlink.datasources.memory import InMemoryDataSource
from starlink.datatypes.schema import Schema, Field
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, lit, Sum, Max, Min, Eq, Gt, Add, Multiply, And, Lt, cast


class BenchmarkResult:
    """Store benchmark results for a single operation."""
    
    def __init__(self, name: str):
        self.name = name
        self.times: List[float] = []
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
            f"{self.name:40s} | "
            f"Mean: {self.mean*1000:8.2f}ms | "
            f"Median: {self.median*1000:8.2f}ms | "
            f"Min: {self.min*1000:8.2f}ms | "
            f"Max: {self.max*1000:8.2f}ms | "
            f"Stdev: {self.stdev*1000:6.2f}ms"
        )


class BenchmarkSuite:
    """Benchmark suite for Starlink operations."""
    
    def __init__(self, iterations: int = 5, warmup: int = 2):
        self.iterations = iterations
        self.warmup = warmup
        self.results: Dict[str, BenchmarkResult] = {}
    
    def run(self, name: str, func, *args, **kwargs):
        """Run a benchmark function multiple times."""
        # Warmup
        for _ in range(self.warmup):
            func(*args, **kwargs)
        
        # Actual benchmark
        result = BenchmarkResult(name)
        for _ in range(self.iterations):
            start = time.perf_counter()
            func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            result.add_time(elapsed)
        
        result.compute_stats()
        self.results[name] = result
        return result
    
    def print_results(self):
        """Print all benchmark results."""
        print("\n" + "="*120)
        print("BENCHMARK RESULTS")
        print("="*120)
        print(f"{'Operation':40s} | {'Mean (ms)':>10s} | {'Median (ms)':>12s} | {'Min (ms)':>10s} | {'Max (ms)':>10s} | {'Stdev (ms)':>12s}")
        print("-"*120)
        
        for result in sorted(self.results.values(), key=lambda x: x.name):
            print(result)
        
        print("="*120)
    
    def save_results(self, filename: str):
        """Save results to a file."""
        with open(filename, 'w') as f:
            f.write("Benchmark Results\n")
            f.write("="*120 + "\n")
            for result in sorted(self.results.values(), key=lambda x: x.name):
                f.write(str(result) + "\n")


def create_test_csv(tmp_path: Path, num_rows: int = 10000) -> str:
    """Create a test CSV file with sample data."""
    csv_file = tmp_path / "test_data.csv"
    
    with open(csv_file, 'w') as f:
        # Write header
        f.write("id,first_name,last_name,age,salary,department\n")
        
        # Write data
        departments = ["Engineering", "Sales", "Marketing", "HR", "Finance"]
        for i in range(num_rows):
            dept = departments[i % len(departments)]
            f.write(f"{i},{'First'}{i},{'Last'}{i},{20 + (i % 40)},{50000 + (i % 100000)},{dept}\n")
    
    return str(csv_file)


def benchmark_csv_reading(bench: BenchmarkSuite, csv_file: str):
    """Benchmark CSV reading operations."""
    print("\n📊 Benchmarking CSV Reading Operations...")
    
    # Test 1: Read all columns
    def read_all_columns():
        csv_ds = CsvDataSource(csv_file, None, True, 1024)
        batches = list(csv_ds.scan([]))
        total_rows = sum(batch.rowCount() for batch in batches)
        return total_rows
    
    bench.run("CSV: Read all columns (no projection)", read_all_columns)
    
    # Test 2: Read with projection (2 columns)
    def read_with_projection():
        csv_ds = CsvDataSource(csv_file, None, True, 1024)
        batches = list(csv_ds.scan(["id", "first_name"]))
        total_rows = sum(batch.rowCount() for batch in batches)
        return total_rows
    
    bench.run("CSV: Read with projection (2 cols)", read_with_projection)
    
    # Test 3: Read with projection (4 columns)
    def read_with_projection_4():
        csv_ds = CsvDataSource(csv_file, None, True, 1024)
        batches = list(csv_ds.scan(["id", "first_name", "last_name", "age"]))
        total_rows = sum(batch.rowCount() for batch in batches)
        return total_rows
    
    bench.run("CSV: Read with projection (4 cols)", read_with_projection_4)
    
    # Test 4: Read with small batch size
    def read_small_batches():
        csv_ds = CsvDataSource(csv_file, None, True, 100)
        batches = list(csv_ds.scan([]))
        total_rows = sum(batch.rowCount() for batch in batches)
        return total_rows
    
    bench.run("CSV: Read with small batches (100)", read_small_batches)


def benchmark_expression_evaluation(bench: BenchmarkSuite):
    """Benchmark expression evaluation operations."""
    print("\n📊 Benchmarking Expression Evaluation...")
    
    # Create test data
    schema = Schema([
        Field("a", pa.int64()),
        Field("b", pa.int64()),
        Field("c", pa.float64()),
    ])
    
    num_rows = 10000
    batch = RecordBatch(schema, [
        ArrowFieldVector(pa.array([i for i in range(num_rows)])),
        ArrowFieldVector(pa.array([i * 2 for i in range(num_rows)])),
        ArrowFieldVector(pa.array([float(i) * 1.5 for i in range(num_rows)])),
    ])
    
    data_source = InMemoryDataSource(schema, [batch])
    ctx = ExecutionContext({})
    
    # Test 1: Simple comparison
    def simple_comparison():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.filter(Gt(col("a"), lit(5000)))
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("Expression: Simple comparison (a > 5000)", simple_comparison)
    
    # Test 2: Complex boolean expression
    def complex_boolean():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.filter(
            And(Gt(col("a"), lit(1000)), Lt(col("b"), lit(15000)))
        )
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("Expression: Complex boolean (a>1000 AND b<15000)", complex_boolean)
    
    # Test 3: Math expression
    from starlink.logicalplan.expressions import Alias
    def math_expression():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.project([Alias(Add(col("a"), col("b")), "sum")])
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("Expression: Math expression (a + b)", math_expression)
    
    # Test 4: Multiple math expressions
    def multiple_math():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.project([
            Alias(Add(col("a"), col("b")), "sum"),
            Alias(Multiply(col("a"), lit(2)), "double_a"),
        ])
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("Expression: Multiple math expressions", multiple_math)


def benchmark_filtering(bench: BenchmarkSuite):
    """Benchmark filtering/selection operations."""
    print("\n📊 Benchmarking Filtering Operations...")
    
    # Create test data
    schema = Schema([
        Field("id", pa.int64()),
        Field("value", pa.int64()),
    ])
    
    num_rows = 10000
    batch = RecordBatch(schema, [
        ArrowFieldVector(pa.array([i for i in range(num_rows)])),
        ArrowFieldVector(pa.array([i % 100 for i in range(num_rows)])),
    ])
    
    data_source = InMemoryDataSource(schema, [batch])
    ctx = ExecutionContext({})
    
    # Test 1: Simple filter (50% selectivity)
    def simple_filter():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.filter(Lt(col("value"), lit(50)))
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("Filter: Simple filter (50% selectivity)", simple_filter)
    
    # Test 2: Tight filter (10% selectivity)
    def tight_filter():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.filter(Lt(col("value"), lit(10)))
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("Filter: Tight filter (10% selectivity)", tight_filter)
    
    # Test 3: Loose filter (90% selectivity)
    def loose_filter():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.filter(Lt(col("value"), lit(90)))
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("Filter: Loose filter (90% selectivity)", loose_filter)


def benchmark_aggregation(bench: BenchmarkSuite):
    """Benchmark aggregation operations."""
    print("\n📊 Benchmarking Aggregation Operations...")
    
    # Create test data with groups
    schema = Schema([
        Field("group", pa.string()),
        Field("value", pa.int64()),
    ])
    
    num_rows = 10000
    groups = ["A", "B", "C", "D", "E"]
    batch = RecordBatch(schema, [
        ArrowFieldVector(pa.array([groups[i % len(groups)] for i in range(num_rows)])),
        ArrowFieldVector(pa.array([i for i in range(num_rows)])),
    ])
    
    data_source = InMemoryDataSource(schema, [batch])
    ctx = ExecutionContext({})
    
    # Test 1: Simple aggregation (5 groups)
    def simple_aggregation():
        df = DataFrameImpl(Scan('', data_source, []))
        df = df.aggregate([col("group")], [Sum(col("value")), Max(col("value")), Min(col("value"))])
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("Aggregate: Simple aggregation (5 groups, 3 aggs)", simple_aggregation)
    
    # Test 2: Single group aggregation
    def single_group():
        schema2 = Schema([Field("value", pa.int64())])
        batch2 = RecordBatch(schema2, [
            ArrowFieldVector(pa.array([i for i in range(num_rows)])),
        ])
        data_source2 = InMemoryDataSource(schema2, [batch2])
        df = DataFrameImpl(Scan('', data_source2, []))
        df = df.aggregate([], [Sum(col("value")), Max(col("value")), Min(col("value"))])
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("Aggregate: Single group (no grouping)", single_group)
    
    # Test 3: Many groups (100 groups)
    def many_groups():
        groups_many = [f"Group_{i}" for i in range(100)]
        batch_many = RecordBatch(schema, [
            ArrowFieldVector(pa.array([groups_many[i % len(groups_many)] for i in range(num_rows)])),
            ArrowFieldVector(pa.array([i for i in range(num_rows)])),
        ])
        data_source_many = InMemoryDataSource(schema, [batch_many])
        df = DataFrameImpl(Scan('', data_source_many, []))
        df = df.aggregate([col("group")], [Sum(col("value"))])
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("Aggregate: Many groups (100 groups)", many_groups)


def benchmark_end_to_end(bench: BenchmarkSuite, csv_file: str):
    """Benchmark end-to-end query operations."""
    print("\n📊 Benchmarking End-to-End Queries...")
    
    ctx = ExecutionContext({})
    
    # Test 1: Simple SELECT with WHERE
    def simple_select_where():
        df = ctx.csv(csv_file)
        # CSV columns are strings, need to cast for comparison
        df = df.filter(Gt(cast(col("age"), pa.int64()), lit(30)))
        df = df.project([col("first_name"), col("last_name"), col("age")])
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("E2E: SELECT with WHERE and projection", simple_select_where)
    
    # Test 2: Aggregation query
    def aggregation_query():
        df = ctx.csv(csv_file)
        # Cast salary to int64 for aggregation
        salary_col = cast(col("salary"), pa.int64())
        df = df.aggregate(
            [col("department")], 
            [Sum(salary_col), Max(salary_col)]
        )
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("E2E: GROUP BY with aggregation", aggregation_query)
    
    # Test 3: Complex query
    def complex_query():
        df = ctx.csv(csv_file)
        # Cast age to int64 for comparison
        df = df.filter(Gt(cast(col("age"), pa.int64()), lit(25)))
        df = df.project([col("department"), col("salary")])
        # Cast salary to int64 for aggregation
        salary_col = cast(col("salary"), pa.int64())
        df = df.aggregate(
            [col("department")], 
            [Sum(salary_col), Max(salary_col)]
        )
        result = list(ctx.execute(df))
        return sum(b.rowCount() for b in result)
    
    bench.run("E2E: Complex query (filter + project + aggregate)", complex_query)


def main():
    parser = argparse.ArgumentParser(description="Benchmark Starlink query engine")
    parser.add_argument("--iterations", type=int, default=5, help="Number of iterations per benchmark")
    parser.add_argument("--warmup", type=int, default=2, help="Number of warmup iterations")
    parser.add_argument("--output", type=str, help="Output file for results")
    parser.add_argument("--rows", type=int, default=10000, help="Number of rows in test data")
    args = parser.parse_args()
    
    print("🚀 Starlink Query Engine Benchmark Suite")
    print("="*120)
    print(f"Iterations: {args.iterations}")
    print(f"Warmup: {args.warmup}")
    print(f"Test data size: {args.rows} rows")
    print("="*120)
    
    bench = BenchmarkSuite(iterations=args.iterations, warmup=args.warmup)
    
    # Create temporary directory for test files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        csv_file = create_test_csv(tmp_path, num_rows=args.rows)
        
        # Run benchmarks
        try:
            benchmark_csv_reading(bench, csv_file)
            benchmark_expression_evaluation(bench)
            benchmark_filtering(bench)
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
    return 0


if __name__ == "__main__":
    # Import here to avoid circular imports
    from starlink.logicalplan.dataframe import DataFrameImpl
    from starlink.logicalplan.scan import Scan
    
    sys.exit(main())

