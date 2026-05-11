# Projeto PL 2025/26

## Compilador Fortran 77

## Autores

1. Diogo Alves Ferreira - A106904
2. José Miguel da Silva Santos - A72443
3. Mariana Vivas Rodrigues - A106898

## Introdução

No âmbito da unidade curricular de Processamento de Linguagens, foi desenvolvido um compilador para a linguagem Fortran 77. O objetivo principal do projeto consistiu na implementação das várias fases de compilação, nomeadamente análise léxica, análise sintática, análise semântica e geração de código para a máquina virtual utilizada na disciplina.

O analisador léxico foi desenvolvido com recurso à biblioteca `ply.lex`, enquanto o analisador sintático foi implementado com `ply.yacc`. A partir da análise sintática, o compilador constrói uma Abstract Syntax Tree (AST), que é posteriormente utilizada na fase de análise semântica para validação de declarações, usos de identificadores, compatibilidade de tipos e coerência de labels. Finalmente, a representação intermédia resultante é usada na geração de código para a máquina virtual.

Ao longo do desenvolvimento do projeto, foi dada particular atenção à modularidade da implementação, à separação entre as várias fases do compilador e à criação de testes com base nos exemplos do enunciado. Embora o compilador implementado não cubra a totalidade de Fortran 77, suporta os principais mecanismos pedidos, incluindo:

- declarações de variáveis;
- expressões aritméticas, lógicas e relacionais;
- instruções de controlo de fluxo;
- operações básicas de entrada e saída;
- arrays unidimensionais;
- definição e chamada de funções.

## Arquitetura e Utilização do Compilador

O compilador desenvolvido encontra-se organizado em várias componentes, correspondentes às diferentes fases do processo de compilação. Numa primeira fase, o código fonte é submetido ao analisador léxico, que o converte numa sequência de _tokens_. De seguida, o analisador sintático utiliza esses _tokens_ para construir uma Abstract Syntax Tree, que representa a estrutura essencial do programa.

Após a construção da AST, é executada a análise semântica, responsável por verificar a correção do programa ao nível de declarações, tipos, chamadas a funções, acessos a arrays e utilização de labels. Por fim, a informação validada é utilizada na fase de geração de código para a máquina virtual alvo.

Em termos de organização, o projeto encontra-se dividido em módulos separados para o lexer, parser e análise semântica, permitindo uma implementação mais clara e mais fácil de testar. A execução do compilador é feita a partir de um ponto de entrada principal, onde é indicado o programa fonte a compilar.

```text
src/
├── lexer/                 # análise léxica                                            Código fonte
│   ├── tokens.py          # definição de tokens e palavras reservadas                      ↓
│   └── lexer.py           # regras do analisador léxico e pré-processamento              Lexer
├── parser/                # análise sintática                                              ↓
│   └── parser.py          # gramática e construção da AST                                Parser
├── semantic/              # análise semântica                                              ↓
│   ├── symboltable.py     # tabela de símbolos e gestão de scopes                         AST
│   ├── typechecker.py     # verificação de tipos                                           ↓
│   └── analyzer.py        # percurso da AST e validação semântica                   Análise Semântica
└── main.py                # ponto de entrada e testes                                      ↓
                                                                                 Geração de Código
```

## Análise Léxica

A análise léxica corresponde à primeira fase do compilador, sendo responsável por transformar o código fonte Fortran 77 numa sequência de _tokens_ utilizada posteriormente pela análise sintática. Para a sua implementação foi utilizada a biblioteca `ply.lex`, que permite descrever os diferentes tipos de lexemas através de expressões regulares em Python.

No analisador léxico desenvolvido foram definidos _tokens_ para identificadores, números inteiros, números reais, cadeias de caracteres, valores lógicos, operadores aritméticos, operadores relacionais, operadores lógicos e palavras reservadas da linguagem. Entre estas palavras reservadas encontram-se, por exemplo, `PROGRAM`, `INTEGER`, `REAL`, `LOGICAL`, `CHARACTER`, `IF`, `THEN`, `ELSE`, `ENDIF`, `DO`, `CONTINUE`, `GOTO`, `PRINT`, `READ`, `FUNCTION`, `RETURN` e `END`.

