from __future__ import annotations

import textwrap

from harness.context import ProjectContext, SpriteContext
from harness.dsl import DSLError, DSLErrors, transpile
from harness.dsl.envelope import normalize


def source(text: str) -> str:
    return textwrap.dedent(text).strip("\n")


def diagnostics(text: str, context: ProjectContext | None = None) -> list[DSLError]:
    try:
        transpile(source(text), context)
    except DSLErrors as exc:
        return exc.errors
    except DSLError as exc:
        return [exc]
    raise AssertionError("expected a diagnostic")


def assert_diagnostic(
    text: str,
    needle: str,
    line: int | None,
    context: ProjectContext | None = None,
) -> DSLError:
    errors = diagnostics(text, context)
    matches = [
        error
        for error in errors
        if needle in error.format() and error.line == line
    ]
    assert matches, [error.format() for error in errors]
    return matches[0]


def body(source_text: str) -> str:
    return (
        '@on_flag(target="Sprite1")\n'
        "def f():\n"
        + textwrap.indent(textwrap.dedent(source_text).strip("\n"), "    ")
        + "\n"
    )


# -- syntax and fences ---------------------------------------------------


def test_syntax_error_is_one_line_precise_diagnostic():
    error = assert_diagnostic(
        "def broken(:", "Python syntax error", 1
    )
    assert "Reply with one fenced python block" in error.format()


def test_prose_before_a_fence_is_recovered():
    reply = (
        "Here is the code:\n"
        "```python\n"
        '@on_flag(target="S")\n'
        "def f():\n"
        "    move(1)\n"
        "```"
    )

    changeset = transpile(reply)
    assert changeset.changes[0].body[0].to_dict() == {
        "op": "move",
        "args": {"steps": 1},
    }

    normalized = normalize(reply)
    assert normalized.fatal is None
    assert normalized.module_text == (
        '@on_flag(target="S")\ndef f():\n    move(1)'
    )
    assert (
        "skipped 1 line of prose before the opening fence"
        in normalized.actions
    )


def test_empty_module_is_reported():
    errors = diagnostics("")
    assert len(errors) == 1
    assert errors[0].line is None
    assert "change set is empty" in errors[0].format()


# -- module-level rejections --------------------------------------------


def test_import_is_rejected():
    assert_diagnostic(
        "import os", "imports are not part of the dialect", 1
    )


def test_module_assignment_is_rejected():
    assert_diagnostic(
        "score = 0",
        "assignments at module level are not part of the dialect",
        1,
    )


def test_module_call_with_non_literal_argument_is_rejected():
    assert_diagnostic(
        'create_variable("x", initial=1 + 2)',
        "module-level change calls take literal values only",
        1,
    )


def test_variable_name_colliding_with_a_function_is_rejected():
    assert_diagnostic(
        'create_variable("move")',
        "collides with a dialect function",
        1,
    )


def test_class_is_rejected():
    assert_diagnostic(
        "class Foo:\n    pass", "classes are not part of the dialect", 1
    )


# -- def / decorator rejections -----------------------------------------


def test_def_without_a_decorator_is_rejected():
    assert_diagnostic(
        "def f():\n    move(1)",
        "a script def needs exactly one event decorator",
        1,
    )


def test_def_with_two_decorators_is_rejected():
    assert_diagnostic(
        '@on_flag(target="S")\n@on_click(target="S")\ndef f():\n    move(1)',
        "a script def needs exactly one event decorator",
        3,
    )


def test_unknown_decorator_is_rejected():
    assert_diagnostic(
        '@on_wave(target="S")\ndef f():\n    move(1)',
        "unknown decorator @on_wave",
        1,
    )


def test_def_arguments_are_rejected():
    assert_diagnostic(
        '@on_flag(target="S")\ndef f(x):\n    move(1)',
        "script defs take no arguments",
        2,
    )


def test_return_is_rejected():
    assert_diagnostic(
        body("return 1"),
        "scripts are not functions",
        3,
    )


