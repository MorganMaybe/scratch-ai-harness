from __future__ import annotations

import re

import pytest

from harness.catalog import catalog_summary
from harness.context import ProjectContext, ScriptSummary, SpriteContext
from harness.prompts import (
    DEFAULT_PROMPT_BUDGET,
    EXAMPLES,
    SYSTEM_PROMPT,
    VERIFIED_PROP_PATHS,
    build_system_prompt,
    build_user_prompt,
    estimate_tokens,
    known_good_media_block,
    media_index_text,
    prompt_budget_chars,
)

CATEGORY_LINE = re.compile(r"^[a-z]+:$")
BLOCK_LINE = re.compile(
    r"^  [a-z_]+\([^()]*\)( \{ \.\.\. \})?( \{ \.\.\. \} else \{ \.\.\. \})?$"
)


def _rich_context() -> ProjectContext:
    scripts = [
        ScriptSummary(
            script_id=f"ai-{index}",
            target="Sprite1",
            label=f"script_{index}",
            hat="when_flag_clicked",
            block_count=10 + index,
            owned=index % 2 == 0,
            user_edited=index == 3,
        )
        for index in range(1, 5)
    ]
    return ProjectContext(
        target="Sprite1",
        sprites={
            "Sprite1": SpriteContext(
                name="Sprite1",
                variables=[f"var{index}" for index in range(1, 9)],
                costumes=[f"costume{index}" for index in range(1, 9)],
                sounds=[f"sound{index}" for index in range(1, 9)],
                scripts=scripts,
            ),
            "Stage": SpriteContext(name="Stage", is_stage=True),
        },
        stage_variables=[f"global{index}" for index in range(1, 6)],
        stage_lists=[f"list{index}" for index in range(1, 5)],
    )


def _snapshot_system(target: str) -> str:
    kind = "stage" if target.lower() == "stage" else "sprite"
    # The verified region is the curated prop paths plus the optional mined
    # tier; the snapshot composes it exactly as the builder does.
    region = VERIFIED_PROP_PATHS + known_good_media_block()
    return (
        SYSTEM_PROMPT.replace(VERIFIED_PROP_PATHS, region)
        .replace("{catalog}", catalog_summary(None, kind))
        .replace("{media}", media_index_text(max_chars=16000))
        + "\n"
        + EXAMPLES
    )


def _snapshot_user(request: str, context: ProjectContext) -> str:
    return f"""User request:
{request}

Project context:
{context.summary_text()}

Return the JSON change set now.
"""


def test_default_system_prompt_is_byte_identical(monkeypatch):
    monkeypatch.delenv("HARNESS_PROMPT_BUDGET", raising=False)
    expected = _snapshot_system("Sprite1")
    assert build_system_prompt(target="Sprite1") == expected
    assert build_system_prompt(target="Sprite1", budget_chars=len(expected)) == expected
    assert build_system_prompt(target="Sprite1", budget_chars=10**9) == expected


def test_default_user_prompt_is_byte_identical(monkeypatch):
    monkeypatch.delenv("HARNESS_PROMPT_BUDGET", raising=False)
    context = ProjectContext.demo()
    expected = _snapshot_user("Draw a square.", context)
    assert build_user_prompt("Draw a square.", context) == expected
    assert (
        build_user_prompt("Draw a square.", context, budget_chars=len(expected))
        == expected
    )


def test_system_prompt_accepts_positional_target_and_legacy_shape():
    expected = _snapshot_system("Sprite1")
    assert build_system_prompt("Sprite1") == expected
    assert build_system_prompt({"events"}, "Sprite1") == build_system_prompt(
        target="Sprite1", categories={"events"}
    )


def test_default_budget_prompts_have_no_marker(monkeypatch):
    monkeypatch.delenv("HARNESS_PROMPT_BUDGET", raising=False)
    context = ProjectContext.demo()
    system = build_system_prompt(target="Sprite1")
    user = build_user_prompt("Draw a square.", context)
    assert "[catalog truncated" not in system
    assert "[truncated " not in user
    assert len(system) + len(user) < DEFAULT_PROMPT_BUDGET


def test_tiny_system_budget_is_respected_and_marked():
    output = build_system_prompt(target="Sprite1", budget_chars=2000)
    assert len(output) <= 2000
    assert "[catalog truncated " in output
    assert output.rstrip().endswith("chars]")


def test_very_tiny_system_budget_still_respects_the_limit():
    output = build_system_prompt(target="Sprite1", budget_chars=800)
    assert len(output) <= 800
    assert "[catalog truncated " in output


def test_catalog_lines_are_never_cut_in_half():
    output = build_system_prompt(target="Sprite1", budget_chars=5200)
    catalog = output.split("Available block ops:\n", 1)[1]
    seen_blocks = 0
    for line in catalog.splitlines():
        if not line.strip():
            continue
        if line.startswith("[catalog truncated"):
            continue
        assert CATEGORY_LINE.match(line) or BLOCK_LINE.match(line), line
        if line.startswith("  "):
            seen_blocks += 1
    assert seen_blocks > 0
    assert len(output) <= 5200


def test_script_targeting_survives_aggressive_trimming():
    context = _rich_context()
    output = build_user_prompt("x" * 600, context, budget_chars=1000)
    assert len(output) <= 1000
    assert "Target: Sprite1" in output
    assert "ai-owned" in output
    assert "user-created, read-only" in output
    for script in context.registry().values():
        assert script.script_id in output
        assert script.label in output


def test_tiny_user_budget_is_respected_and_marked():
    output = build_user_prompt("Draw a square.", ProjectContext.demo(), budget_chars=100)
    assert len(output) <= 100
    assert "[truncated " in output
    assert output.rstrip().endswith("chars]")
    assert "Target: Sprite1" in output


def test_user_trimming_drops_frills_before_script_ids():
    context = _rich_context()
    output = build_user_prompt("Draw a square.", context, budget_chars=700)
    assert "script_1" in output
    assert "costume1" not in output
    assert "sound1" not in output


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("5000", 5000),
        (" 123 ", 123),
        ("0", DEFAULT_PROMPT_BUDGET),
        ("-5", DEFAULT_PROMPT_BUDGET),
        ("not-a-number", DEFAULT_PROMPT_BUDGET),
        ("", DEFAULT_PROMPT_BUDGET),
    ],
)
def test_prompt_budget_chars_honours_environment(monkeypatch, value, expected):
    monkeypatch.setenv("HARNESS_PROMPT_BUDGET", value)
    assert prompt_budget_chars() == expected


def test_prompt_budget_chars_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("HARNESS_PROMPT_BUDGET", raising=False)
    assert prompt_budget_chars() == DEFAULT_PROMPT_BUDGET
    # Large enough for the curated media index plus the full appendix.
    assert DEFAULT_PROMPT_BUDGET == 80000


def test_estimate_tokens_is_monotonic_and_roughly_quarter_length():
    text = ""
    previous = estimate_tokens(text)
    assert previous == 0
    for size in (4, 10, 40, 100, 400, 4000):
        current = estimate_tokens("x" * size)
        assert current >= previous
        assert abs(current - size / 4) <= 1
        previous = current


def test_estimate_tokens_of_a_real_prompt():
    prompt = build_system_prompt(target="Sprite1")
    assert estimate_tokens(prompt) == len(prompt) // 4
