.PHONY: all clean

all:
	/opt/homebrew/bin/python3 tester.py

clean:
	rm -f src/parser/parsetab.py
	rm -f src/parser/parser.out