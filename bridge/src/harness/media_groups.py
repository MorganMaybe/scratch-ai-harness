"""Curated media grouping for the system prompt.

``MediaLibrary.prompt_index`` groups the whole library by its original folder
layout, which is far too large for one system prompt (the Scratch 2.0 import
alone overflows the budget). A separate classification pass can write
``media_groups.json`` next to this module; this module renders that
classification as a compact index and falls back to the raw folder index when
the file is missing or unusable.

The JSON shape is deliberately forgiving: every key is optional and unknown
paths are dropped rather than trusted, so a stale or partial classification
can never put a nonexistent path into the prompt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .media import BACKDROP, COSTUME, MediaAsset, MediaLibrary

#: Default classification file, next to the other harness modules.
DEFAULT_GROUPS_PATH = Path(__file__).resolve().with_name("media_groups.json")

#: Curated groups lead in this order; anything else follows alphabetically.
GROUP_PRIORITY: tuple[str, ...] = (
    "players",
    "enemies",
    "animals",
    "people",
    "geometry",
    "game-items",
    "food",
    "instruments",
    "transport",
    "sports",
    "clothing",
    "ui",
    "background-elements",
    "letters",
    "numbers",
)

HEADER = (
    "Media library: the paths below are exact library values; use them directly "
    "in library fields (a bare file name also works). Assets not listed may "
    "still exist in the unclassified tail."
)
PRESET_HEADER = (
    'Preset groups for create_sprite (pass the name as "preset"):'
)
BACKDROP_HEADER = "Backdrop groups (set_backdrop or switch_backdrop):"

TAIL_MARKER = "[unclassified media truncated {n} chars]"
GROUP_MARKER = "[group {name} truncated {n} chars]"
CORE_MARKER = "[group index truncated {n} chars]"

_PRESET_WIDTH = 90
_ITEM_WIDTH = 100


def load_media_groups(path: Path | None = None) -> dict[str, Any] | None:
    """Load the classification file, or ``None`` when it is unusable.

    Missing file, unreadable file, invalid JSON, an unexpected version, or a
    wrong top-level shape all mean "no classification yet"; callers then use
    the raw library index. This never raises.
    """
    target = Path(path) if path is not None else DEFAULT_GROUPS_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    version = data.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        return None
    for key in ("groups", "preset_groups", "backdrop_groups"):
        value = data.get(key)
        if value is not None and not isinstance(value, dict):
            return None
    return data


def grouped_prompt_index(
    library: MediaLibrary,
    groups: dict,
    max_chars: int = 16000,
) -> str | None:
    """Render the curated index, or ``None`` when there is nothing to render.

    Curated sections are kept intact whenever they fit; the unclassified tail
    is trimmed first, then the largest groups' item tails. Every emitted path
    is validated against the library.
    """
    if not isinstance(groups, dict) or not groups:
        return None
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars <= 0:
        return None

    costume_map = {
        asset.library.casefold(): asset for asset in library.assets(COSTUME)
    }
    backdrop_map = {
        asset.library.casefold(): asset for asset in library.assets(BACKDROP)
    }
    costume_sections = _sections(groups.get("groups"), costume_map)
    backdrop_sections = _sections(groups.get("backdrop_groups"), backdrop_map)
    preset_lines = _preset_lines(groups.get("preset_groups"))
    if not costume_sections and not backdrop_sections and not preset_lines:
        return None

    excluded = _item_keys(groups.get("groups")) | _item_keys(
        groups.get("backdrop_groups")
    )
    prefixes = _family_prefixes(groups.get("groups")) | _family_prefixes(
        groups.get("backdrop_groups")
    )
    tail = _tail_lines(library, excluded, prefixes)

    core = _render_core(costume_sections, preset_lines, backdrop_sections)
    if not tail:
        return _finish(_trim_core(costume_sections, preset_lines, backdrop_sections, max_chars))

    tail_text = "\n".join(tail)
    if len(core) + 1 + len(tail_text) <= max_chars:
        return _finish(core + "\n" + tail_text)

    # Curated sections fit: give the tail only what is left, trimmed on line
    # boundaries with the same marker style the raw index uses.
    if len(core) <= max_chars:
        marker_upper = TAIL_MARKER.format(n=len(tail_text))
        room = max_chars - len(core) - 1 - len(marker_upper) - 1
        kept: list[str] = []
        used = 0
        for line in tail:
            extra = len(line) + (1 if kept else 0)
            if room <= 0 or used + extra > room:
                break
            kept.append(line)
            used += extra
        kept_text = "\n".join(kept)
        marker = TAIL_MARKER.format(n=max(0, len(tail_text) - len(kept_text)))
        combined = core + "\n"
        if kept_text:
            combined += kept_text + "\n"
        combined += marker
        if len(combined) <= max_chars:
            return _finish(combined)

    # Even the curated sections are too large: trim the biggest groups' item
    # tails and mark each cut. The tail is dropped entirely here.
    return _finish(
        _trim_core(costume_sections, preset_lines, backdrop_sections, max_chars)
    )


@dataclass
class _Section:
    name: str
    header: str
    items: list[str] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)
    dropped: int = 0

    def render(self) -> list[str]:
        lines = _wrap_items(self.items) if self.items else []
        lines.extend(self.extras)
        if self.dropped:
            lines.append("  " + GROUP_MARKER.format(name=self.name, n=self.dropped))
        return lines


def _text(value: Any) -> str:
    """One clean ASCII line: whitespace collapsed, non-ASCII replaced."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    text = " ".join(value.split())
    return text.encode("ascii", "replace").decode("ascii")


