"""Wait for the image control server to answer, then print its status."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_control  # noqa: E402

from harness.protocol import Sym  # noqa: E402

deadline = time.time() + 45
last = ""
while time.time() < deadline:
    try:
        print(ai_control.request([Sym("status")], timeout=3.0))
        raise SystemExit(0)
    except Exception as exc:  # noqa: BLE001
        last = str(exc)
        time.sleep(1.5)
print(f"control server did not answer: {last}")
raise SystemExit(1)
