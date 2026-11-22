"""Dialect vocabulary generated from the block catalog.

The function names in Scratch-Python *are* the catalog op names, and their
argument names and order come from each op's :class:`~harness.catalog.ArgSpec`
list.  Nothing here is a second, hand-maintained op table: changing
``harness.catalog.SPECS`` changes the transpiler and the generated prompt
reference together.

Module calls (``create_sprite``, ``set_backdrop`` ...) are the one exception:
they are change-set actions, not blocks, so their signatures are declared
here and mirror the JSON change contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..catalog import ROTATION_STYLES, SPECS, ArgSpec, BlockSpec, spec_for

#: Control bodies are Python syntax, not calls.  These ops are never callable.
CONTROL_OPS: frozenset[str] = frozenset(
    spec.op for spec in SPECS if spec.kind in {"cblock", "ifelse"}
)

#: Every catalog op with a value (a command block or an expression block).
CALLABLE_SPECS: dict[str, BlockSpec] = {
    spec.op: spec for spec in SPECS if spec.kind in {"command", "reporter", "boolean"}
}

COMMAND_OPS: frozenset[str] = frozenset(
    op for op, spec in CALLABLE_SPECS.items() if spec.kind == "command"
)
REPORTER_OPS: frozenset[str] = frozenset(
    op for op, spec in CALLABLE_SPECS.items() if spec.kind == "reporter"
)
BOOLEAN_OPS: frozenset[str] = frozenset(
    op for op, spec in CALLABLE_SPECS.items() if spec.kind == "boolean"
)
EXPRESSION_OPS: frozenset[str] = REPORTER_OPS | BOOLEAN_OPS


@dataclass(frozen=True)
class ModuleParam:
    """One parameter of a module-level change call."""

    name: str
    type: str = "any"  # string | number | bool | any | strings | literals | menu
    required: bool = False
    default: Any = None
    menu: tuple[str, ...] = ()
    #: Display-only example for the API reference; never a parse default.
    example: Any = None


@dataclass(frozen=True)
class ModuleCallSpec:
    """A module-level change call and the change it emits."""

    name: str
    params: tuple[ModuleParam, ...]
    action: str = ""  # empty for summary/notes metadata


def _param(
    name: str,
    type: str = "any",
    *,
    required: bool = False,
    default: Any = None,
    menu: tuple[str, ...] = (),
    example: Any = None,
) -> ModuleParam:
    return ModuleParam(name, type, required, default, menu, example)


MODULE_CALL_SPECS: dict[str, ModuleCallSpec] = {
    "summary": ModuleCallSpec(
        "summary", (_param("text", "string", required=True),)
    ),
    "notes": ModuleCallSpec("notes", (_param("text", "string", required=True),)),
    "set_backdrop": ModuleCallSpec(
        "set_backdrop",
        (
            _param("library", "string", required=True),
            _param("name", "string"),
            _param("select", "bool", default=True),
        ),
        action="set_backdrop",
    ),
    "add_costume": ModuleCallSpec(
        "add_costume",
        (
            _param("target", "string", required=True),
            _param("library", "string", required=True),
            _param("name", "string"),
            _param("select", "bool", default=False),
        ),
        action="add_costume",
    ),
    "create_variable": ModuleCallSpec(
        "create_variable",
        (
            _param("name", "string", required=True),
            _param(
                "scope",
                "scope",
                default="global",
                menu=("global", "sprite"),
            ),
            _param("target", "string"),
            _param("initial", "any", default=0),
        ),
        action="create_variable",
    ),
    "create_list": ModuleCallSpec(
        "create_list",
        (
            _param("name", "string", required=True),
            _param(
                "scope",
                "scope",
                default="global",
                menu=("global", "sprite"),
            ),
            _param("target", "string"),
            _param("items", "literals"),
        ),
        action="create_list",
    ),
    "create_sprite": ModuleCallSpec(
        "create_sprite",
        (
            _param("name", "string", required=True),
            _param("costumes", "strings", example=["Animals/crab1-a.png"]),
            _param("preset", "string"),
            _param("x", "number", default=0),
            _param("y", "number", default=0),
            _param("direction", "number", default=90),
            _param("size", "number", default=100),
            _param("visible", "bool", default=True),
            _param(
                "rotation_style",
                "rotation",
                default="all around",
                menu=ROTATION_STYLES,
            ),
        ),
        action="create_sprite",
    ),
    "set_sprite": ModuleCallSpec(
        "set_sprite",
        (
            _param("target", "string", required=True),
            _param("x", "number"),
            _param("y", "number"),
            _param("direction", "number"),
            _param("size", "number"),
            _param("visible", "bool"),
            _param(
                "rotation_style",
                "rotation",
                menu=ROTATION_STYLES,
            ),
        ),
        action="set_sprite",
    ),
    "duplicate_sprite": ModuleCallSpec(
        "duplicate_sprite",
        (
            _param("target", "string", required=True),
            _param("name", "string", required=True),
        ),
        action="duplicate_sprite",
    ),
    "delete_sprite": ModuleCallSpec(
        "delete_sprite",
        (_param("target", "string", required=True),),
        action="delete_sprite",
    ),
    "delete_script": ModuleCallSpec(
        "delete_script",
        (_param("script_id", "string", required=True),),
        action="delete_script",
    ),
}

MODULE_CALL_NAMES: frozenset[str] = frozenset(MODULE_CALL_SPECS)

#: Event decorator name -> catalog hat op.  The value is looked up in SPECS so
#: argument names come from the catalog too.
HAT_SPECS: dict[str, str] = {
    "on_flag": "when_flag_clicked",
    "on_key": "when_key_pressed",
    "on_click": "when_clicked",
    "on_stage_click": "when_stage_clicked",
    "on_clone_start": "when_clone_start",
    "on_receive": "when_receive",
    "on_backdrop": "when_backdrop_switches",
    "on_loudness": "when_loudness_greater",
    "on_timer": "when_timer_greater",
}

#: Every name the transpiler treats as reserved vocabulary (and therefore
#: unavailable as a bare variable name).
FUNCTION_NAMES: frozenset[str] = (
    frozenset(CALLABLE_SPECS)
    | CONTROL_OPS
    | MODULE_CALL_NAMES
    | frozenset(HAT_SPECS)
)

#: Keyword aliases accepted for module calls.  ``rotation`` appears in the
#: design document's worked example; ``rotation_style`` is the canonical name.
MODULE_KEYWORD_ALIASES: dict[str, str] = {"rotation": "rotation_style"}


def arg_specs(op: str) -> tuple[ArgSpec, ...]:
    """Argument specs for a catalog op (empty when the op is unknown)."""
    spec = spec_for(op)
    return spec.args if spec is not None else ()


def _kind_marker(spec: BlockSpec) -> str:
    if spec.kind == "command":
        return "cmd "
    if spec.kind == "boolean":
        return "bool"
    return "rep "


def _signature(spec: BlockSpec) -> str:
    return f"{spec.op}({', '.join(arg.name for arg in spec.args)})"


def _default_text(value: Any) -> str:
    if isinstance(value, str):
        return '"' + value + '"'
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(f'"{item}"' for item in value) + "]"
    return repr(value)


def _module_signature(spec: ModuleCallSpec) -> str:
    parts: list[str] = []
    for param in spec.params:
        if param.required:
            parts.append(param.name)
        elif param.example is not None:
            parts.append(f"{param.name}={_default_text(param.example)}")
        elif param.default is not None:
            parts.append(f"{param.name}={_default_text(param.default)}")
        else:
            parts.append(f"{param.name}=None")
    return f"{spec.name}({', '.join(parts)})"


def _decorator_signature(name: str) -> str:
    op = HAT_SPECS[name]
    parts = [arg.name for arg in arg_specs(op)]
    parts.extend(('target="SpriteName"', 'label="name"', 'script_id="ai-1"'))
    return f"@{name}({', '.join(parts)})"


#: Render order requested by the design: events first, clone work last.
_GROUP_ORDER: tuple[str, ...] = (
    "events",
    "motion",
    "looks",
    "pen",
    "sound",
    "sensing",
    "operators",
    "variables",
    "lists",
    "control",
    "clone",
)

_CLONE_OPS: frozenset[str] = frozenset({"create_clone", "delete_clone"})


def _group_specs(group: str) -> list[BlockSpec]:
    if group == "clone":
        return [CALLABLE_SPECS[op] for op in ("create_clone", "delete_clone")]
    category = "list" if group == "lists" else group
    specs = [
        spec
        for spec in CALLABLE_SPECS.values()
        if spec.category == category and spec.op not in _CLONE_OPS
    ]
    return specs


def api_reference() -> str:
    """The compact prompt section generated from ``SPECS``."""
    lines: list[str] = [
        "Scratch-Python API reference (generated from the block catalog).",
        "[cmd] = command statement, [rep] = reporter value, [bool] = boolean value.",
        "A bare name reads a variable (score); assignments set it (score = 0).",
        "",
        "module changes (top level, literal arguments only, in source order):",
    ]
    for spec in MODULE_CALL_SPECS.values():
        lines.append("  " + _module_signature(spec))
    lines.extend(("", "event decorators (exactly one per def; target is required):"))
    for name in HAT_SPECS:
        lines.append("  " + _decorator_signature(name))
    lines.extend(
        (
            "",
            "control flow is Python, never a function call:",
            "  for _ in range(n): ...        -> repeat n times",
            "  while True: ...               -> forever",
            "  while not cond: ...           -> repeat until cond",
            "  while cond: ...               -> repeat until not cond",
            "  if cond: ... / elif / else    -> if / if else",
            "Do not call repeat(), forever(), if(), if_else(), repeat_until()"
            " or forever_if().",
        )
    )
    for group in _GROUP_ORDER:
        lines.append("")
        lines.append(f"{group}:")
        if group == "events":
            lines.append("  event hats are the decorators above")
            continue
        for spec in _group_specs(group):
            line = f"  [{_kind_marker(spec)}] {_signature(spec)}"
            if spec.op == "random":
                line += "  # positional only: random(-10, 10)"
            lines.append(line)
    return "\n".join(lines)
