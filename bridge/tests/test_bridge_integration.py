"""Integration checks for the pieces wired after Phases 2 and 3 landed.

These cover the seam between the socket layer, the bridge and the agent: turn
deadline, request-scoped error ids, and safe wire messages.
"""

from __future__ import annotations

import asyncio
import time

from harness.agent import Agent
from harness.context import ProjectContext
from harness.providers.base import ProviderError
from harness.protocol import Sym, encode_frame, make_message, parse_literal, read_frame
from harness.server import Bridge, BridgeServer, _request_id, default_bridge
from harness.llm import MockLLM


def test_bridge_passes_a_turn_deadline(monkeypatch):
    import harness.server as server_module

    captured: list[float | None] = []

    class RecordingAgent(Agent):
        def handle(self, request, request_id=1, *, deadline=None):
            captured.append(deadline)
            raise ProviderError("timeout", "turn budget exhausted")

    monkeypatch.setattr(server_module, "Agent", RecordingAgent)
    bridge = Bridge(Agent(MockLLM([]), ProjectContext.demo()), turn_budget_s=240.0)

    started = time.monotonic()
    response = bridge.handle([Sym("request"), 9, ["Draw a square."], "Sprite1"])[0]

    assert response[0] == Sym("error")
    assert response[1] == 9
    assert "timeout" in str(response[2])
    assert captured and captured[0] is not None
    assert 230 < (captured[0] - started) <= 240.1


def test_request_scoped_error_reply_from_the_socket_layer():
    class ExplodingBridge:
        def handle(self, message):
            raise ValueError("prompt must be a string")

    async def run():
        server = BridgeServer("127.0.0.1", 0, ExplodingBridge())
        await server.start()
        port = server._server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(encode_frame(make_message(Sym("request"), 42, ["hi"], "Sprite1")))
        await writer.drain()
        message = parse_literal((await read_frame(reader)).decode())
        writer.close()
        await writer.wait_closed()
        server._server.close()
        await server._server.wait_closed()
        return message

    message = asyncio.run(run())
    assert message[0] == Sym("error")
    assert message[1] == 42, "a failed request must keep its id, not answer id 0"
    assert "prompt must be a string" in message[2]


def test_request_id_helper():
    assert _request_id([Sym("request"), 77, ["x"], "Sprite1"]) == 77
    assert _request_id([Sym("applied"), 5]) == 5
    assert _request_id([Sym("hello"), "token", "ScratchAI/1"]) == 0
    assert _request_id(None) == 0
    assert _request_id([Sym("request"), "not-an-int"]) == 0


def test_default_bridge_from_mock_profile():
    from harness.config import resolve_config

    bridge = default_bridge(config=resolve_config("mock", config_path="missing.ini", env={}))
    assert bridge.turn_budget_s == 240.0
    assert bridge.max_concurrent == 2
    response = bridge.handle([Sym("request"), 3, ["Draw a square."], "Sprite1"])[0]
    assert response[0] == Sym("result")
    assert response[1] == 3


def test_contextless_clients_keep_the_legacy_accumulating_demo():
    """No context element (mock demos) still sees its own earlier changes."""
    bridge = default_bridge(mock=True)
    first = bridge.handle([Sym("request"), 1, ["Draw a square."], "Sprite1"])[0]
    assert first[0] == Sym("result")
    assert bridge.handle([Sym("applied"), 1])[0][0] == Sym("ok")

    second = bridge.handle([Sym("request"), 2, ["Make it bigger."], "Sprite1"])[0]
    assert second[0] == Sym("result"), "second offline demo request must still resolve"
    assert second[1] == 2

