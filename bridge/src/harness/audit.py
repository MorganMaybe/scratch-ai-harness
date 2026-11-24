"""Per-turn audit bundles for diagnosing model output.

The bridge log deliberately never contains prompts, project context or model
completions: one redaction rule protects every line.  That is good for normal
operation and bad for debugging a turn that produced malformed or "garbled"
output.  This module is the separate, opt-in surface:

* ``meta``  — ``meta.json``, ``outcome.json`` and one ``index.jsonl`` line.
* ``full``  — everything above plus the exact prompts, project context, every
  model attempt (raw text before parsing), validation issues and compiled
  output.

The layout is intentionally stable so ``tools/audit.py`` and, later, the
plan -> per-script chunk generator can read it:

    <audit-dir>/
      index.jsonl
      <timestamp>-req<id>/
        meta.json
        outcome.json
        context/summary.txt
        context/project.literal
        prompts/system.txt
        prompts/user-01.txt
        prompts/assembly.json
        attempts/01/raw.txt
        attempts/01/parsed.json
        attempts/01/validation.json
        attempts/01/dsl.json
        attempts/01/meta.json
        chunks/plan.json
        chunks/changes.json
        chunks/01-draw_square.json
        compiled/changeset.json
        compiled/stacks.json
        compiled/apply.json
        compiled/apply.literal
        compiled/summary.txt

``chunks/`` currently records the model's own one-shot decomposition.  When the
plan -> script chunk stage lands, the same directory will hold each chunk's
request, raw reply and validation without changing the reader.
"""

from __future__ import annotations

import functools
import json
import logging
import re
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .obs import redact
from .smalltalk import Sym, to_literal

log = logging.getLogger("harness.audit")

#: Bundle schema version.  Bump when a reader would need different logic.
SCHEMA = 1

AUDIT_MODES = ("off", "meta", "full")

_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]+")


def default_audit_dir() -> Path:
    """``<repo>/scratch/base/audit`` (harness -> src -> bridge -> repo)."""
    repo = Path(__file__).resolve().parents[3]
    return repo / "scratch" / "base" / "audit"


def _safe_name(value: Any, fallback: str = "turn") -> str:
    text = _SAFE_RE.sub("-", str(value)).strip("-")
    return text[:80] or fallback


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _jsonable(value: Any) -> Any:
    """Convert ``Sym`` and nested containers into JSON-safe values."""
    if isinstance(value, Sym):
        return "#" + value.name
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@dataclass(frozen=True)
class AuditSettings:
    """Validated audit configuration."""

    mode: str = "off"
    directory: Path = field(default_factory=default_audit_dir)
    keep: int = 100

    def __post_init__(self) -> None:
        mode = str(self.mode or "off").strip().lower()
        if mode not in AUDIT_MODES:
            raise ValueError(
                f"audit mode must be one of {', '.join(AUDIT_MODES)}, got {self.mode!r}"
            )
        object.__setattr__(self, "mode", mode)
        try:
            directory = Path(self.directory).expanduser()
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid audit directory: {self.directory!r}") from exc
        object.__setattr__(self, "directory", directory)
        try:
            keep = int(self.keep)
        except (TypeError, ValueError):
            keep = 100
        object.__setattr__(self, "keep", keep)

    @property
    def enabled(self) -> bool:
        return self.mode != "off"


