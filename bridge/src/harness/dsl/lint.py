"""Command-line lint for Scratch-Python files.

Usage::

    python -m harness.dsl.lint FILE [FILE ...]

Each file is checked against the dialect without a project context.  Exit
status is 0 when every file is clean and 1 when any diagnostic is reported.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .parse import lint as lint_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m harness.dsl.lint",
        description="Lint Scratch-Python source files.",
    )
    parser.add_argument("files", nargs="+", metavar="FILE")
    args = parser.parse_args(argv)

    clean = True
    for name in args.files:
        try:
            text = Path(name).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"{name}: error: {exc}")
            clean = False
            continue
        diagnostics = lint_source(text)
        if not diagnostics:
            print(f"{name}: OK")
            continue
        clean = False
        for diagnostic in diagnostics:
            for line in diagnostic.splitlines():
                print(f"{name}: {line}")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
