from __future__ import annotations

from harness.block_ir import ChangeSet
from harness.changeset import compile_changeset
from harness.context import ProjectContext, SpriteContext
from harness.protocol import Sym, parse_literal
from harness.validator import validate_changeset


def changeset(changes: list[dict]) -> ChangeSet:
    return ChangeSet.from_dict({"summary": "clone test", "changes": changes})


def test_clone_block_catalog_and_literal():
    data = changeset(
        [
            {
                "action": "add_script",
                "target": "Sprite1",
                "label": "spawn",
                "hat": {"op": "when_clone_start"},
                "body": [
                    {"op": "create_clone", "args": {"target": "myself"}},
                    {"op": "delete_clone"},
                ],
            }
        ]
    )
    assert validate_changeset(data, ProjectContext.demo()) == []
    compiled = compile_changeset(data, ProjectContext.demo())
    message = parse_literal(compiled.apply_literal(7))
    stack = message[2][0][3]
    assert stack[0] == [Sym("CloneEventHatMorph")]
    assert stack[1] == [Sym("createCloneOf:"), "myself"]
    assert stack[2] == [Sym("deleteThisClone")]


def test_create_clone_accepts_myself_existing_and_new_sprite():
    existing = changeset(
        [
            {
                "action": "add_script",
                "target": "Sprite1",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "create_clone", "args": {"target": "Sprite1"}}],
            }
        ]
    )
    assert validate_changeset(existing, ProjectContext.demo()) == []

    created = changeset(
        [
            {
                "action": "create_sprite",
                "name": "Bullet",
                "costumes": [{"library": "Animals/bat1-a.png"}],
            },
            {
                "action": "add_script",
                "target": "Sprite1",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "create_clone", "args": {"target": "Bullet"}}],
            },
        ]
    )
    assert validate_changeset(created, ProjectContext.demo()) == []
    compiled = compile_changeset(created, ProjectContext.demo())
    message = parse_literal(compiled.apply_literal(8))
    assert message[2][1][3][1] == [Sym("createCloneOf:"), "Bullet"]


def test_create_clone_rejects_unknown_and_stage():
    unknown = changeset(
        [
            {
                "action": "add_script",
                "target": "Sprite1",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "create_clone", "args": {"target": "Ghost"}}],
            }
        ]
    )
    text = "\n".join(str(issue) for issue in validate_changeset(unknown, ProjectContext.demo()))
    assert "unknown clone target" in text

    stage = changeset(
        [
            {
                "action": "add_script",
                "target": "Sprite1",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "create_clone", "args": {"target": "Stage"}}],
            }
        ]
    )
    assert any("cannot be cloned" in str(issue) for issue in validate_changeset(stage, ProjectContext.demo()))


def test_clone_blocks_are_sprite_only():
    context = ProjectContext(
        target="Stage",
        sprites={
            "Stage": SpriteContext(name="Stage", is_stage=True),
            "Sprite1": SpriteContext(name="Sprite1", ai_owned=False),
        },
        stage_variables=[],
        stage_lists=[],
    )
    for hat, body in (
        ("when_clone_start", []),
        ("when_flag_clicked", [{"op": "delete_clone"}]),
        ("when_flag_clicked", [{"op": "create_clone", "args": {"target": "Sprite1"}}]),
    ):
        data = changeset(
            [{"action": "add_script", "target": "Stage", "hat": {"op": hat}, "body": body}]
        )
        assert validate_changeset(data, context), (hat, body)

    okay = changeset(
        [
            {
                "action": "add_script",
                "target": "Sprite1",
                "hat": {"op": "when_clone_start"},
                "body": [{"op": "delete_clone"}],
            }
        ]
    )
    assert validate_changeset(okay, context) == []
