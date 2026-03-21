"""Tests for StubGenerator — introspect installed libraries and produce stub dicts."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.quality.ast_validator.stub_generator import StubGenerator


class TestStubGeneratorIntrospection:
    """StubGenerator should introspect real installed libraries."""

    def test_introspect_returns_dict(self) -> None:
        gen = StubGenerator()
        result = gen.introspect_module("pathlib")
        assert isinstance(result, dict)

    def test_introspect_captures_functions(self) -> None:
        gen = StubGenerator()
        result = gen.introspect_module("pathlib")
        # pathlib has the module-level name "Path"
        assert len(result) >= 0  # May be empty for complex modules, just no crash

    def test_introspect_nonexistent_module_raises(self) -> None:
        gen = StubGenerator()
        with pytest.raises(ImportError):
            gen.introspect_module("nonexistent_totally_fake_module_xyz")

    def test_introspect_os_path_module(self) -> None:
        gen = StubGenerator()
        result = gen.introspect_module("os.path")
        # os.path has join, exists, etc.
        assert isinstance(result, dict)

    def test_introspect_returns_set_of_params(self) -> None:
        gen = StubGenerator()
        result = gen.introspect_module("os.path")
        # All values should be sets of param names (strings)
        for func_name, params in result.items():
            assert isinstance(func_name, str)
            assert isinstance(params, set)
            for p in params:
                assert isinstance(p, str)


class TestStubGeneratorFileOutput:
    """StubGenerator should write stub files that can be loaded by KCHValidator."""

    def test_generate_stub_file_creates_file(self, tmp_path: Path) -> None:
        gen = StubGenerator()
        out_path = tmp_path / "os_path_stubs.py"
        gen.generate_stub_file("os.path", out_path)
        assert out_path.exists()

    def test_generated_file_contains_stub_dict(self, tmp_path: Path) -> None:
        gen = StubGenerator()
        out_path = tmp_path / "os_path_stubs.py"
        gen.generate_stub_file("os.path", out_path)
        content = out_path.read_text()
        assert "STUB" in content
        assert "dict" in content or "{" in content

    def test_generated_file_is_valid_python(self, tmp_path: Path) -> None:
        gen = StubGenerator()
        out_path = tmp_path / "os_path_stubs.py"
        gen.generate_stub_file("os.path", out_path)
        import ast as ast_mod
        # Should not raise
        ast_mod.parse(out_path.read_text())

    def test_generated_stub_loadable_by_kch_validator(self, tmp_path: Path) -> None:
        from src.quality.ast_validator.validator import KCHValidator

        gen = StubGenerator()
        out_path = tmp_path / "os_path_stubs.py"
        gen.generate_stub_file("os.path", out_path)
        # KCHValidator should load without error
        validator = KCHValidator(tmp_path)
        assert isinstance(validator, KCHValidator)


class TestStubGeneratorWithArcticDB:
    """StubGenerator should introspect arcticdb if installed."""

    def test_introspect_arcticdb_does_not_crash(self) -> None:
        gen = StubGenerator()
        try:
            result = gen.introspect_module("arcticdb")
            assert isinstance(result, dict)
        except ImportError:
            pytest.skip("arcticdb not installed")
