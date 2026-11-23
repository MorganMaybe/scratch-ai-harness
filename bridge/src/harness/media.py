from __future__ import annotations

import difflib
import json
import os
from dataclasses import dataclass
from pathlib import Path

#: Image files Scratch's own media library ships. ``.sprite`` bundles and
#: ``*.db`` index files are deliberately excluded from the MVP.
IMAGE_EXTENSIONS: tuple[str, ...] = (".png", ".gif", ".jpg", ".jpeg", ".bmp")

COSTUME = "costume"
BACKDROP = "backdrop"

KIND_TITLES = {
    COSTUME: "Costumes",
    BACKDROP: "Backdrops",
}

#: Scratch 2.0 stores rotation centers in half-pixel costumeditor units; its
#: bitmap costumes are rasterized at 2x. The image side applies this factor.
PRESET_CENTER_SCALE = 2

_ROTATION_STYLE_NAMES = {
    "normal": "all around",
    "leftRight": "left-right",
    "left-right": "left-right",
    "none": "don't rotate",
    "don't rotate": "don't rotate",
    "all around": "all around",
}



def default_media_root() -> Path:
    """``scratch/base/Media`` next to the bridge package.

    ``HARNESS_MEDIA_ROOT`` overrides it for tests and non-standard installs.
    """
    override = os.environ.get("HARNESS_MEDIA_ROOT")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[3] / "scratch" / "base" / "Media"


@dataclass(frozen=True)
class MediaAsset:
    kind: str
    category: str
    name: str
    ext: str
    path: Path

    @property
    def library(self) -> str:
        """Path relative to ``Media/`` as the change-set JSON expresses it."""
        if self.category:
            return f"{self.category}/{self.name}{self.ext}"
        return f"{self.name}{self.ext}"

    @property
    def display(self) -> str:
        return f"{self.name}{self.ext}"


@dataclass(frozen=True)
class PresetCostume:
    """One costume of a Scratch 2.0 sprite preset."""

    library: str
    name: str
    center_x: float = 0.0
    center_y: float = 0.0
    center_scale: float = 1.0

    @property
    def pixel_center(self) -> tuple[float, float]:
        return (self.center_x * self.center_scale, self.center_y * self.center_scale)


@dataclass(frozen=True)
class SpritePreset:
    """A named Scratch 2.0 sprite preset (costumes + initial properties)."""

    name: str
    costumes: tuple[PresetCostume, ...]
    direction: float = 90.0
    size: float = 100.0
    rotation_style: str = "all around"
    sounds: tuple[str, ...] = ()


