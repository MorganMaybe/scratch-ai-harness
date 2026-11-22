from __future__ import annotations

from harness.block_ir import Change, ChangeSet, Script
from harness.changeset import compile_changeset
from harness.context import ProjectContext, ScriptSummary, SpriteContext
from harness.validator import validate_changeset, validate_script


def square_script() -> Script:
    return Script.from_dict(
        {
            "target": "Sprite1",
            "hat": {"op": "when_flag_clicked"},
            "body": [
                {"op": "pen_clear"},
                {"op": "pen_down"},
                {
                    "op": "repeat",
                    "args": {"count": 4},
                    "body": [
                        {"op": "move", "args": {"steps": 100}},
                        {"op": "turn_right", "args": {"degrees": 90}},
                    ],
                },
                {"op": "pen_up"},
            ],
        }
    )


def test_valid_square():
    assert validate_script(square_script(), ProjectContext.demo()) == []


def test_unknown_block():
    script = Script.from_dict(
        {
            "target": "Sprite1",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "move_to", "args": {}}],
        }
    )
    issues = validate_script(script, ProjectContext.demo())
    assert any("unknown block" in issue.message for issue in issues)


def test_wrong_argument_type():
    script = Script.from_dict(
        {
            "target": "Sprite1",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "move", "args": {"steps": "ten"}}],
        }
    )
    issues = validate_script(script, ProjectContext.demo())
    assert any("expected a number" in issue.message for issue in issues)


def test_unknown_variable():
    script = Script.from_dict(
        {
            "target": "Sprite1",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "set_var", "args": {"name": "score", "value": 0}}],
        }
    )
    issues = validate_script(script, ProjectContext.demo())
    assert any("unknown variable" in issue.message for issue in issues)


def test_pen_blocks_are_sprite_only_except_clear():
    script = Script.from_dict(
        {
            "target": "Stage",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "pen_down"}],
        }
    )
    issues = validate_script(script, ProjectContext.demo())
    assert any("pen_down" in issue.message and "Stage" in issue.message for issue in issues)

    clear = Script.from_dict(
        {
            "target": "Stage",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "pen_clear"}],
        }
    )
    assert validate_script(clear, ProjectContext.demo()) == []


def test_stage_backdrop_blocks_validate_and_compile():
    context = ProjectContext.demo()
    context.stage_variables.append("bg")
    script = Script.from_dict(
        {
            "target": "Stage",
            "hat": {"op": "when_flag_clicked"},
            "body": [
                {"op": "switch_backdrop", "args": {"backdrop": "background1"}},
                {"op": "next_backdrop"},
                {
                    "op": "set_var",
                    "args": {
                        "name": "bg",
                        "value": {"op": "backdrop_number"},
                    },
                },
            ],
        }
    )
    assert validate_script(script, context) == []


def test_show_and_hide_variable_require_an_existing_variable():
    context = ProjectContext.demo()
    context.stage_variables.append("score")
    changeset = ChangeSet.from_dict(
        {
            "summary": "hud",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Stage",
                    "label": "hud",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [
                        {"op": "show_variable", "args": {"name": "score"}},
                        {"op": "hide_variable", "args": {"name": "score"}},
                    ],
                }
            ],
        }
    )
    assert validate_changeset(changeset, context) == []

    missing = ChangeSet.from_dict(
        {
            "summary": "hud",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Stage",
                    "label": "hud",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "show_variable", "args": {"name": "missing"}}],
                }
            ],
        }
    )
    issues = validate_changeset(missing, ProjectContext.demo())
    assert any("unknown variable" in issue.message for issue in issues)


def test_stage_cannot_move():
    script = Script.from_dict(
        {
            "target": "Stage",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "move", "args": {"steps": 10}}],
        }
    )
    issues = validate_script(script, ProjectContext.demo())
    assert any("cannot be used" in issue.message for issue in issues)


def test_if_condition_must_be_boolean():
    script = Script.from_dict(
        {
            "target": "Sprite1",
            "hat": {"op": "when_flag_clicked"},
            "body": [
                {
                    "op": "if",
                    "args": {"condition": {"op": "add", "args": {"a": 1, "b": 2}}},
                    "body": [],
                }
            ],
        }
    )
    issues = validate_script(script, ProjectContext.demo())
    assert any("boolean" in issue.message for issue in issues)


def test_menu_rejects_reporter():
    script = Script.from_dict(
        {
            "target": "Sprite1",
            "hat": {"op": "when_flag_clicked"},
            "body": [
                {
                    "op": "switch_costume",
                    "args": {"costume": {"op": "get_var", "args": {"name": "x"}}},
                }
            ],
        }
    )
    issues = validate_script(script, ProjectContext.demo())
    assert any("literal" in issue.message for issue in issues)


def test_add_script_changeset():
    changeset = ChangeSet.from_dict(
        {
            "summary": "Add a square.",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "draw_square",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "pen_clear"}],
                }
            ],
        }
    )
    assert validate_changeset(changeset, ProjectContext.demo()) == []


