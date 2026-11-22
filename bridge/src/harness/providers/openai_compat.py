"""OpenAI-compatible backend (OpenCode Go, DeepSeek direct, Ollama, ...)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from ..config import ConfigError, ModelConfig
from .base import BaseProvider, ModelReply, ModelRequest, ProviderError, parse_json_object

try:  # optional at runtime: the mock path must work without the SDK
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        OpenAI,
        PermissionDeniedError,
        RateLimitError,
        UnprocessableEntityError,
    )
except ImportError:  # pragma: no cover - exercised only without the SDK
    OpenAI = None  # type: ignore[assignment]
    APIConnectionError = APITimeoutError = APIStatusError = ()  # type: ignore[assignment]
    AuthenticationError = PermissionDeniedError = BadRequestError = ()  # type: ignore[assignment]
    RateLimitError = UnprocessableEntityError = ()  # type: ignore[assignment]


#: Our own logger. One line per transport attempt; never prompts or secrets.
logger = logging.getLogger("harness.provider")

#: First backoff, doubled after every retry (before jitter).
_BACKOFF_BASE_S = 0.5


def _sleep(seconds: float) -> None:
    """Sleep helper, kept as a module function so tests can monkeypatch it."""
    if seconds > 0:
        time.sleep(seconds)


def _backoff_seconds(retry_number: int, retry_after: float | None) -> float:
    """Jittered exponential backoff, or the server's requested delay.

    ``retry_number`` starts at 1 for the first retry: about 0.5s, then 1.5s.
    The jitter is a small random addition, so parallel turns do not stampede.
    """
    if retry_after is not None:
        return max(0.0, float(retry_after))
    base = _BACKOFF_BASE_S * (2 ** max(0, retry_number - 1))
    return base + random.uniform(0.0, 0.5 * base)


def _retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    for key in ("retry-after", "Retry-After", "x-ratelimit-reset-requests"):
        raw = headers.get(key)
        if raw is None:
            continue
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            continue
    return None


def map_error(exc: Exception) -> ProviderError:
    """Translate an SDK/socket exception into a stable ``ProviderError``.

    Classification is by exception class name as well as isinstance, so tests
    can inject lightweight stand-ins without importing the SDK.
    """
    if isinstance(exc, ProviderError):
        return exc

    name = type(exc).__name__
    status = getattr(exc, "status_code", None)
    retry_after = _retry_after(exc)

    if isinstance(exc, AuthenticationError) or name in ("AuthenticationError", "PermissionDeniedError") or status in (401, 403):
        return ProviderError("auth", "the endpoint rejected the API key", status=status, detail=str(exc))
    if isinstance(exc, RateLimitError) or name == "RateLimitError" or status == 429:
        return ProviderError("rate_limit", "rate limited by the endpoint", status=status, retry_after=retry_after, detail=str(exc))
    if isinstance(exc, APITimeoutError) or name in ("APITimeoutError", "TimeoutError", "ReadTimeoutError") or status == 408:
        return ProviderError("timeout", "the model did not answer in time", status=status, detail=str(exc))
    if isinstance(exc, (APIConnectionError, ConnectionError, OSError)) or name in ("APIConnectionError", "ConnectionError", "ConnectionResetError"):
        return ProviderError("network", "could not reach the model endpoint", status=status, detail=str(exc))
    if isinstance(exc, UnprocessableEntityError) or status == 422:
        return ProviderError("bad_request", "the endpoint rejected the request", status=status, detail=str(exc))
    if isinstance(exc, BadRequestError) or status == 400:
        return ProviderError("bad_request", "the endpoint rejected the request", status=status, detail=str(exc))
    if isinstance(exc, APIStatusError) or (isinstance(status, int) and status >= 400):
        if isinstance(status, int) and status >= 500:
            return ProviderError("server", "the model endpoint failed", status=status, retry_after=retry_after, detail=str(exc))
        return ProviderError("bad_request", "the endpoint rejected the request", status=status, detail=str(exc))
    return ProviderError("network", "model call failed", detail=str(exc))


def _usage_text(usage: dict[str, int] | None) -> str:
    if not usage:
        return "-"
    return " ".join(f"{key}={value}" for key, value in usage.items())


def _reasoning_tokens(response: Any) -> int | None:
    """Reasoning tokens counted in the completion budget, when reported."""
    usage = getattr(response, "usage", None)
    details = getattr(usage, "completion_tokens_details", None) if usage else None
    value = getattr(details, "reasoning_tokens", None) if details else None
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def _cached_tokens(response: Any) -> int | None:
    """Prompt tokens served from the endpoint cache, when reported."""
    usage = getattr(response, "usage", None)
    details = getattr(usage, "prompt_tokens_details", None) if usage else None
    value = getattr(details, "cached_tokens", None) if details else None
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


class OpenAICompatProvider(BaseProvider):
    """Any OpenAI-compatible ``/chat/completions`` endpoint."""

    name = "openai-compat"

    def __init__(self, config: ModelConfig, api_key: str | None = None):
        super().__init__(config)
        if OpenAI is None:
            raise ConfigError("the 'openai' package is not installed. Run: pip install openai")
        try:
            key = api_key if api_key is not None else config.api_key()
        except ConfigError as exc:
            raise ProviderError("auth", str(exc)) from exc
        self._api_key = key
        self.client = OpenAI(
            api_key=key,
            base_url=config.base_url,
            timeout=config.timeout_s,
            # Our own taxonomy owns retries; the SDK must not add a second,
            # invisible retry budget on top of it.
            max_retries=0,
            default_headers={
                "x-opencode-session": config.session_id,
                "User-Agent": "scratch-ai-harness/0.1",
            },
        )

    def __repr__(self) -> str:
        # Deliberately excludes ``_api_key``; safe to print anywhere.
        return (
            f"{type(self).__name__}(model={self.config.model!r}, "
            f"base_url={self.config.base_url!r})"
        )

    # The legacy attribute names are used by examples/tests.
    @property
    def model(self) -> str:
        return self.config.model

    @property
    def base_url(self) -> str:
        return self.config.base_url

    def _kwargs(self, request: ModelRequest) -> dict[str, Any]:
        config: ModelConfig = self.config
        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        # The JSON change-set contract wants an object back.  A DSL reply is a
        # fenced Python module, so an endpoint-enforced JSON object would
        # contradict the prompt and the transpiler.
        if request.reply_format != "dsl":
            kwargs["response_format"] = {"type": "json_object"}
        # "off" must be sent explicitly.  Omitting the field lets a reasoning
        # model spend the whole completion budget on hidden reasoning and return
        # an empty ``content`` (finish_reason=length), which looks like bad JSON.
        # We also keep the previous opt-in shape for low/high/max.
        thinking = str(config.thinking or "off").strip().lower()
        if thinking in {"off", "none", "disabled", "false"}:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        else:
            # Only some endpoints accept this; ``complete`` drops it and retries
            # once on a 400 that names it.
            kwargs["extra_body"] = {
                "thinking": {"type": "enabled"},
                "reasoning_effort": config.thinking,
            }
        return kwargs

    def _client_with_timeout(self, timeout: float) -> Any:
        """A per-attempt client view. Never mutates ``self.client``.

        ``with_options`` returns a shallow copy in the OpenAI SDK, so parallel
        requests can carry different timeouts safely.
        """
        try:
            option = getattr(self.client, "with_options", None)
            if callable(option):
                return option(timeout=timeout)
        except Exception:  # pragma: no cover - defensive for odd client doubles
            pass
        return self.client

    @staticmethod
    def _remaining(deadline: float | None) -> float | None:
        return None if deadline is None else deadline - time.monotonic()

    def complete(self, request: ModelRequest) -> ModelReply:
        """Call the endpoint, retrying only transport failures.

        Retry budget: ``config.max_retries`` retries (so at most
        ``max_retries + 1`` transport attempts). Only ``retryable`` errors are
        retried; auth/bad_request/bad_json/cancelled fail immediately.

        Two bounded compatibility fallbacks run before that: a 400 naming
        ``response_format`` retries without it, and a 400 naming the thinking /
        reasoning controls retries without ``extra_body``.
        """
        started = time.monotonic()
        kwargs = self._kwargs(request)
        max_retries = max(0, int(self.config.max_retries))
        attempts = 0
        retries_used = 0
        response_format_dropped = False
        thinking_dropped = False

        while True:
            attempt_number = attempts + 1
            remaining = self._remaining(request.deadline)
            if remaining is not None and remaining <= 0:
                raise ProviderError(
                    "timeout",
                    f"turn budget exhausted before attempt {attempt_number}",
                )

            timeout = float(self.config.timeout_s)
            if remaining is not None:
                timeout = min(timeout, remaining)
            client = self._client_with_timeout(timeout)

            attempt_started = time.monotonic()
            attempts += 1
            try:
                response = client.chat.completions.create(**kwargs)
            except Exception as exc:  # noqa: BLE001 - classified below
                error = map_error(exc)
                attempt_latency = int((time.monotonic() - attempt_started) * 1000)
                logger.info(
                    "provider request=%s model=%s attempt=%s latency_ms=%s outcome=%s",
                    request.request_id,
                    self.config.model,
                    attempts,
                    attempt_latency,
                    error.code,
                )

                if (
                    error.code == "bad_request"
                    and not response_format_dropped
                    and "response_format" in kwargs
                    and "response_format" in str(exc)
                ):
                    # Some compatible endpoints reject response_format; the
                    # prompt already asks for JSON, so try once without it.
                    # Bounded: this branch can run at most once per request.
                    response_format_dropped = True
                    kwargs.pop("response_format", None)
                    continue

                text = str(exc).lower()
                if (
                    error.code == "bad_request"
                    and not thinking_dropped
                    and "extra_body" in kwargs
                    and (
                        "thinking" in text
                        or "reasoning" in text
                        or "extra_body" in text
                    )
                ):
                    # Some OpenAI-compatible endpoints do not understand the
                    # thinking controls.  Drop them and retry once; the model
                    # then uses its own default.
                    thinking_dropped = True
                    kwargs.pop("extra_body", None)
                    continue

                if error.retryable and retries_used < max_retries:
                    retries_used += 1
                    delay = _backoff_seconds(retries_used, error.retry_after)
                    left = self._remaining(request.deadline)
                    if left is not None:
                        if left <= 0:
                            raise ProviderError(
                                "timeout",
                                f"turn budget exhausted before attempt {attempts + 1}",
                            ) from exc
                        if delay >= left:
                            # Shorten the wait to the remaining budget; the next
                            # loop turn then reports the exhausted deadline.
                            delay = left
                    _sleep(delay)
                    continue

                error.attempts = attempts  # type: ignore[attr-defined]
                logger.warning(
                    "provider request=%s model=%s attempts=%s failed code=%s status=%s",
                    request.request_id,
                    self.config.model,
                    attempts,
                    error.code,
                    error.status,
                )
                raise error from exc

            try:
                reply = self._parse_response(response, request, attempts, started)
            except ProviderError as error:
                attempt_latency = int((time.monotonic() - attempt_started) * 1000)
                # bad_json is deliberately NOT retried at the transport layer:
                # the agent's repair loop owns malformed/empty payloads.
                logger.info(
                    "provider request=%s model=%s attempt=%s latency_ms=%s outcome=%s",
                    request.request_id,
                    self.config.model,
                    attempts,
                    attempt_latency,
                    error.code,
                )
                logger.warning(
                    "provider request=%s model=%s attempts=%s failed code=%s status=%s",
                    request.request_id,
                    self.config.model,
                    attempts,
                    error.code,
                    error.status,
                )
                error.attempts = attempts  # type: ignore[attr-defined]
                raise

            attempt_latency = int((time.monotonic() - attempt_started) * 1000)
            logger.info(
                "provider request=%s model=%s attempt=%s latency_ms=%s outcome=ok usage=%s",
                request.request_id,
                self.config.model,
                attempts,
                attempt_latency,
                _usage_text(reply.usage),
            )
            return reply

    def _parse_response(
        self,
        response: Any,
        request: ModelRequest,
        attempts: int,
        started: float,
    ) -> ModelReply:
        latency_ms = int((time.monotonic() - started) * 1000)
        choice = response.choices[0] if getattr(response, "choices", None) else None
        finish_reason = getattr(choice, "finish_reason", None)
        content = getattr(getattr(choice, "message", None), "content", None)
        reasoning_tokens = _reasoning_tokens(response)
        cached_tokens = _cached_tokens(response)

        usage = None
        raw_usage = getattr(response, "usage", None)
        if raw_usage is not None:
            usage = {
                key: int(value)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                if (value := getattr(raw_usage, key, None)) is not None
            }

        if not content:
            message = "the model returned an empty response"
            if finish_reason == "length":
                message = (
                    "the model used the entire output budget before returning "
                    "content (finish_reason=length); increase max_tokens or "
                    "reduce the requested change set"
                )
            raise ProviderError(
                "bad_json",
                message,
                raw_text="",
                finish_reason=finish_reason,
                reasoning_tokens=reasoning_tokens,
                content_chars=0,
                cached_tokens=cached_tokens,
            )

        if request.reply_format == "dsl":
            # The raw module is the payload; the agent transpiles it.  No JSON
            # parse, but the usage/latency/finish diagnostics are identical.
            data: dict[str, Any] = {}
        else:
            try:
                data = parse_json_object(content)
            except ProviderError as exc:
                # Keep the exact content and budget diagnostics for the audit
                # bundle.  The transport layer still does not retry bad_json; the
                # agent's repair loop owns it.
                exc.raw_text = content
                exc.finish_reason = finish_reason
                exc.reasoning_tokens = reasoning_tokens
                exc.content_chars = len(content)
                exc.cached_tokens = cached_tokens
                raise
        thinking = str(self.config.thinking or "off").strip().lower()
        if reasoning_tokens and reasoning_tokens > 0 and thinking in {"off", "none", "disabled", "false"}:
            # The endpoint ignored the disable control: reasoning is eating the
            # completion budget the JSON change set needs.  Diagnostics only.
            logger.warning(
                "provider request=%s model=%s reasoning_tokens=%s despite thinking=off; "
                "the model may ignore the thinking-disable control and consume the output budget",
                request.request_id,
                self.config.model,
                reasoning_tokens,
            )
        return ModelReply(
            data=data,
            model=getattr(response, "model", None) or self.config.model,
            latency_ms=latency_ms,
            usage=usage,
            attempts=attempts,
            finish_reason=finish_reason,
            raw_text=content,
            reasoning_tokens=reasoning_tokens,
            cached_tokens=cached_tokens,
        )
