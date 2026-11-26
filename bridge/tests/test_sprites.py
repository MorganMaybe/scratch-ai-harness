from __future__ import annotations

from harness.block_ir import ChangeSet, IRError
from harness.changeset import compile_changeset
from harness.context import ProjectContext, ScriptSummary, SpriteContext
from harness.protocol import Sym, parse_literal
from harness.validator import validate_changeset


def changeset(changes: list[dict]) -> ChangeSet:
    return ChangeSet.from_dict({"summary": "scene test", "changes": changes})


def test_create_sprite_then_script_in_one_changeset():
    data = changeset(
        [
            {
                "action": "create_sprite",
                "name": "Bat",
                "costumes": [{"library": "Animals/bat1-a.png"}],
                "x": 10,
                "y": -20,
                "size": 80,
                "rotation_style": "left-right",
            },
            {
                "action": "add_script",
                "target": "Bat",
                "label": "spin",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "turn_right", "args": {"degrees": 15}}],
            },
        ]
    )
    assert validate_changeset(data, ProjectContext.demo()) == []
    compiled = compile_changeset(data, ProjectContext.demo())
    assert [change.action for change in compiled.changes] == ["create_sprite", "add_script"]
    message = parse_literal(compiled.apply_literal(5))
    create = message[2][0]
    assert create[0] == Sym("createSprite")
    assert create[1] == "Bat"
    assert create[2] == [["Animals/bat1-a.png", "bat1-a"]]
    assert create[3:8] == [10, -20, 90, 80, True]
    assert create[8] == "left-right"
    assert message[2][1][0] == Sym("add")
    assert message[2][1][2] == "Bat"


def test_create_sprite_limits_and_defaults():
    data = changeset(
        [
            {
                "action": "create_sprite",
                "name": "Bat",
                "costumes": [
                    {"library": "Animals/bat1-a.png"},
                    {"library": "Animals/bat1-b.png", "name": "wing"},
                ],
            }
        ]
    )
    assert validate_changeset(data, ProjectContext.demo()) == []
    compiled = compile_changeset(data, ProjectContext.demo())
    assert compiled.changes[0].costumes == [
        ["Animals/bat1-a.png", "bat1-a"],
        ["Animals/bat1-b.png", "wing"],
    ]
    assert compiled.changes[0].x == 0
    assert compiled.changes[0].direction == 90
    assert compiled.changes[0].size == 100
    assert compiled.changes[0].visible is True
    assert compiled.changes[0].rotation_style == "all around"


def test_create_sprite_rejects_unknown_media_with_suggestions():
    data = changeset(
        [
            {
                "action": "create_sprite",
                "name": "Bat",
                "costumes": [{"library": "Animals/bat1-z.png"}],
            }
        ]
    )
    issues = validate_changeset(data, ProjectContext.demo())
    text = "\n".join(str(issue) for issue in issues)
    assert "unknown costume" in text
    assert "near matches" in text


def test_create_sprite_rejects_stage_reserved_and_duplicate_names():
    for name in ("Stage", "stage", "Sprite1", "sprite1", "mouse-pointer"):
        data = changeset(
            [
                {
                    "action": "create_sprite",
                    "name": name,
                    "costumes": [{"library": "Animals/bat1-a.png"}],
                }
            ]
        )
        assert validate_changeset(data, ProjectContext.demo()), name


def test_create_sprite_needs_one_to_three_costumes():
    data = changeset(
        [{"action": "create_sprite", "name": "Bat", "costumes": []}]
    )
    assert validate_changeset(data, ProjectContext.demo())
    too_many = changeset(
        [
            {
                "action": "create_sprite",
                "name": "Bat",
                "costumes": [
                    {"library": "Animals/bat1-a.png"},
                    {"library": "Animals/bat1-b.png"},
                    {"library": "Animals/bat2-a.png"},
                    {"library": "Animals/bat2-b.png"},
                ],
            }
        ]
    )
    assert validate_changeset(too_many, ProjectContext.demo())


