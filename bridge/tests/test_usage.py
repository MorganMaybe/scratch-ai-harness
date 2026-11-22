from __future__ import annotations

from types import SimpleNamespace

from harness.agent import Agent
from harness.context import ProjectContext
from harness.llm import MockLLM, draw_square_response
from harness.obs import bridge_usage
from harness.protocol import Sym
from harness.server import Bridge


def make_bridge(**overrides) -> Bridge:
    context = ProjectContext.demo()
    return Bridge(Agent(MockLLM([draw_square_response()]), context), **overrides)


def test_usage_shape_and_defaults():
    bridge = make_bridge()
    responses = bridge.handle([Sym("usage")])
    assert len(responses) == 1
    reply = responses[0]
    assert reply[0] == Sym("usage")
    # selector + 8 fields
    assert len(reply) == 9
    (
        _kind,
        prompt,
        completion,
        total,
        requests,
        model,
        profile,
        api_key_env,
        key_present,
    ) = reply
    assert (prompt, completion, total, requests) == (0, 0, 0, 0)
    assert isinstance(key_present, bool)
    assert model == "" and profile == ""


def test_usage_counts_a_completed_turn():
    bridge = make_bridge()
    response = bridge.handle([Sym("request"), 1, ["Draw a square."], "Sprite1"])
    assert response[0][0] == Sym("result")
    reply = bridge.handle([Sym("usage")])[0]
    assert reply[4] == 1  # requests
    # MockLLM reports no usage; the turn still counts.
    assert reply[1] == 0 and reply[2] == 0 and reply[3] == 0


def test_usage_accumulates_token_totals():
    bridge = make_bridge(profile="opencode-go", model="deepseek-v4.1-flash")
    with bridge._state_lock:
        bridge._record_usage(
            SimpleNamespace(
                usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
                model="deepseek-v4.1-flash",
            )
        )
        bridge._record_usage(
            SimpleNamespace(
                usage={"prompt_tokens": 50, "completion_tokens": 10},
                model="deepseek-v4.1-flash",
            )
        )
    reply = bridge_usage(bridge)
    assert reply[1:5] == [150, 30, 180, 2]
    assert reply[5] == "deepseek-v4.1-flash"
    assert reply[6] == "opencode-go"


def test_usage_never_contains_the_key_value():
    bridge = make_bridge(api_key_env="DEEPSEEK_API_KEY", api_key_present=True)
    reply = bridge_usage(bridge)
    text = " ".join(str(field) for field in reply)
    assert "DEEPSEEK_API_KEY" in text
    assert "oc_sk_" not in text
    assert "sk-" not in text
    assert reply[7] == "DEEPSEEK_API_KEY"
    assert reply[8] is True


def test_info_contract_is_unchanged():
    bridge = make_bridge()
    reply = bridge.handle([Sym("info")])[0]
    assert reply[0] == Sym("info")
    assert len(reply) == 9
