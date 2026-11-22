from __future__ import annotations

from harness.block_ir import ChangeSet
from harness.changeset import compile_changeset
from harness.context import ProjectContext, ScriptSummary
from harness.protocol import parse_literal
from harness.smalltalk import Sym, to_literal
from harness.script_detail import (
    decompile_script,
    resolve_sprite_name,
    sprite_detail_index,
    sprite_detail_text,
)


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
    compiled = compile_changeset(changeset, ProjectContext.demo())
    return compiled.changes[0].stack


def test_decompile_nested_control_blocks():
    tuples = stack_for(
        [
            {
                "op": "forever",
                "body": [
                    {"op": "move", "args": {"steps": 10}},
                    {"op": "bounce"},
                    {
                        "op": "add_to_list",
                        "args": {
                            "item": {"op": "y_position"},
                            "list": "edge_ys",
                        },
                    },
                ],
            }
        ]
    )
    script = decompile_script(tuples)
    assert script is not None
    assert script["hat"] == {"op": "when_flag_clicked"}
    forever = script["body"][0]
    assert forever["op"] == "forever"
    assert forever["body"][0] == {"op": "move", "args": {"steps": 10}}
    assert forever["body"][1] == {"op": "bounce"}
    assert forever["body"][2]["args"]["item"] == {"op": "y_position"}


def test_decompile_if_else_and_variables():
    tuples = stack_for(
        [
            {"op": "set_var", "args": {"name": "score", "value": 0}},
            {"op": "change_var", "args": {"name": "score", "delta": 1}},
            {
                "op": "if_else",
                "args": {"condition": {"op": "get_var", "args": {"name": "score"}}},
                "then": [{"op": "pen_down"}],
                "else": [{"op": "pen_up"}],
            },
        ]
    )
    body = decompile_script(tuples)["body"]
    assert body[0] == {"op": "set_var", "args": {"name": "score", "value": 0}}
    assert body[1] == {"op": "change_var", "args": {"name": "score", "delta": 1}}
    assert body[2]["op"] == "if_else"
    assert body[2]["then"] == [{"op": "pen_down"}]
    assert body[2]["else"] == [{"op": "pen_up"}]


def test_decompile_colors_round_trip():
    tuples = stack_for(
        [
            {"op": "set_pen_color", "args": {"color": "#ff8800"}},
            {"op": "touching_color", "args": {"color": "#00ff00"}},
        ]
    )
    body = decompile_script(tuples)["body"]
    assert body[0] == {"op": "set_pen_color", "args": {"color": "#ff8800"}}
    assert body[1] == {"op": "touching_color", "args": {"color": "#00ff00"}}


def test_decompile_hats():
    cases = [
        ({"op": "when_receive", "args": {"message": "start"}}, "when_receive"),
        ({"op": "when_key_pressed", "args": {"key": "space"}}, "when_key_pressed"),
        ({"op": "when_clone_start"}, "when_clone_start"),
        (
            {"op": "when_backdrop_switches", "args": {"backdrop": "stars"}},
            "when_backdrop_switches",
        ),
        (
            {"op": "when_timer_greater", "args": {"value": 3}},
            "when_timer_greater",
        ),
    ]
    for hat, op in cases:
        script = decompile_script(stack_for([], hat=hat))
        assert script["hat"]["op"] == op, (hat, script)


def test_decompile_join_reporter():
    tuples = stack_for(
        [
            {
                "op": "set_var",
                "args": {
                    "name": "display",
                    "value": {
                        "op": "join",
                        "args": {
                            "a": {"op": "get_var", "args": {"name": "display"}},
                            "b": "0",
                        },
                    },
                },
            }
        ]
    )
    body = decompile_script(tuples)["body"]
    assert body[0] == {
        "op": "set_var",
        "args": {
            "name": "display",
            "value": {
                "op": "join",
                "args": {
                    "a": {"op": "get_var", "args": {"name": "display"}},
                    "b": "0",
                },
            },
        },
    }


def test_unknown_tuple_falls_back_without_crashing():
    script = decompile_script(
        [
            [Sym("EventHatMorph"), "Scratch-StartClicked"],
            [Sym("mysterySelector"), 1, "two"],
        ]
    )
    assert script["body"][0]["op"] == "unknown_block"
    assert script["body"][0]["selector"] == "mysterySelector"


def test_sprite_detail_text_and_index():
    context = ProjectContext.demo()
    sprite = context.sprites["Sprite1"]
    sprite.scripts.append(
        ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label="spin",
            hat="EventHatMorph",
            block_count=2,
            owned=True,
            tuples=stack_for([{"op": "turn_right", "args": {"degrees": 15}}]),
        )
    )
    sprite.scripts.append(
        ScriptSummary(
            script_id="user-1",
            target="Sprite1",
            label="original EventHatMorph",
            hat="EventHatMorph",
            block_count=1,
            owned=False,
        )
    )
    text = sprite_detail_text(sprite)
    assert '# Sprite detail: "Sprite1"' in text
    assert 'ai-1 "spin"' in text
    assert "turn_right" in text
    assert "user-1" in text and "body omitted" in text
    index = sprite_detail_index(context)
    assert "Sprite1" in index and "ai-1 spin" in index
    assert "user-1" not in index
    assert resolve_sprite_name(context, "sprite1") == "Sprite1"
    assert resolve_sprite_name(context, "missing") is None


def test_context_keeps_script_tuples_from_the_eighth_element():
    literal = to_literal(
        [
            "Sprite1",
            [
                [
                    "Sprite1",
                    False,
                    [],
                    [],
                    ["costume1"],
                    [],
                    [
                        [
                            "ai-1",
                            "spin",
                            "EventHatMorph",
                            2,
                            "hash",
                            True,
                            False,
                            [
                                [Sym("EventHatMorph"), "Scratch-StartClicked"],
                                [Sym("forward:"), 10],
                            ],
                        ]
                    ],
                    [0, 0, 90, 100, True, "normal", True, 1],
                ]
            ],
        ]
    )
    context = ProjectContext.from_literal(parse_literal(literal))
    script = context.sprites["Sprite1"].scripts[0]
    assert script.tuples == [
        [Sym("EventHatMorph"), "Scratch-StartClicked"],
        [Sym("forward:"), 10],
    ]


def test_old_seven_element_scripts_still_parse():
    literal = to_literal(
        [
            "Sprite1",
            [
                [
                    "Sprite1",
                    False,
                    [],
                    [],
                    ["costume1"],
                    [],
                    [["ai-1", "spin", "EventHatMorph", 1, "hash", True, False]],
                    [0, 0, 90, 100, True, "normal", True, 1],
                ]
            ],
        ]
    )
    context = ProjectContext.from_literal(parse_literal(literal))
    assert context.sprites["Sprite1"].scripts[0].tuples is None
