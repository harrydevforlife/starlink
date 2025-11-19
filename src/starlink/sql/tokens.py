from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Set, Dict

# Internal caches for Symbol helpers (module-level to avoid Enum member conflicts)
_SYMBOLS_MAP: Dict[str, "Symbol"] | None = None
_SYMBOL_START_SET: Set[str] | None = None


class TokenType:
    pass


class Literal(Enum):
    LONG = "LONG"
    DOUBLE = "DOUBLE"
    STRING = "STRING"
    IDENTIFIER = "IDENTIFIER"

    @staticmethod
    def isNumberStart(ch: str) -> bool:
        return ch.isdigit() or ch == "."

    @staticmethod
    def isIdentifierStart(ch: str) -> bool:
        return ch.isalpha() or ch == "_"

    @staticmethod
    def isIdentifierPart(ch: str) -> bool:
        return ch.isalpha() or ch.isdigit() or ch in {"_", "."}

    @staticmethod
    def isCharsStart(ch: str) -> bool:
        return ch in ("'", '"')


class Keyword(Enum):
    # common
    SCHEMA = "SCHEMA"
    DATABASE = "DATABASE"
    TABLE = "TABLE"
    COLUMN = "COLUMN"
    VIEW = "VIEW"
    INDEX = "INDEX"
    TRIGGER = "TRIGGER"
    PROCEDURE = "PROCEDURE"
    TABLESPACE = "TABLESPACE"
    FUNCTION = "FUNCTION"
    SEQUENCE = "SEQUENCE"
    CURSOR = "CURSOR"
    FROM = "FROM"
    TO = "TO"
    OF = "OF"
    IF = "IF"
    ON = "ON"
    FOR = "FOR"
    WHILE = "WHILE"
    DO = "DO"
    NO = "NO"
    BY = "BY"
    WITH = "WITH"
    WITHOUT = "WITHOUT"
    TRUE = "TRUE"
    FALSE = "FALSE"
    TEMPORARY = "TEMPORARY"
    TEMP = "TEMP"
    COMMENT = "COMMENT"

    # create
    CREATE = "CREATE"
    REPLACE = "REPLACE"
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    INSTEAD = "INSTEAD"
    EACH = "EACH"
    ROW = "ROW"
    STATEMENT = "STATEMENT"
    EXECUTE = "EXECUTE"
    BITMAP = "BITMAP"
    NOSORT = "NOSORT"
    REVERSE = "REVERSE"
    COMPILE = "COMPILE"

    # alter
    ALTER = "ALTER"
    ADD = "ADD"
    MODIFY = "MODIFY"
    RENAME = "RENAME"
    ENABLE = "ENABLE"
    DISABLE = "DISABLE"
    VALIDATE = "VALIDATE"
    USER = "USER"
    IDENTIFIED = "IDENTIFIED"

    # truncate
    TRUNCATE = "TRUNCATE"

    # drop
    DROP = "DROP"
    CASCADE = "CASCADE"

    # insert
    INSERT = "INSERT"
    INTO = "INTO"
    VALUES = "VALUES"

    # update
    UPDATE = "UPDATE"
    SET = "SET"

    # delete
    DELETE = "DELETE"

    # select
    SELECT = "SELECT"
    DISTINCT = "DISTINCT"
    AS = "AS"
    CASE = "CASE"
    WHEN = "WHEN"
    ELSE = "ELSE"
    THEN = "THEN"
    END = "END"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL = "FULL"
    INNER = "INNER"
    OUTER = "OUTER"
    CROSS = "CROSS"
    JOIN = "JOIN"
    USE = "USE"
    USING = "USING"
    NATURAL = "NATURAL"
    WHERE = "WHERE"
    ORDER = "ORDER"
    ASC = "ASC"
    DESC = "DESC"
    GROUP = "GROUP"
    HAVING = "HAVING"
    UNION = "UNION"

    # others
    DECLARE = "DECLARE"
    GRANT = "GRANT"
    FETCH = "FETCH"
    REVOKE = "REVOKE"
    CLOSE = "CLOSE"
    CAST = "CAST"
    NEW = "NEW"
    ESCAPE = "ESCAPE"
    LOCK = "LOCK"
    SOME = "SOME"
    LEAVE = "LEAVE"
    ITERATE = "ITERATE"
    REPEAT = "REPEAT"
    UNTIL = "UNTIL"
    OPEN = "OPEN"
    OUT = "OUT"
    INOUT = "INOUT"
    OVER = "OVER"
    ADVISE = "ADVISE"
    SIBLINGS = "SIBLINGS"
    LOOP = "LOOP"
    EXPLAIN = "EXPLAIN"
    DEFAULT = "DEFAULT"
    EXCEPT = "EXCEPT"
    INTERSECT = "INTERSECT"
    MINUS = "MINUS"
    PASSWORD = "PASSWORD"
    LOCAL = "LOCAL"
    GLOBAL = "GLOBAL"
    STORAGE = "STORAGE"
    DATA = "DATA"
    COALESCE = "COALESCE"

    # Types
    CHAR = "CHAR"
    CHARACTER = "CHARACTER"
    VARYING = "VARYING"
    VARCHAR = "VARCHAR"
    VARCHAR2 = "VARCHAR2"
    INTEGER = "INTEGER"
    INT = "INT"
    SMALLINT = "SMALLINT"
    DECIMAL = "DECIMAL"
    DEC = "DEC"
    NUMERIC = "NUMERIC"
    FLOAT = "FLOAT"
    REAL = "REAL"
    DOUBLE = "DOUBLE"
    PRECISION = "PRECISION"
    DATE = "DATE"
    TIME = "TIME"
    INTERVAL = "INTERVAL"
    BOOLEAN = "BOOLEAN"
    BLOB = "BLOB"

    # Conditionals
    AND = "AND"
    OR = "OR"
    XOR = "XOR"
    IS = "IS"
    NOT = "NOT"
    NULL = "NULL"
    IN = "IN"
    BETWEEN = "BETWEEN"
    LIKE = "LIKE"
    ANY = "ANY"
    ALL = "ALL"
    EXISTS = "EXISTS"

    # Functions
    AVG = "AVG"
    MAX = "MAX"
    MIN = "MIN"
    SUM = "SUM"
    COUNT = "COUNT"
    GREATEST = "GREATEST"
    LEAST = "LEAST"
    ROUND = "ROUND"
    TRUNC = "TRUNC"
    POSITION = "POSITION"
    EXTRACT = "EXTRACT"
    LENGTH = "LENGTH"
    CHAR_LENGTH = "CHAR_LENGTH"
    SUBSTRING = "SUBSTRING"
    SUBSTR = "SUBSTR"
    INSTR = "INSTR"
    INITCAP = "INITCAP"
    UPPER = "UPPER"
    LOWER = "LOWER"
    TRIM = "TRIM"
    LTRIM = "LTRIM"
    RTRIM = "RTRIM"
    BOTH = "BOTH"
    LEADING = "LEADING"
    TRAILING = "TRAILING"
    TRANSLATE = "TRANSLATE"
    CONVERT = "CONVERT"
    LPAD = "LPAD"
    RPAD = "RPAD"
    DECODE = "DECODE"
    NVL = "NVL"

    # Constraints
    CONSTRAINT = "CONSTRAINT"
    UNIQUE = "UNIQUE"
    PRIMARY = "PRIMARY"
    FOREIGN = "FOREIGN"
    KEY = "KEY"
    CHECK = "CHECK"
    REFERENCES = "REFERENCES"

    @staticmethod
    def textOf(text: str) -> Optional["Keyword"]:
        try:
            return Keyword[text.upper()]
        except KeyError:
            return None


