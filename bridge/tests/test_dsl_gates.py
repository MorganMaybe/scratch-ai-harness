"""Parse-time context and media gates for the Scratch-Python dialect."""

from __future__ import annotations

import json
import os
import textwrap
from contextlib import contextmanager

import pytest

from harness.agent import Agent
from harness.audit import AuditSettings, AuditStore
from harness.context import ProjectContext, SpriteContext
from harness.dsl import DSLError, DSLErrors, lint, transpile
from harness.media import reset_default_library
from harness.providers.base import ModelReply


def source(text: str) -> str:
    return textwrap.dedent(text).strip("\n")


def diagnostics(
    text: str, context: ProjectContext | None = None
) -> list[DSLError]:
    try:
        transpile(source(text), context)
    except DSLErrors as exc:
        return exc.errors
    except DSLError as exc:
        return [exc]
    raise AssertionError("expected a diagnostic")


def only(text: str, context: ProjectContext | None = None) -> DSLError:
    errors = diagnostics(text, context)
    assert len(errors) == 1, [error.format() for error in errors]
    return errors[0]


def context() -> ProjectContext:
    return ProjectContext(
        target="Sprite1",
        sprites={
            "Stage": SpriteContext(
                name="Stage", is_stage=True, costumes=["stars", "grass1"]
            ),
            "Sprite1": SpriteContext(
                name="Sprite1",
                costumes=["costume1", "costume2"],
                sounds=["pop"],
            ),
            "Ground": SpriteContext(name="Ground", costumes=["rock"]),
        },
    )


# -- script target gate --------------------------------------------------


def test_unknown_decorator_target_is_rejected_with_valid_targets():
    error = only(
        '@on_flag(target="Pipe")\ndef f():\n    move(1)', context()
    )

    assert error.line == 1
    assert error.message == "@on_flag() target 'Pipe' does not exist yet"
    assert "create it first with create_sprite('Pipe', ...)" in error.hint
    assert "stage" in error.hint.casefold()
    assert "sprite1" in error.hint.casefold()


def test_decorator_target_created_earlier_in_the_module_passes():
    text = source(
        """
        create_sprite("Bird", costumes=["Animals/bat1-a.png"])
        @on_flag(target="Bird")
        def fly():
            move(1)
        """
    )

    changeset = transpile(text, context())

    assert changeset.changes[1].target == "Bird"


def test_decorator_target_stage_is_case_insensitive():
    text = '@on_flag(target="stage")\ndef f():\n    stop_all()'

    change = transpile(text, context()).changes[0]

    assert change.target == "Stage"


def test_decorator_target_is_not_gated_without_a_context():
    text = '@on_flag(target="Pipe")\ndef f():\n    move(1)'

    change = transpile(text).changes[0]

    assert change.target == "Pipe"


# -- module-call target gate ---------------------------------------------


def test_sprite_scoped_variable_needs_a_target():
    error = only('create_variable("hp", scope="sprite")', context())

    assert error.line == 1
    assert error.message == (
        "create_variable() with scope='sprite' needs target='SpriteName'"
    )
    assert "valid sprite targets" in error.hint


def test_sprite_scoped_variable_unknown_target_is_rejected():
    error = only(
        'create_variable("hp", scope="sprite", target="Pipe")', context()
    )

    assert error.message == "create_variable() target 'Pipe' does not exist yet"
    assert "stage" in error.hint.casefold()


def test_sprite_scoped_variable_with_a_valid_target_passes():
    change = transpile(
        'create_variable("hp", scope="sprite", target="Ground")', context()
    ).changes[0]

    assert change.target == "Ground"


@pytest.mark.parametrize(
    "call,message",
    [
        ('set_sprite("Pipe", x=1)', "set_sprite() target 'Pipe' does not exist yet"),
        (
            'duplicate_sprite("Pipe", name="Pipe2")',
            "duplicate_sprite() target 'Pipe' does not exist yet",
        ),
        ('delete_sprite("Pipe")', "delete_sprite() target 'Pipe' does not exist yet"),
        (
            'add_costume("Pipe", library="Animals/bat1-a.png")',
            "add_costume() target 'Pipe' does not exist yet",
        ),
    ],
)
def test_module_change_target_must_exist(call: str, message: str):
    error = only(call, context())

    assert error.line == 1
    assert error.message == message


