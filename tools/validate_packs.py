"""Offline validation for the change-set examples in the context packs.

Every ``python`` fence in ``context/games.md``, ``context/clones.md`` and
``context/scrolling.md`` is canonical; the ``json`` fence under it is generated
by ``tools/render_pack_json.py``. This tool extracts those generated twins,
prepends the sprites/variables/lists the examples assume, and runs the result
through ``validate_changeset`` + ``compile_changeset`` exactly like a real model
turn. A pack whose own examples fail validation teaches the model bad output.

Usage: python tools/validate_packs.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import pack_examples as pe  # noqa: E402

from harness.block_ir import Change, ChangeSet  # noqa: E402
from harness.changeset import compile_changeset  # noqa: E402
from harness.context import ProjectContext  # noqa: E402
from harness.validator import validate_changeset  # noqa: E402


def pack_changes(name: str) -> tuple[ChangeSet, int]:
    """Build one pack's SETUP + generated twins as a single change set."""
    spec = pe.pack_spec(name)
    twins = pe.json_fences(pe.read_pack(name))
    raw_changes: list[dict] = [dict(item) for item in spec.setup]
    for block in twins:
        loaded = json.loads(block)
        if isinstance(loaded, list):
            raw_changes.extend(loaded)
        else:
            raw_changes.append(loaded)
    changeset = ChangeSet(
        summary=f"{name} pack smoke test",
        changes=[Change.from_dict(raw) for raw in raw_changes],
        notes="",
    )
    return changeset, len(twins)


def main() -> int:
    failed = False
    for name in sorted(pe.PACKS):
        changeset, twins = pack_changes(name)
        print(
            f"context/{name}.md: {twins} JSON example(s), "
            f"{len(changeset.changes)} changes with SETUP"
        )
        issues = validate_changeset(changeset, ProjectContext.demo())
        if issues:
            failed = True
            print(f"  VALIDATION ISSUES ({len(issues)}):")
            for issue in issues:
                print(f"    - {issue}")
            continue
        compiled = compile_changeset(changeset, ProjectContext.demo())
        print("  all patterns validate and compile cleanly")
        print("  " + "\n  ".join(compiled.chat_summary().splitlines()))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
