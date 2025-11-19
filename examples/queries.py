from pathlib import Path
from starlink.execution.context import ExecutionContext

# Create execution context
ctx = ExecutionContext({})

# Register a CSV file
ctx.register_csv("tripdata", Path("data/yellow_tripdata_2019-01.csv"))

# Execute SQL query
df = ctx.sql("""
    SELECT 
        passenger_count, 
        MAX(fare_amount) 
    FROM tripdata
    WHERE CAST(fare_amount AS DOUBLE) > 80
    GROUP BY passenger_count
""")

# View the logical plan
print("Original Plan:")
print(df.logicalPlan().pretty())

# View the optimized plan
print("\nOptimized Plan:")
print(df.optimizedPlan().pretty())

# Execute and get results
result = ctx.execute(df)
result.show()