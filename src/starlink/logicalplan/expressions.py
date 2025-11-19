from typing import List, Union

import pyarrow as pa

from starlink.logicalplan.expr import LogicalExpr
from starlink.logicalplan.logical import LogicalPlan
from starlink.datatypes.schema import Field
from starlink.datatypes.arrow_types import ArrowTypes


class LiteralDouble(LogicalExpr):
    """Create a literal double expression from a float.

    Actually, this is a literal expression for float64 in pyarrow.DataType.
    """
    def __init__(self, n: float):
        self.n = n

    def to_field(self, input: LogicalPlan) -> Field:
        """Return schema field for this literal double."""
        return Field(str(self.n), pa.float64())

    def __str__(self) -> str:
        """String representation of the literal double."""
        return str(self.n)


class LiteralBoolean(LogicalExpr):
    """Create a literal boolean expression from a bool."""

    def __init__(self, b: bool):
        self.b = b

    def to_field(self, input: LogicalPlan) -> Field:
        """Return schema field for this literal boolean."""
        return Field(str(self.b), pa.bool_())

    def __str__(self) -> str:
        """String representation of the literal boolean."""
        return "TRUE" if self.b else "FALSE"


class CastExpr(LogicalExpr):
    """Create a cast expression from an expression and a data type."""

    def __init__(self, expr: LogicalExpr, dataType: pa.DataType):
        self.expr = expr
        self.dataType = dataType

    def to_field(self, input: LogicalPlan) -> Field:
        """Return schema field after casting."""
        return Field(self.expr.to_field(input).name, self.dataType)

    def __str__(self) -> str:
        """String representation of the cast expression."""
        return f"CAST({self.expr} AS {self.dataType})"


class BinaryExpr(LogicalExpr):
    """Create a binary expression from a name, an operator, and two expressions."""

    def __init__(self, name: str, op: str, left: LogicalExpr, right: LogicalExpr):
        self.name = name
        self.op = op
        self.left = left
        self.right = right

    def __str__(self) -> str:
        """String representation of the binary expression."""
        return f"{self.left} {self.op} {self.right}"


class UnaryExpr(LogicalExpr):
    """Create a unary expression from a name, an operator, and an expression."""

    def __init__(self, name: str, op: str, expr: LogicalExpr):
        self.name = name
        self.op = op
        self.expr = expr

    def __str__(self) -> str:
        """String representation of the unary expression."""
        return f"{self.op} {self.expr}"


class Not(UnaryExpr):
    """Create a not expression from an expression."""

    def __init__(self, expr: LogicalExpr):
        super().__init__("not", "NOT", expr)

    def to_field(self, input: LogicalPlan) -> Field:
        """Return schema field for the NOT expression, always boolean type."""
        return Field(self.name, pa.bool_())


class BooleanBinaryExpr(BinaryExpr):
    """Create a boolean binary expression from a name, an operator, and two expressions."""

    def to_field(self, input: LogicalPlan) -> Field:
        """Return schema field for boolean binary expressions, always boolean type."""
        return Field(self.name, pa.bool_())


class And(BooleanBinaryExpr):
    """Create an AND logical expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("and", "AND", left, right)


class Or(BooleanBinaryExpr):
    """Create an OR logical expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("or", "OR", left, right)


class Eq(BooleanBinaryExpr):
    """Create an equality (==) logical expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("eq", "=", left, right)


class Neq(BooleanBinaryExpr):
    """Create a not-equal (!=) logical expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("neq", "!=", left, right)


class Gt(BooleanBinaryExpr):
    """Create a greater-than (>) logical expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("gt", ">", left, right)


class GtEq(BooleanBinaryExpr):
    """Create a greater-than-or-equal (>=) logical expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("gteq", ">=", left, right)


class Lt(BooleanBinaryExpr):
    """Create a less-than (<) logical expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("lt", "<", left, right)


class LtEq(BooleanBinaryExpr):
    """Create a less-than-or-equal (<=) logical expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("lteq", "<=", left, right)


class MathExpr(BinaryExpr):
    """A generic mathematical expression node."""

    def to_field(self, input: LogicalPlan) -> Field:
        """Return a schema field for mathematical expression, using left operand's datatype."""
        return Field(self.name, self.left.to_field(input).dataType)


class Add(MathExpr):
    """Create an addition (+) expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("add", "+", left, right)


class Subtract(MathExpr):
    """Create a subtraction (-) expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("subtract", "-", left, right)


class Multiply(MathExpr):
    """Create a multiplication (*) expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("mult", "*", left, right)


class Divide(MathExpr):
    """Create a division (/) expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("div", "/", left, right)


class Modulus(MathExpr):
    """Create a modulus (%) expression from two expressions."""

    def __init__(self, left: LogicalExpr, right: LogicalExpr):
        super().__init__("mod", "%", left, right)


class Alias(LogicalExpr):
    """Alias an expression with a new field name."""

    def __init__(self, expr: LogicalExpr, alias: str):
        self.expr = expr
        self.alias = alias

    def to_field(self, input: LogicalPlan) -> Field:
        """Return schema field for the aliased expression."""
        return Field(self.alias, self.expr.to_field(input).dataType)

    def __str__(self) -> str:
        """String representation of the alias expression."""
        return f"{self.expr} as {self.alias}"


class ScalarFunction(LogicalExpr):
    """Represents a scalar function expression."""

    def __init__(self, name: str, args: List[LogicalExpr], returnType: pa.DataType):
        self.name = name
        self.args = args
        self.returnType = returnType

    def to_field(self, input: LogicalPlan) -> Field:
        """Return schema field for the scalar function."""
        return Field(self.name, self.returnType)

    def __str__(self) -> str:
        """String representation for the scalar function."""
        return f"{self.name}({', '.join(str(a) for a in self.args)})"


