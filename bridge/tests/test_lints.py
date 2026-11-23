"""Advisory runtime lint tests (offline)."""

from __future__ import annotations

import json

import pytest

from harness.agent import Agent
from harness.audit import AuditSettings, AuditStore
from harness.block_ir import ChangeSet
from harness.changeset import compile_changeset
from harness.context import ProjectContext, ScriptSummary, SpriteContext
from harness.lints import lint_changeset
from harness.llm import (
    MockLLM,
    bigger_square_response,
    draw_square_response,
)
from harness.protocol import Sym
from harness.server import Bridge

DRIFT = (
    "script 'wander' (Crab1): forever loop moves the sprite every frame with no "
    "wait; add a wait block inside the loop (0.05-0.5 s)"
)
FLICKER = (
    "script 'animate' (Crab1): forever loop switches costume every frame with no "
    "wait; add a wait block inside the loop (0.05-0.5 s)"
)
NEVER_SET = (
    "script 'show_score' (Crab1): variable 'score' is read but never set; "
    "it will always be 0"
)


def _context(
    *,
    stage_variables: list[str] | None = None,
    scripts: list[ScriptSummary] | None = None,
) -> ProjectContext:
    stage = SpriteContext(
        name="Stage", is_stage=True, variables=list(stage_variables or [])
    )
    crab = SpriteContext(
        name="Crab1",
        costumes=["crab1-a", "crab1-b"],
        scripts=list(scripts or []),
    )
    return ProjectContext(target="Crab1", sprites={"Crab1": crab, "Stage": stage})


def _changeset(*changes: dict, summary: str = "lint test") -> ChangeSet:
    return ChangeSet.from_dict({"summary": summary, "changes": list(changes)})


def _script(
    body: list[dict],
    *,
    label: str = "wander",
    target: str = "Crab1",
) -> dict:
    return {
        "action": "add_script",
        "target": target,
        "label": label,
        "hat": {"op": "when_flag_clicked"},
        "body": body,
    }


def _create_variable(name: str, initial: int | None = None) -> dict:
    change: dict = {
        "action": "create_variable",
        "name": name,
        "scope": "sprite",
        "target": "Crab1",
    }
    if initial is not None:
        change["initial"] = initial
    return change


def _read(name: str, label: str = "show_score") -> dict:
    return _script(
        [
            {
                "op": "say",
                "args": {"text": {"op": "get_var", "args": {"name": name}}},
            }
        ],
        label=label,
    )


def _script_tuples(context: ProjectContext, body: list[dict]) -> list:
    compiled = compile_changeset(
        _changeset(_script(body, label="writer")), context
    )
    return compiled.changes[0].stack


def test_forever_move_without_wait_triggers_drift():
    changeset = _changeset(
        _script([{"op": "forever", "body": [{"op": "move", "args": {"steps": 5}}]}])
    )
    assert lint_changeset(changeset, _context()) == [DRIFT]


def test_repeat_until_change_without_wait_triggers_drift():
    changeset = _changeset(
        _script(
            [
                {
                    "op": "repeat_until",
                    "args": {"condition": {"op": "touching", "args": {"target": "edge"}}},
                    "body": [{"op": "change_y", "args": {"dy": 3}}],
                }
            ]
        )
    )
    assert lint_changeset(changeset, _context()) == [
        DRIFT.replace("forever loop", "repeat_until loop")
    ]


def test_motion_inside_if_is_not_drift():
    changeset = _changeset(
        _script(
            [
                {
                    "op": "forever",
                    "body": [
                        {
                            "op": "if",
                            "args": {
                                "condition": {"op": "key_pressed", "args": {"key": "up arrow"}}
                            },
                            "body": [{"op": "move", "args": {"steps": 5}}],
                        }
                    ],
                }
            ]
        )
    )
    assert lint_changeset(changeset, _context()) == []


def test_turn_only_spin_is_not_drift():
    changeset = _changeset(
        _script(
            [
                {
                    "op": "forever",
                    "body": [{"op": "turn_right", "args": {"degrees": 15}}],
                }
            ]
        )
    )
    assert lint_changeset(changeset, _context()) == []


