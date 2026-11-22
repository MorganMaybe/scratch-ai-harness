from __future__ import annotations

import pytest

from harness.context_doc import (
    ContextPackError,
    available_context_packs,
    load_context_doc,
    load_context_pack,
    load_context_packs,
    reset_context_doc_cache,
)
from harness.prompts import build_system_prompt


def test_available_context_packs():
    reset_context_doc_cache()
    packs = available_context_packs()
    assert {"clones", "scrolling", "pen-3d"} <= set(packs)
    assert "README" not in packs
    assert all(packs[name] for name in packs)


def test_load_context_pack_and_join():
    text = load_context_pack("clones")
    assert "when_clone_start" in text
    assert "300" in text
    joined = load_context_packs(["clones", "scrolling"])
    assert joined.count("# Loaded context pack:") == 2
    assert joined.index("clones") < joined.index("scrolling")


def test_load_context_pack_rejects_unknown_and_traversal():
    with pytest.raises(ContextPackError):
        load_context_pack("does-not-exist")
    with pytest.raises(ContextPackError):
        load_context_pack("../SCRATCH_AI_CONTEXT")


def test_core_doc_points_at_packs():
    doc = load_context_doc()
    assert "Context packs (load on demand)" in doc
    assert "`clones`" in doc
    assert "`scrolling`" in doc
    assert "`pen-3d`" in doc


def test_loaded_pack_is_visible_in_the_system_prompt():
    doc = load_context_doc() + "\n\n" + load_context_packs(["clones"])
    prompt = build_system_prompt(target="Sprite1", budget_chars=60000, context_doc=doc)
    assert "# Loaded context pack: clones" in prompt
    assert "when_clone_start" in prompt
