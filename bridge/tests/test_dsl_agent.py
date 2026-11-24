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


def test_dsl_ambiguous_plus_repair_quotes_the_line_and_the_rule(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    bad_plus = '''create_variable("first", scope="global", initial=0)
create_variable("last", scope="global", initial=0)

@on_flag(target="Sprite1", label="show_sum")
def show_sum():
    say(first + last)
'''
    provider = _Replies([_raw(bad_plus), _raw(SQUARE_DSL)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    result = agent.handle("Show the sum.", request_id=38)

    assert result.attempts == 2
    repair = provider.requests[1].user
    # The diagnostic now quotes the exact source line, not just its number.
    assert "line 6: say(first + last)" in repair
    assert "'+' between two computed values is ambiguous" in repair
    assert "rewrite `a + b` as `add(a, b)`" in repair
    assert "Do not leave a flagged line unchanged." in repair
    assert "corrected module" in repair


def test_dsl_menu_repair_quotes_the_line_and_names_the_value_rule(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    bad_menu = '''@on_flag(target="Sprite1", label="bad_style")
def bad_style():
    set_rotation_style("sideways")
'''
    provider = _Replies([_raw(bad_menu), _raw(SQUARE_DSL)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    result = agent.handle("Set the style.", request_id=39)

    assert result.attempts == 2
    repair = provider.requests[1].user
    assert 'line 3: set_rotation_style("sideways")' in repair
    assert "must be one of" in repair
    assert "Menu arguments take the exact listed value" in repair
    assert "set_instrument(5)" in repair


def test_dsl_duplicate_name_repair_explains_reuse(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    bad = '''create_variable("score", scope="global", initial=0)
create_variable("score", scope="global", initial=0)

@on_flag(target="Sprite1", label="show_score")
def show_score():
    say(score)
'''
    provider = _Replies([_raw(bad), _raw(SQUARE_DSL)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    result = agent.handle("Show the score.", request_id=40)

    assert result.attempts == 2
    repair = provider.requests[1].user
    assert "line 2: create_variable(\"score\"" in repair
    assert "variable 'score' already exists; reuse it" in repair
    assert "Remove the flagged create_variable/create_list line" in repair


def test_dsl_existing_sprite_repair_explains_set_sprite(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    bad = 'create_sprite("Sprite1", costumes=["Animals/bat1-a.png"])'
    provider = _Replies([_raw(bad), _raw(SQUARE_DSL)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    result = agent.handle("Add a second cat.", request_id=41)

    assert result.attempts == 2
    repair = provider.requests[1].user
    assert "sprite 'Sprite1' already exists" in repair
    assert "Use set_sprite() to change it" in repair


def test_dsl_repairs_exhausted_to_validation_error(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    bad = "import os\n"
    provider = _Replies([_raw(bad), _raw(bad)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    with pytest.raises(ValidationError) as caught:
        agent.handle("Draw a square.", request_id=36)

    assert any("imports are not part of the dialect" in str(issue) for issue in caught.value.issues)
    assert caught.value.attempts == 2


UNKNOWN_CLONE_DSL = '''@on_flag(target="Sprite1", label="spawn")
def spawn():
    create_clone("Ghost")
'''


def test_dsl_parse_repairs_reserve_one_extra_for_validation(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    # Two parse failures spend the whole max_repairs=2 budget, then a parse-clean
    # module fails validation.  That validation failure earns one extra repair.
    provider = _Replies(
        [
            _raw("import os\n"),
            _raw("import sys\n"),
            _raw(UNKNOWN_CLONE_DSL),
            _raw(SQUARE_DSL),
        ]
    )

    agent = Agent(provider, ProjectContext.demo(), max_repairs=2)
    result = agent.handle("Spawn ghosts.", request_id=42)

    assert result.attempts == 4
    assert result.compiled.changes[0].label == "draw_square"
    assert len(provider.requests) == 4


def test_dsl_extra_validation_repair_prompt_quotes_the_change_set(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    provider = _Replies(
        [
            _raw("import os\n"),
            _raw("import sys\n"),
            _raw(UNKNOWN_CLONE_DSL),
            _raw(SQUARE_DSL),
        ]
    )

    agent = Agent(provider, ProjectContext.demo(), max_repairs=2)
    agent.handle("Spawn ghosts.", request_id=43)

    repair = provider.requests[3].user
    assert "Your previous Scratch-Python module could not be used." in repair
    assert "unknown clone target 'Ghost'" in repair
    assert 'create_clone("Ghost")' in repair
    assert "Previous module:" in repair
    assert "corrected module" in repair


def test_dsl_extra_validation_repair_is_granted_only_once(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    # After the extra repair also fails validation, the turn stops instead of
    # granting a second extra.
    provider = _Replies(
        [
            _raw("import os\n"),
            _raw("import sys\n"),
            _raw(UNKNOWN_CLONE_DSL),
            _raw(UNKNOWN_CLONE_DSL),
        ]
    )

    agent = Agent(provider, ProjectContext.demo(), max_repairs=2)
    with pytest.raises(ValidationError) as caught:
        agent.handle("Spawn ghosts.", request_id=44)

    assert caught.value.attempts == 4
    assert len(provider.requests) == 4
    assert any(
        "unknown clone target 'Ghost'" in str(issue)
        for issue in caught.value.issues
    )


def test_dsl_validation_only_repairs_keep_the_normal_cap(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    # Every repair so far is a validation repair, so max_repairs=1 still means
    # two attempts and no extra.
    provider = _Replies([_raw(UNKNOWN_CLONE_DSL), _raw(UNKNOWN_CLONE_DSL)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    with pytest.raises(ValidationError) as caught:
        agent.handle("Spawn ghosts.", request_id=45)

    assert caught.value.attempts == 2
    assert len(provider.requests) == 2
    assert any(
        "unknown clone target 'Ghost'" in str(issue)
        for issue in caught.value.issues
    )


def test_dsl_mode_does_not_fragment_repair(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    provider = _Replies([_raw("this is not python at all\n", model="fake"), _raw(SQUARE_DSL)])

    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    agent.handle("Draw a square.", request_id=37)

    # A DSL rejection must ask for the whole module, never the JSON fragment
    # shape used for one or two bad JSON changes.  The envelope layer turns
    # unparsable prose into its own diagnostic instead of a Python syntax
    # error, so pin the reply-shape message here.
    assert "reply envelope: the reply contains no module" in provider.requests[1].user
    assert "corrected module" in provider.requests[1].user
