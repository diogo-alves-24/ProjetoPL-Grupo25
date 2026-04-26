class SymbolTableError(ValueError):
    pass


class SymbolTable:
    def __init__(self):
        # Scope global com builtins
        self.scopes = [
            {
                "mod": {
                    "kind": "callable",
                    "name": "MOD",
                    "return_type": "INTEGER",
                    "params": ["INTEGER", "INTEGER"],
                    "builtin": True,
                }
            }
        ]

    # -------------------------
    # Scopes
    # -------------------------

    def new_scope(self):
        self.scopes.append({})

    def unstack_top_scope(self):
        if len(self.scopes) == 1:
            raise SymbolTableError("Cannot remove global scope")
        self.scopes.pop()

    # -------------------------
    # Query genérica
    # -------------------------

    def query(self, identifier, error=False, target_object_name="Object"):
        identifier_lower = str(identifier).lower()

        for i, scope in enumerate(reversed(self.scopes)):
            result = scope.get(identifier_lower)
            if result is not None:
                return result, i == 0  # scope mais interno?

        if error:
            raise SymbolTableError(f"{target_object_name} '{identifier}' not found")

        return None, False

    # -------------------------
    # Queries específicas
    # -------------------------

    def query_label(self, identifier, error=False):
        result, top_scope = self.query(str(identifier), error, "Label")

        if result is None:
            return None

        if result["kind"] != "label":
            raise SymbolTableError(f"Object '{identifier}' is not a label")

        if not top_scope:
            raise SymbolTableError(f"Label '{identifier}' not in the top-most scope")

        return result

    def query_variable(self, identifier, error=False):
        result, top_scope = self.query(identifier, error, "Variable")

        if result is None:
            return None, False

        if result["kind"] not in ("variable", "array"):
            raise SymbolTableError(f"Object '{identifier}' is not a variable")

        return result, top_scope

    def query_callable(self, identifier, error=False):
        result, top_scope = self.query(identifier, error, "Callable")

        if result is None:
            return None, False

        if result["kind"] != "callable":
            raise SymbolTableError(f"Object '{identifier}' is not a callable")

        return result, top_scope

    def query_constant(self, identifier, error=False):
        result, top_scope = self.query(identifier, error, "Constant")

        if result is None:
            return None, False

        if result["kind"] != "constant":
            raise SymbolTableError(f"Object '{identifier}' is not a constant")

        return result, top_scope

    def query_type(self, identifier, error=False):
        result, top_scope = self.query(identifier, error, "Type")

        if result is None:
            return None, False

        if result["kind"] != "type":
            raise SymbolTableError(f"Object '{identifier}' is not a type")

        return result, top_scope

    # -------------------------
    # Add
    # -------------------------

    def add(self, value):
        """
        value é um dict, por exemplo:
            {"kind": "variable", "name": "A", "type": "INTEGER"}
            {"kind": "array", "name": "NUMS", "type": "INTEGER", "dims": [5]}
            {"kind": "callable", "name": "CONVRT", "return_type": "INTEGER", "params": [...]}
            {"kind": "label", "name": "20", "statement": ...}
        """
        name = str(value["name"]).lower()
        query_result, top_scope = self.query(name)

        if query_result is not None:
            if top_scope:
                raise SymbolTableError(f"Object with name '{name}' already exists in this scope")
            else:
                # shadowing permitido
                self.scopes[-1][name] = value
        else:
            self.scopes[-1][name] = value