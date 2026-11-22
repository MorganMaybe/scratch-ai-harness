from __future__ import annotations

import asyncio
import time

from harness.agent import Agent
from harness.context import ProjectContext
from harness.llm import DelayedLLM, MockLLM, draw_square_response
from harness.protocol import Sym, encode_frame, make_message, parse_literal, read_frame
from harness.server import Bridge, BridgeServer


def make_bridge() -> Bridge:
    context = ProjectContext.demo()
    return Bridge(Agent(MockLLM([draw_square_response()]), context))


def test_bridge_hello():
    bridge = make_bridge()
    responses = bridge.handle([Sym("hello"), "token", "ScratchAI/1"])
    assert responses[0][0] == Sym("hello-ok")


def test_bridge_request_and_applied():
    bridge = make_bridge()
    responses = bridge.handle([Sym("request"), 5, ["Draw a square."], "Sprite1"])
    result = responses[0]
    assert result[0] == Sym("result")
    assert result[1] == 5
    assert any("draw_square" in line for line in result[2])
    assert result[3][0] == Sym("apply")
    applied = bridge.handle([Sym("applied"), 5])
    assert applied[0] == [Sym("ok"), 5]
    assert "ai-1" in bridge.agent.registry


def test_bridge_unknown_message():
    bridge = make_bridge()
    try:
        bridge.handle([Sym("nope")])
    except Exception as exc:
        assert "unknown message type" in str(exc)
    else:
        raise AssertionError("expected an error")


def test_async_server_roundtrip():
    bridge = make_bridge()

    async def run() -> list:
        server = await asyncio.start_server(
            lambda r, w: _handle_client(bridge, r, w),
            "127.0.0.1",
            0,
        )
        port = server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(encode_frame(make_message(Sym("hello"), "token", "ScratchAI/1")))
        await writer.drain()
        payload = await read_frame(reader)
        message = parse_literal(payload.decode())
        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()
        return message

    message = asyncio.run(run())
    assert message[0] == Sym("hello-ok")


def test_delayed_llm_wraps_response():
    inner = MockLLM([draw_square_response()])
    llm = DelayedLLM(inner, 0.01)
    payload = llm.complete_json("system", "user")
    assert "green-flag" in payload["summary"]
    assert inner.calls


def test_server_answers_while_request_is_slow():
    context = ProjectContext.demo()
    bridge = Bridge(Agent(DelayedLLM(MockLLM([draw_square_response()]), 1.0), context))

    async def run() -> tuple[float, list, list]:
        server = BridgeServer("127.0.0.1", 0, bridge)
        await server.start()
        port = server._server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(encode_frame(make_message(Sym("request"), 1, ["Draw a square."], "Sprite1")))
        await writer.drain()

        # While the request is sleeping in the LLM, a hello must still answer.
        reader2, writer2 = await asyncio.open_connection("127.0.0.1", port)
        started = time.monotonic()
        writer2.write(encode_frame(make_message(Sym("hello"), "token", "ScratchAI/1")))
        await writer2.drain()
        hello_payload = await asyncio.wait_for(read_frame(reader2), timeout=0.5)
        elapsed = time.monotonic() - started

        request_payload = await asyncio.wait_for(read_frame(reader), timeout=3.0)

        writer.close()
        writer2.close()
        await writer.wait_closed()
        await writer2.wait_closed()
        server._server.close()
        await server._server.wait_closed()
        return (
            elapsed,
            parse_literal(hello_payload.decode()),
            parse_literal(request_payload.decode()),
        )

    elapsed, hello, result = asyncio.run(run())
    assert elapsed < 0.5
    assert hello[0] == Sym("hello-ok")
    assert result[0] == Sym("result")


async def _handle_client(bridge: Bridge, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            payload = await read_frame(reader)
            message = parse_literal(payload.decode())
            for response in bridge.handle(message):
                writer.write(encode_frame(make_message(*response)))
            await writer.drain()
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    finally:
        writer.close()
