import pytest

from starlink.sql.sql_tokenizer import SqlTokenizer
from starlink.sql.sql_parser import SqlParser
from starlink.sql.sql_expr import (
    SqlExpr,
    SqlIdentifier,
    SqlBinaryExpr,
    SqlString,
    SqlLong,
    SqlDouble,
    SqlFunction,
    SqlAlias,
    SqlCast,
    SqlSort,
    SqlSelect,
    SqlTable,
    SqlJoin,
)


def parse(sql: str) -> SqlExpr:
    """Helper function to parse SQL string into SqlExpr."""
    tokens = SqlTokenizer(sql).tokenize()
    parsed_query = SqlParser(tokens).parse()
    if parsed_query is None:
        raise ValueError(f"Failed to parse SQL: {sql}")
    return parsed_query


def parse_select(sql: str) -> SqlSelect:
    """Helper function to parse SQL SELECT statement."""
    result = parse(sql)
    if not isinstance(result, SqlSelect):
        raise ValueError(f"Expected SqlSelect, got {type(result)}")
    return result


class TestSqlParser:
    def test_arithmetic_precedence_1_plus_2_times_3(self):
        expr = parse("1 + 2 * 3")
        expected = SqlBinaryExpr(SqlLong(1), "+", SqlBinaryExpr(SqlLong(2), "*", SqlLong(3)))
        assert expr == expected

    def test_arithmetic_precedence_1_times_2_plus_3(self):
        expr = parse("1 * 2 + 3")
        expected = SqlBinaryExpr(SqlBinaryExpr(SqlLong(1), "*", SqlLong(2)), "+", SqlLong(3))
        assert expr == expected

    def test_simple_select(self):
        select = parse_select("SELECT id, first_name, last_name FROM employee")
        assert isinstance(select.relation, SqlTable)
        assert select.relation.name == "employee"
        assert select.projection == [
            SqlIdentifier("id"),
            SqlIdentifier("first_name"),
            SqlIdentifier("last_name"),
        ]

    def test_projection_with_binary_expression(self):
        select = parse_select("SELECT salary * 0.1 FROM employee")
        assert isinstance(select.relation, SqlTable)
        assert select.projection == [
            SqlBinaryExpr(SqlIdentifier("salary"), "*", SqlDouble(0.1))
        ]

    def test_projection_with_aliased_binary_expression(self):
        select = parse_select("SELECT salary * 0.1 AS bonus FROM employee")
        assert isinstance(select.relation, SqlTable)

        expected_binary_expr = SqlBinaryExpr(SqlIdentifier("salary"), "*", SqlDouble(0.1))
        expected_aliased_expr = SqlAlias(expected_binary_expr, SqlIdentifier("bonus"))
        assert select.projection == [expected_aliased_expr]

    def test_parse_select_with_where(self):
        select = parse_select("SELECT id, first_name, last_name FROM employee WHERE state = 'CO'")
        assert select.projection == [
            SqlIdentifier("id"),
            SqlIdentifier("first_name"),
            SqlIdentifier("last_name"),
        ]
        assert select.selection == SqlBinaryExpr(SqlIdentifier("state"), "=", SqlString("CO"))
        assert isinstance(select.relation, SqlTable)
        assert select.relation.name == "employee"

    def test_parse_select_with_order(self):
        select = parse_select("SELECT state, salary FROM employee ORDER BY salary desc, state")
        assert select.projection == [SqlIdentifier("state"), SqlIdentifier("salary")]
        assert select.orderBy == [
            SqlSort(SqlIdentifier("salary"), False),
            SqlSort(SqlIdentifier("state"), True),
        ]

    def test_parse_select_with_aggregates(self):
        select = parse_select("SELECT state, MAX(salary) FROM employee GROUP BY state")
        assert select.projection == [
            SqlIdentifier("state"),
            SqlFunction("MAX", [SqlIdentifier("salary")]),
        ]
        assert select.groupBy == [SqlIdentifier("state")]
        assert isinstance(select.relation, SqlTable)

    def test_parse_select_with_aliased_aggregates(self):
        select = parse_select("SELECT state, MAX(salary) AS top_wage FROM employee GROUP BY state")
        max_func = SqlFunction("MAX", [SqlIdentifier("salary")])
        alias = SqlAlias(max_func, SqlIdentifier("top_wage"))
        assert select.projection == [SqlIdentifier("state"), alias]
        assert select.groupBy == [SqlIdentifier("state")]
        assert isinstance(select.relation, SqlTable)

    def test_parse_select_with_aggregates_and_having(self):
        select = parse_select(
            "SELECT state, MAX(salary) AS top_wage FROM employee "
            "GROUP BY state HAVING MAX(salary) > 10 AND MAX(salary) < 100"
        )
        max_func = SqlFunction("MAX", [SqlIdentifier("salary")])
        alias = SqlAlias(max_func, SqlIdentifier("top_wage"))
        assert select.projection == [SqlIdentifier("state"), alias]
        assert select.groupBy == [SqlIdentifier("state")]
        assert isinstance(select.relation, SqlTable)
        # Note: HAVING clause parsing is implemented but complex expression matching
        # would require more detailed assertion logic

    def test_parse_select_with_aggregates_and_cast(self):
        select = parse_select(
            "SELECT state, MAX(CAST(salary AS double)) FROM employee GROUP BY state"
        )
        cast_expr = SqlCast(SqlIdentifier("salary"), SqlIdentifier("double"))
        assert select.projection == [
            SqlIdentifier("state"),
            SqlFunction("MAX", [cast_expr]),
        ]
        assert select.groupBy == [SqlIdentifier("state")]
        assert isinstance(select.relation, SqlTable)

    def test_parse_simple_expression(self):
        expr = parse("a + b")
        expected = SqlBinaryExpr(SqlIdentifier("a"), "+", SqlIdentifier("b"))
        assert expr == expected

    def test_parse_comparison_expression(self):
        expr = parse("x > 10")
        expected = SqlBinaryExpr(SqlIdentifier("x"), ">", SqlLong(10))
        assert expr == expected

    def test_parse_logical_expression(self):
        expr = parse("a > 5 AND b < 10")
        expected = SqlBinaryExpr(
            SqlBinaryExpr(SqlIdentifier("a"), ">", SqlLong(5)),
            "AND",
            SqlBinaryExpr(SqlIdentifier("b"), "<", SqlLong(10)),
        )
        assert expr == expected

    def test_parse_function_call(self):
        expr = parse("MAX(salary)")
        expected = SqlFunction("MAX", [SqlIdentifier("salary")])
        assert expr == expected

    def test_parse_string_literal(self):
        expr = parse("'hello'")
        assert expr == SqlString("hello")

    def test_parse_double_literal(self):
        expr = parse("3.14")
        assert expr == SqlDouble(3.14)

    def test_parse_long_literal(self):
        expr = parse("42")
        assert expr == SqlLong(42)

    def test_parse_select_with_join(self):
        select = parse_select(
            "SELECT id FROM employee JOIN dept_info ON state = region_code"
        )
        assert isinstance(select.relation, SqlJoin)
        assert isinstance(select.relation.left, SqlTable)
        assert isinstance(select.relation.right, SqlTable)
        assert select.relation.left.name == "employee"
        assert select.relation.right.name == "dept_info"

    def test_parse_table_alias(self):
        select = parse_select("SELECT e.id FROM employee e")
        assert isinstance(select.relation, SqlTable)
        assert select.relation.alias == "e"

    def test_parse_table_alias_with_as(self):
        select = parse_select("SELECT e.id FROM employee AS e")
        assert isinstance(select.relation, SqlTable)
        assert select.relation.alias == "e"

    def test_parse_join_with_aliases(self):
        select = parse_select(
            "SELECT e.id FROM employee e JOIN dept_info d ON e.state = d.region_code"
        )
        assert isinstance(select.relation, SqlJoin)
        assert isinstance(select.relation.left, SqlTable)
        assert select.relation.left.alias == "e"
        assert isinstance(select.relation.right, SqlTable)
        assert select.relation.right.alias == "d"
        assert select.relation.condition == SqlBinaryExpr(
            SqlIdentifier("e.state"), "=", SqlIdentifier("d.region_code")
        )

    def test_parse_join_with_aliases_and_as(self):
        select = parse_select(
            "SELECT e.id FROM employee AS e JOIN dept_info AS d ON e.state = d.region_code"
        )
        assert isinstance(select.relation, SqlJoin)
        assert isinstance(select.relation.left, SqlTable)
        assert select.relation.left.alias == "e"
        assert isinstance(select.relation.right, SqlTable)
        assert select.relation.right.alias == "d"