"""DSL stop-sequence plumbing: dsl only, flag-gated, off by default."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from harness.config import resolve_config
from harness.providers.base import ModelRequest
from harness.providers.openai_compat import OpenAICompatProvider

API_KEY = "oc_sk_test_secret_never_log_me"

DSL_REPLY = '```python\nsummary("Moved the crab left.")\n```'
JSON_REPLY = '{"summary": "Moved the crab left.", "changes": []}'


class _Completion:
    def __init__(self, content: str):
        message = SimpleNamespace(content=content)
        self.choices = [SimpleNamespace(message=message, finish_reason="stop")]
        self.model = "fake-model"
        self.usage = None


class _Client:
    """Minimal ``client.chat.completions.create`` double that records payloads."""

    def __init__(self, content: str):
        self._content = content
        self.calls: list[dict[str, object]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: object) -> _Completion:
        self.calls.append(kwargs)
        return _Completion(self._content)

    def with_options(self, **kwargs: object) -> "_Client":
        return self


def make_provider(content: str) -> OpenAICompatProvider:
    config = replace(
        resolve_config("mock"),
        base_url="http://example.invalid/v1",
        model="test-model",
    )
    provider = OpenAICompatProvider(config, api_key=API_KEY)
    provider.client = _Client(content)
    return provider


def posted_payload(
    provider: OpenAICompatProvider, *, reply_format: str, stop=None
) -> dict[str, object]:
    request = ModelRequest(
        request_id=1,
        system="SYSTEM PROMPT BODY",
        user="USER PROMPT BODY",
        reply_format=reply_format,
        stop=stop,
    )
    provider.complete(request)
    return provider.client.calls[0]


def test_dsl_with_flag_on_sends_the_stop_sequence(monkeypatch):
    monkeypatch.setenv("HARNESS_STOP_SEQUENCE", "on")
    provider = make_provider(DSL_REPLY)

    payload = posted_payload(provider, reply_format="dsl")

    assert payload["stop"] == ["\n```"]


def test_dsl_with_flag_off_sends_no_stop_key(monkeypatch):
    monkeypatch.setenv("HARNESS_STOP_SEQUENCE", "off")
    provider = make_provider(DSL_REPLY)

    payload = posted_payload(provider, reply_format="dsl")

    assert "stop" not in payload


def test_json_with_flag_on_sends_no_stop_key(monkeypatch):
    monkeypatch.setenv("HARNESS_STOP_SEQUENCE", "on")
    provider = make_provider(JSON_REPLY)

    payload = posted_payload(provider, reply_format="json")

    assert "stop" not in payload


def test_explicit_request_stop_overrides_the_derived_value(monkeypatch):
    monkeypatch.setenv("HARNESS_STOP_SEQUENCE", "on")
    provider = make_provider(DSL_REPLY)

    payload = posted_payload(provider, reply_format="dsl", stop=("\nEND",))

    assert payload["stop"] == ["\nEND"]


def test_empty_explicit_stop_sends_no_stop_key(monkeypatch):
    monkeypatch.setenv("HARNESS_STOP_SEQUENCE", "on")
    provider = make_provider(DSL_REPLY)

    payload = posted_payload(provider, reply_format="dsl", stop=())

    assert "stop" not in payload
