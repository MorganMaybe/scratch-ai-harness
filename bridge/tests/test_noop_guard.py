"""The no-op replace guard: a deterministic backstop against echo revisions.

The bridge holds the exact current body of every AI-owned script whose native
tuples the image sent.  A ``replace_script`` whose hat, body and label match
that body byte-for-byte cannot change the project, so the bridge classifies it
as a no-op instead of narrating it as a change:

* a fully no-op turn gets one guard round trip naming two honest outs (make the
  real change, or acknowledge the request is already satisfied);
* a mixed turn has its no-ops stripped with one warning each and applies the
  real rest without an extra model call;
* anything the bridge cannot decompile exactly fails open.
"""

from __future__ import annotations

import json

import pytest

from harness.agent import Agent
from harness.audit import AuditSettings, AuditStore
from harness.block_ir import ChangeSet, parse_changeset_partial
from harness.changeset import compile_changeset
from harness.context import ProjectContext, ScriptSummary
from harness.dsl import DSLErrors, transpile
from harness.llm import draw_square_response
from harness.providers.mock import MockProvider
from harness.smalltalk import Sym
from harness.validator import validate_changeset

ACK_SUMMARY = "The bounce script already does what the request asks."
ACK_NOTES = "No changes were needed."

#: An acknowledgment in both reply shapes the bridge accepts.
ACK_JSON = {
    "summary": ACK_SUMMARY,
    "changes": [],
    "notes": ACK_NOTES,
}
ACK_DSL = f'summary("{ACK_SUMMARY}")\nnotes("{ACK_NOTES}")\n'

#: Replaces ``ai-1`` with exactly the blocks and label it already has.
IDENTICAL_JSON = {
    "summary": "The platforms start lower now.",
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

#: The same replacement in the dialect, for the DSL-mode turn.
IDENTICAL_DSL = '''@on_flag(target="Sprite1", label="bounce", script_id="ai-1")
def bounce():
    move(10)
'''

#: The same blocks, but a new label: a real rename, not a no-op.
RENAME_JSON = {
    "summary": "Renamed the script.",
    "changes": [
        {
            "action": "replace_script",
            "script_id": "ai-1",
            "target": "Sprite1",
            "label": "bounce_higher",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "move", "args": {"steps": 10}}],
        }
    ],
}

#: A genuine body change; the resubmission is blind, so the echo may follow.
REAL_REPLACE = {
    "summary": "Made the bounce bigger.",
    "changes": [
        {
            "action": "replace_script",
            "script_id": "ai-1",
            "target": "Sprite1",
            "label": "bounce",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "move", "args": {"steps": 200}}],
        }
    ],
}

#: A real change of another kind, which no replace guard or echo touches.
REAL_ADD = draw_square_response()


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


