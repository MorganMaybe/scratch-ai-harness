"""Reply-envelope normalization matrix.

One group per row of the envelope rule matrix in ``harness/dsl/envelope.py``,
plus the cross-cutting invariants: normalization never raises, every fatal
carries a line/hint/source, and a fatal reply never hands back module text.
Assertions are byte-level on purpose: the normalizer must recover the module
verbatim and never rewrite, invent or silently drop module-shaped lines.

A no-fence reply is always parsed as-is, even when it is obvious prose:
valid-but-forbidden Python (``import``, ``class``) has to reach the
transpiler's precise dialect diagnostics.  Prose-only replies are named by
``prose_diagnostic``, which ``parse.py`` consults only after ``ast`` has
already rejected the text.
"""

from __future__ import annotations

import pytest

from harness.dsl import DSLError, DSLErrors, transpile
from harness.dsl.envelope import (
    ENVELOPE_PREFIX,
    NormalizedReply,
    normalize,
    prose_diagnostic,
)

MODULE = (
    '@on_flag(target="Sprite1")\n'
    "def go():\n"
    "    move(10)\n"
    '    say("done")'
)


def fenced(content: str, tag: str = "python") -> str:
    return f"```{tag}\n{content}\n```"


def clean(raw: str) -> NormalizedReply:
    """Normalize a reply that the matrix says must recover."""
    result = normalize(raw)
    assert result.fatal is None, result.fatal.format()
    return result


def fatal_of(raw: str) -> DSLError:
    """Normalize a reply that the matrix says must be fatal."""
    result = normalize(raw)
    assert result.fatal is not None, "expected a fatal envelope diagnostic"
    return result.fatal


def assert_fatal(raw: str, message: str, line: int) -> DSLError:
    result = normalize(raw)
    assert result.fatal is not None, "expected a fatal envelope diagnostic"
    # Callers must never use module text from a fatal reply.
    assert result.module_text == ""
    error = result.fatal
    assert error.message == ENVELOPE_PREFIX + message
    assert error.line == line
    assert error.hint
    assert error.source
    return error


def transpile_errors(text: str) -> list[DSLError]:
    try:
        transpile(text)
    except DSLErrors as exc:
        return list(exc.errors)
    except DSLError as exc:
        return [exc]
    raise AssertionError("expected a diagnostic")


def test_envelope_prefix_is_the_documented_marker():
    assert ENVELOPE_PREFIX == "reply envelope: "


# -- one fenced block, nothing else ---------------------------------------


def test_single_fenced_block_is_returned_verbatim():
    result = clean(fenced(MODULE))

    assert result.module_text == MODULE
    assert result.actions == ()
    assert result.fatal is None


def test_single_fenced_block_preserves_blank_lines_and_indentation():
    module = (
        '@on_flag(target="Sprite1")\n'
        "def go():\n"
        "    move(10)\n"
        "\n"
        "    if x_position() > 0:\n"
        '        say("positive")'
    )

    assert clean(fenced(module)).module_text == module


@pytest.mark.parametrize(
    "raw",
    [
        fenced(MODULE),
        fenced(MODULE) + "\n",
        fenced(MODULE) + "\n\n",
    ],
)
def test_single_fenced_block_ignores_boundary_newlines(raw):
    result = clean(raw)

    assert result.module_text == MODULE
    assert result.actions == ()


# -- no fence at all ------------------------------------------------------


def test_reply_without_a_fence_is_parsed_as_is():
    raw = 'summary("x")\nnotes("n")'
    result = clean(raw)

    assert result.module_text == raw
    assert result.actions == ()


def test_reply_without_a_fence_is_stripped():
    raw = '\n\n  summary("x")\n\n'
    result = clean(raw)

    assert result.module_text == 'summary("x")'
    assert result.actions == ()


def test_reply_without_a_fence_keeps_prose_around_a_module_line():
    # Row 2: without a fence the whole raw reply is kept, prose included --
    # the envelope layer must not silently edit it.
    raw = "Intro paragraph.\nmove(10)"

    assert clean(raw).module_text == raw


# -- prose before the opening fence ---------------------------------------


