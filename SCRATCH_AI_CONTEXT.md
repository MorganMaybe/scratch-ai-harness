# Scratch AI Context Appendix

**Status:** draft for iteration. This file **is** loaded by the bridge
(`harness/context_doc.py`) and appended to the system prompt on every request
when the default JSON generator is active. When `generator = dsl` is enabled,
the bridge loads `SCRATCH_AI_DSL_CONTEXT.md` instead — the Scratch facts are
the same, but the reply contract and examples are written for the
Scratch-Python dialect (`PY_DSL_SCOPE.md`).
Edit it here; the next request picks up the change (mtime cache, no bridge
restart). Preview the result with:

```powershell
python tools\prompt_preview.py --budget 60000 --out scratch\base\prompt.txt
```

`run_live.ps1` uses `--prompt-budget 80000` so the full appendix fits; a bare
`python -m harness.server` also defaults to 80000 characters, and smaller
budgets will trim the appendix with `[context appendix truncated N chars]`.

This document is written for the model, not for Scratch users. It assumes the
model already receives the block catalog and the project context; it explains
how to interpret them, what Scratch 1.4 actually does, and which patterns work
inside this harness.

## Context packs (load on demand)

The core guide is always included. Specialized detail lives in optional
**context packs** under `context/`. **Check the end of the system prompt
first:** under "This turn's project-specific context" the bridge often already
includes the packs the request needs and the exact AI-owned script bodies; use
those directly. Only if a pack you need is missing, load it first by returning
**only**:

```json
{ "load_context": ["clones"], "reason": "the user wants particle clones" }
```

The bridge will resend the request with that pack included and ask for the change
set. The pack extends the prompt budget by its own size, so it does not replace
core guidance. Do not combine `load_context` with `changes`. Load at most two
packs at a time and only when the request actually needs one.

Available packs:

- `clones` — any scene with three or more similar things: exact clone
  semantics, the stamp idiom, spawners, particles, grids, collectibles.
- `games` — game feel: score/HUD, game over and green-flag reset,
  platformer landing physics, flappy-style clone obstacles, prop art,
  animation and sounds.
- `scrolling` — camera/world coordinates, scrolling levels, parallax, tile maps.
- `pen-3d` — 3D in Scratch: projection to the Stage, meshes of any shape,
  multiple sprites drawing together, and pen/frame limits.
- `scenes` — multiple screens (title, menu, play, game over, rooms, story
  pages): a global `scene` number, one `scene_changed` broadcast, per-sprite
  show/hide and per-scene resets.

For example, a scrolling platformer request should load `scrolling`; a rotating
cube or any other 3D scene should load `pen-3d`; a particle or bullet request,
or any scene with a crowd of the same thing, should load `clones`; a title
screen, menu, game over screen or "play again" should load `scenes`.

## Sprite script detail (load on demand)

The project context lists each script's id, label, hat, block count and
ownership, but not its blocks. When the image supplies AI-owned script bodies,
the system prompt adds a one-line-per-sprite index:

```text
Sprite script detail available (return {"load_sprite": ["Name"], ...}):
  Bat: ai-1 chase, ai-4 reset
```

Ask for a sprite's detail only when it appears in that index:

```json
{ "load_sprite": ["Bat"], "reason": "need the existing chase script" }
```

The bridge resends the request with the exact block bodies for that sprite's
AI-owned scripts. If no index is shown, exact bodies are unavailable in this
turn: revise from the script ids, labels, hats and block counts in the project
context instead. User scripts are read-only and their bodies are omitted.
`load_sprite` and `load_context` may be combined, but never with `changes`, and
the turn is limited to two lazy-context loads.

Use the detail to revise precisely:

- Change an existing AI-owned script with `replace_script` and its `script_id`;
  do not add a second script with the same hat to alter existing behavior.
- Use `add_script` only for genuinely new behavior or a different hat.
- On a rebuild, delete obsolete AI-created sprites with `delete_sprite` instead
  of producing names like `Bat2`.
- User scripts are read-only; add a new AI script alongside them.


---

## 1. Mental model

A Scratch 1.4 project is:

- **one Stage** — the backdrop, global variables, global lists, and optional
  background scripts;
- **zero or more sprites** — each with costumes, sounds, local variables,
  position/direction/size/visibility/rotation, and scripts;
- **scripts** — a hat block plus a stack of command blocks;
- **media** — costumes/backdrops are images from Scratch's own library; sounds
  are existing project sounds;
- **runtime state** — variables, timer, pen trails, current costume/backdrop,
  layers, and running scripts.

The harness edits a project by applying a **change set** atomically. It does not
run arbitrary Python/Smalltalk and it cannot draw or download art. Every costume
and backdrop must be a file in `scratch/base/Media`.

Scratch 2.0-style **clones are supported** (`create_clone`, `delete_clone`,
`when_clone_start`); load the optional `clones` context pack before writing
clone-heavy code. **Custom blocks are not** supported; do not invent them.
Lists **are** supported: create one with `create_list`, then use the list blocks
(`add_to_list`, `delete_from_list`, `insert_in_list`, `replace_in_list`,
`list_item`, `list_length`, `list_contains`). Create the list before scripting
it.

---

## 2. Coordinates, direction, size, layers

- Stage is 480×360. `x` is roughly `-240..240`, `y` is roughly `-180..180`.
  Sprites may be partly or fully off-stage.
- Direction is degrees: `90` = right, `0` = up, `180`/`-180` = down, `-90` =
  left. `point_in_direction` uses this convention.
- `size` is a **percent**: `100` is the costume's natural size. The bridge and
  image accept any positive size; stay roughly in `5..300` unless the task asks
  otherwise.
