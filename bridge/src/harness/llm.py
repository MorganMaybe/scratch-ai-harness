"""Compatibility shim for the original ``harness.llm`` module.

Everything importable from here before is still importable: ``MockLLM``,
``DelayedLLM``, ``DeepSeekLLM``, ``LLMError``, ``LLMClient``,
``parse_json_object`` and the canned responses. New code should use
``harness.providers`` and ``harness.config`` directly.
"""

from __future__ import annotations

from typing import Any

from .config import resolve_config, with_overrides
from .providers.base import (
    BaseProvider,
    ModelProvider,
    ModelReply,
    ModelRequest,
    ProviderError,
    parse_json_object,
    remaining_seconds,
)
from .providers.mock import DelayedLLM, MockLLM, MockProvider
from .providers.openai_compat import OpenAICompatProvider

#: Legacy name for the classified error type.
LLMError = ProviderError

#: Legacy protocol name.
LLMClient = ModelProvider

__all__ = [
    "BaseProvider",
    "DeepSeekLLM",
    "DelayedLLM",
    "LLMClient",
    "LLMError",
    "MockLLM",
    "MockProvider",
    "ModelProvider",
    "ModelReply",
    "ModelRequest",
    "OpenAICompatProvider",
    "ProviderError",
    "bigger_square_response",
    "draw_square_response",
    "parse_json_object",
    "remaining_seconds",
]


class DeepSeekLLM(OpenAICompatProvider):
    """Legacy class name, now an OpenAI-compatible provider.

    Defaults come from the resolved profile (OpenCode Go), not from the old
    hardcoded ``api.deepseek.com`` / ``deepseek-flash`` pair.
    """

    name = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        thinking: str = "off",
        session_id: str | None = None,
    ):
        base = resolve_config(model=model, base_url=base_url)
        config = with_overrides(
            base,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking=thinking,
            session_id=session_id or base.session_id,
        )
        super().__init__(config, api_key=api_key)


def draw_square_response() -> dict[str, Any]:
    return {
        "summary": "Added a green-flag square-drawing script.",
        "changes": [
            {
                "action": "add_script",
                "target": "Sprite1",
                "label": "draw_square",
                "hat": {"op": "when_flag_clicked"},
                "body": [
                    {"op": "pen_clear"},
                    {"op": "pen_down"},
                    {
                        "op": "repeat",
                        "args": {"count": 4},
                        "body": [
                            {"op": "move", "args": {"steps": 100}},
                            {"op": "turn_right", "args": {"degrees": 90}},
                        ],
                    },
                    {"op": "pen_up"},
                ],
            }
        ],
        "notes": "Click the green flag to try it.",
    }


def bigger_square_response(script_id: str = "ai-1") -> dict[str, Any]:
    return {
        "summary": "Updated the square script and added a Done message.",
        "changes": [
            {
                "action": "replace_script",
                "script_id": script_id,
                "target": "Sprite1",
                "label": "draw_square",
                "hat": {"op": "when_flag_clicked"},
                "body": [
                    {"op": "pen_clear"},
                    {"op": "pen_down"},
                    {
                        "op": "repeat",
                        "args": {"count": 4},
                        "body": [
                            {"op": "move", "args": {"steps": 200}},
                            {"op": "turn_right", "args": {"degrees": 90}},
                        ],
                    },
                    {"op": "pen_up"},
                    {"op": "say", "args": {"text": "Done!"}},
                ],
            }
        ],
        "notes": "The bigger square replaces the original script.",
    }
