from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass
from typing import Any

from .smalltalk import Sym, to_literal

MAX_FRAME = 1_000_000


class ProtocolError(ValueError):
    pass


@dataclass
class Reader:
    text: str
    pos: int = 0

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def take(self) -> str:
        ch = self.peek()
        self.pos += 1
        return ch

    def skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def expect(self, ch: str) -> None:
        self.skip_ws()
        if self.peek() != ch:
            raise ProtocolError(f"expected {ch!r} at position {self.pos}")
        self.pos += 1


def parse_literal(text: str) -> Any:
    reader = Reader(text)
    value = _parse(reader, 0)
    reader.skip_ws()
    if reader.pos != len(reader.text):
        raise ProtocolError(f"trailing data at position {reader.pos}")
    return value


def _parse(reader: Reader, depth: int) -> Any:
    if depth > 60:
        raise ProtocolError("literal nesting is too deep")
    reader.skip_ws()
    ch = reader.peek()
    if not ch:
        raise ProtocolError("unexpected end of literal")
    if ch == "#":
        reader.take()
        if reader.peek() == "(":
            return _parse_array(reader, depth + 1)
        return Sym(_parse_symbol_name(reader))
    if ch == "(":
        return _parse_array(reader, depth + 1)
    if ch == "'":
        return _parse_string(reader)
    if ch == "-" or ch.isdigit():
        return _parse_number(reader)
    if ch.isalpha() or ch == "_":
        token = _parse_bare_token(reader)
        if token == "true":
            return True
        if token == "false":
            return False
        if token == "nil":
            return None
        return Sym(token)
    raise ProtocolError(f"unexpected character {ch!r} at position {reader.pos}")


def _parse_array(reader: Reader, depth: int) -> list[Any]:
    reader.expect("(")
    result: list[Any] = []
    while True:
        reader.skip_ws()
        if reader.peek() == ")":
            reader.take()
            return result
        if not reader.peek():
            raise ProtocolError("unterminated array")
        result.append(_parse(reader, depth))
        if len(result) > 100_000:
            raise ProtocolError("array is too large")


def _parse_string(reader: Reader) -> str:
    reader.expect("'")
    out: list[str] = []
    while True:
        if not reader.peek():
            raise ProtocolError("unterminated string")
        ch = reader.take()
        if ch == "'":
            if reader.peek() == "'":
                reader.take()
                out.append("'")
                continue
            return "".join(out)
        out.append(ch)


def _parse_symbol_name(reader: Reader) -> str:
    start = reader.pos
    while reader.pos < len(reader.text):
        ch = reader.text[reader.pos]
        if ch.isspace() or ch in "()":
            break
        reader.pos += 1
    if reader.pos == start:
        raise ProtocolError("empty symbol")
    return reader.text[start : reader.pos]


def _parse_bare_token(reader: Reader) -> str:
    start = reader.pos
    while reader.pos < len(reader.text):
        ch = reader.text[reader.pos]
        if ch.isspace() or ch in "()":
            break
        reader.pos += 1
    return reader.text[start : reader.pos]


def _parse_number(reader: Reader) -> int | float:
    start = reader.pos
    if reader.peek() == "-":
        reader.take()
    while reader.peek().isdigit():
        reader.take()
    if reader.peek() == ".":
        reader.take()
        while reader.peek().isdigit():
            reader.take()
    token = reader.text[start : reader.pos]
    try:
        return float(token) if "." in token else int(token)
    except ValueError as exc:
        raise ProtocolError(f"invalid number {token!r}") from exc


def message_type(message: Any) -> str:
    if not isinstance(message, list) or not message:
        raise ProtocolError("message must be a non-empty array")
    first = message[0]
    if isinstance(first, Sym):
        return first.name
    if isinstance(first, str):
        return first
    raise ProtocolError("message type must be a symbol or string")


def make_message(*parts: Any) -> str:
    return to_literal(list(parts))


def encode_frame(payload: str | bytes) -> bytes:
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    if len(data) > MAX_FRAME:
        raise ProtocolError("frame is too large")
    return struct.pack(">I", len(data)) + data


def decode_frame(data: bytes) -> tuple[bytes, bytes]:
    if len(data) < 4:
        raise ProtocolError("incomplete frame header")
    length = struct.unpack(">I", data[:4])[0]
    if length > MAX_FRAME:
        raise ProtocolError("frame is too large")
    if len(data) < 4 + length:
        raise ProtocolError("incomplete frame")
    return data[4 : 4 + length], data[4 + length :]


async def read_frame(reader: asyncio.StreamReader) -> bytes:
    header = await reader.readexactly(4)
    length = struct.unpack(">I", header)[0]
    if length > MAX_FRAME:
        raise ProtocolError("frame is too large")
    return await reader.readexactly(length)
