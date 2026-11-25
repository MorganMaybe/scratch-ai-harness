from __future__ import annotations

import os
import re
from typing import Any

from . import known_media
from .catalog import catalog_summary
from .context import ProjectContext, ScriptSummary
from .history import (
    MIN_VERBATIM_TURNS,
    ONE_LINER_LIMIT,
    VERBATIM_TURNS,
    HistoryStats,
    render_history,
)

#: Environment variable that overrides the default prompt budget.
PROMPT_BUDGET_ENV = "HARNESS_PROMPT_BUDGET"

#: Rough character budget used when the environment does not say otherwise.
#: The system prompt carries the curated media index (up to
#: ``GROUPED_MEDIA_CHARS``) alongside the full context appendix, so the
#: default matches the live runner's 90000 (the stable reference measures
#: ~80k with the full media index; per-turn context is appended outside it).
DEFAULT_PROMPT_BUDGET = 90000

#: Always-on prop paths, kept outside the grouped index so trimming cannot
#: hide them. Shared with the budget fallback that drops them when the
#: instructions alone overflow.
VERIFIED_PROP_PATHS = """- Verified prop paths, also valid when the grouped index below is trimmed:
  Geometry/line.png: flat red bar; direction 0 = vertical pipe.
  Letters/Block/a.png: tile block (Block a..z).
  GameItems/paddle.png: pong paddle; UI/scoreboard.gif: HUD.
  Never use Players/fantasy1-a.png or other character art as pipes,
  platforms or geometry; it is a cartoon creature.
"""

#: Optional known-good tier rendered next to ``VERIFIED_PROP_PATHS``. It is
#: mined data (``known_media.json``), so it is absent until live turns exist.
KNOWN_GOOD_HEADER = "Known-good assets (verified in live use):"
KNOWN_GOOD_LIMIT = 24
KNOWN_GOOD_MAX_CHARS = 1100
KNOWN_GOOD_WIDTH = 100


def _wrap_known(
    prefix: str, items: list[str], width: int = KNOWN_GOOD_WIDTH
) -> list[str]:
    """One indented comma list, wrapped on ``", "`` boundaries."""
    lines: list[str] = []
    current = prefix
    for item in items:
        if current == prefix:
            current += item
        elif len(current) + 2 + len(item) > width:
            lines.append(current + ",")
            current = "    " + item
        else:
            current += ", " + item
    lines.append(current)
    return lines


def _render_known(entries: list[tuple[str, str, int]]) -> str:
    if not entries:
        return ""
    lines = [KNOWN_GOOD_HEADER]
    for kind, title in (("costume", "costumes"), ("backdrop", "backdrops")):
        items = [library for library, entry_kind, _ in entries if entry_kind == kind]
        if items:
            lines.extend(_wrap_known(f"  {title}: ", items))
    if len(lines) == 1:
        return ""
    return "\n".join(lines) + "\n"


def _select_known(count: int) -> list[tuple[str, str, int]]:
    """Top ``count`` entries overall, with a small floor for each media kind.

    Backdrops are used far less often than costumes, so a strictly top-N list
    would be all costumes and hide the kind the model gets wrong most
    (``set_backdrop``). When a kind is absent, its top three entries replace
    the lowest-ranked selections; the block stays within ``count`` entries.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        return []
    entries = known_media.ranked_media(max(count, 64))
    selected = entries[:count]
    for kind in ("costume", "backdrop"):
        if any(entry[1] == kind for entry in selected):
            continue
        extra = [entry for entry in entries if entry[1] == kind][:3]
        if extra:
            selected = selected[: max(0, count - len(extra))] + extra
    return selected


def known_good_media_block(
    count: int = KNOWN_GOOD_LIMIT,
    max_chars: int = KNOWN_GOOD_MAX_CHARS,
) -> str:
    """The compact known-good tier, or ``""`` when there is no mined data.

    Paths are ranked by successful live use (the miner canonicalizes them
    against the installed library), and the least-used entries are dropped if
    the block would exceed ``max_chars``.
    """
    entries = _select_known(count)
    block = _render_known(entries)
    while entries and len(block) > max_chars:
        entries = entries[:-1]
        block = _render_known(entries)
    return block


SYSTEM_PROMPT = """You are the AI programming agent inside Scratch 1.4.

You turn a natural-language request into a change set of Scratch blocks for the
current project. The user runs it, then asks you to change it again.