def test_one_prose_line_before_the_fence_is_skipped():
    raw = f'Here is the module:\n{fenced(MODULE)}'
    result = clean(raw)

    assert result.module_text == MODULE
    assert result.actions == (
        "skipped 1 line of prose before the opening fence",
    )


def test_two_prose_lines_before_the_fence_are_skipped():
    raw = f'Here is the module.\nIt moves ten steps:\n{fenced("move(10)")}'
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == (
        "skipped 2 lines of prose before the opening fence",
    )


def test_blank_lines_before_the_fence_are_not_prose():
    raw = "\n\n" + fenced("move(10)")
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == ()


def test_prose_before_the_fence_does_not_change_the_module():
    raw = f'Here it is:\n\n{fenced(MODULE)}'

    assert clean(raw).module_text == MODULE


# -- module-shaped code before the opening fence --------------------------


def test_call_before_the_opening_fence_is_fatal():
    raw = "move(10)\n" + fenced("move(20)")

    assert_fatal(
        raw,
        "code before the opening fence - move it inside the module.",
        1,
    )


def test_assignment_before_the_opening_fence_is_fatal():
    # Line 2 is the assignment; prose on line 1 must not hide it.
    raw = "Here is the module:\nscore = 0\n" + fenced("move(10)")
    error = assert_fatal(
        raw,
        "code before the opening fence - move it inside the module.",
        2,
    )

    assert error.format(include_source=True).startswith(
        f"line 2: score = 0\n  {ENVELOPE_PREFIX}"
    )


def test_first_module_line_before_the_fence_wins():
    raw = "move(1)\nmove(2)\n" + fenced("move(3)")

    assert_fatal(
        raw,
        "code before the opening fence - move it inside the module.",
        1,
    )


def test_a_def_before_the_fence_is_fatal():
    raw = "def helper():\n    move(1)\n" + fenced("move(10)")

    assert_fatal(
        raw,
        "code before the opening fence - move it inside the module.",
        1,
    )


def test_a_decorator_before_the_fence_is_fatal():
    raw = '@on_flag(target="S")\n' + fenced("move(10)")

    assert_fatal(
        raw,
        "code before the opening fence - move it inside the module.",
        1,
    )


# -- missing closing fence ------------------------------------------------


def test_missing_closing_fence_treats_eof_as_the_close():
    raw = "```python\nmove(10)\n"
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == (
        "treated the end of reply as the closing fence",
    )


def test_missing_closing_fence_trims_trailing_blank_lines():
    raw = "```python\nmove(10)\n\n\n"
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == (
        "treated the end of reply as the closing fence",
    )


# -- summary()/notes() after the closing fence ----------------------------


def test_summary_after_the_close_is_appended():
    raw = fenced("move(10)") + '\nsummary("x")'
    result = clean(raw)

    assert result.module_text == 'move(10)\nsummary("x")'
    assert result.actions == (
        "appended summary(...) from after the closing fence",
    )


def test_notes_after_the_close_is_appended():
    raw = fenced("move(10)") + '\nnotes("n")'
    result = clean(raw)

    assert result.module_text == 'move(10)\nnotes("n")'
    assert result.actions == (
        "appended notes(...) from after the closing fence",
    )


def test_summary_and_notes_are_appended_in_reply_order():
    raw = fenced("move(10)") + '\nsummary("x")\nnotes("n")'
    result = clean(raw)

    assert result.module_text == 'move(10)\nsummary("x")\nnotes("n")'
    assert result.actions == (
        "appended summary(...) from after the closing fence",
        "appended notes(...) from after the closing fence",
    )


def test_metadata_after_blank_lines_is_still_appended():
    raw = fenced("move(10)") + '\n\n\nsummary("x")'
    result = clean(raw)

    assert result.module_text == 'move(10)\nsummary("x")'
    assert result.actions == (
        "appended summary(...) from after the closing fence",
    )


def test_wrapped_metadata_call_is_collected_whole():
    wrapped = 'summary(\n    "frame 1",\n    "frame 2",\n)'
    raw = fenced("move(10)") + "\n" + wrapped
    result = clean(raw)

    assert result.module_text == "move(10)\n" + wrapped
    assert result.actions == (
        "appended summary(...) from after the closing fence",
    )


