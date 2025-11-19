from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from starlink.sql.sql_expr import SqlExpr


class PrattParser(ABC):
    """Pratt Top Down Operator Precedence Parser.

    See https://tdop.github.io/ for the original paper.
    """

    def parse(self, precedence: int = 0) -> Optional["SqlExpr"]:
        """Parse an expression with the given precedence level.

        Args:
            precedence: Minimum precedence level to parse (default: 0)

        Returns:
            Parsed expression or None if no expression found
        """
        expr = self.parsePrefix()
        if expr is None:
            return None

        while precedence < self.nextPrecedence():
            expr = self.parseInfix(expr, self.nextPrecedence())

        return expr

    @abstractmethod
    def nextPrecedence(self) -> int:
        """Get the precedence of the next token.

        Returns:
            Precedence value (higher = tighter binding)
        """
        pass

    @abstractmethod
    def parsePrefix(self) -> Optional["SqlExpr"]:
        """Parse the next prefix expression (e.g., unary operators, literals, identifiers).

        Returns:
            Parsed prefix expression or None
        """
        pass

    @abstractmethod
    def parseInfix(self, left: "SqlExpr", precedence: int) -> "SqlExpr":
        """Parse the next infix expression (e.g., binary operators).

        Args:
            left: Left-hand side expression already parsed
            precedence: Precedence level of the infix operator

        Returns:
            Parsed infix expression
        """
        pass
