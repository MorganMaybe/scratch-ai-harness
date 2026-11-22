from __future__ import annotations

import re

from harness.agent import Agent
from harness.context import ProjectContext
from harness.llm import MockLLM, draw_square_response


def test_agent_lazy_loads_a_context_pack():
    provider = MockLLM(
        [
            {"load_context": ["clones"], "reason": "particle request"},
            draw_square_response(),
        ]
    )
    agent = Agent(provider, ProjectContext.demo())
    result = agent.handle("Make a particle spray.", request_id=12)
    assert result.attempts == 2
    assert len(provider.calls) == 2
    first_system, _ = provider.calls[0]
    second_system, second_user = provider.calls[1]
    assert "# Loaded context pack: clones" not in first_system
    assert "# Loaded context pack: clones" in second_system
    assert "now included in the system prompt" in second_user


def test_agent_repairs_unknown_context_pack():
    provider = MockLLM(
        [
            {"load_context": ["does-not-exist"]},
            draw_square_response(),
        ]
    )
    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    result = agent.handle("Draw something.", request_id=13)
    assert result.attempts == 2
    _, second_user = provider.calls[1]
    assert "unknown context pack" in second_user
    assert "clones" in second_user  # available list


def test_agent_rejects_load_context_plus_changes():
    bad = {
        "load_context": ["clones"],
        "changes": draw_square_response()["changes"],
    }
    provider = MockLLM([bad, draw_square_response()])
    agent = Agent(provider, ProjectContext.demo(), max_repairs=1)
    result = agent.handle("Draw a square.", request_id=14)
    assert result.attempts == 2
    _, second_user = provider.calls[1]
    assert "load_context/load_sprite replies may only contain" in second_user


def test_agent_does_not_load_the_same_pack_twice():
    provider = MockLLM(
        [
            {"load_context": ["clones"]},
            {"load_context": ["clones"]},
            draw_square_response(),
        ]
    )
    agent = Agent(provider, ProjectContext.demo(), max_repairs=2)
    result = agent.handle("Draw a square.", request_id=15)
    assert result.attempts == 3
    _, second_user = provider.calls[1]
    assert "now included in the system prompt" in second_user
    _, third_user = provider.calls[2]
    assert "already loaded" in third_user
    assert "# Loaded context pack: clones" in provider.calls[2][0]


def test_loaded_pack_extends_the_prompt_budget(monkeypatch):
    from harness.context_doc import load_context_packs

    monkeypatch.setenv("HARNESS_PROMPT_BUDGET", "60000")
    agent = Agent(MockLLM([]), ProjectContext.demo())
    plain = agent._system_prompt([])
    with_pack = agent._system_prompt(["clones"])
    pack_text = load_context_packs(["clones"])
    # The pack's own characters are added to the budget, so the core guide,
    # media index and catalog keep essentially the same room.
    assert len(with_pack) >= len(plain) + len(pack_text)
    assert "# Loaded context pack: clones" in with_pack
    assert not re.search(r"\[context appendix truncated \d+ chars\]", with_pack)
