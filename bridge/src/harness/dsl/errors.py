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
        source: str | None = None,
    ):
        self.message = message
        self.line = line
        self.col = col
        self.hint = hint
        #: The module text the line number refers to (fence already stripped).
        #: Optional: ``format()`` stays byte-identical unless a caller asks for
        #: the quoted line, so existing lint/test output is unchanged.
        self.source = source
        super().__init__(self.format())

    def format(self, *, include_source: bool = False) -> str:
        prefix = f"line {self.line}: " if self.line is not None else ""
        snippet = ""
        if include_source and self.source and self.line is not None:
            lines = self.source.splitlines()
            if 1 <= self.line <= len(lines):
                snippet = lines[self.line - 1].strip()
        if snippet:
            text = f"{prefix}{snippet}\n  {self.message}"
        else:
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
