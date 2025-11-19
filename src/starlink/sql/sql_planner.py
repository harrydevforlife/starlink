

"""SQL Planner

Converts parsed SQL expressions into logical plans.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import pyarrow as pa

from starlink.logicalplan.dataframe import DataFrame, DataFrameImpl
from starlink.logicalplan.expressions import (
    AggregateExpr,
    Alias,
    And,
    Avg,
    BinaryExpr,
    CastExpr,
    Column,
    ColumnIndex,
    Count,
    Divide,
    Eq,
    Gt,
    GtEq,
    LiteralDouble,
    LiteralLong,
    LiteralString,
    Lt,
    LtEq,
    Max,
    Min,
    Modulus,
    Multiply,
    Neq,
    Or,
    Subtract,
    Sum,
    Add,
)
from starlink.logicalplan.expr import LogicalExpr
from starlink.sql.sql_expr import (
    SqlAlias,
    SqlBinaryExpr,
    SqlCast,
    SqlDouble,
    SqlExpr,
    SqlFunction,
    SqlIdentifier,
    SqlLong,
    SqlSelect,
    SqlString,
    SqlTable,
    SqlJoin,
    SqlRelation,
)

logger = logging.getLogger(__name__)


@dataclass
class RelationInfo:
    """Holds the DataFrame and alias->column mapping for a relation."""

    df: DataFrame
    alias_columns: Dict[str, Dict[str, str]]


class SqlPlanner:
    """SqlPlanner creates a logical plan from a parsed SQL statement."""

    def __init__(self):
        self._relation_aliases: Dict[str, Dict[str, str]] = {}

    def create_data_frame(self, select: SqlSelect, tables: Dict[str, DataFrame]) -> DataFrame:
        """Create logical plan from parsed SQL statement.

        Args:
            select: Parsed SQL SELECT statement
            tables: Map of table names to DataFrame instances

        Returns:
            DataFrame representing the logical plan

        Raises:
            ValueError: If table not found or invalid query structure
        """
        # Build the FROM relation (handling joins) and capture alias metadata
        relation_info = self.create_relation(select.relation, tables)
        plan = relation_info.df
        self._relation_aliases = {
            alias: dict(columns) for alias, columns in relation_info.alias_columns.items()
        }

        # Translate projection SQL expressions into logical expressions
        projectionExpr = [self.create_logical_expr(expr, plan) for expr in select.projection]

        # Build a list of columns referenced in the projection
        columnNamesInProjection = self.get_referenced_columns(projectionExpr)

        aggregateExprCount = sum(1 for expr in projectionExpr if self.is_aggregate_expr(expr))
        if aggregateExprCount == 0 and select.groupBy:
            raise ValueError("GROUP BY without aggregate expressions is not supported")

        # Does the filter expression reference anything not in the final projection?
        columnNamesInSelection = self.get_columns_referenced_by_selection(select, plan)

        if aggregateExprCount == 0:
            return self.plan_non_aggregate_query(
                select, plan, projectionExpr, columnNamesInSelection, columnNamesInProjection
            )
        else:
            projection: List[LogicalExpr] = []
            aggrExpr: List[AggregateExpr] = []
            numGroupCols = len(select.groupBy)
            groupCount = 0

            for expr in projectionExpr:
                if isinstance(expr, AggregateExpr):
                    projection.append(ColumnIndex(numGroupCols + len(aggrExpr)))
                    aggrExpr.append(expr)
                elif isinstance(expr, Alias) and isinstance(expr.expr, AggregateExpr):
                    projection.append(Alias(ColumnIndex(numGroupCols + len(aggrExpr)), expr.alias))
                    aggrExpr.append(expr.expr)
                else:
                    projection.append(ColumnIndex(groupCount))
                    groupCount += 1

            plan = self.plan_aggregate_query(
                projectionExpr, select, columnNamesInSelection, plan, aggrExpr
            )
            plan = plan.project(projection)
            if select.having is not None:
                plan = plan.filter(self.create_logical_expr(select.having, plan))
            return plan

    def is_aggregate_expr(self, expr: LogicalExpr) -> bool:
        """Check if expression is an aggregate expression.

        TODO: implement this correctly - this just handles aggregates and aliased aggregates
        """
        return isinstance(expr, AggregateExpr) or (
            isinstance(expr, Alias) and isinstance(expr.expr, AggregateExpr)
        )

    def plan_non_aggregate_query(
        self,
        select: SqlSelect,
        df: DataFrame,
        projectionExpr: List[LogicalExpr],
        columnNamesInSelection: Set[str],
        columnNamesInProjection: Set[str],
    ) -> DataFrame:
        """Plan a non-aggregate query (no GROUP BY or aggregates).

        Args:
            select: SQL SELECT statement
            df: Input DataFrame
            projectionExpr: List of projection expressions
            columnNamesInSelection: Columns referenced in WHERE clause
            columnNamesInProjection: Columns referenced in projection

        Returns:
            DataFrame with projection and optional filter applied
        """
        plan = df
        if select.selection is None:
            return plan.project(projectionExpr)

        missing = columnNamesInSelection - columnNamesInProjection
        logger.info(f"** missing: {missing}")

        # If the selection only references outputs from the projection we can simply apply
        # the filter expression to the DataFrame representing the projection
        if not missing:
            plan = plan.project(projectionExpr)
            plan = plan.filter(self.create_logical_expr(select.selection, plan))
        else:
            # Because the selection references some columns that are not in the projection
            # output we need to create an interim projection that has the additional
            # columns and then we need to remove them after the selection has been applied
            n = len(projectionExpr)

            plan = plan.project(projectionExpr + [Column(col) for col in missing])
            plan = plan.filter(self.create_logical_expr(select.selection, plan))

            # Drop the columns that were added for the selection
            expr = [Column(plan.schema().fields[i].name) for i in range(n)]
            plan = plan.project(expr)

        return plan

    def plan_aggregate_query(
        self,
        projectionExpr: List[LogicalExpr],
        select: SqlSelect,
        columnNamesInSelection: Set[str],
        df: DataFrame,
        aggregateExpr: List[AggregateExpr],
    ) -> DataFrame:
        """Plan an aggregate query (with GROUP BY and aggregates).

        Args:
            projectionExpr: List of projection expressions
            select: SQL SELECT statement
            columnNamesInSelection: Columns referenced in WHERE clause
            df: Input DataFrame
            aggregateExpr: List of aggregate expressions

        Returns:
            DataFrame with aggregation applied
        """
        plan = df
        # Filter out aggregate expressions (including aliased aggregates)
        projectionWithoutAggregates = [
            expr for expr in projectionExpr 
            if not isinstance(expr, AggregateExpr) 
            and not (isinstance(expr, Alias) and isinstance(expr.expr, AggregateExpr))
        ]
        
        # Get columns referenced by aggregate expressions - these need to be available
        # for the aggregate to work, even if they're not in the final projection
        columnsInAggregates = self.get_referenced_columns(aggregateExpr)

        if select.selection is not None:
            columnNamesInProjectionWithoutAggregates = self.get_referenced_columns(
                projectionWithoutAggregates
            )

            # Missing columns = columns needed by selection but not in projection
            # Also need columns referenced by aggregates
            missing = (columnNamesInSelection | columnsInAggregates) - columnNamesInProjectionWithoutAggregates
            logger.info(f"** missing: {missing}")

            # If the selection only references outputs from the projection we can simply
            # apply the filter expression to the DataFrame representing the projection
            if not missing:
                plan = plan.project(projectionWithoutAggregates)
                plan = plan.filter(self.create_logical_expr(select.selection, plan))
            else:
                # Because the selection references some columns that are not in the
                # projection output we need to create an interim projection that has the
                # additional columns and then we need to remove them after the selection
                # has been applied
                plan = plan.project(
                    projectionWithoutAggregates + [Column(col) for col in missing]
                )
                plan = plan.filter(self.create_logical_expr(select.selection, plan))

        groupByExpr = [self.create_logical_expr(expr, plan) for expr in select.groupBy]
        return plan.aggregate(groupByExpr, aggregateExpr)

    def create_relation(self, relation: SqlRelation, tables: Dict[str, DataFrame]) -> RelationInfo:
        """Create a DataFrame for a SQL relation (table, join, etc.)."""
        if isinstance(relation, SqlTable):
            table = tables.get(relation.name)
            if table is None:
                raise ValueError(f"No table named '{relation.name}'")
            alias_name = relation.alias or relation.name
            columns = {field.name: field.name for field in table.schema().fields}
            return RelationInfo(table, {alias_name: columns})
        if isinstance(relation, SqlJoin):
            left_info = self.create_relation(relation.left, tables)
            right_info = self.create_relation(relation.right, tables)
            left_on, right_on = self._extract_join_columns(relation.condition, left_info, right_info)
            joined_df = left_info.df.join(right_info.df, left_on, right_on, relation.join_type.lower())
            alias_columns = self._merge_alias_maps(left_info, right_info, joined_df)
            return RelationInfo(joined_df, alias_columns)
        if isinstance(relation, SqlSelect):
            # Subqueries not yet supported
            raise ValueError("Subqueries in FROM clause are not supported")
        raise ValueError(f"Unsupported relation type: {type(relation)}")

    def _extract_join_columns(
        self, condition: SqlExpr, left_info: RelationInfo, right_info: RelationInfo
    ) -> Tuple[List[str], List[str]]:
        """Extract join column names from ON clause."""
        if not isinstance(condition, SqlBinaryExpr) or condition.op != "=":
            raise ValueError("Only equality join conditions are supported")
        if not isinstance(condition.l, SqlIdentifier) or not isinstance(condition.r, SqlIdentifier):
            raise ValueError("Join condition must compare two column identifiers")

        left_side, left_column = self._resolve_relation_column(condition.l, left_info, right_info)
        right_side, right_column = self._resolve_relation_column(condition.r, left_info, right_info)

        if left_side == right_side:
            raise ValueError("Join condition must reference both relations")

        if left_side == "left":
            return [left_column], [right_column]
        return [right_column], [left_column]

    def _merge_alias_maps(
        self, left_info: RelationInfo, right_info: RelationInfo, joined_df: DataFrame
    ) -> Dict[str, Dict[str, str]]:
        merged: Dict[str, Dict[str, str]] = {
            alias: dict(columns) for alias, columns in left_info.alias_columns.items()
        }

        left_count = len(left_info.df.schema().fields)
        right_original_names = [field.name for field in right_info.df.schema().fields]
        joined_names = [field.name for field in joined_df.schema().fields]
        right_new_names = joined_names[left_count:]

        if len(right_original_names) != len(right_new_names):
            raise ValueError("Join schema mismatch while merging alias metadata")

        rename_map = dict(zip(right_original_names, right_new_names))

        for alias, columns in right_info.alias_columns.items():
            if alias in merged:
                raise ValueError(f"Duplicate table or alias name '{alias}' in query")
            merged[alias] = {
                original: rename_map.get(actual, actual) for original, actual in columns.items()
            }

        return merged

    def _resolve_relation_column(
        self, identifier: SqlIdentifier, left_info: RelationInfo, right_info: RelationInfo
    ) -> Tuple[str, str]:
        """Resolve which relation (left/right) an identifier references and its actual column name."""
        name = identifier.id

        if "." in name:
            qualifier, column_name = name.split(".", 1)
            if qualifier in left_info.alias_columns:
                actual = self._lookup_alias_column(
                    left_info.alias_columns[qualifier],
                    column_name,
                    qualifier,
                    {field.name for field in left_info.df.schema().fields},
                )
                return "left", actual
            if qualifier in right_info.alias_columns:
                actual = self._lookup_alias_column(
                    right_info.alias_columns[qualifier],
                    column_name,
                    qualifier,
                    {field.name for field in right_info.df.schema().fields},
                )
                return "right", actual
            raise ValueError(f"Unknown table or alias '{qualifier}'")

        left_columns = {field.name for field in left_info.df.schema().fields}
        right_columns = {field.name for field in right_info.df.schema().fields}

        in_left = name in left_columns
        in_right = name in right_columns

        if in_left and in_right:
            raise ValueError(f"Ambiguous column '{name}' in join condition; qualify with an alias")
        if in_left:
            return "left", name
        if in_right:
            return "right", name

        raise ValueError(f"Column '{name}' not found in either relation")

    def _resolve_identifier_name(self, identifier: str) -> str:
        """Resolve a potentially qualified identifier to the actual output column name."""
        if "." not in identifier:
            return identifier

        qualifier, column_name = identifier.split(".", 1)
        alias_entry = self._relation_aliases.get(qualifier)
        if alias_entry is None:
            raise ValueError(f"Unknown table or alias '{qualifier}'")
        actual = alias_entry.get(column_name)
        if actual is None:
            raise ValueError(f"Column '{column_name}' not found in table or alias '{qualifier}'")
        return actual

    def _lookup_alias_column(
        self,
        alias_map: Dict[str, str],
        column_name: str,
        qualifier: str,
        schema_columns: Set[str],
    ) -> str:
        """Helper to resolve a column from an alias map, with fallback to the original name."""
        actual = alias_map.get(column_name)
        if actual is None:
            lower_name = column_name.lower()

            for key, value in alias_map.items():
                if key.lower() == lower_name:
                    return value
                if value.lower() == lower_name:
                    return value

            for schema_name in schema_columns:
                if schema_name.lower() == lower_name:
                    return schema_name

            raise ValueError(f"Column '{column_name}' not found in table or alias '{qualifier}'")
        return actual

    def get_columns_referenced_by_selection(self, select: SqlSelect, df: DataFrame) -> Set[str]:
        """Get column names referenced in the WHERE clause.

        Args:
            select: SQL SELECT statement
            table: Input DataFrame

        Returns:
            Set of column names referenced in WHERE clause
        """
        accumulator: Set[str] = set()
        if select.selection is not None:
            filterExpr = self.create_logical_expr(select.selection, df)
            self.visit(filterExpr, accumulator)
            validColumnNames = {field.name for field in df.schema().fields}
            accumulator = {name for name in accumulator if name in validColumnNames}
        return accumulator

    def get_referenced_columns(self, exprs: List[LogicalExpr]) -> Set[str]:
        """Get column names referenced in a list of expressions.

        Args:
            exprs: List of logical expressions

        Returns:
            Set of column names referenced
        """
        accumulator: Set[str] = set()
        for expr in exprs:
            self.visit(expr, accumulator)
        return accumulator

    def visit(self, expr: LogicalExpr, accumulator: Set[str]) -> None:
        """Visit an expression and collect referenced column names.

        Args:
            expr: Logical expression to visit
            accumulator: Set to accumulate column names into
        """
        if isinstance(expr, Column):
            accumulator.add(expr.name)
        elif isinstance(expr, Alias):
            self.visit(expr.expr, accumulator)
        elif isinstance(expr, BinaryExpr):
            self.visit(expr.l, accumulator)
            self.visit(expr.r, accumulator)
        elif isinstance(expr, CastExpr):
            self.visit(expr.expr, accumulator)
        elif isinstance(expr, AggregateExpr):
            self.visit(expr.expr, accumulator)

    def create_logical_expr(self, expr: SqlExpr, input: DataFrame) -> LogicalExpr:
        """Convert a SQL expression to a logical expression.

        Args:
            expr: SQL expression to convert
            input: Input DataFrame for context

        Returns:
            Logical expression

        Raises:
            ValueError: If expression cannot be converted
        """
        if isinstance(expr, SqlIdentifier):
            resolved = self._resolve_identifier_name(expr.id)
            return Column(resolved)
        elif isinstance(expr, SqlString):
            return LiteralString(expr.value)
        elif isinstance(expr, SqlLong):
            return LiteralLong(expr.value)
        elif isinstance(expr, SqlDouble):
            return LiteralDouble(expr.value)
        elif isinstance(expr, SqlBinaryExpr):
            l = self.create_logical_expr(expr.l, input)
            r = self.create_logical_expr(expr.r, input)
            op = expr.op
            # Comparison operators
            if op == "=":
                return Eq(l, r)
            elif op == "!=":
                return Neq(l, r)
            elif op == ">":
                return Gt(l, r)
            elif op == ">=":
                return GtEq(l, r)
            elif op == "<":
                return Lt(l, r)
            elif op == "<=":
                return LtEq(l, r)
            # Boolean operators
            elif op == "AND":
                return And(l, r)
            elif op == "OR":
                return Or(l, r)
            # Math operators
            elif op == "+":
                return Add(l, r)
            elif op == "-":
                return Subtract(l, r)
            elif op == "*":
                return Multiply(l, r)
            elif op == "/":
                return Divide(l, r)
            elif op == "%":
                return Modulus(l, r)
            else:
                raise ValueError(f"Invalid operator {op}")
        elif isinstance(expr, SqlAlias):
            return Alias(self.create_logical_expr(expr.expr, input), expr.alias.id)
        elif isinstance(expr, SqlCast):
            return CastExpr(
                self.create_logical_expr(expr.expr, input), self.parse_data_type(expr.dataType.id)
            )
        elif isinstance(expr, SqlFunction):
            func_id = expr.id
            # Handle COUNT(*) specially - COUNT(*) doesn't need a column argument
            # For COUNT(*), we use the first column of the input as a dummy argument
            # (the actual value doesn't matter, CountAccumulator just counts rows)
            if func_id == "COUNT" and len(expr.args) == 1 and isinstance(expr.args[0], SqlIdentifier) and expr.args[0].id == "*":
                # COUNT(*) - use first column as dummy argument
                if len(input.schema().fields) == 0:
                    raise ValueError("COUNT(*) requires at least one column in the table")
                # Use first column as dummy argument (value doesn't matter for COUNT)
                dummy_col = Column(input.schema().fields[0].name)
                return Count(dummy_col)

            if not expr.args:
                raise ValueError(f"Function {func_id} requires at least one argument")
            arg_expr = self.create_logical_expr(expr.args[0], input)
            if func_id == "MIN":
                return Min(arg_expr)
            elif func_id == "MAX":
                return Max(arg_expr)
            elif func_id == "SUM":
                return Sum(arg_expr)
            elif func_id == "AVG":
                return Avg(arg_expr)
            elif func_id == "COUNT":
                return Count(arg_expr)
            else:
                raise ValueError(f"Invalid aggregate function: {func_id}")
        else:
            raise ValueError(f"Cannot create logical expression from sql expression: {expr}")

    def parse_data_type(self, id: str) -> pa.DataType:
        """Parse a data type string into a PyArrow DataType.

        Args:
            id: Data type identifier (e.g., "double", "int64")

        Returns:
            PyArrow DataType

        Raises:
            ValueError: If data type is not supported
        """
        id_lower = id.lower()
        if id_lower == "double":
            return pa.float64()
        elif id_lower == "float":
            return pa.float32()
        elif id_lower == "int64" or id_lower == "long":
            return pa.int64()
        elif id_lower == "int32" or id_lower == "int":
            return pa.int32()
        elif id_lower == "string" or id_lower == "varchar":
            return pa.string()
        elif id_lower == "boolean" or id_lower == "bool":
            return pa.bool_()
        else:
            raise ValueError(f"Invalid data type: {id}")
