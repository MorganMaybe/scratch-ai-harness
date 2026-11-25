from __future__ import annotations

import argparse
import asyncio
import copy
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .agent import Agent, AgentResult, CancelToken
from .audit import AuditSettings, AuditStore, default_audit_dir
from .config import (
    ConfigError,
    MODEL_CHOICE_PROFILES,
    MODEL_CHOICES,
    ModelConfig,
    resolve_config,
    resolve_generator,
    resolve_history,
    with_overrides,
)
from .context import ProjectContext
from .history import ConversationHistory
from .llm import DelayedLLM
from .obs import bridge_info, bridge_options, bridge_usage, setup_logging
from .providers.base import ProviderError
from .providers.factory import build_provider
from .providers.replay import CachingProvider, RecordingProvider, ReplayProvider
from .protocol import ProtocolError, Sym, make_message, message_type, parse_literal, read_frame, encode_frame
from .validator import ValidationError

log = logging.getLogger("harness.server")

_CANCELLED_MESSAGE = "request cancelled by the client"
#: ``last_error`` is a one-line diagnostic for ``#info``.  Keep it short and
#: free of prompts, keys and tracebacks.
_MAX_ERROR_CHARS = 200


@dataclass(frozen=True)
class _ConfigSnapshot:
    """The config fields ``obs.bridge_info`` needs, without a live ModelConfig."""

    profile: str = ""
    model: str = ""
    base_url: str = ""


