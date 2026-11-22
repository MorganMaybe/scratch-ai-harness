from __future__ import annotations

import pytest

from harness.protocol import (
    ProtocolError,
    Sym,
    decode_frame,
    encode_frame,
    make_message,
    message_type,
    parse_literal,
)


def test_parse_array_and_symbols():
    value = parse_literal("#(hello 'world' #(a 1 2.5 true false nil))")
    assert value[0] == Sym("hello")
    assert value[1] == "world"
    assert value[2][0] == Sym("a")
    assert value[2][1] == 1
    assert value[2][2] == 2.5
    assert value[2][3] is True
    assert value[2][4] is False
    assert value[2][5] is None


def test_parse_doubled_quotes():
    assert parse_literal("'it''s fine'") == "it's fine"


def test_parse_negative_number():
    assert parse_literal("#(turnLeft: -15)") == [Sym("turnLeft:"), -15]


def test_parse_selector_symbol():
    assert parse_literal("#(changeVariable 'score' #setVar:to: 0)") == [
        Sym("changeVariable"),
        "score",
        Sym("setVar:to:"),
        0,
    ]


def test_parse_trailing_data_rejected():
    with pytest.raises(ProtocolError):
        parse_literal("#(a) junk")


def test_message_roundtrip():
    text = make_message(Sym("result"), 3, ["line one", "line two"], [Sym("ok")])
    assert parse_literal(text) == [Sym("result"), 3, ["line one", "line two"], [Sym("ok")]]
    assert message_type(parse_literal(text)) == "result"


def test_frame_roundtrip():
    frame = encode_frame("#(hello)")
    payload, rest = decode_frame(frame)
    assert payload == b"#(hello)"
    assert rest == b""


def test_frame_incomplete():
    with pytest.raises(ProtocolError):
        decode_frame(b"\x00\x00")
