"""Test environment helpers.

The media tests normally index the real ``scratch/base/Media`` tree. That tree
is intentionally not committed (it is part of the Scratch runtime), so on a
fresh clone / CI we generate a small deterministic library and point
``HARNESS_MEDIA_ROOT`` at it. A developer with the runtime installed keeps using
the real library.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, data: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@pytest.fixture(scope="session", autouse=True)
def _ensure_media_library(tmp_path_factory: pytest.TempPathFactory) -> None:
    if os.environ.get("HARNESS_MEDIA_ROOT"):
        return
    real = _REPO_ROOT / "scratch" / "base" / "Media"
    if real.is_dir():
        return

    root = tmp_path_factory.mktemp("media")
    costumes = root / "Costumes"
    backdrops = root / "Backgrounds"

    # Paths the suite asserts on.
    for relative in (
        "Animals/bat1-a.png",
        "Animals/bat1-b.png",
        "Animals/bat2-a.png",
        "Animals/bat2-b.png",
        "Animals/dove1-a.png",
        "Animals/dove1-b.png",
        "Scenery/rock.png",
        "Geometry/line.png",
        "Geometry/arrow1-a.png",
        "Geometry/arrow1-b.png",
        "Letters/Auto/0.gif",
    ):
        _write(costumes / relative)
    _write(backdrops / "Space/stars.gif")
    _write(backdrops / "Nature/grass1.png")
    for index in range(20):
        _write(backdrops / "Nature" / f"background-with-a-long-name-{index:02d}.png")
    for relative in (
        "Animals/dog-puppy-right.png",
        "Animals/dog-puppy-sit.png",
        "Animals/dog-puppy-side.png",
        "Animals/dog-puppy-back.png",
    ):
        _write(costumes / relative)
    _write(root / "Sounds" / "Scratch2" / "Sprites" / "dog-puppy" / "dog2.wav")

    # Enough names to exercise prompt-index trimming.
    for index in range(60):
        _write(costumes / "Animals" / f"creature-with-a-long-name-{index:03d}.png")

    manifest = {
        "source": "test fixture",
        "sprites": [
            {
                "name": "Dog Puppy",
                "costumes": [
                    "Animals/dog-puppy-right.png",
                    "Animals/dog-puppy-sit.png",
                    "Animals/dog-puppy-side.png",
                    "Animals/dog-puppy-back.png",
                ],
                "rotation_centers": [
                    [107.0, 103.0],
                    [87.0, 112.0],
                    [104.0, 114.0],
                    [234.0, 94.0],
                ],
                "direction": 90,
                "size": 100.0,
                "rotation_style": "normal",
                "sounds": ["Scratch2/Sprites/dog-puppy/dog2.wav"],
            }
        ],
    }
    _write(
        root / "Scratch2" / "sprites.json",
        json.dumps(manifest).encode("utf-8"),
    )
    os.environ["HARNESS_MEDIA_ROOT"] = str(root)


@pytest.fixture
def lazy_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run a test on the lazy-only context path (``eager_context = off``).

    The lazy protocol (``load_context``/``load_sprite``, the replace echo) is
    still the fallback when eager context does not fit or is switched off, so
    its tests pin it explicitly instead of depending on the default.
    """
    monkeypatch.setenv("HARNESS_EAGER_CONTEXT", "off")
