"""CLI entry point for the Point-in-Time compliance validator.

Scans Python source files for look-ahead bias (accessing price-related
DataFrame columns without a preceding .shift() call).

Usage::

    python scripts/pit_validator.py --source src/alpha/
    python scripts/pit_validator.py --source src/alpha/ --json

Exit codes:
    0 — all files compliant
    1 — one or more violations found
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.quality.pit_validator import PiTValidator  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Point-in-Time compliance checker for alpha engine code."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("src/alpha/"),
        help="Directory to scan (default: src/alpha/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output violations as JSON (default: human-readable)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the PiT validator CLI.

    Returns
    -------
    int
        Exit code: 0 if clean, 1 if any violation found.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    source_dir: Path = args.source
    if not source_dir.exists():
        print(f"ERROR: source directory does not exist: {source_dir}", file=sys.stderr)
        return 1

    validator = PiTValidator()
    violations = validator.validate_directory(source_dir)

    if args.output_json:
        output = [
            {
                "file": v.file,
                "line": v.line,
                "column_accessed": v.column_accessed,
                "expression": v.expression,
                "message": v.message,
            }
            for v in violations
        ]
        print(json.dumps(output, indent=2))
    else:
        if violations:
            print(f"PiT Compliance: {len(violations)} violation(s) found\n")
            for v in violations:
                print(f"  {v.file}:{v.line} [{v.column_accessed}]")
                print(f"    {v.message}")
                print()
        else:
            print("PiT Compliance: OK — no look-ahead bias detected.")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
