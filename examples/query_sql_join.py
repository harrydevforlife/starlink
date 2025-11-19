"""
Examples demonstrating SQL JOIN queries with Starlink.

This script registers two in-memory tables (`customers` and `orders`) so it can be
run without any external data files. Each example issues a SQL query that
uses table aliases, performs a JOIN, and prints results via the `QueryResult.show()` API.
"""
from tempfile import NamedTemporaryFile
import os
import csv
from textwrap import dedent

import pyarrow as pa

from starlink.datasources.memory import InMemoryDataSource
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.schema import Field, Schema
from starlink.execution.context import ExecutionContext


created_files = []

def create_csv_table(data: dict) -> str:
    """Write the provided columnar data to a temporary CSV file."""
    column_names = list(data.keys())
    columns = list(data.values())
    row_count = len(columns[0]) if columns else 0
    if any(len(col) != row_count for col in columns):
        raise ValueError("All columns must have the same length")
    rows = zip(*columns)

    tmp = NamedTemporaryFile(mode="w", newline="", suffix=".csv", delete=False)
    try:
        writer = csv.writer(tmp)
        writer.writerow(column_names)
        writer.writerows(rows)
    finally:
        tmp.close()

    created_files.append(tmp.name)
    return tmp.name


def register_csv_table(ctx: ExecutionContext, name: str, path: str) -> None:
    """Register a simple in-memory table built from Python lists."""
    datasource = ctx.csv(path)
    ctx.register(name, datasource)


def run_example(ctx: ExecutionContext, title: str, sql: str) -> None:
    """Execute a SQL query and display its results."""

    print(f"\n=== {title} ===")
    print(sql.strip())
    df = ctx.sql(sql)
    print("Original Plan:")
    print("-"*10)
    print(df.logicalPlan().pretty())
    print("Optimized Plan:")
    print("-"*10)
    print(df.optimizedPlan().pretty())
    result = ctx.execute(df)
    result.show()


def main() -> None:
    ctx = ExecutionContext()

    register_csv_table(
        ctx,
        "customers",
        create_csv_table(
            {
                "customer_id": [1, 2, 3, 4],
                "name": ["Alice", "Bob", "Charlie", "Dana"],
                "city": ["New York", "San Francisco", "New York", "Austin"],
                "vip_status": ["Gold", "Silver", "Bronze", "Gold"],
            }
        )
    )

    register_csv_table(
        ctx,
        "orders",
        create_csv_table(
            {
                "order_id": [100, 101, 102, 103, 104],
                "order_customer_id": [1, 1, 2, 3, 99],  # 99 demonstrates an order without a matching customer
                "total": [23.50, 57.25, 89.00, 12.10, 5.00],
                "status": ["COMPLETE", "PENDING", "COMPLETE", "CANCELLED", "UNKNOWN"],
            }
        )
    )

    run_example(
        ctx,
        "1. Basic inner join between customers and orders",
        dedent(
            """
            SELECT
                c.customer_id,
                c.name,
                o.order_id,
                o.total,
                o.status
            FROM customers c
            JOIN orders o
                ON c.customer_id = o.order_customer_id
            """
        ),
    )

    run_example(
        ctx,
        "2. Join with a filter to show only high-value orders",
        dedent(
            """
            SELECT
                c.name,
                c.city,
                o.order_id,
                o.total
            FROM customers c
            JOIN orders o
                ON c.customer_id = o.order_customer_id
            WHERE CAST(o.total AS DOUBLE) > 30
            """
        ),
    )

    run_example(
        ctx,
        "3. Join followed by aggregation (orders per city)",
        dedent(
            """
            SELECT
                c.city,
                COUNT(o.order_id) AS orders_in_city
            FROM customers c
            JOIN orders o
                ON c.customer_id = o.order_customer_id
            GROUP BY c.city
            """
        ),
    )

    run_example(
        ctx,
        "4. Join with a filter to show only high-value orders",
        dedent(
            """
            SELECT
                c.name,
                c.city,
                o.order_id,
                o.total
            FROM customers AS c
            JOIN orders AS o
                ON c.customer_id = o.order_customer_id
            WHERE CAST(o.total AS DOUBLE) > 30
                AND c.city = 'New York'
            """
        ),
    )


if __name__ == "__main__":
    main()
    for file in created_files:
        os.unlink(file)