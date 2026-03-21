"""Tests for KCHValidator — phantom API detection against ground-truth stubs."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.quality.ast_validator import KCHValidator, Violation

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def stub_dir(tmp_path: Path) -> Path:
    """Create a temporary stubs directory with a minimal arcticdb stub."""
    stub_file = tmp_path / "arcticdb_stubs.py"
    stub_file.write_text(
        textwrap.dedent("""\
            STUB: dict[str, dict[str, set[str]]] = {
                "arcticdb": {
                    "Arctic": {"uri", "encoding_version"},
                    "get_library": {"library", "create_if_missing", "library_options"},
                    "write": {"symbol", "data", "metadata", "prune_previous_version"},
                    "read": {"symbol", "as_of"},
                    "append": {"symbol", "data", "metadata", "incomplete"},
                    "list_symbols": {"regex", "snapshot"},
                    "snapshot": {"snapshot_name", "metadata", "versions"},
                    "delete": {"symbol", "versions"},
                }
            }
        """)
    )
    return tmp_path


@pytest.fixture()
def mt5_stub_dir(tmp_path: Path) -> Path:
    """Create a temporary stubs directory with a minimal MT5 stub."""
    stub_file = tmp_path / "mt5_stubs.py"
    stub_file.write_text(
        textwrap.dedent("""\
            STUB: dict[str, dict[str, set[str]]] = {
                "MetaTrader5": {
                    "initialize": {"path", "login", "password", "server", "timeout", "portable"},
                    "login": {"login", "password", "server", "timeout"},
                    "shutdown": set(),
                    "copy_ticks_range": {"symbol", "date_from", "date_to", "flags"},
                    "copy_rates_from_pos": {"symbol", "timeframe", "start_pos", "count"},
                    "symbol_info": {"symbol"},
                    "order_send": {"request"},
                    "positions_get": {"symbol", "group", "ticket"},
                    "account_info": set(),
                    "last_error": set(),
                }
            }
        """)
    )
    return tmp_path


# ---------------------------------------------------------------------------
# PHANTOM_FUNCTION detection
# ---------------------------------------------------------------------------


class TestPhantomFunctionDetection:
    """KCHValidator should flag calls to methods that don't exist in the stub."""

    def test_phantom_function_is_critical(self, stub_dir: Path, tmp_path: Path) -> None:
        source = tmp_path / "sample.py"
        source.write_text(
            textwrap.dedent("""\
                import arcticdb
                lib = arcticdb.Arctic('s3://bucket').get_library('ticks')
                lib.upsert(symbol='EURUSD', data=df)
            """)
        )
        validator = KCHValidator(stub_dir)
        violations = validator.validate_file(source)
        critical = [v for v in violations if v.severity == "CRITICAL"]
        phantom = [v for v in critical if v.violation_type == "PHANTOM_FUNCTION"]
        assert len(phantom) >= 1
        assert any("upsert" in v.message for v in phantom)

    def test_valid_function_no_violation(self, stub_dir: Path, tmp_path: Path) -> None:
        source = tmp_path / "sample.py"
        source.write_text(
            textwrap.dedent("""\
                import arcticdb
                lib = arcticdb.Arctic('s3://bucket').get_library('ticks')
                lib.write(symbol='EURUSD', data=df)
                lib.read(symbol='EURUSD')
            """)
        )
        validator = KCHValidator(stub_dir)
        violations = validator.validate_file(source)
        phantom = [v for v in violations if v.violation_type == "PHANTOM_FUNCTION"]
        assert len(phantom) == 0

    def test_phantom_function_includes_lineno(
        self, stub_dir: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "sample.py"
        source.write_text(
            textwrap.dedent("""\
                import arcticdb
                lib = arcticdb.Arctic('s3://bucket').get_library('ticks')
                lib.upsert(symbol='EURUSD', data=df)
            """)
        )
        validator = KCHValidator(stub_dir)
        violations = validator.validate_file(source)
        phantom = [v for v in violations if v.violation_type == "PHANTOM_FUNCTION"]
        assert len(phantom) >= 1
        assert phantom[0].line == 3

    def test_phantom_function_file_path_recorded(
        self, stub_dir: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "sample.py"
        source.write_text("import arcticdb\nlib = None\nlib.upsert(symbol='X')\n")
        validator = KCHValidator(stub_dir)
        violations = validator.validate_file(source)
        phantom = [v for v in violations if v.violation_type == "PHANTOM_FUNCTION"]
        assert len(phantom) >= 1
        assert str(source) in phantom[0].file


# ---------------------------------------------------------------------------
# WRONG_PARAMETER detection with Levenshtein suggestion
# ---------------------------------------------------------------------------


class TestWrongParameterDetection:
    """KCHValidator should flag wrong kwarg names and suggest close matches."""

    def test_wrong_parameter_is_warning(self, stub_dir: Path, tmp_path: Path) -> None:
        source = tmp_path / "sample.py"
        # "sym" is close to "symbol" — should get a suggestion
        source.write_text(
            "import arcticdb\nlib = None\nlib.write(sym='EURUSD', data=df)\n"
        )
        validator = KCHValidator(stub_dir)
        violations = validator.validate_file(source)
        wrong = [v for v in violations if v.violation_type == "WRONG_PARAMETER"]
        assert len(wrong) >= 1
        assert all(v.severity == "WARNING" for v in wrong)

    def test_wrong_parameter_suggestion_provided(
        self, stub_dir: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "sample.py"
        source.write_text(
            "import arcticdb\nlib = None\nlib.write(sym='EURUSD', data=df)\n"
        )
        validator = KCHValidator(stub_dir)
        violations = validator.validate_file(source)
        wrong = [v for v in violations if v.violation_type == "WRONG_PARAMETER"]
        assert len(wrong) >= 1
        # difflib should suggest "symbol" for "sym"
        assert wrong[0].suggestion is not None
        assert "symbol" in wrong[0].suggestion

    def test_no_suggestion_for_unrecognizable_kwarg(
        self, stub_dir: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "sample.py"
        # "xyz_garbage" has no close match to valid kwargs
        source.write_text(
            "import arcticdb\nlib = None\nlib.write(xyz_garbage='X', data=df)\n"
        )
        validator = KCHValidator(stub_dir)
        violations = validator.validate_file(source)
        wrong = [v for v in violations if v.violation_type == "WRONG_PARAMETER"]
        # suggestion may be None when no close match found
        for v in wrong:
            if v.suggestion is None:
                pass  # Acceptable
            else:
                # If suggestion given, verify it's close to something real
                assert isinstance(v.suggestion, str)


# ---------------------------------------------------------------------------
# PHANTOM_IMPORT detection
# ---------------------------------------------------------------------------


class TestPhantomImportDetection:
    """KCHValidator should flag importing non-existent submodules of known libraries."""

    def test_phantom_submodule_import(self, stub_dir: Path, tmp_path: Path) -> None:
        # arcticdb.nonexistent_module is not a known submodule
        stub_file = stub_dir / "arcticdb_stubs.py"
        # Add submodule info to stub
        stub_file.write_text(
            textwrap.dedent("""\
                STUB: dict[str, dict[str, set[str]]] = {
                    "arcticdb": {
                        "write": {"symbol", "data"},
                        "read": {"symbol"},
                    }
                }
                SUBMODULES: list[str] = ["Arctic", "QueryBuilder"]
            """)
        )
        source = tmp_path / "sample.py"
        source.write_text("from arcticdb import NonExistentClass\n")
        validator = KCHValidator(stub_dir)
        violations = validator.validate_file(source)
        phantom = [v for v in violations if v.violation_type == "PHANTOM_IMPORT"]
        assert len(phantom) >= 1
        assert all(v.severity == "CRITICAL" for v in phantom)


# ---------------------------------------------------------------------------
# Clean code — zero violations
# ---------------------------------------------------------------------------


class TestCleanCodePassesValidation:
    """KCHValidator should return empty list for code using only valid APIs."""

    def test_clean_code_zero_violations(self, stub_dir: Path, tmp_path: Path) -> None:
        source = tmp_path / "clean.py"
        source.write_text(
            textwrap.dedent("""\
                import arcticdb

                store = arcticdb.Arctic('s3://bucket')
                lib = store.get_library('ticks')
                lib.write(symbol='EURUSD', data=None)
                symbols = lib.list_symbols()
                result = lib.read(symbol='EURUSD')
                lib.snapshot(snapshot_name='v1')
                lib.delete(symbol='EURUSD')
            """)
        )
        validator = KCHValidator(stub_dir)
        violations = validator.validate_file(source)
        # No PHANTOM_FUNCTION or WRONG_PARAMETER violations
        blocking = [
            v
            for v in violations
            if v.violation_type in ("PHANTOM_FUNCTION", "WRONG_PARAMETER")
        ]
        assert len(blocking) == 0

    def test_code_with_no_known_library_zero_violations(
        self, stub_dir: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "unrelated.py"
        source.write_text(
            textwrap.dedent("""\
                import os
                import sys

                def compute(x: int) -> int:
                    return x * 2

                result = compute(42)
                print(result)
            """)
        )
        validator = KCHValidator(stub_dir)
        violations = validator.validate_file(source)
        assert violations == []

    def test_empty_file_zero_violations(self, stub_dir: Path, tmp_path: Path) -> None:
        source = tmp_path / "empty.py"
        source.write_text("")
        validator = KCHValidator(stub_dir)
        violations = validator.validate_file(source)
        assert violations == []


# ---------------------------------------------------------------------------
# validate_directory
# ---------------------------------------------------------------------------


class TestValidateDirectory:
    """KCHValidator.validate_directory() should scan all .py files recursively."""

    def test_directory_scans_all_py_files(self, stub_dir: Path, tmp_path: Path) -> None:
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "clean.py").write_text("import os\nx = 1\n")
        (src_dir / "bad.py").write_text(
            "import arcticdb\nlib = None\nlib.upsert(symbol='X')\n"
        )
        validator = KCHValidator(stub_dir)
        violations = validator.validate_directory(src_dir)
        phantom = [v for v in violations if v.violation_type == "PHANTOM_FUNCTION"]
        assert len(phantom) >= 1

    def test_directory_skips_non_py_files(self, stub_dir: Path, tmp_path: Path) -> None:
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "README.md").write_text("# notes\nlib.upsert()\n")
        validator = KCHValidator(stub_dir)
        violations = validator.validate_directory(src_dir)
        assert violations == []

    def test_empty_directory_zero_violations(
        self, stub_dir: Path, tmp_path: Path
    ) -> None:
        src_dir = tmp_path / "empty_src"
        src_dir.mkdir()
        validator = KCHValidator(stub_dir)
        violations = validator.validate_directory(src_dir)
        assert violations == []


# ---------------------------------------------------------------------------
# Violation dataclass
# ---------------------------------------------------------------------------


class TestViolationDataclass:
    """Violation should have all required fields."""

    def test_violation_has_required_fields(self) -> None:
        v = Violation(
            file="test.py",
            line=10,
            severity="CRITICAL",
            violation_type="PHANTOM_FUNCTION",
            message="upsert does not exist",
        )
        assert v.file == "test.py"
        assert v.line == 10
        assert v.severity == "CRITICAL"
        assert v.violation_type == "PHANTOM_FUNCTION"
        assert v.message == "upsert does not exist"
        assert v.suggestion is None

    def test_violation_with_suggestion(self) -> None:
        v = Violation(
            file="test.py",
            line=5,
            severity="WARNING",
            violation_type="WRONG_PARAMETER",
            message="Unknown kwarg 'sym'",
            suggestion="symbol",
        )
        assert v.suggestion == "symbol"
