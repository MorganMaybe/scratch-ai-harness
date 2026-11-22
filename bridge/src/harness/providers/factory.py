"""Provider construction from a resolved ``ModelConfig``."""

from __future__ import annotations

from typing import Any

from ..config import ConfigError, ModelConfig
from .base import ModelProvider
from .mock import MockProvider
from .openai_compat import OpenAICompatProvider

#: Canned replies for the offline demo path (add square, then replace it).
def demo_responses() -> list[dict[str, Any]]:
    from ..llm import bigger_square_response, draw_square_response

    return [draw_square_response(), bigger_square_response()]


def build_provider(
    config: ModelConfig,
    responses: list[dict[str, Any]] | None = None,
    *,
    api_key: str | None = None,
) -> ModelProvider:
    """Create the backend for ``config``. Raises on missing/misconfigured keys."""
    if config.is_mock:
        return MockProvider(demo_responses() if responses is None else responses, config)
    try:
        return OpenAICompatProvider(config, api_key=api_key)
    except ConfigError as exc:
        # Reclassified so callers see the same stable taxonomy as a live 401.
        from .base import ProviderError

        raise ProviderError("auth", str(exc)) from exc
