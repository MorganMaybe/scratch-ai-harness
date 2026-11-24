"""Agent-level tests for the reply-envelope layer (offline, provider doubles).

Recovered envelope shapes must apply on the first attempt and surface as
advisory lint warnings plus audit fields; an unrecoverable shape must cost
exactly one non-validation repair and still feed the reserved validation
repair.  The JSON fallback never enters the envelope.
"""

from __future__ import annotations

import json

from harness.agent import Agent
from harness.audit import AuditSettings, AuditStore
from harness.context import ProjectContext
from harness.dsl import envelope
from harness.llm import draw_square_response
from harness.providers.base import ModelReply

SQUARE_DSL = '''@on_flag(target="Sprite1", label="draw_square")
def draw_square():
    pen_clear()
    pen_down()
    for _ in range(4):
        move(100)
        turn_right(90)
    pen_up()
'''

UNKNOWN_CLONE_DSL = '''@on_flag(target="Sprite1", label="spawn")
def spawn():
    create_clone("Ghost")
'''


class _Replies:
    """Provider double: pop a reply object or raise an exception."""

    name = "dsl-fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


def _raw(text: str, **kwargs) -> ModelReply:
    values = {"data": {}, "raw_text": text, "model": "fake", "finish_reason": "stop"}
    values.update(kwargs)
    return ModelReply(**values)


def _fenced(module: str) -> str:
    return "```python\n" + module + "```\n"


def _turn_audit(tmp_path):
    store = AuditStore(
        AuditSettings(mode="full", directory=tmp_path / "audit", keep=10)
    )
    return store.start_turn(
        request_id=71,
        prompt="Draw a square.",
        target="Sprite1",
        context=ProjectContext.demo(),
        profile="mock",
        model="mock",
        base_url="",
        turn_budget_s=1.0,
        context_literal=None,
        generator="dsl",
    )


def _attempt_meta(audit, number: int) -> dict:
    path = audit.root / f"attempts/{number:02d}/meta.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_prose_after_the_closing_fence_applies_without_a_repair(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    raw = _fenced(SQUARE_DSL) + "Done - that draws a square.\n"
    provider = _Replies([_raw(raw)])

    agent = Agent(provider, ProjectContext.demo())
    result = agent.handle("Draw a square.", request_id=61)

    # A recovered envelope is not a repair: one model call, one attempt.
    assert result.attempts == 1
    assert len(provider.requests) == 1
    assert result.compiled.changes[0].action == "add_script"
    assert result.compiled.changes[0].label == "draw_square"
    assert (
        "reply envelope: ignored 1 line of prose after the closing fence"
        in result.lint_warnings
    )


def test_notes_after_the_closing_fence_are_appended_and_warned(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    raw = _fenced(SQUARE_DSL) + 'notes("The loop runs four times.")\n'
    provider = _Replies([_raw(raw)])

    agent = Agent(provider, ProjectContext.demo())
    result = agent.handle("Draw a square.", request_id=62)

    assert result.attempts == 1
    assert len(provider.requests) == 1
    assert result.changeset.notes == "The loop runs four times."
    assert result.compiled.changes[0].label == "draw_square"
    assert (
        "reply envelope: appended notes(...) from after the closing fence"
        in result.lint_warnings
    )


def test_a_clean_fenced_reply_produces_no_envelope_warnings(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    provider = _Replies([_raw(_fenced(SQUARE_DSL))])

    agent = Agent(provider, ProjectContext.demo())
    result = agent.handle("Draw a square.", request_id=63)

    assert result.attempts == 1
    assert result.lint_warnings == []
    assert not any(
        "reply envelope:" in warning for warning in result.lint_warnings
    )


def test_two_fenced_blocks_cost_one_repair_and_quote_the_diagnostic(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    two_blocks = _fenced(SQUARE_DSL) + "\n" + _fenced(SQUARE_DSL)
    provider = _Replies([_raw(two_blocks), _raw(SQUARE_DSL)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    result = agent.handle("Draw a square.", request_id=64)

    assert result.attempts == 2
    assert len(provider.requests) == 2
    assert result.compiled.changes[0].label == "draw_square"
    repair = provider.requests[1].user
    assert "reply envelope: two fenced code blocks" in repair
    assert "Previous module:" in repair
    assert provider.requests[1].reply_format == "dsl"


def test_envelope_fatal_earns_the_reserved_validation_repair(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    # Attempt 1 is an envelope fatal (non-validation).  Attempt 2 is a
    # parse-clean module that fails validation; with max_repairs=1 the extra
    # repair must be granted because the earlier repair was non-validation.
    two_blocks = _fenced(SQUARE_DSL) + "\n" + _fenced(SQUARE_DSL)
    provider = _Replies(
        [_raw(two_blocks), _raw(UNKNOWN_CLONE_DSL), _raw(SQUARE_DSL)]
    )

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    result = agent.handle("Spawn ghosts.", request_id=65)

    assert result.attempts == 3
    assert len(provider.requests) == 3
    assert result.compiled.changes[0].label == "draw_square"
    assert "unknown clone target 'Ghost'" in provider.requests[2].user


def test_envelope_fatal_is_one_of_two_non_validation_repairs(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    # Mirrors the existing reserved-repair pattern: the full max_repairs=2
    # budget goes to non-validation failures (envelope fatal, then a parse
    # error), so the following validation failure earns the one extra.
    two_blocks = _fenced(SQUARE_DSL) + "\n" + _fenced(SQUARE_DSL)
    provider = _Replies(
        [
            _raw(two_blocks),
            _raw("import os\n"),
            _raw(UNKNOWN_CLONE_DSL),
            _raw(SQUARE_DSL),
        ]
    )

    agent = Agent(provider, ProjectContext.demo(), max_repairs=2)
    result = agent.handle("Spawn ghosts.", request_id=66)

    assert result.attempts == 4
    assert len(provider.requests) == 4
    assert result.compiled.changes[0].label == "draw_square"


def test_audit_records_envelope_actions_and_fatal(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    two_blocks = _fenced(SQUARE_DSL) + "\n" + _fenced(SQUARE_DSL)
    prose_after = _fenced(SQUARE_DSL) + "That draws a square.\n"
    provider = _Replies([_raw(two_blocks), _raw(prose_after)])
    audit = _turn_audit(tmp_path)

    agent = Agent(provider, ProjectContext.demo(), audit=audit)
    result = agent.handle("Draw a square.", request_id=67)

    assert result.attempts == 2
    fatal_meta = _attempt_meta(audit, 1)
    assert fatal_meta["envelope_fatal"] is True
    assert fatal_meta["envelope_actions"] == []
    assert fatal_meta["envelope_action_count"] == 0

    recovered_meta = _attempt_meta(audit, 2)
    assert recovered_meta["envelope_actions"] == [
        "ignored 1 line of prose after the closing fence"
    ]
    assert recovered_meta["envelope_action_count"] == 1
    assert "envelope_fatal" not in recovered_meta


def test_json_fallback_never_enters_the_envelope(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    provider = _Replies([_raw(json.dumps(draw_square_response()))])

    calls = []
    original = envelope.normalize

    def spy(raw):
        calls.append(raw)
        return original(raw)

    monkeypatch.setattr(envelope, "normalize", spy)

    agent = Agent(provider, ProjectContext.demo())
    result = agent.handle("Draw a square.", request_id=68)

    assert calls == []
    assert result.attempts == 1
    assert result.compiled.changes[0].label == "draw_square"
