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
- operações básicas de entrada e saída.

## Arquitetura e Utilização do Compilador

O compilador desenvolvido encontra-se organizado em várias componentes, correspondentes às diferentes fases do processo de compilação. Numa primeira fase, o código fonte é submetido ao analisador léxico, que o converte numa sequência de *tokens*. De seguida, o analisador sintático utiliza esses *tokens* para construir uma Abstract Syntax Tree, que representa a estrutura essencial do programa.

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

A análise léxica corresponde à primeira fase do compilador, sendo responsável por transformar o código fonte Fortran 77 numa sequência de *tokens* utilizada posteriormente pela análise sintática. Para a sua implementação foi utilizada a biblioteca `ply.lex`, que permite descrever os diferentes tipos de lexemas através de expressões regulares em Python.

No analisador léxico desenvolvido foram definidos *tokens* para identificadores, números inteiros, números reais, cadeias de caracteres, valores lógicos, operadores aritméticos, operadores relacionais, operadores lógicos e palavras reservadas da linguagem. Entre estas palavras reservadas encontram-se, por exemplo, `PROGRAM`, `INTEGER`, `REAL`, `LOGICAL`, `CHARACTER`, `IF`, `THEN`, `ELSE`, `ENDIF`, `DO`, `CONTINUE`, `GOTO`, `PRINT`, `READ`, `FUNCTION`, `RETURN` e `END`.

Uma das principais preocupações nesta fase foi garantir o reconhecimento correto dos operadores típicos de Fortran 77. Em particular, foram tratados explicitamente os operadores relacionais `.EQ.`, `.NE.`, `.LT.`, `.LE.`, `.GT.` e `.GE.`, bem como os operadores lógicos `.AND.`, `.OR.` e `.NOT.`. De forma semelhante, os valores `.TRUE.` e `.FALSE.` são reconhecidos diretamente pelo lexer e convertidos para valores booleanos de Python, simplificando a análise semântica posterior.

Os literais numéricos foram divididos em inteiros e reais. Sempre que um inteiro é reconhecido, o respetivo valor é convertido para `int`; no caso dos reais, o valor é convertido para `float`. Também os literais de texto são processados no momento da análise léxica, removendo-se as aspas exteriores para preservar apenas o conteúdo da cadeia de caracteres.

Como Fortran 77 é uma linguagem *case-insensitive*, o analisador foi construído de forma a aceitar diferentes combinações de maiúsculas e minúsculas. Esta opção é especialmente relevante no reconhecimento de palavras reservadas e dos operadores lógicos e relacionais. No caso dos identificadores e palavras reservadas, a estratégia adotada consistiu em reconhecer primeiro uma sequência alfanumérica geral e, de seguida, verificar se o lexema corresponde a alguma palavra reservada através de uma tabela `reserved`.

Outro aspeto relevante foi o tratamento do formato tradicional de Fortran 77. Para acomodar características do formato fixo, foi introduzida uma etapa de pré-processamento antes da tokenização. Essa etapa trata situações como comentários em coluna 1, continuação de linha e identificação de labels no início da linha lógica. Assim, o lexer recebe uma versão já normalizada do programa, o que torna a tokenização mais simples.

Uma dificuldade particular consistiu em distinguir inteiros normais de labels. Em Fortran 77, um número no início de uma linha lógica pode representar um label, como em `10 CONTINUE` ou `20 IF (...) THEN`. Para resolver este problema, o pré-processamento assinala esse contexto e o lexer produz um token específico para labels, evitando confusão com constantes inteiras usadas em expressões.

Por fim, foi também implementado um mecanismo de tratamento de erros léxicos. Sempre que um símbolo inválido é encontrado, o lexer emite uma mensagem de erro e avança um caracter, permitindo continuar a análise do restante programa em vez de interromper imediatamente a compilação.



## Análise Sintática

Para a construção do analisador sintático foi utilizada a biblioteca `ply.yacc`, que permite definir a gramática da linguagem através de produções escritas em funções Python. A partir da sequência de *tokens* produzida pelo analisador léxico, o parser constrói uma Abstract Syntax Tree (AST), representada no projeto através de tuplos.

A construção da gramática foi feita de forma incremental, partindo do símbolo inicial correspondente à unidade completa de compilação. No caso do subconjunto de Fortran 77 implementado, esse símbolo inicial foi definido como `compilation_unit`, permitindo representar um ficheiro composto por um programa principal e, opcionalmente, uma lista de subprogramas, nomeadamente funções. A partir desse nível superior, a gramática foi sendo expandida em blocos mais pequenos, como declarações, instruções e expressões.

A estrutura geral do parser foi organizada em torno das construções pedidas pelo enunciado: declarações de tipos e variáveis, instruções de atribuição, `PRINT`, `READ`, `IF ... THEN ... ELSE ... ENDIF`, ciclos `DO` com labels, `GOTO`, `CONTINUE`, `RETURN` e definição de funções. Para cada uma destas construções foi criada pelo menos uma produção específica, permitindo que a AST resultante preservasse apenas a estrutura sintática essencial do programa, descartando detalhes auxiliares da gramática, como separadores e símbolos intermédios.

Tal como acontece em muitas gramáticas de linguagens imperativas, uma das partes mais delicadas da implementação do parser foi a gramática das expressões. Para lidar com isso, foi utilizada uma tabela explícita de precedências e associatividades, em vez de decompor manualmente a gramática em muitos níveis de não-terminais. Assim, foi possível tratar corretamente operadores aritméticos, relacionais e lógicos, respeitando a precedência definida no parser. Foram também tratados os operadores unários `+`, `-` e `.NOT.`, com precedência própria.

Outro aspeto importante da análise sintática foi o tratamento de labels. Em Fortran 77, um inteiro no início de uma linha pode representar um label, como em `10 CONTINUE` ou `20 IF (...) THEN`. Para evitar ambiguidades entre inteiros comuns e labels, o analisador léxico produz um token próprio para labels no contexto apropriado, permitindo ao parser distinguir entre uma constante inteira usada numa expressão e uma instrução etiquetada.

Uma decisão relevante no parser foi representar uniformemente construções da forma `IDEN(...)` como um nó intermédio genérico na AST. Esta forma sintática pode corresponder tanto a acesso a arrays, como em `NUMS(I)`, como a chamada de função, como em `MOD(NUM, I)` ou `CONVRT(NUM, BASE)`. Como essa distinção depende da informação de declaração e não apenas da forma sintática, optou-se por deixá-la para a fase de análise semântica. Deste modo, o parser mantém-se mais simples e a ambiguidade é resolvida posteriormente com recurso à tabela de símbolos.

Para as produções recursivas, em particular listas de identificadores, listas de expressões e listas de subprogramas, foi frequentemente utilizada recursividade à esquerda. Esta escolha é natural em parsers do tipo LALR e permite construir listas de forma eficiente, sem aumentar desnecessariamente a complexidade do autómato sintático.

Um exemplo simples desta estratégia é a definição de listas separadas por vírgulas, usada em vários pontos da gramática, como nas listas de argumentos e nas declarações múltiplas:

```python
def p_expr_list_one(p):
    "expr_list : expr"
    p[0] = [p[1]]

def p_expr_list_many(p):
    "expr_list : expr_list ',' expr"
    p[0] = p[1] + [p[3]]