Return ONLY a JSON object. To load detail missing from the end of this
prompt, return
{"load_context": ["name"]} or {"load_sprite": ["SpriteName"]} plus "reason";
the bridge resends it. Otherwise use this change-set shape:
{
  "summary": "one short sentence describing the change",
  "changes": [
    {
      "action": "add_script" | "replace_script" | "delete_script" | "create_variable"
              | "create_sprite" | "delete_sprite" | "duplicate_sprite"
              | "add_costume" | "set_backdrop" | "set_sprite",
      "script_id": "existing id (required for replace/delete; optional for add)",
      "target": "sprite or Stage name",
      "label": "short human name for the script",
      "hat": { "op": "when_flag_clicked" },
      "body": [ { "op": "...", "args": { ... }, "body": [ ... ] } ],
      "name": "variable name, new sprite name, or costume name",
      "scope": "global" | "sprite",
      "initial": 0,
      "costumes": [ { "library": "Animals/bat1-a.png", "name": "bat1-a" } ],
      "x": 0, "y": 0, "direction": 90, "size": 100,
      "visible": true, "rotation_style": "all around" | "left-right" | "don't rotate",
      "library": "Space/stars.gif",
      "select": true
    }
  ],
  "notes": "optional short note"
}

A block is:
{ "op": "op_name", "args": { "arg_name": literal_or_reporter }, "body": [ ... ] }
Use "then" and "else" instead of "body" for if_else.
A reporter argument is a nested block, for example:
{ "op": "move", "args": { "steps": { "op": "add", "args": { "a": 10, "b": { "op": "x_position" } } } } }

Rules:
- Use only the block ops in the catalog below. Never invent blocks.
- Use only sprites, variables, costumes, and sounds in the project context.
- If you need a new variable, add a create_variable change before using it.
- On revisions, use included bodies; never guess a body.
- Change an AI-owned script with replace_script + script_id; use add_script only
  for new behavior or a different hat.
- On a rebuild, delete obsolete AI-created sprites with delete_sprite; do not
  create Bat2.
- User scripts are read-only; add a new script alongside them.
- Do not give add_script a script_id; the harness assigns one.
- Prefer ~80 blocks. If a scene cannot fit, return a coherent core subset and
  put the rest in "notes"; the user can continue.
- For pen drawings, approximate with a few lines or arcs (roughly 30 blocks or
  fewer). Never generate one block per pixel or point.
- Use plain ASCII; no markdown or explanations outside the JSON.
- Never emit placeholders or incomplete values (PLACEHOLDER_*, TBD, "...");
  every block, target and menu value must be final and complete.

Sprites, stage and media:
- Use ONLY the media library names listed below. No generated, downloaded or
  absolute paths. A bare name works when it is unique.
- For library media, use the library file stem as the costume/backdrop name
  (omit "name" and the harness uses the stem). Never label crab2.gif as
  "crab1" or otherwise rename one library file to another file's stem.
- create_sprite needs "name" and 1-3 "costumes" or a "preset" (supplies
  costumes, rotation centers, defaults); x/y/direction/size/visible/
  rotation_style override. Defaults 0,0,90,100,true,"all around".
- delete_sprite and duplicate_sprite work only on AI-created sprites. User
  sprites may receive scripts and costumes but cannot be deleted, renamed or
  duplicated over.
- add_costume adds library media to an existing sprite (or the stage); set
  "select" true to make it the visible costume.
- set_backdrop adds a library backdrop to the stage and selects it by default.
- set_sprite moves or restyles an existing sprite; omit fields to keep them.
- Code attached to Stage is background code. The stage cannot move, turn, say,
  change size or hide; use switch_backdrop (not switch_costume) there.
- A change set applies top-down: put create_sprite before scripts for that
  sprite, and create_variable before using the variable.
- `touching`, `distance_to`, `goto_sprite`, `point_towards` and `attribute_of`
  may target `mouse-pointer`, `edge`, `Stage` (where valid), or the name of an
  existing sprite. A sprite created in the same change set must be created
  before the script that targets it.
- Colors are `#rrggbb` strings. `touching_color` detects whether the sprite is
  touching that color; `color_sees` compares two colors; `set_pen_color` sets
  the RGB pen color. Use these for pen levels and background/color detection.
  The model cannot see the background image, so use known colors or ask the user.
- Reuse costumes and backdrops the project already has when possible.
{verified}
Media library (relative to scratch/base/Media):
{media}

Available block ops:
{catalog}
""".replace("{verified}", VERIFIED_PROP_PATHS)


EXAMPLES = """
Examples:

User: Make the cat draw a square when I click the green flag.
JSON:
{
  "summary": "Added a green-flag square-drawing script.",
  "changes": [{
    "action": "add_script",
    "target": "Sprite1",
    "label": "draw_square",
    "hat": {"op": "when_flag_clicked"},
    "body": [
      {"op": "pen_clear"},
      {"op": "pen_down"},
      {"op": "repeat", "args": {"count": 4}, "body": [
        {"op": "move", "args": {"steps": 100}},
        {"op": "turn_right", "args": {"degrees": 90}}
      ]},
      {"op": "pen_up"}
    ]
  }]
}

User: Add a bat that spins when I click the green flag.
JSON:
{
  "summary": "Added a spinning bat sprite.",
  "changes": [
    {
      "action": "create_sprite",
      "name": "Bat",
      "costumes": [{"library": "Animals/bat1-a.png"}],
      "x": 0, "y": 0, "direction": 90, "size": 100,
      "visible": true, "rotation_style": "all around"
    },
    {
      "action": "add_script",
      "target": "Bat",
      "label": "spin",
      "hat": {"op": "when_flag_clicked"},
      "body": [
        {"op": "forever", "body": [
          {"op": "turn_right", "args": {"degrees": 15}}
        ]}
      ]
    }
  ]
}

