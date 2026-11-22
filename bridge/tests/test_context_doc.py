from __future__ import annotations

import re

from harness.agent import Agent
from harness.context import ProjectContext
from harness.context_doc import load_context_doc
from harness.llm import MockLLM
from harness.prompts import build_system_prompt, estimate_tokens

CONTEXT_MARKER = re.compile(r"\[context appendix truncated \d+ chars\]")


def test_context_doc_loads_the_repository_appendix():
    doc = load_context_doc()
    assert "Scratch AI Context Appendix" in doc
    assert "Media library" in doc


def test_system_prompt_includes_context_appendix():
    doc = load_context_doc()
    prompt = build_system_prompt(target="Sprite1", budget_chars=60000, context_doc=doc)
    assert "Additional Scratch context" in prompt
    assert "Scratch AI Context Appendix" in prompt
    assert len(prompt) <= 60000
    assert not CONTEXT_MARKER.search(prompt)


def test_context_appendix_is_trimmed_before_the_catalog():
    doc = load_context_doc()
    prompt = build_system_prompt(target="Sprite1", budget_chars=22000, context_doc=doc)
    assert len(prompt) <= 22000
    assert CONTEXT_MARKER.search(prompt)
    assert "Available block ops:" in prompt


def test_agent_sends_the_context_appendix_to_the_model(monkeypatch):
    monkeypatch.setenv("HARNESS_PROMPT_BUDGET", "60000")
    response = {
        "summary": "Add a square.",
        "changes": [
            {
                "action": "add_script",
                "target": "Sprite1",
                "label": "square",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "pen_down"}],
            }
        ],
    }
    llm = MockLLM([response])
    result = Agent(llm, ProjectContext.demo()).handle("draw a square")
    assert result.compiled.changes[0].action == "add_script"
    system, _user = llm.calls[0]
    assert "Scratch AI Context Appendix" in system
    assert "Additional Scratch context" in system
    assert estimate_tokens(system) == len(system) // 4
