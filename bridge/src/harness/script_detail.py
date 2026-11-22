"""Turn Scratch block tuples into model-readable IR and per-sprite detail blocks.

The image sends each AI-owned script's ``tupleSequence`` with the normal project
context.  Nothing here enters the prompt until the model asks for a sprite with
``{"load_sprite": ["Bat"]}``; the agent then appends the rendered block bodies.
"""

from __future__ import annotations

import json
from typing import Any

from .catalog import SPECS, BlockSpec
from .context import ProjectContext, ScriptSummary, SpriteContext
from .smalltalk import Sym

#: Per-sprite detail is capped so one huge sprite cannot consume the whole turn.
MAX_DETAIL_CHARS = 24000

_SELECTOR_SPECS: dict[str, list[BlockSpec]] = {}
for _spec in SPECS:
    _SELECTOR_SPECS.setdefault(_spec.selector, []).append(_spec)


def _name(value: Any) -> str | None:
    if isinstance(value, Sym):
        return value.name
    if isinstance(value, str):
        return value
    return None


def _is_color(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and _name(value[0]) == "color"
    )


def _is_block(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and _name(value[0]) is not None
        and not _is_color(value)
    )


def _color(value: list[Any]) -> str:
    red, green, blue = (int(part) for part in value[1:4])
    return f"#{red:02x}{green:02x}{blue:02x}"


def _value(value: Any) -> Any:
    if _is_color(value):
        return _color(value)
    if _is_block(value):
        return decompile_block(value)
    if isinstance(value, list):
        return [_value(item) for item in value]
    if isinstance(value, Sym):
        return value.name
    return value


def _arg_value(spec: BlockSpec, arg_name: str, value: Any) -> Any:
    for arg in spec.args:
        if arg.name == arg_name and arg.type == "color":
            return _color(value) if _is_color(value) else _value(value)
    return _value(value)


def _unknown(selector: str, tuple_: list[Any]) -> dict[str, Any]:
    return {
        "op": "unknown_block",
        "selector": selector,
        "args": [_value(item) for item in tuple_[1:]],
    }


def decompile_block(tuple_: list[Any]) -> dict[str, Any]:
    """Convert one native Scratch block tuple to a change-set block object."""
    selector = _name(tuple_[0])
    if selector is None:
        return {"op": "unknown_block", "args": [_value(item) for item in tuple_]}

    # Variable reporters and setters use a shared carrier selector.
    if selector == "changeVariable":
        name = _value(tuple_[1]) if len(tuple_) > 1 else ""
        operation = _name(tuple_[2]) if len(tuple_) > 2 else ""
        value = _value(tuple_[3]) if len(tuple_) > 3 else 0
        if operation == "setVar:to:":
            return {"op": "set_var", "args": {"name": name, "value": value}}
        if operation == "changeVar:by:":
            return {"op": "change_var", "args": {"name": name, "delta": value}}
        return _unknown(selector, tuple_)
    if selector == "readVariable":
        return {"op": "get_var", "args": {"name": _value(tuple_[1]) if len(tuple_) > 1 else ""}}
    if selector == "computeFunction:of:":
        function = _value(tuple_[1]) if len(tuple_) > 1 else "abs"
        number = _value(tuple_[2]) if len(tuple_) > 2 else 0
        if function == "sqrt":
            return {"op": "sqrt", "args": {"n": number}}
        return {"op": "math_function", "args": {"function": function, "n": number}}

    specs = _SELECTOR_SPECS.get(selector, [])
    if len(specs) != 1:
        return _unknown(selector, tuple_)
    spec = specs[0]

    args: dict[str, Any] = {}
    for index, arg in enumerate(spec.args, start=1):
        if index >= len(tuple_):
            break
        args[arg.name] = _arg_value(spec, arg.name, tuple_[index])
    block: dict[str, Any] = {"op": spec.op}
    if args:
        block["args"] = args

    body_index = len(spec.args) + 1
    if spec.body == "body":
        body = tuple_[body_index] if body_index < len(tuple_) else []
        block["body"] = [
            decompile_block(child) for child in body if _is_block(child)
        ]
    elif spec.body == "then_else":
        then = tuple_[body_index] if body_index < len(tuple_) else []
        otherwise = tuple_[body_index + 1] if body_index + 1 < len(tuple_) else []
        block["then"] = [decompile_block(child) for child in then if _is_block(child)]
        block["else"] = [
            decompile_block(child) for child in otherwise if _is_block(child)
        ]
    return block