Uma das principais preocupações nesta fase foi garantir o reconhecimento correto dos operadores típicos de Fortran 77. Em particular, foram tratados explicitamente os operadores relacionais `.EQ.`, `.NE.`, `.LT.`, `.LE.`, `.GT.` e `.GE.`, bem como os operadores lógicos `.AND.`, `.OR.` e `.NOT.`. De forma semelhante, os valores `.TRUE.` e `.FALSE.` são reconhecidos diretamente pelo lexer e convertidos para valores booleanos de Python, simplificando a análise semântica posterior.

Os literais numéricos foram divididos em inteiros e reais. Sempre que um inteiro é reconhecido, o respetivo valor é convertido para `int`; no caso dos reais, o valor é convertido para `float`. Também os literais de texto são processados no momento da análise léxica, removendo-se as aspas exteriores para preservar apenas o conteúdo da cadeia de caracteres.

Como Fortran 77 é uma linguagem case-insensitive, o analisador foi construído de forma a aceitar diferentes combinações de maiúsculas e minúsculas. Os identificadores e palavras reservadas são normalizados para minúsculas no momento da tokenização. Os operadores relacionais e lógicos, como `.EQ.`, `.AND.` ou `.TRUE.`, são reconhecidos de forma case-insensitive — `.eq.`, `.EQ.` e `.Eq.` são todos aceites — sendo o valor normalizado para maiúsculas no momento da tokenização, pelo que o restante compilador trabalha sempre com a forma canónica uppercase. No caso dos identificadores e palavras reservadas, a estratégia adotada consistiu em reconhecer primeiro uma sequência alfanumérica geral e, de seguida, verificar se o lexema corresponde a alguma palavra reservada através de uma tabela `reserved`.

Outro aspeto relevante foi o tratamento do formato tradicional de Fortran 77. Para acomodar características do formato fixo, foi introduzida uma etapa de pré-processamento antes da tokenização. Essa etapa trata situações como comentários em coluna 1, continuação de linha e identificação de labels no início da linha lógica. Assim, o lexer recebe uma versão já normalizada do programa, o que torna a tokenização mais simples.

Uma dificuldade particular consistiu em distinguir inteiros normais de labels. Em Fortran 77, um número no início de uma linha lógica pode representar um label, como em `10 CONTINUE` ou `20 IF (...) THEN`. Para resolver este problema, o pré-processamento assinala esse contexto e o lexer produz um token específico para labels, evitando confusão com constantes inteiras usadas em expressões.

Por fim, foi também implementado um mecanismo de tratamento de erros léxicos. Sempre que um símbolo inválido é encontrado, o lexer emite uma mensagem de erro e avança um caracter, permitindo continuar a análise do restante programa em vez de interromper imediatamente a compilação.

Durante o desenvolvimento, a gramática original continha 26 conflitos shift/reduce detetados pelo PLY. A causa era a regra `body : empty`, que criava dois caminhos equivalentes para parsear o primeiro item de qualquer corpo não vazio. A correção consistiu em três mudanças: remover a regra `body : empty` e tratar explicitamente os casos de corpo vazio com duas produções novas — `main_program : PROGRAM IDEN END` para programas sem corpo e `function_definition : function_type FUNCTION IDEN '(' param_list_opt ')' END` para funções sem corpo. Estas duas produções garantem que o parser consegue distinguir um corpo vazio de um corpo não vazio com um único token de lookahead, eliminando a ambiguidade sem alterar o comportamento semântico da gramática. Após esta correção, o parser gera tabelas LALR sem qualquer conflito.

## Análise Sintática

Para a construção do analisador sintático foi utilizada a biblioteca `ply.yacc`, que permite definir a gramática da linguagem através de produções escritas em funções Python. A partir da sequência de _tokens_ produzida pelo analisador léxico, o parser constrói uma Abstract Syntax Tree (AST), representada no projeto através de tuplos.