def test_delete_sprite_allows_scriptless_user_sprite():
    # The demo Sprite1 is a user sprite with no scripts, so it is deletable.
    data = changeset([{"action": "delete_sprite", "target": "Sprite1"}])
    assert validate_changeset(data, ProjectContext.demo()) == []


def test_delete_sprite_rejects_user_sprite_with_scripts():
    scripted = ProjectContext.demo()
    scripted.sprites["Sprite1"].scripts = [
        ScriptSummary(
            script_id="user-1",
            target="Sprite1",
            label="user script",
            hat="when_flag_clicked",
            block_count=3,
            owned=False,
        )
    ]
    data = changeset([{"action": "delete_sprite", "target": "Sprite1"}])
    assert any(
        "user sprite" in str(issue) for issue in validate_changeset(data, scripted)
    )


def test_duplicate_sprite_is_ai_sprite_only():
    user_duplicate = changeset(
        [{"action": "duplicate_sprite", "target": "Sprite1", "name": "Cat2"}]
    )
    assert any(
        "user sprite" in str(issue)
        for issue in validate_changeset(user_duplicate, ProjectContext.demo())
    )


def test_delete_and_duplicate_ai_sprites_in_one_changeset():
    data = changeset(
        [
            {
                "action": "create_sprite",
                "name": "Bat",
                "costumes": [{"library": "Animals/bat1-a.png"}],
            },
            {"action": "duplicate_sprite", "target": "Bat", "name": "Bat2"},
            {
                "action": "add_script",
                "target": "Bat2",
                "label": "copy_script",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "move", "args": {"steps": 5}}],
            },
            {"action": "delete_sprite", "target": "Bat"},
        ]
    )
    assert validate_changeset(data, ProjectContext.demo()) == []
    compiled = compile_changeset(data, ProjectContext.demo())
    message = parse_literal(compiled.apply_literal(1))
    assert message[2][1] == [Sym("duplicateSprite"), "Bat", "Bat2"]
    assert message[2][3] == [Sym("deleteSprite"), "Bat"]


def test_adding_costume_and_backdrop():
    data = changeset(
        [
            {"action": "add_costume", "target": "Sprite1", "library": "Animals/bat1-b.png"},
            {"action": "set_backdrop", "library": "Space/stars.gif"},
            {
                "action": "add_script",
                "target": "Stage",
                "label": "backdrop",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "switch_backdrop", "args": {"backdrop": "stars"}}],
            },
        ]
    )
    assert validate_changeset(data, ProjectContext.demo()) == []
    compiled = compile_changeset(data, ProjectContext.demo())
    message = parse_literal(compiled.apply_literal(2))
    assert message[2][0] == [Sym("addCostume"), "Sprite1", "Animals/bat1-b.png", "bat1-b", False]
    assert message[2][1] == [Sym("setBackdrop"), "Space/stars.gif", "stars", True]


def test_stage_code_cannot_move_but_can_switch_backdrop():
    move = changeset(
        [
            {
                "action": "add_script",
                "target": "Stage",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "move", "args": {"steps": 10}}],
            }
        ]
    )
    assert any("cannot be used" in str(issue) for issue in validate_changeset(move, ProjectContext.demo()))

    backdrop = changeset(
        [
            {
                "action": "add_script",
                "target": "Stage",
                "hat": {"op": "when_flag_clicked"},
                "body": [{"op": "switch_backdrop", "args": {"backdrop": "background1"}}],
            }
        ]
    )
    # The demo stage has no costumes, so the name is only checked when known.
    assert validate_changeset(backdrop, ProjectContext.demo()) == []


def test_set_sprite_updates_working_context():
    data = changeset(
        [
            {
                "action": "create_sprite",
                "name": "Bat",
                "costumes": [{"library": "Animals/bat1-a.png"}],
            },
            {
                "action": "set_sprite",
                "target": "Bat",
                "x": 1,
                "y": 2,
                "direction": 45,
                "size": 50,
                "visible": False,
                "rotation_style": "don't rotate",
            },
        ]
    )
    assert validate_changeset(data, ProjectContext.demo()) == []
    compiled = compile_changeset(data, ProjectContext.demo())
    message = parse_literal(compiled.apply_literal(3))
    assert message[2][1] == [Sym("setSprite"), "Bat", 1, 2, 45, 50, False, "don't rotate"]