def test_module_change_target_created_earlier_passes():
    text = source(
        """
        create_sprite("Bird", costumes=["Animals/bat1-a.png"])
        set_sprite("Bird", x=10)
        """
    )

    changes = transpile(text, context()).changes

    assert changes[1].action == "set_sprite"
    assert changes[1].target == "Bird"


def test_add_costume_stage_is_still_allowed():
    change = transpile(
        'add_costume("Stage", library="Space/stars.gif")', context()
    ).changes[0]

    assert change.target == "Stage"


def test_module_change_target_is_not_gated_without_a_context():
    change = transpile('set_sprite("Pipe", x=1)').changes[0]

    assert change.target == "Pipe"


# -- create name gate ----------------------------------------------------

def named_context() -> ProjectContext:
    ctx = context()
    ctx.stage_variables.extend(["angle", "tilt"])
    ctx.stage_lists.append("queue")
    ctx.sprites["Ground"].variables.append("hp")
    ctx.sprites["Ground"].lists.append("ground_queue")
    return ctx


def test_existing_global_variable_is_rejected_with_a_reuse_hint():
    error = only('create_variable("angle")', named_context())

    assert error.line == 1
    assert error.message == "variable 'angle' already exists; reuse it"
    assert "remove this create line" in error.hint
    assert "name = value" in error.hint


def test_variable_created_earlier_in_the_module_is_rejected():
    text = source(
        """
        create_variable("spin")
        create_variable("spin")
        """
    )

    error = only(text, named_context())

    assert error.line == 2
    assert error.message == "variable 'spin' already exists; reuse it"


def test_sprite_scoped_variable_that_shadows_a_global_is_rejected():
    error = only(
        'create_variable("angle", scope="sprite", target="Ground")',
        named_context(),
    )

    assert error.message == "variable 'angle' already exists; reuse it"


def test_existing_sprite_scoped_variable_is_rejected():
    error = only(
        'create_variable("hp", scope="sprite", target="Ground")',
        named_context(),
    )

    assert error.message == "variable 'hp' already exists; reuse it"


def test_existing_global_list_is_rejected():
    error = only('create_list("queue")', named_context())

    assert error.line == 1
    assert error.message == "list 'queue' already exists; reuse it"
    assert "remove this create line" in error.hint


def test_list_created_earlier_in_the_module_is_rejected():
    text = source(
        """
        create_list("seen", items=[])
        create_list("seen", items=[])
        """
    )

    error = only(text, named_context())

    assert error.line == 2
    assert error.message == "list 'seen' already exists; reuse it"


def test_variables_and_lists_keep_separate_name_namespaces():
    text = source(
        """
        create_list("angle", items=[])
        create_variable("queue")
        """
    )

    changes = transpile(text, named_context()).changes

    assert [change.action for change in changes] == [
        "create_list",
        "create_variable",
    ]


@pytest.mark.parametrize(
    "name", ["Stage", "stage", "Edge", "edge", "Mouse-Pointer"]
)
def test_reserved_sprite_name_is_rejected(name: str):
    error = only(
        f'create_sprite("{name}", costumes=["Animals/bat1-a.png"])',
        context(),
    )

    assert error.line == 1
    if name.casefold() == "stage":
        assert error.message == "a sprite cannot be named 'Stage'"
    else:
        assert error.message == (
            f"sprite name {name!r} is a Scratch menu value"
        )
    assert "choose a different sprite name" in error.hint


def test_existing_sprite_name_is_rejected_case_insensitively():
    error = only(
        'create_sprite("ground", costumes=["Animals/bat1-a.png"])',
        context(),
    )

    assert error.message == "sprite 'ground' already exists"
    assert "set_sprite" in error.hint


