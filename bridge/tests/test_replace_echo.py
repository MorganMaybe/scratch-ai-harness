"""The replace echo: a deterministic backstop against blind destructive rewrites.

A turn is stateless.  When the model replaces a script whose exact current body
the bridge already holds (``tuples`` in the project context) without loading
that sprite first, it is reconstructing the script from a label and a block
count.  The echo shows it the real body plus its own submission and asks for a
resubmission.  It is one extra model call, never a repair, and strictly once
per turn.
"""

from __future__ import annotations

import json

import pytest

import harness.agent as agent_module
from harness.agent import Agent, CancelToken
from harness.audit import AuditSettings, AuditStore
from harness.context import ProjectContext, ScriptSummary
from harness.llm import MockLLM, bigger_square_response, draw_square_response
from harness.providers.base import ModelReply, ProviderError
from harness.smalltalk import Sym
from harness.validator import ValidationError

#: Replaces ``ai-1`` and deliberately changes the body: ``move(10)`` can then
#: only come from the current-body section of the echo.
REPLACE_DSL = '''@on_flag(target="Sprite1", label="bounce", script_id="ai-1")
def bounce():
    move(50)
    wait(0.1)
'''

DELETE_SCRIPT = {
    "summary": "Removed the bounce.",
    "changes": [{"action": "delete_script", "script_id": "ai-1"}],
}


class _Replies:
    """Provider double: pop a reply object or raise an exception."""

    name = "replace-echo-fake"

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


