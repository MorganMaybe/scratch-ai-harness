"""Mechanical Python-isms the transpiler now rewrites instead of rejecting.

Every case here used to cost a full repair round trip (a regenerated module)
for a spelling whose Scratch meaning is exact: ``-x`` is ``0 - x``,
``x -= e`` is ``x = x - e``, ``range(a, b)`` repeats ``b - a`` times, and a
``+`` whose operand is statically numeric (or textual) is ``add`` (or
``join``) just as a literal operand already selected.  The genuinely
ambiguous ``+`` - two names with no evidence in the module - is still the
line-quoted diagnostic.
"""

from __future__ import annotations

import textwrap

import pytest

from harness.context import ProjectContext
from harness.dsl import DSLErrors, transpile


def _script(body: str, prelude: str = "") -> list[dict]:
    text = (
        textwrap.dedent(prelude).strip("\n")
        + "\n\n"
        + '@on_flag(target="Sprite1", label="f")\n'
        + "def f():\n"
        + textwrap.indent(textwrap.dedent(body).strip("\n"), "    ")
        + "\n"
    )
    changeset = transpile(text, ProjectContext.demo())
    scripts = [c for c in changeset.changes if c.action == "add_script"]
    assert len(scripts) == 1
    return [block.to_dict() for block in scripts[0].body]


def _var(name: str) -> dict:
    return {"op": "get_var", "args": {"name": name}}


def test_unary_minus_on_a_variable_is_zero_minus():
    blocks = _script("change_x(-vx)", 'create_variable("vx")')
    assert blocks == [
        {
            "op": "change_x",
            "args": {"dx": {"op": "subtract", "args": {"a": 0, "b": _var("vx")}}},
        }
    ]


def test_negative_literal_stays_a_plain_number():
    assert _script("turn_right(-15)") == [
        {"op": "turn_right", "args": {"degrees": -15}}
    ]


def test_augmented_subtraction_of_an_expression():
    blocks = _script("vy -= gravity", 'create_variable("vy")\ncreate_variable("gravity")')
    assert blocks == [
        {
            "op": "set_var",
            "args": {
                "name": "vy",
                "value": {"op": "subtract", "args": {"a": _var("vy"), "b": _var("gravity")}},
            },
        }
    ]


@pytest.mark.parametrize("symbol, op", [("*", "multiply"), ("/", "divide"), ("%", "mod")])
def test_augmented_arithmetic(symbol, op):
    blocks = _script(f"speed {symbol}= 2", 'create_variable("speed")')
    assert blocks == [
        {
            "op": "set_var",
            "args": {"name": "speed", "value": {"op": op, "args": {"a": _var("speed"), "b": 2}}},
        }
    ]


def test_two_argument_range_with_literals_folds_the_count():
    blocks = _script("for _ in range(2, 7):\n    move(1)")
    assert blocks[0]["op"] == "repeat"
    assert blocks[0]["args"] == {"count": 5}


def test_two_argument_range_with_a_variable_subtracts():
    blocks = _script("for _ in range(1, n):\n    move(1)", 'create_variable("n")')
    assert blocks[0]["args"]["count"] == {
        "op": "subtract",
        "args": {"a": _var("n"), "b": 1},
    }


def test_str_and_float_are_identity():
    blocks = _script('say(str(score))', 'create_variable("score")')
    assert blocks == [{"op": "say", "args": {"text": _var("score")}}]


def test_square_of_a_name_is_multiply():
    blocks = _script("d = dx ** 2", 'create_variable("d")\ncreate_variable("dx")')
    assert blocks[0]["args"]["value"] == {
        "op": "multiply",
        "args": {"a": _var("dx"), "b": _var("dx")},
    }


def test_square_root_power_is_sqrt():
    blocks = _script("d = dx ** 0.5", 'create_variable("d")\ncreate_variable("dx")')
    assert blocks[0]["args"]["value"] == {"op": "sqrt", "args": {"n": _var("dx")}}


def test_power_of_a_reporter_stays_rejected():
    with pytest.raises(DSLErrors):
        _script("d = random(1, 5) ** 2", 'create_variable("d")')


def test_plus_with_a_numeric_reporter_is_add():
    blocks = _script("set_y(y_position() + vy)", 'create_variable("vy")')
    assert blocks[0]["args"]["y"]["op"] == "add"


def test_plus_with_a_text_reporter_is_join():
    blocks = _script("say(costume_name() + suffix)", 'create_variable("suffix")')
    assert blocks[0]["args"]["text"]["op"] == "join"


def test_plus_with_an_arithmetic_operand_is_add():
    blocks = _script(
        "x = x + vx * 2", 'create_variable("x")\ncreate_variable("vx")'
    )
    assert blocks[0]["args"]["value"]["op"] == "add"


def test_doodle_jump_physics_line_resolves_from_module_evidence():
    """The audited ``py = py + vy`` that failed three repairs live."""
    blocks = _script(
        """
        py = 0
        vy = 10
        while True:
            vy -= 1
            py = py + vy
            wait(0.03)
        """,
        'create_variable("py")\ncreate_variable("vy")',
    )
    loop = blocks[2]
    assert loop["op"] == "forever"
    assert loop["body"][1]["args"]["value"]["op"] == "add"


def test_text_evidence_selects_join():
    blocks = _script(
        """
        greeting = "Hi "
        name = answer()
        say(greeting + name)
        """,
        'create_variable("greeting")\ncreate_variable("name")',
    )
    assert blocks[2]["args"]["text"]["op"] == "join"


def test_two_names_without_evidence_stay_ambiguous():
    with pytest.raises(DSLErrors) as caught:
        _script("say(a + b)", 'create_variable("a")\ncreate_variable("b")')
    assert "ambiguous" in caught.value.errors[0].format()


def test_default_initial_zero_is_not_evidence():
    with pytest.raises(DSLErrors) as caught:
        _script(
            "say(first + last)",
            'create_variable("first", initial=0)\ncreate_variable("last", initial=0)',
        )
    assert "ambiguous" in caught.value.errors[0].format()


def test_conflicting_evidence_stays_ambiguous():
    with pytest.raises(DSLErrors) as caught:
        _script(
            """
            a = 1
            a = "x"
            say(a + b)
            """,
            'create_variable("a")\ncreate_variable("b")',
        )
    assert any("ambiguous" in e.format() for e in caught.value.errors)
