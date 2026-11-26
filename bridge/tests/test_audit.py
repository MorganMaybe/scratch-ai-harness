"""Per-turn audit bundle tests (offline)."""

from __future__ import annotations

import json

import pytest

from harness.agent import Agent
from harness.audit import AuditSettings, AuditStore
from harness.context import ProjectContext
from harness.llm import MockLLM, draw_square_response
from harness.protocol import Sym
from harness.providers.base import ModelReply, ProviderError
from harness.server import Bridge
from harness.validator import ValidationError


def _store(tmp_path, mode: str = "full", keep: int = 10) -> AuditStore:
    return AuditStore(
        AuditSettings(mode=mode, directory=tmp_path / "audit", keep=keep)
    )


def _turn(store: AuditStore, request_id: int = 7):
    return store.start_turn(
        request_id=request_id,
        prompt="Draw a square.",
        target="Sprite1",
        context=ProjectContext.demo(),
        profile="mock",
        model="mock",
        base_url="",
        turn_budget_s=1.0,
        context_literal=[
            "Sprite1",
            [
                ["Stage", True, [], [], ["background1"], [], []],
                ["Sprite1", False, [], [], ["costume1", "costume2"], [], []],
            ],
        ],
    )


def _finish(audit, result) -> None:
    audit.finish(
        outcome="ok",
        attempts=result.attempts,
        changes=len(result.compiled.changes),
        elapsed_ms=12,
        result=result,
    )


