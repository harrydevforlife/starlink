import timeit
from pathlib import Path

from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, cast, Max, Count
from starlink.datatypes.arrow_types import ArrowTypes
from starlink.optimizer.optimizer import Optimizer

cwd = Path(__file__).parent.parent

def query_count(optimize: bool = True):
    ctx = ExecutionContext()
    df = (
        ctx.csv(cwd / "data" / "yellow_tripdata_2019-01.csv")
        .aggregate(
            [], [Count(col("VendorID"))]
        )
    )
    results = ctx.execute(df)
    print(results.to_markdown())

import pandas as pd

def query_count_pd():
    df = pd.read_csv(cwd / "data" / "yellow_tripdata_2019-01.csv")
    # count the number of rows in the dataframe
    print(f"rows: {len(df)}")


print(timeit.timeit(lambda: query_count(optimize=True), number=1))
print(timeit.timeit(lambda: query_count_pd(), number=1))