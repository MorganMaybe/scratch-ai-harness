"""Merge classifier JSONL output into bridge/src/harness/media_groups.json.

Reads every *.jsonl under tools/media_groups_work/out/, validates each entry
against the real media library (paths must exist; groups must be known;
presets must be real), merges them into the renderer's schema, and writes:

- bridge/src/harness/media_groups.json   (the curated classification package)
- tools/media_groups_work/REVIEW.md      (uncertain + unclassified items for
                                          manual review)

Group descriptions are authored here (not by the classifiers) so every group
renders with a stable, hand-written one-liner.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge" / "src"))

from harness.media import BACKDROP, COSTUME, default_library  # noqa: E402

WORK = ROOT / "tools" / "media_groups_work"
OUT_JSON = ROOT / "bridge" / "src" / "harness" / "media_groups.json"

COSTUME_GROUPS = (
    "players",
    "enemies",
    "animals",
    "people",
    "food",
    "instruments",
    "geometry",
    "game-items",
    "background-elements",
    "ui",
    "transport",
    "sports",
    "clothing",
    "letters",
    "numbers",
)
BACKDROP_GROUPS = (
    "nature",
    "indoors",
    "outdoors",
    "space",
    "sports",
    "holiday",
    "performance",
    "abstract",
)
GROUP_DESCRIPTIONS = {
    "players": "characters suited to a player-controlled actor",
    "enemies": "hostile characters: monsters, ghosts, dragons, witches",
    "animals": "creatures for critters, pets and wildlife",
    "people": "human characters, dancers, walkers",
    "food": "edible props",
    "instruments": "musical instruments",
    "geometry": "structural, non-character art: bars, blocks, tiles, paddles",
    "game-items": "collectibles and interactive props",
    "background-elements": "scenery pieces: trees, clouds, sun, buildings",
    "ui": "interface elements: buttons, monitors, scoreboard",
    "transport": "vehicles",
    "sports": "sports equipment",
    "clothing": "dress-up items: hats, shirts, glasses, shoes",
    "letters": "glyph families, letters a-z (many also carry 0-9)",
    "numbers": "glyph families carrying digits 0-9",
    "nature": "beaches, woods, skies, space skies",
    "indoors": "interior rooms and halls",
    "outdoors": "streets, playgrounds, city scenes",
    "space": "planets and space scenes",
    "holiday": "seasonal and holiday scenes",
    "performance": "stages, dance and music scenes",
    "abstract": "grids and plain frames",
}


_WORD_RE = re.compile(r"[a-z0-9]+")


def _words(text: str) -> list[str]:
    """Lowercase content words: punctuation and digits dropped, short words out."""
    words: list[str] = []
    for word in _WORD_RE.findall(str(text).casefold()):
        word = word.strip("0123456789")
        if len(word) >= 3:
            words.append(word)
    return words


def stem_echo(stem: str, description: str) -> bool:
    """True when a description only restates the file stem.

    A description is an echo when at least one of its content words (three or
    more letters, case-insensitive, digits and punctuation ignored) already
    appears in the stem, so the rest of the phrase only names the file's own
    kind: "arrow1-a" + "arrow shape", "boy1-walking" + "walking animation".
    A description with no stem overlap adds information and is kept: "line" +
    "flat red bar; vertical pipe at direction 0". An empty (or all-numeric)
    description is vacuously an echo; storing "" loses nothing.
    """
    description_words = _words(description)
    if not description_words:
        return True
    stem_words = set(_words(stem))
    return any(word in stem_words for word in description_words)


def main() -> int:
    lib = default_library()
    costume_paths = {a.library: a for a in lib.assets(COSTUME)}
    backdrop_paths = {a.library: a for a in lib.assets(BACKDROP)}
    preset_names = {p.name for p in lib.sprites()}

    groups: dict[str, dict] = {
        name: {"description": GROUP_DESCRIPTIONS[name], "items": {}, "families": {}}
        for name in COSTUME_GROUPS
    }
    backdrop_groups: dict[str, dict] = {
        name: {"description": GROUP_DESCRIPTIONS[name], "items": {}}
        for name in BACKDROP_GROUPS
    }
    preset_groups: dict[str, dict] = {}
    uncertain: list[str] = []
    dropped: list[str] = []
    stats = {"items": 0, "families": 0, "presets": 0, "uncertain": 0, "dropped": 0}

    family_categories = set()

    def note_uncertain(kind: str, name: str, group: str, description: str) -> None:
        stats["uncertain"] += 1
        uncertain.append(f"| {kind} | `{name}` | {group} | {description or '-'} |")

    for path in sorted((WORK / "out").glob("*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                dropped.append(f"{path.name}:{line_no} (invalid JSON)")
                stats["dropped"] += 1
                continue
            flagged = bool(entry.get("uncertain"))
            if "library" in entry:
                libpath = str(entry["library"])
                group = str(entry.get("group", ""))
                desc = str(entry.get("description", ""))
                stored = "" if stem_echo(Path(libpath).stem, desc) else desc
                if libpath in costume_paths:
                    if group not in COSTUME_GROUPS:
                        dropped.append(f"{libpath} (unknown group {group!r})")
                        stats["dropped"] += 1
                        continue
                    groups[group]["items"][libpath] = stored
                    stats["items"] += 1
                    if flagged:
                        note_uncertain("costume", libpath, group, desc)
                elif libpath in backdrop_paths:
                    if group not in BACKDROP_GROUPS:
                        dropped.append(f"{libpath} (unknown group {group!r})")
                        stats["dropped"] += 1
                        continue
                    backdrop_groups[group]["items"][libpath] = stored
                    stats["items"] += 1
                    if flagged:
                        note_uncertain("backdrop", libpath, group, desc)
                else:
                    dropped.append(f"{libpath} (not in library)")
                    stats["dropped"] += 1
            elif "family" in entry:
                family = str(entry["family"])
                # Classifiers may describe one real prefix with several
                # style entries ("Scratch2/Letters/block style"). Normalise
                # by stripping style words / path segments until the prefix
                # actually owns assets, then combine the style notes into a
                # single family description.
                prefix = family
                while prefix and not any(
                    key.startswith(prefix + "/") for key in costume_paths
                ):
                    if " " in prefix:
                        prefix = prefix.rsplit(" ", 1)[0]
                    elif "/" in prefix:
                        prefix = prefix.rsplit("/", 1)[0]
                    else:
                        prefix = ""
                if not prefix:
                    dropped.append(f"family {family} (no assets under prefix)")
                    stats["dropped"] += 1
                    continue
                family_categories.add(prefix)
                group = str(entry.get("group", "letters"))
                if group not in COSTUME_GROUPS:
                    group = "letters"
                sample = sorted(
                    key for key in costume_paths if key.startswith(prefix + "/")
                )
                existing = groups[group]["families"].get(prefix)
                if existing is None:
                    existing = {
                        "description": str(entry.get("description", "")),
                        "glyphs": str(entry.get("glyphs", "")),
                        "example": sample[0] if sample else "",
                    }
                    groups[group]["families"][prefix] = existing
                    stats["families"] += 1
                else:
                    # Second style entry for the same prefix: merge notes.
                    for field in ("description", "glyphs"):
                        value = str(entry.get(field, ""))
                        if value and value not in existing[field]:
                            existing[field] = (
                                existing[field] + " / " + value
                                if existing[field]
                                else value
                            )
                if flagged:
                    note_uncertain(
                        "family", f"{prefix}/*", group, str(entry.get("description", ""))
                    )
            elif "name" in entry:
                name = str(entry["name"])
                group = str(entry.get("group", ""))
                if name not in preset_names:
                    dropped.append(f"preset {name} (unknown preset)")
                    stats["dropped"] += 1
                    continue
                if group not in COSTUME_GROUPS:
                    dropped.append(f"preset {name} (unknown group {group!r})")
                    stats["dropped"] += 1
                    continue
                bucket = preset_groups.setdefault(
                    group, {"description": GROUP_DESCRIPTIONS[group], "names": []}
                )
                bucket["names"].append(name)
                stats["presets"] += 1
                if flagged:
                    note_uncertain("preset", name, group, str(entry.get("description", "")))
            else:
                dropped.append(f"{path.name}:{line_no} (unrecognized shape)")
                stats["dropped"] += 1

    for bucket in preset_groups.values():
        bucket["names"].sort()

    # Anything classified as a family hides its member assets from the
    # unclassified tail; the renderer derives that from the family prefixes.
    classified = set()
    for group in groups.values():
        classified.update(group["items"])
    for group in backdrop_groups.values():
        classified.update(group["items"])
    family_prefixes = [
        prefix
        for group in groups.values()
        for prefix in group.get("families", {})
    ]
    unclassified = [
        path
        for path in costume_paths
        if path not in classified
        and not any(path.startswith(prefix + "/") for prefix in family_prefixes)
    ]
    unclassified_backdrops = [
        path for path in backdrop_paths if path not in classified
    ]

    OUT_JSON.write_text(
        json.dumps(
            {
                "version": 1,
                "groups": groups,
                "preset_groups": preset_groups,
                "backdrop_groups": backdrop_groups,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )

    review = WORK / "REVIEW.md"
    lines = [
        "# Media group classification - manual review",
        "",
        f"Merged {stats['items']} items, {stats['families']} families, "
        f"{stats['presets']} presets; "
        f"{stats['uncertain']} flagged uncertain, "
        f"{stats['dropped']} dropped.",
        "",
        "## Uncertain entries (please correct group/description)",
        "",
        "| kind | item | suggested group | description |",
        "|---|---|---|---|",
        *uncertain,
        "",
        "## Dropped entries (invalid path/preset/group)",
        "",
        *(f"- {entry}" for entry in dropped),
        "",
        "## Assets with no classification (kept in the raw 'other' tail)",
        "",
        f"- {len(unclassified)} costume files, e.g. "
        + ", ".join(f"`{p}`" for p in unclassified[:10]),
        f"- {len(unclassified_backdrops)} backdrop files, e.g. "
        + ", ".join(f"`{p}`" for p in unclassified_backdrops[:10]),
        "",
    ]
    review.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(stats, indent=1))
    print(f"wrote {OUT_JSON}")
    print(f"wrote {review}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