def test_replace_unknown_script():
    changeset = ChangeSet.from_dict(
        {
            "summary": "Update.",
            "changes": [
                {
                    "action": "replace_script",
                    "script_id": "ai-9",
                    "target": "Sprite1",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "pen_clear"}],
                }
            ],
        }
    )
    issues = validate_changeset(changeset, ProjectContext.demo())
    assert any("unknown script_id" in issue.message for issue in issues)


def test_create_duplicate_variable():
    context = ProjectContext.demo()
    context.stage_variables.append("score")
    changeset = ChangeSet.from_dict(
        {
            "summary": "Add score.",
            "changes": [{"action": "create_variable", "name": "score", "scope": "global", "initial": 0}],
        }
    )
    issues = validate_changeset(changeset, context)
    assert any("already exists" in issue.message for issue in issues)


def test_create_variable_then_use_in_same_changeset():
    changeset = ChangeSet.from_dict(
        {
            "summary": "Create and use a score variable.",
            "changes": [
                {"action": "create_variable", "name": "score", "scope": "global", "initial": 0},
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "score_setup",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "set_var", "args": {"name": "score", "value": 0}}],
                },
            ],
        }
    )
    assert validate_changeset(changeset, ProjectContext.demo()) == []


def test_replace_uses_registry_target():
    context = ProjectContext.demo()
    registry = {
        "ai-1": ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label="draw_square",
            hat="when_flag_clicked",
            block_count=5,
        )
    }
    changeset = ChangeSet.from_dict(
        {
            "summary": "Update.",
            "changes": [
                {
                    "action": "replace_script",
                    "script_id": "ai-1",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "pen_up"}],
                }
            ],
        }
    )
    issues = validate_changeset(changeset, context, registry)
    assert issues == []
    assert changeset.changes[0].target == "Sprite1"


def _sprite_target_body(op: str, target: str) -> list[dict]:
    """Body JSON that exercises one sprite-target op (menus need literals)."""
    if op == "touching":
        return [
            {
                "op": "if",
                "args": {"condition": {"op": op, "args": {"target": target}}},
                "body": [],
            }
        ]
    if op in {"distance_to", "attribute_of"}:
        reporter = {"op": op, "args": {"target": target}}
        if op == "attribute_of":
            reporter["args"]["attribute"] = "x position"
        return [{"op": "say", "args": {"text": reporter}}]
    return [{"op": op, "args": {"target": target}}]


def _sprite_target_script(op: str, target: str) -> Script:
    return Script.from_dict(
        {
            "target": "Sprite1",
            "hat": {"op": "when_flag_clicked"},
            "body": _sprite_target_body(op, target),
        }
    )


def test_sprite_names_are_valid_targets_for_sprite_sensing_and_motion():
    context = ProjectContext.demo()
    context.sprites["Player"] = SpriteContext(name="Player")

    for op in ("touching", "distance_to", "goto_sprite", "point_towards", "attribute_of"):
        issues = validate_script(_sprite_target_script(op, "Player"), context)
        assert issues == [], (op, issues)


def test_unknown_sprite_target_is_rejected():
    issues = validate_script(
        _sprite_target_script("touching", "Ghost"), ProjectContext.demo()
    )
    assert any("Ghost" in issue.message for issue in issues)


def test_sprite_target_must_exist_before_the_script():
    late = ChangeSet.from_dict(
        {
            "summary": "late sprite",
            "changes": [
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "chase",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [
                        {"op": "goto_sprite", "args": {"target": "Player"}}
                    ],
                },
                {
                    "action": "create_sprite",
                    "name": "Player",
                    "costumes": [{"library": "Animals/bat1-a.png"}],
                },
            ],
        }
    )
    issues = validate_changeset(late, ProjectContext.demo())
    assert any("Player" in issue.message for issue in issues)

    early = ChangeSet.from_dict(
        {
            "summary": "early sprite",
            "changes": [
                {
                    "action": "create_sprite",
                    "name": "Player",
                    "costumes": [{"library": "Animals/bat1-a.png"}],
                },
                {
                    "action": "add_script",
                    "target": "Sprite1",
                    "label": "chase",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [
                        {"op": "goto_sprite", "args": {"target": "Player"}}
                    ],
                },
            ],
        }
    )
    assert validate_changeset(early, ProjectContext.demo()) == []


def test_sprite_created_earlier_is_a_valid_target_for_every_sprite_target_op():
    # HANDOFF.md §11.8: the menu extension must see sprites created by earlier
    # changes in the same change set, not just those in the base context.
    for op in ("point_towards", "touching", "distance_to", "attribute_of", "goto_sprite"):
        changeset = ChangeSet.from_dict(
            {
                "summary": f"{op} a sprite created earlier",
                "changes": [
                    {
                        "action": "create_sprite",
                        "name": "Player",
                        "costumes": [{"library": "Animals/bat1-a.png"}],
                    },
                    {
                        "action": "add_script",
                        "target": "Sprite1",
                        "label": "chase",
                        "hat": {"op": "when_flag_clicked"},
                        "body": _sprite_target_body(op, "Player"),
                    },
                ],
            }
        )
        assert validate_changeset(changeset, ProjectContext.demo()) == [], op