def test_nested_def_is_rejected():
    assert_diagnostic(
        body("def helper():\n    move(1)"),
        "helper functions are not supported",
        3,
    )


def test_lambda_is_rejected():
    assert_diagnostic(
        body("x = lambda: 1"),
        "lambdas are not part of the dialect",
        3,
    )


def test_annotations_are_rejected():
    assert_diagnostic(
        '@on_flag(target="S")\ndef f() -> None:\n    move(1)',
        "annotations are not part of the dialect",
        2,
    )


# -- statement whitelist -------------------------------------------------


def test_subscript_is_rejected():
    assert_diagnostic(
        body("queue[0]"),
        "indexing is not part of the dialect",
        3,
    )


def test_attribute_is_rejected():
    assert_diagnostic(
        body("self.x"),
        "attribute access is not part of the dialect",
        3,
    )


def test_comprehension_is_rejected():
    assert_diagnostic(
        body("items = [i for i in range(3)]"),
        "comprehensions are not part of the dialect",
        3,
    )


def test_fstring_is_rejected():
    assert_diagnostic(
        body('say(f"hi {x}")'),
        "f-strings are not part of the dialect",
        3,
    )


def test_try_is_rejected():
    assert_diagnostic(
        body("try:\n    move(1)\nexcept:\n    move(2)"),
        "try/except is not part of the dialect",
        3,
    )


def test_break_is_rejected():
    assert_diagnostic(
        body("while True:\n    break"),
        "Scratch has no loop break/continue",
        4,
    )


def test_continue_is_rejected():
    assert_diagnostic(
        body("while True:\n    continue"),
        "Scratch has no loop break/continue",
        4,
    )


def test_pass_is_rejected():
    assert_diagnostic(
        body("pass"),
        "empty bodies are not allowed",
        3,
    )


# -- expression rejections -----------------------------------------------


def test_unary_minus_on_a_computed_value_is_still_rejected_for_bitwise():
    assert_diagnostic(
        body("move(~score)"),
        "Scratch has no bitwise operators",
        3,
    )


def test_chained_comparison_is_rejected():
    assert_diagnostic(
        body("if 1 < 2 < 3:\n    move(1)"),
        "chained comparisons are not supported",
        3,
    )


def test_in_comparison_is_rejected():
    assert_diagnostic(
        body('if "a" in "abc":\n    move(1)'),
        "'in'/'is' comparisons are not part of the dialect",
        3,
    )


def test_true_condition_is_rejected():
    assert_diagnostic(
        body("if True:\n    move(1)"),
        "True/False have no Scratch block",
        3,
    )


def test_none_is_rejected():
    assert_diagnostic(
        body("move(None)"),
        "None is not part of the dialect",
        3,
    )


def test_bool_literal_argument_is_rejected():
    assert_diagnostic(
        body("move(True)"),
        "True/False have no Scratch block",
        3,
    )


def test_command_used_as_a_value_is_rejected():
    assert_diagnostic(
        body("move(10) + 1"),
        "move() is a command block",
        3,
    )


def test_reporter_statement_is_rejected():
    assert_diagnostic(
        body("x_position()"),
        "x_position() is a reporter",
        3,
    )


def test_control_flow_call_is_rejected():
    assert_diagnostic(
        body("repeat(4)"),
        "do not call repeat() directly",
        3,
    )


def test_unknown_function_is_rejected():
    assert_diagnostic(
        body("jump(10)"),
        "unknown function jump()",
        3,
    )


def test_python_builtin_is_also_an_unknown_function():
    assert_diagnostic(
        body("say(min(5, 6))"),
        "unknown function min()",
        3,
    )


def test_starred_arguments_are_rejected():
    assert_diagnostic(
        body("move(*args)"),
        "dialect calls take plain positional or keyword arguments only",
        3,
    )


def test_power_operator_is_rejected():
    assert_diagnostic(
        body("move(2 ** 8)"),
        "Scratch has no power/floor-div/bit operator",
        3,
    )


def test_ambiguous_plus_is_rejected():
    assert_diagnostic(
        body("say(first + last)"),
        "'+' between two computed values is ambiguous",
        3,
    )


