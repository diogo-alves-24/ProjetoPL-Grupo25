from pprint import pprint
from parser.parser import parse

def main():
    code = """
    A = 10
    B = 2
    A = A + B * 2
    """

    result = parse(code)
    pprint(result, sort_dicts=False)

if __name__ == "__main__":
    main()