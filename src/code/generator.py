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

    def num_slots(self) -> int:
        return sum(v["size"] for v in self._vars.values())

    # ── variable registration ────────────────────────────────────────────

    def register(self, name: str, var_type: str, size: int = 1, is_array: bool = False, array_size: int = 0) -> None:
        if name not in self._vars:
            base = sum(v["size"] for v in self._vars.values())
            self._vars[name] = {
                "index":      base,
                "type":       var_type,
                "size":       size,
                "is_array":   is_array,
                "array_size": array_size,
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
        self._in_function: bool = False
        self._local_sym: _GenSymbols = None
        self._return_var: str = None

    def _push_var(self, idx: int) -> str:
        return f"PUSHL {idx}" if self._in_function else f"PUSHG {idx}"

    def _store_var(self, idx: int) -> str:
        return f"STOREL {idx}" if self._in_function else f"STOREG {idx}"

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
            func_code = []
            for func in node[2]:
                func_code += self._gen_function(func)
            main_code = self._gen(node[1])
            if func_code:
                return ["JUMP MAIN"] + func_code + ["MAIN:"] + main_code
            return main_code

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
            if node[3]:
                return self._gen_if_else(node[1], node[2], node[3])
            return self._gen_if(node[1], node[2])

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

        if tag == "goto":
            return [f"JUMP L{node[1]}"]
        
        if tag == "return":
            if self._in_function and self._return_var is not None:
                return self._gen_load(self._return_var) + ["RETURN"]
            return ["RETURN"]

        # ── expressions ─────────────────────────────────────────────────
        if tag == "int":
            return [f"PUSHI {node[1]}"]

        if tag == "float":
            return [f"PUSHF {node[1]}"]

        if tag == "string":
            # node[1] is the string content (without surrounding quotes)
            escaped = str(node[1]).replace('"', '\\"')
            return [f'PUSHS "{escaped}"']
        
        if tag == "bool":
            return [f"PUSHI {1 if node[1] else 0}"]

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
        
        if tag == "apply":
            ann = node[3] if len(node) > 3 and isinstance(node[3], dict) else {}
            if ann.get("resolved_as") == "array":
                return self._gen_array_access(node[1], node[2])
            if ann.get("resolved_as") == "function":
                name = node[1].upper()
                args = node[2]
                code = []
                for arg in args:
                    code += self._gen(arg)
                if name == "MOD":
                    return code + ["MOD"]
                return code + [f"PUSHA {name}", "CALL"]
            return []

        # Unknown node — skip silently
        return []

    # ── program ──────────────────────────────────────────────────────────

    def _gen_program(self, name: str, stmts: list) -> list[str]:
        # primeiro passe — regista variáveis e arrays
        for stmt in stmts:
            if isinstance(stmt, tuple) and stmt[0] == "declaration":
                var_type = stmt[1]
                for var_node in stmt[2]:
                    if var_node[0] == "var":
                        self._sym.register(var_node[1], var_type, size=1)
                    elif var_node[0] == "array_decl":
                        array_size = 1
                        for dim in var_node[2]:
                            array_size *= dim
                        self._sym.register(var_node[1], var_type, size=1, is_array=True, array_size=array_size)

        # aloca slots para variáveis simples
        alloc = []
        for v in self._sym._vars.values():
            if not v.get("is_array"):
                alloc += ["PUSHI 0"] * v["size"]
            else:
                alloc += ["PUSHI 0"]  # reserva o slot para o endereço heap
        # inicializa arrays no heap
        array_init = []
        for vname, vinfo in self._sym.all_vars():
            if vinfo.get("is_array"):
                array_init += [f"PUSHI {vinfo['array_size']}", "ALLOCN", f"STOREG {vinfo['index']}"]

        # segundo passe — gera código
        body = []
        for stmt in stmts:
            if isinstance(stmt, tuple) and stmt[0] == "declaration":
                continue
            body += self._gen(stmt)

        return alloc + array_init + body + ["STOP"]

    # ── declaration (no-op at emission time) ─────────────────────────────

    def _gen_declaration(self, var_type: str, var_list: list) -> list[str]:
        # Variable registration already done in _gen_program's first pass.
        return []

    # ── assignment ───────────────────────────────────────────────────────

    def _gen_assignment(self, target, value) -> list[str]:
        ttype    = target[-1]["type"] if isinstance(target[-1], dict) else "INTEGER"
        val_type = self._expr_type(value)

        # conversão de tipo do valor
        val_code = self._gen(value)
        if ttype == "REAL" and val_type == "INTEGER":
            val_code += ["ITOF"]
        elif ttype == "INTEGER" and val_type == "REAL":
            val_code += ["FTOI"]

        # destino é variável simples
        if target[0] == "id":
            idx = self._sym.lookup(target[1])["index"]
            return val_code + [self._store_var(idx)]

        # destino é elemento de array
        if target[0] == "apply":
            name = target[1]
            base = self._sym.lookup(name)["index"]
            addr_code  = [self._push_var(base)]
            addr_code += self._gen(target[2][0])
            addr_code += ["PUSHI 1", "SUB", "PADD"]
            return addr_code + val_code + ["STORE 0"]

        return val_code

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
            if target[0] == "apply":
                name  = target[1]
                info  = self._sym.lookup(name)
                ttype = info["type"]
                idx   = info["index"]
                # calcula endereço primeiro
                code += [self._push_var(idx)]
                code += self._gen(target[2][0])
                code += ["PUSHI 1", "SUB", "PADD"]
                # lê o valor
                code += ["READ"]
                code += ["ATOF"] if ttype == "REAL" else ["ATOI"]
                # escreve no endereço
                code += ["STORE 0"]
            else:
                name  = target[1]
                info  = self._sym.lookup(name)
                idx   = info["index"]
                ttype = info["type"]
                code += ["READ"]
                code += ["ATOF"] if ttype == "REAL" else ["ATOI"]
                code += [self._store_var(idx)]
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
    
    def _gen_array_access(self, name: str, index_args: list) -> list[str]:
        info = self._sym.lookup(name)
        base = info["index"]
        code  = [self._push_var(base)]   # endereço base do array
        code += self._gen(index_args[0]) # índice I
        code += ["PUSHI 1", "SUB"]       # I - 1
        code += ["PADD"]                 # endereço do elemento
        code += ["LOAD 0"]               # lê o valor
        return code

    # ── DO loop header ───────────────────────────────────────────────────

    def _gen_do_header(self, end_label_num, var_name,
                       start_expr, stop_expr, step_expr) -> list[str]:
        info      = self._sym.lookup(var_name)
        idx       = info["index"]
        start_lbl = self._sym.new_label("DOSTART")
        end_lbl   = self._sym.new_label("DOEND")

        # Initialise loop variable
        code  = self._gen(start_expr) + [self._store_var(idx)]
        code += [f"{start_lbl}:"]

        # Loop condition: var <= stop  (or var >= stop for negative step)
        code += [self._push_var(idx)]
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
            return [f"L{label_num}:"] + inner_code

        tail = []
        while self._sym.has_do():
            di    = self._sym.pop_do()
            tail += self._gen_do_step(di)
            tail += [f"JUMP {di['start_label']}", f"{di['end_label']}:"]
            if di is do_info:
                break

        return [f"L{label_num}:"] + inner_code + tail
    

    def _gen_do_step(self, do_info: dict) -> list[str]:
        idx  = do_info["var_index"]
        step = do_info["step_expr"]
        return [self._push_var(idx)] + self._gen(step) + ["ADD", self._store_var(idx)]

    # ── variable load ────────────────────────────────────────────────────

    def _gen_load(self, name: str) -> list[str]:
        idx = self._sym.lookup(name)["index"]
        return [self._push_var(idx)]

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
        if op in (".NOT.", "NOT"):
            return code + ["NOT"]
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
    
    #nova função
    def _gen_function(self, node) -> list[str]:
        _, return_type, name, params, body = node

        # guarda contexto global
        old_sym        = self._sym
        old_in_func    = self._in_function
        old_return_var = self._return_var

        # entra no contexto local
        self._local_sym   = _GenSymbols()
        self._sym         = self._local_sym
        self._in_function = True
        self._return_var  = name
        self._sym.register(name, return_type, size=1)

        # registar parâmetros com índices negativos
        for i, param in enumerate(reversed(params)):
            self._sym._vars[param] = {
                "index": -(i + 1),
                "type":  None,
                "size":  1,
            }

        # primeiro passe — regista variáveis declaradas
        for stmt in body:
            if isinstance(stmt, tuple) and stmt[0] == "declaration":
                var_type = stmt[1]
                for var_node in stmt[2]:
                    if var_node[0] == "var":
                        # não re-registar parâmetros já registados
                        if var_node[1] not in self._sym._vars:
                            self._sym.register(var_node[1], var_type, size=1)
                        else:
                            # actualiza o tipo do parâmetro
                            self._sym._vars[var_node[1]]["type"] = var_type
                    elif var_node[0] == "array_decl":
                        size = 1
                        for dim in var_node[2]:
                            size *= dim
                        self._sym.register(var_node[1], var_type, size=size)

        # aloca slots locais (só variáveis com índice >= 0)
        num_local = sum(
            v["size"] for v in self._sym._vars.values() if v["index"] >= 0
        )
        alloc = ["PUSHI 0"] * num_local

        # gera o corpo
        body_code = []
        for stmt in body:
            if isinstance(stmt, tuple) and stmt[0] == "declaration":
                continue
            body_code += self._gen(stmt)

        # restaura contexto global
        self._sym         = old_sym
        self._in_function = old_in_func
        self._return_var  = old_return_var

        return [f"{name}:"] + alloc + body_code

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