from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from harness.protocol import Sym, encode_frame, make_message, parse_literal, read_frame


async def main() -> None:
    reader, writer = await asyncio.open_connection("127.0.0.1", 8765)
    messages = [
        [Sym("hello"), "token", "ScratchAI/1"],
        [Sym("request"), 1, ["Make the cat draw a square when I click the green flag."], "Sprite1"],
        [Sym("applied"), 1],
        [Sym("request"), 2, ["Make it bigger and say Done!"], "Sprite1"],
    ]
    for message in messages:
        writer.write(encode_frame(make_message(*message)))
        await writer.drain()
        payload = await read_frame(reader)
        print("RECV:", parse_literal(payload.decode()))
    writer.close()
    await writer.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
