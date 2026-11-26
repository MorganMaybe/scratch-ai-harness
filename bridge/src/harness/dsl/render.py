"""Render block IR back to Scratch-Python source.

The renderer is the inverse of :mod:`harness.dsl.parse`: it turns the JSON
change-set shapes the harness already stores into dialect text that
``transpile`` accepts.  It is deliberately conservative -- when a tree has no
exact dialect spelling, it either uses an explicit catalog call or raises
:class:`~harness.dsl.errors.DSLError` rather than emitting text that would
transpile into different blocks.

Known lossy/normalising cases:

* ``create_sprite`` costume ``name`` fields are dropped; only the library
  path is rendered, which re-parses to the default (stem) name.
* ``forever_if`` renders as ``while True:`` containing ``if cond:``; the
  dialect has no distinct forever-if spelling, so it re-transpiles to the
  equivalent ``forever`` + ``if`` tree.
* Empty bodies render as a bare string statement (``""``), which the
  transpiler drops, preserving the empty block body.
"""

from __future__ import annotations

import json
import keyword
import math
from typing import Any

from ..catalog import SPRITE_TARGET_OPS, spec_for
from ..context import SpriteContext
from ..script_detail import MAX_DETAIL_CHARS, _script_owner, decompile_script
from .errors import DSLError
from .vocab import (
    CALLABLE_SPECS,
    COMMAND_OPS,
    FUNCTION_NAMES,
    HAT_SPECS,
    arg_specs,
)

#: Decorator name for each catalog hat op.
_HAT_DECORATORS: dict[str, str] = {op: name for name, op in HAT_SPECS.items()}

_INDENT = "    "

#: Ops rendered with Python infix syntax.  Operands that are themselves one of
#: these are parenthesised so the rendered Python tree matches the IR tree.
_INFIX_OPS: frozenset[str] = frozenset(
    {
        "add",
        "subtract",
        "multiply",
        "divide",
        "mod",
        "less_than",
        "greater_than",
        "equals",
        "not",
        "and",
        "or",
    }
)

_ARITHMETIC_SYMBOLS: dict[str, str] = {
    "subtract": "-",
    "multiply": "*",
    "divide": "/",
    "mod": "%",
}

_COMPARISON_SYMBOLS: dict[str, str] = {
    "less_than": "<",
    "greater_than": ">",
    "equals": "==",
}

#: Ops with a dedicated Python spelling in expression position.
_DIRECT_EXPR_OPS: frozenset[str] = frozenset(
    {
        "get_var",
        "join",
        "add",
        "not",
        "and",
        "or",
        *_ARITHMETIC_SYMBOLS,
        *_COMPARISON_SYMBOLS,
    }
)

#: Ops with a dedicated Python statement/control spelling.
_CONTROL_BLOCK_OPS: frozenset[str] = frozenset(
    {
        "forever",
        "repeat",
        "if",
        "if_else",
        "repeat_until",
        "forever_if",
        "set_var",
        "change_var",
    }
)

_LITERAL_ARG_TYPES: frozenset[str] = frozenset(
    {
        "string",
        "color",
        "list",
        "list_index",
        "clone_target",
    }
)


# -- small helpers -------------------------------------------------------


def _cannot_render(op: Any, detail: str = "") -> DSLError:
    message = f"cannot render op {op!r}"
    if detail:
        message += f": {detail}"
    return DSLError(message)


def _indent(text: str, level: int) -> str:
    return _INDENT * level + text


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _ascii(value: Any) -> str:
    """Escape a free-text fragment for the ASCII-only detail header."""
    return json.dumps(str(value), ensure_ascii=True)[1:-1]


def _is_block(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("op"), str)


def _is_join_block(value: Any) -> bool:
    return _is_block(value) and value.get("op") == "join"


