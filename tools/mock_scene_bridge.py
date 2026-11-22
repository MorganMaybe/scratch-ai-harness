"""Run a deterministic 8765 bridge that returns one scene change set.

Useful for verifying the image applier end to end without a model call:

    python tools\\mock_scene_bridge.py
    python tools\\ai_control.py send --async "make a bat scene" --wait
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge" / "src"))

from harness.agent import Agent  # noqa: E402
from harness.context import ProjectContext  # noqa: E402
from harness.providers.mock import MockProvider  # noqa: E402
from harness.server import Bridge, BridgeServer  # noqa: E402

SCENE = {
    "summary": "Added a spinning bat and a stars backdrop.",
    "changes": [
        {
            "action": "create_sprite",
            "name": "Bat",
            "costumes": [{"library": "Animals/bat1-a.png"}],
            "x": 0,
            "y": 0,
            "direction": 90,
            "size": 80,
            "visible": True,
            "rotation_style": "left-right",
        },
        {
            "action": "add_script",
            "target": "Bat",
            "label": "spin",
            "hat": {"op": "when_flag_clicked"},
            "body": [
                {
                    "op": "forever",
                    "body": [{"op": "turn_right", "args": {"degrees": 15}}],
                }
            ],
        },
        {"action": "set_backdrop", "library": "Space/stars.gif", "select": True},
        {
            "action": "add_script",
            "target": "Stage",
            "label": "stars_on_start",
            "hat": {"op": "when_flag_clicked"},
            "body": [
                {"op": "switch_backdrop", "args": {"backdrop": "stars"}}
            ],
        },
    ],
}


async def main() -> None:
    provider = MockProvider([SCENE])
    bridge = Bridge(Agent(provider, ProjectContext.demo()))
    bridge.profile = "mock"
    bridge.model = "mock-scene"
    bridge.base_url = ""
    await BridgeServer("127.0.0.1", 8765, bridge).serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
