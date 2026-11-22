from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from harness import media, media_groups
from harness.media import MediaLibrary
from harness.media_groups import (
    TAIL_MARKER,
    grouped_prompt_index,
    load_media_groups,
)
from harness.prompts import build_system_prompt

LIBRARY_FILES = (
    "Costumes/Animals/bat1-a.png",
    "Costumes/Animals/bat2-a.png",
    "Costumes/Letters/Digital/0.gif",
    "Costumes/Letters/Digital/a.gif",
    "Costumes/Geometry/line.png",
    "Costumes/UI/scoreboard.gif",
    "Backgrounds/Space/stars.gif",
    "Backgrounds/Nature/woods.png",
    "Backgrounds/Sports/field.png",
)

GROUPS = {
    "version": 1,
    "groups": {
        "geometry": {
            "description": "structural, non-character art",
            "items": {
                "Geometry/line.png": "flat red bar",
                "Animals/missing.png": "not in the library",
            },
        },
        "animals": {
            "description": "creatures",
            "items": {
                "Animals/bat1-a.png": "startled bat",
                "Animals/bat2-a.png": "",
            },
        },
        "letters": {
            "description": "lettering",
            "items": {},
            "families": {
                "Letters/Digital": {
                    "description": "LCD-style digits",
                    "glyphs": "0-9 and a-z",
                    "example": "Letters/Digital/0.gif",
                }
            },
        },
    },
    "preset_groups": {
        "players": {
            "description": "ready-made characters",
            "names": ["Abby", "Pico", "Ruby", "Gobo", "Giga", "Nano", "Tera"],
        }
    },
    "backdrop_groups": {
        "space": {
            "description": "starfields and planets",
            "items": {"Space/stars.gif": "starfield"},
        }
    },
}


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "Media"
    for relative in LIBRARY_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return MediaLibrary(root)