User: Put stars in the background and switch to them when the green flag is clicked.
JSON:
{
  "summary": "Added a stars backdrop and a stage script.",
  "changes": [
    {"action": "set_backdrop", "library": "Space/stars.gif", "select": true},
    {
      "action": "add_script",
      "target": "Stage",
      "label": "stars_on_start",
      "hat": {"op": "when_flag_clicked"},
      "body": [
        {"op": "switch_backdrop", "args": {"backdrop": "stars"}}
      ]
    }
  ]
}
"""


DSL_SYSTEM_PROMPT = """You are the AI programming agent inside Scratch 1.4.

You turn a natural-language request into a change set of Scratch blocks for the
current project. Write one module of Scratch-Python, a checked subset of Python;
the bridge transpiles it into the same change set it applies today. The user
runs it, then asks you to change it again.

Reply with ONE fenced python block and nothing else. Packs and script bodies
listed at the end of this prompt are already loaded; use them directly. Only
for detail that is missing, return only the JSON shape
{"load_context": ["name"]} or {"load_sprite": ["SpriteName"]} plus "reason";
the bridge resends the request. Control-channel replies stay JSON and are
returned alone, never with a module.

Module level is the change set. The module runs top-down, so create things
before you use them:
summary("one short sentence describing the change")
set_backdrop("Space/stars.gif", select=True)
create_variable("score", scope="global", initial=0)
create_list("queue", scope="global", items=["next", "go"])
create_sprite("Bat", costumes=["Animals/bat1-a.png"], size=80, rotation_style="left-right")
notes("optional short note")

One decorated def is one script; the decorator names the hat:
@on_flag(target="Bat", label="spin")
def bat_spin():
    while True:
        turn_right(15)
        wait(0.1)

Rules:
- Use only the functions in the API reference below. Never invent a function,
  block, menu value or placeholder (PLACEHOLDER_*, TBD, "..."). Every value
  must be final and complete.
- Module-level calls take literal arguments only (strings, numbers, true/false,
  and literal lists). A variable, call or expression there is rejected.
- summary() and notes() are module-level calls, not prose outside the fence.
- Use only sprites, variables, costumes and sounds in the project context. If
  you need a new variable or list, create it at module level before its first
  use. One decorated def is a new script; add script_id="ai-4" to replace an
  AI-owned script.
- Bare names are variables inside a script: score = 0 sets, score += 1 changes,
  score reads. A variable must exist in the context or be created earlier.
- The Python you may use is the reference's control flow and calls only: no
  import, class, lambda, comprehension, try, return, global, with, assert,
  raise, yield, break, continue, pass, f-string, indexing, attribute access
  or chained comparison. Negative literals (-90, x=-100) are fine.
- A command is a statement on its own line; a reporter returns a value and must
  be nested. if/wait_until/repeat_until conditions need a boolean reporter.
- Open any multi-script module with a few # comment lines planning sprites,
  variables, broadcasts and (on a revision) which current behaviours you keep.
- Prefer ~80 blocks. If a scene cannot fit, return a coherent core subset and
  put the rest in notes(); the user can continue. For pen drawings, approximate
  with a few lines or arcs (roughly 30 blocks or fewer), never one block per
  pixel or point.
- Use plain ASCII and no markdown or prose outside the fenced python block.

Sprites, stage and media:
- Use ONLY the media library names listed below. No generated, downloaded or
  absolute paths. A bare name works when it is unique.
- For library media, use the library file stem as the costume/backdrop name
  (omit "name" and the harness uses the stem). Never label crab2.gif as
  "crab1" or otherwise rename one library file to another file's stem.
- create_sprite needs a name and 1-3 costumes or a preset (supplies costumes,
  rotation centers, defaults); x/y/direction/size/visible/rotation_style
  override. Defaults 0,0,90,100,true,"all around".
- delete_sprite and duplicate_sprite work only on AI-created sprites. User
  sprites may receive scripts and costumes but cannot be deleted, renamed or
  duplicated over.
- add_costume adds library media to an existing sprite (or the stage); select
  true makes it the visible costume.
- set_backdrop adds a library backdrop to the stage and selects it by default.
- set_sprite moves or restyles an existing sprite; omit fields to keep them.
- Code attached to Stage is background code. The stage cannot move, turn, say,
  change size or hide; use switch_backdrop (not switch_costume) there.
- A change set applies top-down: put create_sprite before defs for that
  sprite, and create_variable before using the variable.
- touching, distance_to, goto_sprite, point_towards and attribute_of may
  target mouse-pointer, edge, Stage (where valid), or the name of an existing
  sprite. A sprite created in the same module must be created before the def
  that targets it.