@dataclass
class Bridge:
    """Threaded request handler with per-request agent state.

    ``agent`` is the *template* agent.  It is kept so existing callers (and the
    image's diagnostics) can read ``bridge.agent.context`` /
    ``bridge.agent.registry``, but it is only a per-turn cache and never
    authoritative: every request carries the full project snapshot and
    ``handle`` builds a fresh ``Agent`` from that snapshot.  Only the underlying
    ``llm``/provider is shared between requests.

    ``pending`` exists solely to acknowledge a change set.  It maps a request id
    to ``(AgentResult, created_monotonic, request_text)``; entries older than
    ``pending_ttl_s`` are swept when the next message is handled, and an
    ``#applied`` for an unknown/expired id is still acknowledged with ``#ok``.
    The stored request text lets ``#applied`` append the turn to the conversation
    history without re-reading the wire.

    ``max_concurrent`` bounds simultaneous agent turns with a
    ``threading.BoundedSemaphore`` because ``handle`` runs in a worker thread
    (``asyncio.to_thread``), not on the event loop.

    ``cancel`` uses the ``_active`` map of per-request :class:`CancelToken`\\ s.
    Cancellation is cooperative: it stops the turn before its next model
    attempt/repair, but it cannot abort an HTTP call already in flight.

    ``profile``/``model``/``base_url`` mirror the resolved configuration for
    ``#info``.  They default to ``""`` so a hand-built test bridge never
    invents values.
    """

    agent: Agent
    pending: dict[int, tuple[AgentResult, float]] | None = None
    max_concurrent: int = 2
    pending_ttl_s: float = 600.0
    #: Overall budget for one turn, including repairs. The image's async worker
    #: waits 300 s; this stays inside it so the bridge always answers first.
    turn_budget_s: float = 240.0
    clock: Callable[[], float] = time.monotonic
    #: Configuration descriptor for ``#info`` (never secrets).
    profile: str = ""
    model: str = ""
    base_url: str = ""
    #: Resolved config, kept so the Usage page can switch model ids in place.
    #: ``None`` for a hand-built test bridge (switching is then unavailable).
    model_config: ModelConfig | None = None
    #: ``(model id, label)`` pairs offered by ``#selectModel``.  Empty disables
    #: the switcher; the image selects one by its 1-based position.
    model_choices: tuple[tuple[str, str], ...] = ()
    #: Short, safe diagnostic for the last failed request ("" after a success).
    last_error: str = ""
    #: Per-turn audit bundles.  "off" writes nothing; "meta" writes the index and
    #: outcome; "full" also writes prompts, raw model replies, project context
    #: and compiled output under ``audit_dir``.
    audit_mode: str = "off"
    audit_dir: str | None = None
    audit_keep: int = 100
    #: Safe, read-only model options for the image's ``#options`` reply.
    timeout_s: float = 0.0
    max_retries: int = 0
    max_tokens: int = 0
    thinking: str = "off"
    log_file: str = ""
    #: Key *presence* only.  The value itself is never stored on the bridge.
    api_key_env: str = ""
    api_key_present: bool = False
    #: Cumulative token usage for the life of this bridge process.
    usage_prompt_tokens: int = 0
    usage_completion_tokens: int = 0
    usage_total_tokens: int = 0
    usage_requests: int = 0
    #: Model actually used by the last completed turn ("" before the first).
    last_model: str = ""
    #: Bounded, process-local conversation memory.  One bridge serves one image
    #: session and the wire carries no session id, so process lifetime is the
    #: honest v1 scope.  ``__post_init__`` creates one unless a caller supplies
    #: a store (tests, the ladder runner).
    history: ConversationHistory | None = None
    #: ``HARNESS_HISTORY`` / ``[harness] history``; ``None`` resolves it once at
    #: construction.  False records nothing and renders no section, leaving
    #: prompts byte-identical to the pre-history bridge.
    history_enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.pending is None:
            self.pending = {}
        if self.max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        if self.history is None:
            self.history = ConversationHistory()
        if self.history_enabled is None:
            self.history_enabled = resolve_history()
        self._semaphore = threading.BoundedSemaphore(self.max_concurrent)
        self._state_lock = threading.Lock()
        # Guards ``_active``; a separate lock keeps cancellation from waiting
        # on pending/template bookkeeping.
        self._active_lock = threading.Lock()
        self._active: dict[int, CancelToken] = {}
        # The template's demo context is the fallback for requests without a
        # context element.  Publish only copies to the template so a late
        # #applied can never mutate a snapshot a live request is using.
        self._demo_context = self.agent.context
        settings = AuditSettings(
            mode=self.audit_mode,
            directory=Path(self.audit_dir) if self.audit_dir else default_audit_dir(),
            keep=self.audit_keep,
        )
        self._audit = AuditStore(settings) if settings.enabled else None

    def handle(self, message: Any) -> list[list[Any]]:
        kind = message_type(message)
        self.sweep_pending()
        if kind == "hello":
            return [[Sym("hello-ok"), "ScratchAI/1"]]
        if kind == "ping":
            return [[Sym("pong")]]
        if kind == "applied":
            request_id = int(message[1])
            result = self._take_pending(request_id)
            if result is not None:
                self._register_applied(result)
            return [[Sym("ok"), request_id]]
        if kind == "request":
            return self._handle_request(message)
        if kind == "cancel":
            return self._handle_cancel(message)
        if kind == "info":
            return self._handle_info()
        if kind == "options":
            return [bridge_options(self)]
        if kind == "usage":
            return [bridge_usage(self)]
        if kind == "models":
            return [self._handle_models()]
        if kind == "selectModel":
            return [self._handle_select_model(message)]
        raise ProtocolError(f"unknown message type: {kind}")

    def cancel(self, request_id: int) -> bool:
        """Mark a currently running request as cancelled.

        Returns ``True`` when a matching turn is registered, ``False`` for an
        unknown or already-finished id.  This never raises: a client cancelling
        a request that just finished is normal.
        """
        with self._active_lock:
            token = self._active.get(request_id)
            if token is None:
                return False
            # Mark while holding the map lock so cleanup cannot interleave
            # between the lookup and the flag store.
            token.cancel()
        log.info("request id=%s cancelled", request_id)
        return True

    def _handle_cancel(self, message: Any) -> list[list[Any]]:
        if len(message) < 2:
            raise ProtocolError("cancel needs a request id")
        try:
            request_id = int(message[1])
        except (TypeError, ValueError) as exc:
            raise ProtocolError("cancel request id must be an integer") from exc
        if self.cancel(request_id):
            return [[Sym("ok"), request_id]]
        return [[Sym("error"), request_id, "not running"]]

    def _handle_info(self) -> list[list[Any]]:
        """Reply used by ``tools/ai_control.py bridge-status``.

        Exactly nine elements: selector, protocol, profile, model, base_url,
        turn budget, concurrency, live pending count, last short error.
        ``obs.bridge_info`` is the single source of that shape, so the client
        and the server cannot drift.
        """
        snapshot = _ConfigSnapshot(self.profile, self.model, self.base_url)
        return [bridge_info(snapshot, self)]

    def _handle_models(self) -> list[Any]:
        """List the switchable models and the one currently configured.

        Exact contract::

            #(models #(id label) ... active_model)

        An empty choice list means this profile has no switcher.
        """
        return [
            Sym("models"),
            *[[model_id, label] for model_id, label in self.model_choices],
            self.model,
        ]

    def _handle_select_model(self, message: Any) -> list[Any]:
        """Switch the shared provider to the 1-based index the image sent."""
        if len(message) < 2:
            raise ProtocolError("selectModel needs an index")
        try:
            index = int(message[1])
        except (TypeError, ValueError) as exc:
            raise ProtocolError("selectModel index must be an integer") from exc
        selected = self.select_model(index)
        if selected is None:
            if not self.model_choices or self.model_config is None:
                return [Sym("modelError"), "model switching is unavailable"]
            return [Sym("modelError"), f"unknown model index {index}"]
        model_id, label = selected
        return [Sym("model"), model_id, label]

    def select_model(self, index: int) -> tuple[str, str] | None:
        """Switch the provider to ``model_choices[index - 1]``.

        Returns ``(model_id, label)`` on success, ``None`` when switching is
        unavailable or the index is out of range.  The switch applies to later
        turns; an HTTP call already in flight keeps its built request.  Only ids
        from :attr:`model_choices` are accepted, never client text.
        """
        with self._state_lock:
            choices = self.model_choices
            config = self.model_config
            if not choices or config is None:
                return None
            if index < 1 or index > len(choices):
                return None
            model_id, label = choices[index - 1]
            if model_id == config.model:
                self.model = model_id
                return model_id, label
            new_config = with_overrides(config, model=model_id)
            if not _apply_provider_config(self.agent.llm, new_config):
                return None
            self.model_config = new_config
            self.model = model_id
            self.max_tokens = new_config.max_tokens
            self.thinking = new_config.thinking
        log.info("model switched: id=%s label=%s", model_id, label)
        return model_id, label

    def _register_active(self, request_id: int, token: CancelToken) -> None:
        with self._active_lock:
            self._active[request_id] = token

    def _unregister_active(self, request_id: int, token: CancelToken) -> None:
        with self._active_lock:
            # Identity check: a duplicate id from another connection must not
            # be removed by this turn's cleanup.
            if self._active.get(request_id) is token:
                del self._active[request_id]

    def _note_error(self, code: str, message: str) -> None:
        """Record a short safe diagnostic without prompts, keys or tracebacks."""
        text = " ".join(str(message).split())
        if len(text) > _MAX_ERROR_CHARS:
            text = text[: _MAX_ERROR_CHARS - 3] + "..."
        with self._state_lock:
            self.last_error = f"{code}: {text}" if text else code

    def _record_usage(self, result: AgentResult) -> None:
        """Add one completed turn's token usage to the cumulative counters.

        Called while ``_state_lock`` is held.  Missing usage fields count as
        zero; ``total_tokens`` falls back to prompt + completion.  The numbers
        are per bridge process and reset on restart.
        """
        usage = result.usage or {}
        try:
            prompt = int(usage.get("prompt_tokens", 0) or 0)
        except (TypeError, ValueError):
            prompt = 0
        try:
            completion = int(usage.get("completion_tokens", 0) or 0)
        except (TypeError, ValueError):
            completion = 0
        try:
            total = int(usage.get("total_tokens", 0) or 0)
        except (TypeError, ValueError):
            total = 0
        if total <= 0:
            total = prompt + completion
        self.usage_prompt_tokens += max(prompt, 0)
        self.usage_completion_tokens += max(completion, 0)
        self.usage_total_tokens += max(total, 0)
        self.usage_requests += 1
        if result.model:
            self.last_model = result.model

    def sweep_pending(self, now: float | None = None) -> list[int]:
        """Drop ``#applied`` acknowledgements older than ``pending_ttl_s``."""
        current = self.clock() if now is None else now
        pending = self.pending
        assert pending is not None
        with self._state_lock:
            expired = [
                request_id
                for request_id, (_, created, _request) in pending.items()
                if current - created > self.pending_ttl_s
            ]
            for request_id in expired:
                del pending[request_id]
        return expired

    def _take_pending(self, request_id: int) -> AgentResult | None:
        pending = self.pending
        assert pending is not None
        with self._state_lock:
            entry = pending.pop(request_id, None)
            # Ack-gated recording: only a result the image confirmed applied
            # enters history.  Failed turns never reach ``#applied``.
            if entry is not None and self.history_enabled and self.history is not None:
                result, _created, request = entry
                try:
                    self.history.record_result(request, result)
                except Exception:  # a history bug must never break an ack
                    log.warning("event=history.record_failed", exc_info=True)
        return entry[0] if entry is not None else None

    def _register_applied(self, result: AgentResult) -> None:
        """Update the template's per-turn cache only.

        This is **not** authoritative state: the next request rebuilds its
        context and registry from the snapshot the image sends.
        """
        with self._state_lock:
            self.agent.register_applied(result)

    def _publish_template_context(self, context: ProjectContext) -> None:
        snapshot = copy.deepcopy(context)
        with self._state_lock:
            self.agent.use_context(snapshot)

    def _handle_request(self, message: list[Any]) -> list[list[Any]]:
        if len(message) < 3:
            raise ProtocolError("request needs id and prompt")
        request_id = int(message[1])
        prompt = _join_lines(message[2])
        target = _text(message[3]) if len(message) > 3 else ""
        context_literal = message[4] if len(message) > 4 else None
        context = self.agent.context if self.agent.context is not None else self._demo_context
        # Legacy/demo path only: a context-less client has no snapshot to rebuild
        # from, so it keeps the template's accumulating registry (the pre-Phase-3
        # behaviour the offline demos rely on). Snapshot-carrying requests always
        # get a fresh registry built from their own context.
        registry = self.agent.registry
        if len(message) > 4 and message[4] is not None:
            try:
                context = ProjectContext.from_literal(message[4])
            except ValueError as exc:
                raise ProtocolError(f"invalid project context: {exc}") from exc
            if target:
                context.target = target
            registry = None
            self._publish_template_context(context)

        # One audit bundle per request.  It is created before the model call so
        # a crash during the turn still leaves the request, prompt and context
        # on disk.  ``None`` when auditing is off or the directory is unusable.
        audit = None
        if self._audit is not None:
            audit = self._audit.start_turn(
                request_id=request_id,
                prompt=prompt,
                target=target or context.target,
                context=context,
                profile=self.profile,
                model=self.model,
                base_url=self.base_url,
                turn_budget_s=self.turn_budget_s,
                context_literal=context_literal,
                generator=resolve_generator(),
            )

        # Fresh agent per request: only the provider and the conversation store
        # are shared.  A request can therefore never mutate another request's
        # context or registry.
        token = CancelToken()
        agent = Agent(
            self.agent.llm,
            context,
            registry=registry,
            cancel_token=token,
            audit=audit,
            history=self.history if self.history_enabled else None,
        )
        started = self.clock()
        # The deadline must use the real monotonic clock, not the injectable
        # ``clock`` used for pending TTL bookkeeping in tests.
        deadline = time.monotonic() + self.turn_budget_s if self.turn_budget_s > 0 else None
        outcome = "error:internal"
        changes = 0
        attempts: int | None = None
        cancelled = False
        result: AgentResult | None = None
        error_text = ""
        # Register before the turn (including any wait for the semaphore) so a
        # queued request can be cancelled too.  Cleanup is unconditional.
        self._register_active(request_id, token)
        try:
            try:
                with self._semaphore:
                    result = agent.handle(prompt, request_id, deadline=deadline)
                    if token.cancelled:
                        # The model answered after the client cancelled: throw
                        # the reply away instead of publishing a result.  Do not
                        # let the audit outcome claim the discarded reply.
                        result = None
                        raise ProviderError("cancelled", _CANCELLED_MESSAGE)
            except ValidationError as exc:
                outcome = "error:validation"
                attempts = exc.attempts or 0
                # The wire is a Smalltalk literal array: a newline cannot be
                # encoded and would disconnect the image instead of reporting
                # the issues.  Collapse each issue (diagnostics can carry a
                # quoted source line) and keep every issue, joined on one line.
                detail = _validation_detail(exc.issues)
                error_text = detail
                self._note_error("validation", detail)
                return [[Sym("error"), request_id, detail]]
            except ProviderError as exc:
                outcome = f"error:{exc.code}"
                cancelled = exc.code == "cancelled"
                error_text = exc.user_message()
                self._note_error(exc.code, exc.message)
                return [[Sym("error"), request_id, error_text]]
            except Exception as exc:
                # Let the client handler log the traceback and answer with the
                # generic message, but make sure the audit index records the
                # failed turn.
                outcome = "error:internal"
                error_text = f"internal bridge error ({type(exc).__name__})"
                raise
            if token.cancelled:
                # Cancellation landed between the semaphore release and the
                # acknowledgement: still never emit a #result.
                cancelled = True
                result = None
                outcome = "error:cancelled"
                error_text = _CANCELLED_MESSAGE
                self._note_error("cancelled", _CANCELLED_MESSAGE)
                error = ProviderError("cancelled", _CANCELLED_MESSAGE)
                return [[Sym("error"), request_id, error.user_message()]]
            pending = self.pending
            assert pending is not None
            with self._state_lock:
                pending[request_id] = (result, self.clock(), prompt)
                self.last_error = ""
                self._record_usage(result)
            outcome = "ok"
            attempts = result.attempts
            changes = len(result.compiled.changes)
            lines = result.compiled.chat_summary().splitlines()
            for warning in result.lint_warnings:
                lines.append(f"warning: {warning}")
            return [
                [Sym("result"), request_id, lines, result.compiled.apply_structure(request_id)],
            ]
        finally:
            self._unregister_active(request_id, token)
            elapsed_ms = int((self.clock() - started) * 1000)
            if audit is not None:
                audit.finish(
                    outcome=outcome,
                    attempts=attempts or 0,
                    changes=changes,
                    elapsed_ms=elapsed_ms,
                    error=error_text,
                    result=result,
                )
            extra = ""
            if attempts is not None:
                extra += f" attempts={attempts}"
            if cancelled:
                extra += " cancelled=1"
            log.info(
                "request id=%s outcome=%s changes=%d elapsed_ms=%d%s",
                request_id,
                outcome,
                changes,
                elapsed_ms,
                extra,
            )


