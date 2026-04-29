from pprint import pprint
from parser.parser import parse
from semantic.analyzer import SemanticAnalyzer
from code.generator import generate_code

code = """
PROGRAM FATORIAL
INTEGER N, I, FAT

PRINT *, 'Introduza um numero inteiro positivo:'
READ *, N

FAT = 1
DO 10 I = 1, N
FAT = FAT * I
10 CONTINUE

PRINT *, 'Fatorial de ', N, ': ', FAT
END
"""

ast = parse(code, use_preprocess=False)

analyzer = SemanticAnalyzer()
annotated_ast, errors = analyzer.analyze_and_annotate(ast)

print("=== AST ANOTADA ===")
pprint(annotated_ast, width=120)

print("\n=== ERROS ===")
for err in errors:
    print("-", err)

generate_code(annotated_ast)