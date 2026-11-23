"""Revision-fidelity scorer for ladder platformer_chain bundles.

Compares each revision turn's replaced scripts against the platformer turn's
originals at the block-op level, and classifies the extra round trip
(``load_sprite`` control reply vs bridge replace echo vs blind direct).
A blind revision shows up as dropped ops (``touching``, ``next_costume``,
``set_x``...); a faithful one drops none, or only semantically equivalent
rewrites. This is the automated half of the revision item in
``docs/LADDER_RUBRIC.md``.

    python tools\\revision_fidelity.py <ladder-session-dir> [session-dir ...]

Reads only audit bundles (compiled/changeset.json, attempts/*/meta.json);
no model, key or image needed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge" / "src"))  # noqa: E402 - tooling only


def _walk_ops(value: Any, seen: set[str]) -> None:
    if isinstance(value, dict):
        if "op" in value:
            seen.add(value["op"])
        for child in value.values():
            _walk_ops(child, seen)
    elif isinstance(value, list):
        for item in value:
            _walk_ops(item, seen)


def _script_ops(change: dict[str, Any]) -> set[str]:
    ops: set[str] = set()
    _walk_ops(change.get("body", []), ops)
    _walk_ops(change.get("hat"), ops)
    return ops


def _load_changes(bundle: Path) -> list[dict[str, Any]]:
    data = json.loads(
        (bundle / "compiled" / "changeset.json").read_text(encoding="utf-8")
    )
    return data.get("changes", [])


def _script_key(change: dict[str, Any]) -> tuple[str, str]:
    return (change.get("target", ""), change.get("label", ""))


def _first_attempt_kind(bundle: Path) -> str:
    """``load_sprite`` / ``echo`` / ``direct`` from the first attempt."""
    meta_path = bundle / "attempts" / "01" / "meta.json"
    if not meta_path.exists():
        return "?"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("replace_echo"):
        return "echo"
    parsed_path = bundle / "attempts" / "01" / "parsed.json"
    if parsed_path.exists():
        try:
            parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
        except ValueError:
            parsed = None
        if isinstance(parsed, dict) and "load_sprite" in parsed:
            return "load_sprite"
    return "direct"


def _runs(session: Path) -> Iterator[str]:
    seen: set[str] = set()
    for directory in session.iterdir():
        if not directory.is_dir():
            continue
        match = re.search(r"-r(\d+)$", directory.name)
        if match:
            seen.add(match.group(1))
    yield from sorted(seen)


def analyze(session: Path) -> None:
    print(f"### {session.name}")
    for mode in ("json", "dsl"):
        for run in _runs(session):
            platformer = next(session.glob(f"*reqplatformer-{mode}-r{run}"), None)
            revision = next(session.glob(f"*reqrevision-{mode}-r{run}"), None)
            if platformer is None or revision is None:
                continue
            originals = {
                _script_key(change): _script_ops(change)
                for change in _load_changes(platformer)
                if change.get("action") == "add_script"
            }
            dropped_total = 0
            lines: list[str] = []
            for change in _load_changes(revision):
                if change.get("action") != "replace_script":
                    continue
                key = _script_key(change)
                original = originals.get(key)
                if original is None:
                    lines.append(f"    {key[0]}/{key[1]}: replaced (no original under that label)")
                    continue
                new_ops = _script_ops(change)
                dropped = original - new_ops
                dropped_total += len(dropped)
                lines.append(
                    f"    {key[0]}/{key[1]}: "
                    f"dropped={sorted(dropped) if dropped else 'none'} "
                    f"added={sorted(new_ops - original) if new_ops - original else 'none'}"
                )
            outcome = json.loads(
                (revision / "outcome.json").read_text(encoding="utf-8")
            )
            print(
                f"  {mode} r{run}: attempts={outcome.get('attempts')} "
                f"first={_first_attempt_kind(revision)} "
                f"dropped_ops_total={dropped_total}"
            )
            for line in lines:
                print(line)
    print()


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    for arg in argv:
        analyze(Path(arg).expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
