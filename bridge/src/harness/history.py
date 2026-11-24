"""Bounded, process-local conversation memory for the bridge.

Every bridge request used to be stateless: the image sends only this turn's
prompt plus the current project snapshot, so a referential request ("make it
*smaller*", "start *lower*") had nothing to resolve against.  This module keeps
a small ring of **acked** turns and renders them as a prompt section.

The record is factual and bridge-built: the user's words, the model's own
summary and notes, and the ``chat_summary()`` change lines (never the raw change
set).  Failed turns never reach ``#applied`` and therefore never enter history;
the section is about applied reality.  The project context stays authoritative
(undo and manual edits happen image-side), which the rendered header states.

The store is deliberately stdlib-only so it can be imported by prompts, the
server and the ladder runner without pulling in the agent or the provider
stack.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

#: Caps applied when a record is stored, so the store itself stays bounded.
REQUEST_MAX_CHARS = 400
SUMMARY_MAX_CHARS = 240
NOTES_MAX_CHARS = 200
OUTLINE_MAX_LINES = 3
OUTLINE_LINE_MAX_CHARS = 160
MAX_RECORDS = 24

#: Rendering knobs.  Four verbatim turns is the proposed window; one-line
#: compression covers up to eight older turns.
VERBATIM_TURNS = 4
MIN_VERBATIM_TURNS = 2
ONE_LINER_LIMIT = 8
MAX_SECTION_CHARS = 2400
ONE_LINER_REQUEST_CHARS = 90
ONE_LINER_SUMMARY_CHARS = 120

#: The caveat is deliberately part of every section: history is memory, not
#: state.  Undo and manual edits are invisible here.
HEADER = (
    "Conversation so far (older turns compressed; the project context below is\n"
    "authoritative - undo and manual edits are not reflected here):"
)
RECENT_HEADER = "Most recent turns:"


def _clip(value: Any, limit: int) -> str:
    """One-line text clipped to ``limit`` characters, ellipsis included."""
    text = " ".join(str(value or "").split())
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3].rstrip() + "..."


@dataclass(frozen=True)
class TurnRecord:
    """One applied turn, capped and single-lined at record time."""

    request: str
    summary: str
    notes: str
    outline: tuple[str, ...]
    at: str
    #: Compact, factual change counts (``"2 sprites, 4 scripts"``).
    counts: str = ""


@dataclass(frozen=True)
class HistoryStats:
    """What the rendered section actually contains (for the audit meta)."""

    total: int = 0
    turns: int = 0
    dropped: int = 0
    chars: int = 0
    verbatim: int = 0


def _change_lines(compiled: Any) -> list[str]:
    """The factual change lines, without the summary and notes."""
    lines_fn = getattr(compiled, "change_lines", None)
    if callable(lines_fn):
        try:
            return [str(line) for line in lines_fn()]
        except Exception:  # pragma: no cover - a broken compiled object
            return []
    try:
        lines = str(compiled.chat_summary()).splitlines()[1:]
    except Exception:  # pragma: no cover - defensive
        return []
    notes = str(getattr(compiled, "notes", "") or "").strip()
    if notes and lines and lines[-1].strip() == notes:
        lines = lines[:-1]
    return lines


def _counts(lines: Iterable[str]) -> str:
    """``"2 sprites, 4 scripts"`` from chat-summary change lines."""
    sprites = 0
    scripts = 0
    for line in lines:
        if line.startswith(
            ("Created sprite", "Deleted sprite", "Duplicated sprite")
        ):
            sprites += 1
        elif line.startswith(("Added script", "Updated script", "Deleted script")):
            scripts += 1
    parts: list[str] = []
    if sprites:
        parts.append(f"{sprites} sprite" + ("" if sprites == 1 else "s"))
    if scripts:
        parts.append(f"{scripts} script" + ("" if scripts == 1 else "s"))
    return ", ".join(parts)


class ConversationHistory:
    """Bounded, process-local conversation store.

    Thread-safe on its own (the bridge also calls it under its state lock), so
    concurrent acknowledgements and prompt builds cannot interleave badly.
    """

    def __init__(self, max_records: int = MAX_RECORDS):
        if max_records < 1:
            raise ValueError("max_records must be at least 1")
        self.max_records = int(max_records)
        #: Newest last.  Public for tests and diagnostics; use ``snapshot`` for
        #: a stable copy to render from.
        self.recent: list[TurnRecord] = []
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self.recent)

    def snapshot(self) -> list[TurnRecord]:
        """A stable copy of the records, oldest first."""
        with self._lock:
            return list(self.recent)

    def clear(self) -> None:
        with self._lock:
            self.recent.clear()

    def record(
        self,
        request: Any,
        summary: Any,
        notes: Any = "",
        outline: Iterable[Any] | str = (),
        counts: Any = "",
    ) -> TurnRecord:
        """Append one applied turn, pruning the oldest record at the cap."""
        if isinstance(outline, str):
            outline = (outline,)
        lines = tuple(
            _clip(line, OUTLINE_LINE_MAX_CHARS)
            for line in outline
            if str(line).strip()
        )[:OUTLINE_MAX_LINES]
        record = TurnRecord(
            request=_clip(request, REQUEST_MAX_CHARS),
            summary=_clip(summary, SUMMARY_MAX_CHARS),
            notes=_clip(notes, NOTES_MAX_CHARS),
            outline=lines,
            at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            counts=_clip(counts, 80),
        )
        with self._lock:
            self.recent.append(record)
            overflow = len(self.recent) - self.max_records
            if overflow > 0:
                del self.recent[:overflow]
        return record

    def record_result(self, request: Any, result: Any) -> TurnRecord | None:
        """Record a successful ``AgentResult`` the way the server does.

        Duck-typed on purpose: this module stays free of agent imports.  The
        outline comes from the compiled change lines, never the raw change set.
        """
        compiled = getattr(result, "compiled", None)
        if compiled is None:
            return None
        lines = _change_lines(compiled)
        summary = getattr(compiled, "summary", "") or getattr(result, "summary", "")
        notes = getattr(compiled, "notes", "")
        return self.record(
            request,
            summary,
            notes,
            lines,
            _counts(lines),
        )


def render_one_liner(record: TurnRecord) -> str:
    """One compressed older turn, oldest-first in the rendered block."""
    request = _clip(record.request, ONE_LINER_REQUEST_CHARS)
    summary = _clip(record.summary, ONE_LINER_SUMMARY_CHARS)
    line = f'  "{request}"'
    if summary:
        line += f" -> {summary}"
    if record.counts:
        line += f" ({record.counts})"
    return line


def render_verbatim(record: TurnRecord) -> str:
    """One near-verbatim turn.  Every field was already capped at record time."""
    lines = [f"You: {record.request}", f"Assistant: {record.summary}"]
    for line in record.outline:
        lines.append(f"  - {line}")
    if record.notes:
        lines.append(f"  notes: {record.notes}")
    return "\n".join(lines)


def _assemble(
    records: list[TurnRecord], verbatim_count: int, one_liner_count: int
) -> tuple[str, int]:
    if verbatim_count > 0:
        recent = records[-verbatim_count:]
        older = records[:-verbatim_count]
    else:
        recent = []
        older = records
    shown = older[-one_liner_count:] if one_liner_count > 0 else []
    lines = [HEADER]
    lines.extend(render_one_liner(record) for record in shown)
    if recent:
        lines.append(RECENT_HEADER)
        lines.extend(render_verbatim(record) for record in recent)
    return "\n".join(lines), len(shown) + len(recent)


def render_history(
    records: Iterable[TurnRecord],
    *,
    verbatim_turns: int = VERBATIM_TURNS,
    one_liner_limit: int = ONE_LINER_LIMIT,
    max_chars: int = MAX_SECTION_CHARS,
) -> tuple[str, HistoryStats]:
    """Render the section, trimming in the documented stage order.

    * last ``verbatim_turns`` turns near-verbatim, older ones as one-liners;
    * overflow drops one-liners oldest-first;
    * if that is still not enough, the verbatim window shrinks (the freed turn
      becomes a one-liner when a slot is available).

    Returns the text and a :class:`HistoryStats` describing what fit.
    """
    records = list(records)[-MAX_RECORDS:]
    if not records:
        return "", HistoryStats()
    total = len(records)
    verbatim = max(0, min(int(verbatim_turns), total))
    shown = max(0, min(int(one_liner_limit), total - verbatim))
    while True:
        text, included = _assemble(records, verbatim, shown)
        if len(text) <= max_chars or (shown == 0 and verbatim <= 1):
            return text, HistoryStats(
                total=total,
                turns=included,
                dropped=total - included,
                chars=len(text),
                verbatim=verbatim,
            )
        if shown > 0:
            shown -= 1
        else:
            verbatim -= 1
            shown = max(0, min(int(one_liner_limit), total - verbatim))