- Colors are #rrggbb strings. touching_color detects whether the sprite is
  touching that color; color_sees compares two colors; set_pen_color sets the
  RGB pen color. Use these for pen levels and background/color detection.
  The model cannot see the background image, so use known colors or ask the user.
- Reuse costumes and backdrops the project already has when possible.
- Lists are 1-based: list_item(1, "queue"). create the list first; keep monitors
  hidden unless the request asks for them.
{verified}
Media library (relative to scratch/base/Media):
{media}

Available Scratch-Python API:
{catalog}
""".replace("{verified}", VERIFIED_PROP_PATHS)


EXAMPLES_DSL = """
Examples:

User: Make the cat draw a square when I click the green flag.
Python:
```python
summary("Added a green-flag square-drawing script.")

@on_flag(target="Sprite1", label="draw_square")
def draw_square():
    pen_clear()
    pen_down()
    for _ in range(4):
        move(100)
        turn_right(90)
    pen_up()
```

User: Add a bat that spins when I click the green flag.
Python:
```python
summary("Added a spinning bat sprite.")
create_sprite("Bat", costumes=["Animals/bat1-a.png"], direction=90, size=100, visible=True, rotation_style="all around")

@on_flag(target="Bat", label="spin")
def bat_spin():
    while True:
        turn_right(15)
        wait(0.1)
```

User: Put stars in the background and switch to them when the green flag is clicked.
Python:
```python
summary("Added a stars backdrop and a stage script.")
set_backdrop("Space/stars.gif", select=True)

@on_flag(target="Stage", label="stars_on_start")
def stars_on_start():
    switch_backdrop("stars")
```
"""



def prompt_budget_chars() -> int:
    """The character budget for one prompt.

    ``HARNESS_PROMPT_BUDGET`` wins when it holds a positive integer; anything
    else (unset, blank, text, zero, negative) falls back to the safe default.
    """
    raw = os.environ.get(PROMPT_BUDGET_ENV)
    if raw is None:
        return DEFAULT_PROMPT_BUDGET
    text = raw.strip()
    if not text:
        return DEFAULT_PROMPT_BUDGET
    try:
        value = int(text)
    except (TypeError, ValueError):
        return DEFAULT_PROMPT_BUDGET
    if value <= 0:
        return DEFAULT_PROMPT_BUDGET
    return value


def estimate_tokens(text: str) -> int:
    """Rough token estimate: about four characters per token."""
    return max(0, len(text or "") // 4)


def _resolve_budget(budget_chars: int | None) -> int:
    if budget_chars is None:
        return prompt_budget_chars()
    try:
        value = int(budget_chars)
    except (TypeError, ValueError):
        return prompt_budget_chars()
    if value <= 0:
        return prompt_budget_chars()
    return value


def _target_kind(target: str | None) -> str | None:
    if target is None:
        return None
    return "stage" if target.lower() == "stage" else "sprite"


def _truncate_lines(text: str, limit: int) -> str:
    """Keep whole lines that fit in ``limit`` characters (never half a line)."""
    if limit <= 0 or not text:
        return ""
    kept: list[str] = []
    used = 0
    for line in text.splitlines():
        extra = len(line) + (1 if kept else 0)
        if used + extra > limit:
            break
        kept.append(line)
        used += extra
    return "\n".join(kept)


def _drop_trailing_header(text: str) -> str:
    """Remove a category header left dangling by a line-boundary cut."""
    lines = text.splitlines()
    while lines and not lines[-1].startswith("  ") and lines[-1].endswith(":"):
        lines.pop()
    return "\n".join(lines)


def _hard_cut(text: str, budget: int, template: str, full_len: int) -> str:
    """Last-resort cut on a line boundary with an explicit marker."""
    marker_reserve = len("\n" + template.format(n=9999999999))
    room = budget - marker_reserve
    if room <= 0:
        keep = ""
    else:
        keep = _truncate_lines(text, room)
        if not keep and text:
            keep = text[:room].rstrip()
    dropped = max(0, full_len - len(keep))
    marker = template.format(n=dropped)
    return (keep + "\n" + marker) if keep else marker


def _strip_catalog_details(catalog: str) -> str:
    """Drop the human-readable ``# label`` tail from every catalog entry."""
    lines: list[str] = []
    for line in catalog.splitlines():
        if line.startswith("  "):
            line = line.partition("  # ")[0].rstrip()
        lines.append(line)
    return "\n".join(lines)


#: Room for the compact curated index. The grouped render wraps items as
#: comma lists, so the curated core fits here untrimmed while the raw folder
#: index keeps its old 16000-character cap.
GROUPED_MEDIA_CHARS = 30000


def media_index_text(library: Any = None, *, max_chars: int = 16000) -> str:
    """The media index for the ``{media}`` slot of the system prompt.

    Prefers the curated, complete index built from ``media_groups.json`` (up to
    ``GROUPED_MEDIA_CHARS``) and falls back to the raw folder index capped at
    ``max_chars`` when the classification file is absent or unusable.
    ``library`` defaults to the shared library index.
    """
    from .media import default_library
    from .media_groups import grouped_prompt_index, load_media_groups

    lib = default_library() if library is None else library
    groups = load_media_groups()
    if groups:
        grouped = grouped_prompt_index(lib, groups, max_chars=GROUPED_MEDIA_CHARS)
        if grouped is not None:
            return grouped
    return lib.prompt_index(max_chars=max_chars)


