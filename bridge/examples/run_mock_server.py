from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from harness.server import BridgeServer, default_bridge


def main() -> None:
    server = BridgeServer(bridge=default_bridge(mock=True))
    print("mock bridge on 127.0.0.1:8765", flush=True)
    asyncio.run(server.serve_forever())


if __name__ == "__main__":
    main()
