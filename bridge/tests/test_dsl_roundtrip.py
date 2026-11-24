from __future__ import annotations

import dataclasses
import json
from collections import Counter
from pathlib import Path

import pytest

from harness.block_ir import Change, IRError
from harness.catalog import SPRITE_TARGET_OPS
from harness.context import ProjectContext, SpriteContext
from harness.dsl import DSLError, DSLErrors, render_changeset, transpile

#: ``bridge/tests/test_dsl_roundtrip.py`` -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_ROOT = REPO_ROOT / "scratch" / "base" / "audit"


def _add_block(
    block: object, sprites: set[str], variables: set[str]
) -> None:
    if not isinstance(block, dict):
        return
    op = block.get("op")
    args = block.get("args")
    if not isinstance(args, dict):
        args = {}
    if op in {"get_var", "set_var", "change_var", "show_variable", "hide_variable"}:
        name = args.get("name")
        if isinstance(name, str):
            variables.add(name)
    if (
        isinstance(op, str)
        and op in SPRITE_TARGET_OPS
        and isinstance(args.get("target"), str)
    ):
        sprites.add(args["target"])
    if (
        op == "create_clone"
        and isinstance(args.get("target"), str)
        and args["target"] != "myself"
    ):
        sprites.add(args["target"])
    for key in ("body", "then", "else"):
        for child in block.get(key, []) or []:
            _add_block(child, sprites, variables)
    for value in args.values():
        if isinstance(value, dict):
            _add_block(value, sprites, variables)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _add_block(item, sprites, variables)


def _context_for(payload: dict) -> ProjectContext:
    """A permissive context for corpus payloads that reference project state.

    Audit change sets were generated against a live project, so their menus
    mention sprites and variables that are not created in the same payload.
    The round-trip test is about the renderer, so the context accepts every
    name the payload mentions.
    """
    sprites: set[str] = {"Sprite1"}
    variables: set[str] = set()
    for change in payload.get("changes", []):
        if not isinstance(change, dict):
            continue
        action = change.get("action")
        if action in {"create_sprite", "duplicate_sprite"}:
            name = change.get("name")
            if isinstance(name, str):
                sprites.add(name)
        if action == "create_variable":
            name = change.get("name")
            if isinstance(name, str):
                variables.add(name)
        target = change.get("target")
        if isinstance(target, str):
            sprites.add(target)
        for block in change.get("body", []) or []:
            _add_block(block, sprites, variables)
    sprites.discard("Stage")
    table: dict[str, SpriteContext] = {
        "Stage": SpriteContext(name="Stage", is_stage=True)
    }
    for name in sorted(sprites):
        table[name] = SpriteContext(name=name)
    return ProjectContext(
        target="Sprite1",
        sprites=table,
        stage_variables=sorted(variables),
    )


def _compare(original: list[Change], rendered: list[Change]) -> str | None:
    if len(original) != len(rendered):
        return (
            f"change count: {len(original)} original vs {len(rendered)} rendered"
        )
    for index, (left, right) in enumerate(zip(original, rendered)):
        for field in dataclasses.fields(Change):
            a = getattr(left, field.name)
            b = getattr(right, field.name)
            if a != b:
                return f"changes[{index}].{field.name}: {a!r} != {b!r}"
    return None


def _assert_roundtrip(payload: dict) -> None:
    original = [Change.from_dict(change) for change in payload["changes"]]
    text = render_changeset(payload)
    assert text.isascii()
    rendered = transpile(
        text, _context_for(payload), check_names=False
    )
    problem = _compare(original, rendered.changes)
    assert problem is None, problem


# -- the three worked examples from SCRATCH_AI_CONTEXT.md section 12 -------

