from __future__ import annotations

import pytest

from harness.block_ir import Block, IRError, Script
from harness.compiler import compile_block, compile_script
from harness.smalltalk import Sym, to_literal


def square_script() -> Script:
    return Script.from_dict(
        {
            "target": "Sprite1",
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
    )


def test_compile_square():
    stack = compile_script(square_script())
    assert stack[0] == [Sym("EventHatMorph"), "Scratch-StartClicked"]
    assert stack[1] == [Sym("clearPenTrails")]
    assert stack[2] == [Sym("putPenDown")]
    assert stack[3] == [
        Sym("doRepeat"),
        4,
        [
            [Sym("forward:"), 100],
            [Sym("turnRight:"), 90],
        ],
    ]
    assert stack[4] == [Sym("putPenUp")]


def test_emit_square_literal():
    literal = to_literal(compile_script(square_script()))
    assert literal.startswith("#(")
    assert "#(#EventHatMorph 'Scratch-StartClicked')" in literal
    assert "#(#forward: 100)" in literal
    assert "#(#doRepeat 4 #(" in literal


def test_compile_variable_blocks():
    block = Block.from_dict({"op": "set_var", "args": {"name": "score", "value": 3}})
    assert compile_block(block) == [Sym("changeVariable"), "score", Sym("setVar:to:"), 3]
    block = Block.from_dict({"op": "change_var", "args": {"name": "score", "delta": 1}})
    assert compile_block(block) == [Sym("changeVariable"), "score", Sym("changeVar:by:"), 1]
    block = Block.from_dict({"op": "get_var", "args": {"name": "score"}})
    assert compile_block(block) == [Sym("readVariable"), "score"]


def test_compile_if_else():
    block = Block.from_dict(
        {
            "op": "if_else",
            "args": {
                "condition": {
                    "op": "greater_than",
                    "args": {"a": {"op": "x_position"}, "b": 0},
                }
            },
            "then": [{"op": "say", "args": {"text": "right"}}],
            "else": [{"op": "say", "args": {"text": "left"}}],
        }
    )
    tuple_ = compile_block(block)
    assert tuple_[0] == Sym("doIfElse")
    assert tuple_[1] == [Sym(">"), [Sym("xpos")], 0]
    assert tuple_[2] == [[Sym("say:"), "right"]]
    assert tuple_[3] == [[Sym("say:"), "left"]]


def test_compile_sqrt_fixed_arg():
    block = Block.from_dict({"op": "sqrt", "args": {"n": 9}})
    assert compile_block(block) == [Sym("computeFunction:of:"), "sqrt", 9]


def test_unknown_block():
    block = Block.from_dict({"op": "move_to", "args": {}})
    with pytest.raises(IRError):
        compile_block(block)


def test_newline_rejected_by_emitter():
    with pytest.raises(ValueError):
        to_literal("hello\nworld")
