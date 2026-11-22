from __future__ import annotations

import os

from harness.agent import Agent
from harness.config import resolve_config
from harness.context import ProjectContext
from harness.llm import MockLLM, draw_square_response
from harness.obs import bridge_options
from harness.protocol import Sym
from harness.providers.mock import MockProvider
from harness.server import Bridge, default_bridge


def make_bridge(**overrides) -> Bridge:
    context = ProjectContext.demo()
    return Bridge(Agent(MockLLM([draw_square_response()]), context), **overrides)


def test_options_shape_and_defaults():
    bridge = make_bridge()
    reply = bridge.handle([Sym("options")])[0]
    assert reply[0] == Sym("options")
    # selector + 9 fields
    assert len(reply) == 10
    (
        _kind,
        audit_mode,
        audit_dir,
        audit_keep,
        prompt_budget,
        timeout_s,
        retries,
        max_tokens,
        thinking,
        log_file,
    ) = reply
    assert audit_mode == "off"
    assert audit_keep == 100
    assert prompt_budget > 0
    assert thinking == "off"
    assert isinstance(audit_dir, str) and audit_dir


def test_options_reports_audit_settings():
    bridge = make_bridge(audit_mode="full", audit_dir=r"C:\tmp\audit", audit_keep=7)
    reply = bridge_options(bridge)
    assert reply[1] == "full"
    assert reply[2].endswith("audit")
    assert reply[3] == 7


def test_options_rejects_unknown_audit_mode():
    bridge = make_bridge()
    bridge.audit_mode = "secret"
    assert bridge_options(bridge)[1] == "off"


def test_options_contains_no_key_or_prompt():
    bridge = make_bridge(api_key_env="DEEPSEEK_API_KEY", api_key_present=True)
    text = " ".join(str(field) for field in bridge_options(bridge))
    assert "oc_sk_" not in text
    assert "sk-" not in text
    assert "Draw a square" not in text
    assert "DEEPSEEK_API_KEY" not in text


def test_default_bridge_copies_safe_model_options(tmp_path):
    ini = tmp_path / "harness.ini"
    ini.write_text(
        "[model]\ndefault = test\n\n"
        "[profile:test]\n"
        "base_url = http://127.0.0.1:1\n"
        "model = test-model\n"
        "api_key_env = TEST_KEY\n"
        "timeout = 33\n"
        "retries = 1\n"
        "max_tokens = 999\n"
        "thinking = on\n",
        encoding="utf-8",
    )
    config = resolve_config("test", ini)
    bridge = default_bridge(config=config, provider=MockProvider())
    options = bridge_options(bridge)
    assert options[5] == 33
    assert options[6] == 1
    assert options[7] == 999
    assert options[8] == "on"


def test_default_bridge_reports_key_presence_without_value(monkeypatch):
    monkeypatch.setenv("HARNESS_TEST_KEY", "super-secret-value")
    config = resolve_config(
        "opencode-go",
        None,
        env={"HARNESS_PROFILE": "opencode-go"},
    )
    # Point the config at the test variable without exposing its value.
    object.__setattr__(config, "api_key_env", "HARNESS_TEST_KEY")
    bridge = default_bridge(config=config)
    usage = bridge.handle([Sym("usage")])[0]
    assert usage[7] == "HARNESS_TEST_KEY"
    assert usage[8] is True
    text = " ".join(str(field) for field in usage)
    assert "super-secret-value" not in text
    assert os.environ["HARNESS_TEST_KEY"] == "super-secret-value"
