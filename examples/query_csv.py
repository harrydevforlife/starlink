
import timeit
from pathlib import Path

from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, cast, Max, Count
from starlink.datatypes.arrow_types import ArrowTypes
from starlink.optimizer.optimizer import Optimizer

cwd = Path(__file__).parent.parent

def query_csv(optimize: bool = True):
    ctx = ExecutionContext()
    df = (
        ctx.csv(cwd / "data" / "yellow_tripdata_2019-01.csv")
        .aggregate(
            [col("passenger_count")], [Count(col("fare_amount"))]
        )
    )
    if optimize:
        optimizedPlan = Optimizer().optimize(df.logicalPlan())
    else:
        optimizedPlan = df.logicalPlan()

    # print the logical plan
    print(optimizedPlan.pretty())
    results = ctx.execute(optimizedPlan)
    print(results.to_markdown())

print(timeit.timeit(lambda: query_csv(optimize=True), number=1))
# print(timeit.timeit(lambda: query_csv(optimize=False), number=1))