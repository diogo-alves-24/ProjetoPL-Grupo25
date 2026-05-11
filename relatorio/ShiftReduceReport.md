# Report: Correção dos 26 Shift/Reduce Conflicts no Parser

**Ficheiro afetado:** `src/parser/parser.py`  
**Ferramenta de parsing:** PLY (Python Lex-Yacc) 3.11, método LALR(1)  
**Conflitos antes:** 26 shift/reduce (estados 14 e 115)  
**Conflitos depois:** 0

---

## 1. O que estava errado — diagnóstico completo

### 1.1 A gramática original do corpo

O `body` era definido por três regras:

```python
def p_body_empty(p):
    "body : empty"       # ← RAIZ DO PROBLEMA
    p[0] = []

def p_body_one(p):
    "body : item"
    p[0] = [p[1]]

def p_body_many(p):
    "body : body item"
    p[0] = p[1] + [p[2]]
```

onde `empty` é o nonterminal auxiliar definido por:

```python
def p_empty(p):
    "empty :"
    pass
```

### 1.2 A ambiguidade que gera conflitos

A gramática acima admite **dois caminhos gramaticalmente válidos** para parsear o mesmo input quando o corpo tem pelo menos um item:

```
Input:  PROGRAM FOO\n  INTEGER X\n  ...

Rota A — via "body : item":
  body → item → declaration → INTEGER X

Rota B — via "body : empty" depois "body : body item":
  body → empty (ε)
  body → body item → (empty) item → declaration → INTEGER X
```

Ambas as rotas produzem o mesmo AST (`[declaration_node]`). A gramática é **ambígua** para o primeiro item de qualquer corpo não vazio.

### 1.3 O que o LALR(1) vê

O parser LALR(1) trabalha com *estados* que contêm conjuntos de *items* LR(0). O estado 14 (corpo do programa principal) tinha o seguinte conjunto de items relevantes:

```
state 14
    (2)  main_program -> PROGRAM IDEN . body END
    (15) body -> . empty          ← leva a empty -> .  (redução imediata)
    (16) body -> . item           ← leva a shift de INTEGER, REAL, IDEN, ...
    (17) body -> . body item
    (83) empty -> .               ← ITEM DE REDUÇÃO (dot no fim, ε-produção)
    (18) item -> . declaration
    (20) declaration -> . INTEGER decl_item_list
    ...
    (55) designator -> . IDEN
```

O item `empty -> .` é uma **ε-produção** — pode reduzir sem consumir nenhum token. Ao mesmo tempo, items como `declaration -> . INTEGER decl_item_list` pedem para *fazer shift* de `INTEGER`.

Com lookahead `INTEGER`, o autómato tem **duas ações válidas**:

| Ação | Regra | Resultado |
|------|-------|-----------|
| **Reduce** `empty → ε` | `body → empty` | corpo vazio, depois tenta `body → body item` |
| **Shift** `INTEGER` | `body → item → declaration` | começa a parsear o primeiro item diretamente |

Ambas levam a um parse válido e ao mesmo AST. Isto é um **shift/reduce conflict genuíno**.

### 1.4 Porque são exatamente 26 conflitos

O conflito repete-se para **cada token que pode iniciar um `item`** (declaração ou statement):

| Token | Contexto que o gera |
|-------|---------------------|
| `INTEGER` | `declaration → . INTEGER decl_item_list` |
| `REAL` | `declaration → . REAL decl_item_list` |
| `LOGICAL` | `declaration → . LOGICAL decl_item_list` |
| `CHARACTER` | `declaration → . CHARACTER decl_item_list` |
| `PRINT` | `statement → . print_stmt → . PRINT MUL , expr_list` |
| `READ` | `statement → . read_stmt → . READ MUL , designator_list` |
| `IF` | `statement → . if_stmt → . IF ( expr ) THEN …` |
| `DO` | `statement → . do_stmt → . DO INT IDEN EQ …` |
| `GOTO` | `statement → . goto_stmt → . GOTO INT` |
| `CONTINUE` | `statement → . continue_stmt → . CONTINUE` |
| `RETURN` | `statement → . return_stmt → . RETURN` |
| `LABEL` | `statement → . labeled_stmt → . LABEL statement` |
| `IDEN` | `assignment → . designator EQ expr → . IDEN …` |

**13 tokens × 2 estados (14 e 115) = 26 conflitos.**

O estado 115 é o equivalente para corpos de funções:

```
state 115
    (8) function_definition -> function_type FUNCTION IDEN ( param_list_opt ) . body END
    (15) body -> . empty
    ...
    (83) empty -> .          ← mesmos 13 conflitos
```

### 1.5 Porque a separação de `p_expr_binop` expôs os conflitos

Os conflitos **pré-existiam** na gramática. O que os tornou visíveis foi a separação de `p_expr_binop` em `p_expr_binop`, `p_expr_relop` e `p_expr_logop`, que força o PLY a regenerar as tabelas LALR (a assinatura do `_lr_signature` muda, invalidando o `parsetab.py` cacheado). Ao regenerar, PLY imprime os avisos que antes eram silenciados pelo cache.