def _require_dict(value: Any, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DSLError(f"{what} must be an object")
    return value


def _require_list(value: Any, what: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DSLError(f"{what} must be a list")
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _number_text(value: int | float) -> str:
    if isinstance(value, float) and not math.isfinite(value):
        raise DSLError(f"cannot render non-finite number {value!r}")
    return repr(value)


def _module_value(value: Any) -> str:
    """Render one literal for a module-level change call."""
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    if _is_number(value):
        return _number_text(value)
    if isinstance(value, list):
        return _module_list(value)
    if value is None:
        raise DSLError("cannot render a None module argument")
    raise DSLError(f"cannot render module argument {value!r}")


def _module_list(values: list[Any]) -> str:
    parts: list[str] = []
    for value in values:
        if value is None or isinstance(value, (dict, list, tuple)):
            raise DSLError(f"cannot render list item {value!r}")
        parts.append(_module_value(value))
    return "[" + ", ".join(parts) + "]"


def _is_bare_name(name: Any) -> bool:
    """Whether a variable name can appear as a bare Python identifier."""
    return (
        isinstance(name, str)
        and name.isascii()
        and name.isidentifier()
        and not keyword.iskeyword(name)
        and name != "_"
        and name not in FUNCTION_NAMES
    )


def _def_name(label: str) -> str:
    base = "".join(
        char.lower()
        if ("a" <= char.lower() <= "z" or "0" <= char <= "9" or char == "_")
        else "_"
        for char in label
    )
    if not base:
        base = "script"
    if base[0].isdigit():
        base = "script_" + base
    if keyword.iskeyword(base):
        base += "_script"
    return base


# -- expressions ---------------------------------------------------------


def _args(block: dict[str, Any]) -> dict[str, Any]:
    args = block.get("args")
    if args is None:
        return {}
    if not isinstance(args, dict):
        raise _cannot_render(block.get("op"), "args must be an object")
    return args


def _arg(block: dict[str, Any], name: str) -> Any:
    args = _args(block)
    if name not in args or args[name] is None:
        raise _cannot_render(block.get("op"), f"missing argument '{name}'")
    return args[name]


def _check_args(block: dict[str, Any], names: tuple[str, ...]) -> None:
    args = _args(block)
    extra = set(args) - set(names)
    if extra:
        raise _cannot_render(
            block.get("op"), f"unexpected argument {sorted(extra)[0]!r}"
        )


def _needs_parens(value: Any) -> bool:
    return _is_block(value) and value.get("op") in _INFIX_OPS


def _operand(value: Any) -> str:
    text = _expr(value)
    return f"({text})" if _needs_parens(value) else text


def _expr(value: Any) -> str:
    if not _is_block(value):
        if isinstance(value, bool):
            raise DSLError("cannot render a boolean value in an expression")
        if value is None:
            raise DSLError("cannot render None in an expression")
        if isinstance(value, str):
            return _quote(value)
        if _is_number(value):
            return _number_text(value)
        if isinstance(value, list):
            raise DSLError("cannot render a list value in an expression")
        raise DSLError(f"cannot render value {value!r}")

    block = value
    op = block.get("op")
    known_call = op in CALLABLE_SPECS and CALLABLE_SPECS[op].kind in {
        "reporter",
        "boolean",
    }
    if op not in _DIRECT_EXPR_OPS and not known_call:
        raise _cannot_render(op)
    args = _args(block)
    if op == "get_var":
        name = _arg(block, "name")
        if not isinstance(name, str):
            raise _cannot_render(op, "variable name must be a string")
        if _is_bare_name(name):
            return name
        return f"get_var({_quote(name)})"
    if op == "join":
        return _render_call("join", args)
    if op == "add":
        _check_args(block, ("a", "b"))
        left = _arg(block, "a")
        right = _arg(block, "b")
        return _render_add(left, right)
    if op in _ARITHMETIC_SYMBOLS:
        _check_args(block, ("a", "b"))
        left = _arg(block, "a")
        right = _arg(block, "b")
        return f"{_operand(left)} {_ARITHMETIC_SYMBOLS[op]} {_operand(right)}"
    if op in _COMPARISON_SYMBOLS:
        _check_args(block, ("a", "b"))
        left = _arg(block, "a")
        right = _arg(block, "b")
        return f"{_operand(left)} {_COMPARISON_SYMBOLS[op]} {_operand(right)}"
    if op == "not":
        _check_args(block, ("a",))
        return _render_not(block)
    if op == "and":
        _check_args(block, ("a", "b"))
        left = _arg(block, "a")
        right = _arg(block, "b")
        return f"{_operand(left)} and {_operand(right)}"
    if op == "or":
        _check_args(block, ("a", "b"))
        return _render_or(_arg(block, "a"), _arg(block, "b"))
    if op in CALLABLE_SPECS and CALLABLE_SPECS[op].kind in {
        "reporter",
        "boolean",
    }:
        return _render_call(op, args)
    raise _cannot_render(op)


def _render_add(left: Any, right: Any) -> str:
    # ``"literal" + x`` and ``join(...) + x`` would re-transpile to ``join``;
    # two computed values would be ambiguous.  All three cases need the
    # explicit catalog call.
    if isinstance(left, str) or isinstance(right, str):
        return _render_call_from_args("add", {"a": left, "b": right}, ("a", "b"))
    if _is_join_block(left) or _is_join_block(right):
        return _render_call_from_args("add", {"a": left, "b": right}, ("a", "b"))
    if not _is_number(left) and not _is_number(right):
        return _render_call_from_args("add", {"a": left, "b": right}, ("a", "b"))
    return f"{_operand(left)} + {_operand(right)}"


def _render_not(block: dict[str, Any]) -> str:
    value = _arg(block, "a")
    if _is_block(value) and value.get("op") == "equals":
        _check_args(value, ("a", "b"))
        equals_args = _args(value)
        if "a" in equals_args and "b" in equals_args:
            return (
                f"{_operand(equals_args['a'])} != "
                f"{_operand(equals_args['b'])}"
            )
    return f"not {_operand(value)}"


def _render_or(left: Any, right: Any) -> str:
    if (
        _is_block(left)
        and left.get("op") in {"less_than", "greater_than"}
        and _is_block(right)
        and right.get("op") == "equals"
    ):
        _check_args(left, ("a", "b"))
        _check_args(right, ("a", "b"))
        left_args = _args(left)
        right_args = _args(right)
        if (
            "a" in left_args
            and "b" in left_args
            and left_args.get("a") == right_args.get("a")
            and left_args.get("b") == right_args.get("b")
        ):
            symbol = "<=" if left.get("op") == "less_than" else ">="
            return f"{_operand(left_args['a'])} {symbol} {_operand(left_args['b'])}"
    return f"{_operand(left)} or {_operand(right)}"


def _render_call_from_args(
    op: str, args: dict[str, Any], names: tuple[str, ...]
) -> str:
    parts: list[str] = []
    for name in names:
        if name not in args or args[name] is None:
            raise _cannot_render(op, f"missing argument '{name}'")
        parts.append(_operand(args[name]))
    return f"{op}({', '.join(parts)})"


def _render_call(op: str, args: dict[str, Any]) -> str:
    spec = CALLABLE_SPECS.get(op)
    if spec is None:
        raise _cannot_render(op)
    if spec.kind not in {"reporter", "boolean", "command"}:
        raise _cannot_render(op)
    expected = [arg.name for arg in spec.args]
    extra = set(args) - set(expected)
    if extra:
        raise _cannot_render(op, f"unexpected argument {sorted(extra)[0]!r}")
    parts: list[str] = []
    for arg in spec.args:
        if arg.name not in args or args[arg.name] is None:
            raise _cannot_render(op, f"missing argument '{arg.name}'")
        parts.append(_render_arg(op, arg, args[arg.name]))
    return f"{op}({', '.join(parts)})"


def _render_arg(op: str, spec: Any, value: Any) -> str:
    if spec.type == "menu":
        if not isinstance(value, str):
            raise _cannot_render(op, f"menu argument '{spec.name}' must be a string")
        if (
            not (op in SPRITE_TARGET_OPS and spec.name == "target")
            and spec.menu
            and value not in spec.menu
        ):
            raise _cannot_render(
                op, f"menu value {value!r} is not in the catalog menu"
            )
        return _quote(value)
    if spec.type == "list_index":
        if isinstance(value, str):
            if value not in {"last", "all"}:
                raise _cannot_render(
                    op, f"list index value {value!r} is not 'last' or 'all'"
                )
            return _quote(value)
        if _is_number(value):
            return _number_text(value)
        raise _cannot_render(op, f"list index argument '{spec.name}' is invalid")
    if spec.type in _LITERAL_ARG_TYPES:
        if not isinstance(value, str):
            raise _cannot_render(op, f"argument '{spec.name}' must be a string")
        return _quote(value)
    return _expr(value)


# -- statements ----------------------------------------------------------


def _render_body(blocks: list[Any], level: int) -> list[str]:
    lines: list[str] = []
    for block in blocks:
        lines.extend(_render_block(block, level))
    if not lines:
        # A bare string is dropped by the transpiler, so this preserves an
        # empty block body while keeping the source valid Python.
        lines.append(_indent('""', level))
    return lines


def _render_block(block: Any, level: int) -> list[str]:
    if not isinstance(block, dict) or not isinstance(block.get("op"), str):
        raise DSLError("cannot render a non-block statement")
    op = block["op"]
    if op not in _CONTROL_BLOCK_OPS and op not in COMMAND_OPS:
        raise _cannot_render(op)
    body = _require_list(block.get("body"), f"{op} body")
    then = _require_list(block.get("then"), f"{op} then")
    else_ = _require_list(block.get("else"), f"{op} else")
    if op in {"forever", "repeat", "if", "repeat_until", "forever_if"}:
        if then or else_:
            raise _cannot_render(op, "unexpected then/else body")
    elif op == "if_else":
        if body:
            raise _cannot_render(op, "unexpected body field")
    elif body or then or else_:
        raise _cannot_render(op, "unexpected nested body")
    if op == "forever":
        _check_args(block, ())
        return [_indent("while True:", level), *_render_body(body, level + 1)]
    if op == "repeat":
        _check_args(block, ("count",))
        count = _arg(block, "count")
        return [
            _indent(f"for _ in range({_expr(count)}):", level),
            *_render_body(body, level + 1),
        ]
    if op == "if":
        _check_args(block, ("condition",))
        condition = _arg(block, "condition")
        _require_boolean_condition(condition)
        return [
            _indent(f"if {_expr(condition)}:", level),
            *_render_body(body, level + 1),
        ]
    if op == "if_else":
        _check_args(block, ("condition",))
        condition = _arg(block, "condition")
        _require_boolean_condition(condition)
        return [
            _indent(f"if {_expr(condition)}:", level),
            *_render_body(then, level + 1),
            _indent("else:", level),
            *_render_body(else_, level + 1),
        ]
    if op == "repeat_until":
        _check_args(block, ("condition",))
        return _render_repeat_until(block, body, level)
    if op == "forever_if":
        _check_args(block, ("condition",))
        condition = _arg(block, "condition")
        _require_boolean_condition(condition)
        return [
            _indent("while True:", level),
            _indent(f"if {_expr(condition)}:", level + 1),
            *_render_body(body, level + 2),
        ]
    if op == "set_var":
        _check_args(block, ("name", "value"))
        return _render_set_var(block, level)
    if op == "change_var":
        _check_args(block, ("name", "delta"))
        return _render_change_var(block, level)
    if op in COMMAND_OPS:
        return [_indent(_render_call(op, _args(block)), level)]
    raise _cannot_render(op)


def _require_boolean_condition(value: Any) -> None:
    spec = spec_for(value.get("op")) if _is_block(value) else None
    if spec is None or spec.kind != "boolean":
        raise DSLError("cannot render a non-boolean condition")


def _render_repeat_until(
    block: dict[str, Any], body: list[Any], level: int
) -> list[str]:
    condition = _arg(block, "condition")
    if _is_block(condition) and condition.get("op") == "not":
        inner = _arg(condition, "a")
        if _is_block(inner) and inner.get("op") == "not":
            raise _cannot_render("repeat_until", "nested not condition")
        return [
            _indent(f"while {_expr(inner)}:", level),
            *_render_body(body, level + 1),
        ]
    return [
        _indent(f"while not ({_expr(condition)}):", level),
        *_render_body(body, level + 1),
    ]


def _render_set_var(block: dict[str, Any], level: int) -> list[str]:
    name = _arg(block, "name")
    if not isinstance(name, str):
        raise _cannot_render("set_var", "variable name must be a string")
    value = _arg(block, "value")
    if _is_bare_name(name):
        return [_indent(f"{name} = {_expr(value)}", level)]
    return [_indent(f"set_var({_quote(name)}, {_expr(value)})", level)]


def _render_change_var(block: dict[str, Any], level: int) -> list[str]:
    name = _arg(block, "name")
    if not isinstance(name, str):
        raise _cannot_render("change_var", "variable name must be a string")
    delta = _arg(block, "delta")
    if _is_number(delta) and delta < 0:
        if _is_bare_name(name):
            return [_indent(f"{name} -= {_number_text(-delta)}", level)]
        return [
            _indent(f"change_var({_quote(name)}, {_number_text(delta)})", level)
        ]
    text = _expr(delta)
    if _is_bare_name(name):
        if _is_block(delta):
            return [_indent(f"{name} += ({text})", level)]
        return [_indent(f"{name} += {text}", level)]
    return [_indent(f"change_var({_quote(name)}, {text})", level)]


# -- scripts -------------------------------------------------------------


def _render_hat_value(op: str, arg: Any, value: Any) -> str:
    if arg.type == "menu":
        if not isinstance(value, str):
            raise _cannot_render(op, f"hat argument '{arg.name}' must be a string")
        if arg.menu and value not in arg.menu:
            raise _cannot_render(
                op, f"hat menu value {value!r} is not in the catalog menu"
            )
        return _quote(value)
    if arg.type == "string":
        if not isinstance(value, str):
            raise _cannot_render(op, f"hat argument '{arg.name}' must be a string")
        return _quote(value)
    if arg.type == "number":
        if not _is_number(value):
            raise _cannot_render(op, f"hat argument '{arg.name}' must be a number")
        return _number_text(value)
    raise _cannot_render(op, f"unsupported hat argument '{arg.name}'")


def render_script(
    hat: dict,
    body: list[dict],
    *,
    target: str,
    label: str = "",
    script_id: str | None = None,
) -> str:
    """Render one decorated script (hat + body) as dialect text."""
    if not isinstance(hat, dict) or not isinstance(hat.get("op"), str):
        raise DSLError("cannot render a script without a hat")
    if not isinstance(target, str):
        raise DSLError("cannot render a script without a target")
    if not isinstance(label, str):
        raise DSLError("cannot render a non-string script label")
    if script_id is not None and not isinstance(script_id, str):
        raise DSLError("cannot render a non-string script_id")
    hat_op = hat["op"]
    decorator = _HAT_DECORATORS.get(hat_op)
    if decorator is None:
        raise _cannot_render(hat_op)
    hat_args = _args(hat)
    expected = [arg.name for arg in arg_specs(hat_op)]
    extra = set(hat_args) - set(expected)
    if extra:
        raise _cannot_render(hat_op, f"unexpected argument {sorted(extra)[0]!r}")
    parts: list[str] = []
    for arg in arg_specs(hat_op):
        if arg.name not in hat_args or hat_args[arg.name] is None:
            raise _cannot_render(hat_op, f"missing argument '{arg.name}'")
        parts.append(_render_hat_value(hat_op, arg, hat_args[arg.name]))
    parts.append(f"target={_quote(target)}")
    parts.append(f"label={_quote(label)}")
    if script_id is not None:
        parts.append(f"script_id={_quote(script_id)}")
    lines = [f"@{decorator}({', '.join(parts)})"]
    lines.append(f"def {_def_name(label)}():")
    lines.extend(_render_body(_require_list(body, "script body"), 1))
    return "\n".join(lines)


# -- module changes ------------------------------------------------------


def _present(change: dict[str, Any], key: str) -> bool:
    return key in change and change[key] is not None


def _render_change(change: Any) -> str:
    change = _require_dict(change, "change")
    action = change.get("action")
    if not isinstance(action, str):
        raise DSLError("cannot render a change without an action")
    if action in {"add_script", "replace_script"}:
        hat = change.get("hat")
        if not isinstance(hat, dict):
            raise DSLError(f"cannot render action {action!r} without a hat")
        target = change.get("target", "")
        label = change.get("label", "")
        script_id = change.get("script_id")
        if action == "add_script":
            if script_id:
                raise DSLError(
                    "cannot render add_script with a script_id"
                )
            script_id = None
        else:
            if not isinstance(script_id, str) or not script_id:
                raise DSLError(
                    "cannot render replace_script without a script_id"
                )
        return render_script(
            hat,
            _require_list(change.get("body"), "script body"),
            target=target,
            label=label,
            script_id=script_id,
        )
    if action == "delete_script":
        return f"delete_script({_quote(_require_change_str(change, 'script_id'))})"
    if action == "create_variable":
        name = _require_change_str(change, "name")
        if name in FUNCTION_NAMES:
            raise DSLError(
                f"cannot render variable name {name!r}: "
                "it collides with a dialect function"
            )
        if "initial" in change and change["initial"] is None:
            raise DSLError("cannot render a None variable initial value")
        parts = [_quote(name)]
        if _present(change, "scope"):
            parts.append(f"scope={_module_value(change['scope'])}")
        if _present(change, "target"):
            parts.append(f"target={_module_value(change['target'])}")
        if _present(change, "initial"):
            parts.append(f"initial={_module_value(change['initial'])}")
        return f"create_variable({', '.join(parts)})"
    if action == "create_list":
        parts = [_quote(_require_change_str(change, "name"))]
        if _present(change, "scope"):
            parts.append(f"scope={_module_value(change['scope'])}")
        if _present(change, "target"):
            parts.append(f"target={_module_value(change['target'])}")
        if _present(change, "items"):
            parts.append(f"items={_module_list(change['items'])}")
        return f"create_list({', '.join(parts)})"
    if action == "create_sprite":
        parts = [_quote(_require_change_str(change, "name"))]
        if _present(change, "costumes"):
            parts.append(f"costumes={_render_costumes(change['costumes'])}")
        if _present(change, "preset"):
            parts.append(f"preset={_module_value(change['preset'])}")
        parts.extend(_render_sprite_props(change))
        return f"create_sprite({', '.join(parts)})"
    if action == "set_sprite":
        parts = [_quote(_require_change_str(change, "target"))]
        parts.extend(_render_sprite_props(change))
        return f"set_sprite({', '.join(parts)})"
    if action == "duplicate_sprite":
        target = _quote(_require_change_str(change, "target"))
        name = _quote(_require_change_str(change, "name"))
        return f"duplicate_sprite({target}, {name})"
    if action == "delete_sprite":
        return f"delete_sprite({_quote(_require_change_str(change, 'target'))})"
    if action == "add_costume":
        target = _quote(_require_change_str(change, "target"))
        library = _quote(_require_change_str(change, "library"))
        parts = [target, library]
        if _present(change, "name"):
            parts.append(f"name={_module_value(change['name'])}")
        if _present(change, "select"):
            parts.append(f"select={_module_value(change['select'])}")
        return f"add_costume({', '.join(parts)})"
    if action == "set_backdrop":
        parts = [_quote(_require_change_str(change, "library"))]
        if _present(change, "name"):
            parts.append(f"name={_module_value(change['name'])}")
        if _present(change, "select"):
            parts.append(f"select={_module_value(change['select'])}")
        return f"set_backdrop({', '.join(parts)})"
    raise DSLError(f"cannot render change action {action!r}")


def _require_change_str(change: dict[str, Any], key: str) -> str:
    value = change.get(key)
    if not isinstance(value, str):
        raise DSLError(f"cannot render change without a string {key!r}")
    return value


def _render_sprite_props(change: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    for key in ("x", "y", "direction", "size", "visible", "rotation_style"):
        if not _present(change, key):
            continue
        if key == "rotation_style" and change[key] == "":
            continue
        parts.append(f"{key}={_module_value(change[key])}")
    return parts


def _render_costumes(value: Any) -> str:
    if not isinstance(value, list):
        raise DSLError("cannot render non-list costumes")
    libraries: list[str] = []
    for entry in value:
        if isinstance(entry, str):
            libraries.append(entry)
            continue
        if isinstance(entry, dict) and isinstance(entry.get("library"), str):
            # A custom costume ``name`` is intentionally dropped: the library
            # stem is what the dialect re-parses.
            libraries.append(entry["library"])
            continue
        raise DSLError(f"cannot render costume entry {entry!r}")
    return _module_list(libraries)


def render_changeset(payload: dict) -> str:
    """Render a whole change-set payload as a dialect module."""
    if not isinstance(payload, dict):
        raise DSLError("change set must be an object")
    summary = payload.get("summary")
    notes = payload.get("notes")
    for value in (summary, notes):
        if value is not None and not isinstance(value, str):
            raise DSLError("cannot render a non-string summary or notes")
    changes = payload.get("changes", [])
    if not isinstance(changes, list):
        raise DSLError("cannot render a change set whose changes is not a list")
    sections: list[str] = []
    header: list[str] = []
    if summary:
        header.append(f"summary({_quote(summary)})")
    if notes:
        header.append(f"notes({_quote(notes)})")
    if header:
        sections.append("\n".join(header))
    if changes:
        sections.append(
            "\n\n".join(_render_change(change) for change in changes)
        )
    return "\n\n".join(sections)


# -- sprite detail -------------------------------------------------------


def _contains_unknown(value: Any) -> bool:
    if not _is_block(value):
        return False
    op = value.get("op")
    if not isinstance(op, str) or spec_for(op) is None:
        return True
    for key in ("body", "then", "else"):
        children = value.get(key)
        if isinstance(children, list) and any(
            _contains_unknown(child) for child in children
        ):
            return True
    return False


def render_sprite_detail(
    sprite: SpriteContext, max_chars: int = MAX_DETAIL_CHARS
) -> str:
    """Render the load_sprite detail block with dialect script bodies."""
    if sprite.is_stage:
        kind = "Stage"
    elif sprite.ai_owned:
        kind = "AI-created sprite"
    else:
        kind = "user sprite"
    header = (
        f'# Sprite detail: "{_ascii(sprite.name)}" ({kind}; '
        f"costumes={', '.join(_ascii(item) for item in sprite.costumes) or '-'}; "
        f"variables={', '.join(_ascii(item) for item in sprite.variables) or '-'}; "
        f"lists={', '.join(_ascii(item) for item in sprite.lists) or '-'})"
    )
    lines = [header]
    for script in sprite.scripts:
        line = (
            f'- {_ascii(script.script_id)} "{_ascii(script.label)}" '
            f"[{_ascii(script.hat)}] {script.block_count} blocks "
            f"({_script_owner(script)})"
        )
        if script.tuples:
            body = decompile_script(script.tuples)
            if body is not None:
                rendered: str | None = None
                hat = body.get("hat")
                blocks = _require_list(body.get("body"), "detail body")
                if not _contains_unknown(hat) and not any(
                    _contains_unknown(block) for block in blocks
                ):
                    try:
                        rendered = render_script(
                            hat,
                            blocks,
                            target=sprite.name,
                            label=script.label,
                        )
                    except DSLError:
                        rendered = None
                if rendered is not None:
                    line += "\n" + rendered
                else:
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
