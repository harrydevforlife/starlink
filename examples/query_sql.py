import timeit
from pathlib import Path

from starlink.execution.context import ExecutionContext

cwd = Path(__file__).parent.parent

def query_sql(sql: str, file_format: str = "csv"):
    ctx = ExecutionContext({})
    if file_format == "csv":
        ctx.register_csv("tripdata", cwd / "data" / "yellow_tripdata_2019-01.csv")
    elif file_format == "parquet":
        ctx.register_parquet("tripdata", cwd / "data" / "tripdata" / "parquet")
    else:
        raise ValueError(f"Invalid file format: {file_format}")
    df = ctx.sql(sql)
    print("Original Plan:")
    print("-"*10)
    print(df.logicalPlan().pretty())
    print("Optimized Plan:")
    print("-"*10)
    print(df.optimizedPlan().pretty())
    results = ctx.execute(df)
    print(results.to_markdown())

# sql = """
#     SELECT 
#         passenger_count, 
#         COUNT(fare_amount) 
#     FROM tripdata 
#     GROUP BY passenger_count
# """
# print(timeit.timeit(lambda: query_sql(sql), number=1))


sql_without_cast = """
    SELECT t.passenger_count, 
            MAX(t.fare_amount) as max_fare,
            MIN(t.fare_amount) as min_fare,
            COUNT(t.fare_amount) as count
    FROM tripdata t
    GROUP BY t.passenger_count
"""
print(timeit.timeit(lambda: query_sql(sql_without_cast, file_format="parquet"), number=1))


sql_with_cast = """
    SELECT passenger_count, 
            MAX(CAST(fare_amount AS DOUBLE)) as max_fare,
            MIN(CAST(fare_amount AS DOUBLE)) as min_fare,
            COUNT(fare_amount) as count
    FROM tripdata 
    GROUP BY passenger_count
"""
print(timeit.timeit(lambda: query_sql(sql_with_cast, file_format="parquet"), number=1))


sql = """
    SELECT passenger_count, 
            MAX(CAST(fare_amount AS DOUBLE)) as max_fare
    FROM tripdata 
    WHERE CAST(passenger_count AS INT64) > 2 AND CAST(fare_amount AS DOUBLE) > 10
    GROUP BY passenger_count
"""
print(timeit.timeit(lambda: query_sql(sql, file_format="parquet"), number=1))
print("-"*10)
# print(timeit.timeit(lambda: query_sql(sql, file_format="csv"), number=1))