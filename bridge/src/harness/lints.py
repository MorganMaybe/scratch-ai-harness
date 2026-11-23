"""Deterministic advisory lints for a validated change set.

Validation checks exact shapes: ops, arguments, targets and media.  It cannot
see runtime smell.  These lints are the cheap, offline second opinion that
encodes the runtime semantics in ``SCRATCH_AI_CONTEXT.md`` section 8:

* an unconditional move in a frame-rate loop needs a wait;
* an unconditional ``next_costume`` in such a loop strobes the costume;
* a freshly created variable read but never written will always hold its
  initial value (usually 0).

The rules are intentionally conservative: a false positive is worse than a
missed hint, and the system prompt's canonical examples (the waitless spinning
bat, the finite square, the pen drawing) are the exclusion baseline.  Every
message is one line of ASCII so the image's Smalltalk literal wire format can
carry it as chat text.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator

from .block_ir import Block, Change, ChangeSet
from .context import ProjectContext, ScriptSummary
from .script_detail import decompile_script

log = logging.getLogger("harness.lints")

#: Loop shapes that run once per frame unless a wait yields.
_LOOP_OPS: frozenset[str] = frozenset({"forever", "repeat_until"})

#: Unconditional motion that advances the sprite every frame.
_DRIFT_OPS: frozenset[str] = frozenset({"move", "change_x", "change_y"})

#: Costume cycling that strobes when it runs every frame.
_FLICKER_OPS: frozenset[str] = frozenset({"next_costume"})

#: Script actions whose ``body`` is a block tree worth walking.
_SCRIPT_ACTIONS: frozenset[str] = frozenset({"add_script", "replace_script"})

_VARIABLE_WRITES: frozenset[str] = frozenset({"set_var", "change_var"})


def lint_changeset(
    changeset: ChangeSet,
    context: ProjectContext,
    registry: dict[str, ScriptSummary] | None = None,
) -> list[str]:
    """Return one-line advisory warnings for ``changeset`` (possibly empty).

    ``context`` supplies the AI-owned script tuples that already exist in the
    project, so the variable rule can see writes made by earlier turns.
    ``registry`` only supplies labels/targets for ``replace_script`` entries.
    """
    registry = registry or {}
    scripts = [
        change for change in changeset.changes if change.action in _SCRIPT_ACTIONS
    ]
    reads, writes = _change_set_variable_usage(scripts)
    writes |= _context_variable_writes(context)

    warnings: list[str] = []
    for change in scripts:
        label, target = _script_identity(change, registry, context)
        for block in _iter_blocks(change.body):
            if block.op not in _LOOP_OPS:
                continue
            direct = {child.op for child in block.body}
            if not direct or _subtree_has_wait(block):
                continue
            prefix = f"script '{_ascii(label)}' ({_ascii(target)}): "
            if direct & _DRIFT_OPS:
                warnings.append(
                    _ascii(
                        prefix
                        + f"{block.op} loop moves the sprite every frame with no "
                        "wait; add a wait block inside the loop (0.05-0.5 s)"
                    )
                )
            if direct & _FLICKER_OPS:
                warnings.append(
                    _ascii(
                        prefix
                        + f"{block.op} loop switches costume every frame with no "
                        "wait; add a wait block inside the loop (0.05-0.5 s)"
                    )
                )

    seen: set[str] = set()
    for change in changeset.changes:
        if change.action != "create_variable":
            continue
        if not change.name or change.name in seen or not _is_zero(change.initial):
            continue
        if change.name not in reads or change.name in writes:
            continue
        seen.add(change.name)
        label, target = reads[change.name]
        warnings.append(
            _ascii(
                f"script '{label}' ({target}): variable '{change.name}' is read "
                "but never set; it will always be 0"
            )
        )
    return warnings


def _script_identity(
    change: Change,
    registry: dict[str, ScriptSummary],
    context: ProjectContext,
) -> tuple[str, str]:
    existing = registry.get(change.script_id) if change.script_id else None
    label = change.label or (existing.label if existing is not None else "")
    target = change.target or (existing.target if existing is not None else "")
    return label or change.script_id or "script", target or context.target


def _is_zero(value: Any) -> bool:
    """True for the literal 0; booleans are not numeric zeros here."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == 0
    )


def _change_set_variable_usage(
    scripts: list[Change],
) -> tuple[dict[str, tuple[str, str]], set[str]]:
    """Collect ``get_var`` reads (name -> label/target) and writes in a set."""
    reads: dict[str, tuple[str, str]] = {}
    writes: set[str] = set()
    for change in scripts:
        label = change.label or change.script_id or "script"
        target = change.target or "target"
        for block in _iter_blocks(change.body):
            name = block.args.get("name")
            if not isinstance(name, str) or not name:
                continue
            if block.op == "get_var" and name not in reads:
                reads[name] = (_ascii(label), _ascii(target))
            elif block.op in _VARIABLE_WRITES:
                writes.add(name)
    return reads, writes


def _context_variable_writes(context: ProjectContext) -> set[str]:
    """Variable names written by the AI-owned scripts already in the project."""
    writes: set[str] = set()
    if context is None:
        return writes
    for sprite in context.sprites.values():
        for script in sprite.scripts:
            if not script.owned or not script.tuples:
                continue
            try:
                decompiled = decompile_script(script.tuples)
            except Exception:  # pragma: no cover - defensive
                log.warning(
                    "event=lints.decompile_failed script=%s", script.script_id
                )
                continue
            if not decompiled:
                continue
            for block in _walk_dicts(decompiled.get("body") or []):
                if block.get("op") not in _VARIABLE_WRITES:
                    continue
                name = (block.get("args") or {}).get("name")
                if isinstance(name, str) and name:
                    writes.add(name)
    return writes


def _iter_blocks(blocks: list[Block]) -> Iterator[Block]:
    """Yield every block in a tree, descending bodies and nested reporters."""
    for block in blocks:
        yield block
        yield from _iter_blocks(block.body)
        yield from _iter_blocks(block.then)
        yield from _iter_blocks(block.else_)
        for value in block.args.values():
            yield from _iter_arg_blocks(value)


def _iter_arg_blocks(value: Any) -> Iterator[Block]:
    if isinstance(value, Block):
        yield from _iter_blocks([value])
    elif isinstance(value, list):
        for item in value:
            yield from _iter_arg_blocks(item)


def _subtree_has_wait(block: Block) -> bool:
    return any(item.op == "wait" for item in _iter_blocks([block]))


def _walk_dicts(blocks: list[Any]) -> Iterator[dict[str, Any]]:
    """Yield decompiled block dicts from ``body``/``then``/``else``."""
    for block in blocks:
        if not isinstance(block, dict):
            continue
        yield block
        for key in ("body", "then", "else"):
            children = block.get(key)
            if isinstance(children, list):
                yield from _walk_dicts(children)
        args = block.get("args")
        if isinstance(args, dict):
            for value in args.values():
                yield from _walk_dict_values(value)


def _walk_dict_values(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield from _walk_dicts([value])
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dict_values(item)


def _ascii(text: str) -> str:
    """Collapse to one ASCII line for the chat wire (never raises)."""
    text = " ".join(str(text).replace("\r", " ").replace("\n", " ").split())
    return text.encode("ascii", "backslashreplace").decode("ascii")
