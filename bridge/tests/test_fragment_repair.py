"""Fragment-level repair: regenerate only the bad changes, not the whole set."""

from __future__ import annotations

import json

import pytest

from harness.agent import Agent, _fragment_repair_prompt
from harness.audit import AuditSettings, AuditStore
from harness.block_ir import ChangeSet, IRError, parse_changeset_partial
from harness.context import ProjectContext
from harness.providers.base import ModelReply, ProviderError
from harness.validator import ValidationIssue


def _script(label: str, op: str = "pen_clear", args: dict | None = None) -> dict:
    block = {"op": op}
    if args is not None:
        block["args"] = args
    return {
        "action": "add_script",
        "target": "Sprite1",
        "label": label,
        "hat": {"op": "when_flag_clicked"},
        "body": [block],
    }


def _bad_script(label: str = "bad") -> dict:
    return _script(label, op="move_to", args={})


def _fixed_script(label: str = "bad_fixed") -> dict:
    return _script(label, op="move", args={"steps": 10})


_FRAGMENT_NOTE_CASES = [
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

_FRAGMENT_NOTE_PHRASES = sorted({phrase for _, phrase in _FRAGMENT_NOTE_CASES})


def _fragment_prompt(problem: str) -> str:
    return _fragment_repair_prompt(
        "Add two scripts.",
        ProjectContext.demo(),
        [None],
        [0],
        {"changes": [_bad_script("bad")]},
        [ValidationIssue("changes[0]", problem)],
    )


@pytest.mark.parametrize("problem, phrase", _FRAGMENT_NOTE_CASES)
def test_fragment_repair_prompt_includes_the_matching_targeted_note(problem, phrase):
    prompt = _fragment_prompt(problem)

    assert phrase in prompt
    # The JSON contract lines must stay after every note, last in the prompt.
    assert prompt.index(phrase) < prompt.index("Return ONLY a JSON object")
    assert prompt.rstrip().endswith("Use only the block ops in the catalog.")


@pytest.mark.parametrize("problem, phrase", _FRAGMENT_NOTE_CASES)
def test_fragment_repair_note_does_not_fire_another_note(problem, phrase):
    prompt = _fragment_prompt(problem)

    for other in _FRAGMENT_NOTE_PHRASES:
        if other != phrase:
            assert other not in prompt


@pytest.mark.parametrize("phrase", _FRAGMENT_NOTE_PHRASES)
def test_fragment_repair_prompt_omits_notes_for_unrelated_issues(phrase):
    prompt = _fragment_prompt("expected a number, got str")

    assert phrase not in prompt


def test_fragment_repair_prompt_does_not_fire_menu_note_for_a_generic_menu():
    prompt = _fragment_prompt(
        "expected one of all around, left-right, don't rotate, got 'sideways'"
    )

    assert "only accept a sprite that exists at that point" not in prompt


def test_fragment_repair_prompt_with_no_matching_note_keeps_the_contract_neat():
    issue = ValidationIssue("changes[0]", "expected a number, got str")
    prompt = _fragment_repair_prompt(
        "Add two scripts.",
        ProjectContext.demo(),
        [None],
        [0],
        {"changes": [_bad_script("bad")]},
        [issue],
    )

    assert f"- {issue}\n\nReturn ONLY a JSON object:" in prompt


class _SequenceProvider:
    name = "sequence"

    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        if not self.responses:
            raise ProviderError("bad_json", "no responses left")
        return ModelReply(
            data=self.responses.pop(0),
            model="sequence",
            attempts=1,
            finish_reason="stop",
        )


def test_partial_parse_keeps_valid_changes_and_names_the_bad_index():
    data = {
        "summary": "two changes",
        "changes": [
            _script("good"),
            _script("bad", op="pen_clear") | {"PLACEHOLDER": True},
        ],
    }

    result = parse_changeset_partial(data)

    assert result.top_level_error is None
    assert result.problems[0][0] == 1
    assert result.changes[0] is not None
    assert result.changes[1] is None
    with pytest.raises(IRError) as caught:
        ChangeSet.from_dict(data)
    assert "changes[1]" in str(caught.value)


def test_validation_failure_repairs_only_the_failing_change():
    first = {
        "summary": "two scripts",
        "changes": [_script("good"), _bad_script("bad")],
    }
    provider = _SequenceProvider(
        [first, {"changes": [_fixed_script("bad_fixed")]}]
    )
    agent = Agent(provider, ProjectContext.demo(), max_repairs=2)

    result = agent.handle("Add two scripts.", request_id=5)

    assert result.attempts == 2
    assert len(provider.requests) == 2
    assert "exactly 1 corrected change" in provider.requests[1].user
    assert "changes[1]" in provider.requests[1].user
    assert [change.label for change in result.compiled.changes] == [
        "good",
        "bad_fixed",
    ]


def test_parse_failure_repairs_only_the_invalid_change():
    first = {
        "summary": "two scripts",
        "changes": [
            _script("good"),
            _script("bad", op="pen_clear") | {"PLACEHOLDER_PADDLE2": True},
        ],
    }
    provider = _SequenceProvider(
        [first, {"changes": [_fixed_script("bad_fixed")]}]
    )
    agent = Agent(provider, ProjectContext.demo(), max_repairs=2)

    result = agent.handle("Add two scripts.", request_id=6)

    assert result.attempts == 2
    assert "Failing changes (raw JSON)" in provider.requests[1].user
    assert "PLACEHOLDER_PADDLE2" in provider.requests[1].user
    assert len(result.compiled.changes) == 2


def test_fragment_failure_falls_back_to_full_repair():
    first = {
        "summary": "two scripts",
        "changes": [_script("good"), _bad_script("bad")],
    }
    wrong_fragment = {"changes": [_fixed_script("one"), _fixed_script("two")]}
    full_good = {
        "summary": "two scripts",
        "changes": [_script("good"), _fixed_script("bad_fixed")],
    }
    provider = _SequenceProvider([first, wrong_fragment, full_good])
    agent = Agent(provider, ProjectContext.demo(), max_repairs=2)

    result = agent.handle("Add two scripts.", request_id=7)

    assert result.attempts == 3
    assert len(provider.requests) == 3
    assert [change.label for change in result.compiled.changes] == [
        "good",
        "bad_fixed",
    ]


def test_fragment_attempt_is_marked_in_the_audit(tmp_path):
    first = {
        "summary": "two scripts",
        "changes": [_script("good"), _bad_script("bad")],
    }
    provider = _SequenceProvider(
        [first, {"changes": [_fixed_script("bad_fixed")]}]
    )
    store = AuditStore(
        AuditSettings(mode="full", directory=tmp_path / "audit", keep=5)
    )
    audit = store.start_turn(
        request_id=8,
        prompt="Add two scripts.",
        target="Sprite1",
        context=ProjectContext.demo(),
        profile="test",
        model="sequence",
    )
    agent = Agent(provider, ProjectContext.demo(), max_repairs=2, audit=audit)

    result = agent.handle("Add two scripts.", request_id=8)
    audit.finish(
        outcome="ok",
        attempts=result.attempts,
        changes=len(result.compiled.changes),
        elapsed_ms=1,
        result=result,
    )

    meta = json.loads(
        (audit.root / "attempts" / "02" / "meta.json").read_text(encoding="utf-8")
    )
    assert meta["fragment"] is True
    assert meta["fragment_indices"] == [1]
    assert meta["issue_count"] == 0
