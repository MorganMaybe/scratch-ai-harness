"""Eager context, the cache-stable system prompt and history on follow-ups."""

from __future__ import annotations

import pytest

import harness.eager as eager
from harness.agent import Agent
from harness.context import ProjectContext, ScriptSummary
from harness.eager import eager_sprites, suggest_packs
from harness.history import HEADER, ConversationHistory
from harness.llm import MockLLM, bigger_square_response, draw_square_response
from harness.providers.base import ModelReply
from harness.smalltalk import Sym

PACKS = ("clones", "games", "pen-3d", "scrolling")
TURN_MARKER = "# This turn's project-specific context"


def _context_with_body(name: str = "Sprite1") -> ProjectContext:
    context = ProjectContext.demo()
    context.sprites[name].scripts.append(
        ScriptSummary(
            script_id="ai-1",
            target=name,
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


class _Replies:
    name = "eager-fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return self.replies.pop(0)


def _raw(text: str) -> ModelReply:
    return ModelReply(data={}, raw_text=text, model="fake", finish_reason="stop")


# -- pack routing -------------------------------------------------------------


@pytest.mark.parametrize(
    "request_text, expected",
    [
        ("Draw a square", []),
        ("Make a rotating 3D cube", ["pen-3d"]),
        ("A flappy bird game", ["games"]),
        ("Make a platformer with a score and enemies", ["clones", "games"]),
        ("Add a side-scroller camera", ["scrolling"]),
        ("Make it rain particles", ["clones"]),
        ("3D scrolling clone game", ["pen-3d", "scrolling"]),
    ],
)
def test_suggest_packs_routes_on_wording(request_text, expected):
    assert suggest_packs(request_text, PACKS) == expected


def test_suggest_packs_inherits_the_previous_topic_for_a_bare_follow_up():
    assert suggest_packs(
        "make them faster", PACKS, previous_request="a shooter with bullets"
    ) == ["clones", "games"]
    # A follow-up with its own topic is routed on its own words.
    assert suggest_packs(
        "now a 3d cube", PACKS, previous_request="a shooter with bullets"
    ) == ["pen-3d"]


def test_suggest_packs_only_returns_available_packs():
    assert suggest_packs("a 3d game", ("games",)) == ["games"]


# -- sprite bodies ------------------------------------------------------------


def test_eager_sprites_respects_the_budget_and_priority():
    context = _context_with_body()
    sizes = {"Sprite1": 100}
    assert eager_sprites(context, "x", lambda n: "x" * sizes[n]) == ["Sprite1"]
    assert eager_sprites(
        context, "x", lambda n: "x" * sizes[n], budget_chars=50
    ) == []


def test_eager_turn_includes_bodies_and_skips_the_echo(monkeypatch):
    monkeypatch.delenv("HARNESS_EAGER_CONTEXT", raising=False)
    provider = MockLLM([bigger_square_response("ai-1")])
    agent = Agent(provider, _context_with_body())
    result = agent.handle("Make it jump higher.", request_id=1)
    # One call: no load_sprite round trip and no replace echo.
    assert result.attempts == 1
    system, _ = provider.calls[0]
    assert "# Loaded sprite detail: Sprite1" in system
    assert "Do not load_sprite these sprites" in system
    tail = system.partition(TURN_MARKER)[2]
    assert "Sprite script detail available" not in tail


def test_eager_over_budget_falls_back_to_the_lazy_index(monkeypatch):
    monkeypatch.delenv("HARNESS_EAGER_CONTEXT", raising=False)
    monkeypatch.setattr(eager, "EAGER_DETAIL_CHARS", 10)
    provider = MockLLM([draw_square_response()])
    agent = Agent(provider, _context_with_body())
    agent.handle("Draw a square.", request_id=2)
    system, _ = provider.calls[0]
    assert "# Loaded sprite detail" not in system
    assert "Sprite script detail available" in system.partition(TURN_MARKER)[2]


def test_eager_off_restores_the_lazy_prompt(monkeypatch):
    monkeypatch.setenv("HARNESS_EAGER_CONTEXT", "off")
    provider = MockLLM([draw_square_response()])
    agent = Agent(provider, _context_with_body())
    agent.handle("Make a platformer game with bullets.", request_id=3)
    system, _ = provider.calls[0]
    assert "# Loaded context pack" not in system
    assert "# Loaded sprite detail" not in system


def test_eager_packs_ride_attempt_one(monkeypatch):
    monkeypatch.delenv("HARNESS_EAGER_CONTEXT", raising=False)
    provider = MockLLM([draw_square_response()])
    agent = Agent(provider, ProjectContext.demo())
    result = agent.handle("Make a 3D wireframe cube.", request_id=4)
    assert result.attempts == 1
    system, _ = provider.calls[0]
    assert "# Loaded context pack: pen-3d" in system


# -- cache-stable system prompt ------------------------------------------------


def test_system_prompt_prefix_is_identical_across_projects(monkeypatch):
    monkeypatch.delenv("HARNESS_EAGER_CONTEXT", raising=False)
    first = MockLLM([draw_square_response()])
    Agent(first, ProjectContext.demo()).handle("Draw a square.", request_id=5)
    second = MockLLM([bigger_square_response("ai-1")])
    Agent(second, _context_with_body()).handle(
        "Make a platformer game.", request_id=6
    )
    plain, _ = first.calls[0]
    rich, _ = second.calls[0]
    assert TURN_MARKER not in plain
    prefix, marker, _tail = rich.partition("\n\n" + TURN_MARKER)
    assert marker
    # Packs and bodies are appended; the reference before them is unchanged.
    assert prefix == plain


# -- follow-up prompts keep history and the dialect -----------------------------


SQUARE_DSL = '''```python
summary("Drew a square.")

@on_flag(target="Sprite1", label="draw_square")
def draw_square():
    for _ in range(4):
        move(100)
        turn_right(90)
```'''


def test_dsl_repair_prompt_keeps_the_conversation(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    history = ConversationHistory()
    history.record("Add a red ball", "Added Ball.", "", ["Created sprite Ball"])
    bad = '```python\n@on_flag(target="Sprite1")\ndef f():\n    explode()\n```'
    provider = _Replies([_raw(bad), _raw(SQUARE_DSL)])
    agent = Agent(provider, ProjectContext.demo(), history=history)
    result = agent.handle("make it smaller", request_id=7)
    assert result.attempts == 2
    first = provider.requests[0].user
    repair = provider.requests[1].user
    assert HEADER in first
    assert HEADER in repair
    assert "Add a red ball" in repair
    assert repair.count(HEADER) == 1


def test_dsl_context_loaded_prompt_asks_for_the_dialect(monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    monkeypatch.setenv("HARNESS_EAGER_CONTEXT", "off")
    provider = _Replies(
        [
            ModelReply(
                data={"load_context": ["clones"], "reason": "x"},
                raw_text='{"load_context": ["clones"], "reason": "x"}',
                model="fake",
                finish_reason="stop",
            ),
            _raw(SQUARE_DSL),
        ]
    )
    agent = Agent(provider, ProjectContext.demo())
    agent.handle("Add particles.", request_id=8)
    follow_up = provider.requests[1].user
    assert "JSON change set" not in follow_up
    assert "Scratch-Python module" in follow_up


def test_habitual_load_of_eager_context_is_a_free_pointer(monkeypatch):
    monkeypatch.delenv("HARNESS_EAGER_CONTEXT", raising=False)
    provider = MockLLM(
        [
            {"load_sprite": ["Sprite1"], "reason": "habit"},
            bigger_square_response("ai-1"),
        ]
    )
    # max_repairs=0: the pointer must not need a repair to succeed.
    agent = Agent(provider, _context_with_body(), max_repairs=0)
    result = agent.handle("Make it jump higher.", request_id=9)
    assert result.attempts == 2
    _, second_user = provider.calls[1]
    assert "Already loaded: Sprite1" in second_user


@pytest.mark.parametrize(
    "request_text",
    [
        "A beach with three crabs",
        "add 10 fish swimming around",
        "a night sky full of stars",
        "lots of red balloons floating up",
        "a breakout wall of bricks",
    ],
)
def test_a_crowd_of_one_kind_routes_to_clones(request_text):
    assert "clones" in suggest_packs(request_text, PACKS)


@pytest.mark.parametrize(
    "request_text",
    ["move 10 steps", "make it 3 times bigger", "add 2 cats", "draw a square"],
)
def test_counts_of_units_do_not_route_to_clones(request_text):
    assert "clones" not in suggest_packs(request_text, PACKS)
