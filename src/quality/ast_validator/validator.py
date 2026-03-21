"""KCHValidator — detect phantom API calls against ground-truth library stubs.

Knowledge Conflicting Hallucination (KCH) detection pipeline.
Compares extracted API calls against stub files to find:
  - PHANTOM_FUNCTION (CRITICAL): calling a method that does not exist in the library
  - WRONG_PARAMETER (WARNING): passing an unknown kwarg with Levenshtein suggestion
  - PHANTOM_IMPORT (CRITICAL): importing a non-existent submodule of a known library
"""

from __future__ import annotations

import difflib
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from src.quality.ast_validator.extractor import ASTExtractor


@dataclass
class Violation:
    """A single KCH violation found during validation."""

    file: str
    line: int
    severity: str  # "CRITICAL" | "WARNING" | "INFO"
    # "PHANTOM_FUNCTION" | "WRONG_PARAMETER" | "PHANTOM_IMPORT" | "DEPRECATED_API"
    violation_type: str
    message: str
    suggestion: str | None = field(default=None)


# ---------------------------------------------------------------------------
# Internal stub representation
# ---------------------------------------------------------------------------
#
# Each *_stubs.py file exports:
#   STUB: dict[str, dict[str, set[str]]]
#       library_name -> { function_name -> set_of_valid_kwargs }
#
# Optionally:
#   SUBMODULES: list[str]
#       list of known public names importable from the top-level package
#


class KCHValidator:
    """Validate Python source files against ground-truth library stubs.

    Args:
        stub_dir: directory containing ``*_stubs.py`` files.
    """

    def __init__(self, stub_dir: Path) -> None:
        self._stub_dir = stub_dir
        # library_name -> { function_name -> set_of_valid_kwargs }
        self._stubs: dict[str, dict[str, set[str]]] = {}
        # library_name -> list of valid submodule/class names
        self._submodules: dict[str, list[str]] = {}
        self._load_stubs()

    # ------------------------------------------------------------------
    # Stub loading
    # ------------------------------------------------------------------

    def _load_stubs(self) -> None:
        """Import all ``*_stubs.py`` files and merge their STUB dicts."""
        for stub_path in sorted(self._stub_dir.glob("*_stubs.py")):
            module = self._import_stub_file(stub_path)
            stub_data: dict[str, dict[str, set[str]]] = getattr(module, "STUB", {})
            for lib, functions in stub_data.items():
                if lib not in self._stubs:
                    self._stubs[lib] = {}
                self._stubs[lib].update(functions)

            submodules: list[str] = getattr(module, "SUBMODULES", [])
            if submodules:
                # Use the first (and usually only) library key as the owner
                for lib in stub_data:
                    self._submodules.setdefault(lib, []).extend(submodules)

    @staticmethod
    def _import_stub_file(path: Path) -> ModuleType:
        """Dynamically import a stub file by path."""
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load stub file: {path}")
        module = importlib.util.module_from_spec(spec)
        # Give the module a unique name so it does not pollute sys.modules
        unique_name = f"_helix_stubs_{path.stem}_{id(path)}"
        sys.modules[unique_name] = module
        spec.loader.exec_module(module)
        return module

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_file(self, file_path: Path) -> list[Violation]:
        """Validate a single Python source file.

        Args:
            file_path: path to the ``.py`` file to scan.

        Returns:
            List of :class:`Violation` objects (may be empty).
        """
        source = file_path.read_text(encoding="utf-8")
        if not source.strip():
            return []

        extractor = ASTExtractor()
        try:
            extractor.extract(source)
        except SyntaxError:
            return []

        violations: list[Violation] = []
        imported_libs = self._imported_known_libs(extractor.imports)

        for call in extractor.function_calls:
            func_name: str = call["func"]
            kwargs: set[str] = call["kwargs"]
            lineno: int = call["lineno"]

            for lib in imported_libs:
                lib_funcs = self._stubs[lib]
                if func_name not in lib_funcs:
                    violations.append(
                        Violation(
                            file=str(file_path),
                            line=lineno,
                            severity="CRITICAL",
                            violation_type="PHANTOM_FUNCTION",
                            message=(
                                f"'{func_name}' is not a known method of '{lib}'. "
                                "This call may be a hallucinated phantom API."
                            ),
                        )
                    )
                else:
                    valid_kwargs = lib_funcs[func_name]
                    for kwarg in kwargs:
                        if valid_kwargs and kwarg not in valid_kwargs:
                            suggestion = self._suggest(kwarg, valid_kwargs)
                            violations.append(
                                Violation(
                                    file=str(file_path),
                                    line=lineno,
                                    severity="WARNING",
                                    violation_type="WRONG_PARAMETER",
                                    message=(
                                        f"Unknown keyword argument '{kwarg}' passed to "
                                        f"'{lib}.{func_name}'."
                                    ),
                                    suggestion=suggestion,
                                )
                            )

        # Check phantom imports (from library import NonExistentName)
        for imp in extractor.imports:
            for lib in list(self._stubs.keys()):
                prefix = lib + "."
                if imp.startswith(prefix):
                    name = imp[len(prefix) :]
                    known_names = self._submodules.get(lib, [])
                    if known_names and name not in known_names:
                        violations.append(
                            Violation(
                                file=str(file_path),
                                line=0,
                                severity="CRITICAL",
                                violation_type="PHANTOM_IMPORT",
                                message=(
                                    f"'{name}' is not a known export of '{lib}'. "
                                    "This import may reference a non-existent symbol."
                                ),
                            )
                        )

        return violations

    def validate_directory(self, dir_path: Path) -> list[Violation]:
        """Recursively validate all ``.py`` files under *dir_path*.

        Args:
            dir_path: directory to scan (recursive).

        Returns:
            Merged list of :class:`Violation` objects.
        """
        violations: list[Violation] = []
        for py_file in sorted(dir_path.rglob("*.py")):
            violations.extend(self.validate_file(py_file))
        return violations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _imported_known_libs(self, imports: list[str]) -> list[str]:
        """Return the subset of known library names that appear in *imports*."""
        matched: list[str] = []
        for lib in self._stubs:
            for imp in imports:
                # Match "arcticdb" in "arcticdb", "arcticdb.Arctic", etc.
                if (
                    imp == lib or imp.startswith(lib + ".") or imp.startswith(lib + " ")
                ) and lib not in matched:
                    matched.append(lib)
        return matched

    @staticmethod
    def _suggest(wrong: str, valid: set[str]) -> str | None:
        """Return the closest valid kwarg name using difflib, or *None*."""
        matches = difflib.get_close_matches(wrong, list(valid), n=1, cutoff=0.6)
        return matches[0] if matches else None