def test_ambiguous_plus_names_both_explicit_rewrites():
    error = assert_diagnostic(
        body("say(first + last)"),
        "'+' between two computed values is ambiguous",
        3,
    )

    assert "first + last" in error.message
    assert "add(first, last)" in error.message
    assert "join(first, last)" in error.message


def test_source_quoting_puts_the_offending_line_before_the_message():
    error = assert_diagnostic(
        body("say(first + last)"),
        "'+' between two computed values is ambiguous",
        3,
    )

    quoted = error.format(include_source=True)
    assert quoted.startswith("line 3: say(first + last)")
    assert "\n  '+' between two computed values is ambiguous" in quoted
    # The default stays byte-identical for lint, tests and old callers.
    assert error.format().startswith(
        "line 3: '+' between two computed values is ambiguous"
    )


def test_a_bare_variable_is_not_a_boolean_condition():
    assert_diagnostic(
        body("if score:\n    move(1)"),
        "condition must be a boolean reporter",
        3,
    )


def test_bare_function_name_suggests_a_call():
    assert_diagnostic(
        body("move"),
        "did you mean move(...)?",
        3,
    )


# -- call vocabulary -----------------------------------------------------


def test_unknown_keyword_is_rejected():
    assert_diagnostic(
        body("move(distance=1)"),
        "move() takes steps, not 'distance'",
        3,
    )


def test_keyword_collision_is_rejected():
    assert_diagnostic(
        body("move(1, steps=2)"),
        "move() got multiple values for argument 'steps'",
        3,
    )
    assert_diagnostic(
        body("move(steps=1, steps=2)"),
        "move() got multiple values for argument 'steps'",
        3,
    )


def test_missing_argument_is_rejected():
    assert_diagnostic(
        body("move()"),
        "move() needs 1 argument(s): steps",
        3,
    )


def test_too_many_positional_arguments_are_rejected():
    assert_diagnostic(
        body("move(1, 2)"),
        "move() needs 1 argument(s): steps",
        3,
    )


def test_bad_menu_value_is_rejected():
    assert_diagnostic(
        body('point_towards("up")'),
        "point_towards() argument 'target' must be one of",
        3,
    )


# -- loop and augmented-assignment rejections ----------------------------


def test_loop_variable_must_be_underscore():
    assert_diagnostic(
        body("for i in range(4):\n    move(1)"),
        "the loop variable must be _",
        3,
    )


def test_three_argument_range_is_rejected():
    assert_diagnostic(
        body("for _ in range(1, 5, 2):\n    move(1)"),
        "range(a, b) is not supported yet",
        3,
    )


def test_unsupported_augmented_operator_keeps_a_hint():
    error = assert_diagnostic(
        body("score //= 2"),
        "augmented assignment with '//' is not supported",
        3,
    )
    assert error.hint is not None
    assert "set_var" in error.hint


# -- symbol gate ---------------------------------------------------------


def test_unknown_variable_with_context_is_rejected():
    assert_diagnostic(
        body("hp += 1"),
        "unknown variable 'hp'",
        3,
        ProjectContext.demo(),
    )


def test_cross_sprite_local_with_context_is_rejected():
    context = ProjectContext.demo()
    context.sprites["Crab1"] = SpriteContext(name="Crab1", variables=["hp"])
    assert_diagnostic(
        body("hp += 1"),
        "'hp' is a local variable of sprite 'Crab1'",
        3,
        context,
    )


def test_names_created_earlier_in_the_module_pass_the_gate():
    text = source(
        """
        create_variable("score")
        @on_flag(target="Sprite1")
        def hud():
            score += 1
        """
    )
    changeset = transpile(text, ProjectContext.demo())
    assert changeset.changes[1].body[0].op == "change_var"


# -- collection ----------------------------------------------------------


def test_collects_at_most_ten_diagnostics():
    text = body(
        "\n".join(f"jump{index}(1)" for index in range(12))
    )
    errors = diagnostics(text)
    assert len(errors) == 10
    assert all(error.line is not None for error in errors)