A construção da gramática foi feita de forma incremental, partindo do símbolo inicial correspondente à unidade completa de compilação. No caso do subconjunto de Fortran 77 implementado, esse símbolo inicial foi definido como `compilation_unit`, permitindo representar um ficheiro composto por um programa principal e, opcionalmente, uma lista de subprogramas, nomeadamente funções. A partir desse nível superior, a gramática foi sendo expandida em blocos mais pequenos, como declarações, instruções e expressões.

A estrutura geral do parser foi organizada em torno das construções pedidas pelo enunciado: declarações de tipos e variáveis, instruções de atribuição, `PRINT`, `READ`, `IF ... THEN ... ELSE ... ENDIF`, ciclos `DO` com labels, `GOTO`, `CONTINUE`, `RETURN` e definição de funções. Para cada uma destas construções foi criada pelo menos uma produção específica, permitindo que a AST resultante preservasse apenas a estrutura sintática essencial do programa, descartando detalhes auxiliares da gramática, como separadores e símbolos intermédios.

Tal como acontece em muitas gramáticas de linguagens imperativas, uma das partes mais delicadas da implementação do parser foi a gramática das expressões. Para lidar com isso, foi utilizada uma tabela explícita de precedências e associatividades, em vez de decompor manualmente a gramática em muitos níveis de não-terminais. Assim, foi possível tratar corretamente operadores aritméticos, relacionais e lógicos, respeitando a precedência definida no parser. Foram também tratados os operadores unários `+`, `-` e `.NOT.`, com precedência própria.

Outro aspeto importante da análise sintática foi o tratamento de labels. Em Fortran 77, um inteiro no início de uma linha pode representar um label, como em `10 CONTINUE` ou `20 IF (...) THEN`. Para evitar ambiguidades entre inteiros comuns e labels, o analisador léxico produz um token próprio para labels no contexto apropriado, permitindo ao parser distinguir entre uma constante inteira usada numa expressão e uma instrução etiquetada.

Uma decisão relevante no parser foi representar uniformemente construções da forma `IDEN(...)` como um nó intermédio genérico na AST. Esta forma sintática pode corresponder tanto a acesso a arrays, como em `NUMS(I)`, como a chamada de função, como em `MOD(NUM, I)` ou `CONVRT(NUM, BASE)`. Como essa distinção depende da informação de declaração e não apenas da forma sintática, optou-se por deixá-la para a fase de análise semântica. Deste modo, o parser mantém-se mais simples e a ambiguidade é resolvida posteriormente com recurso à tabela de símbolos.

Para as produções recursivas, em particular listas de identificadores, listas de expressões e listas de subprogramas, foi frequentemente utilizada recursividade à esquerda. Esta escolha é natural em parsers do tipo LALR e permite construir listas de forma eficiente, sem aumentar desnecessariamente a complexidade do autómato sintático.

A gramática implementada pode ser descrita formalmente da seguinte forma:

