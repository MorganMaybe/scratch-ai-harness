from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

#: Default appendix next to the repository root.
DEFAULT_CONTEXT_DOC = Path(__file__).resolve().parents[3] / "SCRATCH_AI_CONTEXT.md"
DEFAULT_CONTEXT_DIR = Path(__file__).resolve().parents[3] / "context"

_PACK_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


class ContextPackError(ValueError):
    """An unknown or invalid context-pack name."""


@lru_cache(maxsize=8)
def _read_cached(path: str, mtime_ns: int, size: int) -> str:
    return Path(path).read_text(encoding="utf-8")


def load_context_doc(path: str | Path | None = None) -> str:
    """Load the model context appendix, or "" when it does not exist.

    The cache key includes mtime and size, so editing the markdown is picked up
    by the next request without restarting the bridge.
    """
    target = Path(path) if path is not None else DEFAULT_CONTEXT_DOC
    try:
        stat = target.stat()
    except OSError:
        return ""
    try:
        return _read_cached(str(target), stat.st_mtime_ns, stat.st_size).strip()
    except OSError:
        return ""


def _pack_path(name: str) -> Path:
    text = name.strip().lower()
    if not _PACK_NAME_RE.match(text):
        raise ContextPackError(f"invalid context pack name {name!r}")
    return DEFAULT_CONTEXT_DIR / f"{text}.md"


def _summary(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            note = stripped.lstrip(">").strip()
            if note.lower().startswith("use when:"):
                note = note[len("use when:") :].strip()
            return note[:180]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:180]
    return ""


def load_context_pack(name: str) -> str:
    """Load one optional context pack by slug (for example ``clones``)."""
    target = _pack_path(name)
    try:
        stat = target.stat()
    except OSError:
        raise ContextPackError(f"unknown context pack {name!r}") from None
    try:
        return _read_cached(str(target), stat.st_mtime_ns, stat.st_size).strip()
    except OSError:
        raise ContextPackError(f"cannot read context pack {name!r}") from None


def available_context_packs() -> dict[str, str]:
    """Map pack slug -> one-line description, skipping README files."""
    found: dict[str, str] = {}
    try:
        paths = sorted(DEFAULT_CONTEXT_DIR.glob("*.md"))
    except OSError:
        return found
    for path in paths:
        name = path.stem.lower()
        if name == "readme" or not _PACK_NAME_RE.match(name):
            continue
        try:
            found[name] = _summary(load_context_pack(name))
        except ContextPackError:
            continue
    return found


def load_context_packs(names: list[str] | tuple[str, ...]) -> str:
    """Join the requested packs into one prompt section, preserving order."""
    if not names:
        return ""
    parts: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = str(name).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        text = load_context_pack(key)
        parts.append(f"# Loaded context pack: {key}\n\n{text}")
    return "\n\n".join(parts)


def reset_context_doc_cache() -> None:
    """Test helper."""
    _read_cached.cache_clear()


# Backwards-friendly alias for tests and tools.
reset_context_pack_cache = reset_context_doc_cache

