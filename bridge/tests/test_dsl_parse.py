from __future__ import annotations

import textwrap

from harness.context import ProjectContext, SpriteContext
from harness.dsl import api_reference, lint, transpile
from harness.dsl.vocab import CALLABLE_SPECS
from harness.validator import validate_changeset


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


def test_square_script_matches_the_json_ir_exactly():
    changeset = transpile(SQUARE)

    assert changeset.to_dict() == {
        "summary": "Updated the project.",
        "changes": [
            {
                "action": "add_script",
                "target": "Sprite1",
                "label": "square",
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


def test_score_hud_uses_join_and_get_var():
    text = source(
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

    changeset = transpile(text)

    assert changeset.to_dict() == {
        "summary": "Score HUD.",
        "changes": [
            {
                "action": "create_variable",
                "name": "score",
                "scope": "global",
                "initial": 0,
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


def test_score_increment_is_change_var():
    text = source(
        """
        create_variable("score")
        @on_click(target="Star")
        def caught():
            score += 1
        """
    )

    body = transpile(text).changes[1].body
    assert [block.to_dict() for block in body] == [
        {"op": "change_var", "args": {"name": "score", "delta": 1}}
    ]


def test_score_decrement_literal_is_negative_change_var():
    text = source(
        """
        create_variable("score")
        @on_click(target="Star")
        def caught():
            score -= 2
        """
    )

    body = transpile(text).changes[1].body
    assert body[0].to_dict() == {
        "op": "change_var",
        "args": {"name": "score", "delta": -2},
    }


BEACH = source(
    """
    summary("Beach with wandering crabs.")
    set_backdrop("Space/stars.gif")
    create_variable("score", scope="global", initial=0)
    create_sprite("Crab1",
        costumes=["Animals/bat1-a.png", "Animals/bat1-b.png"],
        x=-100, y=-80, size=40, rotation_style="left-right")
    create_sprite("Crab2",
        costumes=["Animals/bat1-a.png", "Animals/bat1-b.png"],
        x=100, y=-80, size=40, rotation_style="left-right")

    @on_flag(target="Crab1", label="wander")
    def crab1_wander():
        while True:
            move(2)
            turn_right(random(-20, 20))
            bounce()
            next_costume()
            wait(0.2)

    @on_flag(target="Crab2", label="wander")
    def crab2_wander():
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


def _wander_body() -> list[dict]:
    return [
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
    ]


def test_beach_scene_matches_the_expected_change_set():
    changeset = transpile(BEACH)

    assert changeset.to_dict() == {
        "summary": "Beach with wandering crabs.",
        "changes": [
            {
                "action": "set_backdrop",
                "library": "Space/stars.gif",
                "select": True,
            },
            {
                "action": "create_variable",
                "name": "score",
                "scope": "global",
                "initial": 0,
            },
            {
                "action": "create_sprite",
                "name": "Crab1",
                "costumes": [
                    {"library": "Animals/bat1-a.png"},
                    {"library": "Animals/bat1-b.png"},
                ],
                "x": -100,
                "y": -80,
                "size": 40,
                "rotation_style": "left-right",
            },
            {
                "action": "create_sprite",
                "name": "Crab2",
                "costumes": [
                    {"library": "Animals/bat1-a.png"},
                    {"library": "Animals/bat1-b.png"},
                ],
                "x": 100,
                "y": -80,
                "size": 40,
                "rotation_style": "left-right",
            },
            {
                "action": "add_script",
                "target": "Crab1",
                "label": "wander",
                "hat": {"op": "when_flag_clicked"},
                "body": _wander_body(),
            },
            {
                "action": "add_script",
                "target": "Crab2",
                "label": "wander",
                "hat": {"op": "when_flag_clicked"},
                "body": _wander_body(),
            },
            {
                "action": "add_script",
                "target": "Star",
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
        ],
    }


def _beach_context() -> ProjectContext:
    return ProjectContext(
        target="Sprite1",
        sprites={
            "Stage": SpriteContext(
                name="Stage", is_stage=True, costumes=["stars"]
            ),
            "Sprite1": SpriteContext(name="Sprite1", costumes=["costume1"]),
            "Star": SpriteContext(name="Star", costumes=["costume1"]),
        },
    )


def test_beach_scene_passes_the_existing_validator():
    context = _beach_context()
    changeset = transpile(BEACH, context)

    assert validate_changeset(changeset, context) == []


def test_script_id_turns_the_change_into_replace_script():
    text = source(
        """
        @on_flag(script_id="ai-1", target="Sprite1")
        def restart():
            stop_all()
        """
    )

    change = transpile(text).changes[0]
    assert change.action == "replace_script"
    assert change.script_id == "ai-1"
    assert change.target == "Sprite1"
    assert change.label == "restart"
    assert change.hat.op == "when_flag_clicked"


def test_while_true_becomes_forever():
    text = source(
        """
        @on_flag(target="S")
        def f():
            while True:
                move(1)
        """
    )

    body = transpile(text).changes[0].body
    assert [block.to_dict() for block in body] == [
        {"op": "forever", "body": [{"op": "move", "args": {"steps": 1}}]}
    ]


def test_while_not_becomes_repeat_until_the_condition():
    text = source(
        """
        @on_flag(target="S")
        def f():
            while not touching("edge"):
                move(1)
        """
    )

    block = transpile(text).changes[0].body[0].to_dict()
    assert block["op"] == "repeat_until"
    assert block["args"]["condition"] == {
        "op": "touching",
        "args": {"target": "edge"},
    }


def test_while_condition_becomes_repeat_until_not_condition():
    text = source(
        """
        @on_flag(target="S")
        def f():
            while x_position() > 200:
                move(1)
        """
    )

    block = transpile(text).changes[0].body[0].to_dict()
    assert block["args"]["condition"] == {
        "op": "not",
        "args": {
            "a": {
                "op": "greater_than",
                "args": {"a": {"op": "x_position"}, "b": 200},
            }
        },
    }


def test_for_range_literal_count():
    text = source(
        """
        @on_flag(target="S")
        def f():
            for _ in range(4):
                move(1)
        """
    )

    block = transpile(text).changes[0].body[0].to_dict()
    assert block == {
        "op": "repeat",
        "args": {"count": 4},
        "body": [{"op": "move", "args": {"steps": 1}}],
    }


def test_for_range_count_can_be_a_reporter():
    text = source(
        """
        @on_flag(target="S")
        def f():
            for _ in range(random(1, 10)):
                move(1)
        """
    )

    block = transpile(text).changes[0].body[0].to_dict()
    assert block["args"]["count"] == {
        "op": "random",
        "args": {"from": 1, "to": 10},
    }


def test_while_not_a_variable_accepts_the_flag_pattern():
    text = source(
        """
        create_variable("done")
        @on_flag(target="S")
        def f():
            while not done:
                move(1)
        """
    )

    block = transpile(text).changes[1].body[0].to_dict()
    assert block["args"]["condition"] == {
        "op": "get_var",
        "args": {"name": "done"},
    }


def test_if_not_a_variable_is_a_boolean_condition():
    text = source(
        """
        create_variable("done")
        @on_flag(target="S")
        def f():
            if not done:
                move(1)
        """
    )

    block = transpile(text).changes[1].body[0].to_dict()
    assert block["args"]["condition"] == {
        "op": "not",
        "args": {"a": {"op": "get_var", "args": {"name": "done"}}},
    }


def test_elif_chain_nests_the_next_if_inside_else():
    text = source(
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

    block = transpile(text).changes[0].body[0].to_dict()
    assert block["op"] == "if_else"
    assert block["then"] == [{"op": "say", "args": {"text": "high"}}]
    nested = block["else"][0]
    assert nested["op"] == "if_else"
    assert nested["then"] == [{"op": "say", "args": {"text": "mid"}}]
    assert nested["else"] == [{"op": "say", "args": {"text": "low"}}]


def test_not_equals_becomes_not_equals_block():
    text = source(
        """
        @on_flag(target="S")
        def f():
            if a != b:
                move(1)
        """
    )

    condition = transpile(text).changes[0].body[0].args["condition"].to_dict()
    assert condition == {
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
    }


def test_less_than_or_equal_becomes_or_of_less_than_and_equals():
    text = source(
        """
        @on_flag(target="S")
        def f():
            if a <= b:
                move(1)
        """
    )

    condition = transpile(text).changes[0].body[0].args["condition"].to_dict()
    assert condition == {
        "op": "or",
        "args": {
            "a": {
                "op": "less_than",
                "args": {
                    "a": {"op": "get_var", "args": {"name": "a"}},
                    "b": {"op": "get_var", "args": {"name": "b"}},
                },
            },
            "b": {
                "op": "equals",
                "args": {
                    "a": {"op": "get_var", "args": {"name": "a"}},
                    "b": {"op": "get_var", "args": {"name": "b"}},
                },
            },
        },
    }


def test_module_order_is_preserved_around_a_def():
    text = source(
        """
        create_variable("n")
        @on_flag(target="Sprite1")
        def foo():
            n = 1
        set_sprite("Sprite1", x=10)
        """
    )

    changes = transpile(text).changes
    assert [change.action for change in changes] == [
        "create_variable",
        "add_script",
        "set_sprite",
    ]


def test_positional_decorator_value_feeds_the_hat_arg():
    text = source(
        """
        @on_receive("go", target="Crab1")
        def go():
            show()
        """
    )

    change = transpile(text).changes[0]
    assert change.hat.to_dict() == {
        "op": "when_receive",
        "args": {"message": "go"},
    }
    assert change.label == "go"


def test_label_defaults_to_the_def_name():
    text = source(
        """
        @on_flag(target="S")
        def my_script():
            move(1)
        """
    )

    assert transpile(text).changes[0].label == "my_script"


def test_summary_and_notes_last_one_wins():
    text = source(
        """
        summary("first")
        notes("old")
        summary("second")
        notes("new")
        create_variable("x")
        """
    )

    changeset = transpile(text)
    assert changeset.summary == "second"
    assert changeset.notes == "new"


def test_python_and_json_fences_are_both_accepted():
    body = '@on_flag(target="Sprite1")\ndef f():\n    move(1)'

    for fence in ("python", "json", ""):
        text = f"\n```{fence}\n{body}\n```\n"
        changeset = transpile(text)
        assert changeset.changes[0].body[0].to_dict() == {
            "op": "move",
            "args": {"steps": 1},
        }


def test_rotation_alias_matches_the_design_example():
    text = source(
        """
        create_sprite("Crab1",
            costumes=["Animals/bat1-a.png"], rotation="left-right")
        """
    )

    change = transpile(text).changes[0]
    assert change.rotation_style == "left-right"


def test_negative_number_literals_are_literals_not_unary_blocks():
    text = source(
        """
        @on_flag(target="S")
        def f():
            move(-10)
            turn_right(random(-20, 20))
        """
    )

    body = transpile(text).changes[0].body
    assert body[0].to_dict() == {"op": "move", "args": {"steps": -10}}
    assert body[1].args["degrees"].args["from"] == -20


def test_api_reference_is_generated_from_the_catalog():
    reference = api_reference()

    assert "generated from the block catalog" in reference
    for op in CALLABLE_SPECS:
        assert f"{op}(" in reference, op
    assert "repeat(count)" not in reference
    assert "random(from, to)" in reference
    assert "positional only" in reference
    assert "create_sprite(name" in reference
    assert 'create_variable(name, scope="global", target=None, initial=0)' in reference
    assert "@on_receive(message" in reference
    assert "Do not call repeat()" in reference


def test_lint_is_empty_for_clean_source_and_lists_diagnostics_otherwise():
    assert lint(SQUARE) == []

    diagnostics = lint(
        '@on_flag(target="S")\ndef f():\n    jump(1)'
    )
    assert len(diagnostics) == 1
    assert "unknown function jump()" in diagnostics[0]
    assert diagnostics[0].startswith("line 3: ")
