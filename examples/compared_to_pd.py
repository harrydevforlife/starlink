
import timeit
from pathlib import Path

import pandas as pd

from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, cast, Max
from starlink.datatypes.arrow_types import ArrowTypes
from starlink.optimizer.optimizer import Optimizer

cwd = Path(__file__).parent.parent

def query_csv():
    ctx = ExecutionContext()
    df = (
        ctx.csv(cwd / "data" / "yellow_tripdata_2019-01.csv")
        .aggregate(
            [col("passenger_count")], [Max(col("fare_amount"))]
        )
    )
    optimizedPlan = df.optimizedPlan()

    # print the logical plan
    print(optimizedPlan.pretty())
    results = ctx.execute(optimizedPlan)
    print(results.to_csv())

def query_pd():
    df = pd.read_csv(cwd / "data" / "yellow_tripdata_2019-01.csv")
    df = df.groupby("passenger_count").agg({"fare_amount": "max"})
    print(df.to_csv())

starlink_query_time = (timeit.timeit(lambda: query_csv(), number=1))
pd_query_time = (timeit.timeit(lambda: query_pd(), number=1))

print("-"*10)
print(f"Starlink query time: {starlink_query_time} seconds")
print(f"Pandas query time: {pd_query_time} seconds")
print(f"Speedup: {pd_query_time / starlink_query_time}x")
print("-"*10)