from typing import List, Optional, Callable

from starlink.sql.tokens import Token, Literal, Keyword, Symbol, TokenType
from starlink.sql.token_stream import TokenStream


class TokenizeException(Exception):
    pass


class SqlTokenizer:
    """SQL tokenizer.

    Produces a stream of tokens from a SQL statement.
    """

    def __init__(self, sql: str):
        self.sql = sql
        self.offset = 0

    def tokenize(self) -> TokenStream:
        token = self._nextToken()
        tokens: List[Token] = []
        while token is not None:
            tokens.append(token)
            token = self._nextToken()
        return TokenStream(tokens)

    def _nextToken(self) -> Optional[Token]:
        """Get the next token from the SQL string.

        Returns None when end of string is reached.
        All token types return endOffset as the position AFTER the token (exclusive).
        """
        self.offset = self._skipWhitespace(self.offset)
        if self.offset >= len(self.sql):
            return None

        ch = self.sql[self.offset]
        token: Optional[Token] = None

        # Check token types in order of specificity:
        # 1. Identifiers (including backtick-quoted)
        # 2. Numbers (including negative numbers)
        # 3. Symbols
        # 4. String literals

        if Literal.isIdentifierStart(ch) or ch == "`":
            token = self._scanIdentifier(self.offset)
        elif Literal.isNumberStart(ch) or self._isNegativeNumber(ch):
            token = self._scanNumber(self.offset)
        elif Symbol.isSymbolStart(ch):
            token = self._scanSymbol(self.offset)
        elif Literal.isCharsStart(ch):
            token = self._scanChars(self.offset, ch)
        else:
            raise TokenizeException(f"Unexpected character '{ch}' at position {self.offset}")

        if token:
            self.offset = token.endOffset
        return token

    def _isNegativeNumber(self, ch: str) -> bool:
        """Check if '-' is the start of a negative number (not a subtraction operator)."""
        return ch == "-" and self.offset + 1 < len(self.sql) and self.sql[self.offset + 1].isdigit()

    def _skipWhitespace(self, startOffset: int) -> int:
        return self._indexOfFirst(startOffset, lambda ch: not ch.isspace())

    def _scanNumber(self, startOffset: int) -> Token:
        endOffset = (
            self._indexOfFirst(startOffset + 1, lambda ch: not ch.isdigit())
            if self.sql[startOffset] == "-"
            else self._indexOfFirst(startOffset, lambda ch: not ch.isdigit())
        )
        if endOffset == len(self.sql):
            return Token(self.sql[startOffset:endOffset], Literal.LONG, endOffset)
        isFloat = self.sql[endOffset] == "."
        if isFloat:
            endOffset = self._indexOfFirst(endOffset + 1, lambda ch: not ch.isdigit())
        lit_type = Literal.DOUBLE if isFloat else Literal.LONG
        return Token(self.sql[startOffset:endOffset], lit_type, endOffset)

    def _scanIdentifier(self, startOffset: int) -> Token:
        """Scan an identifier, which may be:
        - Backtick-quoted: `identifier`
        - Regular identifier: identifier
        - Ambiguous keyword: group/order (may be keyword or identifier)

        Returns token with endOffset as position AFTER the identifier (exclusive).
        """
        if self.sql[startOffset] == "`":
            # Backtick-quoted identifier: find closing backtick
            closingBacktickPos = self._getOffsetUntilTerminatedChar("`", startOffset + 1)
            # Extract identifier text (without backticks)
            identifierText = self.sql[startOffset + 1:closingBacktickPos]
            # endOffset is position AFTER the closing backtick
            return Token(identifierText, Literal.IDENTIFIER, closingBacktickPos + 1)

        # Regular identifier: scan until non-identifier character
        endOffset = self._indexOfFirst(startOffset, lambda ch: not Literal.isIdentifierPart(ch))
        text = self.sql[startOffset:endOffset]

        # Check for ambiguous identifiers (group/order) that might be keywords
        if self._isAmbiguousIdentifier(text):
            tokenType: TokenType = self._processAmbiguousIdentifier(endOffset, text)
            return Token(text, tokenType, endOffset)
        else:
            # Check if it's a keyword, otherwise it's an identifier
            tokenType = Keyword.textOf(text) or Literal.IDENTIFIER
            return Token(text, tokenType, endOffset)

    def _isAmbiguousIdentifier(self, text: str) -> bool:
        return text.upper() in (Keyword.ORDER.name, Keyword.GROUP.name)

    def _processAmbiguousIdentifier(self, startOffset: int, text: str) -> TokenType:
        """Process ambiguous identifier in Group By or Order By.
        """
        skipWhitespaceOffset = self._skipWhitespace(startOffset)
        if (
            skipWhitespaceOffset != len(self.sql)
            and self.sql[skipWhitespaceOffset:skipWhitespaceOffset + 2].upper() == "BY"
        ):
            kw = Keyword.textOf(text)
            assert kw is not None
            return kw
        return Literal.IDENTIFIER

    def _getOffsetUntilTerminatedChar(self, terminatedChar: str, startOffset: int) -> int:
        idx = self.sql.find(terminatedChar, startOffset)
        if idx != -1:
            return idx
        raise TokenizeException(f"Must contain {terminatedChar} in remain sql[{startOffset} .. end]")

    def _scanSymbol(self, startOffset: int) -> Token:
        """Scan symbol.
        Return Symbol token.
        """
        endOffset = self._indexOfFirst(startOffset, lambda ch: not Symbol.isSymbol(ch))
        text = self.sql[self.offset:endOffset]
        symbol = Symbol.textOf(text)
        while symbol is None and endOffset > startOffset:
            endOffset -= 1
            text = self.sql[self.offset:endOffset]
            symbol = Symbol.textOf(text)
        if symbol is None:
            raise TokenizeException(f"{text} Must be a Symbol!")
        return Token(text, symbol, endOffset)

    def _scanChars(self, startOffset: int, terminatedChar: str) -> Token:
        """Scan chars like 'abc' or "abc"."""
        endOffset = self._getOffsetUntilTerminatedChar(terminatedChar, startOffset + 1)
        return Token(self.sql[startOffset + 1:endOffset], Literal.STRING, endOffset + 1)

    def _indexOfFirst(self, startIndex: int, predicate: Callable[[str], bool]) -> int:
        for index in range(startIndex, len(self.sql)):
            if predicate(self.sql[index]):
                return index
        return len(self.sql)
