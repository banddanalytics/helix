"""CLI entry point for AST/KCH hallucination detection.

Usage:
    python scripts/ast_validator.py --stubs stubs/ --source src/

Exit codes:
    0 — no CRITICAL violations found
    1 — one or more CRITICAL violations found
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure project root is on sys.path when run as a script
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.quality.ast_validator.validator import KCHValidator


def main(argv: list[str] | None = None) -> int:
    """Run the KCH validator CLI.

    Args:
        argv: argument list (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0 if clean, 1 if CRITICAL violations found.
    """
    parser = argparse.ArgumentParser(
        description="Helix KCH Validator — detect phantom API calls in Python source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/ast_validator.py --stubs stubs/ --source src/\n"
            "  python scripts/ast_validator.py --stubs stubs/ --source src/alpha/\n"
        ),
    )
    parser.add_argument(
        "--stubs",
        required=True,
        type=Path,
        metavar="DIR",
        help="Directory containing *_stubs.py ground-truth files.",
    )
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        metavar="DIR",
        help="Source directory to scan (recursive).",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json).",
    )

    args = parser.parse_args(argv)

    stub_dir: Path = args.stubs.resolve()
    source_dir: Path = args.source.resolve()

    if not stub_dir.is_dir():
        print(f"ERROR: stubs directory not found: {stub_dir}", file=sys.stderr)
        return 1
    if not source_dir.is_dir():
        print(f"ERROR: source directory not found: {source_dir}", file=sys.stderr)
        return 1

    validator = KCHValidator(stub_dir)
    violations = validator.validate_directory(source_dir)

    if args.format == "json":
        output = json.dumps([asdict(v) for v in violations], indent=2)
        print(output)
    else:
        if not violations:
            print("No violations found.")
        else:
            for v in violations:
                print(f"[{v.severity}] {v.violation_type} {v.file}:{v.line} — {v.message}")
                if v.suggestion:
                    print(f"  Suggestion: {v.suggestion}")

    has_critical = any(v.severity == "CRITICAL" for v in violations)
    return 1 if has_critical else 0


if __name__ == "__main__":
    sys.exit(main())