def test_sprite_created_earlier_in_the_module_cannot_be_recreated():
    text = source(
        """
        create_sprite("Bird", costumes=["Animals/bat1-a.png"])
        create_sprite("bird", costumes=["Animals/bat1-a.png"])
        """
    )

    error = only(text, context())

    assert error.line == 2
    assert error.message == "sprite 'bird' already exists"


def test_duplicate_sprite_new_name_is_gated():
    error = only('duplicate_sprite("Ground", name="Edge")', context())

    assert error.message == "sprite name 'Edge' is a Scratch menu value"


def test_sprite_name_gate_runs_without_a_context():
    error = only('create_sprite("Edge", costumes=["Animals/bat1-a.png"])')

    assert error.line == 1
    assert error.message == "sprite name 'Edge' is a Scratch menu value"


# -- costume / sound / backdrop name gate --------------------------------


def test_unknown_costume_is_rejected_with_the_target_costumes():
    text = source(
        """
        @on_flag(target="Sprite1")
        def f():
            switch_costume("hat")
        """
    )

    error = only(text, context())

    assert error.line == 3
    assert error.message == "unknown costume 'hat' for 'Sprite1'"
    assert "costume1" in error.hint
    assert "costume2" in error.hint


def test_costume_added_earlier_in_the_module_passes():
    text = source(
        """
        add_costume("Sprite1", library="Animals/bat1-a.png")
        @on_flag(target="Sprite1")
        def f():
            switch_costume("bat1-a")
        """
    )

    changes = transpile(text, context()).changes

    assert changes[1].body[0].args["costume"] == "bat1-a"


def test_costume_of_a_sprite_created_earlier_passes():
    text = source(
        """
        create_sprite("Bird", costumes=["Animals/bat1-a.png"])
        @on_flag(target="Bird")
        def f():
            switch_costume("bat1-a")
        """
    )

    changes = transpile(text, context()).changes

    assert changes[1].body[0].args["costume"] == "bat1-a"


def test_unknown_sound_is_rejected_with_the_target_sounds():
    text = source(
        """
        @on_flag(target="Sprite1")
        def f():
            play_sound("boing")
        """
    )

    error = only(text, context())

    assert error.line == 3
    assert error.message == "unknown sound 'boing' for 'Sprite1'"
    assert "pop" in error.hint


def test_unknown_backdrop_is_rejected_with_the_stage_backdrops():
    text = source(
        """
        @on_flag(target="Stage")
        def f():
            switch_backdrop("moon")
        """
    )

    error = only(text, context())

    assert error.message == "unknown backdrop 'moon'"
    assert "stars" in error.hint
    assert "grass1" in error.hint


def test_backdrop_added_earlier_in_the_module_passes():
    text = source(
        """
        set_backdrop("Space/stars.gif")
        @on_flag(target="Stage")
        def f():
            switch_backdrop("stars")
        """
    )

    changes = transpile(text, context()).changes

    assert changes[1].body[0].args["backdrop"] == "stars"


def test_command_names_are_not_gated_without_a_context():
    text = '@on_flag(target="Sprite1")\ndef f():\n    switch_costume("hat")'

    assert transpile(text).changes[0].body[0].args["costume"] == "hat"


def test_command_names_are_not_gated_when_the_context_knows_none():
    sparse = ProjectContext(
        target="Sprite1",
        sprites={
            "Stage": SpriteContext(name="Stage", is_stage=True),
            "Sprite1": SpriteContext(name="Sprite1"),
        },
    )
    text = '@on_flag(target="Sprite1")\ndef f():\n    switch_costume("hat")'

    assert transpile(text, sparse).changes[0].body[0].args["costume"] == "hat"


# -- media library gate ---------------------------------------------------


def test_unknown_costume_library_path_is_rejected_with_near_matches():
    error = only(
        'create_sprite("Bird", costumes=["Animals/zzzz-bat.png"])', context()
    )

    assert error.line == 1
    assert "unknown costume 'Animals/zzzz-bat.png'" in error.message
    assert "near matches" in error.hint
    assert "bat" in error.hint.casefold()


