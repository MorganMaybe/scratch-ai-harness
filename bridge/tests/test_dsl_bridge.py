"""Offline tests for the generator switch and the DSL-aware plumbing."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from harness.audit import AuditSettings, AuditStore
from harness.config import ConfigError, resolve_config, resolve_generator
from harness.prompts import build_dsl_system_prompt
from harness.providers.base import BaseProvider, ModelReply, ModelRequest, ProviderError
from harness.providers.mock import MockProvider
from harness.providers.openai_compat import OpenAICompatProvider
from harness.providers.replay import RecordingProvider, ReplayProvider


def _write_ini(path, body: str):
    path.write_text(body, encoding="utf-8")
    return path


# -- resolve_generator -------------------------------------------------------


def test_resolve_generator_defaults_to_json(tmp_path):
    path = _write_ini(tmp_path / "harness.ini", "[model]\ndefault=opencode-go\n")
    assert resolve_generator(path, env={}) == "json"
    assert resolve_generator(tmp_path / "missing.ini", env={}) == "json"


def test_resolve_generator_reads_the_harness_section(tmp_path):
    path = _write_ini(tmp_path / "harness.ini", "[model]\ndefault=opencode-go\n[harness]\ngenerator=dsl\n")
    assert resolve_generator(path, env={}) == "dsl"


def test_resolve_generator_env_wins_over_ini(tmp_path):
    path = _write_ini(tmp_path / "harness.ini", "[harness]\ngenerator=dsl\n")
    assert resolve_generator(path, env={"HARNESS_GENERATOR": "json"}) == "json"


def test_blank_values_fall_through_to_the_next_source(tmp_path):
    path = _write_ini(tmp_path / "harness.ini", "[harness]\ngenerator=dsl\n")
    assert resolve_generator(path, env={"HARNESS_GENERATOR": "  "}) == "dsl"
    blank_ini = _write_ini(tmp_path / "blank.ini", "[harness]\ngenerator=\n")
    assert resolve_generator(blank_ini, env={"HARNESS_GENERATOR": ""}) == "json"


@pytest.mark.parametrize("value", ["xml", "DSL2", "json dsl"])
def test_invalid_env_or_ini_generator_raises(tmp_path, value):
    path = _write_ini(tmp_path / "harness.ini", "[harness]\ngenerator=json\n")
    with pytest.raises(ConfigError) as caught:
        resolve_generator(path, env={"HARNESS_GENERATOR": value})
    assert "generator must be one of: json, dsl" in str(caught.value)

    bad_ini = _write_ini(tmp_path / "bad.ini", f"[harness]\ngenerator={value}\n")
    with pytest.raises(ConfigError) as caught:
        resolve_generator(bad_ini, env={})
    assert "generator must be one of: json, dsl" in str(caught.value)


# -- MockProvider ------------------------------------------------------------


def test_mock_provider_string_response_is_raw_text():
    provider = MockProvider(["move(10)\n"])
    reply = provider.complete(ModelRequest(request_id=1, system="s", user="u"))

    assert reply.data == {}
    assert reply.raw_text == "move(10)\n"
    assert reply.model == "mock"
    assert reply.finish_reason == "stop"


def test_mock_provider_dict_response_is_unchanged():
    payload = {"summary": "ok", "changes": []}
    provider = MockProvider([payload])
    reply = provider.complete(ModelRequest(request_id=1, system="s", user="u"))

    assert reply.data == payload
    assert reply.raw_text is None


# -- Replay ------------------------------------------------------------------


class _CannedDsl(BaseProvider):
    name = "canned-dsl"

    def __init__(self, reply: ModelReply):
        super().__init__()
        self.reply = reply

    def complete(self, request: ModelRequest) -> ModelReply:
        return self.reply


def _dsl_request() -> ModelRequest:
    return ModelRequest(
        request_id=1, system="sys", user="user", reply_format="dsl"
    )


def test_replay_records_and_serves_a_dsl_raw_reply(tmp_path):
    path = tmp_path / "dsl.jsonl"
    module = 'import os\n'
    recorder = RecordingProvider(
        _CannedDsl(ModelReply(data={}, raw_text=module, model="m", finish_reason="stop")),
        path,
    )
    recorder.complete(_dsl_request())

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["raw_text"] == module

    reply = ReplayProvider(path).complete(_dsl_request())
    assert reply.data == {}
    assert reply.raw_text == module
    assert reply.finish_reason == "stop"


def test_replay_json_fixture_cannot_serve_a_dsl_request(tmp_path):
    path = tmp_path / "json.jsonl"
    recording = RecordingProvider(
        _CannedDsl(ModelReply(data={"summary": "ok", "changes": []}, model="m")),
        path,
    )
    recording.complete(ModelRequest(request_id=1, system="sys", user="user"))

    with pytest.raises(ProviderError) as caught:
        ReplayProvider(path).complete(_dsl_request())

    assert caught.value.code == "replay"
    assert "raw DSL reply" in caught.value.message


# -- build_dsl_system_prompt -------------------------------------------------


def test_dsl_system_prompt_has_the_reference_and_appendix():
    prompt = build_dsl_system_prompt(
        target="Sprite1",
        budget_chars=10**9,
        context_doc="# Appendix\n\nThe Python you MAY use: while True is forever.",
    )

    assert "Scratch-Python API reference (generated from the block catalog)" in prompt
    assert "Available Scratch-Python API:" in prompt
    assert "The Python you MAY use" in prompt
    assert "Reply with ONE fenced python block" in prompt
    assert "{media}" not in prompt
    assert "{catalog}" not in prompt


def test_dsl_system_prompt_respects_a_tiny_budget():
    prompt = build_dsl_system_prompt(target="Sprite1", budget_chars=2000)

    assert len(prompt) <= 2000
    assert "[catalog truncated " in prompt


# -- audit -------------------------------------------------------------------


def _turn(store, generator="dsl"):
    return store.start_turn(
        request_id=5,
        prompt="Draw a square.",
        target="Sprite1",
        context=None,
        profile="mock",
        model="mock",
        base_url="",
        turn_budget_s=1.0,
        context_literal=None,
        generator=generator,
    )


def test_audit_meta_records_the_generator(tmp_path):
    store = AuditStore(
        AuditSettings(mode="full", directory=tmp_path / "audit", keep=10)
    )

    dsl_turn = _turn(store, "dsl")
    json_turn = _turn(store, "json")

    dsl_meta = json.loads((dsl_turn.root / "meta.json").read_text(encoding="utf-8"))
    json_meta = json.loads((json_turn.root / "meta.json").read_text(encoding="utf-8"))
    assert dsl_meta["generator"] == "dsl"
    assert json_meta["generator"] == "json"


def test_audit_writes_dsl_errors_for_a_failed_attempt(tmp_path):
    store = AuditStore(
        AuditSettings(mode="full", directory=tmp_path / "audit", keep=10)
    )
    audit = _turn(store, "dsl")

    audit.write_attempt(
        1,
        user_prompt="Draw a square.",
        reply=ModelReply(data={}, raw_text="import os\n", model="mock"),
        dsl_errors=["line 1: imports are not part of the dialect."],
    )

    dsl = json.loads(
        (audit.root / "attempts/01/dsl.json").read_text(encoding="utf-8")
    )
    meta = json.loads(
        (audit.root / "attempts/01/meta.json").read_text(encoding="utf-8")
    )
    assert dsl == ["line 1: imports are not part of the dialect."]
    assert meta["dsl_error_count"] == 1
    assert (
        audit.root / "attempts/01/raw.txt"
    ).read_text(encoding="utf-8") == "import os\n"


# -- OpenAI-compatible transport --------------------------------------------


class _Completion:
    def __init__(self, content: str):
        message = SimpleNamespace(content=content)
        self.choices = [SimpleNamespace(message=message, finish_reason="stop")]
        self.model = "fake-model"
        self.usage = SimpleNamespace(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        )


class _Client:
    def __init__(self, content: str):
        self.calls = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )
        self._content = content

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return _Completion(self._content)


def _provider(content: str) -> OpenAICompatProvider:
    config = replace(
        resolve_config("mock"),
        base_url="http://example.invalid/v1",
        model="test-model",
        timeout_s=5.0,
        max_retries=0,
    )
    provider = OpenAICompatProvider(config, api_key="test-key-never-logged")
    provider.client = _Client(content)
    return provider


def test_openai_compat_dsl_returns_raw_text_without_json_parsing():
    module = '```python\n@on_flag(target="Sprite1")\ndef go():\n    move(10)\n```'
    provider = _provider(module)

    reply = provider.complete(
        ModelRequest(request_id=1, system="s", user="u", reply_format="dsl")
    )

    assert reply.data == {}
    assert reply.raw_text == module
    assert reply.finish_reason == "stop"
    assert reply.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert "response_format" not in provider.client.calls[0]


def test_openai_compat_json_path_still_parses_and_requests_an_object():
    provider = _provider('```json\n{"ok": true}\n```')

    reply = provider.complete(ModelRequest(request_id=1, system="s", user="u"))

    assert reply.data == {"ok": True}
    assert provider.client.calls[0]["response_format"] == {"type": "json_object"}


# -- user prompt mode awareness ------------------------------------------------


def test_user_prompt_registry_hint_and_tail_follow_the_generator():
    from harness.context import ProjectContext, ScriptSummary
    from harness.prompts import build_user_prompt

    context = ProjectContext.demo()
    context.sprites["Sprite1"].scripts.append(
        ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label="draw_square",
            hat="EventHatMorph",
            block_count=5,
            owned=True,
        )
    )

    json_prompt = build_user_prompt("make it bigger", context)
    dsl_prompt = build_user_prompt("make it bigger", context, generator="dsl")

    assert (
        "Scripts (use the id for replace_script/delete_script):" in json_prompt
    )
    assert "Return the JSON change set now." in json_prompt
    assert (
        "Scripts (replace one by putting its script_id on the event decorator;"
        " delete_script(script_id) removes):" in dsl_prompt
    )
    assert (
        "Return the Scratch-Python module now, in one fenced python block."
        in dsl_prompt
    )
