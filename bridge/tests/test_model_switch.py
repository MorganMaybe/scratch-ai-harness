from __future__ import annotations

from pathlib import Path

from harness.config import MODEL_CHOICES, ModelConfig
from harness.llm import draw_square_response
from harness.providers.mock import DelayedLLM, MockProvider
from harness.protocol import Sym, make_message, parse_literal
from harness.server import default_bridge


def opencode_config(model: str = "deepseek-v4.1-flash") -> ModelConfig:
    return ModelConfig(
        profile="opencode-go",
        base_url="https://opencode.ai/inference/go/openai/v1",
        model=model,
    )


def make_bridge(inner=None, config: ModelConfig | None = None):
    config = config or opencode_config()
    provider = inner or MockProvider([draw_square_response()], config)
    bridge = default_bridge(config=config, provider=provider)
    return bridge, provider


def test_models_lists_choices_and_active_model():
    bridge, _ = make_bridge()
    reply = bridge.handle([Sym("models")])[0]
    assert reply[0] == Sym("models")
    assert reply[1] == list(MODEL_CHOICES[0])
    assert reply[2] == list(MODEL_CHOICES[1])
    assert reply[3] == "deepseek-v4.1-flash"


def test_select_model_updates_info_usage_and_provider():
    bridge, provider = make_bridge()
    reply = bridge.handle([Sym("selectModel"), 2])[0]
    assert reply == [Sym("model"), "hy4-flash-free", "HY4 Flash Free"]
    assert bridge.model == "hy4-flash-free"
    assert bridge.model_config is not None
    assert bridge.model_config.model == "hy4-flash-free"
    assert provider.config.model == "hy4-flash-free"
    # The read-only surfaces reflect the switch immediately.
    assert bridge.handle([Sym("info")])[0][3] == "hy4-flash-free"
    assert bridge.handle([Sym("usage")])[0][5] == "hy4-flash-free"


def test_select_model_reaches_through_wrappers():
    config = opencode_config()
    inner = MockProvider([draw_square_response()], config)
    bridge, _ = make_bridge(inner=DelayedLLM(inner, 0), config=config)
    bridge.handle([Sym("selectModel"), 2])
    assert inner.config.model == "hy4-flash-free"


def test_select_model_rejects_unknown_index():
    bridge, _ = make_bridge()
    reply = bridge.handle([Sym("selectModel"), 3])[0]
    assert reply[0] == Sym("modelError")
    assert "unknown model index" in reply[1]
    assert bridge.model == "deepseek-v4.1-flash"


def test_switcher_is_disabled_for_non_gateway_profiles():
    config = ModelConfig(profile="mock", base_url="", model="mock")
    bridge, _ = make_bridge(config=config)
    assert bridge.model_choices == ()
    assert bridge.handle([Sym("models")])[0] == [Sym("models"), "mock"]
    reply = bridge.handle([Sym("selectModel"), 1])[0]
    assert reply == [Sym("modelError"), "model switching is unavailable"]


def test_models_reply_round_trips_as_a_smalltalk_literal():
    bridge, _ = make_bridge()
    reply = bridge.handle([Sym("models")])[0]
    wire = make_message(*reply)
    assert wire == (
        "#(#models #('deepseek-v4.1-flash' 'DeepSeek') "
        "#('hy4-flash-free' 'HY4 Flash Free') 'deepseek-v4.1-flash')"
    )
    assert parse_literal(wire) == reply


def test_image_select_literal_parses():
    assert parse_literal("#(#selectModel 2)") == [Sym("selectModel"), 2]


def test_image_switcher_matches_bridge_choices():
    image = (
        Path(__file__).resolve().parents[2] / "image" / "38_bridge_usage_ui.st"
    ).read_text(encoding="utf-8")
    for model_id, label in MODEL_CHOICES:
        assert model_id in image
        assert f"''{label}''" in image


def test_info_contract_keeps_nine_elements_after_switch():
    bridge, _ = make_bridge()
    bridge.handle([Sym("selectModel"), 2])
    assert len(bridge.handle([Sym("info")])[0]) == 9
