import ply.yacc as yacc

from lexer.tokens import tokens
from lexer.lexer import lexer


precedence = (
    ("left", "OR"),
    ("left", "AND"),
    ("right", "NOT"),
    ("nonassoc", "EQEQ", "NE", "LT", "LE", "GT", "GE"),
    ("left", "ADD", "SUB"),
    ("left", "MUL", "DIV"),
    ("right", "POW"),
    ("right", "UMINUS", "UPLUS"),
)


# Unidade de compilação

def p_compilation_unit(p):
    "compilation_unit : main_program subprogram_list_opt"
    p[0] = ("file", p[1], p[2])


def p_main_program(p):
    "main_program : PROGRAM IDEN body END"
    p[0] = ("program", p[2], p[3])


def p_subprogram_list_opt_empty(p):
    "subprogram_list_opt : empty"
    p[0] = []


def p_subprogram_list_opt_nonempty(p):
    "subprogram_list_opt : subprogram_list"
    p[0] = p[1]


def p_subprogram_list_one(p):
    "subprogram_list : subprogram"
    p[0] = [p[1]]


def p_subprogram_list_many(p):
    "subprogram_list : subprogram_list subprogram"
    p[0] = p[1] + [p[2]]


def p_subprogram(p):
    "subprogram : function_definition"
    p[0] = p[1]


# Funções

def p_function_definition(p):
    "function_definition : function_type FUNCTION IDEN '(' param_list_opt ')' body END"
    p[0] = ("function", p[1], p[3], p[5], p[7])


def p_function_type_integer(p):
    "function_type : INTEGER"
    p[0] = "INTEGER"


def p_function_type_real(p):
    "function_type : REAL"
    p[0] = "REAL"


def p_function_type_logical(p):
    "function_type : LOGICAL"
    p[0] = "LOGICAL"


def p_function_type_character(p):
    "function_type : CHARACTER"
    p[0] = "CHARACTER"


def p_param_list_opt_empty(p):
    "param_list_opt : empty"
    p[0] = []


def p_param_list_opt_values(p):
    "param_list_opt : id_list"
    p[0] = p[1]


# Corpo

def p_body_empty(p):
    "body : empty"
    p[0] = []


def p_body_one(p):
    "body : item"
    p[0] = [p[1]]


def p_body_many(p):
    "body : body item"
    p[0] = p[1] + [p[2]]


def p_item(p):
    """
    item : declaration
         | statement
    """
    p[0] = p[1]


# Declarações

def p_declaration_integer(p):
    "declaration : INTEGER decl_item_list"
    p[0] = ("declaration", "INTEGER", p[2])


def p_declaration_real(p):
    "declaration : REAL decl_item_list"
    p[0] = ("declaration", "REAL", p[2])


def p_declaration_logical(p):
    "declaration : LOGICAL decl_item_list"
    p[0] = ("declaration", "LOGICAL", p[2])


def p_declaration_character_simple(p):
    "declaration : CHARACTER decl_item_list"
    p[0] = ("declaration", "CHARACTER", p[2])


def p_declaration_character_star_len(p):
    "declaration : CHARACTER MUL INT decl_item_list"
    p[0] = ("declaration_char", p[3], p[4])


def p_decl_item_list_one(p):
    "decl_item_list : decl_item"
    p[0] = [p[1]]


def p_decl_item_list_many(p):
    "decl_item_list : decl_item_list ',' decl_item"
    p[0] = p[1] + [p[3]]


def p_decl_item_scalar(p):
    "decl_item : IDEN"
    p[0] = ("var", p[1])


def p_decl_item_array(p):
    "decl_item : IDEN '(' int_list ')'"
    p[0] = ("array_decl", p[1], p[3])


def p_int_list_one(p):
    "int_list : INT"
    p[0] = [p[1]]


def p_int_list_many(p):
    "int_list : int_list ',' INT"
    p[0] = p[1] + [p[3]]


def p_id_list_one(p):
    "id_list : IDEN"
    p[0] = [p[1]]


def p_id_list_many(p):
    "id_list : id_list ',' IDEN"
    p[0] = p[1] + [p[3]]


# Statements

def p_statement(p):
    """
    statement : assignment
              | print_stmt
              | read_stmt
              | if_stmt
              | do_stmt
              | goto_stmt
              | continue_stmt
              | return_stmt
              | labeled_stmt
    """
    p[0] = p[1]


