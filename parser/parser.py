import ply.yacc as yacc
from lexer.lexer import tokens

def p_program(p):
    "program : statements"
    p[0] = p[1]

def p_statements_many(p):
    "statements : statements statement"
    p[0] = p[1] + [p[2]]

def p_statements_one(p):
    "statements : statement"
    p[0] = [p[1]]

def p_statement_assign(p):
    "statement : IDEN EQ expr"
    p[0] = ("assign", p[1], p[3])

def p_expr_binop(p):
    """
    expr : expr ADD expr
         | expr SUB expr
         | expr MUL expr
         | expr DIV expr
         | expr POW expr
    """
    p[0] = ("binop", p[2], p[1], p[3])

def p_expr_int(p):
    "expr : INT"
    p[0] = ("int", p[1])

def p_expr_float(p):
    "expr : FLOAT"
    p[0] = ("float", p[1])

def p_expr_string(p):
    "expr : STRING"
    p[0] = ("string", p[1])

def p_expr_id(p):
    "expr : IDEN"
    p[0] = ("id", p[1])

def p_expr_group(p):
    "expr : '(' expr ')'"
    p[0] = p[2]

precedence = (
    ('left', 'ADD', 'SUB'),
    ('left', 'MUL', 'DIV'),
    ('right', 'POW'),
)

def p_error(p):
    if p:
        print("Syntax error at", p.value)
    else:
        print("Syntax error at EOF")



parser = yacc.yacc()

def parse(text):
    return parser.parse(text)