def test_unknown_backdrop_library_path_is_rejected():
    error = only('set_backdrop("Space/zzzz-stars.gif")', context())

    assert "unknown backdrop 'Space/zzzz-stars.gif'" in error.message
    assert "stars.gif" in error.hint


def test_unknown_add_costume_library_path_is_rejected():
    error = only(
        'add_costume("Sprite1", library="Animals/zzzz-bat.png")', context()
    )

    assert "unknown costume 'Animals/zzzz-bat.png'" in error.message
    assert error.hint


def test_unknown_preset_is_rejected_with_near_matches():
    error = only('create_sprite("Bird", preset="Dog Pupy")', context())

    assert "unknown sprite preset 'Dog Pupy'" in error.message
    assert "Dog Puppy" in error.hint


def test_known_preset_passes():
    change = transpile(
        'create_sprite("Dog", preset="Dog Puppy")', context()
    ).changes[0]

    assert change.preset == "Dog Puppy"


def test_media_gate_runs_without_a_context():
    error = only(
        'create_sprite("Bird", costumes=["Animals/zzzz-bat.png"])'
    )

    assert "unknown costume" in error.message


@contextmanager
def media_root(path):
    """Point the cached default library at ``path`` for one call."""
    previous = os.environ.get("HARNESS_MEDIA_ROOT")
    os.environ["HARNESS_MEDIA_ROOT"] = str(path)
    reset_default_library()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("HARNESS_MEDIA_ROOT", None)
        else:
            os.environ["HARNESS_MEDIA_ROOT"] = previous
        reset_default_library()


def test_empty_media_library_skips_the_gate(tmp_path):
    with media_root(tmp_path / "empty"):
        changeset = transpile(
            'create_sprite("Bird", costumes=["Animals/zzzz.png"])',
            context(),
        )

    assert changeset.changes[0].name == "Bird"


# -- lint and the repair loop --------------------------------------------


def test_lint_reports_the_gate_with_its_line_number():
    text = '@on_flag(target="Pipe")\ndef f():\n    move(1)'

    reported = lint(text, context())

    assert len(reported) == 1
    assert reported[0].startswith("line 1: ")
    assert "target 'Pipe' does not exist yet" in reported[0]


SQUARE_DSL = '''@on_flag(target="Sprite1", label="draw_square")
def draw_square():
    pen_clear()
    pen_down()
    for _ in range(4):
        move(100)
        turn_right(90)
    pen_up()
'''


class _Replies:
    name = "dsl-fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


def _raw(text: str, **kwargs) -> ModelReply:
    values = {
        "data": {},
        "raw_text": text,
        "model": "fake",
        "finish_reason": "stop",
    }
    values.update(kwargs)
    return ModelReply(**values)


def test_gate_failure_is_repaired_and_audited_with_a_line(monkeypatch, tmp_path):
    monkeypatch.setenv("HARNESS_GENERATOR", "dsl")
    monkeypatch.setenv("HARNESS_PROMPT_BUDGET", "400000")
    bad = '@on_flag(target="Pipe")\ndef f():\n    move(1)\n'
    provider = _Replies([_raw(bad), _raw(SQUARE_DSL)])
    store = AuditStore(
        AuditSettings(mode="full", directory=tmp_path / "audit", keep=10)
    )
    turn = store.start_turn(
        request_id=91,
        prompt="Move a step.",
        target="Sprite1",
        context=None,
        profile="mock",
        model="mock",
        base_url="",
        turn_budget_s=1.0,
        context_literal=None,
        generator="dsl",
    )
    agent = Agent(provider, context(), max_repairs=1, audit=turn)

    result = agent.handle("Move a step.", request_id=91)

    assert result.attempts == 2
    assert result.compiled.changes[0].label == "draw_square"
    errors = json.loads(
        (turn.root / "attempts/01/dsl.json").read_text(encoding="utf-8")
    )
    assert errors
    assert errors[0].startswith("line 1: ")
    assert "target 'Pipe' does not exist yet" in errors[0]
    repair = provider.requests[1].user
    assert "target 'Pipe' does not exist yet" in repair
