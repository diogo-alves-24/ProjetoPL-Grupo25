import sys
import os

# ---------------------------------------------------------------------------
# Exemplos do enunciado
# ---------------------------------------------------------------------------

EXEMPLOS = {
    1: {"nome": "Olá, Mundo!",                   "f": "exemplo1_hello.f",     "evm": "exemplo1_hello.evm"},
    2: {"nome": "Fatorial",                        "f": "exemplo2_fatorial.f",  "evm": "exemplo2_fatorial.evm"},
    3: {"nome": "É primo?",                        "f": "exemplo3_primo.f",     "evm": "exemplo3_primo.evm"},
    4: {"nome": "Soma de uma lista de inteiros",   "f": "exemplo4_somaarr.f",   "evm": "exemplo4_somaarr.evm"},
    5: {"nome": "Conversor de bases (com FUNCTION)","f": "exemplo5_conversor.f","evm": "exemplo5_conversor.evm"},
}

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def compilar(num, exemplo, pasta):
    print(f"Exemplo {num}: {exemplo['nome']}")

    # Importa o compilador
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
        from parser.parser import parse
        from semantic.analyzer import SemanticAnalyzer
        from code.generator import generate_code
    except ImportError as e:
        print(f"  [ERRO] Não foi possível importar o compilador: {e}")
        return False

    # Lê o ficheiro .f
    caminho_f = os.path.join(pasta, exemplo["f"])
    try:
        with open(caminho_f, "r", encoding="utf-8") as f:
            codigo = f.read()
    except FileNotFoundError:
        print(f"  [ERRO] Ficheiro não encontrado: {caminho_f}")
        return False

    # Parsing
    try:
        ast = parse(codigo)
        if ast is None:
            print("  [ERRO] Erro sintático — parser devolveu None.")
            return False
    except Exception as e:
        print(f"  [ERRO] Exceção no parser: {e}")
        return False

    # Análise semântica
    try:
        analyzer = SemanticAnalyzer()
        ann_ast, erros = analyzer.analyze_and_annotate(ast)
        if erros:
            for err in erros:
                print(f"  [AVISO SEMÂNTICO] {err}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  [ERRO] Exceção na análise semântica: {e}")
        return False

    # Geração de código
    try:
        codigo_ewvm = generate_code(ann_ast)
    except Exception as e:
        print(f"  [ERRO] Exceção na geração de código: {e}")
        return False

    if not codigo_ewvm.strip():
        print("  [AVISO] Código gerado vazio.")
        return False

    # Guarda o ficheiro .evm
    caminho_evm = os.path.join(pasta, exemplo["evm"])
    with open(caminho_evm, "w", encoding="utf-8") as f:
        f.write(codigo_ewvm)

    print(f"  [OK] Guardado em {caminho_evm}")
    return True


def main():
    pasta = os.path.join(os.path.dirname(__file__), "tests")
    os.makedirs(pasta, exist_ok=True)

    resultados = {}
    for num, exemplo in EXEMPLOS.items():
        ok = compilar(num, exemplo, pasta)
        resultados[num] = ok

    print()
    print("=" * 50)
    print("SUMÁRIO")
    print("=" * 50)
    for num, ok in resultados.items():
        estado = "OK" if ok else "FALHOU"
        print(f"  Exemplo {num} ({EXEMPLOS[num]['nome']}): {estado}")
    print()
    print(f"Ficheiros .f e .evm em: {pasta}/")


if __name__ == "__main__":
    main()
