"""Regenerate the JSON twins under the dialect examples in the context packs.

The python fences in ``context/games.md``, ``context/clones.md`` and
``context/scrolling.md`` are the canonical examples.  Each one is transpiled by
the same front end the model's replies go through and the resulting change
object(s) are inserted as a JSON twin under a marker comment, so JSON mode and
the docs cannot drift from the dialect.

Run after editing an example:

    python tools/render_pack_json.py           # rewrite all twins
    python tools/render_pack_json.py --check   # exit 1 when out of sync
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import pack_examples as pe  # noqa: E402


def _twin_text(python_source: str, pack_name: str) -> str:
    """Render one fence's twin: an object for one change, an array for many."""
    changes = pe.render_example_json(python_source, pack_name)
    payload = changes[0] if len(changes) == 1 else changes
    return "```json\n" + json.dumps(payload, indent=2, ensure_ascii=True) + "\n```"


def render_pack(name: str) -> str:
    """Return the pack text with every twin regenerated from its python fence."""
    text = pe.strip_twins(pe.read_pack(name))

    def replace(match: "re.Match[str]") -> str:
        source = match.group(1)
        return (
            match.group(0)
            + "\n"
            + pe.TWIN_MARKER
            + "\n"
            + _twin_text(source, name)
        )

    return pe.PYTHON_FENCE_RE.sub(replace, text)


def write_pack(name: str) -> None:
    """Rewrite one pack in place, preserving LF line endings."""
    path = pe.pack_path(name)
    text = render_pack(name)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def check_pack(name: str) -> str:
    """Return an empty string when in sync, else a short unified diff."""
    current = pe.read_pack(name)
    expected = render_pack(name)
    if current == expected:
        return ""
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile=f"context/{name}.md (current)",
        tofile=f"context/{name}.md (regenerated)",
        n=2,
    )
    lines = list(diff)
    limit = 40
    if len(lines) > limit:
        lines = lines[:limit] + ["... diff truncated ...\n"]
    return "".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report packs whose JSON twins are out of date instead of writing",
    )
    parser.add_argument(
        "packs",
        nargs="*",
        # No ``choices=`` here: Python 3.11's argparse rejects an empty
        # positional list against ``choices``, so ``--check`` with no pack
        # names would exit 2 there while 3.13 accepts it. The names are
        # validated manually below with the same message on every version.
        default=None,
        help="packs to process (default: all packs with examples)",
    )
    args = parser.parse_args(argv)
    known = sorted(pe.PACKS)
    unknown = [name for name in (args.packs or []) if name not in known]
    if unknown:
        parser.error(
            "argument packs: invalid choice: "
            + ", ".join(repr(name) for name in unknown)
            + f" (choose from {', '.join(known)})"
        )
    names = args.packs or known

    if args.check:
        failed = False
        for name in names:
            diff = check_pack(name)
            if diff:
                failed = True
                print(f"context/{name}.md: JSON twins are out of date")
                print(diff)
            else:
                print(f"context/{name}.md: in sync")
        return 1 if failed else 0

    for name in names:
        write_pack(name)
        print(f"context/{name}.md: twins regenerated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