def p_labeled_stmt(p):
    "labeled_stmt : INT statement"
    p[0] = ("labeled", p[1], p[2])


def p_assignment(p):
    "assignment : designator EQ expr"
    p[0] = ("assignment", p[1], p[3])


def p_print_stmt(p):
    "print_stmt : PRINT MUL ',' expr_list"
    p[0] = ("print", p[4])


def p_read_stmt(p):
    "read_stmt : READ MUL ',' designator_list"
    p[0] = ("read", p[4])


def p_goto_stmt(p):
    "goto_stmt : GOTO INT"
    p[0] = ("goto", p[2])


def p_continue_stmt(p):
    "continue_stmt : CONTINUE"
    p[0] = ("continue",)


def p_return_stmt(p):
    "return_stmt : RETURN"
    p[0] = ("return",)


# IF ... THEN ... ELSE ... ENDIF

def p_if_stmt(p):
    "if_stmt : IF '(' expr ')' THEN stmt_block ENDIF"
    p[0] = ("if", p[3], p[6], [])


def p_if_else_stmt(p):
    "if_stmt : IF '(' expr ')' THEN stmt_block ELSE stmt_block ENDIF"
    p[0] = ("if", p[3], p[6], p[8])


def p_stmt_block_one(p):
    "stmt_block : statement"
    p[0] = [p[1]]


def p_stmt_block_many(p):
    "stmt_block : stmt_block statement"
    p[0] = p[1] + [p[2]]


# DO com label

def p_do_stmt_no_step(p):
    "do_stmt : DO INT IDEN EQ expr ',' expr"
    p[0] = ("do", p[2], p[3], p[5], p[7], ("int", 1))


def p_do_stmt_with_step(p):
    "do_stmt : DO INT IDEN EQ expr ',' expr ',' expr"
    p[0] = ("do", p[2], p[3], p[5], p[7], p[9])


# Designators

def p_designator_id(p):
    "designator : IDEN"
    p[0] = ("id", p[1])


def p_designator_apply(p):
    "designator : IDEN '(' expr_list ')'"
    p[0] = ("apply", p[1], p[3])


def p_designator_list_one(p):
    "designator_list : designator"
    p[0] = [p[1]]


def p_designator_list_many(p):
    "designator_list : designator_list ',' designator"
    p[0] = p[1] + [p[3]]


# Listas de expressões

def p_expr_list_one(p):
    "expr_list : expr"
    p[0] = [p[1]]


def p_expr_list_many(p):
    "expr_list : expr_list ',' expr"
    p[0] = p[1] + [p[3]]


# Expressões

def p_expr_binop(p):
    """
    expr : expr ADD expr
         | expr SUB expr
         | expr MUL expr
         | expr DIV expr
         | expr POW expr
         | expr EQEQ expr
         | expr NE expr
         | expr LT expr
         | expr LE expr
         | expr GT expr
         | expr GE expr
         | expr AND expr
         | expr OR expr
    """
    p[0] = ("binop", p[2], p[1], p[3])


def p_expr_not(p):
    "expr : NOT expr"
    p[0] = ("unaryop", p[1], p[2])


def p_expr_uminus(p):
    "expr : SUB expr %prec UMINUS"
    p[0] = ("unaryop", "-", p[2])


def p_expr_uplus(p):
    "expr : ADD expr %prec UPLUS"
    p[0] = ("unaryop", "+", p[2])


def p_expr_group(p):
    "expr : '(' expr ')'"
    p[0] = p[2]


def p_expr_int(p):
    "expr : INT"
    p[0] = ("int", p[1])


def p_expr_float(p):
    "expr : FLOAT"
    p[0] = ("float", p[1])


def p_expr_string(p):
    "expr : STRING"
    p[0] = ("string", p[1])


def p_expr_bool(p):
    "expr : BOOL"
    p[0] = ("bool", p[1])


def p_expr_designator(p):
    "expr : designator"
    p[0] = p[1]


# Auxiliar

def p_empty(p):
    "empty :"
    pass


def p_error(p):
    if p:
        print(f"Syntax error at token {p.type} ({p.value!r})")
    else:
        print("Syntax error at EOF")


parser = yacc.yacc(start="compilation_unit")


def parse(text):
    lexer.lineno = 1
    return parser.parse(text, lexer=lexer)