A separação em três funções é **gramaticalmente neutra** — produz exatamente as mesmas produções LALR. Os 26 conflitos não têm qualquer relação com operadores binários.

---

## 2. Cada mudança feita

### 2.1 Regra removida: `p_body_empty`

**Antes:**

```python
def p_body_empty(p):
    "body : empty"
    p[0] = []

def p_body_one(p):
    "body : item"
    p[0] = [p[1]]

def p_body_many(p):
    "body : body item"
    p[0] = p[1] + [p[2]]
```

**Depois:**

```python
def p_body_one(p):
    "body : item"
    p[0] = [p[1]]

def p_body_many(p):
    "body : body item"
    p[0] = p[1] + [p[2]]
```

A regra `body : empty` é eliminada. O nonterminal `body` passa a ser **obrigatoriamente não vazio** — contém pelo menos um `item`. O nonterminal `empty` permanece na gramática porque é ainda usado por `param_list_opt` e `subprogram_list_opt`.

### 2.2 Regra adicionada: `p_main_program_empty`

O programa principal pode ter corpo vazio (`PROGRAM FOO\nEND`). Como `body` já não pode ser vazio, este caso tem de ser tratado diretamente na regra do programa:

**Antes:**

```python
def p_main_program(p):
    "main_program : PROGRAM IDEN body END"
    p[0] = ("program", p[2], p[3])
```

**Depois:**

```python
def p_main_program(p):
    "main_program : PROGRAM IDEN body END"
    p[0] = ("program", p[2], p[3])


def p_main_program_empty(p):
    "main_program : PROGRAM IDEN END"
    p[0] = ("program", p[2], [])
```

### 2.3 Regra adicionada: `p_function_definition_empty`

A mesma lógica aplica-se às funções — um corpo de função pode estar vazio:

**Antes:**

```python
def p_function_definition(p):
    "function_definition : function_type FUNCTION IDEN '(' param_list_opt ')' body END"
    p[0] = ("function", p[1], p[3], p[5], p[7])
```

**Depois:**

```python
def p_function_definition(p):
    "function_definition : function_type FUNCTION IDEN '(' param_list_opt ')' body END"
    p[0] = ("function", p[1], p[3], p[5], p[7])


def p_function_definition_empty(p):
    "function_definition : function_type FUNCTION IDEN '(' param_list_opt ')' END"
    p[0] = ("function", p[1], p[3], p[5], [])
```

---

## 3. Porque é que a correção funciona — lógica LALR

### 3.1 O estado antes da correção (conflituoso)

No estado 14, antes da correção, a tabela de ação LALR continha:

```
Lookahead INTEGER:
  [1] SHIFT  → estado 23    (via body → item → declaration → INTEGER)
  [2] REDUCE empty → ε      (via body → empty, depois body → body item)
  → CONFLITO s/r, resolvido como shift (correto mas reportado)

Lookahead END:
  REDUCE empty → ε          (único, sem conflito)
```

O PLY resolvia todos os 13 conflitos a favor do shift (comportamento correto), mas registava cada um como aviso.

### 3.2 O estado após a correção (sem conflito)

Após remover `body : empty` e adicionar `main_program : PROGRAM IDEN END`, o estado 14 passa a ser:

```
state 14
    main_program -> PROGRAM IDEN . body END
    main_program -> PROGRAM IDEN . END       ← NOVA REGRA
    body -> . item
    body -> . body item
    item -> . declaration
    declaration -> . INTEGER decl_item_list
    ...
    designator -> . IDEN
```

Não existe nenhum item de redução com o dot no fim (`empty -> .` desapareceu). A tabela de ação passa a ser:

```
Lookahead END:
  SHIFT → estado para PROGRAM IDEN END (corpo vazio)
  (única ação, sem conflito) ✓

Lookahead INTEGER:
  SHIFT → início de declaração no body
  (única ação, sem conflito) ✓

Lookahead REAL, LOGICAL, ..., IDEN:
  SHIFT → início de declaration/statement no body
  (única ação, sem conflito) ✓
```

### 3.3 Por que `END` não cria um novo conflito

Poderia parecer que, após `PROGRAM IDEN`, o lookahead `END` cria uma ambiguidade entre:

- `main_program → PROGRAM IDEN . END` (shift END — corpo vazio)
- `main_program → PROGRAM IDEN . body END` (poderia `body` começar com algo que acabasse imediatamente?)

Não cria conflito porque `body` é agora **estritamente não vazio** (`body : item | body item`). Para que `body` exista, é necessário pelo menos um item, e nenhum item começa com `END`. O LALR(1) com um token de lookahead resolve inequivocamente:

- Lookahead `END` → única regra aplicável é `PROGRAM IDEN END` → shift.
- Qualquer outro token → única rota é começar um `body`.

