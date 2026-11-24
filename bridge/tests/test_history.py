"""Conversation history: the store, the prompt section, and ack-gated recording.

The bridge keeps a bounded, process-local ring of **applied** turns and renders
the last few near-verbatim with older turns compressed to one-liners.  These
tests pin:

* the record shape/caps and the store bound;
* ack-gated recording (a request alone or a failed turn never enters history);
* the H1/H2 trimming stages and the section's own hard cap;
* history-off byte identity, generator neutrality, and the audit metadata;
* ``resolve_history`` precedence;
* lock safety under concurrent sends;
* the ladder's direct ``Agent`` wiring, which records at the same success
  point the server's ``#applied`` acknowledgement uses.
"""

from __future__ import annotations

import threading

import pytest

from harness.agent import Agent
from harness.changeset import CompiledChange, CompiledChangeSet
from harness.config import ConfigError, resolve_history
from harness.context import ProjectContext
from harness.history import (
    MAX_RECORDS,
    MAX_SECTION_CHARS,
    NOTES_MAX_CHARS,
    ONE_LINER_LIMIT,
    OUTLINE_LINE_MAX_CHARS,
    OUTLINE_MAX_LINES,
    REQUEST_MAX_CHARS,
    SUMMARY_MAX_CHARS,
    ConversationHistory,
    render_history,
)
from harness.llm import MockLLM, draw_square_response
from harness.prompts import build_user_prompt, build_user_prompt_with_meta
from harness.server import Bridge
from harness.smalltalk import Sym

ACK_JSON = {
    "summary": "The request is already satisfied.",
    "changes": [],
    "notes": "No changes were needed.",
}


def _record(
    history: ConversationHistory,
    request: str = "make it smaller",
    summary: str = "Shrank the player.",
    notes: str = "",
    outline: tuple[str, ...] = ("Updated script 'play' (2 blocks, id ai-2).",),
    counts: str = "1 script",
) -> None:
    history.record(request, summary, notes, outline, counts)


def _history(count: int, **kwargs) -> ConversationHistory:
    history = ConversationHistory()
    for index in range(count):
        values = dict(kwargs)
        values["request"] = f"{values.get('request', 'make it smaller')} #{index}"
        _record(history, **values)
    return history


def _bridge(responses: list[dict], **kwargs) -> tuple[Bridge, MockLLM]:
    llm = MockLLM(list(responses))
    bridge = Bridge(Agent(llm, ProjectContext.demo()), **kwargs)
    return bridge, llm


# --- the store --------------------------------------------------------------


def test_record_shape_collapses_whitespace_and_applies_caps():
    history = ConversationHistory()
    record = history.record(
        "  make\n it \t smaller  " + "x" * 600,
        "s" * 500,
        "n" * 500,
        ["  line one \n still one ", "line two", "line three", "line four", "line five"],
        "9 sprites",
    )

    assert record.request.startswith("make it smaller ")
    assert len(record.request) <= REQUEST_MAX_CHARS
    assert record.request.endswith("...")
    assert len(record.summary) <= SUMMARY_MAX_CHARS
    assert len(record.notes) <= NOTES_MAX_CHARS
    assert len(record.outline) == OUTLINE_MAX_LINES
    assert record.outline[0] == "line one still one"
    assert all(len(line) <= OUTLINE_LINE_MAX_CHARS for line in record.outline)
    assert record.at  # ISO timestamp, exact zone is not the contract
    assert record.counts == "9 sprites"


def test_store_prunes_oldest_records_at_the_cap():
    history = ConversationHistory(max_records=3)
    for index in range(5):
        _record(history, request=f"request {index}")
    assert len(history) == 3
    assert [record.request for record in history.snapshot()] == [
        "request 2",
        "request 3",
        "request 4",
    ]


def test_default_cap_matches_the_documented_bound():
    assert MAX_RECORDS == 24
    history = ConversationHistory()
    for index in range(MAX_RECORDS + 5):
        _record(history, request=f"request {index}")
    assert len(history) == MAX_RECORDS


