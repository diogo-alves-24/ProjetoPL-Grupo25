from src.semantic.symboltable import SymbolTable, SymbolTableError
from src.semantic.typechecker import TypeChecker, TypeCheckerError


class SemanticAnalyzer:
    def __init__(self):
        self.symbols = SymbolTable()
        self.type_checker = TypeChecker()
        self.errors = []

        self.current_function = None

        # labels
        self.defined_labels = set()
        self.used_labels = set()
        self.do_labels = set()

    # -------------------------
    # API pública
    # -------------------------

    def analyze(self, ast):
        self.visit(ast)
        self._check_labels()
        return self.errors

    # -------------------------
    # Helpers
    # -------------------------

    def error(self, msg):
        self.errors.append(msg)

    def visit(self, node):
        if node is None:
            return None

        if isinstance(node, list):
            for item in node:
                self.visit(item)
            return None

        if not isinstance(node, tuple):
            return None

        # Se a ast tiver um node ("assignment", ...)
        # procura pelo metodo visit_assignment(node)
        tag = node[0]
        method = getattr(self, f"visit_{tag}", None)

        if method is None:
            self.error(f"Unsupported AST node: {tag}")
            return None

        return method(node)

    def _check_labels(self):
        for label in sorted(self.used_labels):
            if str(label) not in self.defined_labels:
                self.error(f"Label '{label}' used but not defined")

        for label in sorted(self.do_labels):
            if str(label) not in self.defined_labels:
                self.error(f"DO label '{label}' not defined")

    def _is_numeric(self, t):
        return t in ("INTEGER", "REAL")

    # -------------------------
    # Top-level
    # -------------------------

    def visit_file(self, node):
        _, main_program, subprograms = node

        # primeiro registar assinaturas das funções
        # para caso seja chamada o programa ja saber que ela existe
        for sub in subprograms:
            if sub[0] == "function":
                _, return_type, name, params, _body = sub
                try:
                    self.symbols.add({
                        "kind": "callable",
                        "name": name,
                        "return_type": return_type,
                        "params": [None for _ in params],  # tipos dos params vêm das declarações
                    })
                except SymbolTableError as e:
                    self.error(str(e))

        # depois analisar programa principal e subprogramas
        self.visit(main_program)
        for sub in subprograms:
            self.visit(sub)

    def visit_program(self, node):
        _, _name, body = node

        self.symbols.new_scope()
        self.visit(body)
        self.symbols.unstack_top_scope()

    def visit_function(self, node):
        _, return_type, name, params, body = node

        old_function = self.current_function
        self.current_function = name

        self.symbols.new_scope()

        # parâmetros entram primeiro como variáveis sem tipo conhecido ainda
        for param in params:
            try:
                self.symbols.add({
                    "kind": "variable",
                    "name": param,
                    "type": None,
                    "is_param": True
                })
            except SymbolTableError as e:
                self.error(str(e))

        # nome da função também funciona como variável de retorno
        try:
            self.symbols.add({
                "kind": "variable",
                "name": name,
                "type": return_type,
                "is_function_result": True
            })
        except SymbolTableError as e:
            self.error(str(e))

        self.visit(body)

        self.symbols.unstack_top_scope()
        self.current_function = old_function

    # -------------------------
    # Declarações
    # -------------------------

    def visit_declaration(self, node):
        _, decl_type, items = node
        for item in items:
            self._declare_item(item, decl_type)

    def visit_declaration_char(self, node):
        _, size, items = node
        decl_type = f"CHARACTER*{size}"
        for item in items:
            self._declare_item(item, decl_type)

    def _declare_item(self, item, decl_type):
        tag = item[0]

        if tag == "var":
            _, name = item
            current_scope = self.symbols.scopes[-1]
            key = name.lower()

            # se já existia como parâmetro sem tipo, atualiza
            if key in current_scope:
                existing = current_scope[key]
                if existing["kind"] == "variable" and existing.get("is_param") and existing.get("type") is None:
                    existing["type"] = decl_type
                    return

            try:
                self.symbols.add({
                    "kind": "variable",
                    "name": name,
                    "type": decl_type
                })
            except SymbolTableError as e:
                self.error(str(e))

        elif tag == "array_decl":
            _, name, dims = item
            try:
                self.symbols.add({
                    "kind": "array",
                    "name": name,
                    "type": decl_type,
                    "dims": dims
                })
            except SymbolTableError as e:
                self.error(str(e))

        else:
            self.error(f"Unknown declaration item: {tag}")

    # -------------------------
    # Statements
    # -------------------------

    def visit_assignment(self, node):
        _, target, expr = node

        left_type = self.check_designator(target, for_assignment=True)
        right_type = self.visit(expr)

        if left_type is not None and right_type is not None:
            if not self.type_checker.can_assign(left_type, right_type):
                self.error(f"Cannot assign {right_type} to {left_type}")

    def visit_print(self, node):
        _, exprs = node
        for expr in exprs:
            self.visit(expr)

    def visit_read(self, node):
        _, targets = node
        for target in targets:
            self.check_designator(target, for_assignment=True)

    def visit_if(self, node):
        _, cond, then_body, else_body = node

        cond_type = self.visit(cond)
        if cond_type is not None and cond_type != "LOGICAL":
            self.error(f"IF condition must be LOGICAL, got {cond_type}")

        self.visit(then_body)
        self.visit(else_body)

    def visit_do(self, node):
        _, label, variable, start, end, step = node

        self.do_labels.add(label)

        try:
            sym, _ = self.symbols.query_variable(variable, error=True)
            if sym["type"] not in ("INTEGER", "REAL"):
                self.error(f"DO variable '{variable}' must be numeric")
        except SymbolTableError as e:
            self.error(str(e))

        for expr in (start, end, step):
            t = self.visit(expr)
            if t is not None and not self._is_numeric(t):
                self.error(f"DO bounds/step must be numeric, got {t}")

    def visit_goto(self, node):
        _, label = node
        self.used_labels.add(label)

    def visit_continue(self, node):
        return None

    def visit_return(self, node):
        return None

    def visit_labeled(self, node):
        _, label, stmt = node
        label_name = str(label)

        if label_name in self.defined_labels:
            self.error(f"Label '{label}' already defined")
        else:
            self.defined_labels.add(label_name)

        try:
            self.symbols.add({
                "kind": "label",
                "name": label_name,
                "statement": stmt
            })
        except SymbolTableError as e:
            self.error(str(e))

        self.visit(stmt)

    # -------------------------
    # Expressões
    # -------------------------

    def visit_int(self, node):
        return "INTEGER"

    def visit_float(self, node):
        return "REAL"

    def visit_string(self, node):
        return "CHARACTER"

    def visit_bool(self, node):
        return "LOGICAL"

    def visit_id(self, node):
        _, name = node
        try:
            sym, _ = self.symbols.query_variable(name, error=True)
            return sym["type"]
        except SymbolTableError as e:
            self.error(str(e))
            return None

    def visit_apply(self, node):
        _, name, args = node

        # tipos dos argumentos
        arg_types = [self.visit(arg) for arg in args]

        # 1) tentar como array
        var_entry, _ = self.symbols.query_variable(name, error=False)
        if var_entry is not None and var_entry["kind"] == "array":
            expected = len(var_entry["dims"])
            got = len(args)

            if expected != got:
                self.error(f"Array '{name}' expected {expected} indices, got {got}")

            for t in arg_types:
                if t is not None and t != "INTEGER":
                    self.error(f"Array index must be INTEGER, got {t}")

            return var_entry["type"]

        # 2) tentar como callable
        try:
            fun_entry, _ = self.symbols.query_callable(name, error=True)
        except SymbolTableError as e:
            self.error(str(e))
            return None

        expected_params = fun_entry.get("params", [])
        if len(expected_params) != len(args):
            self.error(f"Function '{name}' expected {len(expected_params)} args, got {len(args)}")

        return fun_entry["return_type"]

    def visit_binop(self, node):
        _, op, left, right = node
        left_type = self.visit(left)
        right_type = self.visit(right)

        if left_type is None or right_type is None:
            return None

        try:
            return self.type_checker.get_binary_operation_type(op, left_type, right_type)
        except TypeCheckerError as e:
            self.error(str(e))
            return None

    def visit_unaryop(self, node):
        _, op, expr = node
        expr_type = self.visit(expr)

        if expr_type is None:
            return None

        try:
            return self.type_checker.get_unary_operation_type(op, expr_type)
        except TypeCheckerError as e:
            self.error(str(e))
            return None

    # -------------------------
    # Designators
    # -------------------------

    def check_designator(self, node, for_assignment=False):
        tag = node[0]

        if tag == "id":
            _, name = node
            try:
                sym, _ = self.symbols.query_variable(name, error=True)
                return sym["type"]
            except SymbolTableError as e:
                self.error(str(e))
                return None

        if tag == "apply":
            _, name, args = node

            if for_assignment:
                entry, _ = self.symbols.query_variable(name, error=False)
                if entry is None:
                    self.error(f"Variable '{name}' is not declared")
                    return None

                if entry["kind"] != "array":
                    self.error(f"{name}(...) is not assignable because it is not an array")
                    return None

                expected = len(entry["dims"])
                if expected != len(args):
                    self.error(f"Array '{name}' expected {expected} indices, got {len(args)}")

                for arg in args:
                    t = self.visit(arg)
                    if t is not None and t != "INTEGER":
                        self.error(f"Array index must be INTEGER, got {t}")

                return entry["type"]

            return self.visit_apply(node)

        self.error(f"Unsupported designator: {tag}")
        return None