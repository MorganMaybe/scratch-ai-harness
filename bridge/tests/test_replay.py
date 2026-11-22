from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

import pytest

from harness.providers.base import BaseProvider, ModelReply, ModelRequest, ProviderError
from harness.providers.replay import (
    CachingProvider,
    RecordingProvider,
    ReplayProvider,
    load_fixtures,
    prompt_key,
    write_fixture,
)

CANNED: dict[str, Any] = {
    "summary": "Added a green-flag square script.",
    "changes": [
        {
            "action": "add_script",
            "target": "Sprite1",
            "label": "draw_square",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "pen_clear"}, {"op": "pen_down"}],
        }
    ],
}
CANARY_SYSTEM = "SYSTEM-CANARY-alpha do not persist"
CANARY_USER = "USER-CANARY-beta oc_sk_should_never_leak"


def _reply() -> ModelReply:
    return ModelReply(
        data=json.loads(json.dumps(CANNED)),
        model="deepseek-v4.1-flash",
        latency_ms=12,
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        attempts=1,
        finish_reason="stop",
    )


class CannedProvider(BaseProvider):
    """A stateless, thread-safe provider returning one canned reply."""

    name = "canned"

    def __init__(self, reply: ModelReply | None = None, config: Any = None):
        super().__init__(config)
        self.reply = reply or _reply()
        self.calls = 0
        self._lock = threading.Lock()

    def complete(self, request: ModelRequest) -> ModelReply:
        with self._lock:
            self.calls += 1
        return self.reply


def _request(index: int = 1, system: str = "sys", user: str = "user") -> ModelRequest:
    return ModelRequest(request_id=index, system=system, user=user)


def test_record_then_replay_is_identical(tmp_path):
    path = tmp_path / "fixtures" / "turn-1.jsonl"
    recorder = RecordingProvider(CannedProvider(), path)
    first = recorder.complete(_request(system=CANARY_SYSTEM, user=CANARY_USER))

    assert path.exists()
    replay = ReplayProvider(path)
    second = replay.complete(_request(system=CANARY_SYSTEM, user=CANARY_USER))

    assert second.data == CANNED == first.data
    assert second.model == first.model == "deepseek-v4.1-flash"
    assert second.usage == first.usage
    assert second.finish_reason == "stop"
    assert second.latency_ms == 0
    assert second.attempts == 1


def test_replay_legacy_complete_json(tmp_path):
    path = tmp_path / "turn.jsonl"
    RecordingProvider(CannedProvider(), path).complete(_request())
    replay = ReplayProvider(path)
    assert replay.complete_json("sys", "user") == CANNED


def test_prompt_key_is_stable_and_sensitive():
    base = _request(1, "system text", "user text")
    assert prompt_key(base) == prompt_key(_request(2, "system text", "user text"))
    assert len(prompt_key(base)) == 32
    assert prompt_key(base) != prompt_key(_request(1, "system text!", "user text"))
    assert prompt_key(base) != prompt_key(_request(1, "system text", "user text!"))


def test_fixture_has_no_prompt_or_key_text(tmp_path):
    path = tmp_path / "turn.jsonl"
    recorder = RecordingProvider(CannedProvider(), path)
    recorder.complete(_request(system=CANARY_SYSTEM, user=CANARY_USER))

    raw = path.read_text(encoding="utf-8")
    assert "CANARY" not in raw
    assert "oc_sk_" not in raw
    assert CANARY_SYSTEM not in raw
    assert CANARY_USER not in raw
    entry = json.loads(raw.strip())
    assert entry["key"] == prompt_key(_request(system=CANARY_SYSTEM, user=CANARY_USER))
    assert set(entry) == {
        "key",
        "model",
        "usage",
        "finish_reason",
        "latency_ms",
        "attempts",
        "data",
    }


def test_missing_fixture_is_a_terminal_bad_json(tmp_path):
    replay = ReplayProvider(tmp_path / "does-not-exist.jsonl")
    request = _request(user="unrecorded")
    with pytest.raises(ProviderError) as info:
        replay.complete(request)
    assert info.value.code == "bad_json"
    assert info.value.retryable is False
    assert "no replay fixture" in info.value.message
    assert replay.missing_keys == [prompt_key(request)]


def test_caching_provider_calls_inner_once(tmp_path):
    inner = CannedProvider()
    cache = CachingProvider(inner)
    request = _request()
    first = cache.complete(request)
    second = cache.complete(request)
    assert inner.calls == 1
    assert first.data == second.data == CANNED
    assert len(cache) == 1


def test_caching_provider_evicts_fifo():
    inner = CannedProvider()
    cache = CachingProvider(inner, max_entries=2)
    requests = [_request(index, user=f"user-{index}") for index in range(3)]
    for request in requests:
        cache.complete(request)
    assert len(cache) == 2
    assert inner.calls == 3

    cache.complete(requests[0])  # first entry was evicted; inner is called again
    assert inner.calls == 4
    assert len(cache) == 2


def test_recording_is_thread_safe(tmp_path):
    path = tmp_path / "concurrent.jsonl"
    recorder = RecordingProvider(CannedProvider(), path)
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            recorder.complete(_request(index, system="sys", user=f"user-{index}"))
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 8
    entries = [json.loads(line) for line in lines]
    assert len({entry["key"] for entry in entries}) == 8
    for entry in entries:
        assert entry["data"] == CANNED
        assert entry["model"] == "deepseek-v4.1-flash"
        assert entry["usage"] == {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }


def test_recording_failure_does_not_fail_the_turn(tmp_path, caplog):
    # A directory is not a writable fixture file; recording must swallow the error.
    recorder = RecordingProvider(CannedProvider(), tmp_path)
    with caplog.at_level(logging.WARNING):
        reply = recorder.complete(_request())
    assert reply.data == CANNED
    assert any("could not write replay fixture" in message for message in caplog.messages)


def test_providers_construct_and_run_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    path = tmp_path / "keyless.jsonl"
    recorder = RecordingProvider(CannedProvider(), path)
    recorder.complete(_request())
    assert ReplayProvider(path).complete(_request()).data == CANNED
    assert CachingProvider(CannedProvider()).complete(_request()).data == CANNED


def test_load_fixtures_round_trip_and_missing_file(tmp_path):
    path = tmp_path / "fixtures.jsonl"
    entry = {
        "key": "abc123",
        "model": "m",
        "usage": None,
        "finish_reason": "stop",
        "latency_ms": 0,
        "attempts": 1,
        "data": CANNED,
    }
    write_fixture(path, entry)
    assert load_fixtures(path) == {"abc123": entry}
    assert load_fixtures(Path(tmp_path) / "missing.jsonl") == {}
