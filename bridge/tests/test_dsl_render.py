from __future__ import annotations

import textwrap

import pytest

from harness.block_ir import ChangeSet
from harness.changeset import compile_changeset
from harness.context import ProjectContext, ScriptSummary
from harness.dsl import (
    DSLError,
    render_changeset,
    render_script,
    render_sprite_detail,
    transpile,
)
from harness.script_detail import sprite_detail_text
from harness.smalltalk import Sym


def source(text: str) -> str:
    return textwrap.dedent(text).strip("\n")


SQUARE = source(
    """
    @on_flag(target="Sprite1", label="square")
    def square():
        pen_clear()
        pen_down()
        for _ in range(4):
            move(100)
            turn_right(90)
        pen_up()
    """
)

HUD = source(
    """
    summary("Score HUD.")
    create_variable("score", scope="global", initial=0)
    @on_flag(target="Sprite1")
    def score_hud():
        score = 0
        while True:
            say("Score: " + score)
            wait(0.2)
    """
)

BEACH = source(
    """
    summary("Beach with wandering crabs.")
    set_backdrop("Space/stars.gif")
    create_variable("score", scope="global", initial=0)
    create_sprite("Crab1",
        costumes=["Animals/bat1-a.png", "Animals/bat1-b.png"],
        x=-100, y=-80, size=40, rotation_style="left-right")
    @on_flag(target="Crab1", label="wander")
    def crab1_wander():
        while True:
            move(2)
            turn_right(random(-20, 20))
            bounce()
            next_costume()
            wait(0.2)
    @on_click(target="Star", label="caught")
    def star_caught():
        score += 1
        goto_xy(random(-200, 200), random(-140, 140))
    """
)

REPLACE = source(
    """
    @on_flag(script_id="ai-1", target="Sprite1")
    def restart():
        stop_all()
    """
)


@pytest.mark.parametrize("text_source", [SQUARE, HUD, BEACH, REPLACE])
def test_golden_render_roundtrips(text_source: str):
    original = transpile(text_source)
    rendered_text = render_changeset(original.to_dict())

    assert rendered_text.isascii()
    assert transpile(rendered_text).to_dict() == original.to_dict()


HATS = [
    ({"op": "when_flag_clicked"}, "on_flag"),
    ({"op": "when_key_pressed", "args": {"key": "space"}}, "on_key"),
    ({"op": "when_clicked"}, "on_click"),
    ({"op": "when_stage_clicked"}, "on_stage_click"),
    ({"op": "when_clone_start"}, "on_clone_start"),
    ({"op": "when_receive", "args": {"message": "go"}}, "on_receive"),
    (
        {"op": "when_backdrop_switches", "args": {"backdrop": "stars"}},
        "on_backdrop",
    ),
    ({"op": "when_loudness_greater", "args": {"value": 50}}, "on_loudness"),
    ({"op": "when_timer_greater", "args": {"value": 10}}, "on_timer"),
]


@pytest.mark.parametrize("hat,decorator", HATS)
def test_every_hat_renders(hat: dict, decorator: str):
    rendered = render_script(
        hat,
        [{"op": "move", "args": {"steps": 1}}],
        target="Sprite1",
        label="hat test",
    )

    assert f"@{decorator}(" in rendered
    change = transpile(rendered).changes[0]
    assert change.hat.to_dict() == hat
    assert change.target == "Sprite1"
    assert change.label == "hat test"
    assert change.action == "add_script"


def test_script_id_renders_a_replace_script():
    rendered = render_script(
        {"op": "when_flag_clicked"},
        [{"op": "move", "args": {"steps": 1}}],
        target="Sprite1",
        label="restart",
        script_id="ai-1",
    )

    assert 'script_id="ai-1"' in rendered
    change = transpile(rendered).changes[0]
    assert change.action == "replace_script"
    assert change.script_id == "ai-1"


def _roundtrip_block(block: dict, hat: dict | None = None) -> tuple[str, dict]:
    rendered = render_script(
        hat or {"op": "when_flag_clicked"},
        [block],
        target="S",
        label="f",
    )
    return rendered, transpile(rendered).changes[0].body[0].to_dict()


