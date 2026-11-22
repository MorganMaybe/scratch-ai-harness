"""Headless observability: secret redaction, logging setup, events, ``#info``.

Everything here is standard library only.  The bridge, the launcher and the
``bridge-status`` client share these helpers so one redaction rule protects
every rendered log line.

Design rules
------------
* Over-redaction is fine; a leaked key is not.
* Log lines are one line per event, stable and greppable::

      event=<event> key=value key=value ...

* Prompt/context/key-shaped fields are refused by ``log_event`` even if a
  caller passes them accidentally.
* ``bridge_info`` builds the ``#info`` reply and never includes the key.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

#: The wire version every client checks first.
PROTOCOL_VERSION = "ScratchAI/1"

#: Handler marker so repeated ``setup_logging`` calls can find their own
#: handlers instead of stacking duplicates.
_HANDLER_TAG = "_scratch_harness_obs"

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

#: The only fields the image/bridge may need for a status reply.
_INFO_FIELDS = (
    "profile",
    "model",
    "base_url",
    "turn_budget_s",
    "max_concurrent",
    "pending_count",
    "last_error",
)

#: Field names that must never reach a log line, regardless of the value.
_BANNED_FIELDS = frozenset(
    {
        "prompt",
        "system",
        "context",
        "user",
        "authorization",
        "api_key",
    }
)

# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

#: OpenCode/Go key prefix. Keep the prefix, redact the body.
_OC_SK_RE = re.compile(r"oc_sk_[A-Za-z0-9._\-]+")

#: ``Authorization: ...`` / ``Authorization=...`` header values.
_AUTH_RE = re.compile(r"(?i)\b(authorization\s*[:=]\s*)(?:Bearer\s+)?[^\s,;]+")

#: A bare ``Bearer <token>`` (for lines that already lost the header name).
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+\-/]+=*")

#: Classic ``sk-...`` keys. Eight characters after the prefix at minimum,
#: which is already far shorter than any real key.
_SK_RE = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}")

#: ``api_key=...``, ``api-key: ...`` and JSON-shaped ``"api_key": "..."``.
_API_KEY_RE = re.compile(
    r"(?i)\b(api[_-]?key[\"']?\s*[=:]\s*[\"']?)[^\s\"',;}]+"
)

_REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    """Scrub secrets from any rendered log line.

    Removes ``oc_sk_`` tokens, ``Authorization`` header values, ``Bearer``
    tokens, ``sk-`` style keys and ``api[_-]?key=...`` values.  Conservative:
    anything that looks remotely secret is replaced with ``[REDACTED]``.
    """
    if not isinstance(text, str):
        text = str(text)
    text = _API_KEY_RE.sub(r"\1" + _REDACTED, text)
    text = _AUTH_RE.sub(r"\1" + _REDACTED, text)
    text = _BEARER_RE.sub("Bearer " + _REDACTED, text)
    text = _OC_SK_RE.sub("oc_sk_" + _REDACTED, text)
    text = _SK_RE.sub(_REDACTED, text)
    return text


class RedactingFormatter(logging.Formatter):
    """A formatter that redacts the final message, including tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            if record.exc_info and not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                record.exc_text = redact(record.exc_text)
        except Exception:  # pragma: no cover - never lose a log line
            pass
        try:
            return redact(super().format(record))
        except Exception:  # pragma: no cover - defensive
            return redact(f"{record.name}: <unformattable log record>")


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def default_log_path() -> Path:
    """``<repo>/scratch/base/bridge.log`` (harness -> src -> bridge -> repo)."""
    repo = Path(__file__).resolve().parents[3]
    return repo / "scratch" / "base" / "bridge.log"


def _tagged_handlers(root: logging.Logger, kind: str) -> list[logging.Handler]:
    return [
        handler
        for handler in root.handlers
        if getattr(handler, _HANDLER_TAG, (None, None))[0] == kind
    ]