```bnf
compilation_unit ::= main_program subprogram_list_opt

main_program ::= PROGRAM IDEN body END
               | PROGRAM IDEN END

subprogram_list_opt ::= ε
                       | subprogram_list

subprogram_list ::= subprogram
                  | subprogram_list subprogram

subprogram ::= function_definition

function_definition ::= function_type FUNCTION IDEN '(' param_list_opt ')' body END
                       | function_type FUNCTION IDEN '(' param_list_opt ')' END

function_type ::= INTEGER | REAL | LOGICAL | CHARACTER

param_list_opt ::= ε | id_list

id_list ::= IDEN | id_list ',' IDEN

body ::= item | body item

item ::= declaration | statement

declaration ::= INTEGER decl_item_list
              | REAL decl_item_list
              | LOGICAL decl_item_list
              | CHARACTER decl_item_list
              | CHARACTER '*' INT decl_item_list

decl_item_list ::= decl_item | decl_item_list ',' decl_item

decl_item ::= IDEN | IDEN '(' int_list ')'

int_list ::= INT | int_list ',' INT

statement ::= assignment
            | print_stmt
            | read_stmt
            | if_stmt
            | do_stmt
            | goto_stmt
            | continue_stmt
            | return_stmt
            | labeled_stmt

assignment ::= designator '=' expr

print_stmt ::= PRINT '*' ',' expr_list

read_stmt  ::= READ '*' ',' designator_list

if_stmt ::= IF '(' expr ')' THEN stmt_block ENDIF
          | IF '(' expr ')' THEN stmt_block ELSE stmt_block ENDIF

stmt_block ::= statement | stmt_block statement

do_stmt ::= DO INT IDEN '=' expr ',' expr
          | DO INT IDEN '=' expr ',' expr ',' expr

goto_stmt    ::= GOTO INT

continue_stmt ::= CONTINUE

return_stmt  ::= RETURN

labeled_stmt ::= LABEL statement

designator ::= IDEN | IDEN '(' expr_list ')'

designator_list ::= designator | designator_list ',' designator

expr_list ::= expr | expr_list ',' expr

expr ::= expr '+' expr | expr '-' expr
       | expr '*' expr | expr '/' expr
       | expr '**' expr
       | expr .EQ. expr | expr .NE. expr
       | expr .LT. expr | expr .LE. expr
       | expr .GT. expr | expr .GE. expr
       | expr .AND. expr | expr .OR. expr
       | .NOT. expr
       | '-' expr | '+' expr
       | '(' expr ')'
       | INT | FLOAT | STRING | BOOL
       | designator
```

Um exemplo simples desta estratégia é a definição de listas separadas por vírgulas, usada em vários pontos da gramática, como nas listas de argumentos e nas declarações múltiplas:

```python
def p_expr_list_one(p):
    "expr_list : expr"
    p[0] = [p[1]]

def p_expr_list_many(p):
    "expr_list : expr_list ',' expr"
    p[0] = p[1] + [p[3]]
```

## Análise Semântica

A análise semântica constitui a terceira fase do compilador, sendo responsável por verificar a correção do programa para além da sua estrutura sintática. Esta fase percorre a AST produzida pelo parser e produz uma AST anotada, onde cada nó passa a conter informação de tipos e de resolução de identificadores, utilizada posteriormente na geração de código.

A gestão de identificadores é feita através de uma tabela de símbolos com suporte a múltiplos scopes. Cada vez que se entra num novo bloco, programa principal ou função, é criado um scope novo, que é removido no final desse bloco. Esta organização permite que variáveis locais a uma função não sejam visíveis fora dela, e que seja possível ter variáveis com o mesmo nome em funções diferentes. O scope global contém apenas os builtins da linguagem, nomeadamente a função `MOD`.

A verificação de tipos é tratada por um módulo dedicado, o `TypeChecker`, que define as regras de compatibilidade de tipos para operações aritméticas, relacionais e lógicas. Em operações aritméticas, o resultado é `REAL` sempre que pelo menos um dos operandos for `REAL`, e `INTEGER` quando ambos forem inteiros, incluindo a divisão, onde `INTEGER/INTEGER` produz um resultado inteiro, conforme o standard de Fortran 77. As operações relacionais produzem sempre um resultado do tipo `LOGICAL`.

Uma das decisões mais relevantes desta fase foi a resolução da forma sintática `IDEN(...)`, que tanto pode representar um acesso a array como uma chamada a função. Essa distinção é feita com recurso à tabela de símbolos: se o identificador estiver declarado como array, o nó é anotado com `resolved_as: "array"` e as expressões entre parênteses são tratadas como índices; caso contrário, é tratado como uma chamada a função e as expressões são tratadas como argumentos. Esta resolução permite que as fases seguintes tratem os dois casos de forma distinta sem necessidade de análise adicional.

