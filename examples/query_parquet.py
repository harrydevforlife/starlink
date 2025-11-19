
import timeit
from pathlib import Path

from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, cast, Max, Count
from starlink.datatypes.arrow_types import ArrowTypes
from starlink.optimizer.optimizer import Optimizer

cwd = Path(__file__).parent.parent

def query_parquet(optimize: bool = True):
    ctx = ExecutionContext()
    df = ctx.parquet(cwd / "data" / "yellow_tripdata_2019-01.parquet").aggregate(
        [col("passenger_count")], [Max(cast(col("fare_amount"), ArrowTypes.FloatType))]
    )
    if optimize:
        optimizedPlan = Optimizer().optimize(df.logicalPlan())
    else:
        optimizedPlan = df.logicalPlan()
    print(optimizedPlan.pretty())
    results = ctx.execute(optimizedPlan)
    print(results.to_markdown())


def count_rows(optimize: bool = True):
    ctx = ExecutionContext()
    df = ctx.parquet(cwd / "data" / "yellow_tripdata_2019-01.parquet").aggregate(
        [], [Count(col("VendorID"))]
    )
    if optimize:
        optimizedPlan = Optimizer().optimize(df.logicalPlan())
    else:
        optimizedPlan = df.logicalPlan()
    print(optimizedPlan.pretty())
    results = ctx.execute(optimizedPlan)
    for result in results:
        print(result.to_csv())



print(timeit.timeit(lambda: query_parquet(optimize=True), number=1))
print(timeit.timeit(lambda: query_parquet(optimize=False), number=1))
# print(timeit.timeit(lambda: count_rows(optimize=True), number=1))
# print(timeit.timeit(lambda: count_rows(optimize=False), number=1))