def _finish(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii").strip("\n")


def _order_key(name: str) -> tuple[int, int, str]:
    key = _text(name).casefold().replace("_", "-").replace(" ", "-")
    try:
        return (0, GROUP_PRIORITY.index(key), "")
    except ValueError:
        return (1, 0, key)


def _ordered(names: Iterable[Any]) -> list[str]:
    return sorted((name for name in names if isinstance(name, str)), key=_order_key)


def _sections(raw: Any, assets: dict[str, MediaAsset]) -> list[_Section]:
    if not isinstance(raw, dict):
        return []
    sections: list[_Section] = []
    for name in _ordered(raw):
        entry = raw[name]
        if not isinstance(entry, dict):
            continue
        description = _text(entry.get("description"))
        items: list[str] = []
        extras: list[str] = []

        raw_items = entry.get("items")
        if isinstance(raw_items, dict):
            for key, value in raw_items.items():
                if not isinstance(key, str):
                    continue
                asset = assets.get(key.strip().casefold())
                if asset is None:
                    continue
                item_description = _text(value)
                if item_description:
                    items.append(f"{asset.library} ({item_description})")
                else:
                    items.append(asset.library)

        families = entry.get("families")
        if isinstance(families, dict):
            for prefix in sorted(
                (key for key in families if isinstance(key, str)),
                key=str.casefold,
            ):
                family = families[prefix]
                if not isinstance(family, dict):
                    continue
                cleaned = prefix.strip().strip("/")
                if not cleaned or not _has_prefix(assets.values(), cleaned):
                    continue
                line = f"  {cleaned}/<glyph>"
                family_description = _text(family.get("description"))
                glyphs = _text(family.get("glyphs"))
                if family_description:
                    line += f" - {family_description}"
                if glyphs:
                    line += f"; glyphs {glyphs}"
                extras.append(line)

        if not items and not extras:
            continue
        header = f"{name} - {description}" if description else name
        sections.append(
            _Section(name=name, header=header, items=items, extras=extras)
        )
    return sections


def _has_prefix(assets: Iterable[MediaAsset], prefix: str) -> bool:
    lowered = prefix.casefold()
    for asset in assets:
        category = asset.category.casefold()
        if category == lowered or category.startswith(lowered + "/"):
            return True
    return False


def _preset_lines(raw: Any) -> list[str]:
    if not isinstance(raw, dict):
        return []
    blocks: list[tuple[str, list[str]]] = []
    for name in _ordered(raw):
        entry = raw[name]
        names = entry.get("names") if isinstance(entry, dict) else entry
        if not isinstance(names, list):
            continue
        cleaned = [_text(item) for item in names]
        cleaned = [item for item in cleaned if item]
        if cleaned:
            blocks.append((_text(name), cleaned))
    if not blocks:
        return []
    lines = [PRESET_HEADER]
    for name, names in blocks:
        lines.extend(_wrap_preset(name, names))
    return lines


def _wrap_preset(name: str, names: list[str], width: int = _PRESET_WIDTH) -> list[str]:
    prefix = f"  {name}: "
    lines: list[str] = []
    current = prefix
    for item in names:
        separator = "" if current == prefix else ", "
        if current != prefix and len(current) + len(separator) + len(item) > width:
            lines.append(current + ",")
            current = "    " + item
        else:
            current += separator + item
    lines.append(current)
    return lines


def _wrap_items(items: list[str], width: int = _ITEM_WIDTH) -> list[str]:
    """One indented comma list, wrapped on ``", "`` boundaries.

    Lines that continue carry a trailing comma; the last line does not. A
    single entry longer than ``width`` is never split, so a path is always
    emitted whole.
    """
    lines: list[str] = []
    current = "  "
    for item in items:
        if current == "  ":
            current += item
        elif len(current) + 2 + len(item) > width:
            lines.append(current + ",")
            current = "  " + item
        else:
            current += ", " + item
    lines.append(current)
    return lines


def _item_keys(raw: Any) -> set[str]:
    keys: set[str] = set()
    if not isinstance(raw, dict):
        return keys
    for entry in raw.values():
        if not isinstance(entry, dict):
            continue
        items = entry.get("items")
        if not isinstance(items, dict):
            continue
        for key in items:
            if isinstance(key, str) and key.strip():
                keys.add(key.strip().casefold())
    return keys


def _family_prefixes(raw: Any) -> set[str]:
    prefixes: set[str] = set()
    if not isinstance(raw, dict):
        return prefixes
    for entry in raw.values():
        if not isinstance(entry, dict):
            continue
        families = entry.get("families")
        if not isinstance(families, dict):
            continue
        for key in families:
            if isinstance(key, str) and key.strip().strip("/"):
                prefixes.add(key.strip().strip("/").casefold())
    return prefixes


def _tail_lines(
    library: MediaLibrary,
    excluded: set[str],
    prefixes: set[str],
) -> list[str]:
    lines: list[str] = []
    for kind, title in (
        (COSTUME, "Unclassified costumes:"),
        (BACKDROP, "Unclassified backdrops:"),
    ):
        categories: dict[str, list[str]] = {}
        for asset in library.assets(kind):
            if asset.library.casefold() in excluded:
                continue
            category = asset.category.casefold()
            if any(
                category == prefix or category.startswith(prefix + "/")
                for prefix in prefixes
            ):
                continue
            categories.setdefault(asset.category, []).append(asset.display)
        if not categories:
            continue
        lines.append(title)
        for category in sorted(categories, key=str.casefold):
            entries = ", ".join(sorted(categories[category], key=str.casefold))
            lines.append(f"  {category or 'root'}: {entries}")
    return lines


def _render_core(
    costume_sections: list[_Section],
    preset_lines: list[str],
    backdrop_sections: list[_Section],
) -> str:
    lines = [HEADER]
    for section in costume_sections:
        lines.append("")
        lines.append(section.header)
        lines.extend(section.render())
    if preset_lines:
        lines.append("")
        lines.extend(preset_lines)
    if backdrop_sections:
        lines.append("")
        lines.append(BACKDROP_HEADER)
        for section in backdrop_sections:
            lines.append(section.header)
            lines.extend(section.render())
    return "\n".join(lines)


def _trim_core(
    costume_sections: list[_Section],
    preset_lines: list[str],
    backdrop_sections: list[_Section],
    max_chars: int,
) -> str:
    def render() -> str:
        return _render_core(costume_sections, preset_lines, backdrop_sections)

    text = render()
    while len(text) > max_chars:
        candidates = [
            section
            for section in costume_sections + backdrop_sections
            if section.items
        ]
        if not candidates:
            break
        # Biggest section first: it has the most to lose, and dropping from it
        # keeps the smaller curated groups intact longest.
        largest = max(
            candidates, key=lambda section: len(", ".join(section.items))
        )
        removed = largest.items.pop()
        largest.dropped += len(removed) + 2
        text = render()

    if len(text) > max_chars:
        text = _hard_cut(text, max_chars)
    return text


def _hard_cut(text: str, max_chars: int) -> str:
    marker = CORE_MARKER.format(n=len(text))
    if len(marker) >= max_chars:
        return marker[:max_chars]
    kept: list[str] = []
    used = 0
    room = max_chars - len(marker) - 1
    for line in text.splitlines():
        extra = len(line) + (1 if kept else 0)
        if used + extra > room:
            break
        kept.append(line)
        used += extra
    kept_text = "\n".join(kept)
    dropped = max(0, len(text) - len(kept_text))
    result = (kept_text + "\n") if kept_text else ""
    return result + CORE_MARKER.format(n=dropped)
