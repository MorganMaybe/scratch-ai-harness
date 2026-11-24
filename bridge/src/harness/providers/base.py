"""Provider seam: the types every model backend speaks.

This module is deliberately dependency-free (standard library only) so the
configuration layer, the bridge, and future local-model backends can all import
it without pulling in the OpenAI SDK.

Shape of the contract
---------------------
``ModelProvider.complete(ModelRequest) -> ModelReply`` is the rich interface:
it carries a request id, a deadline, usage, latency and attempt count.

``ModelProvider.complete_json(system, user) -> dict`` is the legacy interface
kept for compatibility with the original ``LLMClient`` protocol. New code
should use ``complete``; ``BaseProvider`` implements the legacy method on top
of the rich one so both agree.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

#: Failures worth another attempt: the same request may succeed later.
RETRYABLE_CODES = frozenset({"rate_limit", "timeout", "network", "server"})

#: Failures where retrying cannot help: bad credentials, bad request, bad
#: payload, or a caller-driven cancellation.
TERMINAL_CODES = frozenset({"auth", "bad_request", "bad_json", "cancelled", "replay"})

ALL_CODES = RETRYABLE_CODES | TERMINAL_CODES


class ProviderError(RuntimeError):
    """A model call failed, classified by a stable code.

    The code is for logs and tests; ``user_message()`` is the short, safe text
    that may be sent to the Scratch image. Neither ever contains the API key or
    the prompt body.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int | None = None,
        retry_after: float | None = None,
        detail: str | None = None,
        retryable: bool | None = None,
        attempts: int | None = None,
        raw_text: str | None = None,
        finish_reason: str | None = None,
        reasoning_tokens: int | None = None,
        content_chars: int | None = None,
        cached_tokens: int | None = None,
    ):
        if code not in ALL_CODES:
            raise ValueError(f"unknown provider error code: {code!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retry_after = retry_after
        self.detail = detail
        self._retryable = retryable
        #: Transport attempts made before giving up (set by the provider).
        self.attempts = attempts
        #: Exact model content when it failed to parse, so the audit bundle can
        #: show what was actually generated.  ``None`` when no content arrived.
        self.raw_text = raw_text
        #: Why generation stopped (``stop``, ``length``, ...) and how much of the
        #: completion budget went to hidden reasoning.  Both are diagnostics
        #: only; the wire message stays short.
        self.finish_reason = finish_reason
        self.reasoning_tokens = reasoning_tokens
        self.content_chars = content_chars
        #: Prompt tokens served from the endpoint's cache (not freshly
        #: processed).  A high value is normal: the system prompt is stable.
        self.cached_tokens = cached_tokens

    @property
    def retryable(self) -> bool:
        if self._retryable is not None:
            return self._retryable
        return self.code in RETRYABLE_CODES

    def user_message(self) -> str:
        """A one-line message safe to show in the Scratch chat log."""
        # The wire is a Smalltalk literal array; embedded newlines cannot be
        # encoded.  Keep the user-facing text to one line even if an upstream
        # error or test double supplied a multi-line message.
        text = " ".join(str(self.message).split())
        if self.status is not None:
            return f"model error ({self.code}, HTTP {self.status}): {text}"
        return f"model error ({self.code}): {text}"

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def __repr__(self) -> str:
        return f"ProviderError({self.code!r}, {self.message!r}, status={self.status!r})"


@dataclass
class ModelRequest:
    """One logical model call, shared by every attempt in a retry budget."""

    request_id: int
    system: str
    user: str
    attempt: int = 1
    #: ``time.monotonic()`` deadline for the whole turn, if any.
    deadline: float | None = None
    #: What the caller expects back: ``json`` (the change-set object) or
    #: ``dsl`` (one Scratch-Python module in ``ModelReply.raw_text``).
    reply_format: str = "json"
    #: The DSL stop sequence - a newline plus the closing-fence marker -
    #: requested so nothing can follow the module's closing fence.  Plumbed
    #: but OFF until a live ladder A/B shows the provider honours it without
    #: hurting prompt caching; the provider derives it when the flag is on.
    stop: tuple[str, ...] | None = None


@dataclass
class ModelReply:
    """A successful, parsed model reply plus the metadata we log."""

    data: dict[str, Any]
    model: str
    latency_ms: int = 0
    usage: dict[str, int] | None = None
    attempts: int = 1
    finish_reason: str | None = None
    #: Exact completion content, before JSON parsing.  Kept so the audit bundle
    #: can show what the model actually produced; never sent over the wire.
    raw_text: str | None = None
    #: Hidden reasoning tokens counted inside ``completion_tokens`` when the
    #: endpoint reports them.  Useful for spotting output-budget exhaustion.
    reasoning_tokens: int | None = None
    #: Prompt tokens served from the endpoint's cache when reported.
    cached_tokens: int | None = None


@runtime_checkable
class ModelProvider(Protocol):
    """What the bridge needs from any backend."""

    name: str

    def complete(self, request: ModelRequest) -> ModelReply:
        ...

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        ...


def remaining_seconds(deadline: float | None, now: float | None = None) -> float | None:
    """Seconds left before ``deadline``, or ``None`` when there is no deadline."""
    if deadline is None:
        return None
    import time

    return deadline - (time.monotonic() if now is None else now)


def expired(deadline: float | None, *, now: float | None = None) -> bool:
    left = remaining_seconds(deadline, now)
    return left is not None and left <= 0


def _strip_code_fences(text: str) -> str:
    """Remove leading/trailing Markdown fences, including repeated ones.

    Models sometimes wrap a reply in more than one fence (or close a fence twice).
    Stripping in a loop keeps the strict parse path working for those replies
    without touching fence-like text inside the JSON itself.
    """
    previous = None
    while previous != text:
        previous = text
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
        if text.endswith("```"):
            text = re.sub(r"\s*```$", "", text)
    return text


def _salvage_json_text(text: str) -> str:
    """Repair the malformed punctuation LLMs emit most often.

    Strict ``json.loads`` rejects trailing commas and raw control characters
    inside strings, yet models routinely leave a comma before ``]``/``}`` or
    paste a literal newline/tab into a string value.  A global regex would also
    rewrite matching punctuation *inside* string values, so this scan tracks
    string state and backslash escapes and only edits tokens outside strings.

    Returns the repaired text; validation is still left to ``json.loads``.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if in_string:
            if escaped:
                if ord(char) < 0x20:
                    # A backslash followed by a literal control character is
                    # not a valid escape; drop the dangling backslash so the
                    # escaped control form below can salvage it.
                    out.pop()
                    out.append(f"\\u{ord(char):04x}")
                else:
                    out.append(char)
                escaped = False
            elif char == "\\":
                out.append(char)
                escaped = True
            elif char == '"':
                out.append(char)
                in_string = False
            elif ord(char) < 0x20:
                # A raw control character cannot appear literally in JSON; the
                # escaped form is what the model meant to emit.
                out.append(f"\\u{ord(char):04x}")
            else:
                out.append(char)
        elif char == '"':
            out.append(char)
            in_string = True
        elif char == ",":
            lookahead = index + 1
            while lookahead < length and text[lookahead] in " \t\r\n":
                lookahead += 1
            if lookahead >= length or text[lookahead] not in "]}":
                out.append(char)
            # Otherwise drop the trailing comma before the closing container.
        else:
            out.append(char)
        index += 1
    return "".join(out)


def _parse_salvaged(candidates: tuple[str, ...], last_error: json.JSONDecodeError) -> Any:
    """Try each candidate as JSON after running the salvage scan.

    The candidates are ordered most- to least-specific (whole reply first, then
    the ``{...}`` slice).  If all fail, report the final error, matching the old
    behaviour where the slice's error was the one surfaced.
    """
    for candidate in candidates:
        try:
            return json.loads(_salvage_json_text(candidate))
        except json.JSONDecodeError as exc:
            last_error = exc
    raise ProviderError(
        "bad_json", f"model returned invalid JSON: {last_error.msg}"
    ) from last_error


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object, tolerating code fences, prose and common damage.

    Raises ``ProviderError('bad_json', ...)``. Callers must NOT retry this at the
    transport layer: the repair loop in ``agent.py`` owns malformed payloads.
    """
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = _strip_code_fences(raw)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ProviderError("bad_json", f"model did not return JSON: {exc.msg}") from exc
        sliced = raw[start : end + 1]
        try:
            value = json.loads(sliced)
        except json.JSONDecodeError as exc2:
            # Last resort: repair trailing commas / raw control characters on
            # the whole reply first, then on the narrowed object slice.
            value = _parse_salvaged((raw, sliced), exc2)
    if not isinstance(value, dict):
        raise ProviderError("bad_json", "model returned JSON that is not an object")
    return value


class BaseProvider:
    """Shared plumbing: config holder and the legacy ``complete_json`` bridge."""

    name = "base"

    def __init__(self, config: Any = None):
        self.config = config

    def complete(self, request: ModelRequest) -> ModelReply:  # pragma: no cover - abstract
        raise NotImplementedError

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        reply = self.complete(ModelRequest(request_id=0, system=system, user=user))
        return reply.data
