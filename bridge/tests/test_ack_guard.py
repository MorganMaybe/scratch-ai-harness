"""The empty-acknowledgment guard: a deterministic backstop against fake acks.

An empty change set is the legal acknowledgment shape, so a model can answer a
request that plainly demands a change with ``summary`` + ``notes`` only.  The
bridge cannot verify such a claim from the summary text, so it checks it once
against the current AI-owned bodies:

* one guard round trip restates the request, shows every current body and
  offers two honest outs (confirm it, or make the change now);
* an acknowledgment that directly answers a no-op guard prompt is accepted
  without a second check (the model already saw the bodies);
* a project with no AI-owned bodies skips the guard (nothing to check).
"""

from __future__ import annotations

import json

import pytest

from harness.agent import Agent
from harness.audit import AuditSettings, AuditStore
from harness.context import ProjectContext, ScriptSummary
from harness.llm import draw_square_response
from harness.providers.mock import MockProvider
from harness.smalltalk import Sym

ACK_SUMMARY = "The power cap now clamps to 200."
ACK_NOTES = "No changes were needed."

#: An acknowledgment in both reply shapes the bridge accepts.
ACK_JSON = {
    "summary": ACK_SUMMARY,
    "changes": [],
    "notes": ACK_NOTES,
}
ACK_DSL = f'summary("{ACK_SUMMARY}")\nnotes("{ACK_NOTES}")\n'

#: Replaces ``ai-1`` with exactly the blocks and label it already has.  The
#: no-op guard (not the ack guard) owns this shape.
IDENTICAL_JSON = {
    "summary": "The bounce already starts at 10.",
    "changes": [
        {
            "action": "replace_script",
            "script_id": "ai-1",
            "target": "Sprite1",
            "label": "bounce",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "move", "args": {"steps": 10}}],
        }
    ],
}

#: A real ``add_script`` module for the DSL turn (no replace, so no echo).
ADD_SQUARE_DSL = '''@on_flag(target="Sprite1", label="square")
def square():
    pen_clear()
    pen_down()
    for _ in range(4):
        move(100)
        turn_right(90)
    pen_up()
'''

REQUEST = "Make the power cap 200."


def _context_with_body(label: str = "bounce", tuples=None) -> ProjectContext:
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
            tuples=tuples
            if tuples is not None
            else [
                [Sym("EventHatMorph"), "Scratch-StartClicked"],
                [Sym("forward:"), 10],
            ],
        )
    )
    return context


def _turn(tmp_path, context: ProjectContext, request: str = REQUEST):
    store = AuditStore(
        AuditSettings(mode="full", directory=tmp_path / "audit", keep=10)
    )
    return store.start_turn(
        request_id=1,
        prompt=request,
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


# --- the guard fires once ---------------------------------------------------


@pytest.mark.parametrize(
    "generator,ack,change",
    [
        ("json", ACK_JSON, draw_square_response()),
        ("dsl", ACK_DSL, ADD_SQUARE_DSL),
    ],
    ids=["json", "dsl"],
)
def test_ack_then_change_set_applies_after_one_guard(
    monkeypatch, generator, ack, change
):
    monkeypatch.setenv("HARNESS_GENERATOR", generator)
    monkeypatch.setenv("HARNESS_PROMPT_BUDGET", "400000")
    context = _context_with_body()
    provider = MockProvider([ack, change])

    result = Agent(provider, context).handle(REQUEST, request_id=1)

    assert result.attempts == 2
    assert len(provider.calls) == 2
    guard = provider.calls[1].user
    # The request verbatim, the current body, and both honest outs.
    assert REQUEST in guard
    assert "# Current body: Sprite1" in guard
    if generator == "dsl":
        assert "move(10)" in guard
    else:
        assert '"steps":10' in guard
    assert "You returned no changes" in guard
    assert "1. If the current project genuinely already satisfies" in guard
    assert "2. Otherwise make the change" in guard
    assert provider.calls[1].reply_format == generator

    assert len(result.compiled.changes) == 1
    assert result.compiled.changes[0].action == "add_script"
    # The second reply is a real change, not an acknowledgment.
    assert result.compiled.changes[0].target == "Sprite1"


def test_second_acknowledgment_after_the_guard_is_accepted(tmp_path):
    context = _context_with_body()
    audit = _turn(tmp_path, context)
    provider = MockProvider([ACK_JSON, ACK_JSON])

    result = Agent(provider, context, audit=audit).handle(REQUEST, request_id=1)

    assert result.attempts == 2
    assert len(provider.calls) == 2
    assert "Choose one:" in provider.calls[1].user
    # The guard fires only once; the second ack is accepted as the answer.
    assert result.changeset.changes == []
    assert result.compiled.changes == []
    assert ACK_SUMMARY in result.compiled.chat_summary()
    assert ACK_NOTES in result.compiled.chat_summary()

    first = _attempt_meta(audit, 1)
    assert first["ack_guard"] is True
    assert first["ack_sprites"] == ["Sprite1"]
    assert "ack_guard" not in _attempt_meta(audit, 2)


def test_audit_records_ack_guard_and_ack_sprites(tmp_path):
    context = _context_with_body()
    audit = _turn(tmp_path, context)
    provider = MockProvider([ACK_JSON, draw_square_response()])

    result = Agent(provider, context, audit=audit).handle(REQUEST, request_id=1)

    assert result.attempts == 2
    first = _attempt_meta(audit, 1)
    assert first["ack_guard"] is True
    assert first["ack_sprites"] == ["Sprite1"]
    assert "ack_guard" not in _attempt_meta(audit, 2)


# --- the guard stays quiet --------------------------------------------------


def test_a_direct_change_set_never_triggers_the_guard(tmp_path):
    context = _context_with_body()
    audit = _turn(tmp_path, context)
    provider = MockProvider([draw_square_response()])

    result = Agent(provider, context, audit=audit).handle(REQUEST, request_id=1)

    assert result.attempts == 1
    assert len(provider.calls) == 1
    assert "Choose one:" not in provider.calls[0].user
    assert "ack_guard" not in _attempt_meta(audit, 1)


def test_ack_answering_a_noop_guard_is_accepted_without_the_ack_guard(
    tmp_path,
):
    context = _context_with_body()
    audit = _turn(tmp_path, context)
    provider = MockProvider([IDENTICAL_JSON, ACK_JSON])

    result = Agent(provider, context, audit=audit).handle(REQUEST, request_id=1)

    assert result.attempts == 2
    assert len(provider.calls) == 2
    # Attempt 2's prompt was the no-op guard, not the ack guard.
    noop_prompt = provider.calls[1].user
    assert "identical to the current" in noop_prompt
    assert "You returned no changes" not in noop_prompt
    assert result.compiled.changes == []

    first = _attempt_meta(audit, 1)
    assert first["noop_guard"] is True
    second = _attempt_meta(audit, 2)
    assert "ack_guard" not in second
    assert "noop_guard" not in second


def test_no_ai_owned_bodies_skips_the_guard():
    # The demo context has no script bodies, so there is nothing to check an
    # acknowledgment against: it is accepted as the first and only reply.
    provider = MockProvider([ACK_JSON])

    result = Agent(provider, ProjectContext.demo()).handle(REQUEST, request_id=1)

    assert result.attempts == 1
    assert len(provider.calls) == 1
    assert result.compiled.changes == []