def _apply_provider_config(provider: Any, config: ModelConfig) -> bool:
    """Replace ``config`` on a provider and any wrapper it delegates to.

    Wrappers (delay, cache, record) expose ``inner`` but may not expose the
    resolved config themselves.  Returns true when at least one config-bearing
    provider was updated, so a frozen legacy double cannot silently claim a
    switch.  A visited set guards against accidental wrapper cycles.
    """
    seen: set[int] = set()
    updated = False
    while provider is not None and id(provider) not in seen:
        seen.add(id(provider))
        if getattr(provider, "config", None) is not None:
            provider.config = config
            updated = True
        provider = getattr(provider, "inner", None)
    return updated


def _validation_detail(issues: list[Any]) -> str:
    """One wire-safe line for a validation failure.

    Diagnostics may carry a quoted source line and a hint on the next line; a
    newline cannot be encoded in a Smalltalk literal, so collapse whitespace
    rather than lose the whole reply.
    """
    text = "; ".join(" ".join(str(issue).split()) for issue in issues)
    return text or "invalid change set"


def _join_lines(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return "\n".join(value)
    raise ProtocolError("prompt must be a string or an array of lines")


def _text(value: Any) -> str:
    if isinstance(value, Sym):
        return value.name
    if isinstance(value, str):
        return value
    return ""


def _request_id(message: Any) -> int:
    """Best-effort request id for a failure reply (never the old hardcoded 0)."""
    try:
        if message is not None and len(message) > 1 and message_type(message) in ("request", "applied"):
            return int(message[1])
    except (TypeError, ValueError, IndexError):
        pass
    return 0


class BridgeServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765, bridge: Bridge | None = None):
        self.host = host
        self.port = port
        self.bridge = bridge or default_bridge()
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._client, self.host, self.port)
        sockets = ", ".join(str(sock.getsockname()) for sock in (self._server.sockets or []))
        log.info("bridge listening on %s", sockets)

    async def serve_forever(self) -> None:
        if self._server is None:
            await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        log.info("client connected: %s", peer)
        try:
            while True:
                payload = await read_frame(reader)
                text = payload.decode("utf-8", errors="replace")
                log.debug("recv: %s", text)
                message: Any = None
                try:
                    message = parse_literal(text)
                    # The LLM call is blocking; run it off the event loop so a
                    # long model call does not freeze other connections (an
                    # async send's #applied acknowledgement, for example).
                    responses = await asyncio.to_thread(self.bridge.handle, message)
                except (ProtocolError, ValueError, ValidationError) as exc:
                    # Error text becomes a Smalltalk string literal: collapse
                    # newlines so a multi-line message cannot kill the client.
                    detail = " ".join(str(exc).split()) or "request failed"
                    responses = [[Sym("error"), _request_id(message), detail]]
                except Exception:  # model/runtime failure: answer, do not drop the client
                    # Full detail (with traceback) goes to the log; the wire
                    # message stays short and cannot leak a key or a prompt.
                    log.exception("request handling failed")
                    responses = [[Sym("error"), _request_id(message), "internal bridge error; see the bridge log"]]
                for response in responses:
                    try:
                        data = make_message(*response)
                        frame = encode_frame(data)
                    except Exception:
                        # Last line of defence: never let one unprintable reply
                        # tear down a client connection.
                        log.exception("response serialization failed")
                        fallback = [
                            Sym("error"),
                            _request_id(message),
                            "internal bridge error: reply could not be encoded",
                        ]
                        data = make_message(*fallback)
                        frame = encode_frame(data)
                    log.debug("send: %s", data)
                    writer.write(frame)
                await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        except ConnectionResetError:
            pass
        except Exception:  # pragma: no cover - defensive
            log.exception("client error")
        finally:
            log.info("client disconnected: %s", peer)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


