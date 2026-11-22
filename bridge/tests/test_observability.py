from __future__ import annotations

import logging
from types import SimpleNamespace

from harness.config import resolve_config
from harness.obs import (
    RedactingFormatter,
    bridge_info,
    log_event,
    redact,
    setup_logging,
)
from harness.protocol import Sym

FAKE_OC_SK = "oc_sk_livekeyshouldneverappear123456"
FAKE_SK = "sk-proj-abcdefghijklmnopqrstuvwxyz"
FAKE_API_KEY = "supersecretvalue123"
FAKE_BEARER = "bearervalue987654321"


class _ListHandler(logging.Handler):
    """Collect fully formatted lines so RedactingFormatter is exercised."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


def _remove_obs_handlers() -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_scratch_harness_obs", None) is not None:
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass


def _obs_handlers(kind: str) -> list[logging.Handler]:
    return [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, "_scratch_harness_obs", (None, None))[0] == kind
    ]


# ---------------------------------------------------------------------------
# redact()
# ---------------------------------------------------------------------------


def test_redact_removes_oc_sk_token():
    out = redact(f"using key {FAKE_OC_SK} for the request")
    assert FAKE_OC_SK not in out
    assert "oc_sk_[REDACTED]" in out


def test_redact_removes_authorization_header():
    out = redact(f"Authorization: Bearer {FAKE_BEARER}")
    assert FAKE_BEARER not in out
    assert "Bearer" not in out or "[REDACTED]" in out
    assert "[REDACTED]" in out


def test_redact_removes_api_key_value():
    out = redact(f"config api_key={FAKE_API_KEY} loaded")
    assert FAKE_API_KEY not in out
    assert "api_key=[REDACTED]" in out


def test_redact_removes_sk_style_key():
    out = redact(f"token {FAKE_SK} rejected")
    assert FAKE_SK not in out
    assert "[REDACTED]" in out


def test_redact_is_case_insensitive_for_api_key():
    out = redact(f"API_KEY: {FAKE_API_KEY}")
    assert FAKE_API_KEY not in out


def test_fake_key_never_appears_in_formatted_caplog(caplog):
    logger = logging.getLogger("harness.test.obs.formatter")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = _ListHandler()
    handler.setFormatter(RedactingFormatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    try:
        with caplog.at_level(logging.INFO, logger="harness.test.obs.formatter"):
            logger.info("calling endpoint key=%s auth=Bearer %s", FAKE_OC_SK, FAKE_BEARER)
    finally:
        logger.removeHandler(handler)

    assert handler.lines, "the handler should have formatted one line"
    line = handler.lines[0]
    assert FAKE_OC_SK not in line
    assert FAKE_BEARER not in line
    assert "[REDACTED]" in line


def test_redacting_formatter_scrubs_traceback():
    logger = logging.getLogger("harness.test.obs.traceback")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = _ListHandler()
    handler.setFormatter(RedactingFormatter("%(message)s"))
    logger.addHandler(handler)
    try:
        try:
            raise RuntimeError(f"failed with {FAKE_SK}")
        except RuntimeError:
            logger.exception("provider exploded")
    finally:
        logger.removeHandler(handler)

    line = "\n".join(handler.lines)
    assert FAKE_SK not in line
    assert "[REDACTED]" in line


# ---------------------------------------------------------------------------
# setup_logging()
# ---------------------------------------------------------------------------


def test_setup_logging_writes_redacted_file_and_creates_dirs(tmp_path):
    _remove_obs_handlers()
    target = tmp_path / "missing" / "dirs" / "bridge.log"
    old_level = logging.getLogger().level
    try:
        path = setup_logging(level="INFO", log_file=target, stream=False)
        assert path == target.resolve()
        assert target.parent.is_dir()

        logging.getLogger("harness.test.obs.file").info(
            "endpoint rejected key=%s authorization=Bearer %s", FAKE_OC_SK, FAKE_BEARER
        )
        for handler in _obs_handlers("file"):
            handler.flush()

        text = target.read_text(encoding="utf-8")
        assert FAKE_OC_SK not in text
        assert FAKE_BEARER not in text
        assert "[REDACTED]" in text
    finally:
        _remove_obs_handlers()
        logging.getLogger().setLevel(old_level)


def test_setup_logging_is_idempotent(tmp_path):
    _remove_obs_handlers()
    target = tmp_path / "bridge.log"
    old_level = logging.getLogger().level
    try:
        first = setup_logging(level="INFO", log_file=target, stream=False)
        second = setup_logging(level="INFO", log_file=target, stream=False)
        assert first == second == target.resolve()
        assert len(_obs_handlers("file")) == 1
    finally:
        _remove_obs_handlers()
        logging.getLogger().setLevel(old_level)


def test_setup_logging_default_path_is_under_scratch_base():
    from harness.obs import default_log_path

    path = default_log_path()
    assert path.name == "bridge.log"
    assert path.parent.name == "base"
    assert path.parent.parent.name == "scratch"


def test_setup_logging_false_disables_the_file_handler(tmp_path, monkeypatch):
    """`--no-log-file` must not silently fall back to the default path."""
    import harness.obs as obs

    _remove_obs_handlers()
    old_level = logging.getLogger().level
    monkeypatch.setattr(obs, "default_log_path", lambda: tmp_path / "must-not-exist.log")
    try:
        assert setup_logging(level="INFO", log_file=False, stream=True) is None
        assert _obs_handlers("file") == []
        assert not (tmp_path / "must-not-exist.log").exists()
        assert len(_obs_handlers("stream")) == 1
    finally:
        _remove_obs_handlers()
        logging.getLogger().setLevel(old_level)


# ---------------------------------------------------------------------------
# log_event()
# ---------------------------------------------------------------------------


def test_log_event_emits_one_greppable_line(caplog):
    logger = logging.getLogger("harness.test.obs.event")
    with caplog.at_level(logging.INFO, logger="harness.test.obs.event"):
        log_event(logger, "turn", request=7, outcome="ok", latency_ms=12, skipped=None)

    lines = [record.getMessage() for record in caplog.records]
    assert len(lines) == 1
    line = lines[0]
    assert line.startswith("event=turn ")
    assert "request=7" in line
    assert "outcome=ok" in line
    assert "latency_ms=12" in line
    assert "skipped" not in line


def test_log_event_drops_banned_fields(caplog):
    logger = logging.getLogger("harness.test.obs.event.banned")
    with caplog.at_level(logging.INFO, logger="harness.test.obs.event.banned"):
        log_event(
            logger,
            "request.start",
            prompt="draw a square",
            system="you are a bot",
            user="secret user text",
            api_key=FAKE_API_KEY,
            authorization=f"Bearer {FAKE_BEARER}",
            request=3,
        )

    assert len(caplog.records) == 1
    line = caplog.records[0].getMessage()
    assert line.startswith("event=request.start ")
    assert "request=3" in line
    for banned in ("prompt=", "system=", "user=", "api_key=", "authorization="):
        assert banned not in line
    assert "dropped=prompt" in line
    assert "dropped=system" in line
    assert "dropped=user" in line
    assert "dropped=api_key" in line
    assert "dropped=authorization" in line
    assert FAKE_API_KEY not in line
    assert FAKE_BEARER not in line


def test_log_event_redacts_values(caplog):
    logger = logging.getLogger("harness.test.obs.event.redact")
    with caplog.at_level(logging.INFO, logger="harness.test.obs.event.redact"):
        log_event(logger, "provider.error", detail=f"key={FAKE_OC_SK}")

    line = caplog.records[0].getMessage()
    assert FAKE_OC_SK not in line
    assert "[REDACTED]" in line


# ---------------------------------------------------------------------------
# bridge_info()
# ---------------------------------------------------------------------------


def _mock_config(tmp_path):
    return resolve_config("mock", config_path=tmp_path / "missing.ini", env={})


def test_bridge_info_exact_shape(tmp_path):
    config = _mock_config(tmp_path)
    bridge = SimpleNamespace(
        turn_budget_s=240.0,
        max_concurrent=2,
        pending={},
        last_error="boom from earlier turn",
    )

    info = bridge_info(config, bridge)

    assert isinstance(info, list)
    assert len(info) == 9
    assert info[0] == Sym("info")
    assert info[1] == "ScratchAI/1"
    assert info[2] == "mock"
    assert info[3] == "mock"
    assert info[4] == ""
    assert info[5] == 240.0
    assert info[6] == 2
    assert info[7] == 0
    assert info[8] == "boom from earlier turn"


def test_bridge_info_handles_missing_last_error_and_pending(tmp_path):
    config = _mock_config(tmp_path)
    bridge = SimpleNamespace(turn_budget_s=90.0, max_concurrent=1)

    info = bridge_info(config, bridge)

    assert len(info) == 9
    assert info[7] == 0
    assert info[8] == ""


def test_bridge_info_counts_pending(tmp_path):
    config = _mock_config(tmp_path)
    bridge = SimpleNamespace(
        turn_budget_s=240.0,
        max_concurrent=4,
        pending={1: (None, 0.0), 2: (None, 0.0), 3: (None, 0.0)},
    )

    info = bridge_info(config, bridge)

    assert info[6] == 4
    assert info[7] == 3


def test_bridge_info_never_contains_api_key(tmp_path):
    config = resolve_config("opencode-go", config_path=tmp_path / "missing.ini", env={})
    bridge = SimpleNamespace(
        turn_budget_s=240.0,
        max_concurrent=2,
        pending={},
        last_error=f"auth failed with {FAKE_OC_SK} and api_key={FAKE_API_KEY}",
    )

    info = bridge_info(config, bridge)
    rendered = repr(info)

    assert FAKE_API_KEY not in rendered
    assert FAKE_OC_SK not in rendered
    assert "api_key" not in rendered.lower()
    assert "DEEPSEEK_API_KEY" not in rendered
    assert info[2] == "opencode-go"
    assert info[4] == "https://opencode.ai/inference/go/openai/v1"
