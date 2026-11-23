"""Known-good media ranking: the miner, the loader, the prompt tier and resolve.

The committed ``known_media.json`` is seed data, so every test here
monkeypatches the loader or points it at a throwaway file.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from harness import known_media, prompts
from harness.catalog import catalog_summary
from harness.media import BACKDROP, COSTUME, MediaError, MediaLibrary

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MINER_PATH = _REPO_ROOT / "tools" / "mine_media_usage.py"


def _load_miner():
    spec = importlib.util.spec_from_file_location("mine_media_usage", _MINER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def _media_tree(tmp_path) -> Path:
    """A throwaway library with the paths the miner tests reference."""
    root = tmp_path / "Media"
    for relative in (
        "Costumes/Animals/bat1-a.png",
        "Costumes/Geometry/line.png",
        "Costumes/UI/button.gif",
        "Backgrounds/Space/stars.gif",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return root


def _write_turn(root, name, changes, outcome="ok", changeset=True) -> Path:
    turn = root / name
    (turn / "compiled").mkdir(parents=True, exist_ok=True)
    if outcome is not None:
        (turn / "outcome.json").write_text(
            json.dumps({"outcome": outcome}), encoding="utf-8"
        )
    if changeset:
        (turn / "compiled" / "changeset.json").write_text(
            json.dumps({"changes": changes}), encoding="utf-8"
        )
    return turn


def _changes(*libraries, kind="costume"):
    if kind == "backdrop":
        return [{"action": "set_backdrop", "library": library} for library in libraries]
    return [
        {"action": "create_sprite", "costumes": [{"library": library}]}
        for library in libraries
    ]


def _run(tmp_path, *dirs, out=None, extra=()):
    miner = _load_miner()
    out = out or (tmp_path / "known_media.json")
    argv = ["--out", str(out), "--media-root", str(_media_tree(tmp_path))]
    for directory in dirs:
        argv.extend(["--dir", str(directory)])
    argv.extend(extra)
    return miner.main(argv), out


def test_miner_counts_ok_turns_and_ignores_other_turns(tmp_path):
    audit = tmp_path / "audit"
    _write_turn(
        audit,
        "ok",
        [
            {"action": "create_sprite", "costumes": [
                {"library": "Animals/bat1-a.png"},
                {"library": "Geometry/line.png"},
            ]},
            {"action": "add_costume", "library": "Geometry/line.png"},
            {"action": "set_backdrop", "library": "Space/stars.gif"},
            {"action": "create_sprite", "costumes": [{"name": "no-library"}]},
        ],
    )
    _write_turn(audit, "error", _changes("Animals/bat1-a.png"), outcome="error:validation")
    _write_turn(audit, "no-outcome", _changes("Animals/bat1-a.png"), outcome=None)
    _write_turn(audit, "no-changeset", [], changeset=False)

    code, out = _run(tmp_path, audit)
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema"] == 1
    assert payload["paths"] == [
        {"library": "Geometry/line.png", "kind": "costume", "uses": 2},
        {"library": "Animals/bat1-a.png", "kind": "costume", "uses": 1},
        {"library": "Space/stars.gif", "kind": "backdrop", "uses": 1},
    ]


def test_miner_accumulates_across_turns_and_canonicalizes_paths(tmp_path):
    audit = tmp_path / "audit"
    _write_turn(audit, "one", _changes("animals/BAT1-A.PNG"))
    _write_turn(audit, "two", _changes("Animals/bat1-a.png"))
    # The audited corpora predate the category cleanup; the old spelling must
    # land on today's real path instead of shipping a broken prompt entry.
    _write_turn(audit, "three", _changes("Things/line.png"))

    code, out = _run(tmp_path, audit)
    assert code == 0
    paths = json.loads(out.read_text(encoding="utf-8"))["paths"]
    assert {"library": "Animals/bat1-a.png", "kind": "costume", "uses": 2} in paths
    assert {"library": "Geometry/line.png", "kind": "costume", "uses": 1} in paths
    assert all(entry["library"] != "Things/line.png" for entry in paths)


def test_miner_check_detects_drift(tmp_path):
    audit = tmp_path / "audit"
    _write_turn(audit, "one", _changes("Animals/bat1-a.png"))

    code, out = _run(tmp_path, audit)
    assert code == 0
    assert _run(tmp_path, audit, extra=["--check"])[0] == 0

    # The generated timestamp and source list are not drift on their own.
    payload = json.loads(out.read_text(encoding="utf-8"))
    payload["generated"] = "2000-01-01T00:00:00Z"
    payload["sources"] = ["elsewhere/audit"]
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    assert _run(tmp_path, audit, extra=["--check"])[0] == 0

    _write_turn(audit, "two", _changes("Animals/bat1-a.png"))
    assert _run(tmp_path, audit, extra=["--check"])[0] == 1


def _write_known(path, paths) -> None:
    path.write_text(
        json.dumps({"schema": 1, "generated": "2026-11-23T00:00:00Z",
                    "sources": ["test"], "paths": paths}),
        encoding="utf-8",
    )


def test_loader_missing_or_bad_file_is_empty(tmp_path, monkeypatch):
    missing = tmp_path / "absent.json"
    monkeypatch.setattr(known_media, "KNOWN_MEDIA_PATH", missing)
    assert known_media.load_known_media() == []
    assert known_media.known_media_paths() == frozenset()
    assert known_media.ranked_media(10) == []

    bad = tmp_path / "bad.json"
    for text in ("{not json", "[]", '{"schema": 1, "paths": "nope"}'):
        bad.write_text(text, encoding="utf-8")
        monkeypatch.setattr(known_media, "KNOWN_MEDIA_PATH", bad)
        assert known_media.load_known_media() == []


def test_loader_parses_valid_file_and_ranks_by_uses(tmp_path, monkeypatch):
    path = tmp_path / "known.json"
    _write_known(
        path,
        [
            {"library": "Animals/bat1-a.png", "kind": "costume", "uses": 2},
            {"library": "Space/stars.gif", "kind": "backdrop", "uses": 9},
            {"library": "not-a-path", "kind": "costume", "uses": 0},
        ],
    )
    monkeypatch.setattr(known_media, "KNOWN_MEDIA_PATH", path)
    assert known_media.ranked_media(10) == [
        ("Space/stars.gif", "backdrop", 9),
        ("Animals/bat1-a.png", "costume", 2),
    ]
    assert known_media.known_media_paths() == {
        "space/stars.gif",
        "animals/bat1-a.png",
    }
    assert known_media.ranked_media(1) == [("Space/stars.gif", "backdrop", 9)]
    assert known_media.ranked_media(0) == []


def test_prompt_renders_known_good_tier_after_the_verified_block(monkeypatch):
    monkeypatch.setattr(
        known_media,
        "ranked_media",
        lambda count=20: [
            ("Geometry/line.png", "costume", 12),
            ("Animals/bat1-a.png", "costume", 7),
            ("Space/stars.gif", "backdrop", 4),
        ][:count],
    )
    prompt = prompts.build_system_prompt(
        target="Sprite1", media_index="  Animals: bat1-a.png\n"
    )
    assert prompts.KNOWN_GOOD_HEADER in prompt
    assert prompt.index("Verified prop paths") < prompt.index(prompts.KNOWN_GOOD_HEADER)
    assert "  costumes: Geometry/line.png, Animals/bat1-a.png" in prompt
    assert "  backdrops: Space/stars.gif" in prompt
    assert len(prompts.known_good_media_block()) <= prompts.KNOWN_GOOD_MAX_CHARS

    # The shared builder means the dialect prompt carries the same tier.
    dsl = prompts.build_dsl_system_prompt(
        target="Sprite1", media_index="  Animals: bat1-a.png\n"
    )
    assert prompts.KNOWN_GOOD_HEADER in dsl


def test_prompt_is_unchanged_without_mined_data(monkeypatch):
    monkeypatch.setattr(known_media, "ranked_media", lambda count=20: [])
    prompt = prompts.build_system_prompt(target="Sprite1")
    expected = (
        prompts.SYSTEM_PROMPT.replace(
            "{catalog}", catalog_summary(None, "sprite")
        ).replace("{media}", prompts.media_index_text(max_chars=16000))
        + "\n"
        + prompts.EXAMPLES
    )
    assert prompt == expected
    assert prompts.KNOWN_GOOD_HEADER not in prompt


def test_tight_budget_drops_the_whole_verified_region(monkeypatch):
    monkeypatch.setattr(
        known_media,
        "ranked_media",
        lambda count=20: [("Animals/bat1-a.png", "costume", 9)][:count],
    )
    prompt = prompts.build_system_prompt(target="Sprite1", budget_chars=2000)
    assert len(prompt) <= 2000
    assert "Verified prop paths" not in prompt
    assert prompts.KNOWN_GOOD_HEADER not in prompt
    assert "near matches" not in prompt


def _library_with(tmp_path, relative_paths):
    root = tmp_path / "Media"
    for relative in relative_paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return MediaLibrary(root)


def test_resolve_ranks_known_good_suggestions_first(tmp_path, monkeypatch):
    library = _library_with(
        tmp_path,
        (
            "Costumes/Scenery/apple.png",
            "Costumes/Scenery/banana.png",
            "Costumes/Scenery/cherry.png",
        ),
    )
    known = tmp_path / "known.json"
    _write_known(
        known, [{"library": "Scenery/banana.png", "kind": "costume", "uses": 3}]
    )
    monkeypatch.setattr(known_media, "KNOWN_MEDIA_PATH", known)

    with pytest.raises(MediaError) as excinfo:
        library.resolve(COSTUME, "Scenery/xylophone.png")
    assert excinfo.value.suggestions == [
        "Scenery/banana.png",
        "Scenery/apple.png",
        "Scenery/cherry.png",
    ]
    assert "near matches: Scenery/banana.png, Scenery/apple.png" in str(excinfo.value)

    # With no mined data the resolver keeps its difflib fallback order.
    monkeypatch.setattr(known_media, "KNOWN_MEDIA_PATH", tmp_path / "absent.json")
    with pytest.raises(MediaError) as excinfo:
        library.resolve(COSTUME, "Scenery/xylophone.png")
    assert excinfo.value.suggestions == [
        "Scenery/apple.png",
        "Scenery/cherry.png",
        "Scenery/banana.png",
    ]
