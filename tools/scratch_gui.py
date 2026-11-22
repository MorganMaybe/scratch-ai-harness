from __future__ import annotations

import argparse
import ctypes
import time
from ctypes import wintypes
from pathlib import Path

import pyautogui
import pygetwindow as gw
from PIL import ImageGrab

TITLE_PREFIX = "Scratch 1.4 ("
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040

user32 = ctypes.windll.user32


def is_scratch_window(title: str) -> bool:
    # The title gains a modal prefix such as "Quit?!" while a dialog is up,
    # and a blank project is just "Scratch 1.4 - Scratch", so match the product
    # prefix or the image path instead of the exact image-name suffix.
    return (
        title.startswith(TITLE_PREFIX)
        or title.startswith("Scratch 1.4")
        or ".image" in title.lower()
    )


def find_window() -> gw.Win32Window:
    for _ in range(40):
        for w in gw.getAllWindows():
            if is_scratch_window(w.title):
                return w
        time.sleep(0.25)
    raise RuntimeError("Scratch window not found")


def window_rect() -> tuple[int, int, int, int]:
    w = find_window()
    rect = wintypes.RECT()
    user32.GetWindowRect(w._hWnd, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right, rect.bottom)


def client_origin() -> tuple[int, int]:
    w = find_window()
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(w._hWnd, ctypes.byref(pt))
    return (pt.x, pt.y)


def client_size() -> tuple[int, int]:
    w = find_window()
    rect = wintypes.RECT()
    user32.GetClientRect(w._hWnd, ctypes.byref(rect))
    return (rect.right, rect.bottom)


def move_resize(x: int, y: int, width: int, height: int) -> tuple[int, int, int, int]:
    w = find_window()
    hwnd = w._hWnd
    user32 = ctypes.windll.user32
    ok = user32.SetWindowPos(
        hwnd,
        0,
        x,
        y,
        width,
        height,
        SWP_NOZORDER | SWP_SHOWWINDOW,
    )
    if not ok:
        raise ctypes.WinError()
    time.sleep(0.5)
    return (x, y, width, height)


def screenshot(path: str, window_only: bool = False) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if window_only:
        left, top, right, bottom = window_rect()
        img = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
    else:
        img = ImageGrab.grab(all_screens=True)
    img.save(out)
    return str(out)


def click_client(x: int, y: int, shift: bool = False, double: bool = False) -> None:
    ox, oy = client_origin()
    click(ox + x, oy + y, shift=shift, double=double)


def click(x: int, y: int, shift: bool = False, double: bool = False) -> None:
    if shift:
        pyautogui.keyDown("shift")
    try:
        pyautogui.click(x, y, clicks=2 if double else 1, interval=0.15)
    finally:
        if shift:
            pyautogui.keyUp("shift")


def move_mouse(x: int, y: int) -> None:
    pyautogui.moveTo(x, y)


def key(keys: str) -> None:
    pyautogui.press(keys.split("+"))


def type_text(text: str) -> None:
    pyautogui.write(text, interval=0.02)


def hotkey(keys: str) -> None:
    pyautogui.hotkey(*keys.split("+"))


def focus_window() -> None:
    w = find_window()
    hwnd = w._hWnd
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    # SetForegroundWindow is often refused by Windows' foreground lock;
    # SwitchToThisWindow still works for a process we already own.
    user32.SwitchToThisWindow(hwnd, True)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("move")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("width", type=int)
    p.add_argument("height", type=int)

    p = sub.add_parser("shot")
    p.add_argument("path")
    p.add_argument("--window", action="store_true")

    p = sub.add_parser("info")

    p = sub.add_parser("focus")

    p = sub.add_parser("click")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("--shift", action="store_true")
    p.add_argument("--double", action="store_true")

    p = sub.add_parser("click-client")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("--shift", action="store_true")
    p.add_argument("--double", action="store_true")

    p = sub.add_parser("move-mouse")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)

    p = sub.add_parser("key")
    p.add_argument("keys")

    p = sub.add_parser("type")
    p.add_argument("text")

    p = sub.add_parser("hotkey")
    p.add_argument("keys")

    args = parser.parse_args()
    if args.cmd == "move":
        print(move_resize(args.x, args.y, args.width, args.height))
    elif args.cmd == "shot":
        print(screenshot(args.path, window_only=args.window))
    elif args.cmd == "info":
        print("window", window_rect())
        print("client origin", client_origin())
        print("client size", client_size())
    elif args.cmd == "focus":
        focus_window()
        print("focused")
    elif args.cmd == "click":
        click(args.x, args.y, shift=args.shift, double=args.double)
        print("clicked")
    elif args.cmd == "click-client":
        click_client(args.x, args.y, shift=args.shift, double=args.double)
        print("clicked-client")
    elif args.cmd == "move-mouse":
        move_mouse(args.x, args.y)
        print("moved")
    elif args.cmd == "key":
        key(args.keys)
        print("key")
    elif args.cmd == "type":
        type_text(args.text)
        print("typed")
    elif args.cmd == "hotkey":
        hotkey(args.keys)
        print("hotkey")


if __name__ == "__main__":
    main()