def _move(steps: int = 1) -> dict:
    return {"op": "move", "args": {"steps": steps}}


def test_forever_renders_while_true():
    block = {"op": "forever", "body": [_move()]}
    rendered, result = _roundtrip_block(block)

    assert "while True:" in rendered
    assert result == block


def test_repeat_renders_for_range():
    block = {"op": "repeat", "args": {"count": 4}, "body": [_move()]}
    rendered, result = _roundtrip_block(block)

    assert "for _ in range(4):" in rendered
    assert result == block


def test_if_and_if_else_roundtrip():
    if_block = {
        "op": "if",
        "args": {
            "condition": {
                "op": "touching",
                "args": {"target": "edge"},
            }
        },
        "body": [_move()],
    }
    rendered, result = _roundtrip_block(if_block)
    assert "if touching(\"edge\"):" in rendered
    assert result == if_block

    if_else = {
        "op": "if_else",
        "args": {
            "condition": {
                "op": "key_pressed",
                "args": {"key": "space"},
            }
        },
        "then": [{"op": "show"}],
        "else": [{"op": "hide"}],
    }
    rendered, result = _roundtrip_block(if_else)
    assert "else:" in rendered
    assert result == if_else


def test_elif_chain_renders_nested_if_else_and_roundtrips():
    original = transpile(
        source(
            """
            @on_flag(target="S")
            def f():
                if score > 10:
                    say("high")
                elif score > 5:
                    say("mid")
                else:
                    say("low")
            """
        )
    )
    block = original.changes[0].body[0].to_dict()
    rendered = render_script(
        {"op": "when_flag_clicked"}, [block], target="S", label="f"
    )

    assert "else:" in rendered
    assert transpile(rendered).changes[0].body[0].to_dict() == block


def test_repeat_until_renders_both_inversion_branches():
    not_condition = {
        "op": "repeat_until",
        "args": {
            "condition": {
                "op": "not",
                "args": {
                    "a": {
                        "op": "touching",
                        "args": {"target": "edge"},
                    }
                },
            }
        },
        "body": [_move()],
    }
    rendered, result = _roundtrip_block(not_condition)
    assert "while touching(\"edge\"):" in rendered
    assert result == not_condition

    plain_condition = {
        "op": "repeat_until",
        "args": {
            "condition": {
                "op": "greater_than",
                "args": {"a": {"op": "x_position"}, "b": 200},
            }
        },
        "body": [_move()],
    }
    rendered, result = _roundtrip_block(plain_condition)
    assert "while not (x_position() > 200):" in rendered
    assert result == plain_condition


def test_forever_if_renders_the_documented_while_true_if_shape():
    block = {
        "op": "forever_if",
        "args": {
            "condition": {
                "op": "key_pressed",
                "args": {"key": "space"},
            }
        },
        "body": [_move()],
    }
    rendered, result = _roundtrip_block(block)

    assert "while True:" in rendered
    assert 'if key_pressed("space"):' in rendered
    # The dialect has no distinct forever-if spelling, so this normalises to
    # the equivalent forever + if tree.
    assert result == {
        "op": "forever",
        "body": [
            {
                "op": "if",
                "args": block["args"],
                "body": [_move()],
            }
        ],
    }


def test_empty_bodies_render_a_dropped_string_placeholder():
    block = {"op": "forever", "body": []}
    rendered, result = _roundtrip_block(block)

    assert '""' in rendered
    assert result == {"op": "forever"}