def test_set_x_paddle_follow_is_not_drift():
    changeset = _changeset(
        _script(
            [
                {
                    "op": "forever",
                    "body": [
                        {
                            "op": "set_x",
                            "args": {"x": {"op": "mouse_x"}},
                        }
                    ],
                }
            ]
        )
    )
    assert lint_changeset(changeset, _context()) == []


def test_repeat_pen_drawing_is_not_drift():
    changeset = _changeset(
        _script(
            [
                {
                    "op": "repeat",
                    "args": {"count": 4},
                    "body": [
                        {"op": "move", "args": {"steps": 100}},
                        {"op": "turn_right", "args": {"degrees": 90}},
                    ],
                }
            ]
        )
    )
    assert lint_changeset(changeset, _context()) == []


def test_wait_inside_loop_suppresses_drift():
    changeset = _changeset(
        _script(
            [
                {
                    "op": "forever",
                    "body": [
                        {"op": "move", "args": {"steps": 5}},
                        {"op": "wait", "args": {"seconds": 0.1}},
                    ],
                }
            ]
        )
    )
    assert lint_changeset(changeset, _context()) == []


def test_forever_next_costume_without_wait_triggers_flicker():
    changeset = _changeset(
        _script([{"op": "forever", "body": [{"op": "next_costume"}]}], label="animate")
    )
    assert lint_changeset(changeset, _context()) == [FLICKER]


def test_switch_costume_display_is_not_flicker():
    changeset = _changeset(
        _script(
            [
                {
                    "op": "forever",
                    "body": [
                        {"op": "switch_costume", "args": {"costume": "crab1-b"}}
                    ],
                }
            ],
            label="animate",
        )
    )
    assert lint_changeset(changeset, _context()) == []


def test_wait_suppresses_flicker():
    changeset = _changeset(
        _script(
            [
                {
                    "op": "forever",
                    "body": [
                        {"op": "next_costume"},
                        {"op": "wait", "args": {"seconds": 0.2}},
                    ],
                }
            ],
            label="animate",
        )
    )
    assert lint_changeset(changeset, _context()) == []


def test_variable_read_without_write_warns():
    changeset = _changeset(_create_variable("score"), _read("score"))
    assert lint_changeset(changeset, _context()) == [NEVER_SET]


def test_variable_written_later_in_same_set_is_not_flagged():
    changeset = _changeset(
        _create_variable("score"),
        _read("score"),
        _script(
            [{"op": "change_var", "args": {"name": "score", "delta": 1}}],
            label="score_up",
        ),
    )
    assert lint_changeset(changeset, _context()) == []


def test_variable_with_non_zero_initial_is_not_flagged():
    changeset = _changeset(_create_variable("score", initial=5), _read("score"))
    assert lint_changeset(changeset, _context()) == []


def test_pre_existing_variable_is_not_flagged():
    changeset = _changeset(_read("lives"))
    assert lint_changeset(changeset, _context(stage_variables=["lives"])) == []


def test_ai_owned_script_write_counts_as_a_write():
    base = _context()
    tuples = _script_tuples(
        base, [{"op": "set_var", "args": {"name": "score", "value": 3}}]
    )
    context = _context(
        scripts=[
            ScriptSummary(
                script_id="ai-9",
                target="Crab1",
                label="writer",
                hat="when_flag_clicked",
                block_count=2,
                owned=True,
                tuples=tuples,
            )
        ]
    )
    changeset = _changeset(_create_variable("score"), _read("score"))
    assert lint_changeset(changeset, context, context.registry()) == []


def test_read_only_context_script_write_does_not_count():
    base = _context()
    tuples = _script_tuples(
        base, [{"op": "set_var", "args": {"name": "score", "value": 3}}]
    )
    context = _context(
        scripts=[
            ScriptSummary(
                script_id="user-1",
                target="Crab1",
                label="user_writer",
                hat="when_flag_clicked",
                block_count=2,
                owned=False,
                tuples=tuples,
            )
        ]
    )
    changeset = _changeset(_create_variable("score"), _read("score"))
    assert lint_changeset(changeset, context, context.registry()) == [NEVER_SET]


