

from abc import ABC
from dataclasses import dataclass
from typing import List, Optional


class SqlExpr(ABC):
    """Base interface for SQL expressions."""
    pass


@dataclass
class SqlIdentifier(SqlExpr):
    """Simple SQL identifier such as a table or column name."""

    id: str

    def __str__(self) -> str:
        return self.id


@dataclass
class SqlBinaryExpr(SqlExpr):
    """Binary expression."""

    l: SqlExpr
    op: str
    r: SqlExpr

    def __str__(self) -> str:
        return f"{self.l} {self.op} {self.r}"


@dataclass
class SqlString(SqlExpr):
    """SQL literal string."""

    value: str

    def __str__(self) -> str:
        return f"'{self.value}'"


@dataclass
class SqlLong(SqlExpr):
    """SQL literal long integer."""

    value: int

    def __str__(self) -> str:
        return str(self.value)


@dataclass
class SqlDouble(SqlExpr):
    """SQL literal double (floating point)."""

    value: float

    def __str__(self) -> str:
        return str(self.value)


@dataclass
class SqlFunction(SqlExpr):
    """SQL function call."""

    id: str
    args: List[SqlExpr]

    def __str__(self) -> str:
        return self.id


@dataclass
class SqlAlias(SqlExpr):
    """SQL aliased expression."""

    expr: SqlExpr
    alias: SqlIdentifier


@dataclass
class SqlCast(SqlExpr):
    """SQL cast expression."""

    expr: SqlExpr
    dataType: SqlIdentifier


@dataclass
class SqlSort(SqlExpr):
    """SQL sort expression."""

    expr: SqlExpr
    asc: bool


class SqlRelation(SqlExpr):
    """Base interface for SQL relations (tables, subqueries, etc.)."""
    pass


@dataclass
class SqlTable(SqlRelation):
    """Simple table reference (with optional alias)."""

    name: str
    alias: Optional[str] = None


@dataclass
class SqlJoin(SqlRelation):
    """SQL join relation (supports inner join for now)."""

    left: SqlRelation
    right: SqlRelation
    condition: SqlExpr
    join_type: str = "INNER"


@dataclass
class SqlSelect(SqlRelation):
    """SQL SELECT statement."""

    projection: List[SqlExpr]
    selection: Optional[SqlExpr]
    groupBy: List[SqlExpr]
    orderBy: List[SqlExpr]
    having: Optional[SqlExpr]
    relation: SqlRelation
