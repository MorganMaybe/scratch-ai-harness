"""Mine known-good media paths from audit bundles.

Every audit turn records what the model produced and whether it applied. This
tool turns the successful turns into a small ranking that the prompt and the
media resolver ship:

``bridge/src/harness/known_media.json``::

    {
      "schema": 1,
      "generated": "2026-11-23T12:00:00Z",
      "sources": ["scratch/base/audit"],
      "paths": [
        {"library": "Geometry/line.png", "kind": "costume", "uses": 12},
        ...
      ]
    }

Only turns whose ``outcome.json`` says ``ok`` count. A reference counts when
it appears in that turn's applied ``compiled/changeset.json``, for
``create_sprite`` (each ``costumes`` entry with a ``library``), ``add_costume``
and ``set_backdrop``. References are counted case-insensitively, and each turn
bundle copied into more than one corpus is counted once.

Each reference is resolved against the installed media library and stored under
its canonical current path. The audited corpora predate the library's category
cleanup (``Things/button.gif``, ``Fantasy/fantasy1-a.png``), so storing the
literal old spelling would teach the prompt paths that no longer resolve. A
reference that no longer resolves is mapped to its library asset only when the
file stem matches exactly one asset of the right kind (the old-category and
old-extension cases); anything ambiguous or invented is skipped. ``kind`` is
the action the path appeared in (costume or backdrop); entries sort by uses
descending, then path.

Regeneration workflow: run this after meaningful live sessions, review the
diff, and commit ``known_media.json`` with the code that consumes it. The file
is data, not code: with no live history it is empty and every consumer behaves
exactly as before the ranking existed. ``--check`` ignores the timestamp and
source list, so CI can verify the shipped ranking without the maintainer's
other corpora.

Usage::

    python tools\\mine_media_usage.py
    python tools\\mine_media_usage.py --dir scratch\\base\\audit --out bridge\\src\\harness\\known_media.json
    python tools\\mine_media_usage.py --check        # CI: exit 1 when stale
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge" / "src"))

from harness.media import (  # noqa: E402
    BACKDROP,
    COSTUME,
    MediaAsset,
    MediaError,
    MediaLibrary,
    default_library,
)

SCHEMA = 1
DEFAULT_OUT = ROOT / "bridge" / "src" / "harness" / "known_media.json"
DEFAULT_DIRS = (ROOT / "scratch" / "base" / "audit",)


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _turn_dirs(directory: Path) -> list[Path]:
    """Every bundle under ``directory``, including nested ladder corpora."""
    try:
        outcomes = sorted(directory.rglob("outcome.json"))
    except OSError:
        return []
    return [path.parent for path in outcomes if path.parent.is_dir()]


def _library_refs(changeset: Any) -> list[tuple[str, str]]:
    """``(library, kind)`` for every media reference in a change set."""
    if not isinstance(changeset, dict):
        return []
    changes = changeset.get("changes")
    if not isinstance(changes, list):
        return []
    refs: list[tuple[str, str]] = []
    for change in changes:
        if not isinstance(change, dict):
            continue
        action = change.get("action")
        if action == "create_sprite":
            costumes = change.get("costumes")
            if not isinstance(costumes, list):
                continue
            for costume in costumes:
                if isinstance(costume, dict):
                    library = costume.get("library")
                    if isinstance(library, str) and library.strip():
                        refs.append((library, COSTUME))
        elif action == "add_costume":
            library = change.get("library")
            if isinstance(library, str) and library.strip():
                refs.append((library, COSTUME))
        elif action == "set_backdrop":
            library = change.get("library")
            if isinstance(library, str) and library.strip():
                refs.append((library, BACKDROP))
    return refs


def count_usage(directories: Iterable[Path | str]) -> dict[str, dict[str, Any]]:
    """Count references from ok turns, keyed by the written path casefolded.

    Turn bundles are deduplicated by folder name so the same corpus copied
    into two roots (the main worktree and a branch worktree) counts once.
    """
    counts: dict[str, dict[str, Any]] = {}
    seen_turns: set[str] = set()
    for directory in directories:
        for turn in _turn_dirs(Path(directory)):
            if turn.name in seen_turns:
                continue
            seen_turns.add(turn.name)
            outcome = _read_json(turn / "outcome.json", {})
            if not isinstance(outcome, dict) or outcome.get("outcome") != "ok":
                continue
            changeset = _read_json(turn / "compiled" / "changeset.json")
            for library, kind in _library_refs(changeset):
                key = library.strip().replace("\\", "/").strip("/").casefold()
                entry = counts.setdefault(
                    key,
                    {
                        "library": library.strip().replace("\\", "/").strip("/"),
                        "kind": kind,
                        "uses": 0,
                    },
                )
                entry["uses"] += 1
    return counts


def _resolve_reference(
    library: MediaLibrary, reference: str, kind: str
) -> MediaAsset | None:
    """Today's asset for a reference, tolerating historical category renames.

    An exact resolve wins. Otherwise, because the audited corpora predate the
    library cleanup, accept the single asset of ``kind`` whose file stem is the
    same; more than one candidate is ambiguous and is skipped.
    """
    try:
        return library.resolve(kind, reference)
    except MediaError:
        stem = Path(reference.replace("\\", "/")).stem.casefold()
        matches = [
            asset for asset in library.assets(kind) if asset.name.casefold() == stem
        ]
        return matches[0] if len(matches) == 1 else None


def canonical_entries(
    counts: dict[str, dict[str, Any]], library: MediaLibrary
) -> list[dict[str, Any]]:
    """Resolve counted paths to today's library, merging case/rename variants."""
    merged: dict[str, dict[str, Any]] = {}
    for entry in counts.values():
        asset = _resolve_reference(library, entry["library"], entry["kind"])
        if asset is None:
            continue
        key = asset.library.casefold()
        target = merged.setdefault(
            key, {"library": asset.library, "kind": asset.kind, "uses": 0}
        )
        target["uses"] += entry["uses"]
    return sorted(
        merged.values(), key=lambda item: (-item["uses"], item["library"].casefold())
    )


