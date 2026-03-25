reserved = {
    "if": "IF",
    "then": "THEN",
    "else": "ELSE",
    "endif": "ENDIF",
    "program": "PROGRAM",
    "integer": "INTEGER",
    "real": "REAL",
    "character": "CHARACTER",
    "len": "LEN",
    "logical": "LOGICAL",
    "do": "DO",
    "continue": "CONTINUE",
    "goto": "GOTO",
    "print": "PRINT",
    "read": "READ",
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
    "DCOLON",

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