BEACH_EXAMPLE = {
    "summary": "Added a beach backdrop and three wandering crabs.",
    "changes": [
        {
            "action": "set_backdrop",
            "library": "Nature/beach-malibu.jpg",
            "select": True,
        },
        {
            "action": "create_sprite",
            "name": "Crab1",
            "costumes": [
                {"library": "Animals/crab1-a.png"},
                {"library": "Animals/crab1-b.png"},
            ],
            "x": -100,
            "y": -80,
            "direction": 90,
            "size": 40,
            "visible": True,
            "rotation_style": "left-right",
        },
        {
            "action": "create_sprite",
            "name": "Crab2",
            "costumes": [
                {"library": "Animals/crab1-a.png"},
                {"library": "Animals/crab1-b.png"},
            ],
            "x": 0,
            "y": -70,
            "direction": 90,
            "size": 35,
            "visible": True,
            "rotation_style": "left-right",
        },
        {
            "action": "create_sprite",
            "name": "Crab3",
            "costumes": [{"library": "Animals/crab2.gif"}],
            "x": 100,
            "y": -90,
            "direction": -90,
            "size": 45,
            "visible": True,
            "rotation_style": "left-right",
        },
        {
            "action": "add_script",
            "target": "Crab1",
            "label": "wander",
            "hat": {"op": "when_flag_clicked"},
            "body": [
                {
                    "op": "forever",
                    "body": [
                        {"op": "move", "args": {"steps": 2}},
                        {
                            "op": "turn_right",
                            "args": {
                                "degrees": {
                                    "op": "random",
                                    "args": {"from": -20, "to": 20},
                                }
                            },
                        },
                        {"op": "bounce"},
                        {"op": "next_costume"},
                        {"op": "wait", "args": {"seconds": 0.2}},
                    ],
                }
            ],
        },
        {
            "action": "add_script",
            "target": "Crab2",
            "label": "wander",
            "hat": {"op": "when_flag_clicked"},
            "body": [
                {
                    "op": "forever",
                    "body": [
                        {"op": "move", "args": {"steps": 2}},
                        {
                            "op": "turn_right",
                            "args": {
                                "degrees": {
                                    "op": "random",
                                    "args": {"from": -20, "to": 20},
                                }
                            },
                        },
                        {"op": "bounce"},
                        {"op": "next_costume"},
                        {"op": "wait", "args": {"seconds": 0.2}},
                    ],
                }
            ],
        },
        {
            "action": "add_script",
            "target": "Crab3",
            "label": "wander",
            "hat": {"op": "when_flag_clicked"},
            "body": [
                {
                    "op": "forever",
                    "body": [
                        {"op": "move", "args": {"steps": 2}},
                        {
                            "op": "turn_right",
                            "args": {
                                "degrees": {
                                    "op": "random",
                                    "args": {"from": -20, "to": 20},
                                }
                            },
                        },
                        {"op": "bounce"},
                        {"op": "next_costume"},
                        {"op": "wait", "args": {"seconds": 0.2}},
                    ],
                }
            ],
        },
    ],
    "notes": (
        "Crab3 uses crab2.gif; the costume name is crab2, never crab1."
    ),
}

BACKDROP_EXAMPLE = {
    "summary": "Added a two-backdrop cycle.",
    "changes": [
        {
            "action": "set_backdrop",
            "library": "Nature/stars.gif",
            "select": True,
        },
        {
            "action": "add_costume",
            "target": "Stage",
            "library": "Nature/beach-malibu.jpg",
            "select": False,
        },
        {
            "action": "add_script",
            "target": "Stage",
            "label": "cycle",
            "hat": {"op": "when_flag_clicked"},
            "body": [
                {
                    "op": "forever",
                    "body": [
                        {
                            "op": "switch_backdrop",
                            "args": {"backdrop": "stars"},
                        },
                        {"op": "wait", "args": {"seconds": 2}},
                        {
                            "op": "switch_backdrop",
                            "args": {"backdrop": "beach-malibu"},
                        },
                        {"op": "wait", "args": {"seconds": 2}},
                    ],
                }
            ],
        },
    ],
}

