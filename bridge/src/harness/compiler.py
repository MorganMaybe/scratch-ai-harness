from __future__ import annotations

from typing import Any

from .block_ir import Block, IRError, Script
from .catalog import COLOR_RE, spec_for
from .smalltalk import Sym


def compile_script(script: Script) -> list[list[Any]]:
    return [compile_hat(script.hat)] + [compile_block(block) for block in script.body]


def compile_hat(block: Block) -> list[Any]:
    spec = spec_for(block.op)
    if spec is None or spec.kind != "hat":
        raise IRError(f"{block.op!r} is not a hat block")
    op = block.op
    if op == "when_flag_clicked":
        return [Sym("EventHatMorph"), "Scratch-StartClicked"]
    if op == "when_key_pressed":
        return [Sym("KeyEventHatMorph"), _arg(block, "key")]
    if op == "when_clicked":
        return [Sym("MouseClickEventHatMorph")]
    if op == "when_receive":
        return [Sym("EventHatMorph"), _arg(block, "message")]
    if op == "when_stage_clicked":
        return [Sym("StageClickEventHatMorph")]
    if op == "when_clone_start":
        return [Sym("CloneEventHatMorph")]
    if op == "when_backdrop_switches":
        return [Sym("BackdropHatMorph"), _arg(block, "backdrop")]
    if op == "when_loudness_greater":
        return [Sym("WhenLoudnessHatMorph"), compile_arg(_arg(block, "value"))]
    if op == "when_timer_greater":
        return [Sym("WhenTimerHatMorph"), compile_arg(_arg(block, "value"))]
    raise IRError(f"unsupported hat: {op}")


def compile_block(block: Block) -> list[Any]:
    spec = spec_for(block.op)
    if spec is None:
        raise IRError(f"unknown block: {block.op}")
    if block.op == "set_var":
        return [Sym("changeVariable"), _arg(block, "name"), Sym("setVar:to:"), compile_arg(_arg(block, "value"))]
    if block.op == "change_var":
        return [Sym("changeVariable"), _arg(block, "name"), Sym("changeVar:by:"), compile_arg(_arg(block, "delta"))]
    if block.op == "get_var":
        return [Sym("readVariable"), _arg(block, "name")]
    if block.op == "sqrt":
        return [Sym("computeFunction:of:"), "sqrt", compile_arg(_arg(block, "n"))]

    tuple_: list[Any] = [Sym(spec.selector)]
    for arg_spec in spec.args:
        value = _arg(block, arg_spec.name)
        tuple_.append(
            _compile_color(value) if arg_spec.type == "color" else compile_arg(value)
        )

    if spec.body == "body":
        tuple_.append([compile_block(child) for child in block.body])
    elif spec.body == "then_else":
        tuple_.append([compile_block(child) for child in block.then])
        tuple_.append([compile_block(child) for child in block.else_])
    else:
        if block.body or block.then or block.else_:
            raise IRError(f"{block.op} does not take a body")
    return tuple_


def _compile_color(value: Any) -> list[Any]:
    if not isinstance(value, str) or COLOR_RE.match(value) is None:
        raise IRError("color arguments must be '#rrggbb' strings")
    return [
        Sym("color"),
        int(value[1:3], 16),
        int(value[3:5], 16),
        int(value[5:7], 16),
    ]


def compile_arg(value: Any) -> Any:
    if isinstance(value, Block):
        return compile_block(value)
    if isinstance(value, dict):
        raise IRError("argument objects must use the block shape with an 'op'")
    return value


def _arg(block: Block, name: str) -> Any:
    if name not in block.args:
        raise IRError(f"{block.op} is missing argument {name!r}")
    return block.args[name]