@dataclass
class AuditStore:
    """Creates turn bundles and appends the shared JSONL index."""

    settings: AuditSettings

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    def start_turn(
        self,
        *,
        request_id: int | str,
        prompt: str,
        target: str,
        context: Any,
        profile: str = "",
        model: str = "",
        base_url: str = "",
        turn_budget_s: float = 0.0,
        context_literal: Any = None,
        generator: str = "json",
    ) -> "TurnAudit | None":
        if not self.settings.enabled:
            return None
        base = self.settings.directory
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.warning(
                "event=audit.directory_failed path=%s error=%s",
                base,
                redact(str(exc)),
            )
            return None

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        name = f"{stamp}-req{_safe_name(request_id, '0')}"
        root = base / name
        if root.exists():
            root = base / f"{name}-{uuid.uuid4().hex[:6]}"
        try:
            root.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            log.warning(
                "event=audit.turn_failed path=%s error=%s",
                root,
                redact(str(exc)),
            )
            return None

        try:
            turn = TurnAudit(
                self,
                root,
                request_id=request_id,
                prompt=prompt,
                target=target,
                context=context,
                profile=profile,
                model=model,
                base_url=base_url,
                turn_budget_s=turn_budget_s,
                context_literal=context_literal,
                generator=generator,
            )
        except Exception as exc:  # pragma: no cover - defensive
            log.warning(
                "event=audit.turn_init_failed path=%s error=%s",
                root,
                redact(str(exc)),
            )
            return None
        self.prune(root)
        return turn

    def append_index(self, entry: dict[str, Any]) -> None:
        path = self.settings.directory / "index.jsonl"
        try:
            with self._lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "a", encoding="utf-8", newline="\n") as handle:
                    handle.write(
                        json.dumps(
                            _jsonable(entry), ensure_ascii=True, separators=(",", ":")
                        )
                        + "\n"
                    )
        except OSError as exc:
            log.warning(
                "event=audit.index_failed path=%s error=%s",
                path,
                redact(str(exc)),
            )

    def prune(self, current: Path) -> None:
        """Keep at most ``settings.keep`` turn directories (0 = keep all)."""
        keep = self.settings.keep
        if keep <= 0:
            return
        try:
            directories = sorted(
                (
                    path
                    for path in self.settings.directory.iterdir()
                    if path.is_dir() and path.name != current.name
                ),
                key=lambda path: path.name,
            )
        except OSError:
            return
        excess = len(directories) + 1 - keep
        for path in directories[: max(0, excess)]:
            try:
                shutil.rmtree(path)
            except OSError as exc:
                log.warning(
                    "event=audit.prune_failed path=%s error=%s",
                    path,
                    redact(str(exc)),
                )