class _RawProvider:
    """Provider double that can return a reply with raw text or raise."""

    name = "raw"

    def __init__(self, *, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.calls = 0

    def complete(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.reply


def test_full_bundle_writes_prompts_attempts_compiled_and_chunks(tmp_path):
    store = _store(tmp_path)
    audit = _turn(store)
    assert audit is not None
    agent = Agent(MockLLM([draw_square_response()]), ProjectContext.demo(), audit=audit)

    result = agent.handle("Draw a square.", 7)
    _finish(audit, result)

    root = audit.root
    expected = [
        "meta.json",
        "outcome.json",
        "context/summary.txt",
        "context/project.literal",
        "prompts/system.txt",
        "prompts/user-01.txt",
        "prompts/assembly.json",
        "attempts/01/parsed.json",
        "attempts/01/validation.json",
        "attempts/01/meta.json",
        "compiled/changeset.json",
        "compiled/stacks.json",
        "compiled/apply.json",
        "compiled/apply.literal",
        "compiled/summary.txt",
        "chunks/plan.json",
        "chunks/changes.json",
        "chunks/01-draw_square.json",
    ]
    for relative in expected:
        assert (root / relative).exists(), relative

    parsed = json.loads((root / "attempts/01/parsed.json").read_text(encoding="utf-8"))
    assert parsed["summary"]

    plan = json.loads((root / "chunks/plan.json").read_text(encoding="utf-8"))
    assert plan["source"] == "one-shot-change-set"
    assert plan["changes"][0]["label"] == "draw_square"

    stack = json.loads((root / "compiled/stacks.json").read_text(encoding="utf-8"))
    assert stack[0]["script_id"] == "ai-1"
    assert stack[0]["stack"][0][0] == "#EventHatMorph"

    index = [
        json.loads(line)
        for line in (store.settings.directory / "index.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(index) == 1
    assert index[0]["outcome"] == "ok"
    assert index[0]["dir"] == root.name


def test_bad_json_attempt_keeps_exact_raw_text(tmp_path):
    store = _store(tmp_path)
    audit = _turn(store)
    provider = _RawProvider(
        error=ProviderError(
            "bad_json",
            "model returned invalid JSON",
            raw_text='{"summary": "cut off',
            finish_reason="length",
            reasoning_tokens=8192,
            content_chars=20,
        )
    )
    agent = Agent(provider, ProjectContext.demo(), max_repairs=0, audit=audit)

    with pytest.raises(ValidationError):
        agent.handle("Draw a square.", 7)
    audit.finish(outcome="error:validation", attempts=1, elapsed_ms=1)

    raw = (audit.root / "attempts/01/raw.txt").read_text(encoding="utf-8")
    assert raw == '{"summary": "cut off'
    meta = json.loads((audit.root / "attempts/01/meta.json").read_text(encoding="utf-8"))
    assert meta["raw_available"] is True
    assert meta["error_code"] == "bad_json"
    assert meta["finish_reason"] == "length"
    assert meta["reasoning_tokens"] == 8192
    assert meta["content_chars"] == 20


def test_successful_attempt_keeps_raw_text(tmp_path):
    store = _store(tmp_path)
    audit = _turn(store)
    raw = '{"summary": "Added a square.", "changes": []}'
    reply = ModelReply(
        data=draw_square_response(),
        model="raw",
        raw_text=raw,
        finish_reason="stop",
        usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    )
    provider = _RawProvider(reply=reply)
    agent = Agent(provider, ProjectContext.demo(), audit=audit)

    result = agent.handle("Draw a square.", 7)
    _finish(audit, result)

    assert (audit.root / "attempts/01/raw.txt").read_text(encoding="utf-8") == raw
    outcome = json.loads((audit.root / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["usage"] == {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
    }
    assert outcome["finish_reason"] == "stop"


def test_meta_mode_writes_index_and_outcome_only(tmp_path):
    store = _store(tmp_path, mode="meta")
    audit = _turn(store)
    assert audit is not None
    agent = Agent(MockLLM([draw_square_response()]), ProjectContext.demo(), audit=audit)
    result = agent.handle("Draw a square.", 7)
    _finish(audit, result)

    root = audit.root
    assert (root / "meta.json").exists()
    assert (root / "outcome.json").exists()
    assert not (root / "prompts").exists()
    assert not (root / "attempts").exists()
    assert not (root / "compiled").exists()
    assert (store.settings.directory / "index.jsonl").exists()


def test_off_mode_writes_nothing(tmp_path):
    store = _store(tmp_path, mode="off")
    assert store.start_turn(
        request_id=1,
        prompt="x",
        target="Sprite1",
        context=ProjectContext.demo(),
    ) is None
    assert not (tmp_path / "audit").exists()


def test_bridge_writes_one_bundle_per_request(tmp_path):
    bridge = Bridge(
        Agent(MockLLM([draw_square_response()]), ProjectContext.demo()),
        audit_mode="full",
        audit_dir=str(tmp_path / "audit"),
        audit_keep=5,
    )

    response = bridge.handle([Sym("request"), 42, ["Draw a square."], "Sprite1"])[0]

    assert response[0] == Sym("result")
    bundles = [path for path in (tmp_path / "audit").iterdir() if path.is_dir()]
    assert len(bundles) == 1
    assert (bundles[0] / "meta.json").exists()
    assert (bundles[0] / "outcome.json").exists()


def test_bridge_validation_outcome_records_attempts(tmp_path):
    invalid = {
        "summary": "Bad block.",
        "changes": [
            {
                "action": "add_script",
                "target": "Sprite1",
                "label": "bad",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "move_to", "args": {}}],
            }
        ],
    }
    bridge = Bridge(
        Agent(MockLLM([invalid, invalid, invalid]), ProjectContext.demo()),
        audit_mode="meta",
        audit_dir=str(tmp_path / "audit"),
    )

    response = bridge.handle([Sym("request"), 43, ["Draw a square."], "Sprite1"])[0]

    assert response[0] == Sym("error")
    bundles = [path for path in (tmp_path / "audit").iterdir() if path.is_dir()]
    assert len(bundles) == 1
    outcome = json.loads((bundles[0] / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["outcome"] == "error:validation"
    assert outcome["attempts"] == 3
    index = [
        json.loads(line)
        for line in (tmp_path / "audit" / "index.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert index[-1]["attempts"] == 3


def test_audit_write_failure_never_raises(tmp_path, monkeypatch):
    store = _store(tmp_path)
    audit = _turn(store)
    assert audit is not None

    def boom(*args, **kwargs):
        raise RuntimeError("simulated disk failure")

    monkeypatch.setattr(audit, "_write", boom)
    # These are wrapped by the audit guard; a broken writer must not fail the
    # model turn.
    audit.write_prompts("system", "user")
    audit.write_attempt(1, user_prompt="user")
    audit.finish(outcome="ok", attempts=1, changes=0, elapsed_ms=1)


def test_keep_prunes_old_bundles(tmp_path):
    store = _store(tmp_path, keep=2)
    for request_id in (1, 2, 3):
        audit = _turn(store, request_id=request_id)
        audit.finish(outcome="ok", attempts=1, changes=0, elapsed_ms=1)

    bundles = [path for path in (tmp_path / "audit").iterdir() if path.is_dir()]
    assert len(bundles) == 2
    # The newest turn is always kept.
    assert any("req3" in path.name for path in bundles)


def test_write_prompts_keeps_the_original_first_user_prompt(tmp_path):
    store = _store(tmp_path)
    audit = _turn(store)
    assert audit is not None

    # A lazy-load round re-reports the refreshed prompt through write_prompts;
    # the bundle must keep what attempt 1 actually received, not the rewrite.
    audit.write_prompts("system v1", "first user prompt")
    audit.write_prompts("system v2", "second user prompt")

    root = audit.root
    assert (root / "prompts/user-01.txt").read_text(encoding="utf-8") == (
        "first user prompt"
    )
    # The system prompt keeps last-write-wins: it describes the prompt the
    # final attempt consumed.
    assert (root / "prompts/system.txt").read_text(encoding="utf-8") == "system v2"


def _detail_context() -> ProjectContext:
    """Demo context plus one AI-owned script with tuples, loadable on demand."""
    from harness.context import ScriptSummary

    context = ProjectContext.demo()
    context.sprites["Sprite1"].scripts.append(
        ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label="bounce",
            hat="EventHatMorph",
            block_count=2,
            owned=True,
            tuples=[
                [Sym("EventHatMorph"), "Scratch-StartClicked"],
                [Sym("forward:"), 10],
            ],
        )
    )
    return context


def test_load_round_preserves_attempt_prompts_and_records_events(tmp_path):
    store = _store(tmp_path)
    audit = _turn(store)
    assert audit is not None
    provider = MockLLM(
        [
            {"load_sprite": ["Sprite1"], "reason": "need the bounce body"},
            draw_square_response(),
        ]
    )
    agent = Agent(provider, _detail_context(), audit=audit)
    result = agent.handle("Make it bounce faster.", request_id=7)
    _finish(audit, result)
    assert result.attempts == 2

    root = audit.root
    first = (root / "prompts/user-01.txt").read_text(encoding="utf-8")
    # The original attempt-1 prompt survives the load round: no "included"
    # announcement, and the request line is intact.
    assert "now included in the system prompt" not in first
    assert "User request:\nMake it bounce faster." in first
    # The post-load prompt belongs to attempt 2, under its own number.
    second = (root / "prompts/user-02.txt").read_text(encoding="utf-8")
    assert "now included in the system prompt" in second
    assert "sprite detail: Sprite1" in second
    # The load chain is reconstructible from the bundle alone.
    assembly = json.loads((root / "prompts/assembly.json").read_text(encoding="utf-8"))
    assert assembly["user"]["load_events"] == [
        {"attempt": 1, "packs": [], "sprites": ["Sprite1"]}
    ]