def _context_with_body(label: str = "bounce") -> ProjectContext:
    """A sprite with one AI-owned script whose exact current body is known."""
    context = ProjectContext.demo()
    context.sprites["Sprite1"].scripts.append(
        ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label=label,
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


def _turn(tmp_path, context: ProjectContext, request_id: int = 1):
    store = AuditStore(
        AuditSettings(mode="full", directory=tmp_path / "audit", keep=10)
    )
    return store.start_turn(
        request_id=request_id,
        prompt="Make it jump higher.",
        target="Sprite1",
        context=context,
        profile="mock",
        model="mock",
        base_url="",
        turn_budget_s=1.0,
    )


def _attempt_meta(audit, number: int) -> dict:
    path = audit.root / f"attempts/{number:02d}/meta.json"
    return json.loads(path.read_text(encoding="utf-8"))


# --- the echo fires --------------------------------------------------------


def test_echo_fires_once_and_the_resubmission_applies(tmp_path):
    context = _context_with_body()
    audit = _turn(tmp_path, context)
    assert audit is not None
    provider = MockLLM(
        [bigger_square_response("ai-1"), bigger_square_response("ai-1")]
    )
    agent = Agent(provider, context, audit=audit)

    result = agent.handle("Make it jump higher.", request_id=1)

    assert result.attempts == 2
    assert result.compiled.changes[0].action == "replace_script"
    first_system, first_user = provider.calls[0]
    _, echo = provider.calls[1]
    # The blind turn had no bodies; the echo supplies them plus the submission.
    assert "Current bodies of the script(s)" not in first_user
    assert "Current bodies of the script(s) you are about to replace:" in echo
    assert '"op":"when_flag_clicked"' in echo
    assert '"steps":10' in echo
    assert '"action": "replace_script"' in echo
    assert echo.endswith("without the resend.\n")
    assert "# Loaded sprite detail: Sprite1" not in first_system

    first = _attempt_meta(audit, 1)
    assert first["replace_echo"] is True
    assert first["echo_sprites"] == ["Sprite1"]
    assert "replace_echo" not in _attempt_meta(audit, 2)
    echoed_prompt = (audit.root / "prompts/user-02.txt").read_text(encoding="utf-8")
    assert "Current bodies of the script(s)" in echoed_prompt


def test_echo_does_not_consume_a_repair():
    context = _context_with_body()
    provider = MockLLM(
        [bigger_square_response("ai-1"), bigger_square_response("ai-1")]
    )
    agent = Agent(provider, context, max_repairs=0)

    result = agent.handle("Make it jump higher.", request_id=1)

    assert result.attempts == 2
    assert result.compiled.changes[0].action == "replace_script"


def test_echo_is_strictly_once_per_turn():
    context = _context_with_body()
    provider = MockLLM(
        [
            bigger_square_response("ai-1"),
            bigger_square_response("ai-1"),
            draw_square_response(),
        ]
    )
    agent = Agent(provider, context)

    result = agent.handle("Make it jump higher.", request_id=1)

    # The resubmission is still blind; it applies as-is instead of echoing
    # again, so the canned third reply is never consumed.
    assert result.attempts == 2
    assert len(provider.calls) == 2
    assert result.compiled.changes[0].action == "replace_script"


def test_echo_shows_only_the_scripts_being_replaced():
    context = _context_with_body()
    context.sprites["Sprite1"].scripts.append(
        ScriptSummary(
            script_id="ai-2",
            target="Sprite1",
            label="spin",
            hat="EventHatMorph",
            block_count=2,
            owned=True,
            tuples=[
                [Sym("EventHatMorph"), "Scratch-StartClicked"],
                [Sym("turnRight:"), 15],
            ],
        )
    )
    provider = MockLLM(
        [bigger_square_response("ai-1"), bigger_square_response("ai-1")]
    )
    agent = Agent(provider, context)

    agent.handle("Make it jump higher.", request_id=1)

    echo = provider.calls[1][1]
    assert '- ai-1 "bounce"' in echo
    assert '- ai-2 "spin"' not in echo
    assert '"degrees":15' not in echo


# --- the echo stays quiet --------------------------------------------------


def test_no_echo_when_the_sprite_was_loaded_first():
    context = _context_with_body()
    provider = MockLLM(
        [
            {"load_sprite": ["Sprite1"], "reason": "need the bounce body"},
            bigger_square_response("ai-1"),
        ]
    )
    agent = Agent(provider, context)

    result = agent.handle("Make it jump higher.", request_id=1)

    assert result.attempts == 2
    loaded_system, loaded_user = provider.calls[1]
    assert "# Loaded sprite detail: Sprite1" in loaded_system
    assert "now included in the system prompt" in loaded_user
    assert "Current bodies of the script(s)" not in loaded_user
    assert result.compiled.changes[0].action == "replace_script"


def test_no_echo_when_the_replaced_script_has_no_tuples():
    context = ProjectContext.demo()
    context.sprites["Sprite1"].scripts.append(
        ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label="bounce",
            hat="EventHatMorph",
            block_count=2,
            owned=True,
            tuples=None,
        )
    )
    provider = MockLLM([bigger_square_response("ai-1")])
    agent = Agent(provider, context)

    result = agent.handle("Make it jump higher.", request_id=1)

    assert result.attempts == 1
    assert len(provider.calls) == 1
    assert result.compiled.changes[0].action == "replace_script"


@pytest.mark.parametrize(
    "reply",
    [draw_square_response(), DELETE_SCRIPT],
    ids=["add_script", "delete_script"],
)
def test_no_echo_for_add_or_delete_script(reply):
    context = _context_with_body()
    provider = MockLLM([reply])
    agent = Agent(provider, context)

    result = agent.handle("Change the script.", request_id=1)

    assert result.attempts == 1
    assert len(provider.calls) == 1


def test_no_echo_for_a_user_script():
    context = ProjectContext.demo()
    context.sprites["Sprite1"].scripts.append(
        ScriptSummary(
            script_id="user-1",
            target="Sprite1",
            label="mine",
            hat="EventHatMorph",
            block_count=2,
            owned=False,
            tuples=[
                [Sym("EventHatMorph"), "Scratch-StartClicked"],
                [Sym("forward:"), 10],
            ],
        )
    )
    provider = MockLLM(
        [
            {
                "summary": "Replaced a user script.",
                "changes": [
                    {
                        "action": "replace_script",
                        "script_id": "user-1",
                        "target": "Sprite1",
                        "label": "mine",
                        "hat": {"op": "when_flag_clicked"},
                        "body": [{"op": "pen_down"}],
                    }
                ],
            }
        ]
    )
    agent = Agent(provider, context, max_repairs=0)

    with pytest.raises(ValidationError):
        agent.handle("Change my script.", request_id=1)

    assert len(provider.calls) == 1


