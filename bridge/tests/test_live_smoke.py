"""Opt-in live smoke tests. Never run by the offline suite unless opted in.

Run explicitly with::

    $env:DEEPSEEK_API_KEY = "..."   # or load bridge\\.deepseek_key first
    python -m pytest -q tests/test_live_smoke.py -m live

Total live calls: at most two. The key is never printed or asserted on.
"""

from __future__ import annotations

import dataclasses
import os
import time

import pytest

from harness.config import resolve_config
from harness.providers.base import ModelRequest, ProviderError
from harness.providers.factory import build_provider

pytestmark = pytest.mark.live


def _skip_without_key() -> str:
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        pytest.skip(
            "DEEPSEEK_API_KEY is not set; live smoke tests are opt-in. "
            "Set the key (or let run_live.ps1 load bridge\\.deepseek_key) and re-run."
        )
    return key


def test_live_complete_tiny_reply():
    """One cheap real call: tiny max_tokens, trivial JSON prompt."""
    _skip_without_key()
    config = dataclasses.replace(resolve_config("opencode-go"), max_tokens=32, max_retries=0)
    provider = build_provider(config)
    request = ModelRequest(
        request_id=910001,
        system="Reply with a JSON object only.",
        user='Return exactly {"ok": true}',
    )

    started = time.monotonic()
    try:
        reply = provider.complete(request)
    except ProviderError as exc:
        # A clean, classified failure is acceptable for a smoke test; a crash
        # or malformed error is not.
        elapsed_ms = int((time.monotonic() - started) * 1000)
        assert exc.code in {"auth", "rate_limit", "timeout", "network", "server", "bad_request", "bad_json"}
        print(
            f"model={config.model} outcome=error code={exc.code} "
            f"status={exc.status} latency_ms={elapsed_ms}"
        )
        return

    assert isinstance(reply.data, dict)
    assert reply.latency_ms >= 0
    print(
        f"model={reply.model} usage={reply.usage} latency_ms={reply.latency_ms} "
        f"attempts={reply.attempts}"
    )


def test_live_bad_key_is_auth_without_retry():
    """The endpoint is reachable and a 401-shaped config fails fast, once."""
    _skip_without_key()
    # Terminal errors must not consume the retry budget.
    config = dataclasses.replace(resolve_config("opencode-go"), max_retries=2)
    provider = build_provider(config, api_key="sk-live-smoke-invalid-000000000000000000")
    request = ModelRequest(
        request_id=910002,
        system="Reply with a JSON object only.",
        user='Return exactly {"ok": true}',
    )

    started = time.monotonic()
    with pytest.raises(ProviderError) as caught:
        provider.complete(request)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    error = caught.value

    assert error.code == "auth", (
        f"expected auth from a bad key (endpoint reachable), got {error.code!r}: {error.message}"
    )
    # One call, no retry: the provider records the attempt count on failure.
    assert error.attempts == 1, f"auth must not be retried, attempts={error.attempts}"
    print(f"model={config.model} outcome=auth attempts={error.attempts} latency_ms={elapsed_ms}")
