"""Agent integration tests for generator=dsl (offline, provider doubles)."""

from __future__ import annotations

import pytest

from harness.agent import Agent
from harness.context import ProjectContext, ScriptSummary
from harness.llm import draw_square_response
from harness.providers.base import ModelReply, ProviderError
from harness.smalltalk import Sym
from harness.validator import ValidationError

SQUARE_DSL = '''@on_flag(target="Sprite1", label="draw_square")
def draw_square():
    pen_clear()
    pen_down()
    for _ in range(4):
        move(100)
        turn_right(90)
    pen_up()
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


def _context_with_detail() -> ProjectContext:
    context = ProjectContext.demo()
    context.sprites["Sprite1"].scripts.append(
        ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label="bounce",
            hat="EventHatMorph",
            block_count=2,
            owned=True,
            tuples=[
                [Sym("EventHatMorph"), "Scratch-StartClicked"],
                [Sym("forward:"), 10],
            ],
        )
    )
    return context


def test_dsl_happy_path_compiles_and_sends_the_dialect_prompt(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    monkeypatch.setenv("HARNESS_PROMPT_BUDGET", "400000")
    provider = _Replies([_raw(SQUARE_DSL)])

    agent = Agent(provider, ProjectContext.demo())
    result = agent.handle("Draw a square.", request_id=31)

    assert result.attempts == 1
    assert result.compiled.changes[0].action == "add_script"
    assert result.compiled.changes[0].label == "draw_square"
    assert result.compiled.changes[0].script_id == "ai-1"
    request = provider.requests[0]
    assert request.reply_format == "dsl"
    assert "Scratch-Python API reference (generated from the block catalog)" in request.system
    assert "The Python you MAY use" in request.system
    assert "The Python you may NOT use" in request.system


def test_dsl_transpile_error_uses_one_repair_and_quotes_it(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    bad = "import os\n\n" + SQUARE_DSL
    provider = _Replies([_raw(bad), _raw(SQUARE_DSL)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    result = agent.handle("Draw a square.", request_id=32)

    assert result.attempts == 2
    assert result.compiled.changes[0].label == "draw_square"
    repair = provider.requests[1].user
    assert "Your previous Scratch-Python module could not be used." in repair
    assert "imports are not part of the dialect" in repair
    assert "Previous module:" in repair
    assert "import os" in repair
    assert provider.requests[1].reply_format == "dsl"


def test_dsl_mode_still_accepts_a_dict_reply(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    provider = _Replies(
        [ModelReply(data=draw_square_response(), model="fake", attempts=1)]
    )

    agent = Agent(provider, ProjectContext.demo())
    result = agent.handle("Draw a square.", request_id=33)

    assert result.attempts == 1
    assert result.compiled.changes[0].label == "draw_square"
    assert provider.requests[0].reply_format == "dsl"


def test_dsl_mode_accepts_a_raw_json_context_request(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    provider = _Replies(
        [
            _raw('{"load_sprite": ["Sprite1"], "reason": "need the bounce body"}'),
            _raw(SQUARE_DSL),
        ]
    )

    agent = Agent(provider, _context_with_detail())
    result = agent.handle("Revise the bounce.", request_id=34)

    assert result.attempts == 2
    second = provider.requests[1]
    assert "# Loaded sprite detail: Sprite1" in second.system
    assert '@on_flag(target="Sprite1", label="bounce")' in second.system
    assert "move(10)" in second.system
    assert "now included in the system prompt" in second.user


def test_dsl_validation_failure_repairs_with_the_module(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    bad_costume = '''@on_flag(target="Sprite1", label="bad_costume")
def bad_costume():
    switch_costume("missing")
'''
    provider = _Replies([_raw(bad_costume), _raw(SQUARE_DSL)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    result = agent.handle("Do a costume trick.", request_id=35)

    assert result.attempts == 2
    repair = provider.requests[1].user
    assert "unknown costume 'missing'" in repair
    assert "switch_costume(\"missing\")" in repair
    # Fragment repair is JSON-only; the DSL path always asks for the module.
    assert "corrected module" in repair
    assert '"changes"' not in repair


def test_dsl_repairs_exhausted_to_validation_error(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    bad = "import os\n"
    provider = _Replies([_raw(bad), _raw(bad)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    with pytest.raises(ValidationError) as caught:
        agent.handle("Draw a square.", request_id=36)

    assert any("imports are not part of the dialect" in str(issue) for issue in caught.value.issues)
    assert caught.value.attempts == 2


def test_dsl_mode_does_not_fragment_repair(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    provider = _Replies([_raw("this is not python at all\n", model="fake"), _raw(SQUARE_DSL)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    agent.handle("Draw a square.", request_id=37)

    # A DSL rejection must ask for the whole module, never the JSON fragment
    # shape used for one or two bad JSON changes.
    assert "Python syntax error" in provider.requests[1].user
    assert "corrected module" in provider.requests[1].user
