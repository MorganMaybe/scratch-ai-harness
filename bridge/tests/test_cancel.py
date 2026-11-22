"""Client-initiated cancellation (``#cancel``) and bridge diagnostics (``#info``).

Cancellation is cooperative: the bridge can mark a live turn, and the agent
stops at its next checkpoint, but an HTTP call already in flight cannot be
aborted from another thread.  These tests pin down exactly what a client can
rely on:

* a cancelled turn never emits ``#result`` and never enters ``pending``;
* cancelling one request never affects another;
* an unknown/finished id is reported as ``not running``;
* ``#info`` is a stable nine-element reply with safe diagnostics.
"""

from __future__ import annotations

import logging
import threading
import time

import pytest

import harness.agent as agent_module
from harness.agent import Agent, CancelToken
from harness.config import resolve_config
from harness.context import ProjectContext
from harness.llm import MockLLM, draw_square_response
from harness.protocol import Sym
from harness.providers.base import ProviderError
from harness.server import Bridge, default_bridge

INVALID = {
    "summary": "Bad block.",
    "changes": [
        {
            "action": "add_script",
            "target": "Sprite1",
            "label": "bad",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "move_to", "args": {}}],
        }
    ],
}


def _wait_for(predicate, timeout: float = 5.0) -> bool:
    """Poll ``predicate`` until it is true or the timeout expires."""
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def _start(target) -> threading.Thread:
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def _join(thread: threading.Thread, timeout: float = 10.0) -> None:
    thread.join(timeout)
    assert not thread.is_alive(), "worker thread did not finish"


# --- providers --------------------------------------------------------------


class _BlockingProvider:
    """Block inside the model call until the test releases it."""

    name = "blocking"

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def complete_json(self, system: str, user: str) -> dict:
        self.calls += 1
        self.entered.set()
        assert self.release.wait(10), "provider was never released"
        return draw_square_response()


class _GatedProvider:
    """Block only for prompts containing ``BLOCK``."""

    name = "gated"

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls: list[str] = []

    def complete_json(self, system: str, user: str) -> dict:
        self.calls.append(user)
        if "BLOCK" in user:
            self.entered.set()
            assert self.release.wait(10), "provider was never released"
        return draw_square_response()


class _TwoRequestProvider:
    """Block request A, answer anything else immediately."""

    name = "two-request"

    def __init__(self) -> None:
        self.entered_a = threading.Event()
        self.release_a = threading.Event()
        self.calls: list[str] = []

    def complete_json(self, system: str, user: str) -> dict:
        self.calls.append(user)
        if "MARKER_A" in user:
            self.entered_a.set()
            assert self.release_a.wait(10), "provider A was never released"
        return draw_square_response()


class _FailThenSucceedProvider:
    name = "fail-then-succeed"

    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, system: str, user: str) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise ProviderError(
                "auth",
                "the endpoint rejected the API key",
                status=401,
                detail="Authorization: Bearer oc_sk_test_secret_value",
            )
        return draw_square_response()


class _CancellingRepairProvider:
    """Answer with an invalid change set so the agent repairs."""

    name = "cancelling-repair"

    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, system: str, user: str) -> dict:
        self.calls += 1
        return INVALID


# --- cancelling a live request ---------------------------------------------


def test_cancel_running_request_errors_without_result_or_pending(caplog):
    caplog.set_level(logging.INFO, logger="harness.server")
    provider = _BlockingProvider()
    bridge = Bridge(Agent(provider, ProjectContext.demo()))
    replies: dict[str, list] = {}

    def turn() -> None:
        replies["reply"] = bridge.handle([Sym("request"), 41, ["Draw a square."], "Sprite1"])

    worker = _start(turn)
    assert provider.entered.wait(5), "request never reached the provider"

    assert bridge.handle([Sym("cancel"), 41]) == [[Sym("ok"), 41]]
    provider.release.set()  # release the in-flight model call
    _join(worker)

    response = replies["reply"][0]
    assert response[0] == Sym("error")
    assert response[1] == 41
    assert "cancelled" in response[2]
    assert 41 not in bridge.pending, "a cancelled turn must not be acknowledged"
    assert provider.calls == 1
    # A late reply is discarded, so no apply ever registered a script.
    assert "ai-1" not in bridge.agent.registry

    messages = [record.getMessage() for record in caplog.records]
    assert any("request id=41 cancelled" == message for message in messages)
    cancelled_log = next(
        message
        for message in messages
        if message.startswith("request id=41 outcome=error:cancelled")
    )
    assert "changes=0" in cancelled_log
    assert "elapsed_ms=" in cancelled_log
    assert cancelled_log.endswith(" cancelled=1")


