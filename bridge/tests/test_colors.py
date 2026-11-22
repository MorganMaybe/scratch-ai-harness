"""Color sensing and RGB pen color blocks."""

from __future__ import annotations

import pytest

from harness.block_ir import ChangeSet
from harness.changeset import compile_changeset
from harness.context import ProjectContext
from harness.validator import validate_changeset


def _change(*body: dict) -> ChangeSet:
    return ChangeSet.from_dict(
        {
            "summary": "color probe",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "color_probe",
                    "hat": {"op": "when_flag_clicked"},
                    "body": list(body),
                }
            ],
        }
    )


def test_touching_color_validates_and_compiles_to_a_color_marker():
    changeset = _change(
        {
            "op": "if",
            "args": {
                "condition": {
                    "op": "touching_color",
                    "args": {"color": "#ff0000"},
                }
            },
            "body": [],
        }
    )

    assert validate_changeset(changeset, ProjectContext.demo()) == []
    literal = compile_changeset(changeset, ProjectContext.demo()).apply_literal(1)
    assert "touchingColor:" in literal
    assert "#(#color 255 0 0)" in literal


def test_color_sees_compiles_two_colors():
    changeset = _change(
        {
            "op": "if",
            "args": {
                "condition": {
                    "op": "color_sees",
                    "args": {"color": "#00ff00", "color2": "#ff0000"},
                }
            },
            "body": [],
        }
    )

    assert validate_changeset(changeset, ProjectContext.demo()) == []
    literal = compile_changeset(changeset, ProjectContext.demo()).apply_literal(1)
    assert "color:sees:" in literal
    assert "#(#color 0 255 0)" in literal
    assert "#(#color 255 0 0)" in literal


def test_set_pen_color_compiles():
    changeset = _change({"op": "set_pen_color", "args": {"color": "#123456"}})

    assert validate_changeset(changeset, ProjectContext.demo()) == []
    literal = compile_changeset(changeset, ProjectContext.demo()).apply_literal(1)
    assert "penColor:" in literal
    assert "#(#color 18 52 86)" in literal


@pytest.mark.parametrize("bad", ["red", "#ff00", "#gggggg", 123])
def test_invalid_color_is_rejected(bad):
    changeset = _change(
        {
            "op": "if",
            "args": {
                "condition": {
                    "op": "touching_color",
                    "args": {"color": bad},
                }
            },
            "body": [],
        }
    )

    issues = validate_changeset(changeset, ProjectContext.demo())
    assert any("expected a color" in issue.message for issue in issues)


def test_color_argument_cannot_be_a_reporter():
    changeset = _change(
        {
            "op": "if",
            "args": {
                "condition": {
                    "op": "touching_color",
                    "args": {"color": {"op": "x_position"}},
                }
            },
            "body": [],
        }
    )

    issues = validate_changeset(changeset, ProjectContext.demo())
    assert any("not reporters" in issue.message for issue in issues)