def _dedupe(paths: list[str]) -> list[str]:
    """Drop repeats while keeping the first spelling and original order."""
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        key = path.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _unique_names(paths: list[str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for path in paths:
        base = Path(path).stem
        name = base
        suffix = 2
        while name.casefold() in seen:
            name = f"{base}-{suffix}"
            suffix += 1
        seen.add(name.casefold())
        names.append(name)
    return names


def _known_first(suggestions: list[str]) -> list[str]:
    """Stable-reorder near matches so known-good library paths lead.

    The mined set is casefolded library paths; an entry that is not in it keeps
    its original relative position, and the message format is unchanged.
    """
    if len(suggestions) < 2:
        return suggestions
    from .known_media import known_media_paths

    known = known_media_paths()
    if not known:
        return suggestions
    good = [item for item in suggestions if item.casefold() in known]
    rest = [item for item in suggestions if item.casefold() not in known]
    return good + rest


class MediaError(ValueError):
    """An unresolvable or ambiguous media reference."""

    def __init__(self, message: str, suggestions: list[str] | None = None):
        self.suggestions = list(suggestions or [])
        if self.suggestions:
            message = f"{message}; near matches: {', '.join(self.suggestions)}"
        super().__init__(message)


class MediaLibrary:
    """Read-only index of Scratch's bundled costumes and backdrops.

    The index is built once per instance. Missing media directories degrade to
    an empty library rather than raising at import time: the bridge can still
    answer script-only requests on a machine without the Scratch runtime.
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else default_media_root()
        self._assets: list[MediaAsset] | None = None
        self._presets: list[SpritePreset] | None = None

    def assets(self, kind: str | None = None) -> list[MediaAsset]:
        if self._assets is None:
            self._assets = self._scan()
        if kind is None:
            return list(self._assets)
        return [asset for asset in self._assets if asset.kind == kind]

    def _scan(self) -> list[MediaAsset]:
        found: list[MediaAsset] = []
        for kind, folder in ((COSTUME, "Costumes"), (BACKDROP, "Backgrounds")):
            base = self.root / folder
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                category = path.parent.relative_to(base).as_posix()
                if category == ".":
                    category = ""
                found.append(
                    MediaAsset(
                        kind=kind,
                        category=category,
                        name=path.stem,
                        ext=path.suffix.lower(),
                        path=path,
                    )
                )
        return found

    def names(self, kind: str) -> list[str]:
        return sorted({asset.name for asset in self.assets(kind)}, key=str.casefold)

    # -- Scratch 2.0 sprite presets ------------------------------------

    def sprites(self) -> list[SpritePreset]:
        """Scratch 2.0 sprite presets, or an empty list when not imported."""
        if self._presets is None:
            self._presets = self._load_presets()
        return list(self._presets)

    def _load_presets(self) -> list[SpritePreset]:
        manifest = self.root / "Scratch2" / "sprites.json"
        if not manifest.is_file():
            return []
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        raw = data.get("sprites") if isinstance(data, dict) else None
        if not isinstance(raw, list):
            return []
        presets: list[SpritePreset] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            paths = [
                str(item).strip().replace("\\", "/").strip("/")
                for item in entry.get("costumes", [])
                if isinstance(item, str) and item.strip()
            ]
            if not name or not paths:
                continue
            centers: list[tuple[float, float]] = []
            for value in entry.get("rotation_centers", []):
                if (
                    isinstance(value, (list, tuple))
                    and len(value) >= 2
                    and all(isinstance(n, (int, float)) for n in value[:2])
                ):
                    centers.append((float(value[0]), float(value[1])))
                else:
                    centers.append((0.0, 0.0))
            while len(centers) < len(paths):
                centers.append((0.0, 0.0))
            scales: list[float] = []
            raw_scales = entry.get("rotation_center_scales", [])
            if not isinstance(raw_scales, list):
                raw_scales = []
            for index in range(len(paths)):
                value = raw_scales[index] if index < len(raw_scales) else 1.0
                scales.append(float(value) if isinstance(value, (int, float)) else 1.0)
            names = _unique_names(paths)
            rotation = _ROTATION_STYLE_NAMES.get(
                str(entry.get("rotation_style", "normal")), "all around"
            )
            presets.append(
                SpritePreset(
                    name=name,
                    costumes=tuple(
                        PresetCostume(
                            library=path,
                            name=names[index],
                            center_x=centers[index][0],
                            center_y=centers[index][1],
                            center_scale=scales[index],
                        )
                        for index, path in enumerate(paths)
                    ),
                    direction=float(entry.get("direction", 90) or 90),
                    size=float(entry.get("size", 100) or 100),
                    rotation_style=rotation,
                    sounds=tuple(
                        str(item).strip()
                        for item in entry.get("sounds", [])
                        if isinstance(item, str) and item.strip()
                    ),
                )
            )
        presets.sort(key=lambda preset: preset.name.casefold())
        return presets

    def resolve_sprite(self, query: str) -> SpritePreset:
        """Resolve a preset by case-insensitive name, with near matches."""
        if not isinstance(query, str) or not query.strip():
            raise MediaError("sprite preset name is empty")
        text = query.strip()
        presets = self.sprites()
        for preset in presets:
            if preset.name.casefold() == text.casefold():
                return preset
        pool = [preset.name for preset in presets]
        suggestions = difflib.get_close_matches(text, pool, n=5, cutoff=0.55)
        raise MediaError(f"unknown sprite preset {query!r}", suggestions)

    def preset_index(self, max_chars: int = 4200) -> str:
        """Compact list of preset names for the system prompt."""
        presets = self.sprites()
        if not presets:
            return ""
        header = (
            "Sprite presets (create_sprite may use \"preset\": \"Name\" "
            "instead of costumes): "
        )
        names = ", ".join(preset.name for preset in presets)
        text = header + names
        if len(text) <= max_chars:
            return text
        marker = f" [preset list truncated {len(text) - max_chars} chars]"
        room = max(0, max_chars - len(header) - len(marker))
        kept = names[:room].rsplit(", ", 1)[0]
        return header + kept + marker

    def _exact_stem_matches(self, kind: str, stem: str) -> list[str]:
        """Libraries of ``kind`` whose file stem casefolds to ``stem``.

        A missing or wrong category prefix (``Sprites/line.png`` for the real
        ``Geometry/line.png``) is a common model mistake, and difflib only
        looks inside the category the query named, so it never sees the file
        the model meant. Stem equality is safe to search across every category:
        unlike a global fuzzy search it can only suggest a file spelled exactly
        like the request.
        """
        return sorted(
            {
                asset.library
                for asset in self.assets(kind)
                if asset.name.casefold() == stem
            },
            key=str.casefold,
        )

    def resolve(self, kind: str, query: str) -> MediaAsset:
        """Resolve ``Animals/bat1-a.png``, ``bat1-a.png`` or ``bat1-a``."""
        if not isinstance(query, str) or not query.strip():
            raise MediaError(f"{kind} library reference is empty")
        text = query.strip().replace("\\", "/").strip("/")
        if text.startswith("Media/"):
            text = text[len("Media/") :]
        lowered = text.casefold()
        if ".." in lowered.split("/"):
            raise MediaError(f"invalid {kind} library reference {query!r}")
        if lowered.startswith("/") or ":" in lowered:
            raise MediaError(f"invalid {kind} library reference {query!r}")

        assets = self.assets(kind)
        matches = [asset for asset in assets if asset.library.casefold() == lowered]
        if not matches:
            matches = [asset for asset in assets if asset.path.name.casefold() == lowered]
        if not matches:
            stem = lowered
            for ext in IMAGE_EXTENSIONS:
                if stem.endswith(ext):
                    stem = stem[: -len(ext)]
                    break
            matches = [asset for asset in assets if asset.name.casefold() == stem]
        if not matches:
            # Category/name without an extension.
            matches = [
                asset
                for asset in assets
                if (
                    f"{asset.category}/{asset.name}" if asset.category else asset.name
                ).casefold()
                == lowered
            ]

        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # Imported Scratch 2.0 assets may deliberately reuse the stock
            # library names (for example a bat sprite costume). Keep the
            # original 1.4 meaning of a bare name: prefer the non-Scratch2
            # asset, and require a category path for the imported duplicate.
            stock = [
                asset
                for asset in matches
                if not asset.library.casefold().startswith("scratch2/")
            ]
            if len(stock) == 1:
                return stock[0]
            choices = ", ".join(asset.library for asset in matches[:8])
            raise MediaError(
                f"ambiguous {kind} {query!r} (matches {len(matches)}): {choices}"
            )

        # Prefer suggestions from the requested category. A global closest-match
        # search over the whole library produces nonsense such as skull/ghost
        # for a missing grass tile.
        category = text.rsplit("/", 1)[0] if "/" in text else ""
        if category:
            # However, models often use the wrong category prefix:
            # "Sprites/line.png" names the real "Geometry/line.png". Exact stem
            # matches from any category are precise enough to lead the list,
            # before the fuzzy in-category matches.
            stem = text.rsplit("/", 1)[-1].casefold()
            for ext in IMAGE_EXTENSIONS:
                if stem.endswith(ext):
                    stem = stem[: -len(ext)]
                    break
            exact = self._exact_stem_matches(kind, stem)
            in_category = [
                asset.library
                for asset in assets
                if asset.category.casefold() == category.casefold()
            ]
            if in_category:
                close = difflib.get_close_matches(
                    text, in_category, n=5, cutoff=0.25
                )
                if not close:
                    close = sorted(in_category, key=str.casefold)[:5]
                suggestions = _dedupe(exact + close)[:5]
                raise MediaError(f"unknown {kind} {query!r}", _known_first(suggestions))
            other_kind = BACKDROP if kind == COSTUME else COSTUME
            if any(
                asset.category.casefold() == category.casefold()
                for asset in self.assets(other_kind)
            ):
                raise MediaError(
                    f"unknown {kind} {query!r}: {category!r} is a "
                    f"{other_kind} category, not a {kind} category"
                )
            if exact:
                raise MediaError(f"unknown {kind} {query!r}", _known_first(exact[:5]))

        pool = [asset.library for asset in assets] + [asset.name for asset in assets]
        suggestions = difflib.get_close_matches(text, pool, n=5, cutoff=0.55)
        raise MediaError(f"unknown {kind} {query!r}", _known_first(suggestions))

    def prompt_index(self, kind: str | None = None, max_chars: int = 9000) -> str:
        """Compact grouped list of library names for the system prompt."""
        presets = ""
        if kind is None and max_chars >= 4000:
            presets = self.preset_index(max_chars=min(4200, max_chars // 3))
        kinds = [kind] if kind else [COSTUME, BACKDROP]
        lines: list[str] = []
        for current in kinds:
            assets = self.assets(current)
            if not assets:
                continue
            lines.append(
                f"{KIND_TITLES[current]} (reference as 'category/name.ext'; "
                f"the bare name also works):"
            )
            categories: dict[str, list[str]] = {}
            for asset in assets:
                categories.setdefault(asset.category, []).append(asset.display)
            for category in sorted(categories, key=str.casefold):
                entries = ", ".join(
                    sorted(categories[category], key=str.casefold)
                )
                label = category or "root"
                lines.append(f"  {label}: {entries}")
        body = "\n".join(lines)
        if presets:
            combined = presets + "\n" + body
        else:
            combined = body
        if len(combined) <= max_chars:
            return combined
        marker = f"[media index truncated {len(combined) - max_chars} chars]"
        prefix = presets + "\n" if presets else ""
        if len(prefix) + len(marker) + 1 >= max_chars:
            # No room for the preset list; fall back to the media lines.
            prefix = ""
        room = max(0, max_chars - len(prefix) - len(marker) - 1)
        kept: list[str] = []
        used = 0
        for line in lines:
            extra = len(line) + (1 if kept else 0)
            if used + extra > room:
                break
            kept.append(line)
            used += extra
        text = prefix + "\n".join(kept + [marker])
        if len(text) > max_chars:
            text = prefix + marker
        return text


_DEFAULT_LIBRARY: MediaLibrary | None = None


def default_library() -> MediaLibrary:
    global _DEFAULT_LIBRARY
    if _DEFAULT_LIBRARY is None:
        _DEFAULT_LIBRARY = MediaLibrary()
    return _DEFAULT_LIBRARY


def reset_default_library() -> None:
    """Test helper: drop the cached default index."""
    global _DEFAULT_LIBRARY
    _DEFAULT_LIBRARY = None
