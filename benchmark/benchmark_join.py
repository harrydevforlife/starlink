"""
Benchmark the Starlink join operator on a synthesized large dataset and
optionally compare against Pandas and DuckDB running on the same generated
data. When comparison engines are enabled, the script executes equivalent
join/aggregation logic in each engine and reports per-iteration timings.

Usage example:
    PYTHONPATH=$(pwd)/src uv run python benchmark/benchmark_join.py \\
        --customers 200000 --orders 1000000 --items 4000000 \\
        --iterations 3 --pandas --duckdb
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

try:
    import pandas as pd

    HAS_PANDAS = True
except Exception:  # pragma: no cover
    pd = None
    HAS_PANDAS = False

try:
    import duckdb

    HAS_DUCKDB = True
except Exception:
    HAS_DUCKDB = False

from starlink.execution.context import ExecutionContext


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Starlink join benchmark")
    parser.add_argument("--data-dir", default="data/join_benchmark", help="Directory for generated Parquet files")
    parser.add_argument("--customers", type=int, default=200_000, help="Number of customer rows")
    parser.add_argument("--orders", type=int, default=1_000_000, help="Number of order rows")
    parser.add_argument("--items", type=int, default=4_000_000, help="Number of order_items rows")
    parser.add_argument("--chunk-size", type=int, default=500_000, help="Rows per generated chunk")
    parser.add_argument("--iterations", type=int, default=3, help="Query repetitions for timing")
    parser.add_argument("--force-recreate", action="store_true", help="Regenerate dataset even if files exist")
    parser.add_argument("--print-result", action="store_true", help="Print resulting rows for inspection")
    parser.add_argument("--pandas", action="store_true", help="Run the same query using Pandas")
    parser.add_argument("--duckdb", action="store_true", help="Run the same query using DuckDB (if available)")
    parser.add_argument("--duckdb-path", default=":memory:", help="Optional DuckDB database path")
    return parser.parse_args()


def ensure_dataset(
    data_dir: Path,
    num_customers: int,
    num_orders: int,
    num_items: int,
    chunk_size: int,
    force_recreate: bool,
) -> Dict[str, Path]:
    data_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "customers": data_dir / "customers.parquet",
        "orders": data_dir / "orders.parquet",
        "order_items": data_dir / "order_items.parquet",
    }

    if not force_recreate and all(path.exists() for path in files.values()):
        return files

    rng = np.random.default_rng(seed=42)

    print("Generating synthetic customers table...")
    customer_schema = pa.schema(
        [
            ("customer_id", pa.int64()),
            ("region_id", pa.int16()),
            ("vip_status", pa.bool_()),
            ("signup_days", pa.int32()),
        ]
    )
    _write_parquet(
        files["customers"],
        customer_schema,
        generate_customers(num_customers, chunk_size, rng),
    )

    print("Generating synthetic orders table...")
    order_schema = pa.schema(
        [
            ("order_id", pa.int64()),
            ("customer_id", pa.int64()),
            ("order_days", pa.int32()),
            ("status_code", pa.int8()),
            ("total_amount", pa.float64()),
        ]
    )
    _write_parquet(
        files["orders"],
        order_schema,
        generate_orders(num_orders, num_customers, chunk_size, rng),
    )

    print("Generating synthetic order_items table...")
    item_schema = pa.schema(
        [
            ("item_id", pa.int64()),
            ("order_id", pa.int64()),
            ("sku_id", pa.int32()),
            ("quantity", pa.int16()),
            ("price", pa.float64()),
            ("extended_price", pa.float64()),
        ]
    )
    _write_parquet(
        files["order_items"],
        item_schema,
        generate_order_items(num_items, num_orders, chunk_size, rng),
    )

    return files


def _write_parquet(path: Path, schema: pa.Schema, batches: Iterable[Dict[str, pa.Array]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pq.ParquetWriter(path, schema=schema) as writer:
        for batch in batches:
            table = pa.table(batch, schema=schema)
            writer.write_table(table)


def generate_customers(
    total_rows: int,
    chunk_size: int,
    rng: np.random.Generator,
) -> Generator[Dict[str, pa.Array], None, None]:
    for start in range(0, total_rows, chunk_size):
        size = min(chunk_size, total_rows - start)
        ids = np.arange(start + 1, start + size + 1, dtype=np.int64)
        regions = rng.integers(1, 51, size=size, dtype=np.int16)
        vip_status = rng.random(size=size) < 0.15
        signup_days = rng.integers(0, 365 * 5, size=size, dtype=np.int32)
        yield {
            "customer_id": pa.array(ids, type=pa.int64()),
            "region_id": pa.array(regions, type=pa.int16()),
            "vip_status": pa.array(vip_status, type=pa.bool_()),
            "signup_days": pa.array(signup_days, type=pa.int32()),
        }


def generate_orders(
    total_rows: int,
    num_customers: int,
    chunk_size: int,
    rng: np.random.Generator,
) -> Generator[Dict[str, pa.Array], None, None]:
    status_weights = np.array([0.65, 0.2, 0.1, 0.05])
    status_codes = np.array([1, 2, 3, 4], dtype=np.int8)
    cumulative = np.cumsum(status_weights)

    for start in range(0, total_rows, chunk_size):
        size = min(chunk_size, total_rows - start)
        order_ids = np.arange(start + 1, start + size + 1, dtype=np.int64)
        customer_ids = rng.integers(1, num_customers + 1, size=size, dtype=np.int64)
        order_days = rng.integers(0, 365 * 3, size=size, dtype=np.int32)
        status_rand = rng.random(size=size)
        status = status_codes[np.searchsorted(cumulative, status_rand)]
        totals = rng.gamma(shape=2.0, scale=50.0, size=size).astype(np.float64)

        yield {
            "order_id": pa.array(order_ids, type=pa.int64()),
            "customer_id": pa.array(customer_ids, type=pa.int64()),
            "order_days": pa.array(order_days, type=pa.int32()),
            "status_code": pa.array(status, type=pa.int8()),
            "total_amount": pa.array(totals, type=pa.float64()),
        }


def generate_order_items(
    total_rows: int,
    num_orders: int,
    chunk_size: int,
    rng: np.random.Generator,
) -> Generator[Dict[str, pa.Array], None, None]:
    for start in range(0, total_rows, chunk_size):
        size = min(chunk_size, total_rows - start)
        item_ids = np.arange(start + 1, start + size + 1, dtype=np.int64)
        order_ids = rng.integers(1, num_orders + 1, size=size, dtype=np.int64)
        sku_ids = rng.integers(1, 200_000, size=size, dtype=np.int32)
        quantity = rng.integers(1, 10, size=size, dtype=np.int16)
        price = rng.gamma(shape=2.5, scale=20.0, size=size)
        extended = price * quantity

        yield {
            "item_id": pa.array(item_ids, type=pa.int64()),
            "order_id": pa.array(order_ids, type=pa.int64()),
            "sku_id": pa.array(sku_ids, type=pa.int32()),
            "quantity": pa.array(quantity, type=pa.int16()),
            "price": pa.array(price, type=pa.float64()),
            "extended_price": pa.array(extended, type=pa.float64()),
        }


def _to_python_value(value):
    if isinstance(value, np.generic):
        return value.item()
    return value


def _records_from_dataframe(df: "pd.DataFrame") -> List[Dict[str, object]]:
    records = df.to_dict(orient="records")
    return [{k: _to_python_value(v) for k, v in rec.items()} for rec in records]


def _benchmark_loop(
    name: str,
    iterations: int,
    execute_fn,
) -> (Dict[str, float], List[Dict[str, object]]):
    times: List[float] = []
    preview: List[Dict[str, object]] = []
    rows_count = 0

    for i in range(iterations):
        start = time.perf_counter()
        rows = execute_fn()
        elapsed = time.perf_counter() - start
        rows_count = len(rows)
        times.append(elapsed)
        # if not preview:
        #     preview = rows[:5]
        print(f"{name:9s} iteration {i + 1}/{iterations}: {elapsed:.2f}s ({rows_count} rows)")

    stats = {
        "iterations": len(times),
        "avg": sum(times) / len(times) if times else 0.0,
        "best": min(times) if times else 0.0,
        "worst": max(times) if times else 0.0,
        "rows": rows_count,
    }
    return stats, preview


def run_starlink_benchmark(
    data_paths: Dict[str, Path],
    iterations: int,
    query_sql: str,
) -> (Dict[str, float], List[Dict[str, object]]):
    ctx = ExecutionContext({})
    ctx.register_parquet("customers", str(data_paths["customers"]))
    ctx.register_parquet("orders", str(data_paths["orders"]))
    ctx.register_parquet("order_items", str(data_paths["order_items"]))

    def execute():
        df = ctx.sql(query_sql)
        result = ctx.execute(df)
        return result

    return _benchmark_loop("Starlink", iterations, execute)


def run_pandas_benchmark(
    data_paths: Dict[str, Path],
    iterations: int,
    query_sql: str,
    max_rows: Optional[int] = None,
) -> (Dict[str, float], List[Dict[str, object]]):
    if not HAS_PANDAS:
        raise RuntimeError("Pandas is not available")

    customer_cols = ["customer_id", "region_id", "vip_status"]
    order_cols = ["order_id", "customer_id", "order_days", "total_amount"]
    item_cols = ["order_id", "price", "extended_price"]

    customers_df = pd.read_parquet(data_paths["customers"], columns=customer_cols)
    orders_df = pd.read_parquet(data_paths["orders"], columns=order_cols)
    order_items_df = pd.read_parquet(data_paths["order_items"], columns=item_cols)

    def execute():
        orders_filtered = orders_df.loc[orders_df["order_days"] > 365, ["order_id", "customer_id", "total_amount"]].copy()
        items_filtered = order_items_df.loc[order_items_df["price"] > 15, ["order_id", "extended_price"]].copy()
        merged = orders_filtered.merge(
            customers_df, on="customer_id", how="inner"
        ).merge(
            items_filtered, on="order_id", how="inner"
        )
        grouped = (
            merged.groupby(["region_id", "vip_status"], as_index=False)
            .agg(
                order_rows=("order_id", "count"),
                gross_revenue=("extended_price", "sum"),
                sum_order_total=("total_amount", "sum"),
            )
            .sort_values("gross_revenue", ascending=False)
        )
        return _records_from_dataframe(grouped)

    return _benchmark_loop("Pandas", iterations, execute)


def run_duckdb_benchmark(
    data_paths: Dict[str, Path],
    iterations: int,
    query_sql: str,
    duckdb_path: str,
) -> (Dict[str, float], List[Dict[str, object]]):
    if not HAS_DUCKDB:
        raise RuntimeError("DuckDB is not available")

    con = duckdb.connect(database=duckdb_path, read_only=False)
    try:
        threads = int(duckdb.get_option("threads"))
    except Exception:
        threads = None
    if threads:
        con.execute(f"PRAGMA threads={threads}")
    for table_name, path in data_paths.items():
        con.execute(
            f"CREATE OR REPLACE VIEW {table_name} AS "
            f"SELECT * FROM read_parquet('{path.as_posix()}')"
        )

    def execute():
        res = con.execute(query_sql)
        rows = res.fetchall()
        columns = [col[0] for col in res.description]
        return [dict(zip(columns, row)) for row in rows]

    return _benchmark_loop("DuckDB", iterations, execute)


def benchmark_join(
    data_paths: Dict[str, Path],
    iterations: int,
    print_result: bool,
    run_pandas: bool,
    run_duckdb: bool,
    duckdb_path: str,
) -> None:
    query_sql = """
        SELECT
            c.region_id,
            c.vip_status,
            COUNT(o.order_id) AS order_rows,
            SUM(i.extended_price) AS gross_revenue,
            SUM(o.total_amount) AS sum_order_total
        FROM customers c
        JOIN orders o
            ON c.customer_id = o.customer_id
        JOIN order_items i
            ON o.order_id = i.order_id
        WHERE o.order_days > 365
          AND i.price > 15
        GROUP BY c.region_id, c.vip_status
        ORDER BY gross_revenue DESC
    """

    engines_results = []

    starlink_stats, starlink_preview = run_starlink_benchmark(
        data_paths, iterations, query_sql
    )
    engines_results.append(("Starlink", starlink_stats))

    if run_pandas:
        pandas_stats, pandas_preview = run_pandas_benchmark(
            data_paths, iterations, query_sql, max_rows=100
        )
        engines_results.append(("Pandas", pandas_stats))
        if print_result and pandas_preview:
            starlink_preview = pandas_preview

    if run_duckdb:
        duckdb_stats, duckdb_preview = run_duckdb_benchmark(
            data_paths, iterations, query_sql, duckdb_path
        )
        engines_results.append(("DuckDB", duckdb_stats))
        if print_result and duckdb_preview:
            starlink_preview = duckdb_preview

    print("\n=== Join Benchmark Summary ===")
    for name, stats in engines_results:
        print(
            f"{name:9s} -> iter={stats['iterations']}  "
            f"avg={stats['avg']:.2f}s  best={stats['best']:.2f}s  worst={stats['worst']:.2f}s"
        )

    if run_pandas or run_duckdb:
        starlink_avg = starlink_stats["avg"]
        print("\nSpeedup vs Starlink (lower is faster):")
        for name, stats in engines_results:
            if name == "Starlink":
                continue
            ratio = stats["avg"] / starlink_avg if starlink_avg > 0 else float("inf")
            print(f"  {name:9s}: {ratio:.2f}x of Starlink runtime")

    if print_result and starlink_preview:
        print("\nResult preview (first rows):")
        for row in starlink_preview[:5]:
            print(row)


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    paths = ensure_dataset(
        data_dir,
        num_customers=args.customers,
        num_orders=args.orders,
        num_items=args.items,
        chunk_size=args.chunk_size,
        force_recreate=args.force_recreate,
    )
    benchmark_join(
        paths,
        args.iterations,
        args.print_result,
        run_pandas=args.pandas,
        run_duckdb=args.duckdb,
        duckdb_path=args.duckdb_path,
    )


if __name__ == "__main__":
    main()

