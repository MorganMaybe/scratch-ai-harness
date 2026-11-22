"""Watch image/*.st and reload changed files in the running image.

Usage:
    python tools\\watch_st.py                  # watch image/*.st forever
    python tools\\watch_st.py --once 09_undo.st  # load these files once
    python tools\\watch_st.py --interval 0.5 --settle 0.8

The watcher is deliberately host-side: no extra code runs in the image, and a
bad file is reported by load: instead of wedging the control server.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_control  # noqa: E402

from harness.protocol import Sym  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "image"


def snapshot(directory: Path) -> dict[str, float]:
    return {p.name: p.stat().st_mtime for p in directory.glob("*.st")}


def load_one(name: str, timeout: float = 120.0) -> None:
    try:
        reply = ai_control.request([Sym("load"), name], timeout=timeout)
        print(f"{name} -> {reply}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"{name} !! {exc}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reload image/*.st when they change")
    parser.add_argument("files", nargs="*", help="files for --once (default: all)")
    parser.add_argument("--once", action="store_true", help="load and exit")
    parser.add_argument("--interval", type=float, default=0.75)
    parser.add_argument("--settle", type=float, default=0.6, help="debounce after the last change")
    parser.add_argument("--dir", default=str(IMAGE_DIR))
    args = parser.parse_args()

    directory = Path(args.dir)
    if not directory.is_dir():
        parser.error(f"not a directory: {directory}")

    if args.once:
        names = args.files or sorted(snapshot(directory))
        for name in names:
            load_one(name)
        return 0

    print(f"watching {directory} (Ctrl+C to stop)", flush=True)
    previous = snapshot(directory)
    while True:
        time.sleep(args.interval)
        current = snapshot(directory)
        changed = sorted(
            name
            for name, mtime in current.items()
            if previous.get(name) != mtime
        )
        previous = current
        if not changed:
            continue
        # Wait for writes to settle, then reload the latest mtimes.
        time.sleep(args.settle)
        previous = snapshot(directory)
        for name in changed:
            if (directory / name).exists():
                load_one(name)
        print("watching...", flush=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nstopped")