class Symbol(Enum):
    LEFT_PAREN = "("
    RIGHT_PAREN = ")"
    LEFT_BRACE = "{"
    RIGHT_BRACE = "}"
    LEFT_BRACKET = "["
    RIGHT_BRACKET = "]"
    SEMI = ";"
    COMMA = ","
    DOT = "."
    DOUBLE_DOT = ".."
    PLUS = "+"
    SUB = "-"
    STAR = "*"
    SLASH = "/"
    QUESTION = "?"
    EQ = "="
    GT = ">"
    LT = "<"
    BANG = "!"
    TILDE = "~"
    CARET = "^"
    PERCENT = "%"
    COLON = ":"
    DOUBLE_COLON = "::"
    COLON_EQ = ":="
    LT_EQ = "<="
    GT_EQ = ">="
    LT_EQ_GT = "<=>"
    LT_GT = "<>"
    BANG_EQ = "!="
    BANG_GT = "!>"
    BANG_LT = "!<"
    AMP = "&"
    BAR = "|"
    DOUBLE_AMP = "&&"
    DOUBLE_BAR = "||"
    DOUBLE_LT = "<<"
    DOUBLE_GT = ">>"
    AT = "@"
    POUND = "#"

    @staticmethod
    def _ensure_maps() -> None:
        global _SYMBOLS_MAP, _SYMBOL_START_SET
        if _SYMBOLS_MAP is None or _SYMBOL_START_SET is None:
            _SYMBOLS_MAP = {s.value: s for s in Symbol}
            starts: Set[str] = set()
            for s in Symbol:
                if s.value:
                    starts.add(s.value[0])
            _SYMBOL_START_SET = starts

    @staticmethod
    def textOf(text: str) -> Optional["Symbol"]:
        Symbol._ensure_maps()
        return _SYMBOLS_MAP.get(text)  # type: ignore[arg-type]

    @staticmethod
    def isSymbol(ch: str) -> bool:
        Symbol._ensure_maps()
        return ch in _SYMBOL_START_SET  # type: ignore[arg-type]

    @staticmethod
    def isSymbolStart(ch: str) -> bool:
        return Symbol.isSymbol(ch)


@dataclass
class Token:
    text: str
    type: TokenType | Keyword | Symbol | Literal
    endOffset: int

    def __str__(self) -> str:
        if isinstance(self.type, Keyword):
            type_type = "Keyword"
            type_name = self.type.name
        elif isinstance(self.type, Symbol):
            type_type = "Symbol"
            type_name = self.type.name
        elif isinstance(self.type, Literal):
            type_type = "Literal"
            type_name = self.type.name
        else:
            type_type = type(self.type).__name__
            type_name = str(self.type)
        return f'Token("{self.text}", {type_type}.{type_name}, {self.endOffset})'

