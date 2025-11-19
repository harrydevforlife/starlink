"""Demo of QueryResult API

Shows how to use the new user-friendly QueryResult interface.
"""

from pathlib import Path
from starlink.execution.context import ExecutionContext

cwd = Path(__file__).parent.parent

# Create context and register data
ctx = ExecutionContext({})
ctx.register_csv("tripdata", cwd / "data" / "yellow_tripdata_2019-01.csv")

# Execute query - returns QueryResult
df = ctx.sql("""
    SELECT passenger_count, 
           MAX(CAST(fare_amount AS DOUBLE)) as max_fare,
           MIN(CAST(fare_amount AS DOUBLE)) as min_fare,
           COUNT(fare_amount) as count
    FROM tripdata 
    GROUP BY passenger_count
    LIMIT 10
""")

result = ctx.execute(df)

print("=" * 60)
print("1. Using show() - formatted table display")
print("=" * 60)
result.show(limit=10)

print("\n" + "=" * 60)
print("2. Using to_markdown() - markdown table")
print("=" * 60)
print(result.to_markdown(limit=10))

print("\n" + "=" * 60)
print("3. Using collect() - get as list of dicts")
print("=" * 60)
rows = result.collect()
print(f"Collected {len(rows)} rows")
print(f"First row: {rows[0] if rows else None}")

print("\n" + "=" * 60)
print("4. Using to_csv() - CSV format")
print("=" * 60)
print(result.to_csv()[:200] + "...")

print("\n" + "=" * 60)
print("5. Using __repr__ and __len__")
print("=" * 60)
print(f"Result: {result}")
print(f"Total rows: {len(result)}")

print("\n" + "=" * 60)
print("6. Using execute_batches() - for advanced users")
print("=" * 60)
batches = ctx.execute_batches(df)
batch_list = list(batches)
print(f"Got {len(batch_list)} batches")
if batch_list:
    print(f"First batch has {batch_list[0].row_count()} rows")

