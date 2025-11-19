import pytest

from starlink.sql.sql_tokenizer import SqlTokenizer
from starlink.sql.tokens import Token, Keyword, Symbol, Literal


class TestSqlTokenizer:
    def test_tokenize_simple_select(self):
        expected = [
            Token("SELECT", Keyword.SELECT, 6),
            Token("id", Literal.IDENTIFIER, 9),
            Token(",", Symbol.COMMA, 10),
            Token("first_name", Literal.IDENTIFIER, 21),
            Token(",", Symbol.COMMA, 22),
            Token("last_name", Literal.IDENTIFIER, 32),
            Token("FROM", Keyword.FROM, 37),
            Token("employee", Literal.IDENTIFIER, 46),
        ]
        actual = SqlTokenizer("SELECT id, first_name, last_name FROM employee").tokenize().tokens
        assert actual == expected

    def test_projection_with_binary_expression(self):
        expected = [
            Token("SELECT", Keyword.SELECT, 6),
            Token("salary", Literal.IDENTIFIER, 13),
            Token("*", Symbol.STAR, 15),
            Token("0.1", Literal.DOUBLE, 19),
            Token("FROM", Keyword.FROM, 24),
            Token("employee", Literal.IDENTIFIER, 33),
        ]
        actual = SqlTokenizer("SELECT salary * 0.1 FROM employee").tokenize().tokens
        assert actual == expected

    def test_projection_with_aliased_binary_expression(self):
        expected = [
            Token("SELECT", Keyword.SELECT, 6),
            Token("salary", Literal.IDENTIFIER, 13),
            Token("*", Symbol.STAR, 15),
            Token("0.1", Literal.DOUBLE, 19),
            Token("AS", Keyword.AS, 22),
            Token("bonus", Literal.IDENTIFIER, 28),
            Token("FROM", Keyword.FROM, 33),
            Token("employee", Literal.IDENTIFIER, 42),
        ]
        actual = SqlTokenizer("SELECT salary * 0.1 AS bonus FROM employee").tokenize().tokens
        assert actual == expected

    def test_tokenize_select_with_where(self):
        expected = [
            Token("SELECT", Keyword.SELECT, 6),
            Token("a", Literal.IDENTIFIER, 8),
            Token(",", Symbol.COMMA, 9),
            Token("b", Literal.IDENTIFIER, 11),
            Token("FROM", Keyword.FROM, 16),
            Token("employee", Literal.IDENTIFIER, 25),
            Token("WHERE", Keyword.WHERE, 31),
            Token("state", Literal.IDENTIFIER, 37),
            Token("=", Symbol.EQ, 39),
            Token("CO", Literal.STRING, 44),
        ]
        actual = SqlTokenizer("SELECT a, b FROM employee WHERE state = 'CO'").tokenize().tokens
        assert actual == expected

    def test_tokenize_select_with_aggregates(self):
        expected = [
            Token("SELECT", Keyword.SELECT, 6),
            Token("state", Literal.IDENTIFIER, 12),
            Token(",", Symbol.COMMA, 13),
            Token("MAX", Keyword.MAX, 17),
            Token("(", Symbol.LEFT_PAREN, 18),
            Token("salary", Literal.IDENTIFIER, 24),
            Token(")", Symbol.RIGHT_PAREN, 25),
            Token("FROM", Keyword.FROM, 30),
            Token("employee", Literal.IDENTIFIER, 39),
            Token("GROUP", Keyword.GROUP, 45),
            Token("BY", Keyword.BY, 48),
            Token("state", Literal.IDENTIFIER, 54),
        ]
        actual = SqlTokenizer("SELECT state, MAX(salary) FROM employee GROUP BY state").tokenize().tokens
        assert actual == expected

    def test_tokenize_select_with_aggregates_and_having(self):
        expected = [
            Token("SELECT", Keyword.SELECT, 6),
            Token("state", Literal.IDENTIFIER, 12),
            Token(",", Symbol.COMMA, 13),
            Token("MAX", Keyword.MAX, 17),
            Token("(", Symbol.LEFT_PAREN, 18),
            Token("salary", Literal.IDENTIFIER, 24),
            Token(")", Symbol.RIGHT_PAREN, 25),
            Token("FROM", Keyword.FROM, 30),
            Token("employee", Literal.IDENTIFIER, 39),
            Token("GROUP", Keyword.GROUP, 45),
            Token("BY", Keyword.BY, 48),
            Token("state", Literal.IDENTIFIER, 54),
            Token("HAVING", Keyword.HAVING, 61),
            Token("MAX", Keyword.MAX, 65),
            Token("(", Symbol.LEFT_PAREN, 66),
            Token("salary", Literal.IDENTIFIER, 72),
            Token(")", Symbol.RIGHT_PAREN, 73),
            Token(">", Symbol.GT, 75),
            Token("10", Literal.LONG, 78),
        ]
        actual = SqlTokenizer("SELECT state, MAX(salary) FROM employee GROUP BY state HAVING MAX(salary) > 10").tokenize().tokens
        assert actual == expected

    def test_tokenize_compound_operators(self):
        expected = [
            Token("a", Literal.IDENTIFIER, 1),
            Token(">=", Symbol.GT_EQ, 4),
            Token("b", Literal.IDENTIFIER, 6),
            Token("OR", Keyword.OR, 9),
            Token("a", Literal.IDENTIFIER, 11),
            Token("<=", Symbol.LT_EQ, 14),
            Token("b", Literal.IDENTIFIER, 16),
            Token("OR", Keyword.OR, 19),
            Token("a", Literal.IDENTIFIER, 21),
            Token("<>", Symbol.LT_GT, 24),
            Token("b", Literal.IDENTIFIER, 26),
            Token("OR", Keyword.OR, 29),
            Token("a", Literal.IDENTIFIER, 31),
            Token("!=", Symbol.BANG_EQ, 34),
            Token("b", Literal.IDENTIFIER, 36),
        ]
        actual = SqlTokenizer("a >= b OR a <= b OR a <> b OR a != b").tokenize().tokens
        assert actual == expected

    def test_tokenize_long_values(self):
        expected = [
            Token("123456789", Literal.LONG, 9),
            Token("+", Symbol.PLUS, 11),
            Token("987654321", Literal.LONG, 21),
        ]
        actual = SqlTokenizer("123456789 + 987654321").tokenize().tokens
        assert actual == expected

    def test_tokenize_float_double_values(self):
        expected = [
            Token("123456789.00", Literal.DOUBLE, 12),
            Token("+", Symbol.PLUS, 14),
            Token("987654321.001", Literal.DOUBLE, 28),
        ]
        actual = SqlTokenizer("123456789.00 + 987654321.001").tokenize().tokens
        assert actual == expected

    def test_tokenize_table_group(self):
        expected = [
            Token("select", Keyword.SELECT, 6),
            Token("*", Symbol.STAR, 8),
            Token("from", Keyword.FROM, 13),
            Token("group", Literal.IDENTIFIER, 19),
        ]
        actual = SqlTokenizer("select * from group").tokenize().tokens
        assert actual == expected

    def test_tokenize_string_literals(self):
        expected = [
            Token("name", Literal.IDENTIFIER, 4),
            Token("=", Symbol.EQ, 6),
            Token("John", Literal.STRING, 13),
        ]
        actual = SqlTokenizer("name = 'John'").tokenize().tokens
        assert actual == expected

    def test_tokenize_double_quoted_strings(self):
        expected = [
            Token("name", Literal.IDENTIFIER, 4),
            Token("=", Symbol.EQ, 6),
            Token("John", Literal.STRING, 13),
        ]
        actual = SqlTokenizer('name = "John"').tokenize().tokens
        assert actual == expected

    def test_tokenize_negative_numbers(self):
        expected = [
            Token("-123", Literal.LONG, 4),
            Token("+", Symbol.PLUS, 6),
            Token("456", Literal.LONG, 10),
        ]
        actual = SqlTokenizer("-123 + 456").tokenize().tokens
        assert actual == expected

    def test_tokenize_backtick_identifiers(self):
        expected = [
            Token("select", Keyword.SELECT, 6),
            Token("my_column", Literal.IDENTIFIER, 18),  # After closing backtick
            Token("from", Keyword.FROM, 23),
            Token("my_table", Literal.IDENTIFIER, 34),  # After closing backtick
        ]
        actual = SqlTokenizer("select `my_column` from `my_table`").tokenize().tokens
        assert actual == expected