def default_bridge(
    mock: bool | None = None,
    config: ModelConfig | None = None,
    provider: Any = None,
    *,
    audit_mode: str = "off",
    audit_dir: str | None = None,
    audit_keep: int = 100,
) -> Bridge:
    """Build a bridge from a resolved profile (never from env-only defaults)."""
    context = ProjectContext.demo()
    if config is None and provider is None:
        config = resolve_config(profile="mock" if mock else None)
    if provider is None:
        provider = build_provider(config)
    bridge = Bridge(
        Agent(provider, context),
        audit_mode=audit_mode,
        audit_dir=audit_dir,
        audit_keep=audit_keep,
    )
    # ``#info`` mirrors the resolved configuration.  Without a config (a
    # caller-supplied provider) the fields stay "" rather than guessing.
    if config is not None:
        bridge.profile = config.profile
        bridge.model = config.model
        bridge.base_url = config.base_url
        bridge.model_config = config
        if config.profile in MODEL_CHOICE_PROFILES:
            bridge.model_choices = MODEL_CHOICES
        bridge.timeout_s = config.timeout_s
        bridge.max_retries = config.max_retries
        bridge.max_tokens = config.max_tokens
        bridge.thinking = config.thinking
        bridge.api_key_env = config.api_key_env
        try:
            bridge.api_key_present = config.has_api_key()
        except Exception:  # pragma: no cover - defensive
            bridge.api_key_present = False
    return bridge


