class TypeCheckerError(ValueError):
    pass


class TypeChecker:
    def get_constant_type(self, constant_node):
        """
        constant_node:
            ("int", n)
            ("float", x)
            ("string", s)
            ("bool", b)
        """
        tag = constant_node[0]

        if tag == "int":
            return "INTEGER"
        if tag == "float":
            return "REAL"
        if tag == "string":
            return "CHARACTER"
        if tag == "bool":
            return "LOGICAL"

        raise TypeCheckerError(f"Unknown constant node: {tag}")

    def get_unary_operation_type(self, operator, subtype):
        if operator in ("+", "-") and subtype in ("INTEGER", "REAL"):
            return subtype

        if operator == ".NOT." and subtype == "LOGICAL":
            return "LOGICAL"

        raise TypeCheckerError(f"Invalid type for unary operator '{operator}'")

    def get_binary_operation_type(self, operator, left_type, right_type):
        # aritméticos
        if operator in ("+", "-", "*"):
            if left_type in ("INTEGER", "REAL") and right_type in ("INTEGER", "REAL"):
                return "REAL" if "REAL" in (left_type, right_type) else "INTEGER"

        if operator == "/":
            if left_type in ("INTEGER", "REAL") and right_type in ("INTEGER", "REAL"):
                return "REAL"

        if operator == "**":
            if left_type in ("INTEGER", "REAL") and right_type in ("INTEGER", "REAL"):
                return "REAL" if "REAL" in (left_type, right_type) else "INTEGER"

        # lógicos
        if operator in (".AND.", ".OR."):
            if left_type == "LOGICAL" and right_type == "LOGICAL":
                return "LOGICAL"

        # relacionais
        if operator in (".EQ.", ".NE.", ".LT.", ".LE.", ".GT.", ".GE."):
            # comparação entre tipos iguais
            if left_type == right_type:
                return "LOGICAL"

            # INTEGER e REAL também são compatíveis em comparações
            if left_type in ("INTEGER", "REAL") and right_type in ("INTEGER", "REAL"):
                return "LOGICAL"

        raise TypeCheckerError(
            f"Invalid types for binary operator '{operator}': {left_type} and {right_type}"
        )

    def can_assign(self, left_type, right_type):
        if left_type == right_type:
            return True

        # promoção INTEGER -> REAL
        if left_type == "REAL" and right_type == "INTEGER":
            return True

        return False