def _build_budgeted_prompt(
    prompt_template: str,
    examples: str,
    target: str | set[str] | frozenset[str] | None = None,
    *,
    budget_chars: int | None = None,
    categories: set[str] | None = None,
    media_index: str | None = None,
    context_doc: str | None = None,
    catalog: str | None = None,
) -> str:
    """The shared compaction ladder for every system-prompt variant.

    ``context_doc`` is the model context appendix (usually
    ``SCRATCH_AI_CONTEXT.md``). It is included verbatim when it fits; otherwise
    the worked examples go first, then the appendix is trimmed on line
    boundaries with a marker, then the media index, then the catalog. Passing
    ``None`` (the default) keeps the prompt context-doc free for callers that
    do not want it.

    ``catalog`` overrides the generated block catalog (the DSL builder passes
    the Scratch-Python API reference instead).
    """
    budget = _resolve_budget(budget_chars)
    kind = _target_kind(target)
    if catalog is None:
        catalog = catalog_summary(categories, kind)
    if media_index is None:
        media_index = media_index_text(max_chars=16000)

    doc = (context_doc or "").strip()
    doc_header = "\n\nAdditional Scratch context (semantics and patterns):\n"
    doc_footer = "\n"
    doc_part = (doc_header + doc + doc_footer) if doc else ""

    before, rest = prompt_template.split("{media}")
    middle, after = rest.split("{catalog}")

    # The verified-paths region is optional detail: the hand-curated prop paths
    # plus the mined known-good tier, rendered as one unit so the tight-budget
    # fallback can never keep half of it. With no mined data the text is
    # byte-identical to the pre-ranking prompt.
    verified_region = VERIFIED_PROP_PATHS + known_good_media_block()
    if verified_region != VERIFIED_PROP_PATHS:
        before = before.replace(VERIFIED_PROP_PATHS, verified_region)
    unverified = before.replace(verified_region, "")
    marker_chars = len("\n[media index truncated 9999999999 chars]") + len(
        "\n[catalog truncated 9999999999 chars]"
    )
    if budget < (
        len(unverified)
        + len(middle)
        + len(after)
        + marker_chars
        + 400  # a readable catalog slice
    ):
        before = unverified

    full = before + media_index + middle + catalog + after + doc_part + "\n" + examples
    if len(full) <= budget:
        return full

    # 1. Remove long human-readable block descriptions.
    lean_catalog = _strip_catalog_details(catalog)
    lean = (
        before
        + media_index
        + middle
        + lean_catalog
        + after
        + doc_part
        + "\n"
        + examples
    )
    if len(lean) <= budget:
        return lean

    # 2. Remove the worked examples (prose, not block entries).
    no_examples = before + media_index + middle + lean_catalog + after + doc_part
    if len(no_examples) <= budget:
        return no_examples

    # 3. Trim the context appendix on line boundaries, reserving room for the
    # catalog and at least a media marker. The media index is trimmed after the
    # appendix, so a large preset/media index cannot crowd the appendix out.
    media_template = "[media index truncated {n} chars]"
    media_reserve = len("\n" + media_template.format(n=9999999999))
    if doc:
        doc_template = "[context appendix truncated {n} chars]"
        doc_reserve = len("\n" + doc_template.format(n=9999999999))
        fixed_len = (
            len(before)
            + len(middle)
            + len(lean_catalog)
            + len(after)
            + len(doc_header)
            + len(doc_footer)
            + media_reserve
        )
        room = budget - fixed_len - doc_reserve
        if room > 0:
            kept_doc = _truncate_lines(doc, room)
            if len(kept_doc) >= len(doc):
                doc_candidate = doc_header + doc + doc_footer
            else:
                doc_marker = doc_template.format(n=max(0, len(doc) - len(kept_doc)))
                doc_candidate = doc_header + kept_doc + "\n" + doc_marker + doc_footer
            remaining = budget - (
                len(before)
                + len(middle)
                + len(lean_catalog)
                + len(after)
                + len(doc_candidate)
            )
            if remaining > media_reserve:
                kept_media = _truncate_lines(media_index, remaining - media_reserve)
                media_marker = media_template.format(
                    n=max(0, len(media_index) - len(kept_media))
                )
                candidate = (
                    before
                    + kept_media
                    + "\n"
                    + media_marker
                    + middle
                    + lean_catalog
                    + after
                    + doc_candidate
                )
            else:
                candidate = (
                    before
                    + "\n"
                    + media_template.format(n=max(0, len(media_index)))
                    + middle
                    + lean_catalog
                    + after
                    + doc_candidate
                )
            if len(candidate) <= budget:
                return candidate
        doc_part = ""

    # 4. Trim the media index on line boundaries.
    media_reserve = len("\n" + media_template.format(n=9999999999))
    fixed = before + middle + lean_catalog + after + doc_part
    room = budget - len(fixed) - media_reserve
    kept_media = ""
    if room > 0 and media_index:
        kept_media = _truncate_lines(media_index, room)
        media_marker = media_template.format(n=max(0, len(media_index) - len(kept_media)))
        candidate = (
            before
            + kept_media
            + "\n"
            + media_marker
            + middle
            + lean_catalog
            + after
            + doc_part
        )
        if len(candidate) <= budget:
            return candidate

    # 5. Keep as many complete catalog lines as fit, then mark the cut.
    template = "[catalog truncated {n} chars]"
    marker_reserve = len("\n" + template.format(n=9999999999))
    room = (
        budget
        - len(before)
        - len(kept_media)
        - len(middle)
        - len(after)
        - len(doc_part)
        - marker_reserve
    )
    if room >= 0:
        kept_catalog = _drop_trailing_header(_truncate_lines(lean_catalog, room))
        dropped = len(lean_catalog) - len(kept_catalog)
        marker = template.format(n=max(0, dropped))
        return (
            before
            + kept_media
            + middle
            + kept_catalog
            + "\n"
            + marker
            + after
            + doc_part
        )

    # Even the instructions alone overflow: cut them on line boundaries.
    return _hard_cut(
        before,
        budget,
        template,
        len(before)
        + len(media_index)
        + len(middle)
        + len(lean_catalog)
        + len(after)
        + len(doc_part),
    )


