"""Offline replay of the local audit corpus through the reply envelope.

These tests read the audit turns kept on this machine under
``scratch/base/audit``.  They are skipped when that directory is missing so
CI stays green.  The corpus is dozens of files, not thousands: the whole
module runs in well under a second.

The hard rule is the one the envelope layer exists for: a fence marker must
never survive into the module as a Python syntax error.  Historical model
defects (name gates, ambiguous operators, unrecoverable reply shapes) are
counted, not asserted, so a frozen audit does not fail the suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.context import ProjectContext
from harness.dsl import DSLError, DSLErrors, envelope, transpile
from harness.protocol import parse_literal

AUDIT_ROOT = (
    Path(__file__).resolve().parents[2] / "scratch" / "base" / "audit"
)

#: The cube turn that motivated the envelope layer: attempt 1 puts its
#: ``notes(...)`` call after the closing fence.
CUBE_TURN = AUDIT_ROOT / "20261123T065755.690242Z-req26071857"

pytestmark = pytest.mark.skipif(
    not AUDIT_ROOT.is_dir(),
    reason="local audit corpus scratch/base/audit is not present",
)


def _read_utf8_sig(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _context(turn: Path) -> ProjectContext | None:
    literal_path = turn / "context" / "project.literal"
    if not literal_path.is_file():
        return None
    try:
        literal = _read_utf8_sig(literal_path)
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return ProjectContext.from_literal(parse_literal(literal))
    except ValueError:
        return None


def _dsl_turns() -> list[Path]:
    """Turn directories whose ``meta.json`` records the DSL generator."""
    turns: list[Path] = []
    for turn in sorted(AUDIT_ROOT.iterdir()):
        if not turn.is_dir():
            continue
        meta_path = turn / "meta.json"
        try:
            meta = json.loads(_read_utf8_sig(meta_path))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if meta.get("generator") != "dsl":
            continue
        turns.append(turn)
    return turns


def _transpile_errors(
    raw: str, context: ProjectContext | None
) -> list[DSLError]:
    """Every diagnostic ``transpile`` reports, or an empty list on success."""
    try:
        transpile(raw, context)
    except DSLErrors as exc:
        return list(exc.errors)
    except DSLError as exc:
        return [exc]
    return []


def _offending_line(error: DSLError, raw: str) -> str:
    """The stripped source line a syntax diagnostic points at."""
    if error.line is None:
        return ""
    text = error.source if error.source is not None else raw
    lines = text.splitlines()
    if not 1 <= error.line <= len(lines):
        return ""
    return lines[error.line - 1].strip()


def test_cube_attempt_one_reports_content_errors_not_a_fence_artifact():
    if not CUBE_TURN.is_dir():
        pytest.skip(f"cube turn {CUBE_TURN.name} is not in the corpus")

    context = _context(CUBE_TURN)
    assert context is not None, "cube turn has no readable project context"
    raw = _read_utf8_sig(CUBE_TURN / "attempts" / "01" / "raw.txt")

    errors = _transpile_errors(raw, context)
    formatted = [error.format() for error in errors]
    assert errors, "the cube attempt is expected to have content diagnostics"

    # The trailing notes() is metadata, so the envelope recovers the module.
    normalized = envelope.normalize(raw)
    assert normalized.fatal is None
    assert normalized.actions == (
        "appended notes(...) from after the closing fence",
    )
    assert 'notes("' in normalized.module_text

    # 1. The fence around the module never becomes a Python syntax error.
    assert not any("Python syntax error" in text for text in formatted), formatted

    # 2. The real content diagnostics still surface.
    assert any(
        "already exists" in error.message
        and "'angle'" in error.message
        for error in errors
    ), formatted
    assert any(
        "'+' between two computed values is ambiguous" in error.message
        for error in errors
    ), formatted

    # 3. The envelope recovered the shape instead of failing on it.
    assert not any(
        error.message.startswith(envelope.ENVELOPE_PREFIX)
        for error in errors
    ), formatted


def test_no_reply_leaves_a_fence_line_as_a_python_syntax_error():
    turns_scanned = 0
    clean = 0
    dialect_diagnostics = 0
    envelope_fatals = 0
    fence_syntax_errors: list[str] = []

    for turn in _dsl_turns():
        context = _context(turn)
        if context is None:
            continue
        turns_scanned += 1
        for raw_path in sorted((turn / "attempts").glob("*/raw.txt")):
            try:
                raw = _read_utf8_sig(raw_path)
            except (OSError, UnicodeDecodeError):
                continue

            try:
                envelope.normalize(raw)
            except Exception as exc:  # normalize is documented as pure
                pytest.fail(f"envelope.normalize raised on {raw_path}: {exc!r}")

            errors = _transpile_errors(raw, context)
            if not errors:
                clean += 1
                continue
            if any(
                error.message.startswith(envelope.ENVELOPE_PREFIX)
                for error in errors
            ):
                envelope_fatals += 1
                continue

            dialect_diagnostics += 1
            for error in errors:
                if "Python syntax error" not in error.message:
                    continue
                line = _offending_line(error, raw)
                if line.startswith("```") or line.startswith("~~~"):
                    fence_syntax_errors.append(
                        f"{raw_path}: line {error.line}: {line}"
                    )

    assert not fence_syntax_errors, fence_syntax_errors
    print(
        "audit replay: "
        f"{turns_scanned} turns, "
        f"{clean} clean attempts, "
        f"{dialect_diagnostics} with dialect diagnostics, "
        f"{envelope_fatals} envelope fatals"
    )
