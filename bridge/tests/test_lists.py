"""List change actions, list blocks and the generic math function menu."""

from __future__ import annotations

import pytest

from harness.block_ir import ChangeSet, IRError
from harness.changeset import compile_changeset
from harness.context import ProjectContext
from harness.protocol import parse_literal
from harness.validator import validate_changeset


def _list_changeset(*body: dict) -> ChangeSet:
    return ChangeSet.from_dict(
        {
            "summary": "list probe",
            "changes": [
                {
                    "action": "create_list",
                    "name": "items",
                    "scope": "global",
                    "items": ["a", 1],
                },
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "use_list",
                    "hat": {"op": "when_flag_clicked"},
                    "body": list(body),
                },
            ],
        }
    )


def test_create_list_and_list_blocks_compile():
    changeset = _list_changeset(
        {"op": "add_to_list", "args": {"item": "b", "list": "items"}},
        {"op": "insert_in_list", "args": {"item": "c", "index": 1, "list": "items"}},
        {"op": "replace_in_list", "args": {"index": 1, "list": "items", "item": "d"}},
        {"op": "delete_from_list", "args": {"index": "last", "list": "items"}},
        {
            "op": "say",
            "args": {"text": {"op": "list_item", "args": {"index": 1, "list": "items"}}},
        },
        {
            "op": "say",
            "args": {"text": {"op": "list_length", "args": {"list": "items"}}},
        },
        {
            "op": "if",
            "args": {
                "condition": {
                    "op": "list_contains",
                    "args": {"list": "items", "item": "a"},
                }
            },
            "body": [],
        },
    )

    assert validate_changeset(changeset, ProjectContext.demo()) == []
    literal = compile_changeset(changeset, ProjectContext.demo()).apply_literal(1)
    assert "createList" in literal
    assert "'items'" in literal
    assert "append:toList:" in literal
    assert "insert:at:ofList:" in literal
    assert "setLine:ofList:to:" in literal
    assert "deleteLine:ofList:" in literal
    assert "getLine:ofList:" in literal
    assert "lineCountOfList:" in literal
    assert "list:contains:" in literal


def test_unknown_list_is_rejected():
    changeset = _list_changeset(
        {"op": "add_to_list", "args": {"item": "b", "list": "missing"}}
    )

    issues = validate_changeset(changeset, ProjectContext.demo())
    assert any("unknown list" in issue.message for issue in issues)


def test_list_index_values_are_checked():
    okay = _list_changeset(
        {"op": "delete_from_list", "args": {"index": "all", "list": "items"}}
    )
    assert validate_changeset(okay, ProjectContext.demo()) == []

    bad = _list_changeset(
        {"op": "delete_from_list", "args": {"index": "middle", "list": "items"}}
    )
    issues = validate_changeset(bad, ProjectContext.demo())
    assert any("last' or 'all'" in issue.message for issue in issues)

    zero = _list_changeset(
        {"op": "list_item", "args": {"index": 0, "list": "items"}}
    )
    issues = validate_changeset(zero, ProjectContext.demo())
    assert any("at least 1" in issue.message for issue in issues)


def test_create_list_rejects_duplicate_and_bad_items():
    duplicate = ChangeSet.from_dict(
        {
            "summary": "dupe",
            "changes": [
                {"action": "create_list", "name": "items", "scope": "global"},
                {"action": "create_list", "name": "items", "scope": "global"},
            ],
        }
    )
    issues = validate_changeset(duplicate, ProjectContext.demo())
    assert any("already exists" in issue.message for issue in issues)

    with pytest.raises(IRError):
        ChangeSet.from_dict(
            {
                "summary": "bad",
                "changes": [
                    {
                        "action": "create_list",
                        "name": "items",
                        "scope": "global",
                        "items": [{"not": "a scalar"}],
                    }
                ],
            }
        )
    with pytest.raises(IRError):
        ChangeSet.from_dict(
            {
                "summary": "bad newline",
                "changes": [
                    {
                        "action": "create_list",
                        "name": "items",
                        "scope": "global",
                        "items": ["two\nlines"],
                    }
                ],
            }
        )


def test_sprite_list_is_visible_only_to_that_sprite():
    changeset = ChangeSet.from_dict(
        {
            "summary": "sprite list",
            "changes": [
                {
                    "action": "create_list",
                    "name": "local",
                    "scope": "sprite",
                    "target": "Sprite1",
                    "items": [],
                },
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "use_local",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [
                        {"op": "add_to_list", "args": {"item": "x", "list": "local"}}
                    ],
                },
            ],
        }
    )
    assert validate_changeset(changeset, ProjectContext.demo()) == []

    other = ChangeSet.from_dict(
        {
            "summary": "other sprite",
            "changes": [
                {
                    "action": "create_list",
                    "name": "local",
                    "scope": "sprite",
                    "target": "Sprite1",
                    "items": [],
                },
                {
                    "action": "create_sprite",
                    "name": "Other",
                    "costumes": [{"library": "Animals/bat1-a.png"}],
                },
                {
                    "action": "add_script",
                    "target": "Other",
                    "label": "bad",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [
                        {"op": "add_to_list", "args": {"item": "x", "list": "local"}}
                    ],
                },
            ],
        }
    )
    issues = validate_changeset(other, ProjectContext.demo())
    assert any("unknown list" in issue.message for issue in issues)


def test_context_keeps_sprite_and_global_list_names():
    literal = (
        "#('Sprite1' #("
        "#('Stage' true #() #('global_list') #('background1') #() #() "
        "#(0 0 90 100 true 'normal' false 1)) "
        "#('Sprite1' false #() #('local_list') #('costume1') #() #() "
        "#(0 0 90 100 true 'normal' false 1))))"
    )

    context = ProjectContext.from_literal(parse_literal(literal))

    assert context.list_names("Stage") == ["global_list"]
    assert context.list_names("Sprite1") == ["global_list", "local_list"]
    assert "lists=local_list" in context.summary_text()


def test_math_function_compiles_and_rejects_unknown_functions():
    changeset = ChangeSet.from_dict(
        {
            "summary": "math",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "math",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [
                        {
                            "op": "say",
                            "args": {
                                "text": {
                                    "op": "math_function",
                                    "args": {"function": "sin", "n": 0},
                                }
                            },
                        }
                    ],
                }
            ],
        }
    )
    assert validate_changeset(changeset, ProjectContext.demo()) == []
    literal = compile_changeset(changeset, ProjectContext.demo()).apply_literal(1)
    assert "computeFunction:of:" in literal
    assert "'sin'" in literal

    bad = ChangeSet.from_dict(
        {
            "summary": "math",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "math",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [
                        {
                            "op": "say",
                            "args": {
                                "text": {
                                    "op": "math_function",
                                    "args": {"function": "bogus", "n": 0},
                                }
                            },
                        }
                    ],
                }
            ],
        }
    )
    issues = validate_changeset(bad, ProjectContext.demo())
    assert any("expected one of" in issue.message for issue in issues)
