"""Reply-envelope normalization for Scratch-Python model replies.

A raw reply has an *envelope* -- fences, tags, prose around the module,
CRLF/BOM noise -- and *content*: the module itself.  This layer is pure and
line-based: it recovers the recoverable shapes, records every recovery as a
short human-readable action, and reports the unrecoverable ones as one
fatal diagnostic the repair loop can quote.  It never runs the Python
parser (that is ``ast``'s job in ``parse.py``), never invents module text,
and never picks between two candidate modules.

Rule matrix (see HANDOFF.md, "Planned next: a DSL reply-envelope layer"):

    one fenced block, nothing else     use it
    no fence at all                    parse raw as-is (kept)
    prose before the opening fence     skip, record action
    module-shaped code before the      fatal: move it inside the module
    opening fence
    missing closing fence              treat EOF as the close, recover
    summary()/notes() after the close  append as metadata, recover
    other prose after the close        drop, record action
    second fenced code block           fatal: two candidate modules
    module-shaped code after the close fatal: move it inside the module
    prose-only reply                   fatal: no module - finalized by
                                       ``parse.py`` via ``prose_diagnostic``
                                       once ``ast`` has rejected the text,
                                       so forbidden-but-valid Python
                                       (``import``, ``class``) still gets
                                       its precise dialect diagnostic
    tag variants, indented or doubled  normalize
    fences, CRLF, BOM
    reply is a JSON object             the agent's JSON fallback (unchanged)

Recovered actions cost zero repairs: the agent surfaces them as advisory
``warning:`` lines and audit fields.  Fatal diagnostics carry the
:data:`ENVELOPE_PREFIX` marker so the scorer can classify them, and their
line numbers refer to the normalized raw reply (``DSLError.source`` holds
that text, so ``format(include_source=True)`` can quote the offending line).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import DSLError

#: Every fatal envelope diagnostic starts with this marker, so the repair
#: loop, the audit and the scorer can tell an envelope failure from a
#: module-content failure without deeper string inspection.
ENVELOPE_PREFIX = "reply envelope: "

#: One-line repair instruction shared by every fatal envelope diagnostic.
REPAIR_HINT = (
    "Reply with exactly one fenced python block: opening fence, the module, "
    "closing fence, and nothing else. Put every summary()/notes() call "
    "inside the fence."
)

#: A fence marker at line start: three or more backticks or tildes,
#: optionally indented up to three spaces.
_FENCE_START_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")

#: Everything after the fence marker on an opening line must be empty or a
#: short language tag (```python, ```py, ~~~python); anything else is prose.
#: A tag needs at least one alphanumeric character, so a punctuation-only
#: remainder (a sloppy closing fence) never opens a block.
_TAG_RE = re.compile(r"[A-Za-z0-9_+\-]{0,16}")

#: A closing fence may end with a punctuation character (models write
#: "```." or "```\"").
_CLOSE_INFO_RE = re.compile(r"[.,;:!?'\"\s]*")

#: The only module-level calls recoverable from after the closing fence:
#: they carry no block semantics, only the change set's metadata.
_METADATA_CALL_RE = re.compile(r"^\s{0,8}(summary|notes)\s*\(")

#: A line that could begin Scratch-Python module content: a decorator, a
#: def, a call or an assignment.  Used to reject prose-only replies and to
#: refuse silently dropping module-shaped lines outside a fence; anything
#: matching it is handed to ``ast`` unchanged.
_MODULE_LINE_RE = re.compile(
    r"^\s{0,8}(@|def\s+|[A-Za-z_]\w*\s*\(|[A-Za-z_]\w*\s*=[^=])"
)


@dataclass(frozen=True)
class NormalizedReply:
    """The result of envelope normalization.

    ``actions`` are short, stable, human-readable phrases describing every
    recovery, oldest first (empty for a clean reply).  ``fatal`` is set only
    when the reply shape cannot be recovered; its line number and
    ``source`` refer to the normalized raw reply, not the module text.
    """

    module_text: str
    actions: tuple[str, ...] = ()
    fatal: DSLError | None = None


def _fatal(message: str, line: int, source: str) -> DSLError:
    return DSLError(
        ENVELOPE_PREFIX + message,
        line=line,
        hint=REPAIR_HINT,
        source=source,
    )


def _fence_info(line: str) -> str | None:
    """The text after the fence marker, or ``None`` when not a fence line."""
    match = _FENCE_START_RE.match(line)
    if match is None:
        return None
    return line[match.end() :].strip()


def _opens(info: str | None) -> bool:
    """A fence line with an empty remainder or a valid language tag opens."""
    if info is None:
        return False
    if info == "":
        return True
    return _TAG_RE.fullmatch(info) is not None and any(
        character.isalnum() for character in info
    )


def _closes(info: str | None) -> bool:
    """A fence line with an empty or punctuation-only remainder closes."""
    return info is not None and _CLOSE_INFO_RE.fullmatch(info) is not None


def _line_no(index: int) -> int:
    return index + 1


def _fence_line(line: str) -> bool:
    """A line that is a fence marker in either role (never prose)."""
    info = _fence_info(line)
    return _opens(info) or _closes(info)


def _after_close_plan(
    after: list[str], source: str, base_line: int
) -> tuple[list[str], int, DSLError | None]:
    """Classify the region after a closing fence.

    Returns ``(metadata_blocks, prose_lines, fatal)``; ``fatal`` is set for
    a second fenced block or module-shaped code, and its line number is
    computed against ``base_line`` (the raw-reply index one line past the
    closing fence).  Metadata blocks are the joined text of each
    ``summary()``/``notes()`` call, collected while parentheses stay
    unbalanced (line-based, never a Python parse).
    """
    metadata: list[str] = []
    prose = 0
    index = 0
    while index < len(after):
        line = after[index]
        if not line.strip():
            index += 1
            continue
        info = _fence_info(line)
        if _opens(info) or _closes(info):
            return metadata, prose, _fatal(
                "two fenced code blocks - the reply must contain exactly "
                "one module.",
                _line_no(base_line + index),
                source,
            )
        if _METADATA_CALL_RE.match(line):
            buffer = [line]
            depth = line.count("(") - line.count(")")
            while depth > 0 and index + 1 < len(after):
                index += 1
                buffer.append(after[index])
                depth += after[index].count("(") - after[index].count(")")
            metadata.append("\n".join(buffer))
            index += 1
            continue
        if _MODULE_LINE_RE.match(line):
            return metadata, prose, _fatal(
                "code after the closing fence - move it inside the module.",
                _line_no(base_line + index),
                source,
            )
        prose += 1
        index += 1
    return metadata, prose, None


def normalize(raw: str) -> NormalizedReply:
    """Normalize one raw model reply into module text plus envelope facts.

    Pure and line-based.  Never raises: an unrecoverable reply shape is
    reported through ``NormalizedReply.fatal``.
    """
    text = "" if raw is None else str(raw)
    actions: list[str] = []

    # Byte-level normalization: BOM and CRLF never carry meaning.
    if text.startswith("\ufeff"):
        text = text[1:]
        actions.append("stripped a byte-order mark")
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        actions.append("normalized CRLF line endings")

    lines = text.split("\n")
    count = len(lines)

    # Locate the one opening fence and its closing fence (if any).
    open_at = None
    index = 0
    while index < count:
        info = _fence_info(lines[index])
        if not _opens(info):
            index += 1
            continue
        # A doubled opening fence: "```" immediately followed by "```python".
        # The first marker is spurious; the tagged one is the real opener.
        if index + 1 < count:
            next_info = _fence_info(lines[index + 1])
            if _opens(next_info) and not _closes(next_info):
                actions.append("dropped a doubled opening fence")
                index += 1
                continue
        open_at = index
        break
    if open_at is None:
        return _no_fence_reply(text, actions)

    # Prose before the opening fence is skipped; fence lines dropped above
    # are never counted as prose, and module-shaped lines there are never
    # silently dropped.
    before = lines[:open_at]
    prose_before = [
        n
        for n, line in enumerate(before)
        if line.strip() and not _fence_line(line)
    ]
    module_before = [
        n for n, line in enumerate(before) if _MODULE_LINE_RE.match(line)
    ]
    if module_before:
        first = module_before[0]
        return NormalizedReply(
            "",
            tuple(actions),
            _fatal(
                "code before the opening fence - move it inside the module.",
                _line_no(first),
                text,
            ),
        )
    if prose_before:
        total = len(prose_before)
        actions.append(
            f"skipped {total} line{'s' if total != 1 else ''} of prose "
            "before the opening fence"
        )

    # The closing fence: the next line that closes, or end of reply.
    close_at = None
    index = open_at + 1
    while index < count:
        if _closes(_fence_info(lines[index])):
            close_at = index
            break
        index += 1
    if close_at is None:
        actions.append("treated the end of reply as the closing fence")

    content = lines[open_at + 1 : close_at if close_at is not None else count]
    after = lines[close_at + 1 :] if close_at is not None else []
    # The first ``after`` line sits at raw index ``close_at + 1``.
    base_line = (close_at + 1) if close_at is not None else count

    metadata, prose_after, fatal = _after_close_plan(after, text, base_line)
    if fatal is not None:
        return NormalizedReply("", tuple(actions), fatal)
    if metadata:
        for block in metadata:
            name = "summary(...)" if block.lstrip().startswith("summary") else "notes(...)"
            actions.append(f"appended {name} from after the closing fence")
    if prose_after:
        actions.append(
            f"ignored {prose_after} line{'s' if prose_after != 1 else ''} "
            "of prose after the closing fence"
        )

    parts = ["\n".join(content)]
    parts.extend(metadata)
    module_text = "\n".join(parts).strip("\n")
    return NormalizedReply(module_text, tuple(actions), None)


def _no_fence_reply(text: str, actions: list[str]) -> NormalizedReply:
    """A reply without any fence is parsed as-is (kept behaviour).

    Prose-only rejection is deliberately NOT done here: valid Python the
    dialect forbids (``import``, ``class``) must reach the transpiler's
    precise diagnostics.  :func:`prose_diagnostic` classifies prose after
    ``ast`` has already rejected the text.
    """
    return NormalizedReply(text.strip(), tuple(actions), None)


def prose_diagnostic(text: str) -> DSLError | None:
    """The fatal "no module - only prose" diagnostic, or ``None``.

    The caller must run this only on text ``ast.parse`` has already
    rejected: that failure is the real prose signal, and this line-based
    classifier then decides whether the diagnostic should name the reply
    shape instead of quoting a confusing Python syntax error.  Text with
    any module-shaped line (decorator, def, call, assignment) returns
    ``None`` so the ordinary syntax-error diagnostic is kept.
    """
    lines = ("" if text is None else str(text)).split("\n")
    content = [line for line in lines if line.strip()]
    if not content or any(_MODULE_LINE_RE.match(line) for line in content):
        return None
    first = next(index for index, line in enumerate(lines) if line.strip())
    return _fatal(
        "the reply contains no module - only prose.",
        _line_no(first),
        str(text),
    )
