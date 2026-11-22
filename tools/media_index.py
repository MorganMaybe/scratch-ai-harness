from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge" / "src"))

from harness.media import BACKDROP, COSTUME, MediaLibrary, default_media_root  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect Scratch's bundled costume and backdrop library"
    )
    parser.add_argument("--root", help="Media directory (default: scratch/base/Media)")
    parser.add_argument(
        "--kind",
        choices=[COSTUME, BACKDROP, "all"],
        default="all",
        help="asset kind to list",
    )
    parser.add_argument("--presets", action="store_true", help="list Scratch 2.0 sprite presets")
    parser.add_argument("--search", help="case-insensitive substring filter")
    parser.add_argument("--categories", action="store_true", help="print category counts only")
    parser.add_argument("--json", dest="as_json", action="store_true", help="machine-readable output")
    parser.add_argument("--limit", type=int, default=40, help="maximum assets to print")
    parser.add_argument("--prompt", action="store_true", help="print the system-prompt index")
    args = parser.parse_args()

    library = MediaLibrary(args.root or default_media_root())
    kinds = [COSTUME, BACKDROP] if args.kind == "all" else [args.kind]

    if args.prompt:
        print(library.prompt_index(max_chars=100000))
        return

    if args.presets:
        presets = library.sprites()
        if args.search:
            needle = args.search.casefold()
            presets = [
                preset
                for preset in presets
                if needle in preset.name.casefold()
                or any(needle in costume.library.casefold() for costume in preset.costumes)
            ]
        shown_presets = presets[: max(0, args.limit)]
        if args.as_json:
            print(
                json.dumps(
                    [
                        {
                            "name": preset.name,
                            "costumes": [c.library for c in preset.costumes],
                            "direction": preset.direction,
                            "size": preset.size,
                            "rotation_style": preset.rotation_style,
                        }
                        for preset in shown_presets
                    ],
                    indent=2,
                )
            )
            return
        for preset in shown_presets:
            print(
                f"preset   {preset.name}: {len(preset.costumes)} costume(s), "
                f"{preset.rotation_style}, size {preset.size:g}"
            )
        if len(presets) > len(shown_presets):
            print(f"... {len(presets) - len(shown_presets)} more (use --limit)")
        return

    assets = []
    for kind in kinds:
        assets.extend(library.assets(kind))

    if args.search:
        needle = args.search.casefold()
        assets = [
            asset
            for asset in assets
            if needle in asset.library.casefold() or needle in asset.category.casefold()
        ]

    if args.categories:
        counts: dict[str, int] = {}
        for asset in assets:
            key = f"{asset.kind}:{asset.category}"
            counts[key] = counts.get(key, 0) + 1
        if args.as_json:
            print(json.dumps(counts, indent=2, sort_keys=True))
        else:
            for key in sorted(counts):
                print(f"{key}: {counts[key]}")
        return

    shown = assets[: max(0, args.limit)]
    if args.as_json:
        print(
            json.dumps(
                [
                    {
                        "kind": asset.kind,
                        "category": asset.category,
                        "name": asset.name,
                        "ext": asset.ext,
                        "library": asset.library,
                        "path": str(asset.path),
                    }
                    for asset in shown
                ],
                indent=2,
            )
        )
        return

    for asset in shown:
        print(f"{asset.kind:8} {asset.library}")
    if len(assets) > len(shown):
        print(f"... {len(assets) - len(shown)} more (use --limit)")


if __name__ == "__main__":
    main()