def test_metadata_and_prose_after_the_close_are_both_recovered():
    raw = fenced("move(10)") + '\nthanks for the help\nsummary("x")'
    result = clean(raw)

    assert result.module_text == 'move(10)\nsummary("x")'
    # Both recoveries are recorded; their relative order is not part of the
    # matrix, only that neither is lost.
    assert set(result.actions) == {
        "appended summary(...) from after the closing fence",
        "ignored 1 line of prose after the closing fence",
    }


# -- other prose after the closing fence ----------------------------------


def test_one_prose_line_after_the_close_is_ignored():
    raw = fenced("move(10)") + "\nThanks!"
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == (
        "ignored 1 line of prose after the closing fence",
    )


def test_two_prose_lines_after_the_close_are_ignored():
    raw = fenced("move(10)") + "\nThanks!\nHope it helps."
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == (
        "ignored 2 lines of prose after the closing fence",
    )


def test_prose_after_the_close_does_not_change_the_module():
    raw = fenced(MODULE) + "\nThat should do it."

    assert clean(raw).module_text == MODULE


# -- a second fenced code block -------------------------------------------


def test_second_fenced_block_after_the_close_is_fatal():
    raw = fenced("move(10)") + "\n" + fenced("move(20)")

    assert_fatal(
        raw,
        "two fenced code blocks - the reply must contain exactly one module.",
        4,
    )


def test_second_tagged_block_after_the_close_is_fatal():
    raw = fenced("move(10)") + "\n```py\nmove(20)\n```"

    assert_fatal(
        raw,
        "two fenced code blocks - the reply must contain exactly one module.",
        4,
    )


def test_second_block_line_number_skips_the_closing_fence():
    # Raw lines: 1 fence, 2 module, 3 close, 4 blank, 5 second fence.
    raw = "```python\nmove(10)\n```\n\n```python\nmove(20)\n```"

    assert_fatal(
        raw,
        "two fenced code blocks - the reply must contain exactly one module.",
        5,
    )


def test_second_block_wins_when_it_comes_before_stray_code():
    # The after-close region is scanned left to right, so the earlier
    # offending line decides the diagnostic.
    raw = (
        "```python\nmove(10)\n```\n"
        "```python\nmove(20)\n```\n"
        "move(30)"
    )

    assert_fatal(
        raw,
        "two fenced code blocks - the reply must contain exactly one module.",
        4,
    )


def test_stray_code_wins_when_it_comes_before_the_second_block():
    raw = (
        "```python\nmove(10)\n```\n"
        "move(30)\n"
        "```python\nmove(20)\n```"
    )

    assert_fatal(
        raw,
        "code after the closing fence - move it inside the module.",
        4,
    )


# -- module-shaped code after the closing fence ---------------------------


def test_call_after_the_close_is_fatal():
    raw = fenced("move(10)") + "\nmove(20)"

    assert_fatal(
        raw,
        "code after the closing fence - move it inside the module.",
        4,
    )


def test_decorated_def_after_the_close_is_fatal():
    raw = fenced("move(10)") + '\n@on_flag(target="S")\ndef f():\n    move(1)'

    assert_fatal(
        raw,
        "code after the closing fence - move it inside the module.",
        4,
    )


def test_assignment_after_the_close_is_fatal():
    raw = fenced("move(10)") + "\nscore = 0"

    assert_fatal(
        raw,
        "code after the closing fence - move it inside the module.",
        4,
    )


def test_after_close_line_number_counts_blanks_and_prose():
    # Raw lines: 1 fence, 2 module, 3 close, 4 blank, 5 prose, 6 code.
    raw = "```python\nmove(10)\n```\n\nthanks\nmove(20)"

    assert_fatal(
        raw,
        "code after the closing fence - move it inside the module.",
        6,
    )


# -- prose-only reply, no fence -------------------------------------------


def test_prose_only_reply_without_a_fence_is_parsed_as_is():
    raw = "not module\nalso prose"
    result = clean(raw)

    # No-fence replies are "kept": prose detection needs ast's rejection
    # first, so that valid-but-forbidden Python keeps its dialect diagnostic.
    assert result.module_text == raw
    assert result.actions == ()


