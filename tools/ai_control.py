from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge" / "src"))

from harness.protocol import encode_frame, make_message, message_type, parse_literal  # noqa: E402
from harness.smalltalk import Sym, to_literal  # noqa: E402

HOST = "127.0.0.1"
PORT = 8767
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8765


def recv_exact(sock: socket.socket, count: int) -> bytes:
    chunks: list[bytes] = []
    while count:
        chunk = sock.recv(count)
        if not chunk:
            raise ConnectionError("control server closed the connection")
        chunks.append(chunk)
        count -= len(chunk)
    return b"".join(chunks)


def request(parts: list[object], timeout: float = 180.0) -> str:
    payload = to_literal(parts).encode("utf-8")
    with socket.create_connection((HOST, PORT), timeout=10.0) as sock:
        sock.settimeout(timeout)
        sock.sendall(struct.pack(">I", len(payload)) + payload)
        header = recv_exact(sock, 4)
        length = struct.unpack(">I", header)[0]
        return recv_exact(sock, length).decode("utf-8", "replace")


def bridge_request(host: str, port: int, timeout: float = 2.0) -> str:
    """Send ``#(#info)`` to the bridge and return one raw reply frame.

    ``harness.protocol.read_frame`` is async; this client is deliberately
    synchronous, so it reads the 4-byte big-endian length and then exactly
    that many bytes.
    """
    payload = make_message(Sym("info")).encode("utf-8")
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(encode_frame(payload))
        try:
            header = recv_exact(sock, 4)
            length = struct.unpack(">I", header)[0]
            if length > 1_000_000:
                raise ValueError(f"reply frame is too large ({length} bytes)")
            return recv_exact(sock, length).decode("utf-8", "replace")
        except ConnectionError as exc:
            raise ConnectionError("bridge closed the connection before a full reply") from exc