def build_system_prompt(
    target: str | set[str] | frozenset[str] | None = None,
    *args: Any,
    budget_chars: int | None = None,
    categories: set[str] | None = None,
    media_index: str | None = None,
    context_doc: str | None = None,
) -> str:
    """Render the JSON system prompt, compacting optional sections when over budget.

    The output is unchanged by the DSL variant: this is the original template,
    examples and budget ladder.

    ``target`` is the usual first argument. The old ``(categories, target)``
    call shape is still accepted for compatibility.
    """
    if isinstance(target, (set, frozenset)):
        categories = set(target) if categories is None else categories
        target = args[0] if args else None
        args = ()
    if args:
        raise TypeError("build_system_prompt() takes at most one positional target")
    return _build_budgeted_prompt(
        SYSTEM_PROMPT,
        EXAMPLES,
        target,
        budget_chars=budget_chars,
        categories=categories,
        media_index=media_index,
        context_doc=context_doc,
    )


def build_dsl_system_prompt(
    target: str | None = None,
    *,
    budget_chars: int | None = None,
    context_doc: str | None = None,
    media_index: str | None = None,
) -> str:
    """Render the Scratch-Python system prompt with the generated API reference.

    ``api_reference`` is imported lazily so the JSON path never pays for the
    dialect vocabulary table until ``generator = dsl`` asks for it.
    """
    from .dsl import api_reference

    return _build_budgeted_prompt(
        DSL_SYSTEM_PROMPT,
        EXAMPLES_DSL,
        target,
        budget_chars=budget_chars,
        categories=None,
        media_index=media_index,
        context_doc=context_doc,
        catalog=api_reference(),
    )


def _script_owner(script: ScriptSummary) -> str:
    owner = "ai-owned" if script.owned else "user-created, read-only"
    if script.user_edited:
        owner += ", edited outside the harness"
    return owner


def _context_text(
    context: ProjectContext, level: int, generator: str = "json"
) -> str:
    """Render the project context at a detail level (0 = today's full text).

    Level 1 drops per-script detail beyond id/label/hat/count (ownership is
    always kept), level 2 drops costume/sound lists, and level 3 reduces
    variables and lists to bare names.  ``generator`` only picks the registry
    hint wording so the last line teaching revisions names the dialect's form.
    """
    if level <= 0:
        return context.summary_text(generator=generator)

    lines = [f"Target: {context.target}"]
    lines.append("Sprites: " + ", ".join(context.sprites.keys()))
    if context.stage_variables:
        prefix = "Global variables: " if level < 3 else "Vars: "
        lines.append(prefix + ", ".join(context.stage_variables))
    if context.stage_lists:
        prefix = "Global lists: " if level < 3 else "Lists: "
        lines.append(prefix + ", ".join(context.stage_lists))
    for name, sprite in context.sprites.items():
        if sprite.is_stage:
            continue
        parts: list[str] = []
        if level < 2:
            parts.append(
                f"x={sprite.x} y={sprite.y} direction={sprite.direction} "
                f"size={sprite.size} rotation={sprite.rotation_style}"
            )
        if sprite.ai_owned:
            parts.append("AI-created")
        if sprite.variables:
            label = "variables=" if level < 3 else "vars="
            parts.append(label + ", ".join(sprite.variables))
        if level < 2:
            if sprite.costumes:
                parts.append("costumes=" + ", ".join(sprite.costumes))
            if sprite.sounds:
                parts.append("sounds=" + ", ".join(sprite.sounds))
        if parts:
            lines.append(f"{name}: " + "; ".join(parts))
    registry = context.registry()
    if registry:
        if generator == "dsl":
            lines.append(
                "Scripts (replace_script rewrites the WHOLE script; load its "
                "sprite's detail first when the current body matters; "
                "delete_script(script_id) removes):"
            )
        else:
            lines.append("Scripts (use the id for replace_script/delete_script):")
        for script in registry.values():
            lines.append(
                f"  {script.script_id}: {script.label} / {script.hat} / "
                f"{script.block_count} / {_script_owner(script)}"
            )
    return "\n".join(lines)