def test_record_result_uses_factual_change_lines_and_notes():
    compiled = CompiledChangeSet(
        summary="Made the platforms start lower.",
        changes=[
            CompiledChange(
                action="replace_script",
                script_id="ai-3",
                target="Platform",
                label="spawn",
                block_count=5,
            ),
            CompiledChange(
                action="add_script",
                script_id="ai-4",
                target="Player",
                label="run",
                block_count=12,
            ),
        ],
        notes="Kept the scroll script.",
    )

    class Result:
        pass

    result = Result()
    result.compiled = compiled
    history = ConversationHistory()
    record = history.record_result("start them lower", result)

    assert record is not None
    assert record.summary == "Made the platforms start lower."
    assert record.notes == "Kept the scroll script."
    assert record.outline == (
        "Updated script 'spawn' (5 blocks, id ai-3).",
        "Added script 'run' to Player (12 blocks, id ai-4).",
    )
    assert record.counts == "2 scripts"
    # The raw change set never enters history: no action/body keys survive.
    assert "action" not in record.outline[0]
    assert "body" not in record.outline[0]


def test_record_result_falls_back_to_chat_summary():
    class Compiled:
        summary = "Did a thing."
        notes = "Note."

        def chat_summary(self) -> str:
            return "Did a thing.\nCreated sprite 'Bat' with costumes 'bat1-a'.\nNote."

    class Result:
        compiled = Compiled()

    history = ConversationHistory()
    record = history.record_result("add a bat", Result())
    assert record is not None
    assert record.outline == ("Created sprite 'Bat' with costumes 'bat1-a'.",)
    assert record.counts == "1 sprite"


# --- rendering stages -------------------------------------------------------


def test_render_uses_verbatim_window_then_one_liners():
    history = _history(6)
    text, stats = render_history(history.snapshot())

    assert stats.total == 6
    assert stats.verbatim == 4
    assert stats.turns == 6
    assert stats.dropped == 0
    # Two older turns compressed, four recent turns near-verbatim.
    assert text.count("Assistant:") == 4
    assert text.count('  "make it smaller #') == 2
    assert text.index("make it smaller #0") < text.index("Most recent turns:")
    assert "You: make it smaller #5" in text


def test_render_h1_shrinks_the_verbatim_window_to_two():
    history = _history(6)
    text, stats = render_history(history.snapshot(), verbatim_turns=2)

    assert stats.verbatim == 2
    assert text.count("Assistant:") == 2
    assert text.count('  "make it smaller #') == 4
    assert text.index("make it smaller #3") < text.index("Most recent turns:")


def test_render_h2_drops_oldest_one_liners_before_shrinking_verbatim():
    history = _history(
        10,
        request="r" * 120,
        summary="s" * 80,
        notes="n" * 40,
        outline=("Updated script 'play' (2 blocks, id ai-2).",),
    )
    two_only, _ = render_history(
        history.snapshot(), verbatim_turns=2, one_liner_limit=0
    )
    cap = len(two_only) + 120

    text, stats = render_history(
        history.snapshot(), verbatim_turns=2, one_liner_limit=8, max_chars=cap
    )

    assert len(text) <= cap
    assert stats.verbatim == 2
    assert stats.dropped > 0
    # The oldest compressed turn is the first to go; the newest stays.
    assert f'"{"r" * 120} #0"' not in text
    assert f"You: {'r' * 120} #9" in text


def test_render_hard_cap_holds_for_a_long_store():
    history = _history(
        20,
        request="r" * 350,
        summary="s" * 200,
        notes="n" * 180,
        outline=("l" * 140, "m" * 140, "n" * 140),
    )
    text, stats = render_history(history.snapshot())

    assert len(text) <= MAX_SECTION_CHARS
    assert stats.dropped > 0
    assert stats.verbatim < 4
    assert stats.turns == stats.total - stats.dropped


def test_render_empty_store_is_an_empty_section():
    text, stats = render_history([])
    assert text == ""
    assert stats.total == 0 and stats.turns == 0 and stats.dropped == 0


# --- prompts ----------------------------------------------------------------


def test_prompt_section_sits_between_request_and_project_context():
    history = _history(2)
    prompt, meta = build_user_prompt_with_meta(
        "now make it smaller again", ProjectContext.demo(), history=history
    )

    assert meta["level"] == 0
    assert meta["history_turns"] == 2
    assert meta["history_verbatim"] == 2
    assert meta["history_chars"] == len(render_history(history.snapshot())[0])
    assert meta["history_dropped"] == 0
    assert (
        prompt.index("now make it smaller again")
        < prompt.index("Conversation so far")
        < prompt.index("Project context:")
    )
    # The caveat line is always present: history is memory, not state.
    assert "authoritative - undo and manual edits" in prompt
    assert "Assistant: Shrank the player." in prompt
    assert "Updated script 'play'" in prompt


