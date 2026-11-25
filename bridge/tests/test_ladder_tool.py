"""The Phase C ladder tool: offline wiring test.

``tools/ladder.py`` is a live-run benchmark, but its plumbing (audit bundles,
scenario chaining, manifest/summary output) must stay green offline. The
dry-run stub provider answers every turn with the same valid square change
set, so a restricted one-run ladder exercises the whole path without a
network, key or image.
"""

from __future__ import annotations

import pytest

import importlib.util
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LADDER_PATH = _REPO_ROOT / "tools" / "ladder.py"


def _load_ladder():
    spec = importlib.util.spec_from_file_location("ladder_tool", _LADDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    # Register before exec: dataclass introspection looks the module up in
    # sys.modules by __name__ (Agent's dataclasses, the tool's own Step).
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


@pytest.mark.usefixtures("lazy_context")
def test_dry_run_ladder_writes_bundles_and_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "json")
    ladder = _load_ladder()
    audit_dir = tmp_path / "ladder"

    code = ladder.main(
        [
            "--dry-run",
            "-Runs",
            "1",
            "-Scenarios",
            "square_chain",
            "-AuditDir",
            str(audit_dir),
        ]
    )

    assert code == 0
    manifest = json.loads((audit_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dry_run"] is True
    assert manifest["runs"] == 1
    assert manifest["modes"] == ["json", "dsl"]
    assert manifest["history"] is True
    turns = manifest["turns"]
    assert len(turns) == 4  # 2 steps x 2 modes x 1 run
    assert all(turn["outcome"] == "ok" for turn in turns)
    assert all(turn["history"] is True for turn in turns)
    assert {turn["mode"] for turn in turns} == {"json", "dsl"}

    # Every turn wrote a full audit bundle tagged with its generator.
    for turn in turns:
        bundle = audit_dir / turn["dir"]
        assert (bundle / "meta.json").is_file(), bundle
        meta = json.loads((bundle / "meta.json").read_text(encoding="utf-8"))
        assert meta["generator"] == turn["mode"]
        assert meta["mode"] == "full"
        assert (bundle / "outcome.json").is_file()
        assert (bundle / "prompts" / "system.txt").is_file()
        assert (bundle / "attempts" / "01" / "raw.txt").is_file()

    # The chained step sees the state its predecessor built: the follow-up
    # user prompt must list the applied script id, and the system prompt
    # must offer the sprite script detail that replace_script needs.
    bigger_json = next(
        turn
        for turn in turns
        if turn["step"] == "bigger_say" and turn["mode"] == "json"
    )
    bundle = audit_dir / bigger_json["dir"]
    user_prompt = (bundle / "prompts" / "user-01.txt").read_text(encoding="utf-8")
    assert "ai-1" in user_prompt
    assert "draw_square" in user_prompt
    # The chained step also sees the previous turn's conversation: the square
    # request and its applied summary are in the history section.
    assert "Conversation so far" in user_prompt
    assert "Make the cat draw a square" in user_prompt
    assert "Assistant: Added a green-flag square-drawing script." in user_prompt
    system_prompt = (bundle / "prompts" / "system.txt").read_text(encoding="utf-8")
    # The appendix shows a generic example; the live index line names the
    # actual sprite and script ids for this project.
    assert "Sprite1: ai-1 draw_square" in system_prompt
    first = audit_dir / turns[0]["dir"]
    first_system = (first / "prompts" / "system.txt").read_text(encoding="utf-8")
    assert "Sprite1: ai-1" not in first_system

    # The summary aggregates per (step, mode) and computes the flip verdict.
    summary = json.loads((audit_dir / "summary.json").read_text(encoding="utf-8"))
    rows = summary["summary"]
    assert len(rows) == 4
    assert all(row["ok"] == 1 for row in rows)
    assert {row["mode"] for row in rows} == {"json", "dsl"}
    verdict = summary["flip_verdict"]
    assert verdict["json"]["ok"] == 2
    assert verdict["dsl"]["ok"] == 2
    assert verdict["dsl"]["bad_json_outcomes"] == 0


def test_dry_run_ladder_history_off_leaves_prompts_stateless(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_GENERATOR", "json")
    ladder = _load_ladder()
    audit_dir = tmp_path / "ladder-off"

    code = ladder.main(
        [
            "--dry-run",
            "-Runs",
            "1",
            "-Scenarios",
            "square_chain",
            "-AuditDir",
            str(audit_dir),
            "-History",
            "off",
        ]
    )

    assert code == 0
    manifest = json.loads((audit_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["history"] is False
    assert all(turn["history"] is False for turn in manifest["turns"])
    for turn in manifest["turns"]:
        prompt = audit_dir / turn["dir"] / "prompts" / "user-01.txt"
        assert "Conversation so far" not in prompt.read_text(encoding="utf-8")


def test_unknown_scenario_and_mode_are_rejected(tmp_path):
    ladder = _load_ladder()
    for argv in (
        ["--dry-run", "-Runs", "1", "-Scenarios", "nope"],
        ["--dry-run", "-Runs", "1", "-Modes", "yaml"],
        ["--dry-run", "-Runs", "0"],
    ):
        try:
            ladder.main(argv)
        except SystemExit as exc:
            assert exc.code not in (0, None)
        else:
            raise AssertionError(f"expected SystemExit for {argv}")


def test_context_after_apply_carries_scripts_and_variables():
    ladder = _load_ladder()

    class CompiledChange:
        action = "add_script"
        script_id = "ai-7"
        target = "Sprite1"
        label = "wander"
        stack = [
            ["EventHatMorph", "Scratch-StartClicked"],
            ["forward:", 10],
        ]
        block_count = 2

    class Compiled:
        changes = [CompiledChange()]

    class Result:
        compiled = Compiled()

    context = ladder.clean_context()
    applied = ladder.context_after_apply(context, Result())

    script = applied.sprites["Sprite1"].scripts[-1]
    assert script.script_id == "ai-7"
    assert script.owned is True
    assert script.tuples == CompiledChange.stack
    assert script.label == "wander"
    # The original context is untouched (each turn gets a fresh snapshot).
    assert context.sprites["Sprite1"].scripts == []
