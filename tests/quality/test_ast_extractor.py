"""Tests for ASTExtractor — import/call/attribute extraction from Python ASTs."""

from __future__ import annotations

import textwrap

import pytest

from src.quality.ast_validator import ASTExtractor


class TestASTExtractorImports:
    """Tests for import statement extraction."""

    def test_extract_simple_import(self) -> None:
        code = "import arcticdb"
        extractor = ASTExtractor()
        extractor.extract(code)
        assert "arcticdb" in extractor.imports

    def test_extract_from_import(self) -> None:
        code = "from arcticdb import Arctic"
        extractor = ASTExtractor()
        extractor.extract(code)
        assert "arcticdb.Arctic" in extractor.imports

    def test_extract_multiple_imports(self) -> None:
        code = textwrap.dedent("""\
            import zmq
            import arcticdb
            from pathlib import Path
        """)
        extractor = ASTExtractor()
        extractor.extract(code)
        assert "zmq" in extractor.imports
        assert "arcticdb" in extractor.imports
        assert "pathlib.Path" in extractor.imports

    def test_extract_aliased_import(self) -> None:
        code = "import numpy as np"
        extractor = ASTExtractor()
        extractor.extract(code)
        assert "numpy" in extractor.imports

    def test_extract_from_import_multiple_names(self) -> None:
        code = "from os.path import join, exists"
        extractor = ASTExtractor()
        extractor.extract(code)
        assert "os.path.join" in extractor.imports
        assert "os.path.exists" in extractor.imports

    def test_no_imports(self) -> None:
        code = "x = 1 + 2"
        extractor = ASTExtractor()
        extractor.extract(code)
        assert extractor.imports == []


class TestASTExtractorFunctionCalls:
    """Tests for function/method call extraction."""

    def test_extract_simple_function_call(self) -> None:
        code = "print('hello')"
        extractor = ASTExtractor()
        extractor.extract(code)
        funcs = [c["func"] for c in extractor.function_calls]
        assert "print" in funcs

    def test_extract_method_call(self) -> None:
        code = "lib.write(symbol='EURUSD', data=df)"
        extractor = ASTExtractor()
        extractor.extract(code)
        funcs = [c["func"] for c in extractor.function_calls]
        assert "write" in funcs

    def test_extract_kwargs(self) -> None:
        code = "lib.write(symbol='EURUSD', data=df)"
        extractor = ASTExtractor()
        extractor.extract(code)
        write_calls = [c for c in extractor.function_calls if c["func"] == "write"]
        assert len(write_calls) == 1
        assert "symbol" in write_calls[0]["kwargs"]
        assert "data" in write_calls[0]["kwargs"]

    def test_extract_lineno(self) -> None:
        code = textwrap.dedent("""\
            x = 1
            lib.write(symbol='EURUSD')
        """)
        extractor = ASTExtractor()
        extractor.extract(code)
        write_calls = [c for c in extractor.function_calls if c["func"] == "write"]
        assert len(write_calls) == 1
        assert write_calls[0]["lineno"] == 2

    def test_extract_call_no_kwargs(self) -> None:
        code = "mt5.shutdown()"
        extractor = ASTExtractor()
        extractor.extract(code)
        shutdown_calls = [c for c in extractor.function_calls if c["func"] == "shutdown"]
        assert len(shutdown_calls) == 1
        assert shutdown_calls[0]["kwargs"] == set()

    def test_extract_nested_calls(self) -> None:
        code = "result = lib.read(lib.list_symbols()[0])"
        extractor = ASTExtractor()
        extractor.extract(code)
        funcs = [c["func"] for c in extractor.function_calls]
        assert "read" in funcs
        assert "list_symbols" in funcs

    def test_no_function_calls(self) -> None:
        code = "x = 1 + 2"
        extractor = ASTExtractor()
        extractor.extract(code)
        assert extractor.function_calls == []


class TestASTExtractorAttributeAccesses:
    """Tests for attribute access extraction."""

    def test_extract_attribute_access(self) -> None:
        code = "value = obj.attribute"
        extractor = ASTExtractor()
        extractor.extract(code)
        attrs = [(a["obj"], a["attr"]) for a in extractor.attribute_accesses]
        assert ("obj", "attribute") in attrs

    def test_extract_chained_attribute(self) -> None:
        code = "value = mt5.TIMEFRAME_M1"
        extractor = ASTExtractor()
        extractor.extract(code)
        attrs = [(a["obj"], a["attr"]) for a in extractor.attribute_accesses]
        assert ("mt5", "TIMEFRAME_M1") in attrs

    def test_extract_attribute_lineno(self) -> None:
        code = textwrap.dedent("""\
            x = 1
            y = obj.attr
        """)
        extractor = ASTExtractor()
        extractor.extract(code)
        attr_entries = [a for a in extractor.attribute_accesses if a["attr"] == "attr"]
        assert len(attr_entries) >= 1
        assert attr_entries[0]["lineno"] == 2


class TestASTExtractorEdgeCases:
    """Tests for edge cases and error handling."""

    def test_extract_empty_code(self) -> None:
        extractor = ASTExtractor()
        extractor.extract("")
        assert extractor.imports == []
        assert extractor.function_calls == []
        assert extractor.attribute_accesses == []

    def test_extract_resets_on_new_call(self) -> None:
        extractor = ASTExtractor()
        extractor.extract("import zmq")
        extractor.extract("import arcticdb")
        # Only the second extract's imports should be present
        assert "arcticdb" in extractor.imports
        assert "zmq" not in extractor.imports

    def test_extract_syntax_error_raises(self) -> None:
        extractor = ASTExtractor()
        with pytest.raises(SyntaxError):
            extractor.extract("def broken(:")

    def test_extract_multiline_code(self) -> None:
        code = textwrap.dedent("""\
            import arcticdb
            from pathlib import Path

            store = arcticdb.Arctic('s3://bucket')
            lib = store.get_library('ticks')
            lib.write(symbol='EURUSD', data=None)
        """)
        extractor = ASTExtractor()
        extractor.extract(code)
        assert "arcticdb" in extractor.imports
        assert "pathlib.Path" in extractor.imports
        funcs = [c["func"] for c in extractor.function_calls]
        assert "write" in funcs
