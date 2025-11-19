

import logging
from typing import List, Optional, cast

from starlink.sql.pratt_parser import PrattParser
from starlink.sql.token_stream import TokenStream
from starlink.sql.tokens import Keyword, Symbol, Literal
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
    SqlRelation,
)


class SqlParser(PrattParser):
    def __init__(self, tokens: TokenStream):
        self.tokens = tokens
        self.logger = logging.getLogger(self.__class__.__name__)

    def nextPrecedence(self) -> int:
        token = self.tokens.peek()
        if token is None:
            return 0

        precedence = 0
        if isinstance(token.type, Keyword):
            if token.type in (Keyword.AS, Keyword.ASC, Keyword.DESC):
                precedence = 10
            elif token.type == Keyword.OR:
                precedence = 20
            elif token.type == Keyword.AND:
                precedence = 30
        elif isinstance(token.type, Symbol):
            if token.type in (Symbol.LT, Symbol.LT_EQ, Symbol.EQ, Symbol.BANG_EQ, Symbol.GT_EQ, Symbol.GT):
                precedence = 40
            elif token.type in (Symbol.PLUS, Symbol.SUB):
                precedence = 50
            elif token.type in (Symbol.STAR, Symbol.SLASH):
                precedence = 60
            elif token.type == Symbol.LEFT_PAREN:
                precedence = 70

        self.logger.debug("nextPrecedence(%s) returning %d", token, precedence)
        return precedence

    def parsePrefix(self) -> Optional[SqlExpr]:
        self.logger.debug("parsePrefix() next token = %s", self.tokens.peek())
        token = self.tokens.next()
        if token is None:
            return None

        expr: Optional[SqlExpr] = None
        if isinstance(token.type, Keyword):
            if token.type == Keyword.SELECT:
                expr = self._parse_select()
            elif token.type == Keyword.CAST:
                expr = self._parse_cast()
            elif token.type in (Keyword.MAX, Keyword.MIN, Keyword.SUM, Keyword.COUNT, Keyword.AVG, Keyword.INT, Keyword.DOUBLE):
                # Parse aggregate function keywords as identifiers so they can be used in function calls
                expr = SqlIdentifier(token.text)
        elif isinstance(token.type, Symbol):
            # Handle * (STAR) as a special identifier for COUNT(*) and SELECT *
            if token.type == Symbol.STAR:
                expr = SqlIdentifier("*")
        elif isinstance(token.type, Literal):
            if token.type == Literal.IDENTIFIER:
                expr = SqlIdentifier(token.text)
            elif token.type == Literal.STRING:
                expr = SqlString(token.text)
            elif token.type == Literal.LONG:
                expr = SqlLong(int(token.text))
            elif token.type == Literal.DOUBLE:
                expr = SqlDouble(float(token.text))

        if expr is None:
            raise ValueError(f"Unexpected token {token}")

        self.logger.debug("parsePrefix() returning %s", expr)
        return expr

    def parseInfix(self, left: SqlExpr, precedence: int) -> SqlExpr:
        self.logger.debug("parseInfix() next token = %s", self.tokens.peek())
        token = self.tokens.peek()
        if token is None:
            raise ValueError("Unexpected end of tokens in infix expression")

        expr: SqlExpr
        if isinstance(token.type, Symbol):
            if token.type in (Symbol.PLUS, Symbol.SUB, Symbol.STAR, Symbol.SLASH, Symbol.EQ, Symbol.GT, Symbol.LT):
                self.tokens.next()  # consume the token
                right = self.parse(precedence)
                if right is None:
                    raise ValueError("Error parsing infix")
                expr = SqlBinaryExpr(left, token.text, right)
            elif token.type == Symbol.LEFT_PAREN:
                if isinstance(left, SqlIdentifier):
                    self.tokens.next()  # consume the token
                    args = self._parse_expr_list()
                    next_token = self.tokens.next()
                    if next_token is None or next_token.type != Symbol.RIGHT_PAREN:
                        raise ValueError("Expected RIGHT_PAREN")
                    expr = SqlFunction(left.id, args)
                else:
                    raise ValueError("Unexpected LPAREN")
            else:
                raise ValueError(f"Unexpected infix token {token}")
        elif isinstance(token.type, Keyword):
            if token.type == Keyword.AS:
                self.tokens.next()  # consume the token
                expr = SqlAlias(left, self._parse_identifier())
            elif token.type in (Keyword.AND, Keyword.OR):
                self.tokens.next()  # consume the token
                right = self.parse(precedence)
                if right is None:
                    raise ValueError("Error parsing infix")
                expr = SqlBinaryExpr(left, token.text, right)
            elif token.type in (Keyword.ASC, Keyword.DESC):
                self.tokens.next()
                expr = SqlSort(left, token.type == Keyword.ASC)
            else:
                raise ValueError(f"Unexpected infix token {token}")
        else:
            raise ValueError(f"Unexpected infix token {token}")

        self.logger.debug("parseInfix() returning %s", expr)
        return expr

    def _parse_order(self) -> List[SqlSort]:
        sort_list: List[SqlSort] = []
        sort = self._parse_expr()
        while sort is not None:
            if isinstance(sort, SqlIdentifier):
                sort = SqlSort(sort, True)
            elif not isinstance(sort, SqlSort):
                raise ValueError(f"Unexpected expression {sort} after order by.")

            sort_list.append(cast(SqlSort, sort))

            peek = self.tokens.peek()
            if peek is not None and peek.type == Symbol.COMMA:
                self.tokens.next()
            else:
                break
            sort = self._parse_expr()
        return sort_list

    def _parse_cast(self) -> SqlCast:
        if not self.tokens.consumeTokenType(Symbol.LEFT_PAREN):
            raise ValueError("Expected LEFT_PAREN in CAST")
        expr = self._parse_expr()
        if expr is None:
            raise ValueError("Expected expression in CAST")
        if not isinstance(expr, SqlAlias):
            raise ValueError("CAST expects AS expression")
        if not self.tokens.consumeTokenType(Symbol.RIGHT_PAREN):
            raise ValueError("Expected RIGHT_PAREN in CAST")
        return SqlCast(expr.expr, expr.alias)

    def _parse_select(self) -> SqlSelect:
        projection = self._parse_expr_list()

        if not self.tokens.consumeKeyword("FROM"):
            peek = self.tokens.peek()
            raise ValueError(f"Expected FROM keyword, found {peek}")

        relation = self._parse_relation()

        # parse optional WHERE clause
        filter_expr: Optional[SqlExpr] = None
        if self.tokens.consumeKeyword("WHERE"):
            filter_expr = self._parse_expr()

        # parse optional GROUP BY clause
        group_by: List[SqlExpr] = []
        if self.tokens.consumeKeywords(["GROUP", "BY"]):
            group_by = self._parse_expr_list()

        # parse optional HAVING clause
        having_expr: Optional[SqlExpr] = None
        if self.tokens.consumeKeyword("HAVING"):
            having_expr = self._parse_expr()

        # parse optional ORDER BY clause
        order_by: List[SqlExpr] = []
        if self.tokens.consumeKeywords(["ORDER", "BY"]):
            order_by = self._parse_order()

        return SqlSelect(projection, filter_expr, group_by, order_by, having_expr, relation)

    def _parse_expr_list(self) -> List[SqlExpr]:
        self.logger.debug("parseExprList()")
        expr_list: List[SqlExpr] = []
        expr = self._parse_expr()
        while expr is not None:
            expr_list.append(expr)
            peek = self.tokens.peek()
            if peek is not None and peek.type == Symbol.COMMA:
                self.tokens.next()
            else:
                break
            expr = self._parse_expr()
        self.logger.debug("parseExprList() returning %s", expr_list)
        return expr_list

    def _parse_relation(self) -> SqlRelation:
        relation: SqlRelation = self._parse_table_reference()

        while True:
            join_detected = False
            peek = self.tokens.peek()
            if peek is None:
                break

            join_type = "INNER"
            if isinstance(peek.type, Keyword) and peek.text == "JOIN":
                self.tokens.next()  # consume JOIN
                join_detected = True
            elif isinstance(peek.type, Keyword) and peek.text == "INNER":
                # Expect INNER JOIN
                self.tokens.next()  # consume INNER
                next_token = self.tokens.peek()
                if next_token is None or not (isinstance(next_token.type, Keyword) and next_token.text == "JOIN"):
                    raise ValueError("Expected JOIN after INNER")
                self.tokens.next()  # consume JOIN
                join_detected = True
            else:
                break

            if not join_detected:
                break

            right = self._parse_table_reference()
            if not self.tokens.consumeKeyword("ON"):
                raise ValueError("Expected ON after JOIN")
            condition = self._parse_expr()
            if condition is None:
                raise ValueError("Expected join condition after ON")
            relation = SqlJoin(relation, right, condition, join_type)

        return relation

    def _parse_table_reference(self) -> SqlRelation:
        table_expr = self._parse_expr()
        alias: Optional[str] = None

        if isinstance(table_expr, SqlAlias) and isinstance(table_expr.expr, SqlIdentifier):
            table_name = table_expr.expr.id
            alias = table_expr.alias.id
        elif isinstance(table_expr, SqlIdentifier):
            table_name = table_expr.id
            if self.tokens.consumeKeyword("AS"):
                alias_token = self._parse_identifier()
                alias = alias_token.id
            else:
                peek = self.tokens.peek()
                if peek is not None and isinstance(peek.type, Literal) and peek.type == Literal.IDENTIFIER:
                    alias = self._parse_identifier().id
        else:
            raise ValueError("Expected table identifier")

        return SqlTable(table_name, alias)

    def _parse_expr(self) -> Optional[SqlExpr]:
        return self.parse(0)

    def _parse_identifier(self) -> SqlIdentifier:
        expr = self._parse_expr()
        if expr is None:
            raise ValueError("Expected identifier, found EOF")
        if not isinstance(expr, SqlIdentifier):
            raise ValueError(f"Expected identifier, found {expr}")
        return expr
