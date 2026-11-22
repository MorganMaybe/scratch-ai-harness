"""Small block-gap pack: catalog, validation and tuple compilation."""

from __future__ import annotations

from harness.block_ir import ChangeSet
from harness.changeset import compile_changeset
from harness.context import ProjectContext
from harness.validator import validate_changeset


def _gaps_changeset() -> ChangeSet:
    return ChangeSet.from_dict(
        {
            "summary": "block gaps",
            "changes": [
                {
                    "action": "create_list",
                    "name": "items",
                    "scope": "global",
                    "items": ["a", "b"],
                },
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "gaps",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [
                        {"op": "current", "args": {"part": "year"}},
                        {"op": "days_since_2000"},
                        {"op": "username"},
                        {
                            "op": "set_rotation_style",
                            "args": {"style": "left-right"},
                        },
                        {"op": "go_to_back"},
                        {
                            "op": "go_forward_layers",
                            "args": {"layers": 2},
                        },
                        {"op": "stop_other_scripts"},
                        {"op": "key_pressed", "args": {"key": "any"}},
                        {
                            "op": "set_attribute_of",
                            "args": {
                                "attribute": "x position",
                                "target": "Sprite1",
                                "value": 10,
                            },
                        },
                        {
                            "op": "change_attribute_of",
                            "args": {
                                "attribute": "size",
                                "target": "Sprite1",
                                "delta": 10,
                            },
                        },
                        {
                            "op": "show_list",
                            "args": {"list": "items"},
                        },
                        {
                            "op": "hide_list",
                            "args": {"list": "items"},
                        },
                        {
                            "op": "list_item_number",
                            "args": {"item": "a", "list": "items"},
                        },
                    ],
                },
                {
                    "action": "add_script",
                    "target": "Stage",
                    "label": "stage_hats",
                    "hat": {"op": "when_stage_clicked"},
                    "body": [{"op": "next_backdrop"}],
                },
                {
                    "action": "add_script",
                    "target": "Stage",
                    "label": "backdrop_hat",
                    "hat": {
                        "op": "when_backdrop_switches",
                        "args": {"backdrop": "background1"},
                    },
                    "body": [{"op": "next_backdrop"}],
                },
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "timer_hat",
                    "hat": {
                        "op": "when_timer_greater",
                        "args": {"value": 1},
                    },
                    "body": [{"op": "move", "args": {"steps": 1}}],
                },
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "loudness_hat",
                    "hat": {
                        "op": "when_loudness_greater",
                        "args": {"value": 10},
                    },
                    "body": [{"op": "move", "args": {"steps": 1}}],
                },
            ],
        }
    )


def test_gap_changeset_validates_and_compiles():
    context = ProjectContext.demo()
    assert validate_changeset(_gaps_changeset(), context) == []

    literal = compile_changeset(_gaps_changeset(), context).apply_literal(1)
    for selector in (
        "current:",
        "daysSince2000",
        "username",
        "setRotationStyle:",
        "goToBack",
        "goForwardByLayers:",
        "stopOtherScripts",
        "setAttribute:of:to:",
        "changeAttribute:of:by:",
        "showList:",
        "hideList:",
        "itemNumOf:inList:",
        "StageClickEventHatMorph",
        "BackdropHatMorph",
        "WhenTimerHatMorph",
        "WhenLoudnessHatMorph",
    ):
        assert selector in literal


def test_stage_only_hats_are_rejected_on_a_sprite():
    changeset = ChangeSet.from_dict(
        {
            "summary": "bad stage hat",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "bad",
                    "hat": {"op": "when_stage_clicked"},
                    "body": [],
                }
            ],
        }
    )
    issues = validate_changeset(changeset, ProjectContext.demo())
    assert any("cannot be used on" in issue.message for issue in issues)


def test_unknown_backdrop_and_attribute_are_rejected():
    changeset = ChangeSet.from_dict(
        {
            "summary": "bad args",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Stage",
                    "label": "bad_backdrop",
                    "hat": {
                        "op": "when_backdrop_switches",
                        "args": {"backdrop": "not-a-backdrop"},
                    },
                    "body": [],
                },
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "bad_attr",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [
                        {
                            "op": "set_attribute_of",
                            "args": {
                                "attribute": "not-an-attribute",
                                "target": "Sprite1",
                                "value": 1,
                            },
                        }
                    ],
                },
            ],
        }
    )
    context = ProjectContext.demo()
    context.sprites["Stage"].costumes.append("background1")
    issues = validate_changeset(changeset, context)
    assert any("unknown backdrop" in issue.message for issue in issues)
    assert any("unknown attribute" in issue.message for issue in issues)
