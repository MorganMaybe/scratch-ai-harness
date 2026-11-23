"""Known-good media paths mined from successful live turns.

``tools/mine_media_usage.py`` writes ``known_media.json`` next to this module
from audit bundles whose turn actually applied. The data serves two purposes:
a compact known-good tier in the system prompt, and known-good-first ranking of
``MediaLibrary.resolve``'s near-match suggestions.

Like ``media_groups.json``, the file is data rather than code: every field is
optional and malformed entries are dropped instead of trusted, so a stale or
partial file can never break prompting or error messages. A missing file means
"no known-good data yet" and every consumer degrades to its previous behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: Mined data, next to the other harness modules.
KNOWN_MEDIA_PATH = Path(__file__).resolve().with_name("known_media.json")

SCHEMA = 1

KINDS = ("costume", "backdrop")

#: One entry is ``{"library", "kind", "uses"}``. Cache the parse keyed by the
#: file's identity so a regenerated file is picked up without a restart.
_CACHE_KEY: tuple[str, int, int] | None = None
_CACHE_ENTRIES: tuple[dict[str, Any], ...] = ()


def _clean_path(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip().replace("\\", "/").strip("/")
    if not text or ".." in text.split("/"):
        return ""
    return text


def _clean_entry(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    library = _clean_path(entry.get("library"))
    kind = entry.get("kind")
    uses = entry.get("uses")
    if not library or kind not in KINDS:
        return None
    if isinstance(uses, bool) or not isinstance(uses, int) or uses < 1:
        return None
    return {"library": library, "kind": kind, "uses": uses}


def _read(path: Path) -> tuple[dict[str, Any], ...]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return ()
    if not isinstance(data, dict):
        return ()
    schema = data.get("schema")
    if schema is not None and (
        isinstance(schema, bool) or not isinstance(schema, int) or schema != SCHEMA
    ):
        return ()
    raw = data.get("paths")
    if not isinstance(raw, list):
        return ()
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        clean = _clean_entry(item)
        if clean is None:
            continue
        key = clean["library"].casefold()
        if key in seen:
            continue
        seen.add(key)
        entries.append(clean)
    entries.sort(key=lambda entry: (-entry["uses"], entry["library"].casefold()))
    return tuple(entries)


def load_known_media(path: Path | None = None) -> list[dict[str, Any]]:
    """Load the mined paths, or an empty list when unusable.

    Missing file, unreadable file, invalid JSON, an unexpected schema, or a
    wrong top-level shape all mean "no data"; individual malformed entries are
    dropped. This never raises.
    """
    global _CACHE_KEY, _CACHE_ENTRIES
    target = Path(path) if path is not None else KNOWN_MEDIA_PATH
    try:
        stat = target.stat()
    except OSError:
        return []
    key = (str(target), stat.st_mtime_ns, stat.st_size)
    if key != _CACHE_KEY:
        _CACHE_KEY = key
        _CACHE_ENTRIES = _read(target)
    return [dict(entry) for entry in _CACHE_ENTRIES]


def known_media_paths() -> frozenset[str]:
    """Casefolded library paths that succeeded in live use."""
    return frozenset(entry["library"].casefold() for entry in load_known_media())


def ranked_media(count: int = 20) -> list[tuple[str, str, int]]:
    """The top ``count`` known-good ``(library, kind, uses)`` entries."""
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        return []
    return [
        (entry["library"], entry["kind"], entry["uses"])
        for entry in load_known_media()[:count]
    ]