class AggregateExpr(LogicalExpr):
    """Base class for aggregate expressions."""

    def __init__(self, name: str, expr: LogicalExpr):
        """
        Args:
            name: Name of the aggregation.
            expr: Logical expression to aggregate.
        """
        self.name = name
        self.expr = expr

    def to_field(self, input: LogicalPlan) -> Field:
        """Return schema field for the aggregate expression."""
        return Field(self.name, self.expr.to_field(input).dataType)

    def __str__(self) -> str:
        """String representation for the aggregate expression."""
        return f"{self.name}({self.expr})"


class Sum(AggregateExpr):
    """Sum aggregate function."""

    def __init__(self, input: LogicalExpr):
        """
        Args:
            input: Expression to sum.
        """
        super().__init__("SUM", input)


class Min(AggregateExpr):
    """Min aggregate function."""

    def __init__(self, input: LogicalExpr):
        """
        Args:
            input: Expression to take the minimum of.
        """
        super().__init__("MIN", input)


class Max(AggregateExpr):
    """Max aggregate function."""

    def __init__(self, input: LogicalExpr):
        """
        Args:
            input: Expression to take the maximum of.
        """
        super().__init__("MAX", input)


class Avg(AggregateExpr):
    """Average aggregate function."""

    def __init__(self, input: LogicalExpr):
        """
        Args:
            input: Expression to average.
        """
        super().__init__("AVG", input)


class Count(AggregateExpr):
    """Count aggregate function."""

    def __init__(self, input: LogicalExpr):
        """
        Args:
            input: Expression to count (non-null values).
        """
        super().__init__("COUNT", input)

    def to_field(self, input: LogicalPlan) -> Field:
        """Returns an int32 count field irrespective of input's datatype."""
        return Field("COUNT", pa.int32())

    def __str__(self) -> str:
        """String representation for count aggregate."""
        return f"COUNT({self.expr})"


class CountDistinct(AggregateExpr):
    """Count distinct aggregate function."""

    def __init__(self, input: LogicalExpr):
        """
        Args:
            input: Expression to count distinct non-null values of.
        """
        super().__init__("COUNT DISTINCT", input)

    def to_field(self, input: LogicalPlan) -> Field:
        """Returns an int32 count_distinct field."""
        return Field("COUNT_DISTINCT", pa.int32())

    def __str__(self) -> str:
        """String representation for count distinct aggregate."""
        return f"COUNT(DISTINCT {self.expr})"

class Column(LogicalExpr):
    """Represents a named column."""

    def __init__(self, name: str):
        """
        Args:
            name: The name of the column.
        """
        self.name = name

    def to_field(self, input: LogicalPlan) -> Field:
        """Return the schema field corresponding to this column."""
        fields = input.schema().fields
        for field in fields:
            if field.name == self.name:
                return field
        raise ValueError(f"No column named '{self.name}' in {', '.join([field.name for field in fields])}")

    def __str__(self) -> str:
        """String representation for the column."""
        return f"#{self.name}"

class ColumnIndex(LogicalExpr):
    """Represents a column by index in schema."""

    def __init__(self, i: int):
        """
        Args:
            i: The index of the column in input schema.
        """
        self.i = i

    def to_field(self, input: LogicalPlan) -> Field:
        """Return the schema field for the column at the given index."""
        return input.schema().fields[self.i]

    def __str__(self) -> str:
        """String representation for the column index."""
        return f"#{self.i}"

class LiteralString(LogicalExpr):
    """Represents a literal string."""

    def __init__(self, str: str):
        """
        Args:
            str: The string value.
        """
        self.str = str

    def to_field(self, input: LogicalPlan) -> Field:
        """Return a schema field for this literal string."""
        return Field(self.str, pa.string())

    def __str__(self) -> str:
        """String representation of literal string."""
        return f"'{self.str}'"

class LiteralLong(LogicalExpr):
    """Represents a literal 64-bit integer."""

    def __init__(self, n: int):
        """
        Args:
            n: The integer value.
        """
        self.n = n

    def to_field(self, input: LogicalPlan) -> Field:
        """Return a schema field for this literal long."""
        return Field(self.n, ArrowTypes.Int64Type)

    def __str__(self) -> str:
        """String representation of literal long."""
        return str(self.n)



def col(name: str) -> "Column":
    """Create a column expression from a name.

    Args:
        name: The name of the column.

    Returns:
        A column expression.
    """
    return Column(name)


def cast(expr: LogicalExpr, dataType: pa.DataType) -> CastExpr:
    """Create a cast expression from an expression and a data type.

    Args:
        expr: The expression to cast.
        dataType: The data type to cast to.

    Returns:
        A cast expression.
    """
    if not isinstance(expr, LogicalExpr):
        raise TypeError(f"expr must be a LogicalExpr, got {type(expr)}")
    if not isinstance(dataType, pa.DataType):
        raise TypeError(f"dataType must be a pyarrow.DataType, got {type(dataType)}")
    return CastExpr(expr, dataType)


def lit(value: Union[str, int, float, bool]) -> LogicalExpr:
    """Create a literal expression from a value.

    Args:
        value: The value to create a literal expression from.

    Returns:
        A literal expression.
    """
    if isinstance(value, str):
        return LiteralString(value)
    if isinstance(value, bool):
        return LiteralBoolean(value)
    if isinstance(value, int):
        return LiteralLong(value)
    if isinstance(value, float):
        return LiteralDouble(value)
    raise TypeError(f"Unsupported literal type: {type(value)}")