def main() -> None:
    parser = argparse.ArgumentParser(description="Scratch AI bridge")
    parser.add_argument("--profile", help="model profile name (opencode-go, deepseek-direct, local, mock)")
    parser.add_argument("--config", help="path to harness.ini (default: bridge/harness.ini)")
    parser.add_argument("--model", help="override the profile's model id")
    parser.add_argument("--base-url", dest="base_url", help="override the profile's endpoint")
    parser.add_argument("--timeout", type=float, help="per-attempt timeout in seconds")
    parser.add_argument("--retries", type=int, help="transport retries per attempt")
    parser.add_argument("--live", action="store_true", help="deprecated: use the default live profile (same as --profile with no name)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--delay", type=float, default=0.0, help="sleep N seconds before each LLM reply (async-send testing)")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--log-file", help="structured bridge log (default: scratch/base/bridge.log)")
    parser.add_argument("--no-log-file", action="store_true", help="log to stderr only")
    parser.add_argument("--replay", metavar="FILE", help="answer from a recorded JSONL fixture instead of the model")
    parser.add_argument("--record", metavar="FILE", help="append every model reply to a JSONL fixture")
    parser.add_argument("--cache", action="store_true", help="cache identical prompts in memory (development)")
    parser.add_argument("--prompt-budget", type=int, metavar="CHARS", help="prompt/context budget (default 90000)")
    parser.add_argument(
        "--audit",
        choices=("off", "meta", "full"),
        default="off",
        help="per-turn audit bundles: off, meta (index/outcome) or full (prompts + raw replies)",
    )
    parser.add_argument(
        "--audit-dir",
        help="audit bundle directory (default: scratch/base/audit)",
    )
    parser.add_argument(
        "--audit-keep",
        type=int,
        default=100,
        help="keep at most N full turn bundles; 0 keeps all (default 100)",
    )
    args = parser.parse_args()

    log_path = False if args.no_log_file else (args.log_file or None)
    resolved_log = setup_logging(args.log_level, log_file=log_path, stream=True)

    if args.prompt_budget is not None:
        if args.prompt_budget <= 0:
            print("bridge: --prompt-budget must be > 0", file=sys.stderr)
            raise SystemExit(2)
        os.environ["HARNESS_PROMPT_BUDGET"] = str(args.prompt_budget)

    if args.profile:
        profile = args.profile
    elif args.live:
        profile = None  # resolve the default live profile: ini/env, else opencode-go
    else:
        profile = "mock"  # keep the original offline default for bare `python -m harness.server`

    try:
        config = resolve_config(
            profile,
            args.config,
            model=args.model,
            base_url=args.base_url,
            timeout=args.timeout,
            retries=args.retries,
        )
        if args.replay:
            # Replay must work with no key and no network: do not construct a
            # live provider just to throw it away.
            provider = ReplayProvider(args.replay)
        else:
            provider = build_provider(config)
        if args.cache:
            provider = CachingProvider(provider)
        if args.record:
            provider = RecordingProvider(provider, args.record)
        bridge = default_bridge(
            config=config,
            provider=provider,
            audit_mode=args.audit,
            audit_dir=args.audit_dir,
            audit_keep=args.audit_keep,
        )
    except (ConfigError, ProviderError) as exc:
        print(f"bridge: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    log.info("model config: %s", config.describe())
    if args.audit != "off":
        audit_path = Path(args.audit_dir) if args.audit_dir else default_audit_dir()
        log.info(
            "turn audit: mode=%s dir=%s keep=%d",
            args.audit,
            audit_path,
            args.audit_keep,
        )
    if resolved_log is not None:
        bridge.log_file = str(resolved_log)
        log.info("structured log: %s", resolved_log)
    if args.replay:
        log.info("replay fixtures: %s", args.replay)
    if args.record:
        log.info("recording replies to: %s", args.record)
    if args.delay > 0:
        bridge.agent.llm = DelayedLLM(bridge.agent.llm, args.delay)
    server = BridgeServer(args.host, args.port, bridge)
    try:
        asyncio.run(server.serve_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
