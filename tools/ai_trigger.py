from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "scratch" / "base"


def write_trigger(name: str, text: str) -> None:
    """Write atomically so the image never reads a half-written trigger."""
    target = BASE / name
    tmp = BASE / (name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)


def wait_gone(name: str, timeout: float = 10.0) -> bool:
    target = BASE / name
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not target.exists():
            return True
        time.sleep(0.05)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Drive the Scratch AI dev watcher")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("load", help="load an image/*.st script")
    p.add_argument("file")

    p = sub.add_parser("send", help="send a chat prompt through the bridge")
    p.add_argument("prompt", nargs=argparse.REMAINDER)

    sub.add_parser("undo", help="undo the last change set")

    args = parser.parse_args()

    if args.cmd == "load":
        write_trigger("ai_load.txt", args.file)
        ok = wait_gone("ai_load.txt")
        print("load trigger consumed" if ok else "load trigger still pending")
    elif args.cmd == "send":
        prompt = " ".join(args.prompt).strip()
        if not prompt:
            parser.error("prompt is required")
        write_trigger("ai_send.txt", prompt)
        ok = wait_gone("ai_send.txt")
        print("send trigger consumed" if ok else "send trigger still pending")
    elif args.cmd == "undo":
        write_trigger("ai_undo.txt", "")
        ok = wait_gone("ai_undo.txt")
        print("undo trigger consumed" if ok else "undo trigger still pending")


if __name__ == "__main__":
    main()