def _guard(method):
    """Make an audit write best-effort: it must never fail the model turn."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            self._warn(method.__name__, exc)
            return None

    return wrapper


class TurnAudit:
    """One request's audit bundle.  Every write is best-effort."""

    def __init__(
        self,
        store: AuditStore,
        root: Path,
        *,
        request_id: int | str,
        prompt: str,
        target: str,
        context: Any,
        profile: str,
        model: str,
        base_url: str,
        turn_budget_s: float,
        context_literal: Any,
        generator: str = "json",
    ):
        self.store = store
        self.root = root
        self.mode = store.settings.mode
        self.request_id = str(request_id)
        self.started_at = _utc_now()
        self.prompt = prompt or ""
        self.target = target or ""
        self.context = context
        self.profile = profile or ""
        self.model = model or ""
        self.base_url = base_url or ""
        self.turn_budget_s = float(turn_budget_s or 0.0)
        self.generator = generator or "json"
        self._finished = False

        self._write_json(
            "meta.json",
            {
                "schema": SCHEMA,
                "turn": self.root.name,
                "request_id": self.request_id,
                "started_at": self.started_at,
                "mode": self.mode,
                "generator": self.generator,
                "profile": self.profile,
                "model": self.model,
                "base_url": self.base_url,
                "turn_budget_s": self.turn_budget_s,
                "target": self.target,
                "prompt_chars": len(self.prompt),
                "context_summary_chars": self._context_summary_chars(),
                "context_literal_present": context_literal is not None,
            },
        )
        self._write_context(context, context_literal)

    @property
    def full(self) -> bool:
        return self.mode == "full"

    def _context_summary_chars(self) -> int:
        try:
            return len(self.context.summary_text())
        except Exception:  # pragma: no cover - defensive
            return 0

    def _warn(self, relative: str, exc: Exception) -> None:
        log.warning(
            "event=audit.write_failed path=%s error=%s",
            relative,
            redact(str(exc)),
        )

    def _write(self, relative: str, text: str, *, full_only: bool = False) -> None:
        if full_only and not self.full:
            return
        path = self.root / relative
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(text), encoding="utf-8", newline="\n")
        except OSError as exc:
            self._warn(relative, exc)

    def _write_json(self, relative: str, value: Any, *, full_only: bool = False) -> None:
        if full_only and not self.full:
            return
        text = json.dumps(_jsonable(value), indent=2, ensure_ascii=True) + "\n"
        self._write(relative, text)

    def _write_context(self, context: Any, context_literal: Any) -> None:
        if not self.full:
            return
        summary = ""
        try:
            if context is not None:
                summary = context.summary_text()
        except Exception:  # pragma: no cover - defensive
            summary = ""
        self._write("context/summary.txt", summary, full_only=True)
        if context_literal is None:
            literal = "(no context literal: template/demo context)\n"
        else:
            try:
                literal = to_literal(context_literal)
            except Exception:  # pragma: no cover - defensive
                literal = repr(context_literal)
        self._write("context/project.literal", literal, full_only=True)

    @_guard
    def write_prompts(
        self,
        system: str,
        user: str,
        *,
        system_info: dict[str, Any] | None = None,
        user_info: dict[str, Any] | None = None,
    ) -> None:
        if not self.full:
            return
        self._write("prompts/system.txt", system, full_only=True)
        self._write_json(
            "prompts/assembly.json",
            {
                "schema": SCHEMA,
                "system": system_info or {},
                "user": user_info or {},
            },
            full_only=True,
        )
        # The first user prompt is written here; repair prompts are written by
        # write_attempt() under the attempt number so they can be compared.
        self._write("prompts/user-01.txt", user, full_only=True)

    @_guard
    def write_attempt(
        self,
        number: int,
        *,
        user_prompt: str | None = None,
        reply: Any = None,
        error: Any = None,
        parse_error: Any = None,
        issues: list[Any] | None = None,
        fragment: bool = False,
        fragment_indices: list[int] | None = None,
        dsl_errors: list[str] | None = None,
        replace_echo: bool = False,
        echo_sprites: list[str] | None = None,
        noop_guard: bool = False,
        noop_sprites: list[str] | None = None,
        envelope_actions: list[str] | None = None,
        envelope_fatal: bool = False,
    ) -> None:
        if not self.full:
            return
        attempt = max(1, int(number))
        folder = f"attempts/{attempt:02d}"
        meta: dict[str, Any] = {
            "schema": SCHEMA,
            "number": attempt,
            "user_prompt_chars": len(user_prompt or ""),
        }
        if fragment:
            meta["fragment"] = True
            if fragment_indices is not None:
                meta["fragment_indices"] = list(fragment_indices)
        if replace_echo:
            # The reply was a valid change set that replaced a script whose
            # current body the model had not loaded; the bridge answered with
            # one echo round showing those bodies.  ``echo_sprites`` names the
            # sprites whose bodies were shown.
            meta["replace_echo"] = True
            meta["echo_sprites"] = list(echo_sprites or [])
        if noop_guard:
            # The reply was a valid change set that only replaced AI-owned
            # scripts with byte-identical content; the bridge answered with one
            # guard round naming the two legitimate ways forward.
            meta["noop_guard"] = True
            meta["noop_sprites"] = list(noop_sprites or [])
        if envelope_actions is not None:
            # The reply-envelope layer recovered this reply's shape (prose
            # around the fence, notes after the close, a missing close, ...).
            # Recoveries cost zero repairs, so the audit keeps them visible
            # for drift measurement instead of hiding them in a warning line.
            actions = [str(action) for action in envelope_actions]
            meta["envelope_actions"] = actions
            meta["envelope_action_count"] = len(actions)
        if envelope_fatal:
            # A fatal envelope diagnostic was this attempt's failure (two
            # fenced blocks, code outside the fence, a prose-only reply).
            meta["envelope_fatal"] = True
        if user_prompt is not None:
            self._write(
                f"prompts/user-{attempt:02d}.txt", user_prompt, full_only=True
            )

        raw_text = None
        if reply is not None:
            raw_text = getattr(reply, "raw_text", None)
            data = getattr(reply, "data", None)
            if data is not None:
                self._write_json(f"{folder}/parsed.json", data, full_only=True)
            meta.update(
                {
                    "model": getattr(reply, "model", "") or "",
                    "finish_reason": getattr(reply, "finish_reason", None),
                    "usage": getattr(reply, "usage", None),
                    "latency_ms": getattr(reply, "latency_ms", None),
                    "transport_attempts": getattr(reply, "attempts", None),
                    "reasoning_tokens": getattr(reply, "reasoning_tokens", None),
                    "cached_tokens": getattr(reply, "cached_tokens", None),
                }
            )
        if error is not None:
            raw_text = getattr(error, "raw_text", None)
            meta.update(
                {
                    "error_code": getattr(error, "code", ""),
                    "error_message": redact(
                        str(getattr(error, "message", error))
                    ),
                    "error_status": getattr(error, "status", None),
                    "finish_reason": getattr(error, "finish_reason", None),
                    "reasoning_tokens": getattr(error, "reasoning_tokens", None),
                    "content_chars": getattr(error, "content_chars", None),
                    "cached_tokens": getattr(error, "cached_tokens", None),
                }
            )
        if raw_text is not None:
            self._write(f"{folder}/raw.txt", raw_text, full_only=True)
            meta["raw_available"] = True
            meta["raw_chars"] = len(str(raw_text))
        else:
            meta["raw_available"] = False
        if parse_error is not None:
            meta["parse_error"] = redact(str(parse_error))
        if issues is not None:
            items = [_issue_dict(issue) for issue in issues]
            self._write_json(f"{folder}/validation.json", items, full_only=True)
            meta["issue_count"] = len(items)
        if dsl_errors is not None:
            errors = [redact(str(error)) for error in dsl_errors]
            self._write_json(f"{folder}/dsl.json", errors, full_only=True)
            meta["dsl_error_count"] = len(errors)
        self._write_json(f"{folder}/meta.json", meta, full_only=True)

    @_guard
    def write_compiled(self, changeset: Any, compiled: Any) -> None:
        if not self.full:
            return
        try:
            self._write_json(
                "compiled/changeset.json",
                changeset.to_dict(),
                full_only=True,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._warn("compiled/changeset.json", exc)
        try:
            self._write_json(
                "compiled/stacks.json",
                [_compiled_change_json(change) for change in compiled.changes],
                full_only=True,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._warn("compiled/stacks.json", exc)
        try:
            self._write_json(
                "compiled/apply.json",
                compiled.apply_structure(int(self.request_id)),
                full_only=True,
            )
        except Exception:  # pragma: no cover - request ids can be non-numeric
            self._write_json(
                "compiled/apply.json",
                compiled.apply_structure(0),
                full_only=True,
            )
        try:
            self._write(
                "compiled/apply.literal",
                compiled.apply_literal(_request_number(self.request_id)),
                full_only=True,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._warn("compiled/apply.literal", exc)
        try:
            self._write(
                "compiled/summary.txt",
                compiled.chat_summary(),
                full_only=True,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._warn("compiled/summary.txt", exc)

    @_guard
    def write_chunks(self, changeset: Any, compiled: Any) -> None:
        """Record the decomposition of this change set.

        Today the model returns one JSON object, so each change is a *derived*
        chunk (``source: one-shot-change-set``).  The future plan -> script
        stage will reuse the same filenames for actual per-chunk requests and
        replies, with ``source: plan-chunks``.
        """
        if not self.full:
            return
        changes = list(getattr(changeset, "changes", []) or [])
        compiled_changes = list(getattr(compiled, "changes", []) or [])
        try:
            normalized = list(changeset.to_dict().get("changes", []) or [])
        except Exception:  # pragma: no cover - defensive
            normalized = []
        plan: dict[str, Any] = {
            "schema": SCHEMA,
            "source": "one-shot-change-set",
            "note": (
                "Plan -> per-script chunk generation is not enabled yet; this is "
                "the model's own decomposition of the request."
            ),
            "request": self.prompt,
            "target": self.target,
            "changes": [],
        }
        for index, change in enumerate(changes):
            compiled_change = compiled_changes[index] if index < len(compiled_changes) else None
            item = {
                "index": index,
                "action": getattr(change, "action", ""),
                "target": getattr(change, "target", "")
                or getattr(compiled_change, "target", ""),
                "label": getattr(change, "label", "")
                or getattr(compiled_change, "label", ""),
                "script_id": getattr(compiled_change, "script_id", ""),
                "block_count": getattr(compiled_change, "block_count", 0),
            }
            plan["changes"].append(item)
            chunk = {
                "schema": SCHEMA,
                "source": "one-shot-change-set",
                **item,
                "change": normalized[index] if index < len(normalized) else {},
            }
            name = _safe_name(item["label"] or item["action"], "change")
            self._write_json(
                f"chunks/{index + 1:02d}-{name}.json",
                chunk,
                full_only=True,
            )
        self._write_json("chunks/plan.json", plan, full_only=True)
        try:
            self._write_json(
                "chunks/changes.json",
                normalized,
                full_only=True,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._warn("chunks/changes.json", exc)

    @_guard
    def write_lints(self, lints: list[str]) -> None:
        """Record this turn's advisory lint warnings as ``lints.json``."""
        if not self.full:
            return
        self._write_json(
            "lints.json",
            [str(item) for item in (lints or [])],
            full_only=True,
        )

    @_guard
    def finish(
        self,
        *,
        outcome: str,
        attempts: int = 0,
        changes: int = 0,
        elapsed_ms: int = 0,
        error: str = "",
        result: Any = None,
    ) -> None:
        if self._finished:
            return
        self._finished = True
        usage = getattr(result, "usage", None) if result is not None else None
        if usage is not None:
            try:
                usage = dict(usage)
            except (TypeError, ValueError):
                usage = None
        finish_reason = (
            getattr(result, "finish_reason", None) if result is not None else None
        )
        latency_ms = getattr(result, "latency_ms", None) if result is not None else None
        reasoning_tokens = (
            getattr(result, "reasoning_tokens", None) if result is not None else None
        )
        cached_tokens = (
            getattr(result, "cached_tokens", None) if result is not None else None
        )
        summary = getattr(result, "summary", "") if result is not None else ""
        error_text = redact(str(error)) if error else ""

        data = {
            "schema": SCHEMA,
            "turn": self.root.name,
            "request_id": self.request_id,
            "started_at": self.started_at,
            "outcome": outcome,
            "attempts": int(attempts or 0),
            "changes": int(changes or 0),
            "elapsed_ms": int(elapsed_ms or 0),
            "error": error_text,
            "profile": self.profile,
            "model": self.model,
            "base_url": self.base_url,
            "usage": usage,
            "latency_ms": latency_ms,
            "finish_reason": finish_reason,
            "reasoning_tokens": reasoning_tokens,
            "cached_tokens": cached_tokens,
            "summary": summary,
        }
        self._write_json("outcome.json", data)

        tokens = usage or {}
        self.store.append_index(
            {
                "schema": SCHEMA,
                "turn": self.root.name,
                "request_id": self.request_id,
                "started_at": self.started_at,
                "outcome": outcome,
                "attempts": data["attempts"],
                "changes": data["changes"],
                "elapsed_ms": data["elapsed_ms"],
                "prompt_tokens": tokens.get("prompt_tokens"),
                "completion_tokens": tokens.get("completion_tokens"),
                "total_tokens": tokens.get("total_tokens"),
                "reasoning_tokens": reasoning_tokens,
                "cached_tokens": cached_tokens,
                "error": error_text,
                "dir": self.root.name,
            }
        )


def _request_number(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _issue_dict(issue: Any) -> dict[str, str]:
    return {
        "path": str(getattr(issue, "path", "")),
        "message": redact(str(getattr(issue, "message", issue))),
    }


def _compiled_change_json(change: Any) -> dict[str, Any]:
    # Do not use ``dataclasses.asdict`` here: it recursively turns ``Sym``
    # values inside the compiled stack into ``{"name": ...}`` dictionaries.
    return {
        "action": getattr(change, "action", ""),
        "script_id": getattr(change, "script_id", ""),
        "target": getattr(change, "target", ""),
        "label": getattr(change, "label", ""),
        "block_count": getattr(change, "block_count", 0),
        "name": getattr(change, "name", ""),
        "scope": getattr(change, "scope", ""),
        "initial": getattr(change, "initial", None),
        "costumes": _jsonable(getattr(change, "costumes", [])),
        "library": getattr(change, "library", ""),
        "select": getattr(change, "select", False),
        "x": getattr(change, "x", None),
        "y": getattr(change, "y", None),
        "direction": getattr(change, "direction", None),
        "size": getattr(change, "size", None),
        "visible": getattr(change, "visible", None),
        "rotation_style": getattr(change, "rotation_style", ""),
        "stack": _jsonable(getattr(change, "stack", None)),
    }
