"""Filter the curated media groups for a redistributable release bundle.

The public bundle ships stock Scratch 1.4 media only. This drops any curated
costume/backdrop path that is not present in the staged Media tree and removes
the Scratch 2.0 sprite-preset list (its assets are not redistributed).

Usage:
    python tools/release_media_groups.py <media_groups.json> <staged Media dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _asset_exists(media_root: Path, key: str) -> bool:
    cleaned = key.strip().replace("\\", "/").strip("/")
    return any((base / cleaned).is_file() for base in (media_root / "Costumes", media_root / "Backgrounds"))


def _family_exists(media_root: Path, prefix: str) -> bool:
    cleaned = prefix.strip().replace("\\", "/").strip("/")
    for base in (media_root / "Costumes", media_root / "Backgrounds"):
        folder = base / cleaned
        if folder.is_dir() and any(folder.iterdir()):
            return True
    return False


def _filter_section(media_root: Path, section: object) -> None:
    if not isinstance(section, dict):
        return
    for entry in section.values():
        if not isinstance(entry, dict):
            continue
        items = entry.get("items")
        if isinstance(items, dict):
            entry["items"] = {
                key: value
                for key, value in items.items()
                if isinstance(key, str) and _asset_exists(media_root, key)
            }
        families = entry.get("families")
        if isinstance(families, dict):
            entry["families"] = {
                key: value
                for key, value in families.items()
                if isinstance(key, str) and _family_exists(media_root, key)
            }


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    groups_path = Path(sys.argv[1])
    media_root = Path(sys.argv[2])
    data = json.loads(groups_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"unexpected groups file: {groups_path}")
    _filter_section(media_root, data.get("groups"))
    _filter_section(media_root, data.get("backdrop_groups"))
    # Scratch 2.0 presets are not in the redistributable bundle.
    data["preset_groups"] = {}
    groups_path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