def test_prose_only_reply_is_not_an_envelope_fatal():
    result = clean("Sorry, I cannot do that today.")

    assert result.module_text == "Sorry, I cannot do that today."
    assert result.fatal is None


def test_transpile_names_a_prose_only_reply():
    errors = transpile_errors("not module\nalso prose")

    assert len(errors) == 1
    assert errors[0].message == (
        ENVELOPE_PREFIX + "the reply contains no module - only prose."
    )
    assert errors[0].line == 1


@pytest.mark.parametrize(
    "raw, needle",
    [
        ("import os", "imports are not part of the dialect"),
        ("class Foo:\n    pass", "classes are not part of the dialect"),
    ],
)
def test_forbidden_but_valid_python_keeps_its_dialect_diagnostic(raw, needle):
    # These replies are not prose: ast parses them, so the dialect layer
    # must report the precise reason, never the envelope prose diagnostic.
    assert clean(raw).module_text == raw

    errors = transpile_errors(raw)
    assert any(needle in error.message for error in errors)
    assert not any(
        error.message.startswith(ENVELOPE_PREFIX) for error in errors
    )


# -- prose_diagnostic (post-ast classifier) -------------------------------


def test_prose_diagnostic_names_a_prose_reply():
    text = "Sorry, I cannot do that today."
    error = prose_diagnostic(text)

    assert error is not None
    assert error.message == (
        ENVELOPE_PREFIX + "the reply contains no module - only prose."
    )
    assert error.line == 1
    assert error.hint
    assert error.source == text


def test_prose_diagnostic_line_is_the_first_non_blank_line():
    error = prose_diagnostic("\n\nnot module\nalso prose")

    assert error is not None
    assert error.line == 3


def test_prose_diagnostic_format_quotes_the_first_line():
    text = "\n\nnot module\nalso prose"
    error = prose_diagnostic(text)

    assert error is not None
    assert error.format(include_source=True).startswith(
        f"line 3: not module\n  {ENVELOPE_PREFIX}"
    )
    # The quote comes from the source the line number indexes.
    assert error.source == text


@pytest.mark.parametrize(
    "text",
    [
        'summary("x")',
        'notes("n")',
        "move(10)",
        '@on_flag(target="Sprite1")',
        "def f():\n    pass",
        "score = 0",
        "Sorry:\nmove(10)",
    ],
)
def test_prose_diagnostic_returns_none_for_module_shaped_text(text):
    assert prose_diagnostic(text) is None


@pytest.mark.parametrize("text", ["", "   ", "\n\n\n", None])
def test_prose_diagnostic_returns_none_for_empty_text(text):
    assert prose_diagnostic(text) is None


# -- fence tag and envelope variants --------------------------------------


@pytest.mark.parametrize(
    "open_fence, close_fence",
    [
        ("```python", "```"),
        ("```py", "```"),
        ("````python", "````"),
        ("~~~python", "~~~"),
        ("~~~", "~~~"),
        ("```", "```"),
    ],
)
def test_fence_variants_open_and_close_the_same_block(open_fence, close_fence):
    raw = f"{open_fence}\nmove(10)\n{close_fence}"
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == ()


@pytest.mark.parametrize("indent", [1, 2, 3])
def test_fences_indented_up_to_three_spaces(indent):
    pad = " " * indent
    raw = f"{pad}```python\nmove(10)\n{pad}```"
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == ()


def test_indented_opening_and_flush_closing_fence():
    raw = "   ```python\nmove(10)\n```"

    assert clean(raw).module_text == "move(10)"


def test_doubled_opening_fence_is_dropped():
    raw = "```\n```python\nmove(10)\n```"
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == ("dropped a doubled opening fence",)


def test_doubled_opening_fence_marker_is_not_prose():
    # The spurious first marker must not also be counted as one prose line.
    raw = "Here:\n```\n```python\nmove(10)\n```"
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == (
        "dropped a doubled opening fence",
        "skipped 1 line of prose before the opening fence",
    )


@pytest.mark.parametrize(
    "close_fence",
    ["```.", "```,", "```:", "```!", '```"', "```   "],
)
def test_closing_fence_with_trailing_punctuation_or_spaces(close_fence):
    raw = f"```python\nmove(10)\n{close_fence}"
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == ()