def test_empty_history_leaves_the_prompt_byte_identical():
    context = ProjectContext.demo()
    plain = build_user_prompt("Draw a square.", context)
    empty = build_user_prompt("Draw a square.", context, history=ConversationHistory())
    assert plain == empty
    assert "Conversation so far" not in plain
    _, meta = build_user_prompt_with_meta(
        "Draw a square.", context, history=ConversationHistory()
    )
    assert meta["history_turns"] == 0
    assert meta["history_chars"] == 0
    assert meta["history_dropped"] == 0


def test_history_section_is_generator_neutral():
    history = _history(2)
    context = ProjectContext.demo()
    json_prompt = build_user_prompt("make it smaller", context, history=history)
    dsl_prompt = build_user_prompt(
        "make it smaller", context, generator="dsl", history=history
    )

    def section(prompt: str) -> str:
        start = prompt.index("Conversation so far")
        end = prompt.index("\n\nProject context:")
        return prompt[start:end]

    assert section(json_prompt) == section(dsl_prompt)
    assert "Conversation so far" in dsl_prompt
    assert "Return the Scratch-Python module now" in dsl_prompt


def test_prompt_ladder_uses_h1_when_the_full_verbatim_window_does_not_fit():
    context = ProjectContext.demo()
    history = _history(
        6,
        request="r" * 150,
        summary="s" * 100,
        notes="",
        outline=("Updated script 'play' (2 blocks, id ai-2).",),
    )
    records = history.snapshot()
    first_text, _ = render_history(records, verbatim_turns=4)
    second_text, _ = render_history(records, verbatim_turns=2)
    base = len(build_user_prompt("make it smaller", context))
    budget = base + len(second_text) + 2

    prompt, meta = build_user_prompt_with_meta(
        "make it smaller", context, budget_chars=budget, history=history
    )

    assert len(prompt) <= budget
    assert len(first_text) > len(second_text)
    assert meta["level"] == 0
    assert meta["history_verbatim"] == 2


def test_prompt_ladder_h2_drops_oldest_one_liners_before_context():
    context = ProjectContext.demo()
    history = _history(
        8,
        request="r" * 60,
        summary="s" * 60,
        outline=("o" * 40,),
    )
    records = history.snapshot()
    _, h1_stats = render_history(records, verbatim_turns=2)
    h2_text, _ = render_history(records, verbatim_turns=2, one_liner_limit=2)
    base = len(build_user_prompt("now go", context))
    budget = base + len(h2_text) + 2

    prompt, meta = build_user_prompt_with_meta(
        "now go", context, budget_chars=budget, history=history
    )

    assert len(prompt) <= budget
    assert meta["level"] == 0
    assert meta["history_verbatim"] == 2
    assert meta["history_turns"] < h1_stats.turns
    # The oldest compressed turns were dropped; the newest compressed one and
    # the verbatim window survive.
    assert f'"{"r" * 60} #0"' not in prompt
    assert f'"{"r" * 60} #1"' not in prompt
    assert f'"{"r" * 60} #5"' in prompt
    assert f"You: {'r' * 60} #7" in prompt


def test_hard_fit_drops_history_before_the_targeting_surface():
    from harness.context import ScriptSummary, SpriteContext

    context = ProjectContext(
        target="Sprite1",
        sprites={
            "Sprite1": SpriteContext(
                name="Sprite1",
                scripts=[
                    ScriptSummary(
                        script_id="ai-1",
                        target="Sprite1",
                        label="draw_square",
                        hat="when_flag_clicked",
                        block_count=5,
                        owned=True,
                    )
                ],
            )
        },
    )
    history = _history(6, request="r" * 300, summary="s" * 200)
    prompt, meta = build_user_prompt_with_meta(
        "x" * 400, context, budget_chars=900, history=history
    )

    assert len(prompt) <= 900
    assert "Target: Sprite1" in prompt
    assert "ai-1" in prompt
    assert "Conversation so far" not in prompt
    assert meta["level"] == 3
    assert meta["truncated"] is True
    assert meta["history_turns"] == 0
    assert meta["history_dropped"] == len(history)


# --- ack-gated recording through the bridge --------------------------------


def test_applied_turn_reaches_the_next_prompt():
    bridge, llm = _bridge(
        [draw_square_response(), ACK_JSON], history_enabled=True
    )

    first = bridge.handle(
        [Sym("request"), 1, ["Draw a square."], "Sprite1"]
    )[0]
    assert first[0] == Sym("result")
    assert "Conversation so far" not in llm.calls[0][1]
    assert len(bridge.history) == 0

    assert bridge.handle([Sym("applied"), 1]) == [[Sym("ok"), 1]]
    assert len(bridge.history) == 1

    second = bridge.handle(
        [Sym("request"), 2, ["make it smaller"], "Sprite1"]
    )[0]
    assert second[0] == Sym("result")
    prompt = llm.calls[1][1]
    assert "Conversation so far" in prompt
    assert "You: Draw a square." in prompt
    assert "Assistant: Added a green-flag square-drawing script." in prompt
    assert "Added script 'draw_square' to Sprite1" in prompt