def test_sprite_created_later_is_not_a_valid_target():
    for op in ("point_towards", "touching", "distance_to", "attribute_of"):
        changeset = ChangeSet.from_dict(
            {
                "summary": f"{op} too early",
                "changes": [
                    {
                        "action": "add_script",
                        "target": "Sprite1",
                        "label": "chase",
                        "hat": {"op": "when_flag_clicked"},
                        "body": _sprite_target_body(op, "Player"),
                    },
                    {
                        "action": "create_sprite",
                        "name": "Player",
                        "costumes": [{"library": "Animals/bat1-a.png"}],
                    },
                ],
            }
        )
        issues = validate_changeset(changeset, ProjectContext.demo())
        assert any("unknown sprite 'Player'" in issue.message for issue in issues), op


def test_unknown_sprite_target_message_explains_the_top_down_rule():
    for op in ("point_towards", "touching", "distance_to", "attribute_of", "goto_sprite"):
        issues = validate_script(
            _sprite_target_script(op, "Ghost"), ProjectContext.demo()
        )
        assert len(issues) == 1, (op, issues)
        assert issues[0].message.startswith(
            "unknown sprite 'Ghost'; this menu accepts a sprite that exists at this "
            "point in the change set (create it earlier), or one of "
        ), op


def test_generic_menu_message_is_unchanged():
    script = Script.from_dict(
        {
            "target": "Sprite1",
            "hat": {"op": "when_flag_clicked"},
            "body": [{"op": "set_rotation_style", "args": {"style": "sideways"}}],
        }
    )
    issues = validate_script(script, ProjectContext.demo())
    assert any(
        issue.message == "expected one of all around, left-right, don't rotate, got 'sideways'"
        for issue in issues
    )


def test_sprite_target_compiles_into_the_tuple():
    context = ProjectContext.demo()
    context.sprites["Player"] = SpriteContext(name="Player")
    script = _sprite_target_script("goto_sprite", "Player")
    changeset = ChangeSet(summary="chase", changes=[Change(
        action="add_script",
        target="Sprite1",
        label="chase",
        hat=script.hat,
        body=script.body,
    )])

    compiled = compile_changeset(changeset, context, context.registry())

    assert "'Player'" in compiled.apply_literal(1)
    assert "gotoSpriteOrMouse:" in compiled.apply_literal(1)


def test_create_sprite_registers_after_an_unrelated_earlier_failure():
    """Registration is per change, not per turn.

    The gate used to read the turn-wide issue list, so one bad earlier change
    (here a sprite-scoped variable with no real target) silently skipped every
    later create_sprite.  Scripts for those sprites then failed with a false
    unknown target, which also inflated the failing-change count past the
    fragment repair limit.
    """
    changeset = ChangeSet.from_dict(
        {
            "summary": "Create Player despite an unrelated failure.",
            "changes": [
                {
                    "action": "create_variable",
                    "name": "hp",
                    "scope": "sprite",
                    "target": "Ghost",
                },
                {
                    "action": "create_sprite",
                    "name": "Player",
                    "costumes": [{"library": "Scenery/rock.png"}],
                },
                {
                    "action": "add_script",
                    "target": "Player",
                    "label": "walk",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "move", "args": {"steps": 10}}],
                },
            ],
        }
    )
    issues = validate_changeset(changeset, ProjectContext.demo())
    assert [issue.path for issue in issues] == ["changes[0]"]
    assert "valid target" in issues[0].message
    assert not any("unknown target" in issue.message for issue in issues)


def test_create_sprite_with_its_own_issue_is_not_registered():
    """A sprite whose own media is invalid must still be withheld.

    This guards the other half of the fix: the new gate must not become
    "always register", or a failed create_sprite would validate later scripts
    against a sprite that the compiler will never create.
    """
    changeset = ChangeSet.from_dict(
        {
            "summary": "Create Player with a missing costume.",
            "changes": [
                {
                    "action": "create_sprite",
                    "name": "Player",
                    "costumes": [{"library": "Things/zzz-nope.png"}],
                },
                {
                    "action": "add_script",
                    "target": "Player",
                    "label": "walk",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "move", "args": {"steps": 10}}],
                },
            ],
        }
    )
    issues = validate_changeset(changeset, ProjectContext.demo())
    assert len(issues) == 2, issues
    assert issues[0].path == "changes[0].costumes[0].library"
    assert issues[1].path == "changes[1]"
    assert "unknown target sprite/stage: 'Player'" in issues[1].message

