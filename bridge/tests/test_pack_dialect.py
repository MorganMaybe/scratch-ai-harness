"""Dialect-first context packs and their generated JSON twins.

The python fences in ``context/games.md``, ``context/clones.md`` and
``context/scrolling.md`` are canonical. These tests keep the twins in sync,
check them at the IR level (no media tree needed), and verify the per-generator
filtering the bridge applies before a pack reaches a prompt.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from harness.context_doc import (
    load_context_pack,
    load_context_packs,
    reset_context_doc_cache,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_DIR = _REPO_ROOT / "tools"


def _load_tool(name: str):
    """Load one ``tools/`` module by path (the ladder test's pattern)."""
    path = _TOOLS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"pack_tool_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclass introspection looks the module up in sys.modules by __name__.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


pack_examples = _load_tool("pack_examples")
render_pack_json = _load_tool("render_pack_json")

PACKS = sorted(pack_examples.PACKS)


def test_render_pack_json_check_is_in_sync():
    assert render_pack_json.main(["--check"]) == 0


@pytest.mark.parametrize("pack", PACKS)
def test_python_fences_match_json_twins(pack):
    text = pack_examples.read_pack(pack)
    sources = pack_examples.python_fences(text)
    twins = [json.loads(block) for block in pack_examples.json_fences(text)]
    assert sources, f"{pack} has no python examples"
    assert len(sources) == len(twins)
    for index, (source, twin) in enumerate(zip(sources, twins), 1):
        expected = pack_examples.render_example_json(source, pack)
        parsed = twin if isinstance(twin, list) else [twin]
        assert parsed == expected, f"{pack} example {index} drifted"


@pytest.mark.parametrize("pack", PACKS)
def test_pack_filtering_keeps_one_dialect(pack):
    reset_context_doc_cache()
    dsl = load_context_pack(pack, generator="dsl")
    js = load_context_pack(pack, generator="json")

    assert "```python" in dsl
    assert "```json" not in dsl
    assert pack_examples.TWIN_MARKER not in dsl

    assert "```json" in js
    assert "```python" not in js
    assert pack_examples.TWIN_MARKER not in js

    # The default stays the historical JSON shape.
    assert load_context_pack(pack) == js


def test_joined_dsl_packs_have_no_json_examples():
    joined = load_context_packs(list(PACKS), generator="dsl")
    assert "```json" not in joined
    assert joined.count("```python") >= 11
    for pack in PACKS:
        assert f"# Loaded context pack: {pack}" in joined


def test_agent_system_prompt_uses_generator_filter():
    from harness.agent import Agent
    from harness.context import ProjectContext
    from harness.llm import MockLLM

    agent = Agent(MockLLM([]), ProjectContext.demo())
    json_prompt = agent._system_prompt(["clones"], generator="json")
    dsl_prompt = agent._system_prompt(["clones"], generator="dsl")

    assert 'create_clone("myself")' not in json_prompt
    assert 'create_clone("myself")' in dsl_prompt