def test_leading_bom_is_stripped():
    raw = "\ufeff" + fenced(MODULE)
    result = clean(raw)

    assert result.module_text == MODULE
    assert result.actions == ("stripped a byte-order mark",)


@pytest.mark.parametrize("newline", ["\r\n", "\r"])
def test_crlf_line_endings_are_normalized(newline):
    raw = (
        "```python"
        + newline
        + '@on_flag(target="S")'
        + newline
        + "def go():"
        + newline
        + "    move(10)"
        + newline
        + "```"
    )
    result = clean(raw)

    expected = '@on_flag(target="S")\ndef go():\n    move(10)'
    assert result.module_text == expected
    assert result.actions == ("normalized CRLF line endings",)


def test_bom_and_crlf_actions_are_both_recorded():
    raw = "\ufeffHere it is:\r\n" + fenced("move(10)").replace("\n", "\r\n")
    result = clean(raw)

    assert result.module_text == "move(10)"
    assert result.actions == (
        "stripped a byte-order mark",
        "normalized CRLF line endings",
        "skipped 1 line of prose before the opening fence",
    )


# -- cross-cutting invariants ---------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "\n\n\n",
        "\t",
        "\ufeff",
        "\r\n",
        "```",
        "```python",
        "~~~",
        "```python\n",
        "not a module",
        "a\nb\nc",
        "```python\nmove(10)\n```\n```python\nmove(20)\n```",
        "```python\nmove(10)\n```\nmove(20)",
    ],
)
def test_normalize_never_raises(raw):
    result = normalize(raw)

    assert isinstance(result, NormalizedReply)
    assert isinstance(result.module_text, str)
    assert isinstance(result.actions, tuple)


def test_none_is_treated_as_an_empty_reply():
    result = normalize(None)  # type: ignore[arg-type]

    assert result.module_text == ""
    assert result.actions == ()
    assert result.fatal is None


FATAL_SAMPLES = [
    "move(10)\n" + fenced("move(20)"),
    fenced("move(10)") + "\nmove(20)",
    fenced("move(10)") + "\n" + fenced("move(20)"),
    "\ufeff" + fenced("move(10)").replace("\n", "\r\n") + "\r\nmove(20)",
]


@pytest.mark.parametrize("raw", FATAL_SAMPLES)
def test_every_fatal_carries_prefix_line_hint_and_source(raw):
    result = normalize(raw)

    assert result.module_text == ""
    error = result.fatal
    assert error is not None
    assert error.message.startswith(ENVELOPE_PREFIX)
    assert error.line is not None
    assert error.hint
    assert error.source


@pytest.mark.parametrize(
    "raw, line, snippet",
    [
        ("Here:\nscore = 0\n" + fenced("move(10)"), 2, "score = 0"),
        (fenced("move(10)") + "\nmove(20)", 4, "move(20)"),
        (fenced("move(10)") + "\n\n" + fenced("move(20)"), 5, "```python"),
    ],
)
def test_fatal_format_quotes_the_offending_line(raw, line, snippet):
    error = fatal_of(raw)

    assert error.format(include_source=True).startswith(
        f"line {line}: {snippet}\n  {ENVELOPE_PREFIX}"
    )


def test_fatal_source_is_the_normalized_reply():
    # The source must match the text the line number indexes: BOM stripped
    # and CRLF folded to LF.
    raw = "\ufeff" + fenced("move(10)").replace("\n", "\r\n") + "\r\nmove(20)"
    error = fatal_of(raw)

    assert error.source == "```python\nmove(10)\n```\nmove(20)"
    assert error.line == 4


def test_actions_are_a_tuple():
    result = clean(fenced("move(10)") + "\nThanks!")

    assert isinstance(result.actions, tuple)
    assert result.actions == (
        "ignored 1 line of prose after the closing fence",
    )


def test_fence_indented_eight_spaces_is_content():
    # A marker too deep to be a fence must stay inside the module verbatim.
    raw = "```python\nmove(10)\n        ```\nmove(20)\n```"
    result = clean(raw)

    assert result.module_text == "move(10)\n        ```\nmove(20)"
    assert result.actions == ()