@pytest.mark.parametrize(
    "condition,needle",
    [
        (
            {
                "op": "or",
                "args": {
                    "a": {
                        "op": "less_than",
                        "args": {"a": {"op": "x_position"}, "b": 10},
                    },
                    "b": {
                        "op": "equals",
                        "args": {"a": {"op": "x_position"}, "b": 10},
                    },
                },
            },
            "<=",
        ),
        (
            {
                "op": "or",
                "args": {
                    "a": {
                        "op": "greater_than",
                        "args": {"a": {"op": "x_position"}, "b": 10},
                    },
                    "b": {
                        "op": "equals",
                        "args": {"a": {"op": "x_position"}, "b": 10},
                    },
                },
            },
            ">=",
        ),
        (
            {
                "op": "not",
                "args": {
                    "a": {
                        "op": "equals",
                        "args": {
                            "a": {"op": "get_var", "args": {"name": "a"}},
                            "b": {"op": "get_var", "args": {"name": "b"}},
                        },
                    }
                },
            },
            "!=",
        ),
    ],
)
def test_comparison_shorthands_unexpand(condition: dict, needle: str):
    block = {
        "op": "if",
        "args": {"condition": condition},
        "body": [_move()],
    }
    rendered, result = _roundtrip_block(block)

    assert needle in rendered
    assert result == block


def test_negative_change_var_renders_minus_equals():
    block = {"op": "change_var", "args": {"name": "score", "delta": -3}}
    rendered, result = _roundtrip_block(block)

    assert "score -= 3" in rendered
    assert result == block


def test_join_with_a_string_literal_renders_an_explicit_join():
    block = {
        "op": "set_var",
        "args": {
            "name": "display",
            "value": {
                "op": "join",
                "args": {
                    "a": "Score: ",
                    "b": {"op": "get_var", "args": {"name": "score"}},
                },
            },
        },
    }
    rendered, result = _roundtrip_block(block)

    assert "join(" in rendered
    assert result == block


def test_add_with_a_string_literal_renders_the_explicit_call():
    value = {"op": "add", "args": {"a": "1", "b": 2}}
    block = {
        "op": "set_var",
        "args": {"name": "x", "value": value},
    }
    rendered, result = _roundtrip_block(block)

    assert "add(" in rendered
    assert result == block


def test_add_with_two_computed_values_renders_the_explicit_call():
    value = {
        "op": "add",
        "args": {
            "a": {"op": "get_var", "args": {"name": "a"}},
            "b": {"op": "get_var", "args": {"name": "b"}},
        },
    }
    block = {"op": "set_var", "args": {"name": "x", "value": value}}
    rendered, result = _roundtrip_block(block)

    assert "add(" in rendered
    assert result == block


def test_arithmetic_precedence_is_preserved_with_parentheses():
    value = {
        "op": "multiply",
        "args": {
            "a": {"op": "add", "args": {"a": 1, "b": 2}},
            "b": 3,
        },
    }
    block = {"op": "set_var", "args": {"name": "x", "value": value}}
    rendered, result = _roundtrip_block(block)

    assert "(1 + 2) * 3" in rendered
    assert result == block


def test_non_identifier_variable_names_use_explicit_calls():
    block = {
        "op": "set_var",
        "args": {
            "name": "left score",
            "value": {"op": "get_var", "args": {"name": "left score"}},
        },
    }
    rendered, result = _roundtrip_block(block)

    assert 'set_var("left score"' in rendered
    assert 'get_var("left score")' in rendered
    assert result == block


def test_unknown_op_raises_a_dsl_error():
    with pytest.raises(DSLError, match="cannot render op"):
        render_script(
            {"op": "when_flag_clicked"},
            [{"op": "unknown_block", "args": []}],
            target="Sprite1",
            label="broken",
        )


def test_unknown_hat_raises_a_dsl_error():
    with pytest.raises(DSLError, match="cannot render op"):
        render_script(
            {"op": "when_nothing_clicked"},
            [],
            target="Sprite1",
            label="broken",
        )


