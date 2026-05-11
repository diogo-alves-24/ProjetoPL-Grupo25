import ply.lex as lex
from .tokens import tokens, literals, reserved

# ---------------------------------------------------------------------------
# Operadores aritméticos
#
# t_POW e t_MUL são funções em vez de strings para garantir que o PLY os
# testa nesta ordem, independentemente da versão. Com strings simples o PLY
# ordena por comprimento decrescente automaticamente — mas torná-lo explícito
# elimina qualquer ambiguidade futura se o ficheiro for reorganizado.
# ---------------------------------------------------------------------------

def t_POW(t):
    r"\*\*"
    return t

def t_MUL(t):
    r"\*"
    return t

t_ADD = r"\+"
t_SUB = r"-"
t_DIV = r"/"
t_EQ  = r"="

# ---------------------------------------------------------------------------
# Operadores relacionais e lógicos (ponto obrigatório, case-insensitive via
# regex explícito — Fortran aceita .lt. e .LT. igualmente)
# ---------------------------------------------------------------------------

def t_EQEQ(t): r"\.EQ\.";  t.value = t.value.upper(); return t  # noqa: E704
def t_NE(t):   r"\.NE\.";  t.value = t.value.upper(); return t  # noqa: E704
def t_LE(t):   r"\.LE\.";  t.value = t.value.upper(); return t  # noqa: E704
def t_LT(t):   r"\.LT\.";  t.value = t.value.upper(); return t  # noqa: E704
def t_GE(t):   r"\.GE\.";  t.value = t.value.upper(); return t  # noqa: E704
def t_GT(t):   r"\.GT\.";  t.value = t.value.upper(); return t  # noqa: E704
def t_AND(t):  r"\.AND\."; t.value = t.value.upper(); return t  # noqa: E704
def t_OR(t):   r"\.OR\.";  t.value = t.value.upper(); return t  # noqa: E704
def t_NOT(t):  r"\.NOT\."; t.value = t.value.upper(); return t  # noqa: E704

# ---------------------------------------------------------------------------
# Literais numéricos
#
# FLOAT tem de vir antes de INT para que "1.5" seja capturado inteiro e não
# como INT(1) + DIV + FLOAT(.5).
# Suporta notação científica Fortran: 1.5E3, 2.0D-4, .5e+2, etc.
# ---------------------------------------------------------------------------

def t_FLOAT(t):
    r"(\d+\.\d*|\.\d+)([EeDd][+-]?\d+)?"
    # Normaliza 'D'/'d' (double precision Fortran) para 'E' do Python
    t.value = float(t.value.replace('D', 'E').replace('d', 'e'))
    return t

def t_INT(t):
    r"\d+"
    t.value = int(t.value)
    # Se estamos no início da linha lógica, este inteiro é um LABEL de
    # statement (ex: "100 CONTINUE"). O flag at_line_start é gerido pelo
    # handler t_newline e pelo preprocess.
    if getattr(t.lexer, 'at_line_start', False):
        t.type = "LABEL"
    t.lexer.at_line_start = False
    return t

# ---------------------------------------------------------------------------
# String: sequência entre plicas. Fortran 77 não suporta '' como plica
# escapada — deixamos isso como extensão futura se necessário.
# ---------------------------------------------------------------------------

def t_STRING(t):
    r"'[^'\n]*'"
    t.value = t.value[1:-1]   # remove delimitadores
    return t

# ---------------------------------------------------------------------------
# Booleano: .TRUE. / .FALSE. (case-insensitive)
# ---------------------------------------------------------------------------

def t_BOOL(t):
    r"\.(TRUE|FALSE)\."
    t.value = t.value.upper() == ".TRUE."
    return t

# ---------------------------------------------------------------------------
# Comentários com !
# Comentários de coluna 1 (C/*) são removidos pelo preprocess() abaixo.
# ---------------------------------------------------------------------------

def t_COMMENT(t):
    r"!.*"
    pass   # descarta; não devolve token