def _install_stream_handler(level: str | int, stream: bool) -> None:
    root = logging.getLogger()
    try:
        root.setLevel(str(level).upper() if not isinstance(level, int) else level)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        root.setLevel(logging.INFO)
    if stream and not _tagged_handlers(root, "stream"):
        handler = logging.StreamHandler()
        handler.setFormatter(RedactingFormatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT))
        setattr(handler, _HANDLER_TAG, ("stream", None))
        root.addHandler(handler)


def setup_logging(
    level: str = "INFO",
    log_file: str | Path | bool = None,
    stream: bool = True,
) -> Path | None:
    """Install the redacting stderr and file handlers exactly once.

    ``log_file`` semantics: ``None`` uses the default bridge log path, a path
    selects that file, and ``False`` disables the file handler entirely
    (stderr only).  Calling this twice with the same arguments must not
    duplicate handlers.

    Returns the path of the file handler actually used, or ``None`` when the
    file is disabled or cannot be opened (a warning is logged instead of
    raising).
    """
    if log_file is False:
        _install_stream_handler(level, stream)
        return None

    _install_stream_handler(level, stream)
    root = logging.getLogger()
    formatter = RedactingFormatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    path = default_log_path() if log_file is None else Path(log_file).expanduser()
    try:
        path = path.resolve()
    except OSError:  # pragma: no cover - extremely rare on Windows
        pass
    key = str(path)

    existing = [
        handler
        for handler in _tagged_handlers(root, "file")
        if getattr(handler, _HANDLER_TAG, (None, None))[1] == key
    ]
    if existing:
        return path

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8", delay=False)
    except OSError as exc:
        logging.getLogger("harness.obs").warning(
            "event=logging.file_failed path=%s error=%s", path, redact(str(exc))
        )
        return None

    handler.setFormatter(formatter)
    setattr(handler, _HANDLER_TAG, ("file", key))
    root.addHandler(handler)
    return path


# ---------------------------------------------------------------------------
# Structured events
# ---------------------------------------------------------------------------