def test_rotation_style_is_validated_at_parse_time():
    try:
        ChangeSet.from_dict(
            {
                "summary": "bad",
                "changes": [
                    {
                        "action": "create_sprite",
                        "name": "Bat",
                        "costumes": [{"library": "Animals/bat1-a.png"}],
                        "rotation_style": "sideways",
                    }
                ],
            }
        )
    except IRError as exc:
        assert "rotation_style" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected IRError")


def test_context_accepts_optional_sprite_properties():
    raw = [
        "Bat",
        [
            ["Stage", True, [], [], ["background1"], [], []],
            [
                "Bat",
                False,
                [],
                [],
                ["bat1-a"],
                [],
                [],
                [10, -20, 45, 80, False, "leftRight", True, 1],
            ],
        ],
    ]
    context = ProjectContext.from_literal(raw)
    sprite = context.sprites["Bat"]
    assert sprite.x == 10
    assert sprite.y == -20
    assert sprite.direction == 45
    assert sprite.size == 80
    assert sprite.visible is False
    assert sprite.rotation_style == "left-right"
    assert sprite.ai_owned is True
    assert sprite.costume_index == 1


def test_seven_element_context_still_works():
    context = ProjectContext.from_literal(
        ["Sprite1", [["Sprite1", False, [], [], [], [], []]]]
    )
    sprite = context.sprites["Sprite1"]
    assert sprite.ai_owned is False
    assert sprite.rotation_style == "all around"


def test_create_sprite_from_preset():
    data = changeset([{"action": "create_sprite", "name": "Dog", "preset": "Dog Puppy"}])
    assert validate_changeset(data, ProjectContext.demo()) == []
    compiled = compile_changeset(data, ProjectContext.demo())
    create = compiled.changes[0]
    assert create.action == "create_sprite"
    assert len(create.costumes) > 3  # presets may exceed the manual 1-3 limit
    library, name, cx, cy = create.costumes[0]
    assert library == "Animals/dog-puppy-right.png"
    assert name
    assert cx > 0 and cy > 0
    assert "Created sprite 'Dog'" in compiled.chat_summary()
    message = parse_literal(compiled.apply_literal(11))
    assert message[2][0][0] == Sym("createSprite")
    assert message[2][0][1] == "Dog"
    assert len(message[2][0][2][0]) == 4


def test_preset_defaults_can_be_overridden():
    data = changeset(
        [
            {
                "action": "create_sprite",
                "name": "Dog",
                "preset": "Dog Puppy",
                "x": 10,
                "y": 20,
                "size": 50,
                "rotation_style": "left-right",
            }
        ]
    )
    assert validate_changeset(data, ProjectContext.demo()) == []
    create = compile_changeset(data, ProjectContext.demo()).changes[0]
    assert create.x == 10
    assert create.y == 20
    assert create.size == 50
    assert create.rotation_style == "left-right"


def test_unknown_preset_and_mixed_costumes_are_rejected():
    unknown = changeset(
        [{"action": "create_sprite", "name": "Dog", "preset": "Doggy"}]
    )
    text = "\n".join(str(issue) for issue in validate_changeset(unknown, ProjectContext.demo()))
    assert "unknown sprite preset" in text
    assert "near matches" in text

    mixed = changeset(
        [
            {
                "action": "create_sprite",
                "name": "Dog",
                "preset": "Dog Puppy",
                "costumes": [{"library": "Animals/bat1-a.png"}],
            }
        ]
    )
    assert any(
        "either 'preset' or 'costumes'" in str(issue)
        for issue in validate_changeset(mixed, ProjectContext.demo())
    )
