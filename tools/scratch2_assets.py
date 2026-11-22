r"""Import Scratch 2.0 library assets into the Scratch 1.4 media tree.

This is intentionally an *opt-in* tool.  Scratch 2.0's sprite/costume/backdrop/
sound libraries are not open source; do not redistribute the imported files in
a public build without checking the Scratch Source Code License and the
Scratch trademark rules.  The tool writes a local attribution/manifest file so
the provenance of every imported asset is visible.

Typical use (offline editor already extracted):

    python tools/scratch2_assets.py ^
        --source "C:\...\Scratch 2\media" ^
        --resvg "C:\...\resvg.exe" --all

Outputs:

    scratch/base/Media/Costumes/Scratch2/...
    scratch/base/Media/Backgrounds/Scratch2/...
    scratch/base/Media/Sounds/Scratch2/...
    scratch/base/Media/Scratch2/sprites.json
    scratch/base/Media/Scratch2/ATTRIBUTION.md
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "scratch" / "base" / "Media"


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, list):
        raise SystemExit(f"{path}: expected a JSON array")
    return [item for item in value if isinstance(item, dict)]


def slug(value: str, fallback: str = "asset") -> str:
    text = value.strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or fallback


def category_for(entry: dict[str, Any], fallback: str = "Other") -> str:
    tags = entry.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.strip():
                return slug(tag, fallback).title().replace("-", " ")
    return fallback


def source_path(media: Path, md5: str) -> Path:
    path = media / md5
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def copy_or_render(
    source: Path,
    destination: Path,
    resvg: str,
    scale: float,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == ".svg":
        subprocess.run(
            [resvg, "-z", str(scale), str(source), str(destination)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    elif source.suffix.lower() in {".png", ".gif", ".jpg", ".jpeg", ".bmp"}:
        destination.write_bytes(source.read_bytes())
    else:
        shutil.copy2(source, destination)


def import_costume(
    entry: dict[str, Any],
    media: Path,
    output: Path,
    resvg: str,
    scale: float,
    prefix: tuple[str, ...],
) -> str | None:
    md5 = entry.get("baseLayerMD5")
    name = entry.get("costumeName") or entry.get("name") or "costume"
    if not isinstance(md5, str) or not md5:
        return None
    source = media / md5
    if not source.is_file():
        return None
    ext = ".png" if source.suffix.lower() == ".svg" else source.suffix.lower()
    relative = output / "Costumes" / Path(*prefix) / f"{slug(str(name))}{ext}"
    copy_or_render(source, relative, resvg, scale)
    return Path(*prefix, f"{slug(str(name))}{ext}").as_posix()


def import_library_assets(
    entries: list[dict[str, Any]],
    kind: str,
    media: Path,
    output: Path,
    resvg: str,
    scale: float,
) -> list[str]:
    imported: list[str] = []
    target_root = "Costumes" if kind == "costume" else "Backgrounds"
    for entry in entries:
        entry_type = entry.get("type")
        if entry_type and entry_type != kind:
            continue
        md5 = entry.get("md5")
        name = entry.get("name")
        if not isinstance(md5, str) or not isinstance(name, str):
            continue
        source = media / md5
        if not source.is_file():
            continue
        ext = ".png" if source.suffix.lower() == ".svg" else source.suffix.lower()
        category = category_for(entry)
        relative = output / target_root / "Scratch2" / category / f"{slug(name)}{ext}"
        copy_or_render(source, relative, resvg, scale)
        imported.append(Path("Scratch2", category, f"{slug(name)}{ext}").as_posix())
    return imported


def import_sprite(
    entry: dict[str, Any],
    media: Path,
    output: Path,
    resvg: str,
    scale: float,
) -> dict[str, Any] | None:
    md5 = entry.get("md5")
    name = entry.get("name")
    if not isinstance(md5, str) or not isinstance(name, str):
        return None
    sprite_path = media / md5
    if not sprite_path.is_file():
        return None
    with sprite_path.open("r", encoding="utf-8") as handle:
        sprite = json.load(handle)
    if not isinstance(sprite, dict):
        return None

    sprite_slug = slug(name)
    costumes: list[str] = []
    centers: list[list[float]] = []
    center_scales: list[float] = []
    costume_entries = sprite.get("costumes", [])
    if not isinstance(costume_entries, list):
        costume_entries = []
    for index, costume in enumerate(costume_entries, 1):
        if not isinstance(costume, dict):
            continue
        costume_md5 = costume.get("baseLayerMD5")
        if not isinstance(costume_md5, str):
            continue
        source = media / costume_md5
        if not source.is_file():
            continue
        ext = ".png" if source.suffix.lower() == ".svg" else source.suffix.lower()
        costume_name = slug(str(costume.get("costumeName") or f"costume-{index}"))
        relative = (
            output
            / "Costumes"
            / "Scratch2"
            / "Sprites"
            / sprite_slug
            / f"{costume_name}{ext}"
        )
        copy_or_render(source, relative, resvg, scale)
        costumes.append(
            Path(
                "Scratch2",
                "Sprites",
                sprite_slug,
                f"{costume_name}{ext}",
            ).as_posix()
        )
        centers.append(
            [
                float(costume.get("rotationCenterX", 0) or 0),
                float(costume.get("rotationCenterY", 0) or 0),
            ]
        )
        # SVG costumes are rendered at --scale; bitmap costumes are copied 1:1.
        center_scales.append(scale if source.suffix.lower() == ".svg" else 1.0)

    sounds: list[str] = []
    sound_entries = sprite.get("sounds", [])
    if not isinstance(sound_entries, list):
        sound_entries = []
    for index, sound in enumerate(sound_entries, 1):
        if not isinstance(sound, dict):
            continue
        sound_md5 = sound.get("md5")
        if not isinstance(sound_md5, str):
            continue
        source = media / sound_md5
        if not source.is_file():
            continue
        sound_name = slug(str(sound.get("soundName") or f"sound-{index}"))
        relative = (
            output
            / "Sounds"
            / "Scratch2"
            / "Sprites"
            / sprite_slug
            / f"{sound_name}{source.suffix.lower()}"
        )
        relative.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, relative)
        sounds.append(
            Path(
                "Scratch2",
                "Sprites",
                sprite_slug,
                f"{sound_name}{source.suffix.lower()}",
            ).as_posix()
        )

    if not costumes:
        return None
    return {
        "name": name,
        "costumes": costumes,
        "rotation_centers": centers,
        "rotation_center_scales": center_scales,
        "sounds": sounds,
        "direction": sprite.get("direction", 90),
        "size": round(float(sprite.get("scale", 1) or 1) * 100, 3),
        "rotation_style": sprite.get("rotationStyle", "normal"),
    }


def import_sound_library(
    entries: list[dict[str, Any]],
    media: Path,
    output: Path,
) -> int:
    count = 0
    for entry in entries:
        if entry.get("type") != "sound":
            continue
        md5 = entry.get("md5")
        name = entry.get("name")
        if not isinstance(md5, str) or not isinstance(name, str):
            continue
        source = media / md5
        if not source.is_file():
            continue
        category = category_for(entry, "Other")
        relative = output / "Sounds" / "Scratch2" / category / f"{slug(name)}{source.suffix.lower()}"
        relative.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, relative)
        count += 1
    return count


def write_attribution(output: Path, source: Path, counts: dict[str, int]) -> None:
    path = output / "Scratch2" / "ATTRIBUTION.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Scratch 2.0 library assets (local import)",
                "",
                "Source: Scratch 2.0 offline editor (v461) media library.",
                f"Imported: {_dt.date.today().isoformat()}",
                f"Source folder: `{source}`",
                "",
                "**These assets are not open source.** The Scratch Team's sprite,",
                "costume, backdrop and sound libraries are not released under the",
                "Scratch 1.4 GPL source license. This folder is for local",
                "development/personal use only. Do not redistribute these files in a",
                "public build without permission; check the Scratch Source Code",
                "License and the Scratch trademark rules first.",
                "",
                "Counts:",
                *[f"- {key}: {value}" for key, value in sorted(counts.items())],
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Scratch 2.0 'media' folder")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Scratch 1.4 Media folder")
    parser.add_argument("--resvg", default="resvg", help="resvg executable (needed for SVG costumes)")
    parser.add_argument("--scale", type=float, default=2.0, help="SVG raster scale (default 2)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="import sprite, costume, backdrop and sound libraries",
    )
    parser.add_argument("--sprites", action="store_true", help="import sprite presets and their costumes")
    parser.add_argument("--costumes", action="store_true", help="import the costume library")
    parser.add_argument("--backdrops", action="store_true", help="import the backdrop library")
    parser.add_argument("--sounds", action="store_true", help="import the sound library")
    parser.add_argument("--no-sprites", action="store_true", help="skip sprite presets")
    args = parser.parse_args()

    media = Path(args.source)
    output = Path(args.output)
    libs = media / "libs"
    if not libs.is_dir():
        raise SystemExit(f"{libs}: expected Scratch 2.0 'media/libs'")
    if not (media / "Scratch.swf").parent.is_dir():
        # The media folder is enough; this is a deliberate no-op check for a
        # clearer error if the wrong directory is passed.
        pass

    do_sprites = args.all or args.sprites
    do_costumes = args.all or args.costumes
    do_backdrops = args.all or args.backdrops
    do_sounds = args.all or args.sounds
    if not any((do_sprites, do_costumes, do_backdrops, do_sounds)):
        raise SystemExit("choose --all, or one of --sprites/--costumes/--backdrops/--sounds")

    counts: dict[str, int] = {}
    if do_costumes:
        entries = load_json(libs / "costumeLibrary.json")
        counts["costume_library"] = len(
            import_library_assets(entries, "costume", media, output, args.resvg, args.scale)
        )
    if do_backdrops:
        entries = load_json(libs / "backdropLibrary.json")
        counts["backdrop_library"] = len(
            import_library_assets(entries, "backdrop", media, output, args.resvg, args.scale)
        )
    if do_sounds:
        entries = load_json(libs / "soundLibrary.json")
        counts["sound_library"] = import_sound_library(entries, media, output)

    if do_sprites and not args.no_sprites:
        entries = load_json(libs / "spriteLibrary.json")
        sprites: list[dict[str, Any]] = []
        for entry in entries:
            imported = import_sprite(entry, media, output, args.resvg, args.scale)
            if imported is not None:
                sprites.append(imported)
        sprites.sort(key=lambda item: str(item["name"]).casefold())
        manifest = {
            "source": "Scratch 2.0 offline editor v461",
            "note": "Local import; not open source. See ATTRIBUTION.md.",
            "sprites": sprites,
        }
        manifest_path = output / "Scratch2" / "sprites.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        counts["sprite_presets"] = len(sprites)
        counts["sprite_costumes"] = sum(len(item["costumes"]) for item in sprites)
        counts["sprite_sounds"] = sum(len(item["sounds"]) for item in sprites)

    write_attribution(output, media, counts)
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
