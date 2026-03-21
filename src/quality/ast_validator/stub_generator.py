"""StubGenerator — introspect installed libraries and produce stub dicts.

Uses importlib and inspect.signature() to extract the real API surface.
For libraries not importable on Linux (MetaTrader5), hand-written stubs are used.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any


class StubGenerator:
    """Introspect installed Python libraries and generate KCH stub files.

    Usage::

        gen = StubGenerator()
        stubs = gen.introspect_module("arcticdb")
        gen.generate_stub_file("arcticdb", Path("stubs/arcticdb_stubs.py"))
    """

    def introspect_module(self, module_name: str) -> dict[str, set[str]]:
        """Introspect *module_name* and return ``{function_name: set_of_params}``.

        Args:
            module_name: Dotted module name, e.g. ``"arcticdb"`` or ``"os.path"``.

        Returns:
            Dict mapping callable names to their parameter name sets.

        Raises:
            ImportError: if the module cannot be imported.
        """
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            raise ImportError(f"Cannot import module '{module_name}': {exc}") from exc

        result: dict[str, set[str]] = {}
        for name, obj in inspect.getmembers(module):
            if name.startswith("_"):
                continue
            if callable(obj):
                try:
                    sig = inspect.signature(obj)
                    params: set[str] = {
                        p
                        for p, param in sig.parameters.items()
                        if p not in ("self", "cls")
                        and param.kind
                        not in (
                            inspect.Parameter.VAR_POSITIONAL,
                            inspect.Parameter.VAR_KEYWORD,
                        )
                    }
                    result[name] = params
                except (ValueError, TypeError):
                    # Some built-ins don't expose signatures — skip silently
                    result[name] = set()
        return result

    def generate_stub_file(self, module_name: str, output_path: Path) -> None:
        """Write a stub Python file for *module_name* at *output_path*.

        The generated file defines a ``STUB`` dict compatible with
        :class:`~src.quality.ast_validator.validator.KCHValidator`.

        Args:
            module_name: Dotted module name to introspect.
            output_path: Path where the stub file will be written.

        Raises:
            ImportError: if the module cannot be imported.
        """
        stubs = self.introspect_module(module_name)
        # Build the source representation
        lines: list[str] = [
            f'"""Auto-generated stub for {module_name}. Do not edit manually."""',
            "",
            "from __future__ import annotations",
            "",
            "STUB: dict[str, dict[str, set[str]]] = {",
            f'    "{module_name}": {{',
        ]
        for func_name, params in sorted(stubs.items()):
            if params:
                params_repr = "{" + ", ".join(f'"{p}"' for p in sorted(params)) + "}"
            else:
                params_repr = "set()"
            lines.append(f'        "{func_name}": {params_repr},')
        lines += [
            "    }",
            "}",
            "",
        ]
        output_path.write_text("\n".join(lines), encoding="utf-8")