def _decompile_hat(tuple_: list[Any]) -> dict[str, Any]:
    selector = _name(tuple_[0])
    first = _value(tuple_[1]) if len(tuple_) > 1 else ""
    if selector == "EventHatMorph":
        if first == "Scratch-StartClicked":
            return {"op": "when_flag_clicked"}
        return {"op": "when_receive", "args": {"message": first}}
    if selector == "KeyEventHatMorph":
        return {"op": "when_key_pressed", "args": {"key": first}}
    if selector == "MouseClickEventHatMorph":
        return {"op": "when_clicked"}
    if selector == "StageClickEventHatMorph":
        return {"op": "when_stage_clicked"}
    if selector == "CloneEventHatMorph":
        return {"op": "when_clone_start"}
    if selector == "BackdropHatMorph":
        return {"op": "when_backdrop_switches", "args": {"backdrop": first}}
    if selector == "WhenLoudnessHatMorph":
        return {"op": "when_loudness_greater", "args": {"value": first}}
    if selector == "WhenTimerHatMorph":
        return {"op": "when_timer_greater", "args": {"value": first}}
    return _unknown(selector or "unknown", tuple_)


def decompile_script(tuples: list[Any]) -> dict[str, Any] | None:
    """Convert a script's tuple sequence (hat first) to ``hat`` + ``body``."""
    if not isinstance(tuples, list) or not tuples or not _is_block(tuples[0]):
        return None
    return {
        "hat": _decompile_hat(tuples[0]),
        "body": [decompile_block(item) for item in tuples[1:] if _is_block(item)],
    }


def _script_owner(script: ScriptSummary) -> str:
    if not script.owned:
        return "user script, read-only"
    if script.user_edited:
        return "ai-owned, edited outside the harness"
    return "ai-owned, editable"


def sprite_detail_text(
    sprite: SpriteContext, max_chars: int = MAX_DETAIL_CHARS
) -> str:
    """Render the exact script bodies for one sprite."""
    if sprite.is_stage:
        kind = "Stage"
    elif sprite.ai_owned:
        kind = "AI-created sprite"
    else:
        kind = "user sprite"
    header = (
        f'# Sprite detail: "{sprite.name}" ({kind}; '
        f"costumes={', '.join(sprite.costumes) or '-'}; "
        f"variables={', '.join(sprite.variables) or '-'}; "
        f"lists={', '.join(sprite.lists) or '-'})"
    )
    lines = [header]
    for script in sprite.scripts:
        line = (
            f'- {script.script_id} "{script.label}" [{script.hat}] '
            f"{script.block_count} blocks ({_script_owner(script)})"
        )
        if script.tuples:
            body = decompile_script(script.tuples)
            if body is not None:
                line += "\n  " + json.dumps(
                    body, ensure_ascii=True, separators=(",", ":")
                )
        elif not script.owned:
            line += "\n  body omitted (user script, read-only)"
        lines.append(line)

    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    marker = f"\n[sprite detail truncated {len(text) - max_chars} chars]"
    room = max(0, max_chars - len(marker))
    kept = text[:room].rsplit("\n", 1)[0]
    return kept + marker


def sprite_detail_index(context: ProjectContext) -> str:
    """One-line-per-sprite index of blocks that can be loaded on demand."""
    entries: list[str] = []
    for sprite in context.sprites.values():
        editable = [
            script for script in sprite.scripts if script.owned and script.tuples
        ]
        if not editable:
            continue
        described = ", ".join(
            f"{script.script_id} {script.label}" for script in editable
        )
        entries.append(f"  {sprite.name}: {described}")
    if not entries:
        return ""
    return (
        'Sprite script detail available (return {"load_sprite": ["Name"], '
        '"reason": "..."} to include exact block bodies):\n' + "\n".join(entries)
    )


def resolve_sprite_name(context: ProjectContext, name: str) -> str | None:
    """Resolve a sprite name case-insensitively to its context key."""
    folded = name.strip().casefold()
    for key in context.sprites:
        if key.casefold() == folded:
            return key
    return None
