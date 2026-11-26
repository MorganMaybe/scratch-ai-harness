"""Offline replay of the local audit corpus through the advisory lints.

Like ``test_dsl_envelope_corpus`` these tests read the audit turns kept on
this machine under ``scratch/base/audit`` and skip when that directory is
missing, so CI and fresh clones stay green.

Two properties matter here:

* ``lint_changeset`` must never raise on a historical module: the caller
  catches lint failures, but a crash would silently drop every warning;
* the slingshot bundle that motivated the say-while-hidden rule must actually
  report it.  Total warning counts are printed for information only, because
  a frozen audit should not fail the suite when a future rule starts firing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.context import ProjectContext
from harness.dsl import DSLError, DSLErrors, envelope, transpile
from harness.lints import lint_changeset
from harness.protocol import parse_literal

AUDIT_ROOT = (
    Path(__file__).resolve().parents[2] / "scratch" / "base" / "audit"
)

#: The slingshot turn that motivated the say-while-hidden rule: its accepted
#: module hides the Ball and then speaks through the "hud" script.
SLINGSHOT_TURN = AUDIT_ROOT / "20261125T232037.500499Z-req257832729"

#: One exact line from the accepted slingshot module, kept short so the test
#: pins the rule without pinning unrelated message wording.
HUD_WARNING = (
    "script 'hud' (Ball): say while hidden - speech bubbles on a hidden "
    "sprite do not show"
)

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


def _linted_attempt(
    raw_path: Path, context: ProjectContext
) -> list[str] | None:
    """Lint one attempt, or ``None`` when the module does not transpile."""
    try:
        raw = _read_utf8_sig(raw_path)
    except (OSError, UnicodeDecodeError):
        return None
    try:
        envelope.normalize(raw)
    except Exception as exc:  # normalize is documented as pure
        pytest.fail(f"envelope.normalize raised on {raw_path}: {exc!r}")
    try:
        changeset = transpile(raw, context)
    except DSLErrors:
        return None
    except DSLError:
        return None
    try:
        return lint_changeset(changeset, context, context.registry())
    except Exception as exc:
        pytest.fail(f"lint_changeset raised on {raw_path}: {exc!r}")


def test_lints_never_raise_on_historical_modules():
    turns_scanned = 0
    modules_linted = 0
    total_warnings = 0
    say_hidden = 0
    dead_store = 0
    read_never_set = 0
    other = 0

    for turn in _dsl_turns():
        context = _context(turn)
        if context is None:
            continue
        turns_scanned += 1
        for raw_path in sorted((turn / "attempts").glob("*/raw.txt")):
            warnings = _linted_attempt(raw_path, context)
            if warnings is None:
                continue
            modules_linted += 1
            total_warnings += len(warnings)
            for message in warnings:
                if "say while hidden" in message:
                    say_hidden += 1
                elif "written but never read" in message:
                    dead_store += 1
                elif "read but never set" in message:
                    read_never_set += 1
                else:
                    other += 1

    print(
        "audit lint replay: "
        f"{turns_scanned} turns, "
        f"{modules_linted} modules linted, "
        f"{total_warnings} warnings "
        f"(say-hidden={say_hidden}, dead-store={dead_store}, "
        f"read-never-set={read_never_set}, other={other})"
    )


def test_slingshot_turn_reports_say_while_hidden():
    if not SLINGSHOT_TURN.is_dir():
        pytest.skip(f"slingshot turn {SLINGSHOT_TURN.name} is not in the corpus")
    context = _context(SLINGSHOT_TURN)
    assert context is not None, "slingshot turn has no readable project context"

    warnings: list[str] = []
    for raw_path in sorted((SLINGSHOT_TURN / "attempts").glob("*/raw.txt")):
        attempt = _linted_attempt(raw_path, context)
        if attempt is not None:
            warnings.extend(attempt)

    assert HUD_WARNING in warnings, warnings