def _write_groups(path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _rendered(library, max_chars=16000):
    text = grouped_prompt_index(library, GROUPS, max_chars=max_chars)
    assert text is not None
    return text


def _core_prefix(text: str) -> str:
    return text.split("Unclassified costumes:", 1)[0].rstrip()


def test_load_media_groups_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(media_groups, "DEFAULT_GROUPS_PATH", tmp_path / "absent.json")
    assert load_media_groups() is None


def test_load_media_groups_invalid_json_returns_none(tmp_path, monkeypatch):
    path = tmp_path / "media_groups.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(media_groups, "DEFAULT_GROUPS_PATH", path)
    assert load_media_groups() is None


def test_load_media_groups_wrong_version_returns_none(tmp_path, monkeypatch):
    path = tmp_path / "media_groups.json"
    _write_groups(path, {"version": 2, "groups": {}})
    monkeypatch.setattr(media_groups, "DEFAULT_GROUPS_PATH", path)
    assert load_media_groups() is None


def test_load_media_groups_wrong_shape_returns_none(tmp_path, monkeypatch):
    path = tmp_path / "media_groups.json"
    _write_groups(path, {"version": 1, "groups": ["not", "a", "dict"]})
    monkeypatch.setattr(media_groups, "DEFAULT_GROUPS_PATH", path)
    assert load_media_groups() is None


def test_load_media_groups_accepts_valid_file(tmp_path, monkeypatch):
    path = tmp_path / "media_groups.json"
    _write_groups(path, GROUPS)
    monkeypatch.setattr(media_groups, "DEFAULT_GROUPS_PATH", path)
    loaded = load_media_groups()
    assert loaded is not None
    assert loaded["groups"]["geometry"]["items"]["Geometry/line.png"] == "flat red bar"


def test_grouped_index_renders_headers_items_families_presets_and_backdrops(library):
    text = _rendered(library)

    assert "exact library values" in text
    assert "animals - creatures" in text
    assert "geometry - structural, non-character art" in text
    # Priority order puts animals before geometry regardless of JSON order.
    assert text.index("animals - creatures") < text.index("geometry - structural")
    assert "  Animals/bat1-a.png (startled bat), Animals/bat2-a.png" in text
    # Empty descriptions omit the parentheses entirely.
    assert "bat2-a.png (" not in text
    assert (
        "  Letters/Digital/<glyph> - LCD-style digits; glyphs 0-9 and a-z" in text
    )
    assert "Preset groups for create_sprite" in text
    assert '"preset"' in text
    assert "  players: Abby, Pico, Ruby" in text
    assert "Backdrop groups" in text
    assert "space - starfields and planets" in text
    assert "  Space/stars.gif (starfield)" in text
    assert text.isascii()


def test_grouped_index_renders_items_as_comma_lists(library):
    text = _rendered(library)
    # One indented comma list per group, with the description in parentheses.
    assert "  Geometry/line.png (flat red bar)" in text
    assert "  Geometry/line.png - flat red bar" not in text
    assert "  Animals/bat1-a.png (startled bat), Animals/bat2-a.png" in text


def test_grouped_index_wraps_item_lists_at_about_100_chars(tmp_path):
    root = tmp_path / "Media"
    names = [f"creature-number-{index:02d}.png" for index in range(20)]
    paths = [f"Animals/{name}" for name in names]
    for relative in paths:
        path = root / "Costumes" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    wide = MediaLibrary(root)
    groups = {
        "version": 1,
        "groups": {
            "animals": {
                "description": "creatures",
                "items": {path: "" for path in paths},
            }
        },
    }
    text = grouped_prompt_index(wide, groups, max_chars=999999)
    assert text is not None
    item_lines = [line for line in text.splitlines() if "creature-number" in line]
    assert len(item_lines) > 1
    for line in item_lines[:-1]:
        assert line.startswith("  ")
        assert line.endswith(",")
        assert len(line) <= 100
    for path in paths:
        assert path in text


def test_grouped_index_drops_paths_that_are_not_in_the_library(library):
    text = _rendered(library)
    assert "Animals/missing.png" not in text
    assert "Geometry/line.png (flat red bar)" in text


def test_grouped_index_includes_unclassified_tail(library):
    text = _rendered(library)
    assert "Unclassified costumes:" in text
    assert "  UI: scoreboard.gif" in text
    assert "Unclassified backdrops:" in text
    assert "  Sports: field.png" in text
    # Classified assets and family glyphs never repeat in the tail.
    assert "Animals: bat1-a.png" not in text
    assert "Nature: woods.png" in text  # backdrop group only lists stars
    assert "0.gif" not in text
    assert "a.gif" not in text


def test_grouped_index_trims_the_tail_first(library):
    full = _rendered(library)
    core = _core_prefix(full)
    tail = "Unclassified costumes:" + full.split("Unclassified costumes:", 1)[1]
    limit = len(core) + 1 + len(TAIL_MARKER.format(n=len(tail))) + 1 + 20
    assert limit < len(full)

    trimmed = _rendered(library, max_chars=limit)
    assert len(trimmed) <= limit
    assert "[unclassified media truncated" in trimmed
    # Every curated group survives intact.
    assert "animals - creatures" in trimmed
    assert "  Animals/bat1-a.png (startled bat), Animals/bat2-a.png" in trimmed
    assert "  Letters/Digital/<glyph>" in trimmed
    assert "space - starfields and planets" in trimmed
    assert "[group " not in trimmed


def test_grouped_index_trims_group_items_last(library):
    full = _rendered(library)
    core = _core_prefix(full)
    limit = len(core) - 60
    assert limit > 0

    trimmed = _rendered(library, max_chars=limit)
    assert len(trimmed) <= limit
    assert "[group " in trimmed
    assert "truncated" in trimmed
    # The whole raw tail is gone before group items are cut.
    assert "Unclassified costumes:" not in trimmed


def test_group_index_trimming_drops_whole_entries(library):
    full = _rendered(library)
    core = _core_prefix(full)
    limit = len(core) - 100
    assert limit > 0

    trimmed = _rendered(library, max_chars=limit)
    assert "[group " in trimmed
    known = {
        "Animals/bat1-a.png (startled bat)",
        "Animals/bat2-a.png",
        "Geometry/line.png (flat red bar)",
        "Space/stars.gif (starfield)",
    }
    for line in trimmed.splitlines():
        stripped = line.strip()
        if not stripped.startswith(("Animals/", "Geometry/", "Space/")):
            continue
        for entry in stripped.rstrip(",").split(", "):
            assert entry in known, entry


def _merge_tool():
    path = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "media_groups_work"
        / "merge.py"
    )
    spec = importlib.util.spec_from_file_location("media_groups_merge", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stem_echo_prunes_only_redundant_descriptions():
    merge = _merge_tool()
    assert merge.stem_echo("arrow1-a", "arrow shape")
    assert merge.stem_echo("boy1-walking", "walking animation")
    assert not merge.stem_echo(
        "line", "flat red bar; vertical pipe at direction 0"
    )
    assert merge.stem_echo("line", "")


def test_curated_groups_prune_stem_echo_descriptions():
    groups = load_media_groups()
    assert groups is not None
    geometry = groups["groups"]["geometry"]["items"]
    assert geometry["Geometry/arrow1-a.png"] == ""
    assert "vertical pipe" in geometry["Geometry/line.png"]


def test_grouped_index_returns_none_for_empty_groups(library):
    assert grouped_prompt_index(library, {}, max_chars=16000) is None
    assert grouped_prompt_index(library, {"version": 1}, max_chars=16000) is None
    assert grouped_prompt_index(library, GROUPS, max_chars=0) is None


def test_grouped_index_output_is_ascii(library):
    groups = {
        "version": 1,
        "groups": {
            "food": {
                "description": "caf\u00e9 snacks \u2014 tasty",
                "items": {"Geometry/line.png": "cr\u00e8me br\u00fbl\u00e9e"},
            }
        },
    }
    text = grouped_prompt_index(library, groups, max_chars=16000)
    assert text is not None
    assert text.isascii()
    assert "food - caf? snacks" in text


def test_build_system_prompt_uses_grouped_index(tmp_path, monkeypatch, library):
    path = tmp_path / "media_groups.json"
    _write_groups(path, GROUPS)
    monkeypatch.setattr(media_groups, "DEFAULT_GROUPS_PATH", path)
    monkeypatch.setattr(media, "default_library", lambda: library)

    prompt = build_system_prompt(target="Sprite1")
    assert "exact library values" in prompt
    assert "  Geometry/line.png (flat red bar)" in prompt
    assert "  players: Abby" in prompt
    assert "reference as 'category/name.ext'" not in prompt


def test_build_system_prompt_falls_back_to_raw_index(tmp_path, monkeypatch, library):
    monkeypatch.setattr(
        media_groups, "DEFAULT_GROUPS_PATH", tmp_path / "absent.json"
    )
    monkeypatch.setattr(media, "default_library", lambda: library)

    prompt = build_system_prompt(target="Sprite1")
    assert "reference as 'category/name.ext'" in prompt
    assert "Animals: bat1-a.png" in prompt
    assert "exact library values" not in prompt
