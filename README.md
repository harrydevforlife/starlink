# Starlink: A Python Query Engine

> **Making query engines understandable for Python developers**

Starlink is an educational query engine implementation in Python, designed to demystify how modern query engines work. Built with clarity and learning in mind, it demonstrates the complete journey from SQL queries to data retrieval.

## Philosophy

Starlink aims to make query engines **easily understandable for Pythonistas**. It focuses on the **process** - showing you exactly how a query flows through the system:

```
SQL → Logical Plan → Optimized Plan → Physical Plan → Data Sources
```

## Inspiration

Special thanks to Andy Grove and [How Query Engines Work](https://howqueryengineswork.com/00-introduction.html) for inspiring this project. The book provides a comprehensive introduction to query engines, and Starlink aims to make these concepts accessible to Python developers through a clean, educational implementation.

## Starlink's further implementation
- Supported hash join, inner join at this moment.
- Supported SQL alias expr.
- Supported filter pushdown.

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/harrydevforlife/starlink.git
cd starlink

# Install dependencies
uv sync

# Set up Python path
export PYTHONPATH=$PWD/src:$PYTHONPATH
```

### Basic Usage

#### Using SQL

```python
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
result.to_markdown()
```
The output will be like this:
```text
Original Plan:
Projection: #0, #1
        Aggregate: groupExpr=[#passenger_count], aggregateExpr=[MAX(#fare_amount)]
                Selection: CAST(#fare_amount AS double) > 80
                        Projection: #passenger_count, #fare_amount
                                Scan: data/yellow_tripdata_2019-01.csv; projection=None


Optimized Plan:
Projection: #0, #1
        Aggregate: groupExpr=[#passenger_count], aggregateExpr=[MAX(#fare_amount)]
                Projection: #passenger_count, #fare_amount
                        Scan: data/yellow_tripdata_2019-01.csv; projection=[passenger_count, fare_amount], filter=CAST(#fare_amount AS double) > 80

|   passenger_count |   MAX |
|-------------------|-------|
|                 1 | 99.99 |
|                 2 | 99.75 |
|                 4 | 99    |
|                 5 | 99.5  |
|                 6 | 98    |
|                 3 | 99.75 |
|                 0 | 99    |
|                 8 | 87    |
|                 9 | 92    |

(9 row(s) shown)
```


For join operations, you can use the `join` method:
```sql
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
```

#### Using DataFrame API

```python
from starlink.execution.context import ExecutionContext
from starlink.logicalplan.expressions import col, Max, Count

ctx = ExecutionContext({})
df = (
    ctx.csv("data/yellow_tripdata_2019-01.csv")
    .aggregate(
        [col("passenger_count")], 
        [Max(col("fare_amount")), Count(col("fare_amount"))]
    )
)

result = ctx.execute(df)
result.to_markdown()
```

## Architecture: The Query Journey

Starlink demonstrates the complete query execution pipeline. Here's how a query flows through the system:

### 1. SQL Parsing (`sql/`)

**Input:** SQL string  
**Output:** Abstract Syntax Tree (AST)

```text
# SQL: "SELECT passenger_count, MAX(fare_amount) FROM tripdata GROUP BY passenger_count"
# ↓
# SqlSelect AST with projection, table, and groupBy information
```

**Key Components:**
- `sql_tokenizer.py` - Tokenizes SQL into tokens
- `sql_parser.py` - Parses tokens into SQL AST using Pratt parser
- `sql_expr.py` - Defines SQL expression types

### 2. Logical Planning (`logicalplan/`)

**Input:** SQL AST  
**Output:** Logical Plan (what to do, not how)

```text
# Logical Plan represents the "what" - high-level operations
Projection: #0, #1
    Aggregate: groupExpr=[#passenger_count], aggregateExpr=[MAX(#fare_amount)]
        Scan: tripdata; projection=None
```

**Key Components:**
- `scan.py` - Represents reading from a data source
- `projection.py` - Represents column selection/transformation
- `aggregate.py` - Represents grouping and aggregation
- `select.py` - Represents filtering (WHERE clause)
- `expressions.py` - Logical expressions (Column, Max, Count, etc.)

### 3. Query Optimization (`optimizer/`)

**Input:** Logical Plan  
**Output:** Optimized Logical Plan

```text
# Optimizer applies rules to improve the plan
# Example: Projection Pushdown
Projection: #0, #1
    Aggregate: groupExpr=[#passenger_count], aggregateExpr=[MAX(#fare_amount)]
        Scan: tripdata; projection=[passenger_count, fare_amount]  # ← Pushed down!
```

**Optimization Rules:**
- **Projection Pushdown** - Only read columns that are actually needed
- **Predicate Pushdown** - Only read rows that are actually needed
- More rules can be added following the `OptimizerRule` interface

### 4. Physical Planning (`queryplanner/`)

**Input:** Optimized Logical Plan  
**Output:** Physical Plan (how to execute)

```text
# Physical Plan represents the "how" - concrete execution steps
HashAggregateExec: groupExpr=[ColumnExpression(0)], aggregateExpr=[MaxExpression(ColumnExpression(1))]
    ScanExec: projection=[passenger_count, fare_amount]
```

**Key Components:**
- `queryplanner.py` - Converts logical plans to physical plans
- Physical operators in `physicalplan/`:
  - `ScanExec` - Scans data sources
  - `ProjectionExec` - Applies projections
  - `SelectionExec` - Applies filters
  - `HashAggregateExec` - Performs hash-based aggregation

### 5. Execution (`execution/` + `physicalplan/`)

**Input:** Physical Plan  
**Output:** RecordBatch results

```python
# Physical operators execute the plan
# Each operator produces RecordBatch objects (columnar data)
results = physical_plan.execute_batches()
# Returns: Sequence[RecordBatch]

results = ctx.execute(df)
# Returns: QueryResult
```

**Execution Flow:**
1. `ExecutionContext.execute()` - Entry point
2. Optimizes the logical plan
3. Creates physical plan
4. Executes physical plan
5. Returns results as `RecordBatch` objects

### 6. Data Sources (`datasources/`)

**Input:** File paths or data  
**Output:** RecordBatch streams

**Supported Formats:**
- **CSV** (`csv.py`) - With automatic delimiter detection, header support
- **Parquet** (`parquet.py`) - Efficient columnar format
- **Memory** (`memory.py`) - In-memory data sources. Just for testing.

## Key Concepts

### Logical vs Physical Plans

**Logical Plan** (What):
- High-level, declarative representation
- Independent of execution strategy
- Example: "Aggregate by passenger_count"

**Physical Plan** (How):
- Concrete execution strategy
- Specific algorithms chosen
- Example: "HashAggregateExec using hash table"

### Columnar Data Format

Starlink uses Apache Arrow's columnar format:
- **RecordBatch** - A batch of rows stored column-wise
- **ColumnVector** - Interface for column data
- **ArrowFieldVector** - PyArrow-based implementation

This format enables:
- Efficient vectorized operations
- Better cache locality
- Reduced memory overhead

### Projection Pushdown

A key optimization that pushes column selection down to the data source:

```text
# Without optimization: Read all columns, then filter
Scan: tripdata; projection=None  # Reads all 18 columns

# With optimization: Only read needed columns
Scan: tripdata; projection=[passenger_count, fare_amount]  # Reads only 2 columns
```

This dramatically reduces I/O and memory usage for wide tables.

### Predicate Pushdown

A key optimization that pushes filter selection down to the data source:

```text
# Without optimization: Read all columns, then filter
Scan: tripdata; filter=None  # Reads all 18 columns

# With optimization: Only read needed columns
Scan: tripdata; filter=CAST(#total AS double) > 30  # Reads only 2 columns
```

## Project Structure

```
starlink/
├── datatypes/          # Core data types (Schema, RecordBatch, ColumnVector)
├── datasources/        # Data source implementations (CSV, Parquet)
├── logicalplan/        # Logical plan nodes and expressions
├── optimizer/          # Query optimization rules
├── physicalplan/       # Physical execution operators
├── queryplanner/       # Logical → Physical plan conversion
├── sql/                # SQL parsing and planning
└── execution/          # Execution context and coordination
```

## Examples

Check out the `examples/` directory for more examples:

- `query_sql.py` - SQL query examples
- `query_csv.py` - DataFrame API with CSV
- `query_parquet.py` - Parquet file queries
- `query_count.py` - COUNT aggregation examples
- `query_sql_join.py` - SQL join examples
- `queries.py` - SQL query examples

## Extending Starlink

### Adding a New Optimization Rule

```python
from starlink.optimizer.optimizer import OptimizerRule
from starlink.logicalplan.logical import LogicalPlan

class MyOptimizationRule(OptimizerRule):
    def optimize(self, plan: LogicalPlan) -> LogicalPlan:
        # Your optimization logic here
        return optimized_plan
```

### Adding a New Data Source

```python
from starlink.datasources.datasource import DataSource
from starlink.datatypes.record_batch import RecordBatch

class MyDataSource(DataSource):
    def schema(self) -> Schema:
        # Return schema
        pass
    
    def scan(self, projection: List[str], filter: Optional[Expression] = None) -> Sequence[RecordBatch]:
        # Return RecordBatch stream
        pass
```

### Adding a New Aggregate Function

1. Add logical expression in `logicalplan/expressions.py`
2. Add physical expression in `physicalplan/expressions/`
3. Add accumulator in the aggregate expression
4. Update `queryplanner.py` to handle the new function

##  Testing

```bash
# Run all tests
PYTHONPATH=src python -m pytest tests/ -v

# Run specific test suite
PYTHONPATH=src python -m pytest tests/starlink/optimizer/ -v
```

## Performance

Starlink is designed for **educational purposes** and focuses on **clarity over performance**. However, it demonstrates:

- Columnar data processing with Apache Arrow
- Projection pushdown optimization
- Efficient batch processing
- Memory-efficient streaming

[Benchmarking results](benchmark/BENCHMARK_RESULTS.md) for more details.

For production use, consider:
- [Apache Arrow DataFusion](https://github.com/apache/arrow-datafusion) (Rust)
- [Polars](https://www.pola.rs/) (Rust, Python bindings)
- [DuckDB](https://duckdb.org/) (C++)

## Contributing

Contributions are welcome! Areas where help is needed:

- Additional optimization rules
- More data source formats
- Additional SQL features
- Performance improvements
- Documentation improvements
- Test coverage

##  License



## Acknowledgments

- **Andy Grove** and [How Query Engines Work](https://howqueryengineswork.com/) - For the excellent educational resource that inspired this project
- **Apache Arrow** - For the columnar data format and PyArrow library
- The Python data engineering community - For continuous inspiration

## Resources

- [How Query Engines Work](https://howqueryengineswork.com/) - The book that inspired this project
- [Apache Arrow Documentation](https://arrow.apache.org/docs/)
- [PyArrow Documentation](https://arrow.apache.org/docs/python/)
- [NYC Dataset](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)

## Roadmap

- [x] Additional SQL features (JOINs, subqueries, etc.). Inner join is supported.
- [x] More optimization rules (predicate pushdown, etc.). Already implemented projection pushdown, predicate pushdown.
- [ ] Additional data sources (JSON, database connectors)
- [ ] Query execution statistics
- [ ] Better error messages
- [ ] Performance profiling tools

---

**Happy Querying and Exploring!**

*Starlink - Making query engines understandable, one Python line at a time.*
# starlink