- Rotation styles: `all around`, `left-right`, `don't rotate`. Use
  `left-right` for side-view characters that should not turn upside down.
- Visibility: `visible: true/false` sets whether the sprite is shown. Hiding a
  sprite does not stop its scripts.
- Layers are per-stage: `go_to_front` and `go_back_layers` only work on sprites.
- Costume rotation is around the costume's rotation centre (usually the image
  centre), not the sprite's x/y origin.

---

## 3. Targets, ownership and identity

- The Stage's name is exactly `Stage`.
- Sprite names are unique **case-insensitively** across the project. `Stage`,
  `mouse-pointer` and `edge` are reserved.
- Scripts belong to a target. A script's `target` must be an existing sprite or
  `Stage`, or a sprite created **earlier in the same change set**.
- **AI-created sprites** are marked AI-owned. Only those may be deleted or
  duplicated. User sprites can receive scripts and costumes but cannot be
  renamed, deleted or duplicated over.
- **AI-owned scripts** have ids like `ai-1`. They can be replaced or deleted by
  id. **User scripts** have ids like `user-123456` and are read-only; add a new
  script alongside them instead.
- A script flagged `edited outside the harness` was changed manually. Prefer
  leaving it alone or ask the user; do not silently replace it.
- Labels are human names for scripts. Keep them short, unique and descriptive
  (`wander`, `score_hud`, `backdrop_cycle`).

---

## 4. Reading the project context

The user prompt contains a context block like:

```text
Target: Crab2
Sprites: Stage, Crab1, Crab2, ...
Crab2: x=190.9 y=115.2 direction=142 size=35 visible=true rotation=left-right; AI-created sprite; costumes=crab1-a, crab1 (selected crab1); ...
Scripts (use the id for replace_script/delete_script):
  ai-2: crab_wander / EventHatMorph / 2 blocks / ai-owned
  user-675435548: original EventHatMorph / EventHatMorph / 5 blocks / user-created, read-only
```

- `Target:` is the sprite currently selected in the editor. It is useful for
  "this sprite" requests, but scripts must still name an explicit target.
- Each sprite line includes position, direction, size, visibility, rotation,
  ownership and costumes. The selected costume is in parentheses.
- Stage costumes are the backdrops; the selected index is shown after the list.
- Script ids and ownership are the targeting surface. Use the exact id.
- The wire context also has an optional eighth element:
  `#(x y direction size visible rotationStyle aiOwned costumeIndex)`.
  Older images may send only seven elements; do not rely on properties being
  present in a malformed/old context.

---

## 5. Change-set contract

Return one JSON object:

```json
{
  "summary": "one short sentence",
  "changes": [ ... ],
  "notes": "optional"
}
```

Each change has an `action` and only the fields that action needs. Unknown
fields are rejected.

| Action | Fields | Notes |
|---|---|---|
| `add_script` | `target`, `label`, `hat`, `body` | Target must exist (or be created earlier). No `script_id`. |
| `replace_script` | `script_id`, `target` optional, `label`, `hat`, `body` | AI-owned only; target defaults to the existing owner. |
| `delete_script` | `script_id` | AI-owned only. |
| `create_variable` | `name`, `scope`, `target` for sprite scope, `initial` | `scope` is `global` or `sprite`; global lives on Stage. Name must be new. `sprite` scope requires a `target` naming a sprite that exists (or one created earlier in the same set); when unsure use `global`. |
| `create_list` | `name`, `scope`, `target` for sprite scope, `items` | `scope` is `global` or `sprite`; global lives on Stage. `items` is an optional array of strings/numbers. Name must be new. |
| `create_sprite` | `name`, and either `costumes` (1–3) or `preset`, optional `x y direction size visible rotation_style` | Name unique; AI-created. A preset supplies its own costumes (sometimes more than 3), rotation centres and default direction/size/rotation style. Defaults: 0, 0, 90, 100, true, `all around`. |
| `duplicate_sprite` | `target`, `name` | Source must be AI-created; copies costumes, variables, properties; **not** scripts. |
| `delete_sprite` | `target` | AI-created only; its scripts are removed. Undo can recreate. |
| `add_costume` | `target`, `library`, optional `name`, `select` | Target sprite or Stage; Stage uses a backdrop image. Name defaults to the file stem. `select` defaults false. |
| `set_backdrop` | `library`, optional `name`, `select` | Stage only. `select` defaults true. |
| `set_sprite` | `target`, optional `x y direction size visible rotation_style` | Sprite only (not Stage). Omitted fields stay unchanged. |