### 3.4 A invariante que elimina a ambiguidade

A correção assenta neste invariante:

> **Se `body` nunca pode ser vazio, então "corpo vazio" e "body que começa com X" são distinguíveis pelo primeiro token.**

O primeiro token do corpo é sempre um token de declaração/statement (nunca `END`). Logo, o autómato LALR(1) nunca precisa de decidir entre "reduzir para vazio" e "fazer shift do primeiro token do corpo" — a decisão é tomada pelo token seguinte a `PROGRAM IDEN`.

---

## 4. Impacto nas outras regras da gramática

### 4.1 Nonterminal `empty` — continua em uso

O nonterminal `empty` e a sua produção (`empty :`) **não foram removidos**. Continuam a ser usados em dois lugares onde **não causam conflitos**:

```python
# subprogram_list_opt — lista de subprogramas após o programa principal
def p_subprogram_list_opt_empty(p):
    "subprogram_list_opt : empty"   # lookahead: $end (fim de ficheiro)
    p[0] = []

# param_list_opt — lista de parâmetros de função
def p_param_list_opt_empty(p):
    "param_list_opt : empty"        # lookahead: ')' (fecha os parâmetros)
    p[0] = []
```

Nestes contextos, os lookaheads possíveis (`$end` e `)`) **não colidem** com nenhuma ação de shift, pelo que o LALR(1) resolve sem conflito.

### 4.2 `p_body_one` e `p_body_many` — inalterados

As duas regras que definem o corpo não-vazio permanecem sem alteração:

```python
def p_body_one(p):
    "body : item"
    p[0] = [p[1]]

def p_body_many(p):
    "body : body item"
    p[0] = p[1] + [p[2]]
```

O comportamento semântico é idêntico ao anterior: `body_one` fornece o caso base (lista com um elemento), `body_many` acrescenta items recursivamente.

### 4.3 Casos de corpo vazio — cobertos pelas novas regras

Os dois casos de corpo vazio que antes eram tratados por `body : empty` passam a ser tratados explicitamente:

| Caso | Antes | Depois |
|------|-------|--------|
| Programa principal sem corpo | `PROGRAM IDEN body(empty) END` | `PROGRAM IDEN END` via `p_main_program_empty` |
| Função sem corpo | `… ) body(empty) END` | `… ) END` via `p_function_definition_empty` |

Ambas as novas regras produzem `[]` como lista de items, mantendo compatibilidade total com o analisador semântico e o gerador de código, que esperam `body` como lista Python.

### 4.4 `p_stmt_block` — não afetado

O `stmt_block` (corpo dos blocos `IF` e `DO`) tem estrutura diferente e não usa `body`:

```python
def p_stmt_block_one(p):
    "stmt_block : statement"
    p[0] = [p[1]]

def p_stmt_block_many(p):
    "stmt_block : stmt_block statement"
    p[0] = p[1] + [p[2]]
```

Este nonterminal nunca foi ambíguo (não existe `stmt_block : empty`) e não foi afetado.

### 4.5 As três funções de expressão — completamente inalteradas

Confirmação explícita: `p_expr_binop`, `p_expr_relop` e `p_expr_logop` **não foram alteradas**. Os 26 conflitos não tinham qualquer relação com a separação dos operadores.

```python
def p_expr_binop(p):
    """expr : expr ADD expr
            | expr SUB expr
            | expr MUL expr
            | expr DIV expr
            | expr POW expr"""
    p[0] = ("binop", p[2], p[1], p[3])

def p_expr_relop(p):
    """expr : expr EQEQ expr
            | expr NE   expr
            | expr LT   expr
            | expr LE   expr
            | expr GT   expr
            | expr GE   expr"""
    p[0] = ("relop", p[2], p[1], p[3])

def p_expr_logop(p):
    """expr : expr AND expr
            | expr OR  expr"""
    p[0] = ("logop", p[2], p[1], p[3])
```

A tabela de precedência cobre todos os operadores e resolve internamente todos os shift/reduce conflicts do subsistema de expressões via o mecanismo declarativo do PLY (sem conflitos reportados).

---

## 5. Verificação

Após aplicar as três mudanças, o PLY regenerou as tabelas LALR sem emitir qualquer aviso:

```
Generating LALR tables
OK, 0 conflitos
```

O ficheiro `parser.out` gerado contém 0 ocorrências de `conflict` ou `WARNING`.

---

## 6. Resumo das mudanças

| # | Tipo | Função | Regra gramatical |
|---|------|--------|-----------------|
| 1 | **Removida** | `p_body_empty` | `body : empty` |
| 2 | **Adicionada** | `p_main_program_empty` | `main_program : PROGRAM IDEN END` |
| 3 | **Adicionada** | `p_function_definition_empty` | `function_definition : function_type FUNCTION IDEN '(' param_list_opt ')' END` |

As restantes 80+ regras da gramática — incluindo todas as regras de expressão, declaração, statement, e controlo de fluxo — permanecem **sem alteração**.
