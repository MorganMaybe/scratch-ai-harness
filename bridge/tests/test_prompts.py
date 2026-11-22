from __future__ import annotations

from harness.context import ProjectContext
from harness.prompts import (
    analyze_system_prompt,
    build_system_prompt,
    build_user_prompt,
    build_user_prompt_with_meta,
)


def test_system_prompt_contains_catalog_and_schema():
    system = build_system_prompt(target="Sprite1")
    assert "change set" in system
    assert "move(steps: number)" in system
    assert "when_flag_clicked" in system
    assert "Return ONLY a JSON object" in system


def test_system_prompt_keeps_verified_prop_paths_when_index_is_trimmed():
    trimmed = build_system_prompt(
        target="Sprite1", media_index="  Players: fantasy1-a.png\n"
    )
    for path in (
        "Geometry/line.png",
        "Letters/Block/a.png",
        "GameItems/paddle.png",
        "UI/scoreboard.gif",
    ):
        assert path in trimmed
    assert "Never use Players/fantasy1-a.png" in trimmed
    assert "cartoon creature" in trimmed
    assert "Media library (relative to scratch/base/Media):" in trimmed

    ordinary = build_system_prompt(target="Sprite1")
    assert "Media library (relative to scratch/base/Media):" in ordinary
    assert "Geometry/line.png" in ordinary


def test_user_prompt_contains_context():
    user = build_user_prompt("Draw a square.", ProjectContext.demo())
    assert "Draw a square." in user
    assert "Sprite1" in user
    assert "costume1" in user


def test_user_prompt_meta_reports_full_context():
    prompt, meta = build_user_prompt_with_meta("Draw a square.", ProjectContext.demo())
    assert meta["level"] == 0
    assert meta["truncated"] is False
    assert meta["dropped_chars"] == 0
    assert meta["chars"] == len(prompt)


def test_user_prompt_meta_reports_hard_truncation():
    prompt, meta = build_user_prompt_with_meta(
        "Draw a square.", ProjectContext.demo(), budget_chars=40
    )
    assert meta["level"] == 3
    assert meta["truncated"] is True
    assert meta["dropped_chars"] > 0
    assert "[truncated" in prompt


def test_analyze_system_prompt_detects_budget_markers():
    info = analyze_system_prompt(
        "header\n[media index truncated 120 chars]\n[catalog truncated 50 chars]\n"
    )
    assert info["truncations"] == {"media index": 120, "catalog": 50}
    assert info["has_examples"] is False
    assert info["has_appendix"] is False
