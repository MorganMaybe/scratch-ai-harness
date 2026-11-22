"""Offline validation for the JSON patterns in context/games.md.

Extracts every ```json fence from the pack, prepends the sprites/variables the
patterns assume (in top-down order), and runs the result through
validate_changeset + compile_changeset exactly like a real model turn.
Run this after editing the pack; a pack whose own examples fail validation
teaches the model bad output.

Usage: python tools/validate_games_pack.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge" / "src"))

from harness.block_ir import Change, ChangeSet  # noqa: E402
from harness.changeset import compile_changeset  # noqa: E402
from harness.context import ProjectContext  # noqa: E402
from harness.validator import validate_changeset  # noqa: E402

#: Sprites and variables the pack's patterns assume, in creation order.
#: `scored` is global here; the pack tells the model to create it before the
#: pipe scripts that use it.
SETUP = [
    {"action": "create_variable", "name": "vy", "scope": "global", "initial": 0},
    {"action": "create_variable", "name": "score", "scope": "global", "initial": 0},
    {"action": "create_variable", "name": "game_over", "scope": "global", "initial": 0},
    {"action": "create_variable", "name": "scored", "scope": "global", "initial": 0},
    {"action": "create_sprite", "name": "Cat", "costumes": [{"library": "Animals/dove1-a.png"}]},
    {"action": "create_sprite", "name": "Ground", "costumes": [{"library": "Scenery/rock.png"}], "x": 0, "y": -150, "size": 100},
    {"action": "create_sprite", "name": "Platform1", "costumes": [{"library": "Scenery/rock.png"}], "x": -80, "y": -30, "size": 120},
    {"action": "create_sprite", "name": "Platform2", "costumes": [{"library": "Scenery/rock.png"}], "x": 90, "y": 40, "size": 120},
    {"action": "create_sprite", "name": "Bird", "costumes": [
        {"library": "Animals/dove1-a.png"},
        {"library": "Animals/dove1-b.png"}], "x": -120, "y": 0},
]


def main() -> int:
    pack = (ROOT / "context" / "games.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", pack, flags=re.S)
    print(f"extracted {len(blocks)} JSON blocks from context/games.md")
    raw_changes = SETUP + [json.loads(block) for block in blocks]
    changeset = ChangeSet(
        summary="games pack smoke test",
        changes=[Change.from_dict(raw) for raw in raw_changes],
        notes="",
    )
    issues = validate_changeset(changeset, ProjectContext.demo())
    if issues:
        print(f"VALIDATION ISSUES ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    compiled = compile_changeset(changeset, ProjectContext.demo())
    print("all patterns validate and compile cleanly")
    print(compiled.chat_summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