CLICKER_EXAMPLE = {
    "summary": "Added a clickable starfish and a score.",
    "changes": [
        {
            "action": "create_variable",
            "name": "score",
            "scope": "global",
            "initial": 0,
        },
        {
            "action": "create_sprite",
            "name": "Starfish",
            "costumes": [{"library": "Animals/starfish1-a.png"}],
            "x": 0,
            "y": 0,
            "direction": 90,
            "size": 40,
            "visible": True,
            "rotation_style": "all around",
        },
        {
            "action": "add_script",
            "target": "Starfish",
            "label": "caught",
            "hat": {"op": "when_clicked"},
            "body": [
                {
                    "op": "change_var",
                    "args": {"name": "score", "delta": 1},
                },
                {
                    "op": "goto_xy",
                    "args": {
                        "x": {
                            "op": "random",
                            "args": {"from": -200, "to": 200},
                        },
                        "y": {
                            "op": "random",
                            "args": {"from": -140, "to": 140},
                        },
                    },
                },
            ],
        },
        {
            "action": "add_script",
            "target": "Sprite1",
            "label": "score_hud",
            "hat": {"op": "when_flag_clicked"},
            "body": [
                {
                    "op": "set_var",
                    "args": {"name": "score", "value": 0},
                },
                {
                    "op": "forever",
                    "body": [
                        {
                            "op": "say",
                            "args": {
                                "text": {
                                    "op": "join",
                                    "args": {
                                        "a": "Score: ",
                                        "b": {
                                            "op": "get_var",
                                            "args": {"name": "score"},
                                        },
                                    },
                                }
                            },
                        },
                        {"op": "wait", "args": {"seconds": 0.2}},
                    ],
                },
            ],
        },
    ],
}


@pytest.mark.parametrize(
    "payload",
    [BEACH_EXAMPLE, BACKDROP_EXAMPLE, CLICKER_EXAMPLE],
    ids=["beach", "backdrop-cycle", "clicker"],
)
def test_worked_example_roundtrips(payload: dict):
    _assert_roundtrip(payload)


# -- audit-bundle corpus --------------------------------------------------


def test_audit_bundle_corpus_roundtrips():
    if not AUDIT_ROOT.is_dir():
        pytest.skip("no local audit corpus (scratch/base/audit is absent)")

    paths = sorted(AUDIT_ROOT.rglob("parsed.json"))
    paths += sorted(AUDIT_ROOT.rglob("changeset.json"))
    if not paths:
        pytest.skip("no audit bundles found")

    stats: Counter[str] = Counter()
    render_skips: Counter[str] = Counter()
    mismatches: list[str] = []
    exercised = 0

    for path in paths:
        stats["files"] += 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stats["unreadable file"] += 1
            continue
        if not isinstance(data, dict):
            stats["not a change-set object"] += 1
            continue
        raw_changes = data.get("changes")
        if not isinstance(raw_changes, list) or not raw_changes:
            stats["no non-empty changes list"] += 1
            continue
        try:
            original = [Change.from_dict(change) for change in raw_changes]
        except IRError:
            stats["unparseable change"] += 1
            continue
        try:
            text = render_changeset(data)
        except DSLError as exc:
            render_skips[exc.message] += 1
            continue
        try:
            rendered = transpile(
                text, _context_for(data), check_names=False
            )
        except (DSLError, DSLErrors) as exc:
            errors = [exc] if isinstance(exc, DSLError) else exc.errors
            mismatches.append(
                f"{path}: transpile failed: "
                + " | ".join(error.message for error in errors)
            )
            continue
        problem = _compare(original, rendered.changes)
        if problem is not None:
            mismatches.append(f"{path}: {problem}")
        else:
            exercised += 1

    report = (
        f"files={stats['files']} exercised={exercised} "
        f"skipped={sum(render_skips.values())} "
        f"other={sum(stats.values())} "
        f"skip_reasons={dict(render_skips.most_common(5))}"
    )
    assert not mismatches, (
        report + "\n" + "\n".join(mismatches[:10])
    )
    assert exercised >= 20, report
