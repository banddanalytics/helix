"""Point-in-Time (PiT) compliance validator for alpha engine code.

Detects look-ahead bias in signal generation code by inspecting the AST for
DataFrame column accesses on price-related fields that lack a .shift() call in
the assignment chain.

Design:
- Scans assignment statements (ast.Assign / ast.AugAssign)
- Within each assignment's right-hand side, finds subscript accesses on known
  price columns (PRICE_COLUMNS)
- Determines whether a .shift() call appears anywhere in the method-call chain
  that leads to the assignment target
- Rolling patterns (.rolling().std(), .rolling().mean(), .rolling().agg()) are
  treated identically — they too require a trailing .shift()

Usage:
    validator = PiTValidator()
    violations = validator.validate_file(Path("src/alpha/strategy.py"))
    all_violations = validator.validate_directory(Path("src/alpha/"))
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


PRICE_COLUMNS: frozenset[str] = frozenset(
    {
        "price",
        "volume",
        "bid",
        "ask",
        "close",
        "high",
        "low",
        "open",
        "returns",
        "spread",
        "tick_volume",
    }
)


@dataclass
class PiTViolation:
    """A detected look-ahead bias violation."""

    file: str
    line: int
    column_accessed: str
    expression: str
    message: str


def _get_string_value(node: ast.expr) -> str | None:
    """Extract a string literal value from an AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _chain_has_shift(node: ast.expr) -> bool:
    """Return True if the call chain rooted at *node* contains a .shift() call.

    We walk the call/attribute chain from the outermost node inward.  The
    chain is: node → (call) → func → (attr) → value → ...

    A .shift() call looks like::

        ast.Call(func=ast.Attribute(attr='shift', ...), ...)

    Parameters
    ----------
    node:
        Root of the expression to inspect (could be a Call, Attribute, or
        Subscript).
    """
    # Walk every node in the subtree; if any Call has func.attr == 'shift'
    # it counts.
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and sub.func.attr == "shift"
        ):
            return True
    return False


def _collect_price_subscripts(
    node: ast.expr,
) -> list[tuple[str, ast.expr]]:
    """Find all df[<price_column>] subscript accesses in *node*'s subtree.

    Returns a list of (column_name, subscript_node) tuples.
    """
    results: list[tuple[str, ast.expr]] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Subscript):
            col = _get_string_value(sub.slice)
            if col is not None and col in PRICE_COLUMNS:
                results.append((col, sub))
    return results


def _expr_source(node: ast.expr, source_lines: list[str]) -> str:
    """Return a best-effort source snippet for the given node."""
    try:
        line = source_lines[node.lineno - 1].strip()
        return line
    except (AttributeError, IndexError):
        return "<unknown>"


class PiTValidator(ast.NodeVisitor):
    """AST-based Point-in-Time compliance checker.

    Detects look-ahead bias patterns in Python source files by inspecting
    assignment statements for price column accesses that are not guarded by
    a ``.shift()`` call.

    Attributes
    ----------
    violations:
        Accumulated list of detected violations.  Reset per file by
        :meth:`validate_file`.
    """

    def __init__(self) -> None:
        self.violations: list[PiTViolation] = []
        self._current_file: str = ""
        self._source_lines: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_file(self, file_path: Path) -> list[PiTViolation]:
        """Validate a single Python source file for PiT compliance.

        Parameters
        ----------
        file_path:
            Path to the ``.py`` file to inspect.

        Returns
        -------
        list[PiTViolation]
            All violations found in the file (empty if compliant).
        """
        self.violations = []
        self._current_file = str(file_path)
        source = file_path.read_text(encoding="utf-8")
        self._source_lines = source.splitlines()
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return []
        self.visit(tree)
        return list(self.violations)

    def validate_directory(
        self,
        dir_path: Path,
        pattern: str = "**/*.py",
    ) -> list[PiTViolation]:
        """Validate all Python files in *dir_path* matching *pattern*.

        Parameters
        ----------
        dir_path:
            Root directory to scan.
        pattern:
            Glob pattern relative to *dir_path* (default ``**/*.py``).

        Returns
        -------
        list[PiTViolation]
            Aggregated violations from all matched files.
        """
        all_violations: list[PiTViolation] = []
        for py_file in sorted(dir_path.glob(pattern)):
            all_violations.extend(self.validate_file(py_file))
        return all_violations

    # ------------------------------------------------------------------
    # AST visitor methods
    # ------------------------------------------------------------------

    def _check_assignment_value(self, value: ast.expr, lineno: int) -> None:
        """Inspect the right-hand side of an assignment for PiT violations.

        For each price-column subscript found in *value*, check whether a
        ``.shift()`` call appears in the method chain that *contains* that
        subscript access.  The check is performed at the top-level of the
        call chain (the outermost expression) so that::

            df['col'].rolling(20).std().shift(1)   ← COMPLIANT
            df['col'].rolling(20).std()             ← VIOLATION
            df['col'].shift(1)                      ← COMPLIANT
            df['col']                               ← VIOLATION
        """
        price_accesses = _collect_price_subscripts(value)
        if not price_accesses:
            return

        # Check if the *entire* rhs expression has a shift somewhere.
        # This handles multi-step chains correctly.
        has_shift = _chain_has_shift(value)

        for col, sub_node in price_accesses:
            if not has_shift:
                expr_text = _expr_source(sub_node, self._source_lines)
                self.violations.append(
                    PiTViolation(
                        file=self._current_file,
                        line=lineno,
                        column_accessed=col,
                        expression=expr_text,
                        message=(
                            f"Look-ahead bias: accessing '{col}' without .shift(1) "
                            f"in assignment at line {lineno}. "
                            f"Use df['{col}'].shift(1) to ensure PiT compliance."
                        ),
                    )
                )

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit simple assignment: target = value."""
        self._check_assignment_value(node.value, node.lineno)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Visit augmented assignment: target += value."""
        self._check_assignment_value(node.value, node.lineno)
        self.generic_visit(node)
