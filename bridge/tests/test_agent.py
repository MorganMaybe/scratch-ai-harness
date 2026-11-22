from __future__ import annotations

import pytest

from harness.agent import Agent, _repair_prompt
from harness.context import ProjectContext
from harness.llm import MockLLM, bigger_square_response, draw_square_response
from harness.protocol import Sym, parse_literal
from harness.providers.base import ModelReply, ProviderError
from harness.validator import ValidationError, ValidationIssue


def test_agent_draw_square():
    context = ProjectContext.demo()
    agent = Agent(MockLLM([draw_square_response()]), context)
    result = agent.handle("Make the cat draw a square.", request_id=7)
    assert result.request_id == 7
    assert result.attempts == 1
    assert "Added script 'draw_square'" in result.compiled.chat_summary()
    message = parse_literal(result.apply_literal)
    assert message[0] == Sym("apply")
    assert message[1] == 7
    assert len(result.compiled.changes) == 1


def test_agent_replace_after_register():
    context = ProjectContext.demo()
    agent = Agent(MockLLM([draw_square_response(), bigger_square_response("ai-1")]), context)
    first = agent.handle("Draw a square.", 1)
    agent.register_applied(first)
    assert "ai-1" in agent.registry
    second = agent.handle("Make it bigger and say Done!", 2)
    assert second.compiled.changes[0].action == "replace_script"
    assert second.compiled.changes[0].script_id == "ai-1"
    assert "Updated script 'draw_square'" in second.compiled.chat_summary()


