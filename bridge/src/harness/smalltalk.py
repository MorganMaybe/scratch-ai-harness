from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Sym:
    """A Smalltalk symbol (selector or class name)."""

    name: str


def to_literal(value: Any) -> str:
    if isinstance(value, Sym):
        return "#" + value.name
    if isinstance(value, str):
        if "\n" in value or "\r" in value:
            raise ValueError("newlines in Smalltalk string literals are not supported")
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "nil"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            raise ValueError("non-finite numbers are not supported")
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "#(" + " ".join(to_literal(v) for v in value) + ")"
    raise TypeError(f"cannot emit {type(value).__name__} as a Smalltalk literal")
