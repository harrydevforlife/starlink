"""Execution Context

Provides a context for executing queries, managing tables, and executing logical plans.
"""

from typing import Dict, Optional, Sequence, Union

from starlink.datasources.csv import CsvDataSource
from starlink.datasources.datasource import DataSource
from starlink.datasources.parquet import ParquetDataSource
from starlink.datatypes.record_batch import RecordBatch
from starlink.execution.result import QueryResult
from starlink.logicalplan.dataframe import DataFrame, DataFrameImpl
from starlink.logicalplan.logical import LogicalPlan
from starlink.logicalplan.scan import Scan
from starlink.optimizer.optimizer import Optimizer
from starlink.queryplanner.queryplanner import QueryPlanner
from starlink.sql.sql_parser import SqlParser
from starlink.sql.sql_planner import SqlPlanner
from starlink.sql.sql_tokenizer import SqlTokenizer


class ExecutionContext:
    """Execution context for managing tables and executing queries.

    Provides methods to:
    - Register tables (CSV files, DataFrames, DataSources)
    - Execute SQL queries
    - Execute logical plans
    """

    def __init__(self, settings: Optional[Dict[str, str]] = None):
        """Initialize execution context.

        Args:
            settings: Optional dictionary of settings. Currently supports:
                - "starlink.datasources.csv.batchSize": Batch size for CSV reading (default: "1024")
        """
        self.settings = settings or {}
        self.batch_size = int(self.settings.get("starlink.datasources.csv.batchSize", "1024"))

        # Tables registered with this context
        self._tables: Dict[str, DataFrame] = {}

    def sql(self, sql: str) -> DataFrame:
        """Create a DataFrame for the given SQL SELECT statement.

        Args:
            sql: SQL SELECT statement string

        Returns:
            DataFrame representing the query

        Raises:
            ValueError: If SQL cannot be parsed or table not found
        """
        tokens = SqlTokenizer(sql).tokenize()
        ast = SqlParser(tokens).parse()

        # Ensure we got a SqlSelect
        from starlink.sql.sql_expr import SqlSelect
        if not isinstance(ast, SqlSelect):
            raise ValueError(f"Expected SELECT statement, got: {type(ast)}")

        df = SqlPlanner().create_data_frame(ast, self._tables)
        return DataFrameImpl(df.logicalPlan())

    def csv(self, filename: str) -> DataFrame:
        """Get a DataFrame representing the specified CSV file.

        Args:
            filename: Path to CSV file

        Returns:
            DataFrame for the CSV file
        """
        return DataFrameImpl(
            Scan(filename, CsvDataSource(filename, None, True, self.batch_size), [])
        )

    def parquet(self, filename: str) -> DataFrame:
        """Get a DataFrame representing the specified Parquet file or directory.

        Args:
            filename: Path to Parquet file or directory containing Parquet files
                     - If file: Uses native PyArrow API (educational)
                     - If directory: Uses PyArrow Dataset API (production, supports predicate pushdown)

        Returns:
            DataFrame for the Parquet file(s)
        """
        return DataFrameImpl(
            Scan(filename, ParquetDataSource(filename, self.batch_size), [])
        )

    def register(self, tablename: str, df: DataFrame) -> None:
        """Register a DataFrame with the context.

        Args:
            tablename: Name to register the table under
            df: DataFrame to register
        """
        self._tables[tablename] = df

    def register_data_source(self, tablename: str, datasource: DataSource) -> None:
        """Register a DataSource with the context.

        Args:
            tablename: Name to register the table under
            datasource: DataSource to register
        """
        self.register(tablename, DataFrameImpl(Scan(tablename, datasource, [])))

    def register_csv(self, tablename: str, filename: str) -> None:
        """Register a CSV data source with the context.

        Args:
            tablename: Name to register the table under
            filename: Path to CSV file
        """
        self.register(tablename, self.csv(filename))

    def register_parquet(self, tablename: str, filename: str) -> None:
        """Register a Parquet data source with the context.

        Args:
            tablename: Name to register the table under
            filename: Path to Parquet file
        """
        self.register(tablename, self.parquet(filename))

    def execute(self, plan_or_df: Union[LogicalPlan, DataFrame]) -> QueryResult:
        """Execute the logical plan represented by a DataFrame or a LogicalPlan.

        This method:
        1. Optimizes the logical plan
        2. Creates a physical plan
        3. Executes the physical plan

        Args:
            plan_or_df: Either a DataFrame or LogicalPlan to execute

        Returns:
            QueryResult object providing convenient methods like show(), to_markdown(), collect()
        """
        batches = self.execute_batches(plan_or_df)
        return QueryResult(batches)
    
    def execute_batches(self, plan_or_df: Union[LogicalPlan, DataFrame]) -> Sequence[RecordBatch]:
        """Execute the logical plan and return raw RecordBatch sequence.

        This method:
        1. Optimizes the logical plan
        2. Creates a physical plan
        3. Executes the physical plan

        Args:
            plan_or_df: Either a DataFrame or LogicalPlan to execute

        Returns:
            Sequence of RecordBatch objects (generator) for advanced use cases
        """
        if isinstance(plan_or_df, DataFrame):
            plan = plan_or_df.logicalPlan()
        else:
            plan = plan_or_df

        optimized_plan = Optimizer().optimize(plan)
        physical_plan = QueryPlanner().create_physical_plan(optimized_plan)
        return physical_plan.execute()
