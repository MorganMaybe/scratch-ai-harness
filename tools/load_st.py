"""Load one or more image/*.st files through the control server with short timeouts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_control  # noqa: E402

from harness.protocol import Sym  # noqa: E402

for name in sys.argv[1:]:
    try:
        print(f"{name} -> {ai_control.request([Sym('load'), name], timeout=30.0)}")
    except Exception as exc:  # noqa: BLE001
        print(f"{name} !! {exc}")
