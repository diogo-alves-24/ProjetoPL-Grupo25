reserved = {
    "if": "IF",
    "then": "THEN",
    "else": "ELSE",
    "endif": "ENDIF",
    "program": "PROGRAM",
    "integer": "INTEGER",
    "real": "REAL",
    "character": "CHARACTER",
    "logical": "LOGICAL",
    "do": "DO",
    "continue": "CONTINUE",
    "goto": "GOTO",
    "print": "PRINT",
    "read": "READ",
    "function": "FUNCTION",
    "return": "RETURN",
    "end": "END"
}

tokens = [
    "INT",
    "FLOAT",
    "STRING",
    "BOOL",
    "ADD",
    "SUB",
    "MUL",
    "DIV",
    "POW",
    "EQ",
    "IDEN",

    # relacionais
    "EQEQ",
    "NE",
    "LT",
    "LE",
    "GT",
    "GE",

    # lógicos
    "AND",
    "OR",
    "NOT"
] + list(reserved.values())

literals = [
    '(',
    ')',
    ',',
    ':'
]