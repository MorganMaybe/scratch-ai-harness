"""Replay fixtures, response recording, and a small in-memory cache.

All three providers are standard-library only: constructing them never needs an
API key and never opens a network connection. They exist so a development turn
can be recorded once and replayed deterministically afterwards.

Fixture format (one JSON object per line)::

    {"key": "<sha256 prefix>", "model": "...", "usage": {...},
     "finish_reason": "stop", "latency_ms": 12, "attempts": 1,
     "data": {"summary": "...", "changes": [...]}}

Only the prompt *hash* is stored. Prompts, system prompts, project context, and
API keys never reach the fixture.

DSL recordings add the raw module text, because that is their payload::

     {"key": "...", "data": {}, "raw_text": "@on_flag(...)\ndef ..."}
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

from .base import BaseProvider, ModelReply, ModelRequest, ProviderError

logger = logging.getLogger(__name__)

#: Fields written into every fixture line, in a stable order.
FIXTURE_FIELDS = (
    "key",
    "model",
    "usage",
    "finish_reason",
    "latency_ms",
    "attempts",
    "data",
)


def prompt_key(request: ModelRequest) -> str:
    """A stable sha256 of the system and user prompts (first 32 hex chars)."""
    digest = hashlib.sha256()
    digest.update((request.system or "").encode("utf-8"))
    digest.update(b"\x00")
    digest.update((request.user or "").encode("utf-8"))
    return digest.hexdigest()[:32]


def _reply_entry(request: ModelRequest, reply: ModelReply) -> dict[str, Any]:
    entry = {
        "key": prompt_key(request),
        "model": str(reply.model or ""),
        "usage": dict(reply.usage) if reply.usage is not None else None,
        "finish_reason": reply.finish_reason,
        "latency_ms": int(reply.latency_ms or 0),
        "attempts": int(reply.attempts or request.attempt or 1),
        "data": reply.data,
    }
    # A DSL reply's payload is the raw module; JSON recordings stay exactly as
    # they were so old fixtures and the documented format keep working.
    if request.reply_format == "dsl" and reply.raw_text is not None:
        entry["raw_text"] = reply.raw_text
    return entry


def write_fixture(path: str | Path, entry: dict[str, Any]) -> Path:
    """Append one fixture entry as a JSON line, creating parent directories."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ordered = {field: entry.get(field) for field in FIXTURE_FIELDS if field in entry}
    for key, value in entry.items():
        if key not in ordered:
            ordered[key] = value
    line = json.dumps(ordered, ensure_ascii=True, separators=(",", ":"))
    with open(target, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
    return target


def load_fixtures(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load a JSONL fixture file into ``{key: entry}``; a missing file is empty."""
    target = Path(path)
    entries: dict[str, dict[str, Any]] = {}
    if not target.exists():
        return entries
    with open(target, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                entry = json.loads(text)
            except json.JSONDecodeError:
                logger.warning("ignoring malformed replay fixture line %d in %s", number, target)
                continue
            if not isinstance(entry, dict):
                logger.warning("ignoring non-object replay fixture line %d in %s", number, target)
                continue
            key = entry.get("key")
            if not isinstance(key, str) or not key:
                logger.warning("ignoring replay fixture line %d without a key", number)
                continue
            entries[key] = entry
    return entries


def _complete_inner(inner: Any, request: ModelRequest) -> ModelReply:
    """Call the rich interface, falling back to legacy ``complete_json``."""
    complete = getattr(inner, "complete", None)
    if callable(complete):
        reply = complete(request)
        if isinstance(reply, ModelReply):
            return reply
        return ModelReply(data=reply, model=str(getattr(inner, "name", "") or ""))
    data = inner.complete_json(request.system, request.user)
    return ModelReply(data=data, model=str(getattr(inner, "name", "") or ""))


class RecordingProvider(BaseProvider):
    """Wrap a provider and append every successful reply to a JSONL fixture."""

    name = "recording"

    def __init__(self, inner: Any, path: str | Path, config: Any = None):
        super().__init__(config)
        self.inner = inner
        self.path = Path(path)
        self._lock = threading.Lock()

    def complete(self, request: ModelRequest) -> ModelReply:
        reply = _complete_inner(self.inner, request)
        entry = _reply_entry(request, reply)
        self._record(entry)
        return reply

    def _record(self, entry: dict[str, Any]) -> None:
        try:
            with self._lock:
                write_fixture(self.path, entry)
        except Exception as exc:  # pragma: no cover - exact OS error varies
            logger.warning("could not write replay fixture %s: %s", self.path, exc)


class ReplayProvider(BaseProvider):
    """Serve replies from a recorded fixture, keyed by the prompt hash."""

    name = "replay"

    def __init__(self, path: str | Path, config: Any = None):
        super().__init__(config)
        self.path = Path(path)
        self.entries = load_fixtures(self.path)
        #: Keys requested during this process that had no fixture.
        self.missing_keys: list[str] = []
        self._lock = threading.Lock()

    def complete(self, request: ModelRequest) -> ModelReply:
        key = prompt_key(request)
        entry = self.entries.get(key)
        if entry is None:
            with self._lock:
                self.missing_keys.append(key)
            raise ProviderError(
                "bad_json",
                "no replay fixture for this prompt",
                retryable=False,
            )
        if request.reply_format == "dsl":
            raw_text = entry.get("raw_text")
            if not isinstance(raw_text, str):
                raise ProviderError(
                    "replay",
                    "this replay recording has no raw DSL reply; re-record the "
                    "turn with generator=dsl so raw_text is stored",
                    retryable=False,
                )
            return ModelReply(
                data={},
                raw_text=raw_text,
                model=str(entry.get("model") or ""),
                latency_ms=0,
                usage=copy.deepcopy(entry.get("usage")),
                attempts=1,
                finish_reason=entry.get("finish_reason"),
            )
        return ModelReply(
            data=copy.deepcopy(entry.get("data")),
            model=str(entry.get("model") or ""),
            latency_ms=0,
            usage=copy.deepcopy(entry.get("usage")),
            attempts=1,
            finish_reason=entry.get("finish_reason"),
        )


class CachingProvider(BaseProvider):
    """An in-memory, thread-safe, FIFO response cache in front of a provider."""

    name = "caching"

    def __init__(self, inner: Any, max_entries: int = 64, config: Any = None):
        super().__init__(config)
        self.inner = inner
        self.max_entries = max(0, int(max_entries))
        self._entries: OrderedDict[str, ModelReply] = OrderedDict()
        self._lock = threading.Lock()
        #: Number of inner-provider calls that reached the wrapped provider.
        self.misses = 0
        self.hits = 0

    def complete(self, request: ModelRequest) -> ModelReply:
        key = prompt_key(request)
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self.hits += 1
                return cached
        self.misses += 1
        reply = _complete_inner(self.inner, request)
        if self.max_entries > 0:
            with self._lock:
                existing = self._entries.get(key)
                if existing is not None:
                    return existing
                while len(self._entries) >= self.max_entries:
                    self._entries.popitem(last=False)
                self._entries[key] = reply
        return reply

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