def test_module_changes_render_and_roundtrip():
    payload = {
        "summary": "modules",
        "changes": [
            {"action": "create_list", "name": "q", "items": ["a", 1]},
            {
                "action": "create_sprite",
                "name": "A",
                "costumes": [
                    {"library": "Animals/bat1-a.png", "name": "custom"}
                ],
                "x": 10,
            },
            {"action": "set_sprite", "target": "A", "x": 20, "visible": False},
            {"action": "add_costume", "target": "A", "library": "Animals/bat1-b.png"},
            {"action": "duplicate_sprite", "target": "A", "name": "B"},
            {"action": "delete_sprite", "target": "B"},
            {"action": "delete_script", "script_id": "ai-1"},
            {"action": "set_backdrop", "library": "Space/stars.gif", "select": False},
        ],
    }

    rendered = render_changeset(payload)
    changes = transpile(rendered).changes

    assert "set_sprite(\"A\", x=20, visible=False)" in rendered
    assert 'delete_script("ai-1")' in rendered
    assert changes[0].action == "create_list"
    assert changes[1].costumes[0].library == "Animals/bat1-a.png"
    # The dialect renders the library path only; a custom costume name is lost.
    assert changes[1].costumes[0].name == ""
    assert changes[2].visible is False


def test_non_ascii_strings_render_ascii_and_roundtrip():
    payload = {
        "summary": "caf\u00e9 \u2603",
        "notes": "na\u00efve",
        "changes": [
            {
                "action": "add_script",
                "target": "Sprite1",
                "label": "caf\u00e9",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "say", "args": {"text": "h\u00e9llo"}}],
            }
        ],
    }

    rendered = render_changeset(payload)
    assert rendered.isascii()

    changeset = transpile(rendered)
    assert changeset.summary == payload["summary"]
    assert changeset.notes == payload["notes"]
    assert changeset.changes[0].label == "caf\u00e9"


def stack_for(body: list[dict], hat: dict | None = None) -> list:
    changeset = ChangeSet.from_dict(
        {
            "summary": "detail test",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "test",
                    "hat": hat or {"op": "when_flag_clicked"},
                    "body": body,
                }
            ],
        }
    )
    return compile_changeset(changeset, ProjectContext.demo()).changes[0].stack


def test_render_sprite_detail_uses_dialect_bodies_and_fallbacks():
    context = ProjectContext.demo()
    sprite = context.sprites["Sprite1"]
    sprite.scripts.append(
        ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label="spin",
            hat="EventHatMorph",
            block_count=3,
            owned=True,
            tuples=stack_for(
                [
                    {
                        "op": "forever",
                        "body": [
                            {"op": "turn_right", "args": {"degrees": 15}},
                            {"op": "wait", "args": {"seconds": 0.5}},
                        ],
                    }
                ]
            ),
        )
    )
    sprite.scripts.append(
        ScriptSummary(
            script_id="ai-2",
            target="Sprite1",
            label="caf\u00e9",
            hat="EventHatMorph",
            block_count=1,
            owned=True,
            tuples=stack_for([{"op": "move", "args": {"steps": 1}}]),
        )
    )
    sprite.scripts.append(
        ScriptSummary(
            script_id="user-1",
            target="Sprite1",
            label="original",
            hat="EventHatMorph",
            block_count=1,
            owned=False,
        )
    )
    sprite.scripts.append(
        ScriptSummary(
            script_id="ai-3",
            target="Sprite1",
            label="broken",
            hat="EventHatMorph",
            block_count=1,
            owned=True,
            tuples=[
                [Sym("EventHatMorph"), "Scratch-StartClicked"],
                [Sym("mysterySelector"), 1],
            ],
        )
    )

    detail = render_sprite_detail(sprite)

    assert detail.isascii()
    assert detail.splitlines()[0] == sprite_detail_text(sprite).splitlines()[0]
    assert '- ai-1 "spin"' in detail
    assert '@on_flag(target="Sprite1", label="spin")' in detail
    assert "while True:" in detail
    assert "body omitted (user script, read-only)" in detail
    assert "unknown_block" in detail and "mysterySelector" in detail


def test_render_sprite_detail_truncates_like_the_json_detail():
    context = ProjectContext.demo()
    sprite = context.sprites["Sprite1"]
    sprite.scripts.append(
        ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label="spin",
            hat="EventHatMorph",
            block_count=21,
            owned=True,
            tuples=stack_for(
                [{"op": "move", "args": {"steps": 10}} for _ in range(20)]
            ),
        )
    )

    detail = render_sprite_detail(sprite, max_chars=180)

    assert "[sprite detail truncated" in detail
    assert len(detail) <= 180
