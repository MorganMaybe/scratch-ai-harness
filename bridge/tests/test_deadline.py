"""Agent deadline and repair-loop tests (offline)."""

from __future__ import annotations

import time

import pytest

import harness.agent as agent_module
from harness.agent import Agent
from harness.context import ProjectContext
from harness.llm import draw_square_response
from harness.providers.base import ModelReply, ProviderError
from harness.validator import ValidationError

INVALID = {
    "summary": "Bad block.",
    "changes": [
        {
            "action": "add_script",
            "target": "Sprite1",
            "label": "bad",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "move_to", "args": {}}],
        }
    ],
}


class ScriptedProvider:
    """Rich-interface provider that records every call."""

    name = "scripted"

    def __init__(self, replies: list[dict], *, on_call=None):
        self.replies = list(replies)
        self.calls: list = []
        self.on_call = on_call

    def complete(self, request):
        self.calls.append(request)
        if self.on_call is not None:
            self.on_call(len(self.calls))
        data = self.replies.pop(0) if self.replies else INVALID
        return ModelReply(
            data=data,
            model="scripted-model",
            latency_ms=42,
            usage={"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            attempts=1,
            finish_reason="stop",
        )


def test_valid_first_reply_uses_one_attempt():
    context = ProjectContext.demo()
    provider = ScriptedProvider([draw_square_response()])
    agent = Agent(provider, context)

    result = agent.handle("Make the cat draw a square.", request_id=9)

    assert result.attempts == 1
    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call.request_id == 9
    assert call.attempt == 1
    assert call.deadline is None
    assert result.model == "scripted-model"
    assert result.usage == {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}
    assert result.latency_ms == 42
    assert result.finish_reason == "stop"


def test_three_invalid_replies_exhaust_repairs():
    context = ProjectContext.demo()
    provider = ScriptedProvider([INVALID, INVALID, INVALID])
    agent = Agent(provider, context, max_repairs=2)

    with pytest.raises(ValidationError):
        agent.handle("Draw a square.", request_id=3)

    assert len(provider.calls) == 3


def test_deadline_in_the_past_fails_before_any_call():
    context = ProjectContext.demo()
    provider = ScriptedProvider([draw_square_response()])
    agent = Agent(provider, context)

    with pytest.raises(ProviderError) as caught:
        agent.handle("Draw a square.", deadline=time.monotonic() - 1.0)

    assert caught.value.code == "timeout"
    assert provider.calls == []


def test_deadline_expiring_between_repairs_stops_early(monkeypatch):
    clock = {"now": 100.0}
    monkeypatch.setattr(
        agent_module,
        "remaining_seconds",
        lambda deadline: None if deadline is None else deadline - clock["now"],
    )
    context = ProjectContext.demo()

    def advance(_call_number: int) -> None:
        clock["now"] += 2.0

    provider = ScriptedProvider([INVALID, INVALID, INVALID], on_call=advance)
    agent = Agent(provider, context, max_repairs=2)

    with pytest.raises(ProviderError) as caught:
        agent.handle("Draw a square.", deadline=101.5)

    assert caught.value.code == "timeout"
    assert "after 1 attempt(s)" in str(caught.value)
    assert len(provider.calls) < 3
    assert len(provider.calls) == 1


def test_legacy_complete_json_only_double_still_works():
    context = ProjectContext.demo()

    class LegacyDouble:
        name = "legacy"

        def __init__(self, replies):
            self.replies = list(replies)
            self.calls: list[tuple[str, str]] = []

        def complete_json(self, system, user):
            self.calls.append((system, user))
            return self.replies.pop(0)

    provider = LegacyDouble([draw_square_response()])
    agent = Agent(provider, context)

    result = agent.handle("Draw a square.", request_id=4)

    assert result.attempts == 1
    assert result.request_id == 4
    assert len(provider.calls) == 1
    assert result.model == ""
