"""Scratch-Python: a checked Python subset that transpiles to block IR."""

from __future__ import annotations

from .errors import DSLError, DSLErrors
from .envelope import ENVELOPE_PREFIX, NormalizedReply, normalize, prose_diagnostic
from .parse import lint, transpile
from .render import render_changeset, render_script, render_sprite_detail
from .vocab import api_reference

__all__ = [
    "DSLError",
    "DSLErrors",
    "ENVELOPE_PREFIX",
    "NormalizedReply",
    "api_reference",
    "lint",
    "normalize",
    "prose_diagnostic",
    "render_changeset",
    "render_script",
    "render_sprite_detail",
    "transpile",
]