def _number_text(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return str(value)


def bridge_status(args: argparse.Namespace) -> None:
    """Query the bridge's ``#info`` and print a readable block (or JSON)."""
    host, port = args.bridge_host, args.bridge_port
    try:
        raw = bridge_request(host, port)
    except (OSError, ConnectionError, ValueError) as exc:
        reason = str(exc).strip() or type(exc).__name__
        print(f"bridge: not reachable on {host}:{port} ({reason})")
        raise SystemExit(1) from exc

    try:
        reply = parse_literal(raw)
        kind = message_type(reply)
    except ValueError as exc:
        print(f"bridge: unreadable reply from {host}:{port}: {exc}")
        print(raw)
        raise SystemExit(1) from exc

    if kind != "info" or len(reply) != 9:
        print(f"bridge: unexpected reply from {host}:{port} (wanted #info):")
        print(raw)
        raise SystemExit(1)

    version, profile, model, base_url, budget, max_concurrent, pending, last_error = reply[1:]
    offline = str(profile) == "mock" or not str(base_url)
    shown_base_url = str(base_url) if str(base_url) else "-"
    shown_last_error = str(last_error) if str(last_error) else "-"

    if args.as_json:
        payload = {
            "ok": True,
            "host": host,
            "port": port,
            "version": str(version),
            "profile": str(profile),
            "model": str(model),
            "base_url": shown_base_url,
            "budget_s": budget,
            "max_concurrent": max_concurrent,
            "pending": pending,
            "last_error": shown_last_error,
            "offline": offline,
        }
        print(json.dumps(payload, indent=2))
        return

    print(f"bridge: {host}:{port} ok")
    print(f"version: {version}")
    print(f"profile: {profile}")
    print(f"model: {model}")
    print(f"base_url: {shown_base_url}")
    print(
        f"budget: {_number_text(budget)}s, "
        f"max_concurrent={_number_text(max_concurrent)}, "
        f"pending={_number_text(pending)}"
    )
    print(f"last_error: {shown_last_error}")
    if offline:
        print("note: offline mock profile (no network)")


def poll_send(send_id: str, timeout: float = 330.0) -> str:
    """Poll #poll <id> until the async send finishes or the timeout expires."""
    deadline = time.time() + timeout
    delay = 0.2
    while time.time() < deadline:
        reply = request([Sym("poll"), str(send_id)], timeout=15.0)
        if reply != "pending":
            return reply
        time.sleep(delay)
        delay = min(delay * 1.5, 1.0)
    return "pending"


def main() -> None:
    global PORT
    parser = argparse.ArgumentParser(description="Control the Scratch AI image without the GUI")
    parser.add_argument("--port", type=int, default=PORT)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("load", help="load an image/*.st script")
    p.add_argument("file")

    p = sub.add_parser("send", help="send a chat prompt through the bridge")
    p.add_argument("prompt", nargs="+")
    p.add_argument("--async", dest="async_", action="store_true",
                   help="queue the send and return an id immediately")
    p.add_argument("--wait", action="store_true",
                   help="with --async, poll until the reply is ready")

    p = sub.add_parser("poll", help="poll an asynchronous send id")
    p.add_argument("id")
    p.add_argument("--timeout", type=float, default=330.0)

    sub.add_parser("bootstrap", help="load image/00_bootstrap.st's file list")

    sub.add_parser("undo", help="undo the last change set")
    sub.add_parser("status", help="report scripts/registry/undo counts")
    sub.add_parser("log", help="read the chat pane log")
    sub.add_parser("context", help="dump the project context literal")

    p = sub.add_parser("save", help="save the image under a new name (no dialog)")
    p.add_argument("name")

    sub.add_parser("clean", help="remove all scripts/extra sprites and clear the chat")
    p = sub.add_parser("save-clean", help="clean the project, then save under a new image name")
    p.add_argument("name")

    p = sub.add_parser(
        "release-save",
        help="clean, enter end-user full screen, and save a release image",
    )
    p.add_argument("name")

    sub.add_parser("snapshot", help="snapshot in place (overwrite the current image)")
    sub.add_parser("doctor", help="image health: frame, server, scripts, paths")
    sub.add_parser("errors", help="tail the dev error log")
    sub.add_parser("config", help="show the parsed harness.ini")

    p = sub.add_parser("bridge-status", help="show the bridge's #info (default 127.0.0.1:8765)")
    p.add_argument("--bridge-host", default=BRIDGE_HOST)
    p.add_argument("--bridge-port", type=int, default=BRIDGE_PORT)
    p.add_argument("--json", dest="as_json", action="store_true",
                   help="print the #info fields as a JSON object")

    p = sub.add_parser("project-open", help="open a .sb project by absolute path")
    p.add_argument("path")

    p = sub.add_parser("project-save", help="save the project to an absolute .sb path")
    p.add_argument("path")

    p = sub.add_parser("project-export-text", help="export a git-diffable text project to a directory")
    p.add_argument("path")

    p = sub.add_parser("project-import-text", help="import a text project directory")
    p.add_argument("path")

    args = parser.parse_args()

    PORT = args.port

    if args.cmd == "load":
        reply = request([Sym("load"), args.file], timeout=600.0)
    elif args.cmd == "send":
        prompt = " ".join(args.prompt).strip()
        if not prompt:
            parser.error("prompt is required")
        prompt = prompt.replace("\r", " ").replace("\n", " ")
        if args.async_:
            reply = request([Sym("send-async"), prompt], timeout=30.0)
            print(reply)
            if args.wait and reply.startswith("ok send "):
                send_id = reply.split()[-1]
                reply = poll_send(send_id)
            else:
                raise SystemExit(0)
        else:
            reply = request([Sym("send"), prompt], timeout=330.0)
    elif args.cmd == "poll":
        reply = poll_send(args.id, timeout=args.timeout)
    elif args.cmd == "bootstrap":
        reply = request([Sym("bootstrap")], timeout=600.0)
    elif args.cmd == "undo":
        reply = request([Sym("undo")])
    elif args.cmd == "status":
        reply = request([Sym("status")])
    elif args.cmd == "log":
        reply = request([Sym("log")])
    elif args.cmd == "context":
        reply = request([Sym("context")])
    elif args.cmd == "save":
        reply = request([Sym("save"), args.name], timeout=300.0)
    elif args.cmd == "clean":
        reply = request([Sym("clean")], timeout=180.0)
    elif args.cmd == "save-clean":
        reply = request([Sym("save-clean"), args.name], timeout=300.0)
    elif args.cmd == "release-save":
        reply = request([Sym("release-save"), args.name], timeout=300.0)
    elif args.cmd == "snapshot":
        reply = request([Sym("snapshot")], timeout=300.0)
    elif args.cmd == "doctor":
        reply = request([Sym("doctor")])
    elif args.cmd == "errors":
        reply = request([Sym("errors")])
    elif args.cmd == "config":
        reply = request([Sym("config")])
    elif args.cmd == "bridge-status":
        bridge_status(args)
        raise SystemExit(0)
    elif args.cmd == "project-open":
        reply = request([Sym("project"), Sym("open"), args.path], timeout=120.0)
    elif args.cmd == "project-save":
        reply = request([Sym("project"), Sym("save"), args.path], timeout=120.0)
    elif args.cmd == "project-export-text":
        path = Path(args.path).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        reply = request([Sym("project"), Sym("export-text"), str(path)], timeout=180.0)
    elif args.cmd == "project-import-text":
        path = Path(args.path).expanduser().resolve()
        if not path.is_dir():
            parser.error(f"directory not found: {path}")
        reply = request([Sym("project"), Sym("import-text"), str(path)], timeout=180.0)
    else:  # pragma: no cover
        parser.error("unknown command")
    print(reply)


if __name__ == "__main__":
    main()
