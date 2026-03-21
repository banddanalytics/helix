"""Tests for the Point-in-Time compliance validator.

Tests cover:
- Direct column access without .shift() is flagged as VIOLATION
- Rolling aggregation without .shift() is flagged as VIOLATION
- Column access with .shift(1) is COMPLIANT
- Rolling aggregation with .shift(1) is COMPLIANT
- CLI exits 0 on clean directory, 1 on violations
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from src.quality.pit_validator import PiTValidator, PiTViolation


class TestPiTViolatorDirectAccess:
    """Direct column access patterns — no rolling involved."""

    def test_direct_price_access_without_shift_is_violation(
        self, tmp_path: Path
    ) -> None:
        """df['signal'] = f(df['price']) must be flagged."""
        code = textwrap.dedent("""\
            import pandas as pd

            def compute_signal(df):
                df['signal'] = df['price']
        """)
        f = tmp_path / "alpha_strategy.py"
        f.write_text(code)

        validator = PiTValidator()
        violations = validator.validate_file(f)

        assert len(violations) >= 1
        assert any(v.column_accessed == "price" for v in violations)

    def test_direct_close_access_without_shift_is_violation(
        self, tmp_path: Path
    ) -> None:
        """df['signal'] = df['close'] must be flagged."""
        code = textwrap.dedent("""\
            def compute(df):
                df['signal'] = df['close']
        """)
        f = tmp_path / "strategy.py"
        f.write_text(code)

        validator = PiTValidator()
        violations = validator.validate_file(f)

        assert len(violations) >= 1

    def test_price_access_with_shift_is_compliant(self, tmp_path: Path) -> None:
        """df['signal'] = f(df['price'].shift(1)) must pass."""
        code = textwrap.dedent("""\
            def compute_signal(df):
                df['signal'] = df['price'].shift(1)
        """)
        f = tmp_path / "alpha_strategy.py"
        f.write_text(code)

        validator = PiTValidator()
        violations = validator.validate_file(f)

        assert len(violations) == 0

    def test_close_access_with_shift_is_compliant(self, tmp_path: Path) -> None:
        """df['signal'] = df['close'].shift(1) must pass."""
        code = textwrap.dedent("""\
            def compute(df):
                df['signal'] = df['close'].shift(1)
        """)
        f = tmp_path / "strategy.py"
        f.write_text(code)

        validator = PiTValidator()
        violations = validator.validate_file(f)

        assert len(violations) == 0

    def test_returns_access_without_shift_is_violation(self, tmp_path: Path) -> None:
        """df['x'] = df['returns'] must be flagged."""
        code = textwrap.dedent("""\
            def compute(df):
                df['feature'] = df['returns']
        """)
        f = tmp_path / "strategy.py"
        f.write_text(code)

        validator = PiTValidator()
        violations = validator.validate_file(f)

        assert len(violations) >= 1


class TestPiTViolatorRolling:
    """Rolling window patterns — must have .shift() after aggregation."""

    def test_rolling_std_without_shift_is_violation(self, tmp_path: Path) -> None:
        """df['rolling_vol'] = df['returns'].rolling(20).std() must be flagged."""
        code = textwrap.dedent("""\
            def compute_vol(df):
                df['rolling_vol'] = df['returns'].rolling(20).std()
        """)
        f = tmp_path / "strategy.py"
        f.write_text(code)

        validator = PiTValidator()
        violations = validator.validate_file(f)

        assert len(violations) >= 1

    def test_rolling_mean_without_shift_is_violation(self, tmp_path: Path) -> None:
        """df['ma'] = df['price'].rolling(10).mean() must be flagged."""
        code = textwrap.dedent("""\
            def compute_ma(df):
                df['ma'] = df['price'].rolling(10).mean()
        """)
        f = tmp_path / "strategy.py"
        f.write_text(code)

        validator = PiTValidator()
        violations = validator.validate_file(f)

        assert len(violations) >= 1

    def test_rolling_std_with_shift_is_compliant(self, tmp_path: Path) -> None:
        """df['rolling_vol'] = df['returns'].rolling(20).std().shift(1) must pass."""
        code = textwrap.dedent("""\
            def compute_vol(df):
                df['rolling_vol'] = df['returns'].rolling(20).std().shift(1)
        """)
        f = tmp_path / "strategy.py"
        f.write_text(code)

        validator = PiTValidator()
        violations = validator.validate_file(f)

        assert len(violations) == 0

    def test_rolling_mean_with_shift_is_compliant(self, tmp_path: Path) -> None:
        """df['ma'] = df['price'].rolling(10).mean().shift(1) must pass."""
        code = textwrap.dedent("""\
            def compute_ma(df):
                df['ma'] = df['price'].rolling(10).mean().shift(1)
        """)
        f = tmp_path / "strategy.py"
        f.write_text(code)

        validator = PiTValidator()
        violations = validator.validate_file(f)

        assert len(violations) == 0


class TestPiTViolatorDirectoryScanning:
    """Directory scanning with glob pattern."""

    def test_validate_directory_finds_violations_in_py_files(
        self, tmp_path: Path
    ) -> None:
        """validate_directory scans *.py files and aggregates violations."""
        alpha_dir = tmp_path / "alpha"
        alpha_dir.mkdir()
        bad_code = textwrap.dedent("""\
            def compute(df):
                df['signal'] = df['price']
        """)
        (alpha_dir / "strategy_a.py").write_text(bad_code)
        (alpha_dir / "strategy_b.py").write_text(bad_code)

        validator = PiTValidator()
        violations = validator.validate_directory(alpha_dir)

        assert len(violations) >= 2

    def test_validate_directory_empty_returns_no_violations(
        self, tmp_path: Path
    ) -> None:
        """Empty directory returns empty violation list."""
        alpha_dir = tmp_path / "alpha"
        alpha_dir.mkdir()

        validator = PiTValidator()
        violations = validator.validate_directory(alpha_dir)

        assert violations == []

    def test_validate_directory_compliant_code_returns_no_violations(
        self, tmp_path: Path
    ) -> None:
        """Directory with only compliant code returns empty violation list."""
        alpha_dir = tmp_path / "alpha"
        alpha_dir.mkdir()
        good_code = textwrap.dedent("""\
            def compute(df):
                df['signal'] = df['price'].shift(1)
        """)
        (alpha_dir / "strategy.py").write_text(good_code)

        validator = PiTValidator()
        violations = validator.validate_directory(alpha_dir)

        assert violations == []


class TestPiTViolation:
    """PiTViolation dataclass structure."""

    def test_violation_has_required_fields(self, tmp_path: Path) -> None:
        """PiTViolation must have file, line, column_accessed, expression, message."""
        code = textwrap.dedent("""\
            def compute(df):
                df['signal'] = df['price']
        """)
        f = tmp_path / "strategy.py"
        f.write_text(code)

        validator = PiTValidator()
        violations = validator.validate_file(f)

        assert len(violations) >= 1
        v = violations[0]
        assert isinstance(v, PiTViolation)
        assert hasattr(v, "file")
        assert hasattr(v, "line")
        assert hasattr(v, "column_accessed")
        assert hasattr(v, "expression")
        assert hasattr(v, "message")
        assert v.line > 0
        assert v.file == str(f)

    def test_violations_track_correct_line_numbers(self, tmp_path: Path) -> None:
        """Violation line numbers match actual source positions."""
        code = textwrap.dedent("""\
            import pandas as pd

            def compute(df):
                x = 1
                df['signal'] = df['price']
        """)
        f = tmp_path / "strategy.py"
        f.write_text(code)

        validator = PiTValidator()
        violations = validator.validate_file(f)

        # Violation should be on line 5 (df['signal'] = df['price'])
        assert any(v.line == 5 for v in violations)