# ---------------------------------------------------------------------------
# Identificadores e palavras reservadas
# Fortran 77 é case-insensitive: normaliza para lowercase no lookup.
# O valor original é preservado para mensagens de erro mais legíveis.
# ---------------------------------------------------------------------------

def t_IDEN(t):
    r"[A-Za-z][A-Za-z0-9_]*"
    t.type = reserved.get(t.value.lower(), "IDEN")
    t.lexer.at_line_start = False
    return t

# ---------------------------------------------------------------------------
# Nova linha: avança o contador de linhas e sinaliza início de linha para o
# mecanismo de deteção de LABEL.
# ---------------------------------------------------------------------------

def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)
    t.lexer.at_line_start = True

# ---------------------------------------------------------------------------
# Espaços e tabs são ignorados.
# Nota: NÃO resetamos at_line_start aqui — o label pode aparecer com espaços
# à esquerda na coluna 1-5 após o preprocess ("  100 CONTINUE").
# ---------------------------------------------------------------------------

t_ignore = " \t\r"

# ---------------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------------

def t_error(t):
    print(f"Linha {t.lexer.lineno}: símbolo inválido {t.value[0]!r}")
    t.lexer.skip(1)

# ---------------------------------------------------------------------------
# Construção do lexer
# ---------------------------------------------------------------------------

lexer = lex.lex()
lexer.at_line_start = True   # início do ficheiro = início de linha


# ===========================================================================
# Pré-processamento para Fortran 77 formato fixo
#
# Resolve ANTES de entregar o texto ao PLY:
#   col 1    : C, c ou * → linha de comentário (descarta)
#   col 6    : carácter ≠ ' ' e ≠ '0' → continuação da linha anterior
#   cols 1-5 : label de statement (inteiro)
#   cols 7-72: código efectivo
#
# O resultado é texto "livre" onde:
#   - Labels ficam como inteiros no início da linha → t_INT emite LABEL
#   - Continuações são unidas numa só linha lógica
#   - Comentários são linhas vazias (preserva numeração para mensagens de erro)
# ===========================================================================

def preprocess(source: str) -> str:
    """
    Normaliza Fortran 77 formato fixo para um stream compatível com o lexer.
    Suporta formato livre (sem colunas fixas) se nenhuma linha tiver
    conteúdo na col 6 — o preprocess torna-se um no-op nesse caso.
    """
    lines = source.splitlines()
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]
        padded = line.ljust(72)
        col1   = padded[0].upper()

        # --- Linha vazia ou comentário ---
        if line.strip() == '' or col1 in ('C', '*'):
            result.append('')
            i += 1
            continue

        # --- Código: extrai corpo (cols 7-72) ---
        stmt = padded[6:72].rstrip()

        # --- Recolhe linhas de continuação ---
        while i + 1 < len(lines):
            nxt     = lines[i + 1].ljust(72)
            nxt_c1  = nxt[0].upper()

            # Comentário intercalado entre continuações: consome e ignora
            if nxt.strip() == '' or nxt_c1 in ('C', '*'):
                result.append('')
                i += 1
                continue

            cont = nxt[5]   # coluna 6 (índice 5)
            if cont not in (' ', '0'):
                stmt += ' ' + nxt[6:72].rstrip()
                result.append('')   # linha vazia preserva numeração
                i += 1
            else:
                break   # próxima linha é um novo statement

        # --- Reconstrói com label à frente (se existir) ---
        label_part = padded[0:5].strip()
        if label_part.isdigit():
            result.append(f"{label_part} {stmt}")
        else:
            result.append(stmt)

        i += 1

    return '\n'.join(result)


# ---------------------------------------------------------------------------
# Ponto de entrada para debug / testes
# ---------------------------------------------------------------------------

def tokenize(text: str, use_preprocess: bool = True):
    src = preprocess(text) if use_preprocess else text
    lexer.lineno = 1
    lexer.at_line_start = True
    lexer.input(src)
    for tok in lexer:
        print(tok)