"""Green-flag reset guidance in the core guides and the scenes pack."""

from __future__ import annotations

from harness.context_doc import (
    DEFAULT_DSL_CONTEXT_DOC,
    available_context_packs,
    load_context_doc,
    load_context_pack,
)
from harness.prompts import DSL_SYSTEM_PROMPT


def test_both_core_guides_teach_a_full_green_flag_reset():
    for doc in (load_context_doc(), load_context_doc(DEFAULT_DSL_CONTEXT_DOC)):
        assert "### Reset on green flag" in doc
        assert "nothing resets by itself" in doc
        for needle in ("pen_clear", "clear_effects", "reset_timer", "goto_xy"):
            assert needle in doc, needle
        # Revisions that move a start point must edit the reset script.
        flat = " ".join(doc.split())
        assert "alone is undone by the next green flag" in flat


def test_dsl_system_prompt_requires_the_reset():
    assert "The green flag resets everything the project changes" in DSL_SYSTEM_PROMPT


def test_scenes_pack_is_listed_and_indexed():
    assert "scenes" in available_context_packs()
    for doc in (load_context_doc(), load_context_doc(DEFAULT_DSL_CONTEXT_DOC)):
        assert "`scenes`" in doc


def test_scenes_pack_teaches_the_router_contract():
    dsl = load_context_pack("scenes", "dsl")
    assert 'broadcast("scene_changed")' in dsl
    assert "while scene == 2:" in dsl
    json_text = load_context_pack("scenes", "json")
    # JSON mode sees generated twins and neutral prose, never dialect calls.
    assert 'broadcast("scene_changed")' not in json_text
    assert '"when_receive"' in json_text
    for text in (dsl, json_text):
        assert "Every sprite needs a scene handler" in text
        assert "Entering a scene resets that scene" in text
