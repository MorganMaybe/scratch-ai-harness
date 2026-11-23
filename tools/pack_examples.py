"""Shared helpers for the dialect context-pack examples and their JSON twins.

Every change-set example in ``context/games.md``, ``context/clones.md`` and
``context/scrolling.md`` is written in the Scratch-Python dialect; the JSON
block below each example is generated from it by
``tools/render_pack_json.py``.  This module owns the parts both the generator
and the validator need:

* the per-pack SETUP changes the examples assume (sprites, global/local
  variables and lists, in creation order);
* extraction of the python fences and the generated JSON twins;
* :func:`setup_context`, which applies the SETUP through the normal
  validate/compile simulation path so a fence can be transpiled exactly like a
  model reply.

Stdlib only: the tooling is imported by ``bridge/tests`` through
``importlib`` just like ``tools/ladder.py``.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge" / "src"))

from harness.block_ir import Change, ChangeSet  # noqa: E402
from harness.changeset import compile_changeset  # noqa: E402
from harness.context import ProjectContext, SpriteContext  # noqa: E402
from harness.validator import validate_changeset  # noqa: E402

#: Comment line that separates a hand-written python example from its twin.
TWIN_MARKER = (
    "<!-- generated from the python example above by "
    "tools/render_pack_json.py; edit the python, not this -->"
)

PYTHON_FENCE_RE = re.compile(r"```python\n(.*?)```", re.S)
JSON_FENCE_RE = re.compile(r"```json\n(.*?)```", re.S)
TWIN_RE = re.compile(
    r"\n" + re.escape(TWIN_MARKER) + r"\n```json\n.*?```", re.S
)


@dataclass(frozen=True)
class PackSpec:
    """One context pack with change-set examples."""

    name: str
    #: Changes the examples assume but do not create, top-down.
    setup: tuple[dict[str, Any], ...] = ()
    #: Sprite names other examples create, added as symbols when transpiling a
    #: fence out of order (the validator still sees only ``setup`` + examples).
    ambient_sprites: tuple[str, ...] = ()


#: Only packs with change-set examples are listed; pen-3d has none.
PACKS: dict[str, PackSpec] = {
    "games": PackSpec(
        name="games",
        setup=(
            {"action": "create_variable", "name": "vy", "scope": "global", "initial": 0},
            {"action": "create_variable", "name": "score", "scope": "global", "initial": 0},
            {"action": "create_variable", "name": "game_over", "scope": "global", "initial": 0},
            {"action": "create_variable", "name": "scored", "scope": "global", "initial": 0},
            {
                "action": "create_sprite",
                "name": "Cat",
                "costumes": [{"library": "Animals/dove1-a.png"}],
            },
            {
                "action": "create_sprite",
                "name": "Ground",
                "costumes": [{"library": "Scenery/rock.png"}],
                "x": 0,
                "y": -150,
                "size": 100,
            },
            {
                "action": "create_sprite",
                "name": "Platform1",
                "costumes": [{"library": "Scenery/rock.png"}],
                "x": -80,
                "y": -30,
                "size": 120,
            },
            {
                "action": "create_sprite",
                "name": "Platform2",
                "costumes": [{"library": "Scenery/rock.png"}],
                "x": 90,
                "y": 40,
                "size": 120,
            },
            {
                "action": "create_sprite",
                "name": "Bird",
                "costumes": [
                    {"library": "Animals/dove1-a.png"},
                    {"library": "Animals/dove1-b.png"},
                ],
                "x": -120,
                "y": 0,
            },
        ),
        ambient_sprites=("Pipe",),
    ),
    "clones": PackSpec(
        name="clones",
        setup=(
            {"action": "create_variable", "name": "spawn_index", "scope": "global", "initial": 0},
            {
                "action": "create_sprite",
                "name": "Bullet",
                "costumes": [{"library": "Geometry/line.png"}],
            },
            {
                "action": "create_sprite",
                "name": "Spark",
                "costumes": [{"library": "Animals/bat1-a.png"}],
            },
            {
                "action": "create_sprite",
                "name": "Tile",
                "costumes": [{"library": "Geometry/line.png"}],
            },
            {
                "action": "create_variable",
                "name": "life",
                "scope": "sprite",
                "target": "Spark",
                "initial": 30,
            },
            {
                "action": "create_variable",
                "name": "tile_index",
                "scope": "sprite",
                "target": "Tile",
                "initial": 0,
            },
        ),
    ),
    "scrolling": PackSpec(
        name="scrolling",
        setup=(
            {"action": "create_variable", "name": "cam_x", "scope": "global", "initial": 0},
            {"action": "create_variable", "name": "player_x", "scope": "global", "initial": 0},
            {"action": "create_variable", "name": "spawn_index", "scope": "global", "initial": 0},
            {"action": "create_list", "name": "map", "scope": "global", "items": [1, 0, 1, 1, 0]},
            {
                "action": "create_sprite",
                "name": "Player",
                "costumes": [{"library": "Animals/bat1-a.png"}],
            },
            {
                "action": "create_sprite",
                "name": "Tile",
                "costumes": [{"library": "Geometry/line.png"}],
            },
            {
                "action": "create_variable",
                "name": "tile_x",
                "scope": "sprite",
                "target": "Tile",
                "initial": 0,
            },
        ),
    ),
}


def pack_spec(name: str) -> PackSpec:
    """Look up one pack spec, rejecting packs without change-set examples."""
    text = name.strip().lower()
    if text not in PACKS:
        raise KeyError(f"no change-set examples for pack {name!r}")
    return PACKS[text]


def pack_path(name: str) -> Path:
    """Filesystem path of a pack markdown file."""
    return ROOT / "context" / f"{pack_spec(name).name}.md"


def read_pack(name: str) -> str:
    """Read a pack with its newlines untouched."""
    return pack_path(name).read_text(encoding="utf-8")


def python_fences(text: str) -> list[str]:
    """Every ```python fence body in a pack, in document order."""
    return PYTHON_FENCE_RE.findall(text)


def json_fences(text: str) -> list[str]:
    """Every ```json fence body in a pack, in document order."""
    return JSON_FENCE_RE.findall(text)


def strip_twins(text: str) -> str:
    """Remove every marker-comment + JSON twin pair, leaving the python."""
    return TWIN_RE.sub("", text)


def render_example_json(python_source: str, pack_name: str) -> list[dict[str, Any]]:
    """Transpile one python fence into its JSON change objects.

    One change stays one object; a fence that (like the multi-script clone
    examples) yields several changes becomes an array.
    """
    from harness.dsl import transpile

    changeset = transpile(python_source, setup_context(pack_name))
    return list(changeset.to_dict()["changes"])


@lru_cache(maxsize=1)
def _context_after_apply() -> Callable[[ProjectContext, Any], ProjectContext]:
    """The ladder tool's applied-context simulation, imported by path.

    It is the one existing helper that turns a compiled change set into the
    project snapshot the image would send back, so the packs reuse it instead
    of inventing a second apply path.
    """
    path = ROOT / "tools" / "ladder.py"
    spec = importlib.util.spec_from_file_location("pack_examples_ladder", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # Dataclass introspection looks modules up by __name__ while executing.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module.context_after_apply


def setup_context(name: str) -> ProjectContext:
    """Apply a pack's SETUP to ``ProjectContext.demo()`` and return it.

    The SETUP is validated and compiled exactly like a model turn, then the
    compiled changes are replayed through the ladder's applied-context helper.
    Ambient sprites that the pack's own examples create are added as symbol
    placeholders so any fence can be transpiled on its own (they carry no
    scripts, costumes or variables).
    """
    spec = pack_spec(name)
    demo = ProjectContext.demo()
    changeset = ChangeSet(
        summary=f"{spec.name} pack setup",
        changes=[Change.from_dict(item) for item in spec.setup],
        notes="",
    )
    issues = validate_changeset(changeset, demo)
    if issues:
        raise ValueError(
            f"{spec.name} SETUP failed validation: " + "; ".join(issues)
        )
    compiled = compile_changeset(changeset, demo)
    applied = _context_after_apply()(
        demo, SimpleNamespace(compiled=compiled)
    )
    for sprite_name in spec.ambient_sprites:
        applied.sprites.setdefault(sprite_name, SpriteContext(name=sprite_name))
    return applied