#: The closing instruction of the user prompt.  The json tail keeps the
#: historical wording byte-for-byte; the dsl tail names the dialect so the
#: last line the model reads cannot contradict the system prompt.
JSON_REPLY_TAIL = "\n\nReturn the JSON change set now.\n"
DSL_REPLY_TAIL = (
    "\n\nReturn the Scratch-Python module now, "
    "in one fenced python block.\n"
)


def _reply_tail(generator: str) -> str:
    return DSL_REPLY_TAIL if generator == "dsl" else JSON_REPLY_TAIL


def _user_prompt(
    request: str,
    context_text: str,
    tail: str = JSON_REPLY_TAIL,
    history_text: str = "",
) -> str:
    history_part = f"\n\n{history_text}" if history_text else ""
    return (
        f"User request:\n"
        f"{request}"
        f"{history_part}"
        f"\n\n"
        f"Project context:\n"
        f"{context_text}"
        f"{tail}"
    )


def _essential_context_lines(compact: str) -> list[str]:
    """The targeting surface: target sprite, sprite names, and every script id."""
    lines = compact.splitlines()
    target = [line for line in lines if line.startswith("Target:")]
    sprites = [line for line in lines if line.startswith("Sprites:")]
    scripts = [line for line in lines if line.startswith("  ")]
    if not target and lines:
        target = [lines[0]]
    return target + sprites + scripts


def _hard_user_fit(
    request: str,
    compact_context: str,
    budget: int,
    full_len: int,
    tail: str = JSON_REPLY_TAIL,
    history_text: str = "",
) -> tuple[str, int, bool]:
    """Trim context detail and the request, keeping the targeting surface.

    Returns ``(prompt, dropped_chars, used_history)`` so the audit bundle can
    record how much of the original request/context did not reach the model.
    The conversation section is dropped entirely before the targeting surface
    is sacrificed: memory is optional, the project context is not.
    """
    head = "User request:\n"
    context_head = "\n\nProject context:\n"
    history_part = f"\n\n{history_text}" if history_text else ""
    template = "[truncated {n} chars]"
    marker_reserve = len("\n" + template.format(n=9999999999))

    core = _essential_context_lines(compact_context)
    candidates: list[list[str]] = [core]
    if len(core) > 1:
        candidates.extend(core[:index] for index in range(len(core) - 1, 0, -1))
    candidates.append([])

    history_options = (True, False) if history_text else (False,)
    for use_history in history_options:
        hist = history_part if use_history else ""
        for candidate in candidates:
            context_text = "\n".join(candidate)
            for include_tail in (True, False):
                fixed = head + hist + context_head + context_text
                if include_tail:
                    fixed += tail
                room = budget - len(fixed) - marker_reserve
                if room < 0:
                    continue
                kept_request = request if len(request) <= room else request[:room].rstrip()
                content = head + kept_request + hist + context_head + context_text
                if include_tail:
                    content += tail
                dropped = max(0, full_len - len(content))
                marker = template.format(n=dropped)
                text = content.rstrip("\n") + "\n" + marker
                return text, dropped, use_history

    text = _hard_cut(head, budget, template, full_len)
    return text, max(0, full_len - len(text)), False


def _user_meta(
    level: int,
    prompt: str,
    budget: int,
    context_text: str,
    *,
    truncated: bool = False,
    dropped_chars: int = 0,
    history: HistoryStats | None = None,
) -> dict[str, Any]:
    stats = history or HistoryStats()
    return {
        "level": level,
        "chars": len(prompt),
        "estimated_tokens": estimate_tokens(prompt),
        "budget_chars": budget,
        "truncated": truncated,
        "dropped_chars": dropped_chars,
        "context_chars": len(context_text),
        "history_turns": stats.turns,
        "history_chars": stats.chars,
        "history_dropped": stats.dropped,
        "history_verbatim": stats.verbatim,
    }


def build_user_prompt_with_meta(
    request: str,
    context: ProjectContext,
    *,
    budget_chars: int | None = None,
    generator: str = "json",
    history: Any = None,
) -> tuple[str, dict[str, Any]]:
    """Build the user prompt and report which trimming stage was used.

    See :func:`build_user_prompt_with_history`, which also returns the
    conversation section that made it into the prompt.
    """
    prompt, meta, _history = build_user_prompt_with_history(
        request,
        context,
        budget_chars=budget_chars,
        generator=generator,
        history=history,
    )
    return prompt, meta


