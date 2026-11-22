"""Scratch-Python: a checked Python subset that transpiles to block IR."""

from __future__ import annotations

from .errors import DSLError, DSLErrors
from .parse import lint, transpile
from .vocab import api_reference

__all__ = [
    "DSLError",
    "DSLErrors",
    "api_reference",
    "lint",
    "transpile",
]
