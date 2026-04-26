from pprint import pprint
from parser.parser import parse
from semantic.analyzer import SemanticAnalyzer

code = """
PROGRAM FATORIAL
INTEGER N, I, FAT
PRINT *, 'Introduza um numero inteiro positivo:'
READ *, N
FAT = 2
DO 10 I = 1, N
FAT = FAT * I
10 CONTINUE
PRINT *, 'Fatorial de ', N, ': ', FAT
END
"""

ast = parse(code, use_preprocess=False)
print("=== AST ===")
pprint(ast, width=120)

analyzer = SemanticAnalyzer()
errors = analyzer.analyze(ast)

print("\n=== SEMANTIC ERRORS ===")
if not errors:
    print("Sem erros semânticos.")
else:
    for err in errors:
        print("-", err)