def _value_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    try:
        text = str(value)
    except Exception:  # pragma: no cover - defensive
        return "<unprintable>"
    # Exactly one physical log line per event, even for exception text.
    return text.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit one greppable INFO line: ``event=<event> k=v k=v``.

    ``None`` values are skipped.  Banned field names (prompt, system, context,
    user, authorization, api_key) are replaced by ``dropped=<field>`` so an
    accidental call is visible but harmless.
    """
    parts = [f"event={redact(_value_text(event))}"]
    for key, value in fields.items():
        name = str(key)
        if name.lower() in _BANNED_FIELDS:
            parts.append(f"dropped={redact(name)}")
            continue
        if value is None:
            continue
        parts.append(f"{name}={redact(_value_text(value))}")
    logger.info(" ".join(parts))


# ---------------------------------------------------------------------------
# The #info payload
# ---------------------------------------------------------------------------


def _pending_count(bridge: Any) -> int:
    pending = getattr(bridge, "pending", None)
    if pending is None:
        return 0
    try:
        return len(pending)
    except TypeError:  # pragma: no cover - defensive
        return 0


#: Only redact secret-shaped *field names* when they are actually assigning a
#: value (``api_key=...``).  Prose like "the endpoint rejected the API key" is a
#: legitimate diagnostic and must survive.
_BANNED_WORD_RE = re.compile(r"(?i)\b(?:authorization|api[\s_-]?key)[\"']?(?=\s*[=:])")


def _info_text(value: Any) -> str:
    """Redact a status string and remove secret-shaped assignments entirely."""
    text = redact(_value_text(value))
    return _BANNED_WORD_RE.sub("[REDACTED]", text)


def _last_error(bridge: Any) -> str:
    value = getattr(bridge, "last_error", "") or ""
    return _info_text(value)


def bridge_info(config: Any, bridge: Any) -> list[Any]:
    """Build the ``#info`` reply payload.

    Exact contract::

        #(info 'ScratchAI/1' profile model base_url
          turn_budget_s max_concurrent pending_count last_error)

    The API key is never read, and every string is redacted defensively.
    """
    from .protocol import Sym

    profile = _info_text(getattr(config, "profile", "") or "")
    model = _info_text(getattr(config, "model", "") or "")
    base_url = _info_text(getattr(config, "base_url", "") or "")

    turn_budget = getattr(bridge, "turn_budget_s", 0.0)
    if not isinstance(turn_budget, (int, float)) or isinstance(turn_budget, bool):
        turn_budget = 0.0

    max_concurrent = getattr(bridge, "max_concurrent", 1)
    if not isinstance(max_concurrent, int) or isinstance(max_concurrent, bool):
        max_concurrent = 1

    return [
        Sym("info"),
        PROTOCOL_VERSION,
        profile,
        model,
        base_url,
        turn_budget,
        max_concurrent,
        _pending_count(bridge),
        _last_error(bridge),
    ]


# ---------------------------------------------------------------------------
# Additive status surfaces: #options and #usage
# ---------------------------------------------------------------------------


def _effective_audit_dir(bridge: Any) -> str:
    value = getattr(bridge, "audit_dir", None)
    if value:
        return str(value)
    try:
        from .audit import default_audit_dir

        return str(default_audit_dir())
    except Exception:  # pragma: no cover - defensive
        return ""


def bridge_options(bridge: Any) -> list[Any]:
    """Build the additive ``#options`` reply payload.

    Exact contract::

        #(options audit_mode audit_dir audit_keep prompt_budget_chars
          timeout_s retries max_tokens thinking log_file)

    Read-only configuration for the image's Bridge page.  Never includes the
    API key, prompts, project context or raw model replies.  ``#info`` keeps its
    nine-element contract; this is a separate message.
    """
    from .protocol import Sym
    from .prompts import prompt_budget_chars

    audit_mode = str(getattr(bridge, "audit_mode", "off") or "off")
    if audit_mode not in ("off", "meta", "full"):
        audit_mode = "off"

    try:
        audit_keep = int(getattr(bridge, "audit_keep", 0) or 0)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        audit_keep = 0

    def _number(name: str, default: float = 0) -> float:
        value = getattr(bridge, name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default
        return value

    def _integer(name: str, default: int = 0) -> int:
        value = getattr(bridge, name, default)
        if isinstance(value, bool) or not isinstance(value, int):
            return default
        return value

    try:
        budget = int(prompt_budget_chars())
    except Exception:  # pragma: no cover - defensive
        budget = 0

    return [
        Sym("options"),
        audit_mode,
        _info_text(_effective_audit_dir(bridge)),
        audit_keep,
        budget,
        _number("timeout_s"),
        _integer("max_retries"),
        _integer("max_tokens"),
        _info_text(str(getattr(bridge, "thinking", "off") or "off")),
        _info_text(str(getattr(bridge, "log_file", "") or "")),
    ]


def bridge_usage(bridge: Any) -> list[Any]:
    """Build the additive ``#usage`` reply payload.

    Exact contract::

        #(usage prompt_tokens completion_tokens total_tokens requests
          last_model last_profile api_key_env key_present)

    Token totals are cumulative for this bridge process ("since bridge start").
    ``api_key_env`` is the environment variable *name*; ``key_present`` says
    whether it is set.  The key value is never read for this reply.
    """

    from .protocol import Sym

    def _count(name: str) -> int:
        value = getattr(bridge, name, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return 0
        return value

    return [
        Sym("usage"),
        _count("usage_prompt_tokens"),
        _count("usage_completion_tokens"),
        _count("usage_total_tokens"),
        _count("usage_requests"),
        _info_text(str(getattr(bridge, "model", "") or "")),
        _info_text(str(getattr(bridge, "profile", "") or "")),
        _info_text(str(getattr(bridge, "api_key_env", "") or "")),
        bool(getattr(bridge, "api_key_present", False)),
    ]