def _source_label(directory: Path | str) -> str:
    """Repo-relative provenance where possible, never a bare machine path."""
    resolved = Path(directory).expanduser().resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        try:
            return Path(os.path.relpath(resolved, ROOT)).as_posix()
        except ValueError:
            return resolved.as_posix()


def build_payload(
    directories: Iterable[Path | str],
    library: MediaLibrary,
    *,
    generated: str | None = None,
) -> dict[str, Any]:
    dirs = [Path(directory) for directory in directories]
    stamp = generated or datetime.now(timezone.utc).isoformat(timespec="seconds")
    if stamp.endswith("+00:00"):
        stamp = stamp[:-6] + "Z"
    return {
        "schema": SCHEMA,
        "generated": stamp,
        "sources": [_source_label(directory) for directory in dirs],
        "paths": canonical_entries(count_usage(dirs), library),
    }


def _payload_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _same_data(existing: Any, payload: dict[str, Any]) -> bool:
    """Compare mined data, ignoring provenance and the run timestamp.

    ``generated`` and ``sources`` record where the data came from, but CI does
    not have the maintainer's other audit corpora; the ranking itself is what
    must match.
    """
    if not isinstance(existing, dict):
        return False
    return (
        existing.get("schema") == payload["schema"]
        and existing.get("paths") == payload["paths"]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mine known-good media paths from successful audit turns"
    )
    parser.add_argument(
        "--dir",
        action="append",
        dest="dirs",
        help="audit directory (repeatable; default scratch/base/audit)",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="output JSON (default bridge/src/harness/known_media.json)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when the mined paths are missing or stale "
        "(provenance and timestamp are ignored)",
    )
    parser.add_argument(
        "--media-root",
        help="Media directory to resolve paths against (default scratch/base/Media)",
    )
    args = parser.parse_args(argv)

    directories = args.dirs or [str(path) for path in DEFAULT_DIRS]
    library = (
        MediaLibrary(args.media_root) if args.media_root else default_library()
    )
    if not library.assets():
        print(
            f"no media library at {library.root}; pass --media-root",
            file=sys.stderr,
        )
        return 2

    payload = build_payload(directories, library)
    out = Path(args.out)

    if args.check:
        existing = _read_json(out)
        if _same_data(existing, payload):
            print(f"{out}: up to date ({len(payload['paths'])} paths)")
            return 0
        print(f"{out}: stale; rerun tools/mine_media_usage.py", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_payload_text(payload), encoding="utf-8")
    print(f"{out}: {len(payload['paths'])} paths from {len(directories)} dirs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
