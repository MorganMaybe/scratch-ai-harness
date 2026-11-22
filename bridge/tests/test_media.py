from __future__ import annotations

import pytest

from harness.media import BACKDROP, COSTUME, MediaError, MediaLibrary, default_library


def _library_with(tmp_path, relative_paths):
    """A throwaway Media tree with just the files a test needs."""
    root = tmp_path / "Media"
    for relative in relative_paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return MediaLibrary(root)


def test_default_library_indexes_scratch_media():
    library = default_library()
    costumes = library.assets(COSTUME)
    backdrops = library.assets(BACKDROP)
    assert costumes, "the Scratch costume library should be indexed"
    assert backdrops, "the Scratch backdrop library should be indexed"
    assert all(asset.path.is_file() for asset in costumes[:20])
    assert all(asset.path.is_file() for asset in backdrops[:20])
    # .sprite bundles and index files are not costumes for the MVP.
    assert not any(asset.ext == ".sprite" for asset in costumes)
    assert not any(asset.ext == ".db" for asset in costumes)


def test_resolve_accepts_full_path_name_and_bare_stem():
    library = default_library()
    asset = library.resolve(COSTUME, "Animals/bat1-a.png")
    assert asset.name == "bat1-a"
    assert asset.library == "Animals/bat1-a.png"
    assert library.resolve(COSTUME, "bat1-a.png") == asset
    assert library.resolve(COSTUME, "BAT1-A") == asset


def test_resolve_backdrop_and_nested_letter_category():
    library = default_library()
    stars = library.resolve(BACKDROP, "Space/stars.gif")
    assert stars.kind == BACKDROP
    assert stars.category == "Space"
    letter = library.resolve(COSTUME, "Letters/Auto/0.gif")
    assert letter.category == "Letters/Auto"


def test_resolve_reports_near_matches():
    library = default_library()
    with pytest.raises(MediaError) as excinfo:
        library.resolve(COSTUME, "Animals/bat1-z.png")
    assert "unknown costume" in str(excinfo.value)
    assert "near matches" in str(excinfo.value)


def test_resolve_puts_cross_category_exact_stem_first(tmp_path):
    # The deduplicated tree has only one "line" file, so recreate the
    # cross-category duplicate condition in a throwaway library.
    library = _library_with(
        tmp_path,
        (
            "Costumes/Scenery/lime.png",
            "Costumes/Scenery/line-up.png",
            "Costumes/Geometry/line.png",
            "Costumes/Presets/line.png",
        ),
    )
    with pytest.raises(MediaError) as excinfo:
        library.resolve(COSTUME, "Scenery/line.png")
    suggestions = excinfo.value.suggestions
    assert "Geometry/line.png" in suggestions
    assert "Presets/line.png" in suggestions
    # Exact stems lead; the requested category's fuzzy matches follow.
    assert suggestions[:2] == [
        "Geometry/line.png",
        "Presets/line.png",
    ]
    assert all(suggestion.startswith("Scenery/") for suggestion in suggestions[2:])
    assert len(suggestions) <= 5


def test_resolve_exact_stem_suggestions_stay_within_the_kind(tmp_path):
    # Stock and imported copies of the same backdrop used to coexist; create
    # both again, plus a costume with the same stem that must not leak in.
    library = _library_with(
        tmp_path,
        (
            "Backgrounds/Outdoors/atom-playground.jpg",
            "Backgrounds/Scratch2/Outdoors/atom-playground.jpg",
            "Backgrounds/Sports/field.png",
            "Costumes/Players/atom-playground.jpg",
        ),
    )
    with pytest.raises(MediaError) as excinfo:
        library.resolve(BACKDROP, "Sports/atom-playground.jpg")
    suggestions = excinfo.value.suggestions
    assert suggestions[:2] == [
        "Outdoors/atom-playground.jpg",
        "Scratch2/Outdoors/atom-playground.jpg",
    ]
    assert "Players/atom-playground.jpg" not in suggestions


def test_resolve_nonsense_name_keeps_in_category_suggestions(tmp_path):
    library = _library_with(
        tmp_path,
        (
            "Costumes/Geometry/line.png",
            "Costumes/Geometry/arrow1-a.png",
            "Costumes/Geometry/arrow1-b.png",
        ),
    )
    with pytest.raises(MediaError) as excinfo:
        library.resolve(COSTUME, "Geometry/zzzzq.png")
    suggestions = excinfo.value.suggestions
    assert suggestions
    assert all(suggestion.startswith("Geometry/") for suggestion in suggestions)
    assert len(suggestions) <= 5


def test_resolve_existing_cross_category_asset_is_unaffected(tmp_path):
    # An exact category path must still win when the same stem also exists in
    # another category (the old stock/Scratch2 duplicate arrangement).
    library = _library_with(
        tmp_path,
        (
            "Costumes/Animals/bat1-a.png",
            "Costumes/Players/bat1-a.png",
        ),
    )
    asset = library.resolve(COSTUME, "Players/bat1-a.png")
    assert asset.kind == COSTUME
    assert asset.library == "Players/bat1-a.png"


def test_resolve_explains_wrong_category():
    library = default_library()
    with pytest.raises(MediaError) as excinfo:
        library.resolve(COSTUME, "Nature/grass1.png")
    text = str(excinfo.value)
    assert "unknown costume" in text
    assert "backdrop category" in text


@pytest.mark.parametrize("query", ["../Costumes/Animals/bat1-a.png", "/etc/passwd", "C:/x.png"])
def test_resolve_rejects_traversal_and_absolute_paths(query):
    with pytest.raises(MediaError):
        default_library().resolve(COSTUME, query)


def test_prompt_index_is_compact_and_trimmed():
    library = default_library()
    tight = library.prompt_index(max_chars=1200)
    assert len(tight) <= 1200
    assert "truncated" in tight
    # Curated folders put many more names on one line, so use a cap that fits
    # the first category line and still trims the rest.
    trimmed = library.prompt_index(max_chars=3000)
    assert len(trimmed) <= 3000
    assert "Animals:" in trimmed
    assert "truncated" in trimmed
    full = library.prompt_index(max_chars=100000)
    assert "Animals/bat1-a.png" not in full  # grouped as category + name
    assert "bat1-a.png" in full
    assert "Nature:" in full


def test_sprite_presets_load_and_resolve():
    library = default_library()
    presets = library.sprites()
    assert presets, "Scratch 2.0 sprite presets should be available locally"
    dog = library.resolve_sprite("dog puppy")
    assert dog.name == "Dog Puppy"
    assert len(dog.costumes) >= 1
    assert all(costume.name for costume in dog.costumes)
    assert dog.rotation_style in {"all around", "left-right", "don't rotate"}


def test_sprite_preset_prompt_index_is_bounded():
    library = default_library()
    text = library.preset_index(max_chars=900)
    assert text
    assert len(text) <= 900
    assert "Sprite presets" in text