def build_user_prompt_with_history(
    request: str,
    context: ProjectContext,
    *,
    budget_chars: int | None = None,
    generator: str = "json",
    history: Any = None,
) -> tuple[str, dict[str, Any], str]:
    """Build the user prompt and report which trimming stage was used.

    ``history`` is a :class:`harness.history.ConversationHistory` (or any object
    with a ``snapshot()`` returning records).  Its section is inserted between
    the request and the project context and is trimmed on its own stages
    **before** the context ladder, so memory never starves the targeting
    surface.  With no history the prompt is byte-identical to the pre-history
    builder, which the snapshot test in ``test_budget.py`` pins.

    The audit bundle records the metadata so a turn that dropped project detail
    can be distinguished from one that did not.  ``generator`` only picks the
    closing instruction: json keeps the historical wording, dsl names the
    Scratch-Python module.
    """
    budget = _resolve_budget(budget_chars)
    request = "" if request is None else str(request)
    tail = _reply_tail(generator)

    records: list[Any] = []
    if history is not None:
        snapshot = getattr(history, "snapshot", None)
        records = snapshot() if callable(snapshot) else list(history)

    full_context = context.summary_text(generator=generator)

    # H0: the full verbatim window.  H1: only the last MIN_VERBATIM_TURNS
    # verbatim, the rest compressed.  H2: at that compressed window, drop the
    # oldest one-liners one at a time.  render_history also enforces the
    # section's own hard cap at every stage.
    candidates: list[tuple[str, HistoryStats]] = [("", HistoryStats())]
    if records:
        candidates = []
        for verbatim in (VERBATIM_TURNS, MIN_VERBATIM_TURNS):
            text, stats = render_history(records, verbatim_turns=verbatim)
            if all(text != existing for existing, _ in candidates):
                candidates.append((text, stats))
        for limit in range(ONE_LINER_LIMIT - 1, -1, -1):
            text, stats = render_history(
                records,
                verbatim_turns=MIN_VERBATIM_TURNS,
                one_liner_limit=limit,
            )
            if all(text != existing for existing, _ in candidates):
                candidates.append((text, stats))

    full_prompt = _user_prompt(request, full_context, tail, candidates[0][0])
    for history_text, stats in candidates:
        prompt = _user_prompt(request, full_context, tail, history_text)
        if len(prompt) <= budget:
            return (
                prompt,
                _user_meta(0, prompt, budget, full_context, history=stats),
                history_text,
            )

    history_text, stats = candidates[-1]
    for level in (1, 2, 3):
        context_text = _context_text(context, level, generator)
        prompt = _user_prompt(request, context_text, tail, history_text)
        if len(prompt) <= budget:
            return (
                prompt,
                _user_meta(level, prompt, budget, context_text, history=stats),
                history_text,
            )

    compact = _context_text(context, 3, generator)
    prompt, dropped, used_history = _hard_user_fit(
        request, compact, budget, len(full_prompt), tail, history_text
    )
    if not used_history:
        stats = HistoryStats(total=stats.total, dropped=stats.total)
    return (
        prompt,
        _user_meta(
            3,
            prompt,
            budget,
            compact,
            truncated=True,
            dropped_chars=dropped,
            history=stats,
        ),
        history_text if used_history else "",
    )


def build_user_prompt(
    request: str,
    context: ProjectContext,
    *,
    budget_chars: int | None = None,
    generator: str = "json",
    history: Any = None,
) -> str:
    """Render the user prompt, trimming context detail before the request.

    The full prompt is returned byte-for-byte when it fits. Otherwise context
    detail is removed in four stages: per-script detail, costume/sound lists,
    variable/list labels, and finally a marked hard truncation that keeps the
    targeting surface (target sprite and every script id/label/owner).
    Conversation history, when supplied, is trimmed on its own stages first.
    """
    return build_user_prompt_with_meta(
        request,
        context,
        budget_chars=budget_chars,
        generator=generator,
        history=history,
    )[0]


_TRUNCATION_MARKER_RE = re.compile(
    r"\[(context appendix|media index|catalog) truncated (\d+) chars\]"
)


def analyze_system_prompt(prompt: str) -> dict[str, Any]:
    """Describe the final system prompt for the audit bundle.

    This is deliberately derived from the rendered text: it is what the model
    actually received, after every budget fallback, not what we intended to
    send.
    """
    text = prompt or ""
    truncations = {
        name: int(count) for name, count in _TRUNCATION_MARKER_RE.findall(text)
    }
    lines = text.splitlines()
    return {
        "chars": len(text),
        "estimated_tokens": estimate_tokens(text),
        "truncations": truncations,
        "has_examples": "Examples:\n" in text,
        "has_appendix": "Additional Scratch context" in text,
        "catalog_entries": sum(
            1 for line in lines if line.startswith("  ") and "  # " in line
        ),
    }
