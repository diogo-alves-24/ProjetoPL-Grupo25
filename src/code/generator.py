# ---------------------------------------------------------------------------
# Internal generator-local symbol index
# ---------------------------------------------------------------------------

class _GenSymbols:
    """
    Minimal variable registry used only during code generation.

    Builds a mapping  variable_name -> {index, type}  by walking the
    annotated AST declarations.  Keeps separate counters for labels and
    tracks active DO loops.
    """

    def __init__(self):
        self._vars: dict[str, dict] = {}   # name -> {index, type}
        self._label_counter: int = 0
        self._do_stack: list = []

    # ── variable registration ────────────────────────────────────────────

    def register(self, name: str, var_type: str) -> None:
        """Register a variable (idempotent – second call is ignored)."""
        if name not in self._vars:
            self._vars[name] = {
                "index": len(self._vars),
                "type":  var_type,
            }

    def lookup(self, name: str) -> dict:
        if name not in self._vars:
            # Graceful fallback so we don't crash on undeclared vars that
            # the semantic analyser already reported.
            raise KeyError(
                f"[codegen] Variable '{name}' not found in generator index. "
                "Was it declared before use?"
            )
        return self._vars[name]

    def num_vars(self) -> int:
        return len(self._vars)

    def all_vars(self):
        return self._vars.items()

    # ── label generation ─────────────────────────────────────────────────

    def new_label(self, prefix: str = "L") -> str:
        self._label_counter += 1
        return f"{prefix}{self._label_counter}"

    # ── DO loop stack ────────────────────────────────────────────────────

    def push_do(self, info: dict) -> None:
        self._do_stack.append(info)

    def pop_do(self) -> dict:
        return self._do_stack.pop()

    def has_do(self) -> bool:
        return bool(self._do_stack)

    def find_do_by_label(self, label_num: int):
        """Return the innermost DO entry whose terminating label matches."""
        for entry in reversed(self._do_stack):
            if entry.get("end_label_num") == label_num:
                return entry
        return None


# ---------------------------------------------------------------------------
# Code Generator
# ---------------------------------------------------------------------------