def test_canonical_wander_script_is_clean():
    changeset = _changeset(
        _script(
            [
                {
                    "op": "forever",
                    "body": [
                        {"op": "move", "args": {"steps": 5}},
                        {"op": "wait", "args": {"seconds": 0.1}},
                        {
                            "op": "if",
                            "args": {
                                "condition": {"op": "touching", "args": {"target": "edge"}}
                            },
                            "body": [
                                {"op": "turn_right", "args": {"degrees": 180}}
                            ],
                        },
                    ],
                }
            ]
        )
    )
    assert lint_changeset(changeset, _context()) == []


@pytest.mark.parametrize(
    "reply", [draw_square_response(), bigger_square_response("ai-1")]
)
def test_mock_canned_scenes_have_no_lints(reply):
    changeset = ChangeSet.from_dict(reply)
    assert lint_changeset(changeset, ProjectContext.demo()) == []


def test_messages_are_single_line_ascii():
    changeset = _changeset(
        _script(
            [{"op": "forever", "body": [{"op": "move", "args": {"steps": 5}}]}],
            label="w\u00e1nder\nnow",
        )
    )
    messages = lint_changeset(changeset, _context())
    assert len(messages) == 1
    assert "\n" not in messages[0]
    assert messages[0].isascii()


def test_agent_records_drift_warning_and_lints_json(tmp_path):
    reply = {
        "summary": "Added a wandering script.",
        "changes": [
            {
                "action": "add_script",
                "target": "Sprite1",
                "label": "wander",
                "hat": {"op": "when_flag_clicked"},
                "body": [
                    {"op": "forever", "body": [{"op": "move", "args": {"steps": 5}}]}
                ],
            }
        ],
    }
    store = AuditStore(
        AuditSettings(mode="full", directory=tmp_path / "audit", keep=5)
    )
    audit = store.start_turn(
        request_id=9,
        prompt="Make the cat wander.",
        target="Sprite1",
        context=ProjectContext.demo(),
        profile="mock",
        model="mock",
        base_url="",
        turn_budget_s=1.0,
    )
    assert audit is not None
    agent = Agent(MockLLM([reply]), ProjectContext.demo(), audit=audit)

    result = agent.handle("Make the cat wander.", 9)
    audit.finish(
        outcome="ok",
        attempts=result.attempts,
        changes=len(result.compiled.changes),
        elapsed_ms=1,
        result=result,
    )

    expected = [
        "script 'wander' (Sprite1): forever loop moves the sprite every frame "
        "with no wait; add a wait block inside the loop (0.05-0.5 s)"
    ]
    assert result.lint_warnings == expected
    assert result.summary
    lints = json.loads((audit.root / "lints.json").read_text(encoding="utf-8"))
    assert lints == expected


def test_lint_failure_never_fails_the_turn(monkeypatch):
    import harness.agent as agent_module

    def boom(*args, **kwargs):
        raise RuntimeError("simulated lint failure")

    monkeypatch.setattr(agent_module, "lint_changeset", boom)
    agent = Agent(MockLLM([draw_square_response()]), ProjectContext.demo())

    result = agent.handle("Draw a square.", 10)

    assert result.summary
    assert result.lint_warnings == []


def test_lints_json_is_full_mode_only(tmp_path):
    store = AuditStore(
        AuditSettings(mode="meta", directory=tmp_path / "audit", keep=5)
    )
    audit = store.start_turn(
        request_id=12,
        prompt="Draw a square.",
        target="Sprite1",
        context=ProjectContext.demo(),
    )
    assert audit is not None

    audit.write_lints(["warning text"])

    assert not (audit.root / "lints.json").exists()


def test_result_chat_lines_include_warning_line():
    reply = {
        "summary": "Added a wandering script.",
        "changes": [
            {
                "action": "add_script",
                "target": "Sprite1",
                "label": "wander",
                "hat": {"op": "when_flag_clicked"},
                "body": [
                    {"op": "forever", "body": [{"op": "move", "args": {"steps": 5}}]}
                ],
            }
        ],
    }
    bridge = Bridge(Agent(MockLLM([reply]), ProjectContext.demo()))

    response = bridge.handle([Sym("request"), 11, ["Make the cat wander."], "Sprite1"])[0]

    assert response[0] == Sym("result")
    assert (
        "warning: script 'wander' (Sprite1): forever loop moves the sprite every "
        "frame with no wait; add a wait block inside the loop (0.05-0.5 s)"
        in response[2]
    )
    assert all("\n" not in line and line.isascii() for line in response[2])