def _turn(tmp_path, context: ProjectContext, request_id: int = 1):
    store = AuditStore(
        AuditSettings(mode="full", directory=tmp_path / "audit", keep=10)
    )
    return store.start_turn(
        request_id=request_id,
        prompt="Make the platform start lower.",
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


# --- behavior A: a fully no-op turn ---------------------------------------


def test_fully_noop_replace_gets_one_guard_round_trip(tmp_path):
    context = _context_with_body()
    audit = _turn(tmp_path, context)
    assert audit is not None
    provider = MockProvider([IDENTICAL_JSON, ACK_JSON])
    agent = Agent(provider, context, audit=audit)

    result = agent.handle("Make the platform start lower.", request_id=1)

    assert result.attempts == 2
    assert len(provider.calls) == 2
    guard = provider.calls[1].user
    # Current body, the identical-submission statement, and both outs.
    assert '"hat":{"op":"when_flag_clicked"}' in guard
    assert '"steps":10' in guard
    assert "identical to the current" in guard
    assert "would change nothing" in guard
    assert "1. Make the change the request actually asks for" in guard
    assert "2. If the request is already satisfied" in guard
    assert (
        '{"summary": "...", "changes": [], "notes": "..."}' in guard
    )
    assert "Make the platform start lower." in guard
    assert "Target: Sprite1" in guard
    assert provider.calls[1].reply_format == "json"

    first = _attempt_meta(audit, 1)
    assert first["noop_guard"] is True
    assert first["noop_sprites"] == ["Sprite1"]
    assert "noop_guard" not in _attempt_meta(audit, 2)


@pytest.mark.parametrize(
    "generator,ack",
    [("json", ACK_JSON), ("dsl", ACK_DSL)],
    ids=["json", "dsl"],
)
def test_acknowledgment_after_the_guard_applies_nothing(
    monkeypatch, generator, ack
):
    monkeypatch.setenv("HARNESS_GENERATOR", generator)
    monkeypatch.setenv("HARNESS_PROMPT_BUDGET", "400000")
    first = IDENTICAL_DSL if generator == "dsl" else IDENTICAL_JSON
    provider = MockProvider([first, ack])
    context = _context_with_body()

    result = Agent(provider, context).handle(
        "Make the platform start lower.", request_id=2
    )

    assert result.attempts == 2
    assert len(provider.calls) == 2
    guard = provider.calls[1].user
    assert "Choose one:" in guard
    if generator == "dsl":
        assert 'summary("...") and notes("...")' in guard
        assert "no defs" in guard
        assert "move(10)" in guard
    else:
        assert '{"summary": "...", "changes": [], "notes": "..."}' in guard
        assert '"steps":10' in guard
    assert result.changeset.changes == []
    assert result.compiled.changes == []
    # The acknowledgment still reaches the chat: the summary is the turn text.
    assert ACK_SUMMARY in result.compiled.chat_summary()
    assert ACK_NOTES in result.compiled.chat_summary()
    assert result.compiled.apply_structure(2)[2] == []


def test_guard_resubmission_with_a_real_change_is_applied():
    context = _context_with_body()
    provider = MockProvider([IDENTICAL_JSON, REAL_ADD])

    result = Agent(provider, context).handle(
        "Make the platform start lower.", request_id=3
    )

    assert result.attempts == 2
    assert len(provider.calls) == 2
    assert len(result.compiled.changes) == 1
    assert result.compiled.changes[0].action == "add_script"
    assert "Added script 'draw_square'" in result.compiled.chat_summary()


def test_a_second_noop_is_stripped_with_a_warning_and_no_second_guard(
    tmp_path,
):
    context = _context_with_body()
    audit = _turn(tmp_path, context)
    provider = MockProvider([IDENTICAL_JSON, IDENTICAL_JSON])

    result = Agent(provider, context, audit=audit).handle(
        "Make the platform start lower.", request_id=4
    )

    assert result.attempts == 2
    assert len(provider.calls) == 2
    assert result.compiled.changes == []
    assert result.lint_warnings == [
        "script 'bounce' (Sprite1): replacement identical to the current"
        " script - nothing changed"
    ]
    # The second reply is a no-op again; it is stripped, not guarded again.
    assert "noop_guard" not in _attempt_meta(audit, 2)


# --- behavior B: a mixed turn ---------------------------------------------


def test_mixed_turn_strips_the_noop_and_applies_the_rest():
    context = _context_with_body()
    add_square = draw_square_response()["changes"][0]
    provider = MockProvider(
        [
            {
                "summary": "Moved the platform and added a square.",
                "changes": [IDENTICAL_JSON["changes"][0], add_square],
                "notes": "Both changes in one turn.",
            }
        ]
    )

    result = Agent(provider, context).handle(
        "Move the platform and draw a square.", request_id=5
    )

    assert result.attempts == 1
    assert len(provider.calls) == 1
    assert [change.action for change in result.compiled.changes] == [
        "add_script"
    ]
    assert len(result.changeset.changes) == 1
    assert result.changeset.summary == "Moved the platform and added a square."
    assert result.lint_warnings == [
        "script 'bounce' (Sprite1): replacement identical to the current"
        " script - nothing changed"
    ]


@pytest.mark.usefixtures("lazy_context")
def test_mixed_turn_still_echoes_a_blind_real_replace():
    context = _context_with_body()
    provider = MockProvider(
        [
            {
                "summary": "Moved the platform and changed the bounce.",
                "changes": [
                    IDENTICAL_JSON["changes"][0],
                    {
                        "action": "replace_script",
                        "script_id": "ai-1",
                        "target": "Sprite1",
                        "label": "bounce",
                        "hat": {"op": "when_flag_clicked"},
                        "body": [{"op": "move", "args": {"steps": 200}}],
                    },
                ],
            },
            REAL_REPLACE,
        ]
    )

    result = Agent(provider, context).handle(
        "Move the platform and change the bounce.", request_id=6
    )

    assert result.attempts == 2
    resend = provider.calls[1].user
    assert "Current bodies of the script(s) you are about to replace:" in resend
    assert '"steps":10' in resend
    assert result.compiled.changes[0].action == "replace_script"


# --- the guard stays quiet -------------------------------------------------


def test_label_only_rename_is_a_real_change():
    context = _context_with_body()
    provider = MockProvider(
        [{"load_sprite": ["Sprite1"], "reason": "rename it"}, RENAME_JSON]
    )

    result = Agent(provider, context).handle(
        "Rename the bounce script.", request_id=7
    )

    assert result.attempts == 2
    assert len(provider.calls) == 2
    assert result.compiled.changes[0].action == "replace_script"
    assert result.compiled.changes[0].label == "bounce_higher"
    assert "Choose one:" not in provider.calls[1].user


def test_unknown_block_in_the_current_body_fails_open():
    context = _context_with_body(
        tuples=[
            [Sym("EventHatMorph"), "Scratch-StartClicked"],
            [Sym("mysteryOp:"), 5],
        ]
    )
    provider = MockProvider(
        [{"load_sprite": ["Sprite1"], "reason": "inspect it"}, REAL_REPLACE]
    )

    result = Agent(provider, context).handle(
        "Make the bounce bigger.", request_id=8
    )

    assert result.attempts == 2
    assert len(provider.calls) == 2
    assert result.compiled.changes[0].action == "replace_script"
    assert "Choose one:" not in provider.calls[1].user


def test_no_guard_when_the_replaced_script_has_no_tuples():
    context = _context_with_body()
    context.sprites["Sprite1"].scripts[0].tuples = None
    provider = MockProvider([IDENTICAL_JSON])

    result = Agent(provider, context).handle(
        "Make the platform start lower.", request_id=9
    )

    assert result.attempts == 1
    assert len(provider.calls) == 1
    assert result.compiled.changes[0].action == "replace_script"
    assert result.lint_warnings == []


# --- the acknowledgment path is legal end to end --------------------------


def test_json_empty_changes_acknowledgment_is_legal():
    context = _context_with_body()
    parsed = parse_changeset_partial(ACK_JSON)

    assert parsed.top_level_error is None
    assert parsed.problems == []
    changeset = ChangeSet(
        summary=parsed.summary,
        changes=[change for change in parsed.changes if change is not None],
        notes=parsed.notes,
    )
    assert validate_changeset(changeset, context) == []
    compiled = compile_changeset(changeset, context)
    assert compiled.changes == []
    assert compiled.apply_structure(10)[2] == []
    assert ACK_SUMMARY in compiled.chat_summary()
    assert ACK_NOTES in compiled.chat_summary()


def test_dsl_summary_only_module_is_an_acknowledgment():
    changeset = transpile(ACK_DSL)

    assert changeset.changes == []
    assert changeset.summary == ACK_SUMMARY
    assert changeset.notes == ACK_NOTES


def test_dsl_truly_empty_module_still_reports_empty():
    with pytest.raises(DSLErrors) as caught:
        transpile("")

    assert "change set is empty" in caught.value.errors[0].format()
