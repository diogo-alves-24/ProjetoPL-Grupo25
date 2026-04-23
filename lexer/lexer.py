import ply.lex as lex
from .tokens import tokens, literals, reserved

t_ADD = r"\+"
t_SUB = r"-"
t_POW = r"\*\*"
t_MUL = r"\*"
t_DIV = r"/"
t_EQ = r"="

t_EQEQ = r"\.EQ\."
t_NE = r"\.NE\."
t_LE = r"\.LE\."
t_LT = r"\.LT\."
t_GE = r"\.GE\."
t_GT = r"\.GT\."

t_AND = r"\.AND\."
t_OR  = r"\.OR\."
t_NOT = r"\.NOT\."

t_ignore = " \t"

def t_FLOAT(t):
    r"(\d+\.\d*|\.\d+)"
    t.value = float(t.value)
    return t

def t_INT(t):
    r"\d+"
    t.value = int(t.value)
    return t

def t_STRING(t):
    r"'[^']*'"
    t.value = t.value[1:-1]
    return t

def t_BOOL(t):
    r"\.(TRUE|FALSE)\."
    t.value = True if t.value.upper() == ".TRUE." else False
    return t

def t_COMMENT(t):
    r"!.*"
    pass

def t_IDEN(t):
    r"[A-Za-z][A-Za-z0-9]*"
    t.type = reserved.get(t.value.lower(), "IDEN")
    return t

def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)

def t_error(t):
    print("Invalid symbol:", t.value[0])
    t.lexer.skip(1)

lexer = lex.lex()

def tokenize(text):
    lexer.input(text)
    for tok in lexer:
        print(tok)