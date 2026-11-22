from __future__ import annotations

import pytest

from harness.agent import Agent
from harness.changeset import compile_changeset
from harness.context import ProjectContext
from harness.block_ir import ChangeSet
from harness.llm import MockLLM, draw_square_response
from harness.protocol import ProtocolError, Sym, parse_literal
from harness.server import Bridge
from harness.smalltalk import to_literal
from harness.validator import validate_changeset


CONTEXT = [
    "Sprite1",
    [
        ["Stage", True, ["score"], ["log"], ["background1"], [], []],
        [
            "Sprite1",
            False,
            [],
            [],
            ["costume1", "costume2"],
            ["meow"],
            [
                ["user-123", "EventHatMorph", "EventHatMorph", 5, "123456", False, False],
                ["ai-1", "EventHatMorph", "EventHatMorph", 4, "654321", True, False],
            ],
        ],
    ],
]


def make_context() -> ProjectContext:
    return ProjectContext.from_literal(parse_literal(to_literal(CONTEXT)))


def test_context_from_literal():
    context = make_context()
    assert context.target == "Sprite1"
    assert set(context.sprites) == {"Stage", "Sprite1"}
    assert context.sprites["Stage"].is_stage
    assert context.stage_variables == ["score"]
    assert context.stage_lists == ["log"]
    assert context.variable_names("Sprite1") == ["score"]
    assert context.costume_names("Sprite1") == ["costume1", "costume2"]
    assert context.sound_names("Sprite1") == ["meow"]
    registry = context.registry()
    assert set(registry) == {"user-123", "ai-1"}
    assert registry["ai-1"].owned is True
    assert registry["user-123"].owned is False
    assert registry["user-123"].target == "Sprite1"


def test_context_summary_marks_read_only_scripts():
    text = make_context().summary_text()
    assert "user-123" in text
    assert "read-only" in text
    assert "ai-1" in text


def test_context_rejects_malformed_entries():
    with pytest.raises(ValueError):
        ProjectContext.from_literal(["Sprite1"])
    with pytest.raises(ValueError):
        ProjectContext.from_literal(["Sprite1", [["Stage", True]]])


def test_validator_rejects_user_owned_replace_and_delete():
    context = make_context()
    registry = context.registry()
    replace = ChangeSet.from_dict(
        {
            "summary": "Change a user script.",
            "changes": [
                {
                    "action": "replace_script",
                    "script_id": "user-123",
                    "target": "Sprite1",
                    "label": "mine",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "pen_down"}],
                }
            ],
        }
    )
    issues = validate_changeset(replace, context, registry)
    assert any("read-only" in str(issue) for issue in issues)

    delete = ChangeSet.from_dict(
        {
            "summary": "Delete a user script.",
            "changes": [{"action": "delete_script", "script_id": "user-123"}],
        }
    )
    issues = validate_changeset(delete, context, registry)
    assert any("read-only" in str(issue) for issue in issues)


def test_add_ignores_model_supplied_script_id():
    context = make_context()
    registry = context.registry()
    changeset = ChangeSet.from_dict(
        {
            "summary": "Add with a colliding id.",
            "changes": [
                {
                    "action": "add_script",
                    "script_id": "ai-1",
                    "target": "Sprite1",
                    "label": "square",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "pen_down"}],
                }
            ],
        }
    )
    assert validate_changeset(changeset, context, registry) == []
    compiled = compile_changeset(changeset, context, registry)
    assert compiled.changes[0].script_id == "ai-2"


def test_bridge_uses_context_from_request():
    context = make_context()
    bridge = Bridge(Agent(MockLLM([draw_square_response()]), context))
    responses = bridge.handle(
        [Sym("request"), 9, ["Draw a square."], "Sprite1", parse_literal(to_literal(CONTEXT))]
    )
    result = responses[0]
    assert result[0] == Sym("result")
    assert result[1] == 9
    assert bridge.agent.context.stage_variables == ["score"]
    assert bridge.agent.registry["ai-1"].owned is True
    assert result[3][2][0][0] == Sym("add")
    assert result[3][2][0][1] == "ai-2"


def test_bridge_rejects_bad_context():
    context = ProjectContext.demo()
    bridge = Bridge(Agent(MockLLM([draw_square_response()]), context))
    with pytest.raises(ProtocolError):
        bridge.handle([Sym("request"), 1, ["hi"], "Sprite1", ["Sprite1"]])
