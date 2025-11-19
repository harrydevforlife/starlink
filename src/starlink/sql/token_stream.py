import logging
from typing import List, Optional

from starlink.sql.tokens import Token, Keyword, TokenType


class TokenStream:
    """Token stream.
    A token stream is a sequence of tokens. It is used to tokenize the SQL statement.
    """

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.i = 0
        self.logger = logging.getLogger(self.__class__.__name__)

    def peek(self) -> Optional[Token]:
        if self.i < len(self.tokens):
            return self.tokens[self.i]
        else:
            return None

    def next(self) -> Optional[Token]:
        if self.i < len(self.tokens):
            t = self.tokens[self.i]
            self.i += 1
            return t
        else:
            return None

    def consumeKeywords(self, s: List[str]) -> bool:
        save = self.i
        for keyword in s:
            if not self.consumeKeyword(keyword):
                self.i = save
                return False
        return True

    def consumeKeyword(self, s: str) -> bool:
        peek = self.peek()
        self.logger.debug("consumeKeyword('%s') next token is %s", s, peek)
        if peek is not None and isinstance(peek.type, Keyword) and peek.text == s:
            self.i += 1
            self.logger.debug("consumeKeyword() returning true")
            return True
        else:
            self.logger.debug("consumeKeyword() returning false")
            return False

    def consumeTokenType(self, t: TokenType) -> bool:
        peek = self.peek()
        if peek is not None and peek.type == t:
            self.i += 1
            return True
        else:
            return False

    def __str__(self) -> str:
        parts = []
        for index, token in enumerate(self.tokens):
            if index == self.i:
                parts.append(f"*{token}")
            else:
                parts.append(str(token))
        return " ".join(parts)