# --- mode awareness --------------------------------------------------------


def test_dsl_echo_quotes_the_module_and_asks_for_one_python_block(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    monkeypatch.setenv("HARNESS_PROMPT_BUDGET", "400000")
    provider = _Replies([_raw(REPLACE_DSL), _raw(REPLACE_DSL)])
    agent = Agent(provider, _context_with_body())

    result = agent.handle("Make it bounce higher.", request_id=41)

    assert result.attempts == 2
    echo = provider.requests[1].user
    assert "Current bodies of the script(s) you are about to replace:" in echo
    # The current body, rendered in the dialect.
    assert "move(10)" in echo
    assert '@on_flag(target="Sprite1", label="bounce")\ndef bounce():' in echo
    # The model's own module, verbatim.
    assert '```python\n@on_flag(target="Sprite1", label="bounce", script_id="ai-1")' in echo
    assert "ONE fenced python block" in echo
    assert "Do not switch to a JSON" in echo
    assert '{"load_sprite": ["Sprite1"]}' in echo
    assert provider.requests[1].reply_format == "dsl"


def test_json_echo_quotes_the_payload_and_asks_for_one_json_object():
    context = _context_with_body()
    provider = MockLLM(
        [bigger_square_response("ai-1"), bigger_square_response("ai-1")]
    )
    agent = Agent(provider, context)

    agent.handle("Make it jump higher.", request_id=42)

    echo = provider.calls[1][1]
    # The current body, rendered as JSON IR.
    assert '"hat":{"op":"when_flag_clicked"}' in echo
    assert '"steps":10' in echo
    # The model's own submission.
    assert '```json\n{\n  "summary":' in echo
    assert '"action": "replace_script"' in echo
    assert "ONE JSON object" in echo
    assert "one fenced python block" not in echo
    assert '{"load_sprite": ["Sprite1"]}' in echo


# --- cancellation and deadline --------------------------------------------


def test_echo_respects_a_cancel_token_set_after_the_blind_reply(monkeypatch):
    token = CancelToken()
    context = _context_with_body()
    provider = MockLLM(
        [bigger_square_response("ai-1"), bigger_square_response("ai-1")]
    )
    agent = Agent(provider, context, cancel_token=token)
    original = Agent._replace_echo

    def cancelling_echo(self, *args, **kwargs):
        echo = original(self, *args, **kwargs)
        if echo is not None:
            token.cancel()
        return echo

    monkeypatch.setattr(Agent, "_replace_echo", cancelling_echo)

    with pytest.raises(ProviderError) as caught:
        agent.handle("Make it jump higher.", request_id=1)

    assert caught.value.code == "cancelled"
    assert len(provider.calls) == 1, "cancellation must prevent the echo model call"


def test_echo_honours_the_turn_deadline(monkeypatch):
    context = _context_with_body()
    provider = MockLLM(
        [bigger_square_response("ai-1"), bigger_square_response("ai-1")]
    )
    remaining = [None, 0.5]
    monkeypatch.setattr(
        agent_module,
        "remaining_seconds",
        lambda deadline: remaining.pop(0) if remaining else 0.5,
    )
    agent = Agent(provider, context)

    with pytest.raises(ProviderError) as caught:
        agent.handle("Make it jump higher.", request_id=1)

    assert caught.value.code == "timeout"
    assert "turn budget exhausted after 1 attempt(s)" in caught.value.message
    assert len(provider.calls) == 1
