"""Deterministic providers for tests and offline demos."""

from __future__ import annotations

import time
from typing import Any

from .base import BaseProvider, ModelReply, ModelRequest, ProviderError


class MockLLM:
    """Deterministic LLM for tests and offline demos.

    Kept behaviour-compatible with the original ``harness.llm.MockLLM``:
    ``calls`` records every ``(system, user)`` pair and responses are consumed
    in order.
    """

    name = "mock"

    def __init__(self, responses: list[dict[str, Any]] | None = None):
        self.responses = list(responses or [])
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        self.calls.append((system, user))
        if not self.responses:
            raise ProviderError("bad_json", "MockLLM has no responses left", retryable=False)
        return self.responses.pop(0)


class DelayedLLM:
    """Wrap an LLM and sleep before answering, for async-send tests."""

    name = "delayed"

    def __init__(self, inner: Any, delay_seconds: float):
        self.inner = inner
        self.delay_seconds = float(delay_seconds)

    def complete(self, request: ModelRequest) -> ModelReply:
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        inner = self.inner
        if hasattr(inner, "complete"):
            return inner.complete(request)
        started = time.monotonic()
        data = inner.complete_json(request.system, request.user)
        return ModelReply(
            data=data,
            model=getattr(inner, "model", "mock"),
            latency_ms=int((time.monotonic() - started) * 1000),
            attempts=request.attempt,
        )

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        return self.inner.complete_json(system, user)


class MockProvider(BaseProvider):
    """A real provider (rich interface) driven by canned responses."""

    name = "mock"

    def __init__(self, responses: list[dict[str, Any]] | None = None, config: Any = None):
        super().__init__(config)
        self.responses = list(responses or [])
        self.calls: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelReply:
        self.calls.append(request)
        started = time.monotonic()
        if not self.responses:
            raise ProviderError("bad_json", "mock provider has no responses left", retryable=False)
        data = self.responses.pop(0)
        return ModelReply(
            data=data,
            model="mock",
            latency_ms=int((time.monotonic() - started) * 1000),
            attempts=request.attempt,
            finish_reason="stop",
        )