Foi também implementada a verificação de labels utilizados em instruções `DO` e `GOTO`. O analisador regista todos os labels definidos e todos os labels referenciados, verificando no final que não existem labels usados mas não definidos, nem labels de `DO` sem o respetivo statement de terminação.

Uma dificuldade encontrada nesta fase foi o tratamento de parâmetros de funções. Em Fortran 77, os parâmetros são declarados dentro do corpo da função com o seu tipo, e não na assinatura. Isto implica que, quando se entra no scope da função, os parâmetros são registados inicialmente sem tipo, sendo este atribuído posteriormente quando a declaração correspondente é encontrada.

### Exemplos de AST

Para ilustrar a estrutura interna produzida pelo compilador, apresenta-se o nó AST gerado para uma atribuição simples e para um ciclo DO.

**Atribuição** `FAT = FAT * I`:

```python
("assignment",
    ("id", "FAT", {"kind": "variable", "type": "INTEGER"}),
    ("binop", "*",
        ("id", "FAT", {"kind": "variable", "type": "INTEGER"}),
        ("id", "I",   {"kind": "variable", "type": "INTEGER"}),
        {"type": "INTEGER", "left_type": "INTEGER", "right_type": "INTEGER"}
    ),
    {"target_type": "INTEGER", "value_type": "INTEGER"}
)
```

**Ciclo DO** `DO 10 I = 1, N`:

```python
("do", 10, "I",
    ("int", 1, {"type": "INTEGER"}),
    ("id", "N", {"kind": "variable", "type": "INTEGER"}),
    ("int", 1, {"type": "INTEGER"}),
    {"var_type": "INTEGER", "start_type": "INTEGER",
     "end_type": "INTEGER", "step_type": "INTEGER"}
)
```

Cada nó é um tuplo onde o primeiro elemento é o tag que identifica o tipo de construção, seguido dos seus filhos e de um dicionário de anotações semânticas no último elemento.

## Geração de Código

A geração de código constitui a fase final do compilador, sendo responsável por traduzir a AST anotada produzida pela análise semântica em instruções para a máquina virtual EWVM. O gerador percorre a AST de forma recursiva através de um método dispatcher central, `_gen`, que identifica o tag de cada nó e delega para o método especializado correspondente.

As variáveis são geridas através de uma tabela interna ao gerador, `_GenSymbols`, que associa cada variável a um índice na stack global da EWVM. No início da geração de cada programa, é feito um primeiro passo pela lista de declarações para registar todas as variáveis e calcular os seus índices. Para variáveis simples é alocado um slot com `PUSHI 0`. Para arrays, é alocado 1 slot para guardar o endereço heap, inicializado posteriormente com `ALLOCN`.

Arrays unidimensionais são alocados no heap da EWVM usando a instrução `ALLOCN`, que recebe o tamanho e devolve um endereço. Esse endereço é guardado num slot da stack global. Para aceder a um elemento `NUMS(I)`, o gerador empurra o endereço base do array, calcula o offset `I - 1` com `PADD`, e usa `LOAD 0` para leitura ou `STORE 0` para escrita. O `-1` deve-se ao facto de Fortran indexar a partir de 1.

Para as instruções de controlo de fluxo, a geração baseia-se na criação de labels internos da VM. No caso do `IF` sem `ELSE`, é gerado um label de fim e uma instrução `JZ` que salta para esse label se a condição for falsa. No caso do `IF` com `ELSE`, são gerados dois labels, um para o início do bloco `ELSE` e outro para o fim do `ENDIF`, com um `JUMP` incondicional a separar os dois blocos. Para o `GOTO`, é emitida uma instrução `JUMP` para o label VM correspondente ao label Fortran, que é sempre emitido pelo gerador quando encontra um statement etiquetado.

Os ciclos `DO` são gerados em duas partes. O cabeçalho do ciclo inicializa a variável de controlo, emite o label de início, avalia a condição de paragem e emite um `JZ` para o label de fim. O fecho do ciclo, incremento da variável, salto para o início e emissão do label de fim, é emitido quando o gerador encontra o statement etiquetado com o label de terminação do `DO`, registado previamente numa pilha de loops ativos.

