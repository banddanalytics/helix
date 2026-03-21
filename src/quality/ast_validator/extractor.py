"""ASTExtractor — walk Python ASTs to extract imports, calls, and attribute accesses.

D-15: Custom AST validator scans for phantom API calls against a whitelist of
known-valid API methods.
"""

from __future__ import annotations

import ast
from typing import Any


class ASTExtractor(ast.NodeVisitor):
    """Extract imports, function calls, and attribute accesses from Python source.

    Usage::

        extractor = ASTExtractor()
        extractor.extract(source_code)
        print(extractor.imports)
        print(extractor.function_calls)
        print(extractor.attribute_accesses)
    """

    def __init__(self) -> None:
        self.imports: list[str] = []
        self.function_calls: list[dict[str, Any]] = []
        self.attribute_accesses: list[dict[str, Any]] = []

    def extract(self, source: str) -> None:
        """Parse *source* and populate imports/function_calls/attribute_accesses.

        Raises:
            SyntaxError: if *source* is not valid Python.
        """
        # Reset state so each call is idempotent
        self.imports = []
        self.function_calls = []
        self.attribute_accesses = []

        tree = ast.parse(source)
        self.visit(tree)

    # ------------------------------------------------------------------
    # Import visitors
    # ------------------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        """Handle ``import X`` and ``import X as Y`` statements."""
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle ``from X import Y`` statements."""
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}" if module else alias.name)
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Call visitor
    # ------------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        """Extract function / method calls."""
        info = self._extract_call(node)
        if info is not None:
            self.function_calls.append(info)
        self.generic_visit(node)

    def _extract_call(self, node: ast.Call) -> dict[str, Any] | None:
        """Return a call descriptor dict or *None* if the call is unrecognisable."""
        kwargs: set[str] = {kw.arg for kw in node.keywords if kw.arg is not None}

        if isinstance(node.func, ast.Attribute):
            return {
                "func": node.func.attr,
                "kwargs": kwargs,
                "lineno": node.lineno,
            }
        if isinstance(node.func, ast.Name):
            return {
                "func": node.func.id,
                "kwargs": kwargs,
                "lineno": node.lineno,
            }
        return None

    # ------------------------------------------------------------------
    # Attribute access visitor
    # ------------------------------------------------------------------

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Extract attribute accesses like ``obj.attr``."""
        obj_name: str | None = None
        if isinstance(node.value, ast.Name):
            obj_name = node.value.id
        elif isinstance(node.value, ast.Attribute):
            obj_name = node.value.attr

        if obj_name is not None:
            self.attribute_accesses.append(
                {
                    "obj": obj_name,
                    "attr": node.attr,
                    "lineno": node.lineno,
                }
            )
        self.generic_visit(node)
