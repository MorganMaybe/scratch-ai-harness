"""Transport retry, timeout and error-taxonomy tests (offline)."""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from harness.config import resolve_config
from harness.providers import openai_compat
from harness.providers.base import ModelRequest, ProviderError, parse_json_object
from harness.providers.openai_compat import OpenAICompatProvider

API_KEY = "oc_sk_test_secret_never_log_me"


# --- Fake SDK exception stand-ins (classified by class name). ---------------


class _FakeResponse:
    def __init__(self, status_code: int, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.headers = dict(headers or {})


class RateLimitError(Exception):
    def __init__(self, message: str = "rate limited", *, status_code: int = 429, retry_after: float | None = None):
        super().__init__(message)
        self.status_code = status_code
        headers = {} if retry_after is None else {"retry-after": str(retry_after)}
        self.response = _FakeResponse(status_code, headers)


class AuthenticationError(Exception):
    def __init__(self, message: str = "bad key", *, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code
        self.response = _FakeResponse(status_code)


class APITimeoutError(Exception):
    def __init__(self, message: str = "timed out"):
        super().__init__(message)
        self.status_code = None
        self.response = None


class APIConnectionError(Exception):
    def __init__(self, message: str = "connection reset"):
        super().__init__(message)
        self.status_code = None
        self.response = None


class APIStatusError(Exception):
    def __init__(self, message: str = "server failed", *, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code
        self.response = _FakeResponse(status_code)


class BadRequestError(Exception):
    def __init__(self, message: str = "bad request", *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
        self.response = _FakeResponse(status_code)


# --- Fake OpenAI client -----------------------------------------------------


class FakeCompletion:
    def __init__(
        self,
        content: str = '{"ok": true}',
        *,
        model: str = "fake-model",
        finish_reason: str = "stop",
        with_usage: bool = True,
        reasoning_tokens: int | None = None,
    ):
        message = SimpleNamespace(content=content)
        self.choices = [SimpleNamespace(message=message, finish_reason=finish_reason)]
        self.model = model
        details = (
            SimpleNamespace(reasoning_tokens=reasoning_tokens)
            if reasoning_tokens is not None
            else None
        )
        self.usage = (
            SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                completion_tokens_details=details,
            )
            if with_usage
            else None
        )


class FakeClient:
    """Minimal ``client.chat.completions.create`` double."""

    def __init__(self, outcomes: list[object], *, delay: float = 0.0):
        self._outcomes = list(outcomes)
        self.delay = delay
        self.calls: list[dict[str, object]] = []
        self.timeouts: list[float] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: object) -> FakeCompletion:
        self.calls.append(kwargs)
        if self.delay:
            time.sleep(self.delay)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, FakeCompletion)
        return outcome

    def with_options(self, **kwargs: object) -> "FakeClient":
        self.timeouts.append(float(kwargs["timeout"]))  # type: ignore[arg-type]
        return self


def make_provider(*, retries: int = 2, timeout: float = 5.0) -> OpenAICompatProvider:
    config = replace(
        resolve_config("mock"),
        base_url="http://example.invalid/v1",
        model="test-model",
        timeout_s=timeout,
        max_retries=retries,
    )
    return OpenAICompatProvider(config, api_key=API_KEY)


def make_request(*, request_id: int = 1, deadline: float | None = None) -> ModelRequest:
    return ModelRequest(
        request_id=request_id,
        system="SYSTEM PROMPT BODY",
        user="USER PROMPT BODY",
        deadline=deadline,
    )


@pytest.fixture(autouse=True)
def sleeps(monkeypatch):
    """Never actually sleep; record the requested backoff values."""
    recorded: list[float] = []
    monkeypatch.setattr(openai_compat, "_sleep", lambda seconds: recorded.append(seconds))
    return recorded


# --- Retryable failures -----------------------------------------------------


def test_rate_limit_then_success():
    provider = make_provider(retries=2)
    provider.client = FakeClient([RateLimitError(), FakeCompletion()])

    reply = provider.complete(make_request())

    assert reply.attempts == 2
    assert reply.data == {"ok": True}
    assert len(provider.client.calls) == 2


def test_server_error_then_success():
    provider = make_provider(retries=2)
    provider.client = FakeClient([APIStatusError(status_code=500), FakeCompletion()])

    reply = provider.complete(make_request())

    assert reply.attempts == 2
    assert len(provider.client.calls) == 2


def test_timeout_then_success():
    provider = make_provider(retries=2)
    provider.client = FakeClient([APITimeoutError(), FakeCompletion()])

    reply = provider.complete(make_request())

    assert reply.attempts == 2


def test_network_error_then_success():
    provider = make_provider(retries=2)
    provider.client = FakeClient([APIConnectionError(), FakeCompletion()])

    reply = provider.complete(make_request())

    assert reply.attempts == 2


def test_retries_exhausted_uses_full_budget():
    provider = make_provider(retries=2)
    provider.client = FakeClient(
        [APIStatusError(status_code=500), APIStatusError(status_code=503), APIStatusError(status_code=502)]
    )

    with pytest.raises(ProviderError) as caught:
        provider.complete(make_request())

    assert caught.value.code == "server"
    assert caught.value.attempts == 3  # max_retries + 1
    assert len(provider.client.calls) == 3


# --- Terminal failures are never retried ------------------------------------


def test_auth_error_is_not_retried():
    provider = make_provider(retries=2)
    provider.client = FakeClient([AuthenticationError(), FakeCompletion()])

    with pytest.raises(ProviderError) as caught:
        provider.complete(make_request())

    assert caught.value.code == "auth"
    assert caught.value.retryable is False
    assert len(provider.client.calls) == 1


def test_bad_request_is_not_retried():
    provider = make_provider(retries=2)
    provider.client = FakeClient([BadRequestError(), FakeCompletion()])

    with pytest.raises(ProviderError) as caught:
        provider.complete(make_request())

    assert caught.value.code == "bad_request"
    assert len(provider.client.calls) == 1


# --- Backoff and deadline ---------------------------------------------------


def test_retry_after_is_honoured(sleeps):
    provider = make_provider(retries=2)
    provider.client = FakeClient([RateLimitError(retry_after=3), FakeCompletion()])

    reply = provider.complete(make_request())

    assert reply.attempts == 2
    assert sleeps[0] == pytest.approx(3.0)


def test_max_retries_zero_makes_one_attempt(sleeps):
    provider = make_provider(retries=0)
    provider.client = FakeClient([RateLimitError(), FakeCompletion()])

    with pytest.raises(ProviderError) as caught:
        provider.complete(make_request())

    assert caught.value.code == "rate_limit"
    assert len(provider.client.calls) == 1
    assert sleeps == []


def test_deadline_already_expired_calls_nothing():
    provider = make_provider(retries=2)
    provider.client = FakeClient([FakeCompletion()])

    with pytest.raises(ProviderError) as caught:
        provider.complete(make_request(deadline=time.monotonic() - 0.01))

    assert caught.value.code == "timeout"
    assert "before attempt 1" in str(caught.value)
    assert provider.client.calls == []


def test_per_attempt_timeout_is_capped_by_deadline():
    provider = make_provider(retries=1, timeout=30.0)
    provider.client = FakeClient([FakeCompletion()])

    reply = provider.complete(make_request(deadline=time.monotonic() + 5.0))

    assert reply.attempts == 1
    assert provider.client.timeouts
    assert 0 < provider.client.timeouts[0] <= 5.0


# --- Payload failures are not transport-retried -----------------------------


def test_empty_content_is_bad_json_without_retry():
    provider = make_provider(retries=2)
    provider.client = FakeClient([FakeCompletion("")])

    with pytest.raises(ProviderError) as caught:
        provider.complete(make_request())

    assert caught.value.code == "bad_json"
    assert caught.value.raw_text == ""
    assert len(provider.client.calls) == 1


def test_malformed_json_is_bad_json_without_retry():
    provider = make_provider(retries=2)
    provider.client = FakeClient([FakeCompletion("this is not json")])

    with pytest.raises(ProviderError) as caught:
        provider.complete(make_request())

    assert caught.value.code == "bad_json"
    assert caught.value.raw_text == "this is not json"
    assert len(provider.client.calls) == 1


def test_fenced_json_still_parses():
    provider = make_provider(retries=2)
    provider.client = FakeClient([FakeCompletion('```json\n{"ok": true}\n```')])

    reply = provider.complete(make_request())

    assert reply.data == {"ok": True}
    assert reply.attempts == 1


# --- JSON salvage for common model malformations ----------------------------


def test_strict_json_object_still_parses():
    assert parse_json_object('{"ok": true}') == {"ok": True}


def test_fenced_json_object_is_unwrapped_before_parsing():
    assert parse_json_object('```json\n{"ok": true}\n```') == {"ok": True}


def test_trailing_comma_before_array_close_is_salvaged():
    data = parse_json_object('{"items": [1, 2, 3,]}')

    assert data == {"items": [1, 2, 3]}


def test_trailing_comma_before_object_close_is_salvaged():
    data = parse_json_object('{"ok": true,}')

    assert data == {"ok": True}


def test_raw_newline_inside_string_value_is_salvaged():
    data = parse_json_object('{"summary": "line one\nline two"}')

    assert data == {"summary": "line one\nline two"}


def test_prose_fence_trailing_comma_and_control_char_are_salvaged_together():
    reply = (
        "Here is the change set:\n"
        '```json\n{"summary": "a\tb", "changes": [1, 2,],}\n```\n'
        "Let me know if you want more."
    )

    data = parse_json_object(reply)

    assert data == {"summary": "a\tb", "changes": [1, 2]}


def test_salvage_leaves_string_contents_unchanged():
    data = parse_json_object('{"note": "keep, ] and, } as text", "items": [1, 2,]}')

    assert data == {"note": "keep, ] and, } as text", "items": [1, 2]}


def test_salvage_respects_backslash_escapes():
    data = parse_json_object('{"note": "a \\"quote\\" and \\\\ slash", "items": [1, 2,]}')

    assert data == {"note": 'a "quote" and \\ slash', "items": [1, 2]}


def test_backslash_before_raw_newline_is_salvaged():
    data = parse_json_object('{"summary": "line one\\\nline two", "items": [1, 2,]}')

    assert data == {"summary": "line one\nline two", "items": [1, 2]}


def test_top_level_array_is_still_rejected():
    with pytest.raises(ProviderError) as caught:
        parse_json_object('[{"ok": true}]')

    assert caught.value.code == "bad_json"
    assert "not an object" in caught.value.message


def test_top_level_array_with_trailing_comma_is_still_rejected():
    with pytest.raises(ProviderError) as caught:
        parse_json_object("[1, 2,]")

    assert caught.value.code == "bad_json"


# --- Thinking / reasoning controls ------------------------------------------


def test_kwargs_default_to_thinking_disabled():
    provider = make_provider()

    kwargs = provider._kwargs(make_request())

    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_kwargs_enable_reasoning_when_configured():
    provider = make_provider()
    provider.config = replace(provider.config, thinking="low")

    kwargs = provider._kwargs(make_request())

    assert kwargs["extra_body"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
    }


def test_thinking_rejection_drops_extra_body_and_retries():
    provider = make_provider(retries=0)
    provider.client = FakeClient(
        [BadRequestError("unknown field 'thinking'"), FakeCompletion()]
    )

    reply = provider.complete(make_request())

    assert reply.data == {"ok": True}
    assert len(provider.client.calls) == 2
    assert "extra_body" in provider.client.calls[0]
    assert "extra_body" not in provider.client.calls[1]


def test_empty_length_response_reports_budget_diagnostics():
    provider = make_provider()
    provider.client = FakeClient([FakeCompletion("", finish_reason="length")])

    with pytest.raises(ProviderError) as caught:
        provider.complete(make_request())

    error = caught.value
    assert error.code == "bad_json"
    assert "output budget" in error.message
    assert error.finish_reason == "length"
    assert error.content_chars == 0
    assert error.raw_text == ""


def test_success_reports_reasoning_and_cached_tokens():
    provider = make_provider()
    completion = FakeCompletion()
    completion.usage.completion_tokens_details = SimpleNamespace(reasoning_tokens=7)
    completion.usage.prompt_tokens_details = SimpleNamespace(cached_tokens=9)
    provider.client = FakeClient([completion])

    reply = provider.complete(make_request())

    assert reply.reasoning_tokens == 7
    assert reply.cached_tokens == 9


def test_reasoning_tokens_with_thinking_off_logs_one_warning(caplog):
    caplog.set_level(logging.WARNING, logger="harness.provider")
    provider = make_provider()
    provider.config = replace(provider.config, thinking="off")
    provider.client = FakeClient([FakeCompletion(reasoning_tokens=16384)])

    reply = provider.complete(make_request())

    assert reply.reasoning_tokens == 16384
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.name == "harness.provider" and record.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    assert "reasoning_tokens=16384 despite thinking=off" in warnings[0]
    assert "consume the output budget" in warnings[0]
    assert "SYSTEM PROMPT BODY" not in warnings[0]
    assert "USER PROMPT BODY" not in warnings[0]


@pytest.mark.parametrize("reasoning_tokens", [0, None])
def test_no_reasoning_tokens_with_thinking_off_does_not_warn(caplog, reasoning_tokens):
    caplog.set_level(logging.WARNING, logger="harness.provider")
    provider = make_provider()
    provider.config = replace(provider.config, thinking="off")
    provider.client = FakeClient([FakeCompletion(reasoning_tokens=reasoning_tokens)])

    reply = provider.complete(make_request())

    assert reply.reasoning_tokens == reasoning_tokens
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "despite thinking=off" not in text


# --- Metadata and logging ---------------------------------------------------


def test_success_populates_usage_latency_and_finish_reason():
    provider = make_provider(retries=2)
    provider.client = FakeClient([FakeCompletion(finish_reason="stop")], delay=0.01)

    reply = provider.complete(make_request())

    assert reply.attempts == 1
    assert reply.model == "fake-model"
    assert reply.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert reply.finish_reason == "stop"
    assert reply.latency_ms >= 5
    assert reply.raw_text == '{"ok": true}'


def test_key_and_prompts_never_appear_in_logs(caplog):
    caplog.set_level(logging.INFO, logger="harness.provider")
    provider = make_provider(retries=1)
    provider.client = FakeClient([RateLimitError(), FakeCompletion()])

    provider.complete(make_request())

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "oc_sk_" not in text
    assert "Authorization" not in text
    assert "SYSTEM PROMPT BODY" not in text
    assert "USER PROMPT BODY" not in text
    assert "attempt=1" in text
    assert "attempt=2" in text
    assert "outcome=ok" in text
    assert API_KEY not in repr(provider)


def test_legacy_complete_json_still_works():
    provider = make_provider(retries=2)
    provider.client = FakeClient([FakeCompletion()])

    data = provider.complete_json("system", "user")

    assert data == {"ok": True}
    assert provider.client.calls
    assert provider.client.calls[0]["model"] == "test-model"


def test_provider_error_user_message_is_one_line():
    error = ProviderError("timeout", "first line\nsecond line")

    message = error.user_message()

    assert "\n" not in message
    assert "first line second line" in message