def test_cancel_before_first_attempt_makes_zero_provider_calls():
    token = CancelToken()
    token.cancel()
    provider = _BlockingProvider()
    agent = Agent(provider, ProjectContext.demo(), cancel_token=token)

    with pytest.raises(ProviderError) as caught:
        agent.handle("Draw a square.", request_id=1)

    assert caught.value.code == "cancelled"
    assert str(caught.value) == "cancelled: request cancelled by the client"
    assert provider.calls == 0


def test_cancel_while_queued_behind_the_semaphore_makes_zero_calls():
    provider = _GatedProvider()
    bridge = Bridge(Agent(provider, ProjectContext.demo()), max_concurrent=1)
    replies: dict[str, list] = {}

    def first() -> None:
        replies["first"] = bridge.handle([Sym("request"), 51, ["BLOCK on this one."], "Sprite1"])

    def second() -> None:
        replies["second"] = bridge.handle([Sym("request"), 52, ["SECOND request."], "Sprite1"])

    first_thread = _start(first)
    assert provider.entered.wait(5), "blocking request never reached the provider"

    second_thread = _start(second)
    # Registration happens before the turn waits for the semaphore.
    assert _wait_for(lambda: 52 in bridge._active), "queued request was not registered"
    assert bridge.handle([Sym("cancel"), 52]) == [[Sym("ok"), 52]]

    provider.release.set()
    _join(first_thread)
    _join(second_thread)

    assert replies["first"][0][0] == Sym("result")
    response = replies["second"][0]
    assert response[0] == Sym("error")
    assert response[1] == 52
    assert "cancelled" in response[2]
    assert 52 not in bridge.pending
    assert not any("SECOND request." in user for user in provider.calls)


def test_cancel_between_repairs_stops_the_loop(monkeypatch):
    token = CancelToken()
    provider = _CancellingRepairProvider()
    agent = Agent(provider, ProjectContext.demo(), max_repairs=2, cancel_token=token)
    repair_calls: list[int] = []
    original = agent_module._repair_prompt
    original_fragment = agent_module._fragment_repair_prompt

    def cancelling_repair_prompt(*args, **kwargs):
        repair_calls.append(1)
        token.cancel()
        return original(*args, **kwargs)

    def cancelling_fragment_prompt(*args, **kwargs):
        repair_calls.append(1)
        token.cancel()
        return original_fragment(*args, **kwargs)

    monkeypatch.setattr(agent_module, "_repair_prompt", cancelling_repair_prompt)
    monkeypatch.setattr(
        agent_module, "_fragment_repair_prompt", cancelling_fragment_prompt
    )

    with pytest.raises(ProviderError) as caught:
        agent.handle("Draw a square.", request_id=5)

    assert caught.value.code == "cancelled"
    assert repair_calls == [1], "the first repair prompt should be built once"
    assert provider.calls == 1, "cancellation must prevent the repair model call"


# --- ids that are not running ----------------------------------------------


def test_cancel_unknown_and_finished_ids_report_not_running():
    bridge = Bridge(Agent(MockLLM([draw_square_response()]), ProjectContext.demo()))

    assert bridge.handle([Sym("cancel"), 999]) == [[Sym("error"), 999, "not running"]]
    assert bridge.cancel(999) is False

    response = bridge.handle([Sym("request"), 7, ["Draw a square."], "Sprite1"])[0]
    assert response[0] == Sym("result")
    assert bridge.cancel(7) is False
    assert bridge.handle([Sym("cancel"), 7]) == [[Sym("error"), 7, "not running"]]
    assert 7 in bridge.pending


