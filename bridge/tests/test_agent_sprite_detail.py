from __future__ import annotations

import pytest

import re

from harness.agent import Agent
from harness.context import ProjectContext, ScriptSummary
from harness.llm import MockLLM, draw_square_response
from harness.smalltalk import Sym



pytestmark = pytest.mark.usefixtures("lazy_context")

def context_with_detail(*, user_script: bool = False) -> ProjectContext:
    context = ProjectContext.demo()
    context.sprites["Sprite1"].scripts.append(
        ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label="bounce",
            hat="EventHatMorph",
            block_count=2,
            owned=not user_script,
            tuples=(
                None
                if user_script
                else [
                    [Sym("EventHatMorph"), "Scratch-StartClicked"],
                    [Sym("forward:"), 10],
                ]
            ),
        )
    )
    return context


def test_agent_lazy_loads_sprite_detail():
    provider = MockLLM(
        [
            {"load_sprite": ["Sprite1"], "reason": "need the bounce body"},
            draw_square_response(),
        ]
    )
    agent = Agent(provider, context_with_detail())
    result = agent.handle("Make it bounce faster.", request_id=21)
    assert result.attempts == 2
    first_system, _ = provider.calls[0]
    second_system, second_user = provider.calls[1]
    assert "# Loaded sprite detail: Sprite1" not in first_system
    assert "Sprite script detail available" in first_system
    assert "# Loaded sprite detail: Sprite1" in second_system
    assert '"op":"when_flag_clicked"' in second_system
    assert "forward" in second_system
    assert "now included in the system prompt" in second_user
    assert "sprite detail: Sprite1" in second_user


def test_agent_repairs_unknown_sprite_detail():
    provider = MockLLM(
        [
            {"load_sprite": ["Missing"]},
            draw_square_response(),
        ]
    )
    agent = Agent(provider, context_with_detail(), max_repairs=1)
    result = agent.handle("Revise it.", request_id=22)
    assert result.attempts == 2
    _, second_user = provider.calls[1]
    assert "unknown sprite" in second_user
    assert "Sprite1" in second_user


def test_agent_repairs_sprite_with_no_editable_scripts():
    provider = MockLLM(
        [
            {"load_sprite": ["Sprite1"]},
            draw_square_response(),
        ]
    )
    agent = Agent(provider, context_with_detail(user_script=True), max_repairs=1)
    result = agent.handle("Revise it.", request_id=23)
    assert result.attempts == 2
    _, second_user = provider.calls[1]
    assert "no editable script detail" in second_user


def test_agent_does_not_load_same_sprite_twice():
    provider = MockLLM(
        [
            {"load_sprite": ["Sprite1"]},
            {"load_sprite": ["sprite1"]},
            draw_square_response(),
        ]
    )
    agent = Agent(provider, context_with_detail(), max_repairs=2)
    result = agent.handle("Revise it.", request_id=24)
    assert result.attempts == 3
    third_system, third_user = provider.calls[2]
    assert "already loaded" in third_user
    assert third_system.count("# Loaded sprite detail: Sprite1") == 1


def test_agent_rejects_load_sprite_plus_changes():
    provider = MockLLM(
        [
            {
                "load_sprite": ["Sprite1"],
                "changes": draw_square_response()["changes"],
            },
            draw_square_response(),
        ]
    )
    agent = Agent(provider, context_with_detail(), max_repairs=1)
    result = agent.handle("Revise it.", request_id=25)
    assert result.attempts == 2
    _, second_user = provider.calls[1]
    assert "load_context/load_sprite replies may only contain" in second_user


def test_agent_can_load_a_pack_and_sprite_detail_together():
    provider = MockLLM(
        [
            {"load_context": ["clones"], "load_sprite": ["Sprite1"]},
            draw_square_response(),
        ]
    )
    agent = Agent(provider, context_with_detail())
    result = agent.handle("Add particles and revise the bounce.", request_id=26)
    assert result.attempts == 2
    second_system, second_user = provider.calls[1]
    assert "# Loaded context pack: clones" in second_system
    assert "# Loaded sprite detail: Sprite1" in second_system
    assert "context pack(s): clones" in second_user
    assert "sprite detail: Sprite1" in second_user


def test_agent_no_detail_repair_tells_model_to_stop_requesting():
    provider = MockLLM(
        [
            {"load_sprite": ["Sprite1"]},
            draw_square_response(),
        ]
    )
    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    result = agent.handle("Revise it.", request_id=27)
    assert result.attempts == 2
    first_system, _ = provider.calls[0]
    _, second_user = provider.calls[1]
    assert "  Sprite1:" not in first_system
    assert "No sprite script detail is available" in second_user
    assert "Do not return" in second_user


def test_sprite_detail_extends_the_prompt_budget(monkeypatch):
    monkeypatch.setenv("HARNESS_PROMPT_BUDGET", "60000")
    agent = Agent(MockLLM([]), context_with_detail())
    plain = agent._system_prompt([])
    with_detail = agent._system_prompt([], ["Sprite1"])
    assert len(with_detail) > len(plain)
    assert "# Loaded sprite detail: Sprite1" in with_detail
    assert not re.search(r"\[context appendix truncated \d+ chars\]", with_detail)