As funções definidas pelo utilizador são compiladas como blocos de código independentes, precedidos por um label com o nome da função. O programa principal começa sempre com `JUMP MAIN` para saltar por cima dos corpos das funções. Dentro de uma função, as variáveis locais são acedidas com `PUSHL`/`STOREL` em vez de `PUSHG`/`STOREG`, usando o frame pointer. Os parâmetros são passados antes do `PUSHA` e acedidos com índices negativos (`PUSHL -1`, `PUSHL -2`, etc.). O valor de retorno é empurrado para a stack antes do `RETURN`, através da variável com o mesmo nome da função.

Uma dificuldade significativa nesta fase foi a coordenação entre os statements etiquetados e o fecho dos ciclos `DO`. Em Fortran 77, o label de terminação de um `DO` aparece num statement separado que pode estar vários níveis abaixo na AST, tornando necessário manter uma pilha de loops ativos para saber quais os loops a fechar quando um label é encontrado.

## Limitações e Trabalho Futuro

O compilador implementado cobre os principais mecanismos pedidos pelo enunciado, mas apresenta algumas limitações que ficam identificadas para trabalho futuro.

A construção `SUBROUTINE` não foi implementada. Ao contrário das funções, as subrotinas não devolvem um valor e são invocadas com a instrução `CALL`, o que implicaria suporte adicional no lexer, no parser, na análise semântica e na geração de código.

Arrays unidimensionais são suportados com alocação no heap usando `ALLOCN`, permitindo acesso dinâmico por índice. Arrays multidimensionais não foram testados e podem requerer extensão ao método de cálculo de endereço para considerar múltiplos índices e dimensões.

## Testes e Resultados

Os cinco exemplos do enunciado foram compilados e testados na máquina virtual EWVM. A tabela seguinte resume os inputs utilizados e os outputs esperados:

| Exemplo           | Input       | Output esperado                                  |
| ----------------- | ----------- | ------------------------------------------------ |
| 1 — Olá, Mundo!   | —           | `Ola, Mundo!`                                    |
| 2 — Fatorial      | `10`        | `Fatorial de 10: 3628800`                        |
| 3 — É primo?      | `7`         | `7 e um numero primo`                            |
| 3 — É primo?      | `10`        | `10 nao e um numero primo`                       |
| 4 — Soma de array | `1 2 3 4 5` | `A soma dos numeros e: 15`                       |
| 5 — Conversor     | `10`        | `BASE 2: 1010`, `BASE 3: 101`, `BASE 4: 22`, ... |

Todos os exemplos foram verificados no site [https://ewvm.epl.di.uminho.pt/](https://ewvm.epl.di.uminho.pt/) com os ficheiros `.evm` gerados pelo compilador, produzindo os resultados esperados.

O script `tester.py` compila automaticamente os 5 exemplos a partir dos ficheiros `.f` em `tests/` e gera os respetivos ficheiros `.evm`. A compilação de todos os exemplos completa sem erros semânticos.

## Como Correr o Compilador

### Dependências

- Python 3.10 ou superior
- Biblioteca `ply`:

```bash
pip install ply
```

### Estrutura do projeto

```text
ProjetoPL-Grupo25/
├── src/                  # código fonte do compilador
├── tests/                # ficheiros .f (source) e .evm (output)
├── relatorio/            # relatório técnico
├── tester.py             # script de teste dos 5 exemplos
└── Makefile              # atalho para correr o tester
```

### Correr os testes

```bash
make
```

Ou diretamente:

```bash
python tester.py
```

O script lê cada ficheiro `.f` em `tests/`, compila-o e guarda o código EWVM no ficheiro `.evm` correspondente.

### Testar na máquina virtual

O código gerado nos ficheiros `.evm` pode ser testado em [https://ewvm.epl.di.uminho.pt/](https://ewvm.epl.di.uminho.pt/) — basta colar o conteúdo do ficheiro na interface web.
