"""Clones are the default for crowds: the core guides say so, the pack is exact."""

from __future__ import annotations

from harness.context_doc import (
    DEFAULT_DSL_CONTEXT_DOC,
    load_context_doc,
    load_context_pack,
)
from harness.prompts import DSL_SYSTEM_PROMPT


def test_both_core_guides_make_clones_the_crowd_default():
    for doc in (load_context_doc(), load_context_doc(DEFAULT_DSL_CONTEXT_DOC)):
        assert 'the default for "many of the same thing"' in doc
        assert "Three or more similar actors are one template sprite plus clones" in doc


def test_dsl_system_prompt_names_the_clone_default():
    assert "one hidden template sprite plus clones" in DSL_SYSTEM_PROMPT


def test_dsl_worked_crab_example_uses_one_sprite_and_clones():
    doc = load_context_doc(DEFAULT_DSL_CONTEXT_DOC)
    example = doc[doc.index("### A. A beach") : doc.index("### B.")]
    assert example.count("create_sprite(") == 1
    assert 'create_clone("myself")' in example
    assert "@on_clone_start" in example


def test_clone_pack_documents_the_real_semantics():
    text = load_context_pack("clones", "dsl")
    for needle in (
        "as it is at that instant",  # fullCopy at create time
        "**visibility**",  # hidden template -> hidden clones
        "every other hat",  # receive/key/click run in clones
        "No clone bombs",
        "stamp idiom",
        "300",
    ):
        assert needle in text, needle