class CodeGenerator:
    """
    Translates an annotated AST (tuples) produced by a Fortran-like front-end
    into EWVM assembly instructions.

    The annotated AST format follows the convention that the *last* element of
    most tuples is a dict of type annotations, e.g. {'type': 'INTEGER'}.
    """

    # ── EWVM instruction maps ────────────────────────────────────────────

    _INT_BINOP = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "mod": "MOD"}
    _FLOAT_BINOP = {"+": "FADD", "-": "FSUB", "*": "FMUL", "/": "FDIV"}

    _INT_CMP = {
        "<": "INF", "<=": "INFEQ",
        ">": "SUP", ">=": "SUPEQ",
        "==": "EQUAL", ".EQ.": "EQUAL",
        "/=": None,  # handled specially → EQUAL + NOT
        ".NE.": None,
        ".LT.": "INF", ".LE.": "INFEQ",
        ".GT.": "SUP", ".GE.": "SUPEQ",
    }
    _FLOAT_CMP = {
        "<": "FINF", "<=": "FINFEQ",
        ">": "FSUP", ">=": "FSUPEQ",
        "==": "EQUAL", ".EQ.": "EQUAL",
        "/=": None, ".NE.": None,
        ".LT.": "FINF", ".LE.": "FINFEQ",
        ".GT.": "FSUP", ".GE.": "FSUPEQ",
    }

    # ────────────────────────────────────────────────────────────────────

    def __init__(self):
        self._sym: _GenSymbols = _GenSymbols()

    # ── public entry point ───────────────────────────────────────────────

    def generate(self, ast) -> list[str]:
        """Return EWVM instructions as a list of strings."""
        self._sym = _GenSymbols()
        return self._gen(ast)

    # ── dispatcher ───────────────────────────────────────────────────────

    def _gen(self, node) -> list[str]:
        if node is None:
            return []

        # Handle plain lists (sequence of statements)
        if isinstance(node, list):
            result = []
            for stmt in node:
                result += self._gen(stmt)
            return result

        if not isinstance(node, tuple):
            return []

        tag = node[0]

        # ── top-level wrappers ───────────────────────────────────────────
        if tag == "file":
            # ('file', program_node, extra)
            return self._gen(node[1])

        if tag == "program":
            # ('program', name, stmts)  OR  ('program', name, stmts, ann)
            return self._gen_program(node[1], node[2])

        # ── declarations ────────────────────────────────────────────────
        if tag == "declaration":
            # ('declaration', type, [('var', name, ann), ...])
            return self._gen_declaration(node[1], node[2])

        # ── statements ──────────────────────────────────────────────────
        if tag == "assignment":
            # ('assignment', target, value, ann)
            return self._gen_assignment(node[1], node[2])

        if tag == "print":
            # ('print', items_list)
            return self._gen_print(node[1])

        if tag == "read":
            # ('read', targets_list)
            return self._gen_read(node[1])

        if tag == "if":
            # ('if', cond_label, cond, then_stmts, ann)
            return self._gen_if(node[2], node[3])

        if tag == "if_else":
            # ('if_else', cond_label, cond, then_stmts, else_stmts, ann)
            return self._gen_if_else(node[2], node[3], node[4])

        if tag == "do":
            # ('do', end_label_num, var_name, start, stop, step, ann)
            return self._gen_do_header(
                end_label_num=node[1],
                var_name=node[2],
                start_expr=node[3],
                stop_expr=node[4],
                step_expr=node[5],
            )

        if tag == "labeled":
            # ('labeled', label_num, inner_stmt, ann)
            return self._gen_labeled(node[1], node[2])

        if tag == "continue":
            return []  # no-op in EWVM

        # ── expressions ─────────────────────────────────────────────────
        if tag == "int":
            return [f"PUSHI {node[1]}"]

        if tag == "real":
            return [f"PUSHF {node[1]}"]

        if tag == "string":
            # node[1] is the string content (without surrounding quotes)
            escaped = str(node[1]).replace('"', '\\"')
            return [f'PUSHS "{escaped}"']

        if tag in ("id", "var"):
            return self._gen_load(node[1])

        if tag == "binop":
            # ('binop', op, left, right, ann)
            ann = node[4] if len(node) > 4 and isinstance(node[4], dict) else {}
            return self._gen_binop(node[1], node[2], node[3], ann)

        if tag == "unaryop":
            ann = node[3] if len(node) > 3 and isinstance(node[3], dict) else {}
            return self._gen_unaryop(node[1], node[2], ann)

        if tag == "relop":
            ann = node[4] if len(node) > 4 and isinstance(node[4], dict) else {}
            return self._gen_relop(node[1], node[2], node[3], ann)

        if tag == "logop":
            return self._gen_logop(node[1], node[2], node[3])

        if tag == "not":
            return self._gen(node[1]) + ["NOT"]

        # Unknown node — skip silently
        return []

    # ── program ──────────────────────────────────────────────────────────

    def _gen_program(self, name: str, stmts: list) -> list[str]:
        # First pass: register every declared variable so indices are stable
        for stmt in stmts:
            if isinstance(stmt, tuple) and stmt[0] == "declaration":
                var_type = stmt[1]
                for var_node in stmt[2]:
                    var_name = var_node[1]   # ('var', NAME, ann)
                    self._sym.register(var_name, var_type)

        # Allocate one stack slot per variable
        alloc = ["PUSHI 0"] * self._sym.num_vars()

        # Second pass: generate code for all non-declaration statements
        body = []
        for stmt in stmts:
            if isinstance(stmt, tuple) and stmt[0] == "declaration":
                continue
            body += self._gen(stmt)

        return alloc + body + ["STOP"]

    # ── declaration (no-op at emission time) ─────────────────────────────

    def _gen_declaration(self, var_type: str, var_list: list) -> list[str]:
        # Variable registration already done in _gen_program's first pass.
        return []

    # ── assignment ───────────────────────────────────────────────────────

    def _gen_assignment(self, target, value) -> list[str]:
        name  = target[1]
        info  = self._sym.lookup(name)
        idx   = info["index"]
        ttype = info["type"]

        code      = self._gen(value)
        val_type  = self._expr_type(value)

        if ttype == "REAL" and val_type == "INTEGER":
            code += ["ITOF"]
        elif ttype == "INTEGER" and val_type == "REAL":
            code += ["FTOI"]

        return code + [f"STOREG {idx}"]

    # ── PRINT ────────────────────────────────────────────────────────────

    def _gen_print(self, items: list) -> list[str]:
        code = []
        for item in items:
            item_code = self._gen(item)
            item_type = self._expr_type(item)
            if item_type == "CHARACTER":
                code += item_code + ["WRITES"]
            elif item_type == "REAL":
                code += item_code + ["WRITEF"]
            else:
                code += item_code + ["WRITEI"]
        code += ["WRITELN"]
        return code

    # ── READ ─────────────────────────────────────────────────────────────

    def _gen_read(self, targets: list) -> list[str]:
        code = []
        for target in targets:
            name  = target[1]
            info  = self._sym.lookup(name)
            idx   = info["index"]
            ttype = info["type"]
            code += ["READ"]
            code += ["ATOF"] if ttype == "REAL" else ["ATOI"]
            code += [f"STOREG {idx}"]
        return code

    # ── IF ───────────────────────────────────────────────────────────────

    def _gen_if(self, cond, then_body) -> list[str]:
        end_lbl = self._sym.new_label("ENDIF")
        code    = self._gen(cond)
        code   += [f"JZ {end_lbl}"]
        code   += self._gen(then_body)
        code   += [f"{end_lbl}:"]
        return code

    # ── IF-ELSE ──────────────────────────────────────────────────────────

    def _gen_if_else(self, cond, then_body, else_body) -> list[str]:
        else_lbl = self._sym.new_label("ELSE")
        end_lbl  = self._sym.new_label("ENDIF")
        code     = self._gen(cond)
        code    += [f"JZ {else_lbl}"]
        code    += self._gen(then_body)
        code    += [f"JUMP {end_lbl}", f"{else_lbl}:"]
        code    += self._gen(else_body)
        code    += [f"{end_lbl}:"]
        return code

    # ── DO loop header ───────────────────────────────────────────────────

    def _gen_do_header(self, end_label_num, var_name,
                       start_expr, stop_expr, step_expr) -> list[str]:
        info      = self._sym.lookup(var_name)
        idx       = info["index"]
        start_lbl = self._sym.new_label("DO_START")
        end_lbl   = self._sym.new_label("DO_END")

        # Initialise loop variable
        code  = self._gen(start_expr) + [f"STOREG {idx}"]
        code += [f"{start_lbl}:"]

        # Loop condition: var <= stop  (or var >= stop for negative step)
        code += [f"PUSHG {idx}"]
        code += self._gen(stop_expr)
        step_val = self._static_int(step_expr)
        code += ["SUPEQ"] if (step_val is not None and step_val < 0) else ["INFEQ"]
        code += [f"JZ {end_lbl}"]

        # Save info for the matching CONTINUE / labeled statement
        self._sym.push_do({
            "var_name":      var_name,
            "var_index":     idx,
            "step_expr":     step_expr,
            "start_label":   start_lbl,
            "end_label":     end_lbl,
            "end_label_num": end_label_num,
        })

        return code

    # ── labeled statement (may close a DO) ───────────────────────────────

    def _gen_labeled(self, label_num: int, inner_stmt) -> list[str]:
        inner_code = self._gen(inner_stmt)
        do_info    = self._sym.find_do_by_label(label_num)

        if do_info is None:
            return inner_code

        # Close every DO loop up to and including this one
        tail = []
        while self._sym.has_do():
            di    = self._sym.pop_do()
            tail += self._gen_do_step(di)
            tail += [f"JUMP {di['start_label']}", f"{di['end_label']}:"]
            if di is do_info:
                break

        return inner_code + tail

    def _gen_do_step(self, do_info: dict) -> list[str]:
        idx  = do_info["var_index"]
        step = do_info["step_expr"]
        return [f"PUSHG {idx}"] + self._gen(step) + ["ADD", f"STOREG {idx}"]

    # ── variable load ────────────────────────────────────────────────────

    def _gen_load(self, name: str) -> list[str]:
        return [f"PUSHG {self._sym.lookup(name)['index']}"]

    # ── binary arithmetic ────────────────────────────────────────────────

    def _gen_binop(self, op: str, left, right, ann: dict) -> list[str]:
        result_type = ann.get("type", "INTEGER")
        left_type   = self._expr_type(left)
        right_type  = self._expr_type(right)

        code = self._gen(left)
        if result_type == "REAL" and left_type == "INTEGER":
            code += ["ITOF"]

        code += self._gen(right)
        if result_type == "REAL" and right_type == "INTEGER":
            code += ["ITOF"]

        table = self._FLOAT_BINOP if result_type == "REAL" else self._INT_BINOP
        instr = table.get(op)
        if instr is None:
            raise NotImplementedError(f"[codegen] Unsupported binary op: {op!r}")

        return code + [instr]

    # ── unary arithmetic ─────────────────────────────────────────────────

    def _gen_unaryop(self, op: str, operand, ann: dict) -> list[str]:
        code      = self._gen(operand)
        expr_type = ann.get("type", "INTEGER")
        if op == "-":
            if expr_type == "REAL":
                return ["PUSHF 0.0"] + code + ["FSUB"]
            return ["PUSHI 0"] + code + ["SUB"]
        if op == "+":
            return code
        raise NotImplementedError(f"[codegen] Unsupported unary op: {op!r}")

    # ── relational operators ─────────────────────────────────────────────

    def _gen_relop(self, op: str, left, right, ann: dict) -> list[str]:
        left_type  = self._expr_type(left)
        right_type = self._expr_type(right)
        use_float  = (left_type == "REAL" or right_type == "REAL")

        code = self._gen(left)
        if use_float and left_type == "INTEGER":
            code += ["ITOF"]
        code += self._gen(right)
        if use_float and right_type == "INTEGER":
            code += ["ITOF"]

        table = self._FLOAT_CMP if use_float else self._INT_CMP
        instr = table.get(op)
        if instr is None:
            # /= or .NE. → EQUAL then NOT
            return code + ["EQUAL", "NOT"]
        return code + [instr]

    # ── logical operators ────────────────────────────────────────────────

    def _gen_logop(self, op: str, left, right) -> list[str]:
        code = self._gen(left) + self._gen(right)
        op_upper = op.upper()
        if op_upper in (".AND.", "AND"):
            return code + ["AND"]
        if op_upper in (".OR.", "OR"):
            return code + ["OR"]
        raise NotImplementedError(f"[codegen] Unsupported logical op: {op!r}")

    # ── helpers ──────────────────────────────────────────────────────────

    def _expr_type(self, node) -> str:
        """Return the Fortran type stored in the last-element annotation dict."""
        if not isinstance(node, tuple) or len(node) == 0:
            return "INTEGER"
        ann = node[-1]
        if isinstance(ann, dict):
            return ann.get("type", "INTEGER")
        return "INTEGER"

    @staticmethod
    def _static_int(node):
        """Return the integer value if node is a literal integer, else None."""
        if isinstance(node, tuple) and node[0] == "int":
            return node[1]
        return None


# ---------------------------------------------------------------------------
# Public convenience function
# ---------------------------------------------------------------------------

def generate_code(annotated_ast) -> str:
    """
    Generate EWVM code from an annotated AST.

    Returns the full program as a single newline-joined string and also
    prints it so you can see it in the terminal.

    Parameters
    ----------
    annotated_ast : tuple
        The annotated AST returned by SemanticAnalyzer.analyze_and_annotate().

    Returns
    -------
    str
        EWVM instructions, one per line.
    """
    gen        = CodeGenerator()
    code_lines = gen.generate(annotated_ast)
    code_str   = "\n".join(code_lines)
    print("\n=== CÓDIGO GERADO (EWVM) ===")
    print(code_str)
    return code_str