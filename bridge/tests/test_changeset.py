from __future__ import annotations

import pytest

from harness.block_ir import Block, ChangeSet, IRError
from harness.changeset import compile_changeset
from harness.context import ProjectContext, ScriptSummary
from harness.protocol import Sym, parse_literal


def test_add_compiles_and_assigns_id():
    changeset = ChangeSet.from_dict(
        {
            "summary": "Add square.",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "draw_square",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [
                        {"op": "pen_clear"},
                        {"op": "pen_down"},
                        {
                            "op": "repeat",
                            "args": {"count": 4},
                            "body": [
                                {"op": "move", "args": {"steps": 100}},
                                {"op": "turn_right", "args": {"degrees": 90}},
                            ],
                        },
                        {"op": "pen_up"},
                    ],
                }
            ],
        }
    )
    compiled = compile_changeset(changeset, ProjectContext.demo())
    assert compiled.changes[0].script_id == "ai-1"
    assert compiled.changes[0].block_count == 5
    assert "Added script 'draw_square'" in compiled.chat_summary()
    literal = compiled.apply_literal(7)
    message = parse_literal(literal)
    assert message[0] == Sym("apply")
    assert message[1] == 7
    assert message[2][0][0] == Sym("add")
    assert message[2][0][1] == "ai-1"
    assert message[2][0][2] == "Sprite1"
    assert message[2][0][4] == "draw_square"


def test_replace_uses_registry():
    context = ProjectContext.demo()
    registry = {
        "ai-1": ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label="draw_square",
            hat="when_flag_clicked",
            block_count=5,
        )
    }
    changeset = ChangeSet.from_dict(
        {
            "summary": "Make bigger.",
            "changes": [
                {
                    "action": "replace_script",
                    "script_id": "ai-1",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "move", "args": {"steps": 200}}],
                }
            ],
        }
    )
    compiled = compile_changeset(changeset, context, registry)
    assert compiled.changes[0].script_id == "ai-1"
    assert compiled.changes[0].target == "Sprite1"
    assert "Updated script 'draw_square'" in compiled.chat_summary()
    message = parse_literal(compiled.apply_literal(1))
    assert message[2][0][0] == Sym("replace")
    assert message[2][0][1] == "ai-1"


def test_delete_script():
    context = ProjectContext.demo()
    registry = {
        "ai-1": ScriptSummary("ai-1", "Sprite1", "draw_square", "when_flag_clicked", 5)
    }
    changeset = ChangeSet.from_dict(
        {"summary": "Remove it.", "changes": [{"action": "delete_script", "script_id": "ai-1"}]}
    )
    compiled = compile_changeset(changeset, context, registry)
    assert compiled.changes[0].action == "delete_script"
    message = parse_literal(compiled.apply_literal(2))
    assert message[2][0] == [Sym("delete"), "ai-1"]


def test_create_variable():
    changeset = ChangeSet.from_dict(
        {
            "summary": "Add score.",
            "changes": [{"action": "create_variable", "name": "score", "scope": "global", "initial": 0}],
        }
    )
    compiled = compile_changeset(changeset, ProjectContext.demo())
    assert compiled.changes[0].action == "create_variable"
    message = parse_literal(compiled.apply_literal(3))
    assert message[2][0] == [Sym("createVariable"), "score", Sym("global"), 0, "Stage"]


def test_create_sprite_variable_carries_its_target():
    changeset = ChangeSet.from_dict(
        {
            "summary": "Add a local counter.",
            "changes": [
                {
                    "action": "create_variable",
                    "name": "life",
                    "scope": "sprite",
                    "target": "Sprite1",
                    "initial": 3,
                }
            ],
        }
    )
    compiled = compile_changeset(changeset, ProjectContext.demo())
    message = parse_literal(compiled.apply_literal(4))
    assert message[2][0] == [Sym("createVariable"), "life", Sym("sprite"), 3, "Sprite1"]


def test_apply_structure_is_nested():
    changeset = ChangeSet.from_dict(
        {
            "summary": "Add square.",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "draw_square",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "pen_clear"}],
                }
            ],
        }
    )
    compiled = compile_changeset(changeset, ProjectContext.demo())
    structure = compiled.apply_structure(9)
    assert structure[0].name == "apply"
    assert structure[1] == 9
    assert structure[2][0][0].name == "add"
    assert structure[2][0][1] == "ai-1"


def test_nested_block_as_named_field_names_the_block_and_the_fix():
    # The live failure shape: a wait written as a field of if instead of in body.
    data = {
        "op": "if",
        "args": {},
        "body": [],
        "wait": {"op": "wait", "args": {"seconds": 0.04}},
    }

    with pytest.raises(IRError) as excinfo:
        Block.from_dict(data)

    message = str(excinfo.value)
    assert message == (
        "unknown block fields ['wait'] on block 'if'; a nested block belongs "
        "in the body list (or then/else), not as a named field"
    )
    assert "\n" not in message


def test_argument_hoisted_to_block_level_names_the_argument():
    with pytest.raises(IRError) as excinfo:
        Block.from_dict({"op": "repeat", "count": 4, "body": []})

    message = str(excinfo.value)
    assert "on block 'repeat'" in message
    assert "argument 'count' belongs inside 'args'" in message


def test_plain_unknown_field_gets_the_general_rule():
    with pytest.raises(IRError) as excinfo:
        Block.from_dict({"op": "move", "args": {}, "speed": 5})

    message = str(excinfo.value)
    assert "unknown block fields ['speed'] on block 'move'" in message
    assert "blocks take only op, args, body, then, else" in message


def test_block_with_only_allowed_fields_still_parses():
    block = Block.from_dict(
        {
            "op": "if_else",
            "args": {"condition": True},
            "body": [{"op": "wait", "args": {"seconds": 0.04}}],
            "then": [{"op": "stop_all"}],
            "else": [],
        }
    )

    assert block.op == "if_else"
    assert block.args == {"condition": True}
    assert [child.op for child in block.body] == ["wait"]
    assert [child.op for child in block.then] == ["stop_all"]
    assert block.else_ == []
