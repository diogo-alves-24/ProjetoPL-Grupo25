from semantic.symboltable import SymbolTable, SymbolTableError
from semantic.typechecker import TypeChecker, TypeCheckerError


class SemanticAnalyzer:
    def __init__(self):
        self.symbols = SymbolTable()
        self.type_checker = TypeChecker()
        self.errors = []

        self.current_function = None
        self.defined_labels = set()
        self.used_labels = set()
        self.do_labels = set()

    # -------------------------------------------------
    # API pública
    # -------------------------------------------------

    def analyze_and_annotate(self, ast):
        annotated = self.visit(ast)
        self._check_labels()
        return annotated, self.errors

    def error(self, msg):
        self.errors.append(msg)

    def _check_labels(self):
        for label in sorted(self.used_labels):
            if str(label) not in self.defined_labels:
                self.error(f"Label '{label}' used but not defined")

        for label in sorted(self.do_labels):
            if str(label) not in self.defined_labels:
                self.error(f"DO label '{label}' not defined")

    def _is_numeric(self, t):
        return t in ("INTEGER", "REAL")

    # -------------------------------------------------
    # Dispatcher geral
    # -------------------------------------------------

    def visit(self, node):
        if node is None:
            return None

        if isinstance(node, list):
            return [self.visit(item) for item in node]

        if not isinstance(node, tuple):
            return node

        tag = node[0]
        method = getattr(self, f"visit_{tag}", None)

        if method is None:
            self.error(f"Unsupported AST node: {tag}")
            return node

        return method(node)

    # -------------------------------------------------
    # Top-level
    # -------------------------------------------------

    def visit_file(self, node):
        _, main_program, subprograms = node

        # Registar assinaturas das funções antes de analisar corpos
        for sub in subprograms:
            if sub[0] == "function":
                _, return_type, name, params, _body = sub
                try:
                    self.symbols.add({
                        "kind": "callable",
                        "name": name,
                        "return_type": return_type,
                        "params": [None for _ in params],
                    })
                except SymbolTableError as e:
                    self.error(str(e))

        ann_main = self.visit(main_program)
        ann_subs = [self.visit(sub) for sub in subprograms]

        return ("file", ann_main, ann_subs)

    def visit_program(self, node):
        _, name, body = node
        self.symbols.new_scope()
        ann_body = self.visit(body)
        self.symbols.unstack_top_scope()
        return ("program", name, ann_body)

    def visit_function(self, node):
        _, return_type, name, params, body = node

        old_function = self.current_function
        self.current_function = name

        self.symbols.new_scope()

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

        try:
            self.symbols.add({
                "kind": "variable",
                "name": name,
                "type": return_type,
                "is_function_result": True
            })
        except SymbolTableError as e:
            self.error(str(e))

        ann_body = self.visit(body)

        self.symbols.unstack_top_scope()
        self.current_function = old_function

        return ("function", return_type, name, params, ann_body)

    # -------------------------------------------------
    # Declarações
    # -------------------------------------------------

    def visit_declaration(self, node):
        _, decl_type, items = node
        ann_items = []

        for item in items:
            ann_items.append(self._declare_item(item, decl_type))

        return ("declaration", decl_type, ann_items)

    def visit_declaration_char(self, node):
        _, size, items = node
        decl_type = f"CHARACTER*{size}"
        ann_items = []

        for item in items:
            ann_items.append(self._declare_item(item, decl_type))

        return ("declaration_char", size, ann_items)

    def _declare_item(self, item, decl_type):
        tag = item[0]

        if tag == "var":
            _, name = item
            current_scope = self.symbols.scopes[-1]
            key = name.lower()

            if key in current_scope:
                existing = current_scope[key]
                if existing["kind"] == "variable" and existing.get("is_param") and existing.get("type") is None:
                    existing["type"] = decl_type
                    return ("var", name, {"type": decl_type, "kind": "variable", "is_param": True})

            try:
                self.symbols.add({
                    "kind": "variable",
                    "name": name,
                    "type": decl_type
                })
            except SymbolTableError as e:
                self.error(str(e))

            return ("var", name, {"type": decl_type, "kind": "variable"})

        if tag == "array_decl":
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

            return ("array_decl", name, dims, {"type": decl_type, "kind": "array"})

        self.error(f"Unknown declaration item: {tag}")
        return item

    # -------------------------------------------------
    # Statements
    # -------------------------------------------------

    def visit_assignment(self, node):
        _, target, expr = node

        ann_target, target_type = self.check_designator(target, for_assignment=True)
        ann_expr, expr_type = self.visit_expr(expr)

        if target_type is not None and expr_type is not None:
            if not self.type_checker.can_assign(target_type, expr_type):
                self.error(f"Cannot assign {expr_type} to {target_type}")

        return ("assignment", ann_target, ann_expr, {
            "target_type": target_type,
            "value_type": expr_type
        })

    def visit_print(self, node):
        _, exprs = node
        ann_exprs = [self.visit_expr(expr)[0] for expr in exprs]
        return ("print", ann_exprs)

    def visit_read(self, node):
        _, targets = node
        ann_targets = [self.check_designator(t, for_assignment=True)[0] for t in targets]
        return ("read", ann_targets)

    def visit_if(self, node):
        _, cond, then_body, else_body = node

        ann_cond, cond_type = self.visit_expr(cond)
        if cond_type is not None and cond_type != "LOGICAL":
            self.error(f"IF condition must be LOGICAL, got {cond_type}")

        ann_then = self.visit(then_body)
        ann_else = self.visit(else_body)

        return ("if", ann_cond, ann_then, ann_else, {"condition_type": cond_type})

    def visit_do(self, node):
        _, label, variable, start, end, step = node

        self.do_labels.add(label)

        var_type = None
        try:
            sym, _ = self.symbols.query_variable(variable, error=True)
            var_type = sym["type"]
            if var_type not in ("INTEGER", "REAL"):
                self.error(f"DO variable '{variable}' must be numeric")
        except SymbolTableError as e:
            self.error(str(e))

        ann_start, start_type = self.visit_expr(start)
        ann_end, end_type = self.visit_expr(end)
        ann_step, step_type = self.visit_expr(step)

        for t in (start_type, end_type, step_type):
            if t is not None and not self._is_numeric(t):
                self.error(f"DO bounds/step must be numeric, got {t}")

        return ("do", label, variable, ann_start, ann_end, ann_step, {
            "var_type": var_type,
            "start_type": start_type,
            "end_type": end_type,
            "step_type": step_type
        })

    def visit_goto(self, node):
        _, label = node
        self.used_labels.add(label)
        return ("goto", label, {"resolved": False})

    def visit_continue(self, node):
        return ("continue",)

    def visit_return(self, node):
        return ("return",)

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

        ann_stmt = self.visit(stmt)
        return ("labeled", label, ann_stmt, {"kind": "label", "defined": True})

    # -------------------------------------------------
    # Expressões
    # -------------------------------------------------

    def visit_expr(self, node):
        tag = node[0]

        if tag in ("int", "float", "string", "bool", "id", "apply", "binop", "unaryop"):
            method = getattr(self, f"visit_{tag}")
            return method(node)

        self.error(f"Unsupported expression node: {tag}")
        return node, None

    def visit_int(self, node):
        _, value = node
        return ("int", value, {"type": "INTEGER"}), "INTEGER"

    def visit_float(self, node):
        _, value = node
        return ("float", value, {"type": "REAL"}), "REAL"

    def visit_string(self, node):
        _, value = node
        return ("string", value, {"type": "CHARACTER"}), "CHARACTER"

    def visit_bool(self, node):
        _, value = node
        return ("bool", value, {"type": "LOGICAL"}), "LOGICAL"

    def visit_id(self, node):
        _, name = node
        try:
            sym, _ = self.symbols.query_variable(name, error=True)
            t = sym["type"]
            return ("id", name, {"kind": sym["kind"], "type": t}), t
        except SymbolTableError as e:
            self.error(str(e))
            return ("id", name, {"kind": "unknown", "type": None}), None

    def visit_apply(self, node):
        _, name, args = node

        ann_args = []
        arg_types = []

        for arg in args:
            ann_arg, arg_type = self.visit_expr(arg)
            ann_args.append(ann_arg)
            arg_types.append(arg_type)

        # 1) array
        var_entry, _ = self.symbols.query_variable(name, error=False)
        if var_entry is not None and var_entry["kind"] == "array":
            expected = len(var_entry["dims"])
            got = len(args)

            if expected != got:
                self.error(f"Array '{name}' expected {expected} indices, got {got}")

            for t in arg_types:
                if t is not None and t != "INTEGER":
                    self.error(f"Array index must be INTEGER, got {t}")

            result_type = var_entry["type"]
            return (
                "apply",
                name,
                ann_args,
                {"resolved_as": "array", "type": result_type, "dims": var_entry["dims"]}
            ), result_type

        # 2) function
        try:
            fun_entry, _ = self.symbols.query_callable(name, error=True)
        except SymbolTableError as e:
            self.error(str(e))
            return ("apply", name, ann_args, {"resolved_as": "unknown", "type": None}), None

        expected_params = fun_entry.get("params", [])
        if len(expected_params) != len(args):
            self.error(f"Function '{name}' expected {len(expected_params)} args, got {len(args)}")

        result_type = fun_entry["return_type"]
        return (
            "apply",
            name,
            ann_args,
            {"resolved_as": "function", "type": result_type, "return_type": result_type}
        ), result_type

    def visit_binop(self, node):
        _, op, left, right = node

        ann_left, left_type = self.visit_expr(left)
        ann_right, right_type = self.visit_expr(right)

        if left_type is None or right_type is None:
            return ("binop", op, ann_left, ann_right, {"type": None}), None

        try:
            result_type = self.type_checker.get_binary_operation_type(op, left_type, right_type)
            return (
                "binop",
                op,
                ann_left,
                ann_right,
                {"type": result_type, "left_type": left_type, "right_type": right_type}
            ), result_type
        except TypeCheckerError as e:
            self.error(str(e))
            return (
                "binop",
                op,
                ann_left,
                ann_right,
                {"type": None, "left_type": left_type, "right_type": right_type}
            ), None

    def visit_unaryop(self, node):
        _, op, expr = node

        ann_expr, expr_type = self.visit_expr(expr)

        if expr_type is None:
            return ("unaryop", op, ann_expr, {"type": None}), None

        try:
            result_type = self.type_checker.get_unary_operation_type(op, expr_type)
            return (
                "unaryop",
                op,
                ann_expr,
                {"type": result_type, "operand_type": expr_type}
            ), result_type
        except TypeCheckerError as e:
            self.error(str(e))
            return (
                "unaryop",
                op,
                ann_expr,
                {"type": None, "operand_type": expr_type}
            ), None

    # -------------------------------------------------
    # Designators
    # -------------------------------------------------

    def check_designator(self, node, for_assignment=False):
        tag = node[0]

        if tag == "id":
            _, name = node
            try:
                sym, _ = self.symbols.query_variable(name, error=True)
                t = sym["type"]
                return ("id", name, {"kind": sym["kind"], "type": t}), t
            except SymbolTableError as e:
                self.error(str(e))
                return ("id", name, {"kind": "unknown", "type": None}), None

        if tag == "apply":
            _, name, args = node

            if for_assignment:
                entry, _ = self.symbols.query_variable(name, error=False)
                if entry is None:
                    self.error(f"Variable '{name}' is not declared")
                    return ("apply", name, args, {"resolved_as": "unknown", "type": None}), None

                if entry["kind"] != "array":
                    self.error(f"{name}(...) is not assignable because it is not an array")
                    return ("apply", name, args, {"resolved_as": "invalid", "type": None}), None

                ann_args = []
                for arg in args:
                    ann_arg, t = self.visit_expr(arg)
                    ann_args.append(ann_arg)
                    if t is not None and t != "INTEGER":
                        self.error(f"Array index must be INTEGER, got {t}")

                expected = len(entry["dims"])
                if expected != len(args):
                    self.error(f"Array '{name}' expected {expected} indices, got {len(args)}")

                return (
                    "apply",
                    name,
                    ann_args,
                    {"resolved_as": "array", "type": entry["type"], "dims": entry["dims"]}
                ), entry["type"]

            return self.visit_apply(node)

        self.error(f"Unsupported designator: {tag}")
        return node, None