def test_agent_repairs_invalid_response():
    context = ProjectContext.demo()
    invalid = {
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
    agent = Agent(MockLLM([invalid, draw_square_response()]), context, max_repairs=1)
    result = agent.handle("Draw a square.", 1)
    assert result.attempts == 2
    assert result.compiled.changes[0].script_id == "ai-1"


def test_repair_prompt_calls_out_output_budget_exhaustion():
    issues = [
        ValidationIssue(
            "json",
            "model returned invalid JSON (finish_reason=length, output budget exhausted)",
        )
    ]

    prompt = _repair_prompt("Build a large scene.", ProjectContext.demo(), None, issues)

    assert "ran out of output tokens" in prompt
    assert "smaller change set" in prompt


def test_repair_prompt_calls_out_hidden_reasoning_budget_use():
    issues = [
        ValidationIssue(
            "json",
            "the model returned an empty response (finish_reason=length, output budget "
            "exhausted); 16384 tokens went to hidden reasoning before any JSON",
        )
    ]

    prompt = _repair_prompt("Build a large scene.", ProjectContext.demo(), None, issues)

    assert "Hidden reasoning consumed the output budget" in prompt
    assert "no step-by-step planning" in prompt
    assert "very large scenes will not fit" in prompt


def test_repair_prompt_omits_hidden_reasoning_passage_without_that_issue():
    issues = [
        ValidationIssue(
            "json",
            "model returned invalid JSON (finish_reason=length, output budget exhausted)",
        )
    ]

    prompt = _repair_prompt("Build a large scene.", ProjectContext.demo(), None, issues)

    assert "Hidden reasoning consumed the output budget" not in prompt
    assert "very large scenes will not fit" not in prompt


def test_repair_prompt_calls_out_missing_media():
    issues = [
        ValidationIssue(
            "changes[6].costumes[0].library",
            "unknown costume 'Nature/grass1.png': 'Nature' is a backdrop category",
        )
    ]

    prompt = _repair_prompt("Build a scrolling scene.", ProjectContext.demo(), None, issues)

    assert "media library is strict" in prompt
    assert "Do not invent a path" in prompt
    assert "if the file is missing" in prompt


_REPAIR_NOTE_CASES = [
    (
        "unknown variable 'lives'; add a create_variable change first",
        "Check whose variable it is",
    ),
    (
        "sprite-scoped variable requires a valid target",
        "needs a target naming a sprite",
    ),
    ("unknown argument 'delta'", "do not drop the movement"),
    ("missing argument 'dx'", "do not drop the movement"),
    ("missing argument 'dy'", "do not drop the movement"),
    (
        "unknown target sprite/stage: 'Ghost'",
        "Every target must exist when its change runs",
    ),
    (
        "unknown sprite 'Ghost'; this menu accepts a sprite that exists at this "
        "point in the change set (create it earlier), or one of mouse-pointer, "
        "edge, Stage",
        "only accept a sprite that exists at that point",
    ),
    ("'change_x' cannot be used on 'Stage'", "stage-safe equivalents"),
    (
        "unknown block fields ['wait'] on block 'if'; a nested block belongs in "
        "the body list (or then/else), not as a named field",
        "never a named field",
    ),
]

_REPAIR_NOTE_PHRASES = sorted({phrase for _, phrase in _REPAIR_NOTE_CASES})


def _issue(problem: str) -> ValidationIssue:
    return ValidationIssue("changes[0]", problem)


@pytest.mark.parametrize("problem, phrase", _REPAIR_NOTE_CASES)
def test_repair_prompt_includes_the_matching_targeted_note(problem, phrase):
    prompt = _repair_prompt(
        "Do the thing.", ProjectContext.demo(), None, [_issue(problem)]
    )

    assert phrase in prompt


@pytest.mark.parametrize("problem, phrase", _REPAIR_NOTE_CASES)
def test_repair_note_does_not_fire_another_note(problem, phrase):
    prompt = _repair_prompt(
        "Do the thing.", ProjectContext.demo(), None, [_issue(problem)]
    )

    for other in _REPAIR_NOTE_PHRASES:
        if other != phrase:
            assert other not in prompt


@pytest.mark.parametrize("phrase", _REPAIR_NOTE_PHRASES)
def test_repair_prompt_omits_notes_for_unrelated_issues(phrase):
    prompt = _repair_prompt(
        "Do the thing.",
        ProjectContext.demo(),
        None,
        [_issue("expected a number, got str")],
    )

    assert phrase not in prompt


def test_repair_prompt_does_not_fire_menu_note_for_a_generic_menu():
    prompt = _repair_prompt(
        "Do the thing.",
        ProjectContext.demo(),
        None,
        [_issue("expected one of all around, left-right, don't rotate, got 'sideways'")],
    )

    assert "only accept a sprite that exists at that point" not in prompt


def test_repair_prompt_with_no_matching_note_keeps_the_original_layout():
    issue = _issue("expected a number, got str")
    prompt = _repair_prompt("Do the thing.", ProjectContext.demo(), None, [issue])

    assert f"- {issue}\n\nReturn a corrected JSON change set only." in prompt


def test_agent_fails_after_repairs():
    context = ProjectContext.demo()
    invalid = {
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
    agent = Agent(MockLLM([invalid, invalid]), context, max_repairs=1)
    with pytest.raises(ValidationError):
        agent.handle("Draw a square.", 1)


class _BadJsonThenGood:
    name = "fake"

    def __init__(self, payload, error: ProviderError | None = None):
        self.payload = payload
        self.error = error or ProviderError("bad_json", "model returned invalid JSON: test")
        self.calls = 0
        self.requests = []

    def complete(self, request):
        self.calls += 1
        self.requests.append(request)
        if self.calls == 1:
            raise self.error
        return ModelReply(data=self.payload, model="fake", attempts=1)


class _AlwaysBad:
    name = "fake"

    def __init__(self, error: ProviderError | None = None):
        self.error = error or ProviderError("bad_json", "model returned an empty response")
        self.calls = 0

    def complete(self, request):
        self.calls += 1
        raise self.error


class _AuthFail:
    name = "fake"

    def __init__(self):
        self.calls = 0

    def complete(self, request):
        self.calls += 1
        raise ProviderError("auth", "the endpoint rejected the API key")


def test_agent_repairs_bad_json():
    provider = _BadJsonThenGood(draw_square_response())
    agent = Agent(provider, ProjectContext.demo())
    result = agent.handle("Draw a square.", 1)
    assert result.attempts == 2
    assert provider.calls == 2
    assert "Added script 'draw_square'" in result.compiled.chat_summary()


def test_agent_gives_up_after_bad_json_repairs():
    provider = _AlwaysBad()
    agent = Agent(provider, ProjectContext.demo(), max_repairs=2)
    with pytest.raises(ValidationError) as exc:
        agent.handle("Draw a square.", 1)
    assert provider.calls == 3
    assert any("json" in str(issue) for issue in exc.value.issues)


def test_agent_bad_json_issue_names_hidden_reasoning_tokens():
    provider = _AlwaysBad(
        ProviderError(
            "bad_json",
            "the model returned an empty response",
            finish_reason="length",
            reasoning_tokens=16384,
        )
    )
    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)

    with pytest.raises(ValidationError) as exc:
        agent.handle("Draw a square.", 1)

    issues = "\n".join(str(issue) for issue in exc.value.issues)
    assert "hidden reasoning" in issues
    assert "16384 tokens went to hidden reasoning before any JSON" in issues
    # The existing finish_reason text is still there.
    assert "finish_reason=length, output budget exhausted" in issues


def test_agent_repair_prompt_gets_hidden_reasoning_note():
    provider = _BadJsonThenGood(
        draw_square_response(),
        ProviderError(
            "bad_json",
            "the model returned an empty response",
            finish_reason="length",
            reasoning_tokens=16384,
        ),
    )
    agent = Agent(provider, ProjectContext.demo())

    result = agent.handle("Draw a square.", 1)

    assert result.attempts == 2
    repair_user = provider.requests[1].user
    assert "16384 tokens went to hidden reasoning before any JSON" in repair_user
    assert "Hidden reasoning consumed the output budget" in repair_user
    assert "very large scenes will not fit" in repair_user


@pytest.mark.parametrize("reasoning_tokens", [None, 0])
def test_agent_bad_json_without_reasoning_tokens_keeps_previous_text(reasoning_tokens):
    provider = _BadJsonThenGood(
        draw_square_response(),
        ProviderError(
            "bad_json",
            "the model returned an empty response",
            finish_reason="length",
            reasoning_tokens=reasoning_tokens,
        ),
    )
    agent = Agent(provider, ProjectContext.demo())

    agent.handle("Draw a square.", 1)

    repair_user = provider.requests[1].user
    assert (
        "the model returned an empty response (finish_reason=length, output budget exhausted)"
        in repair_user
    )
    assert "hidden reasoning" not in repair_user
    assert "Hidden reasoning consumed the output budget" not in repair_user


def test_agent_does_not_repair_auth_errors():
    provider = _AuthFail()
    agent = Agent(provider, ProjectContext.demo())
    with pytest.raises(ProviderError) as exc:
        agent.handle("Draw a square.", 1)
    assert exc.value.code == "auth"
    assert provider.calls == 1