def test_cancelling_one_request_leaves_a_concurrent_one_untouched():
    provider = _TwoRequestProvider()
    bridge = Bridge(Agent(provider, ProjectContext.demo()), max_concurrent=2)
    replies: dict[str, list] = {}

    def turn_a() -> None:
        replies["a"] = bridge.handle(
            [Sym("request"), 31, ["MARKER_A draw a square."], "Sprite1"]
        )

    worker_a = _start(turn_a)
    assert provider.entered_a.wait(5), "request A never reached the provider"

    assert bridge.handle([Sym("cancel"), 31]) == [[Sym("ok"), 31]]

    # B runs concurrently while A is still parked inside its model call.
    replies["b"] = bridge.handle([Sym("request"), 32, ["Just draw a square."], "Sprite1"])

    provider.release_a.set()
    _join(worker_a)

    response_a = replies["a"][0]
    assert response_a[0] == Sym("error")
    assert response_a[1] == 31
    assert "cancelled" in response_a[2]

    response_b = replies["b"][0]
    assert response_b[0] == Sym("result")
    assert response_b[1] == 32
    assert 31 not in bridge.pending
    assert 32 in bridge.pending
    assert bridge.pending[32][0].request_id == 32


# --- #info ------------------------------------------------------------------


def test_info_has_the_exact_nine_element_shape_and_matches_the_bridge():
    bridge = Bridge(
        Agent(MockLLM([draw_square_response()]), ProjectContext.demo()),
        max_concurrent=3,
        turn_budget_s=120.0,
        profile="mock",
        model="mock-model",
        base_url="https://example.invalid/v1",
    )

    info = bridge.handle([Sym("info")])[0]

    assert len(info) == 9
    assert info[0] == Sym("info")
    assert info[1] == "ScratchAI/1"
    assert info[2] == "mock"
    assert info[3] == "mock-model"
    assert info[4] == "https://example.invalid/v1"
    assert info[5] == 120.0 and isinstance(info[5], float)
    assert info[6] == 3 and isinstance(info[6], int)
    assert info[7] == 0
    assert info[8] == ""

    assert bridge.handle([Sym("request"), 8, ["Draw a square."], "Sprite1"])[0][0] == Sym("result")
    assert bridge.handle([Sym("info")])[0][7] == 1

    assert bridge.handle([Sym("applied"), 8]) == [[Sym("ok"), 8]]
    assert bridge.handle([Sym("info")])[0][7] == 0


def test_info_defaults_to_empty_configuration_strings():
    bridge = Bridge(Agent(MockLLM([]), ProjectContext.demo()))
    info = bridge.handle([Sym("info")])[0]
    assert info[2:5] == ["", "", ""]


def test_default_bridge_fills_info_from_the_resolved_config():
    config = resolve_config("mock", config_path="missing.ini", env={})
    bridge = default_bridge(config=config)
    info = bridge.handle([Sym("info")])[0]
    assert info[2:5] == ["mock", config.model, config.base_url]
    assert info[5] == bridge.turn_budget_s
    assert info[6] == bridge.max_concurrent


def test_last_error_is_safe_short_and_cleared_by_a_later_success():
    secret = "oc_sk_test_secret_value"
    bridge = Bridge(
        Agent(_FailThenSucceedProvider(), ProjectContext.demo()),
        profile="opencode-go",
        model="deepseek-v4.1-flash",
        base_url="https://opencode.ai/inference/go/openai/v1",
    )

    failed = bridge.handle([Sym("request"), 1, ["Draw a square."], "Sprite1"])[0]
    assert failed[0] == Sym("error")
    assert "model error (auth, HTTP 401)" in failed[2]

    info = bridge.handle([Sym("info")])[0]
    assert info[8] == "auth: the endpoint rejected the API key"
    assert secret not in str(info)
    assert "Traceback" not in str(info)
    assert "Draw a square." not in str(info)

    succeeded = bridge.handle([Sym("request"), 2, ["Draw a square."], "Sprite1"])[0]
    assert succeeded[0] == Sym("result")
    assert bridge.handle([Sym("info")])[0][8] == ""


# --- logging --------------------------------------------------------------


def test_success_log_keeps_the_greppable_prefix_and_adds_attempts(caplog):
    caplog.set_level(logging.INFO, logger="harness.server")
    bridge = Bridge(Agent(MockLLM([draw_square_response()]), ProjectContext.demo()))

    response = bridge.handle([Sym("request"), 11, ["Draw a square."], "Sprite1"])[0]
    assert response[0] == Sym("result")

    message = next(
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("request id=11")
    )
    assert message.startswith("request id=11 outcome=ok changes=1 elapsed_ms=")
    assert message.endswith(" attempts=1")