def test_unacked_and_unknown_applied_do_not_record():
    bridge, _ = _bridge([draw_square_response()], history_enabled=True)

    bridge.handle([Sym("request"), 1, ["Draw a square."], "Sprite1"])
    assert len(bridge.history) == 0

    # An #applied for an unknown/expired id is acknowledged but records nothing.
    assert bridge.handle([Sym("applied"), 999]) == [[Sym("ok"), 999]]
    assert len(bridge.history) == 0


def test_failed_turn_never_records():
    bridge, _ = _bridge([], history_enabled=True)

    response = bridge.handle(
        [Sym("request"), 1, ["Draw a square."], "Sprite1"]
    )[0]
    assert response[0] == Sym("error")
    assert 1 not in bridge.pending
    assert len(bridge.history) == 0


def test_acknowledgment_turn_is_recorded_without_outline():
    bridge, _ = _bridge([ACK_JSON], history_enabled=True)

    bridge.handle([Sym("request"), 1, ["make it lower"], "Sprite1"])
    bridge.handle([Sym("applied"), 1])

    record = bridge.history.snapshot()[0]
    assert record.request == "make it lower"
    assert record.summary == "The request is already satisfied."
    assert record.notes == "No changes were needed."
    assert record.outline == ()
    assert record.counts == ""


def test_history_off_records_nothing_and_prompts_stay_plain():
    bridge, llm = _bridge(
        [draw_square_response(), ACK_JSON], history_enabled=False
    )

    bridge.handle([Sym("request"), 1, ["Draw a square."], "Sprite1"])
    bridge.handle([Sym("applied"), 1])
    bridge.handle([Sym("request"), 2, ["make it smaller"], "Sprite1"])

    assert len(bridge.history) == 0
    assert all("Conversation so far" not in user for _, user in llm.calls)


def test_agent_direct_wiring_renders_history_for_the_ladder():
    context = ProjectContext.demo()
    history = _history(1)
    llm = MockLLM([draw_square_response()])

    Agent(llm, context, history=history).handle("add a square", 1)

    assert "Conversation so far" in llm.calls[0][1]
    assert "Assistant: Shrank the player." in llm.calls[0][1]


# --- switch and concurrency -------------------------------------------------


def test_resolve_history_defaults_on(tmp_path):
    assert resolve_history(tmp_path / "missing.ini", env={}) is True


def test_resolve_history_reads_the_harness_section(tmp_path):
    path = tmp_path / "harness.ini"
    path.write_text("[harness]\nhistory=off\n", encoding="utf-8")
    assert resolve_history(path, env={}) is False


def test_resolve_history_env_wins_over_ini(tmp_path):
    path = tmp_path / "harness.ini"
    path.write_text("[harness]\nhistory=off\n", encoding="utf-8")
    assert resolve_history(path, env={"HARNESS_HISTORY": "on"}) is True
    assert resolve_history(path, env={"HARNESS_HISTORY": " OFF "}) is False
    # Blank env falls through to the file.
    assert resolve_history(path, env={"HARNESS_HISTORY": "  "}) is False


@pytest.mark.parametrize("value", ["yes", "true", "1", "sometimes"])
def test_resolve_history_rejects_unknown_values(tmp_path, value):
    with pytest.raises(ConfigError):
        resolve_history(tmp_path / "missing.ini", env={"HARNESS_HISTORY": value})
    path = tmp_path / "harness.ini"
    path.write_text(f"[harness]\nhistory={value}\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        resolve_history(path, env={})


def test_store_is_safe_under_concurrent_record_and_snapshot():
    history = ConversationHistory(max_records=16)
    errors: list[BaseException] = []

    def writer(prefix: str) -> None:
        try:
            for index in range(200):
                _record(history, request=f"{prefix} {index}")
        except BaseException as exc:  # pragma: no cover - only on a real bug
            errors.append(exc)

    def reader() -> None:
        try:
            for _ in range(400):
                snapshot = history.snapshot()
                render_history(snapshot)
        except BaseException as exc:  # pragma: no cover - only on a real bug
            errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=("a",)),
        threading.Thread(target=writer, args=("b",)),
        threading.Thread(target=reader),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(history) == 16
