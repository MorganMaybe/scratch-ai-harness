"""Diagnostics for the Scratch-Python dialect.

The transpiler reports every problem as a :class:`DSLError` carrying the
Python line (and column, when known) plus an optional repair hint.  The
formatted text is what the repair prompt quotes, so it stays short, line
precise, and ASCII.
"""

from __future__ import annotations

#: Stop collecting after this many diagnostics; more than this is noise for a
#: repair pass, and the model needs a bounded prompt.
MAX_DIAGNOSTICS = 10


class DSLError(ValueError):
    """One dialect diagnostic."""

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        col: int | None = None,
        hint: str | None = None,
    ):
        self.message = message
        self.line = line
        self.col = col
        self.hint = hint
        super().__init__(self.format())

    def format(self) -> str:
        prefix = f"line {self.line}: " if self.line is not None else ""
        text = prefix + self.message
        if self.hint:
            text += "\n  " + self.hint
        return text


class DSLErrors(ValueError):
    """A batch of diagnostics collected from one reply."""

    def __init__(self, errors: list[DSLError]):
        self.errors = list(errors)[:MAX_DIAGNOSTICS]
        super().__init__(self.__str__())

    def __str__(self) -> str:
        return "\n\n".join(error.format() for error in self.errors)
