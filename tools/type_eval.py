from __future__ import annotations

import argparse
import time
from pathlib import Path

import pyautogui

import scratch_gui


def type_text(text: str) -> None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line:
            pyautogui.write(line, interval=0.005)
        if i < len(lines) - 1:
            pyautogui.press("enter")
            time.sleep(0.05)


def focus_and_click(x: int, y: int) -> None:
    scratch_gui.focus_window()
    time.sleep(0.4)
    # First click activates the window on Windows, second places the caret.
    pyautogui.click(x, y)
    time.sleep(0.4)
    pyautogui.click(x, y)
    time.sleep(0.4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="text file containing Smalltalk code")
    parser.add_argument("--x", type=int, default=400)
    parser.add_argument("--y", type=int, default=400)
    parser.add_argument("--no-select", action="store_true")
    parser.add_argument("--no-doit", action="store_true")
    args = parser.parse_args()

    text = Path(args.file).read_text(encoding="utf-8")
    focus_and_click(args.x, args.y)
    if not args.no_select:
        pyautogui.hotkey("alt", "a")
        time.sleep(0.3)
    type_text(text)
    time.sleep(0.5)
    if not args.no_doit:
        pyautogui.hotkey("alt", "d")
        time.sleep(1.0)
    print("typed")


if __name__ == "__main__":
    main()