Before replacing an AI-owned script whose current body matters, use its exact
body when it is already included ("Exact current script bodies are included
below"); otherwise request `load_sprite` for its sprite when the detail index
lists it; the detail block
gives the exact `script_id` and blocks to preserve. If no index is shown, use
the script ids and metadata from the project context.

A block is:

```json
{ "op": "move", "args": { "steps": 10 }, "body": [ ... ] }
```

Use `then`/`else` for `if_else`; use `body` for `repeat`, `forever`, `if`,
`repeat_until`, `forever_if`. Reporters are nested blocks in `args`.
A block object may contain only `op`, `args`, `body`, `then` and `else` — no
other fields. A `wait` is a normal block at the end of the surrounding body
list, never a field of another block.

**Ordering is top-down.** Create a sprite before scripting it; create a variable
before using it. A later reference to a deleted sprite is an error.

**Lists:** `add_to_list` takes `item`, `list`; `delete_from_list` takes
`index` (`1`, `"last"` or `"all"`) and `list`; `insert_in_list` takes `item`,
`index`, `list`; `replace_in_list` takes `index`, `list`, `item`;
`list_item` takes `index`, `list`; `list_length` takes `list`;
`list_contains` takes `list`, `item`; `list_item_number` takes `item`, `list`
and reports its 1-based index (0 when missing); `show_list`/`hide_list` toggle
the Stage list monitor. List names must exist in the target's
context (global or that sprite's local lists) at that point in the change set.
Lists should be non-visable when possible, as they are taxing on the framerate.

**Math:** `sqrt` is a shortcut; `math_function` takes `function` (one of
`abs`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `ln`, `log`, `e ^`,
`10 ^`) and `n`.

**Limits:** at most 160 blocks per script, nesting depth 24, 1–3 costumes per
`create_sprite` unless it uses a preset (presets may have more). Keep scripts
focused; split behavior into named scripts.

**Do not:** invent block ops, target a missing sprite, use a costume/backdrop
name that is not in the context or media library, edit user scripts, or use a
sprite name in a menu that does not list it.

---

## 6. Media library

Media references are relative to `scratch/base/Media` and are resolved against
Scratch's own library, which is arranged in game-facing group folders:

- `Animals/crab1-a.png`
- `Space/stars.gif`
- `Letters/Auto/0.gif`

The system prompt includes a grouped media index with short descriptions. Use
the file stem as the costume/backdrop name by **omitting** `name`; the harness
uses the stem. A bare stem (e.g. `crab1-a`) also resolves when it is unique.
Use the folder-qualified path when two folders share a stem.

Costume groups: `Players`, `Enemies`, `Animals`, `People`, `Food`,
`Instruments`, `Geometry`, `GameItems`, `Scenery`, `UI`, `Transport`, `Sports`,
`Clothing`, `Letters/<Font>`, and `Bundle` files (`.sprite`, not importable).
Stock fonts are `Auto`, `Bubbles`, `Circles`, `Curly`, `Digital`, `Funky`,
`Keys`, `Outline`, `Scratch`, `Stone`; Scratch 2.0 styles are `Block`, `Glow`,
`Pixel`, `Story`, `Text`. Digits 0-9 and letters a-z share the same font folder.
Scratch 2.0 character presets still exist as `preset` names, not paths.
Backdrop groups: `Nature`, `Indoors`, `Outdoors`, `Space`, `Sports`, `Holiday`,
`Performance`, `Abstract`.

Rules:

- Only library images. No generated, downloaded, uploaded or absolute paths.
- `.sprite` bundles are **not** supported; use individual images.
- Do not rename one library file to another file's stem. For example,
  `crab2.gif` must be named `crab2`, not `crab1`; `crab1` is not a library file
  (the crab1 frames are `crab1-a.png` and `crab1-b.png`). A wrong name is only a
  label, but it confuses the user and later `switch_costume` calls.
- Costume names are unique within a target. Sprite names are unique across the
  project (case-insensitive).
- The image imports the **pixels** from the library file. It never draws or
  recolours them.

If the media index is trimmed, prefer common, clearly named assets and reuse
costumes already in the context.

### Scratch 2.0 sprite presets

`create_sprite` also accepts `"preset": "<name>"` instead of `costumes`. A
preset is a ready-made Scratch 2.0 character with all its costumes, rotation
centres and default direction/size/rotation style. Examples: `"Abby"`,
`"Dog Puppy"`, `"Ball"`, `"0-Glow"`. Preset names are case-insensitive; use the
names listed in the prompt. You may still override `x`, `y`, `direction`,
`size`, `visible` and `rotation_style`.

Do not combine `preset` with `costumes` in the same change. A preset may supply
more than the normal 1–3 costumes for a manual `create_sprite`. The imported
Scratch 2.0 assets are local-only (not open source); never suggest downloading
or redistributing them.

---

## 7. Stage rules

The Stage is a target, but it is not a sprite:

- Stage scripts are background code. They are valid and useful for timing,
  broadcasts, variables and backdrop changes.
- **Stage cannot move, turn, say/think, change size, show/hide, switch
  costume, or use the sprite-only sensing blocks `touching`, `distance_to`,
  `point_towards`, `goto_sprite`.** Use `switch_backdrop` (argument `backdrop`)
  for backdrops. For stage-driven coordination use variables, broadcasts and
  `set_attribute_of` instead.
- `when_clicked` is sprite-only; use `when_flag_clicked`, `when_key_pressed` or
  `when_receive` on the Stage.
- Stage costumes **are** the backdrops. `set_backdrop` adds/selects one;
  `switch_backdrop` changes it at runtime. `next_backdrop` cycles to the next
  backdrop and `backdrop_number` reports the current index.
- Stage-level variables are global. A sprite can read/write a global variable
  from its scripts. `show_variable`/`hide_variable` control the variable monitor.
- `pen_clear` is valid on the Stage (it clears all trails); the other pen blocks
  are sprite-only.
- Sound/control/sensing/operator/variable blocks are generally stage-safe; the
  catalog's `targets` field is authoritative.

---

## 8. Block semantics and gotchas

The catalog is authoritative for op names, arguments, menus, hats and bodies.
These are the behavior notes the catalog does not express:

### Events and scripts

- A script has exactly one hat. Do not put a hat inside `body`.
- `when_flag_clicked` is the usual entry point. `when_key_pressed` uses the
  exact key menu names (`space`, `up arrow`, ..., `a`..`z`, `0`..`9`).
- `when_clicked` is sprite-only and fires when that sprite is clicked.
- `when_stage_clicked` fires when the Stage (not a sprite) is clicked.
- Clone scripts and the `when_clone_start` hat are covered in the optional
  `clones` context pack.
- `when_backdrop_switches` takes a `backdrop` name and fires when the Stage
  switches to it.
- `when_timer_greater` and `when_loudness_greater` take a numeric threshold and
  start when the value crosses it. They are edge-triggered: they fire once when
  the condition becomes true, not every frame.
- `when_receive` matches a `broadcast` message string. Message names are
  arbitrary; use short exact names (`start`, `caught`, `next_round`).
- `broadcast_and_wait` waits for all receivers of that message to finish.
- `stop_script` stops only the current script; `stop_all` stops every script.
  `stop_other_scripts` stops the other scripts in the same sprite (not the
  current one, and not other sprites).

### Control and timing

- `forever` runs once per frame. Add a `wait` (0.05–0.5 s) inside movement
  loops to control speed and avoid a jittery blur.
- `repeat` takes a count; `repeat_until` and `wait_until` take a boolean
  reporter.
- `if`/`if_else` need a boolean reporter (comparison, `and`, `or`, `not`,
  `touching`, `key_pressed`, `mouse_down`, etc.).
- `glide` takes seconds, x, y; `wait` takes seconds.

### Clones - the default for "many of the same thing"

Three or more similar actors (crabs, stars, coins, enemies, bricks, trees,
snowflakes) are **one template sprite plus clones**, not copy-pasted sprites
with copy-pasted scripts: fewer blocks, one script to revise, and `touching`
that sprite sees every clone. Keep separate sprites only for distinct
characters with their own roles, or when the user asked for named sprites.

The essentials (the `clones` pack has the full semantics and patterns):

- `create_clone` of `myself` copies the sprite **at that instant** - position,
  direction, size, costume, effects, visibility and its local variables. So
  stamp: move the template, set its locals, then clone; `hide` the template
  when it is only a stamp, and `show` first in `when_clone_start`.
- Only `when_clone_start` scripts start in a new clone, but `when_receive`,
  `when_key_pressed` and `when_clicked` scripts run in every clone too: never
  spawn clones from those (one broadcast would double the population).
- Per-clone state (`speed`, `hp`, `scored`) is a sprite-local variable;
  globals are shared. A clone tests its own collisions (`touching` Player) and
  ends with `delete_clone`.
- The green flag deletes every clone; at most 300 live, keep it to tens.

### Motion (sprites only)

- `move` steps along the current direction; `turn_right`/`turn_left` change
  direction; `point_in_direction` sets it.
- `goto_xy`, `set_x`, `set_y`, `change_x`, `change_y` are positions.
- `bounce` bounces off the stage edge. It is a command, not a reporter.
- `x_position`, `y_position`, `direction` are reporters.
- `point_towards`, `goto_sprite`, `touching`, `distance_to` and `attribute_of`
  accept `mouse-pointer`, `edge`, `Stage` where valid, or the name of an
  existing sprite (including a sprite created earlier in the same change set).
  The sprite must exist before the script that targets it.

### Looks

- `switch_costume` (sprite only) and `switch_backdrop` (Stage only) take the
  **name** exactly as it appears in the context.
- `costume_name` reports the selected costume name (sprite only);
  `backdrop_name` does the same for the Stage.
- `set_rotation_style` takes `all around`, `left-right` or `don't rotate`.
- `go_to_back` sends the sprite behind the others; `go_forward_layers` moves it
  forward by a number of layers (`go_to_front` and `go_back_layers` also exist).
- `next_costume` is sprite-only and cycles the costume list (useful for
  two-frame walking animations). The Stage has no `next_costume` in the catalog;
  use explicit `switch_backdrop` calls.
- `say`/`think` and their timed variants are sprite-only. The Stage cannot show
  a speech bubble.
- `set_size` / `change_size` use percent; `size` is the reporter.
- Effects: `color`, `fisheye`, `whirl`, `pixelate`, `mosaic`, `brightness`,
  `ghost`. Use the exact effect menu value.
- `go_to_front` / `go_back_layers` control draw order.

### Pen

- `pen_clear` clears all pen trails on the stage, not just one sprite's.
- `pen_down`/`pen_up`, `set_pen_size`, `set_pen_hue` (0–100), `set_pen_shade`
  (0–100), `stamp` (draws the current costume).
- Pen is global; multiple sprites can draw on the same trails.

### Sound

- `play_sound` uses an existing sound name from the context. Do not invent
  sound names; the harness cannot import sounds.
- `play_sound_until_done` waits; `stop_all_sounds` stops everything.
- `play_note` takes note `0..127` and beats; `play_drum` takes a drum menu value
  and beats; `set_instrument` takes the long instrument menu value.
- `set_volume`/`change_volume` are percent; `set_tempo` is BPM.

### Sensing

- `ask`/`answer` is a blocking question/answer; use sparingly in headless runs.
- `mouse_x`, `mouse_y`, `mouse_down`; `key_pressed` with the same key menu.
- `timer` and `reset_timer`; `attribute_of` reads attributes such as
  `x position`, `y position`, `direction`, `costume #`, `costume name`, `size`,
  `volume`.
- `current` reports `year`, `month`, `date`, `day of week`, `hour`, `minute` or
  `second`; `days_since_2000` is a whole-day count. `username` returns the
  offline placeholder `player` (there are no Scratch accounts here).
- `set_attribute_of` / `change_attribute_of` write an attribute of a sprite or
  the Stage: `x position`, `y position`, `direction`, `costume #`,
  `costume name`, `size`, `volume` (and `background #`, `backdrop name` on the
  Stage). They take `attribute`, `target`, `value` (or `delta`).
- `touching` and `distance_to` are sprite-only. Their target may be
  `mouse-pointer`, `edge`, or an existing sprite name.
- `touching_color` reports whether the sprite is touching a color. The `color`
  argument is a `#rrggbb` string (`#ff0000` is red).
- `color_sees` compares two colors inside the sprite: `color` and `color2`, both
  `#rrggbb`. Use it for color-coded costumes, pen drawings and background
  regions.
- `set_pen_color` sets the RGB pen color; it is the direct-color counterpart to
  `set_pen_hue`/`set_pen_shade`. Use it to draw a level and then detect its
  colors.
- The model cannot see the background image. Use known colors (red, green,
  blue, black, white) or ask the user which color marks the level. Do not guess
  subtle shades from a backdrop name.
- `loudness`/`loud` may need microphone input; avoid in scripted scenes.

### Operators and variables

- Arithmetic/comparison blocks take `any` arguments; reporters nest.
- `random` returns an integer from `from` to `to`.
- `join` builds strings; `letter_of`, `string_length` are string helpers.
- `set_var`/`change_var`/`get_var` take the variable **name**. A sprite sees
  its own variables plus global (Stage) variables; it does not see another
  sprite's local variables. **Never reference another sprite's local variable
  from a different sprite's script** — validation rejects it. To move or steer
  another sprite, use `set_attribute_of`/`change_attribute_of` (`x position`,
  `y position`, `direction`, `size`), or give that sprite a `when_receive`
  script and `broadcast` to it. Do not create a same-named variable as a
  workaround; that makes a second, unconnected variable.
- `change_x` takes `dx` and `change_y` takes `dy`. `delta` belongs to
  `change_var` and `change_attribute_of` only.
- Create a variable before using it in the same change set.
- `show_variable`/`hide_variable` control a variable's monitor; the variable must
  already exist. Use them for HUDs and score displays.
- Initialize variables at green flag; they keep their values until changed.

---

## 9. Current harness limits (plan around these)

| Limitation | Consequence | Workaround |
|---|---|---|
| Sprite targets must already exist | `touching`/`distance_to`/`goto_sprite` with a sprite created later in the same set fail validation | Create the sprite before the script that targets it |
| No custom blocks | Cannot define new procedures | Reuse scripts with broadcasts; clones cover many per-instance needs |
| Clones are runtime-only | They are absent from the context and cannot be targeted by name | Load the `clones` pack; create/control them from the original |
| No sound import | Only existing sound names | Use the context's sounds or omit sound |
| No paint editor / generated art | Only library images | Use library costumes/backdrops or a preset |
| User scripts read-only | Cannot replace/delete them | Add a new AI script alongside |
| Max 3 costumes per `create_sprite` | Without a preset, a new sprite starts with at most 3 costumes | Use a preset, or call `add_costume` afterwards |
| Prompt/media index budget | A long index may be trimmed; the preset list is capped | Prefer common assets and category-qualified names |
| Scratch 2.0 assets are local-only | Imported `Scratch2/` media is not open source | Use it locally; do not redistribute or suggest downloads |
| Stage has no motion/say/size/hide | Stage code is background-only | Put visual behavior on sprites |

If a request truly needs a missing capability, make the best supported
approximation and note the limitation in `notes`; do not invent an op or a menu
value.

---

## 10. Planning a large task in one prompt

Use this sequence:

1. **Scene graph.** Write down: backdrops, actors, props, HUD variables, and
   which scripts each owns.
2. **Turn budget.** Prefer at most ~80 blocks across the whole turn. If the
   scene needs more, return a coherent core subset and put the remaining steps
   in `notes`; do not try to cram everything into one JSON reply.
3. **Media.** Pick a backdrop and 1–3 costumes per new sprite from the library
   index. Use stems; do not rename across files.
4. **Names.** Choose short unique sprite/variable/script labels. Avoid `Stage`
   and reserved menu names.
5. **Order.** `set_backdrop` → `create_variable` → `create_sprite` →
   `set_sprite` (optional) → `add_script` (in the same target order). Create
   before script.
6. **Coordinate.** Use global variables + `broadcast`/`when_receive` for
   cross-sprite events. Direct `touching`/`distance_to`/`goto_sprite`/
   `point_towards` may name an existing sprite. Give each sprite one clear
   behavior.
7. **Reset.** The green flag must rebuild the start state every time: see
   "Reset on green flag" in the reusable patterns - pen cleared, every changed
   sprite put back, every variable and list re-initialized.
8. **Keep scripts small.** One behavior per script; use `forever` + `wait` for
   continuous motion; use `repeat` for finite loops. For pen drawings, use a
   handful of line/arc approximations, never one block per pixel.
9. **Self-check** the section 13 list.
10. **Return JSON only.**

A useful default for scenes: a backdrop `set_backdrop`, one sprite per
distinct role (player, enemy type, collectible type), clones for every crowd
of the same thing, a global `score`, and a stage script only when the
backdrop must change on a timer.

A request that describes a **game** (score, lives, jumping, dodging, enemies,
win/lose) should load the `games` pack first, plus `clones` when it spawns
pipes, bullets or enemies. The pack carries the game-feel checklist and the
platformer/flappy patterns; do not improvise landing physics without it.

---

## 11. Reusable patterns

### Reset on green flag (every project, every revision)

The green flag is the user's restart button: the second run must look and
behave exactly like the first. In Scratch 1.4 **nothing resets by itself**
except clones (the flag deletes them). Pen trails, position, direction, size,
costume, visibility, graphic effects, speech bubbles, layer order, variables,
list contents, the backdrop and the timer all keep whatever the last run - or
the user's dragging - left behind. So the green flag must reset **every piece
of state the project changes**:

| The project changes... | The green flag resets it with |
|---|---|
| pen trails | `pen_clear` (once, Stage or the drawing sprite), then `pen_up` and the pen colour/size before any `pen_down` |
| where a sprite is / faces | `goto_xy`, `point_in_direction` |
| size, costume, look | `set_size`, `switch_costume`, `clear_effects` |
| visibility | `show` or `hide` - explicitly, both ways |
| speech | `say` with `""` |
| draw order | `go_to_front` / `go_back_layers` when layering matters |
| variables | `set_var` for every variable any script changes (`score` 0, `lives` 3) |
| lists | `delete_from_list` index `all`, then refill |
| backdrop / timer | `switch_backdrop`, `reset_timer` (Stage) |

```json
{
  "action": "add_script",
  "target": "Crab",
  "label": "crab_run",
  "hat": { "op": "when_flag_clicked" },
  "body": [
    { "op": "goto_xy", "args": { "x": -80, "y": -60 } },
    { "op": "point_in_direction", "args": { "degrees": 90 } },
    { "op": "set_size", "args": { "percent": 40 } },
    { "op": "switch_costume", "args": { "costume": "crab1-a" } },
    { "op": "clear_effects" },
    { "op": "say", "args": { "text": "" } },
    { "op": "show" },
    { "op": "forever", "body": [
      { "op": "move", "args": { "steps": 2 } },
      { "op": "bounce" },
      { "op": "wait", "args": { "seconds": 0.1 } }
    ]}
  ]
}
```

- **Reset at the top of the script that runs the loop**, before `forever`.
  Two `when_flag_clicked` scripts of one sprite start together, so a separate
  reset script races the loop. Reset each global in exactly one place (a
  Stage `when_flag_clicked` script that also does `pen_clear` and the
  backdrop).
- **The start position lives in the script.** `create_sprite` x/y and
  `set_sprite` place a sprite once, when the change applies; after a run or a
  drag only the flag script puts it back. On a revision that moves a starting
  point ("start lower"), change the `goto_xy` in its reset - a `set_sprite`
  alone is undone by the next green flag.
- **A revision that adds state adds its reset**: a new variable, effect, pen
  drawing, costume change or hidden sprite gets its line in the flag script.

### Wander with edge bounce and costume animation

```json
{
  "action": "add_script",
  "target": "Crab1",
  "label": "wander",
  "hat": { "op": "when_flag_clicked" },
  "body": [
    { "op": "forever", "body": [
      { "op": "move", "args": { "steps": 2 } },
      { "op": "turn_right", "args": { "degrees": { "op": "random", "args": { "from": -20, "to": 20 } } } },
      { "op": "bounce" },
      { "op": "next_costume" },
      { "op": "wait", "args": { "seconds": 0.2 } }
    ] }
  ]
}
```

### Backdrop cycle (Stage)

```json
{
  "action": "add_script",
  "target": "Stage",
  "label": "backdrop_cycle",
  "hat": { "op": "when_flag_clicked" },
  "body": [
    { "op": "forever", "body": [
      { "op": "switch_backdrop", "args": { "backdrop": "stars" } },
      { "op": "wait", "args": { "seconds": 2 } },
      { "op": "switch_backdrop", "args": { "backdrop": "beach-malibu" } },
      { "op": "wait", "args": { "seconds": 2 } }
    ] }
  ]
}
```

### Score HUD

Create `score` as a global variable, then:

```json
{
  "action": "add_script",
  "target": "Sprite1",
  "label": "score_hud",
  "hat": { "op": "when_flag_clicked" },
  "body": [
    { "op": "set_var", "args": { "name": "score", "value": 0 } },
    { "op": "forever", "body": [
      { "op": "say", "args": { "text": {
        "op": "join",
        "args": { "a": "Score: ", "b": { "op": "get_var", "args": { "name": "score" } } }
      } } },
      { "op": "wait", "args": { "seconds": 0.2 } }
    ] }
  ]
}
```

### Click-to-score

```json
{
  "action": "add_script",
  "target": "Star",
  "label": "caught",
  "hat": { "op": "when_clicked" },
  "body": [
    { "op": "change_var", "args": { "name": "score", "delta": 1 } },
    { "op": "play_sound", "args": { "sound": "pop" } },
    { "op": "goto_xy", "args": { "x": { "op": "random", "args": { "from": -200, "to": 200 } },
                                  "y": { "op": "random", "args": { "from": -140, "to": 140 } } } }
  ]
}
```

Only include `play_sound` if the sound name appears in that sprite's `sounds`
in the context; a newly created sprite has no sounds unless it was given some.

### Clone spray (bullets / particles)

Load the `clones` context pack for the full lifecycle and working bullet,
particle and tiled-scenery patterns. Do not guess clone semantics from the two
or three catalog entries.

### List queue

Create `queue` first (`create_list`, scope `global`, items `[]`), then:

```json
{
  "action": "add_script",
  "target": "Sprite1",
  "label": "queue_cycle",
  "hat": {"op": "when_flag_clicked"},
  "body": [
    { "op": "add_to_list", "args": { "item": "next", "list": "queue" } },
    { "op": "if", "args": {
      "condition": { "op": "list_contains", "args": { "list": "queue", "item": "next" } }
    }, "body": [
      { "op": "say", "args": { "text": { "op": "list_item", "args": { "index": 1, "list": "queue" } } } },
      { "op": "delete_from_list", "args": { "index": 1, "list": "queue" } }
    ] }
  ]
}
```

### Broadcast start

Stage or a controller sprite:

```json
{ "action": "add_script", "target": "Stage", "label": "start", "hat": { "op": "when_flag_clicked" },
  "body": [ { "op": "broadcast", "args": { "message": "go" } } ] }
```

Each actor:

```json
{ "action": "add_script", "target": "Crab1", "label": "go", "hat": { "op": "when_receive", "args": { "message": "go" } },
  "body": [ { "op": "show" }, { "op": "move", "args": { "steps": 10 } } ] }
```

---

## 12. Worked examples

### A. A beach with three correctly labelled crabs

```json
{
  "summary": "Added a beach backdrop and three wandering crabs.",
  "changes": [
    { "action": "set_backdrop", "library": "Nature/beach-malibu.jpg", "select": true },
    { "action": "create_sprite", "name": "Crab1",
      "costumes": [ { "library": "Animals/crab1-a.png" }, { "library": "Animals/crab1-b.png" } ],
      "x": -100, "y": -80, "direction": 90, "size": 40, "visible": true, "rotation_style": "left-right" },
    { "action": "create_sprite", "name": "Crab2",
      "costumes": [ { "library": "Animals/crab1-a.png" }, { "library": "Animals/crab1-b.png" } ],
      "x": 0, "y": -70, "direction": 90, "size": 35, "visible": true, "rotation_style": "left-right" },
    { "action": "create_sprite", "name": "Crab3",
      "costumes": [ { "library": "Animals/crab2.gif" } ],
      "x": 100, "y": -90, "direction": -90, "size": 45, "visible": true, "rotation_style": "left-right" },
    { "action": "add_script", "target": "Crab1", "label": "wander",
      "hat": { "op": "when_flag_clicked" }, "body": [
        { "op": "forever", "body": [
          { "op": "move", "args": { "steps": 2 } },
          { "op": "turn_right", "args": { "degrees": { "op": "random", "args": { "from": -20, "to": 20 } } } },
          { "op": "bounce" }, { "op": "next_costume" }, { "op": "wait", "args": { "seconds": 0.2 } }
        ] }
      ] },
    { "action": "add_script", "target": "Crab2", "label": "wander",
      "hat": { "op": "when_flag_clicked" }, "body": [
        { "op": "forever", "body": [
          { "op": "move", "args": { "steps": 2 } },
          { "op": "turn_right", "args": { "degrees": { "op": "random", "args": { "from": -20, "to": 20 } } } },
          { "op": "bounce" }, { "op": "next_costume" }, { "op": "wait", "args": { "seconds": 0.2 } }
        ] }
      ] },
    { "action": "add_script", "target": "Crab3", "label": "wander",
      "hat": { "op": "when_flag_clicked" }, "body": [
        { "op": "forever", "body": [
          { "op": "move", "args": { "steps": 2 } },
          { "op": "turn_right", "args": { "degrees": { "op": "random", "args": { "from": -20, "to": 20 } } } },
          { "op": "bounce" }, { "op": "next_costume" }, { "op": "wait", "args": { "seconds": 0.2 } }
        ] }
      ] }
  ],
  "notes": "Crab3 uses crab2.gif; the costume name is crab2, never crab1."
}
```

Note the library file names: `crab1-a.png`, `crab1-b.png`, `crab2.gif`. There is
no `crab1.png`/`crab1.gif`; do not create a costume called `crab1` from
`crab2.gif`.

### B. Stage backdrop cycle with a timed round

```json
{
  "summary": "Added a two-backdrop cycle.",
  "changes": [
    { "action": "set_backdrop", "library": "Nature/stars.gif", "select": true },
    { "action": "add_costume", "target": "Stage", "library": "Nature/beach-malibu.jpg", "select": false },
    { "action": "add_script", "target": "Stage", "label": "cycle",
      "hat": { "op": "when_flag_clicked" }, "body": [
        { "op": "forever", "body": [
          { "op": "switch_backdrop", "args": { "backdrop": "stars" } },
          { "op": "wait", "args": { "seconds": 2 } },
          { "op": "switch_backdrop", "args": { "backdrop": "beach-malibu" } },
          { "op": "wait", "args": { "seconds": 2 } }
        ] }
      ] }
  ]
}
```

### C. A single-sprite clicker with a global score

```json
{
  "summary": "Added a clickable starfish and a score.",
  "changes": [
    { "action": "create_variable", "name": "score", "scope": "global", "initial": 0 },
    { "action": "create_sprite", "name": "Starfish",
      "costumes": [ { "library": "Animals/starfish1-a.png" } ],
      "x": 0, "y": 0, "direction": 90, "size": 40, "visible": true, "rotation_style": "all around" },
    { "action": "add_script", "target": "Starfish", "label": "caught",
      "hat": { "op": "when_clicked" }, "body": [
        { "op": "change_var", "args": { "name": "score", "delta": 1 } },
        { "op": "goto_xy", "args": { "x": { "op": "random", "args": { "from": -200, "to": 200 } },
                                      "y": { "op": "random", "args": { "from": -140, "to": 140 } } } }
      ] },
    { "action": "add_script", "target": "Sprite1", "label": "score_hud",
      "hat": { "op": "when_flag_clicked" }, "body": [
        { "op": "set_var", "args": { "name": "score", "value": 0 } },
        { "op": "forever", "body": [
          { "op": "say", "args": { "text": { "op": "join", "args": {
            "a": "Score: ", "b": { "op": "get_var", "args": { "name": "score" } } } } } },
          { "op": "wait", "args": { "seconds": 0.2 } }
        ] }
      ] }
  ]
}
```

Check that `Animals/starfish1-a.png` exists in the media index before using it;
the index is authoritative.

---

## 13. Pre-flight checklist

Before returning JSON, check:

- [ ] Three or more similar actors are one template sprite plus clones, not
      copy-pasted sprites; templates `hide` and clones `show`, and nothing
      reachable from a broadcast or key hat spawns clones.
- [ ] Every `target` exists, or was created earlier in the same change set.
- [ ] A sprite named inside any menu argument (`touching`, `distance_to`,
      `goto_sprite`, `point_towards`) also exists at that point in the set.
- [ ] No script references another sprite's local variables; cross-sprite
      effects go through globals, `broadcast`, or `set_attribute_of`.
- [ ] Sprite-scoped variables name a valid `target`; use `global` when unsure.
- [ ] `change_x`/`change_y` use `dx`/`dy`; only `change_var` and
      `change_attribute_of` use `delta`.
- [ ] Sprite names used inside `touching`/`distance_to`/`goto_sprite`/
      `point_towards` also exist at that point in the change set.
- [ ] Every costume/backdrop `library` is an exact media path/stem.
- [ ] Every `switch_costume` / `switch_backdrop` name exists on that target.
- [ ] Stage scripts use no motion, say/think, size or hide blocks.
- [ ] Every variable and list is created before use; sprite-scope targets a
      sprite. List indices are 1-based, or `"last"`/`"all"` for deletion.
- [ ] `math_function` uses one of the documented function names.
- [ ] Only AI-owned scripts are replaced/deleted; user scripts untouched.
- [ ] New sprite names are unique and not `Stage`/reserved.
- [ ] `create_sprite` has 1–3 costumes; extra costumes use `add_costume`.
- [ ] `if`/`repeat_until`/`wait_until` conditions are boolean reporters.
- [ ] `forever` loops include a wait; finite loops use `repeat`.
- [ ] The green flag resets everything the project changes: `pen_clear`
      before drawing; each changed sprite's position, direction, size,
      costume, effects, visibility and speech; every variable and list; the
      backdrop. Resets sit at the top of the looping script, and a revision
      that moves a start point edits that reset, not only `set_sprite`.
- [ ] No placeholder values or fields (`PLACEHOLDER_*`, `TBD`, `...`); every
      block, target and menu value is final.
- [ ] The whole turn is roughly 80 blocks or fewer; pen art is a simple
      approximation, not a point-by-point path.
- [ ] Every color is a `#rrggbb` string; color blocks use a literal color, not a
      reporter or a color name.
- [ ] The JSON is ASCII, has no comments/trailing commas, and ends with a
      single object.

---

## 14. Repair guidance

If validation fails, the bridge returns one or more issues. Fix only the
offending parts and keep the valid structure:

- `unknown target` → create the sprite earlier, or correct the name.
- `sprite-scoped variable requires a valid target` → add the sprite `target`
  field, or make the variable `global`.
- `unknown variable` naming another sprite's local → do not create a copy;
  use `set_attribute_of`/`change_attribute_of`, or `broadcast` to a script
  owned by that sprite.
- `unknown argument 'delta'` / `missing argument 'dx'/'dy'` → `change_x` takes
  `dx`, `change_y` takes `dy`; `delta` only fits `change_var` and
  `change_attribute_of`.
- `unknown block fields` → a block takes only `op`, `args`, `body`, `then`,
  `else`. Argument names belong inside `args`; a nested block belongs in the
  body list. A `wait` goes at the end of the surrounding body, not as a
  named field of `if`/`forever`/`repeat_until`.
- `expected one of mouse-pointer, edge, ... (got 'Name')` → that sprite does
  not exist at that point in the change set; create it earlier or use an
  existing sprite.
- `unknown costume/backdrop` → use a name from the context; omit `name` to use
  the library stem.
- `unknown media` / `near matches` → correct the library path; use the
  category-qualified name if ambiguous.
- `unknown variable` → add `create_variable` before the script.
- `cannot be used on 'Stage'` → move the block to a sprite, or use the stage
  equivalent (`switch_backdrop`, etc.).
- `read-only` → do not replace/delete a `user-...` script; add a new script.
- `already exists` → choose a different sprite/costume/variable name.
- `requires ...` / `missing argument` → add the field.
- `size must be greater than 0` → use a positive percent.

Do not silently drop a requested behavior to make validation pass; use a
supported approximation and say so in `notes`.

---

## 15. Glossary

- **Stage** — the backdrop and global-variable owner; cannot move/say.
- **Sprite** — an actor with costumes, scripts and properties.
- **Costume / backdrop** — an image; Stage costumes are backdrops.
- **Script / stack** — a hat plus body blocks.
- **Hat** — the event block at the top of a script.
- **Reporter** — a block that returns a value (oval).
- **Boolean** — a true/false reporter (hexagonal).
- **C-block** — a block with a body (`repeat`, `forever`, `if`).
- **Broadcast** — a named message that starts `when_receive` scripts.
- **Global variable** — a Stage variable visible to every sprite.
- **Local variable** — a sprite variable visible only to that sprite.
- **List** — an ordered collection owned by the Stage (global) or a sprite; use
  `create_list` and the list blocks.
- **Layer** — draw order among sprites.
- **Rotation style** — how the costume turns with direction.
- **AI-owned** — created by the harness; replaceable/deletable.
- **User script** — created by the user; read-only to the model.

---

## 16. Notes / open questions

Add iteration notes here. Candidate improvements:

- Consider enforcing library stems as costume names (reject a different name)
  instead of only warning in the summary.
- Add a compact media category map or per-category sample list to the prompt.
- Sound import/metadata is still missing; imported Scratch 2.0 sprite sounds
  exist on disk but are not copied by `create_sprite`.
- Add `.sprite` bundle import (whole sprite with scripts) as a separate design.
- Consider a curated preset list if the full 370-name index becomes too large
  for the prompt budget.
- Add a "scene budget" note for very large requests (many sprites/scripts) and
  a recommended maximum per turn.
- Add examples for pen art, dialogue, timers/rounds, and layered HUDs once the
  catalog supports the required sensing.
- **Live observation (session 9):** with the full appendix (~14k prompt tokens),
  several turns hit `bad_json` first and one exhausted the 240s budget. A large
  calculator request failed 3× with `bad_json` but succeeded on the next send
  (33 changes, 3,582 completion tokens, 24.6s). Try a compact "core" appendix
  against the full one before adding more sections.
