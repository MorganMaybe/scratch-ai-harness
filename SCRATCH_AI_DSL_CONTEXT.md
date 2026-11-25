# Scratch AI Context Appendix (Scratch-Python)

**Status:** draft for iteration. This file is loaded by the bridge
(`harness/context_doc.py`) and appended to the system prompt on every request
when `generator = dsl` is set in `harness.ini`. Edit it here; the next request
picks up the change (mtime cache, no bridge restart). With `generator = json`
the bridge loads `SCRATCH_AI_CONTEXT.md` instead.

This document is written for the model, not for Scratch users. It assumes the
model already receives the block catalog and the project context; it explains
how to write the restricted Python dialect ("Scratch-Python"), what Scratch 1.4
actually does, and which patterns work here.

The dialect is a checked subset of Python. The bridge parses it, transpiles it
to the same change set the JSON front end uses, and validates that change set.
Anything outside the subset gets a line-precise diagnostic; it is never silently
guessed. Read the reply contract (section 5) before writing code.

## Context packs and script detail (load on demand)

The core guide is always included. Optional **context packs** under `context/`
add specialized detail. **Check the end of the system prompt first:** under
"This turn's project-specific context" the bridge often already includes the
packs the request needs and the exact bodies of the AI-owned scripts. Anything
listed there is loaded - use it and answer with the module straight away. Only
when a pack or a sprite's bodies you need are missing, load them first by
returning JSON **only** (not a python fence):

```json
{ "load_context": ["clones"], "reason": "the user wants particle clones" }
{ "load_sprite": ["Bat"], "reason": "need the existing chase script" }
```

The bridge resends with the pack or bodies included. Do not combine these with
a module; load at most two packs at a time. Packs: `clones` (any scene with
three or more similar things; exact clone semantics, spawners, particles,
grids, collectibles), `games` (score/HUD, game over, platformer and
flappy physics), `scrolling` (camera, parallax, tile maps), `pen-3d` (3D
projection, meshes, pen/frame limits), `scenes` (title/menu/play/game-over
screens driven by a global `scene` number and a `scene_changed` broadcast).

**Loaded packs show block examples in this dialect**, with the same function
names and argument order as this reference. The JSON blocks you may see in the
repository are generated from those examples for `generator = json`; never
write JSON in a change-set reply.

When the image supplies AI-owned script bodies, the prompt adds an index such
as `Bat: ai-1 chase, ai-4 reset`. Ask for detail only when it appears there; the
bodies come back in **this same dialect**:

```python
# ai-1 "chase" [when_flag_clicked] 7 blocks (ai-owned, editable)
@on_flag(target="Bat", label="chase")
def bat_chase():
    while True:
        point_towards("mouse-pointer")
        move(3)
        wait(0.2)
```

Keep the `script_id` to replace an AI-owned script
(`@on_flag(target="Bat", label="chase", script_id="ai-1")`). Replacing rewrites
the **whole** script: the def you return is the entire new body, never a patch.
Never reconstruct it from the label and the block count - the count is
top-level only, so a `forever` loop's body is invisible. Load the sprite's
detail first when the current body matters, then keep the behaviors that still
matter and say in `notes` what you deliberately drop. If no index is
shown, exact bodies are unavailable: revise from ids, labels, hats and counts.
User scripts are read-only and their bodies are omitted. `load_sprite` and
`load_context` may be combined, never with a module, and the turn is limited to
two lazy-context loads.

Before replacing an AI-owned script whose current body matters, make sure its
exact body is in the prompt: it usually already is (see "Exact current script
bodies are included below"). Only a sprite that is still listed under "Sprite
script detail available" needs `{"load_sprite": ["Name"], "reason": ...}`.

---

## 1. Mental model

A Scratch 1.4 project is:

- **one Stage** - the backdrop, global variables, global lists, and optional
  background scripts;
- **zero or more sprites** - each with costumes, sounds, local variables,
  position/direction/size/visibility/rotation, and scripts;
- **scripts** - a hat block plus a stack of command blocks;
- **media** - costumes/backdrops are images from Scratch's own library; sounds
  are existing project sounds;
- **runtime state** - variables, timer, pen trails, current costume/backdrop,
  layers, and running scripts.

The harness edits a project by transpiling one Scratch-Python module into a
**change set** applied atomically. It does not run arbitrary Python/Smalltalk
and cannot draw or download art. Every costume and backdrop must be a file in
`scratch/base/Media`.

Scratch 2.0-style **clones are supported** (`create_clone`, `delete_clone`,
`@on_clone_start`); load the `clones` pack before clone-heavy code. **Custom
blocks are not** supported; do not invent them. Lists **are** supported: create
one with `create_list`, then use the list functions.

---

## 2. Coordinates, direction, size, layers

- Stage is 480x360. `x` is roughly `-240..240`, `y` is roughly `-180..180`.
  Sprites may be partly or fully off-stage.
- Direction is degrees: `90` = right, `0` = up, `180`/`-180` = down, `-90` =
  left. Negative numbers are ordinary literals everywhere (`x=-100`,
  `direction=-90`, `goto_xy(-80, -60)`, `random(-20, 20)`).
- `size` is a **percent**: `100` is natural size. Stay roughly in `5..300`
  unless the task asks otherwise.
- Rotation styles: `all around`, `left-right`, `don't rotate`. Use
  `left-right` for side-view characters that should not turn upside down.
- Visibility: `visible=True`/`False`. Hiding a sprite does not stop its scripts.
- Layers are per-stage: `go_to_front()` and `go_back_layers(layers)` only work
  on sprites.
- Costume rotation is around the costume's rotation centre (usually the image
  centre), not the sprite's x/y origin.

---

## 3. Targets, ownership and identity

- The Stage's name is exactly `Stage`.
- Sprite names are unique **case-insensitively** across the project. `Stage`,
  `mouse-pointer` and `edge` are reserved.
- A decorator's `target` must be an existing sprite or `Stage`, or a sprite
  created **earlier in the same module**.
- **AI-created sprites** are marked AI-owned. Only those may be deleted or
  duplicated. User sprites can receive scripts and costumes but cannot be
  renamed, deleted or duplicated over.
- **AI-owned scripts** have ids like `ai-1`; replace/delete by id. **User
  scripts** have ids like `user-123456` and are read-only; add a new script
  alongside them.
- To replace an AI-owned script, put `script_id="ai-4"` on that def's event
  decorator. Without `script_id`, the def adds a new script. Replacement
  rewrites the whole body: load the sprite's detail first when the current body
  matters (the block count is top-level only, so loop bodies are invisible),
  keep the behaviors that still matter, and note what you drop.
- A script flagged `edited outside the harness` was changed manually. Leave it
  alone or ask the user; do not silently replace it.
- Labels are human names. Keep them short, unique and descriptive (`wander`,
  `score_hud`, `backdrop_cycle`).

---

## 4. Reading the project context

The user prompt contains a context block like:

```text
Target: Crab2
Sprites: Stage, Crab1, Crab2, ...
Crab2: x=190.9 y=115.2 direction=142 size=35 visible=true rotation=left-right; AI-created sprite; costumes=crab1-a, crab1 (selected crab1); ...
Scripts (use the id for script_id/delete_script):
  ai-2: crab_wander / EventHatMorph / 2 blocks / ai-owned
  user-675435548: original EventHatMorph / EventHatMorph / 5 blocks / user-created, read-only
```

- `Target:` is the sprite selected in the editor. Decorators still name an
  explicit `target`.
- Each sprite line includes position, direction, size, visibility, rotation,
  ownership and costumes (selected one in parentheses).
- Stage costumes are the backdrops; the selected index follows the list.
- Script ids and ownership are the targeting surface. Use the exact id.
- The optional eighth wire element is
  `#(x y direction size visible rotationStyle aiOwned costumeIndex)`. Older
  images may send only seven; do not rely on missing properties.
- Loaded script detail uses this same dialect, so edit the def and keep its
  `script_id`.

---

## 5. The reply contract

Return **one** fenced `python` block and nothing else. No prose before or after
it. The module inside the fence is the whole change set.
If the request is already satisfied, return `summary(...)` with `notes(...)` and no defs — the bridge treats it as an acknowledgment and nothing is applied.

### Exact reply shape

```python
summary("Moved the crab left.")
set_sprite("Crab1", x=-100)

@on_flag(target="Crab1")
def patrol():
    move(5)
```

- Everything goes between the two fences: no "Here is the module:" before the
  opening fence, no commentary after the closing fence.
- **Plan in comments.** For anything bigger than a one-script change, open the
  module with 2-8 `#` comment lines: the sprites and what each one does, the
  variables and who writes them, the broadcasts, and for a revision which
  behaviours of the current bodies you keep. Comments are free (the bridge
  ignores them) and they are the only place to think before you write code.
- `summary()` and `notes()` go INSIDE the fence, at module level.
- Exactly ONE fenced block. A second block is an error, even an identical copy.
- A JSON control message is the JSON object alone: no fence, no prose.

**Control-channel replies stay JSON.** When you need more context, return only
one of the small JSON objects from the preamble (not a python fence). Do not
combine them with a module; the bridge detects the shape first and resends the
request.

### Module level = the change set

The module executes top-down into the change list. **Create before use.**
Module-level change calls take literal arguments only (strings, numbers,
booleans, and literal lists of strings/numbers). A variable, call or expression
as a module argument is rejected.

Exact module-call signatures:

```python
summary(text)
notes(text)
set_backdrop(library, name=None, select=True)
add_costume(target, library, name=None, select=False)
create_variable(name, scope="global", target=None, initial=0)
create_list(name, scope="global", target=None, items=None)
create_sprite(name, costumes=["Animals/crab1-a.png"], preset=None, x=0, y=0, direction=90, size=100, visible=True, rotation_style="all around")
set_sprite(target, x=None, y=None, direction=None, size=None, visible=None, rotation_style=None)
duplicate_sprite(target, name)
delete_sprite(target)
delete_script(script_id)
```

- `summary` is one sentence; `notes` is optional. `set_backdrop` is Stage-only;
  `add_costume` works on a sprite or Stage.
- `create_variable`/`create_list`: `scope` is `"global"` or `"sprite"`; a
  sprite scope requires an existing `target`. `items` is an optional literal
  list.
- `create_sprite` takes `costumes` (1-3 library paths) or `preset`, not both.
  A preset supplies its costumes and defaults; the file stem names a costume.
- `duplicate_sprite` copies costumes, variables and properties, **not**
  scripts. `delete_sprite` removes an AI-created sprite and its scripts.
  `set_sprite` changes properties at apply time; omitted fields stay unchanged.
- Negative literals are fine everywhere, module calls included (`x=-100`,
  `random(-20, 20)`, `turn_right(-15)`). `-x` on a computed value becomes the
  `0 - x` subtract block.
- `=None` in a signature means the argument is optional: omit it. Do not pass
  `None`; the `None` literal itself is rejected.
- Module-level assignments are not allowed; create variables and lists with
  `create_variable`/`create_list`. Control ops (`repeat`, `forever`, `if`,
  `if_else`, `repeat_until`, `forever_if`) are Python syntax, never calls.
- Order: `summary`, backdrops, variables/lists, sprites, defs, `notes`.

### One decorated def = one script

The decorator names the hat; the function body is the script body.

```python
@on_flag(target="Crab1", label="wander")
def crab1_wander():
    while True:
        move(2)
        turn_right(random(-20, 20))
        bounce()
        next_costume()
        wait(0.2)
```

The nine event decorators:

| Decorator | Hat | Valid target |
|---|---|---|
| `@on_flag` | when green flag clicked | sprite or Stage |
| `@on_key("space")` | when key pressed | sprite or Stage |
| `@on_click` | when this sprite clicked | sprite only |
| `@on_stage_click` | when Stage clicked | Stage only |
| `@on_clone_start` | when I start as a clone | sprite only |
| `@on_receive("go")` | when I receive `go` | sprite or Stage |
| `@on_backdrop("stars")` | when backdrop switches to `stars` | Stage only |
| `@on_loudness(50)` | when loudness > 50 | sprite or Stage |
| `@on_timer(10)` | when timer > 10 | sprite or Stage |

Key names are exactly: `any`, `space`, `up arrow`, `down arrow`, `right arrow`,
`left arrow`, `a` through `z`, `0` through `9`.

Decorator kwargs: `target="Sprite1"` is required (and must exist or be created
earlier); `label="wander"` is optional and defaults to the def name;
`script_id="ai-4"` is optional and means replace that AI-owned script instead of
adding one. Exactly one decorator per def; defs take no arguments or
annotations. A plain or nested def, or two decorators, is rejected.

### The Python you MAY use

| Python construct | Scratch block |
|---|---|
| `while True:` body | `forever` |
| `for _ in range(n):` body | `repeat` with `count` |
| `while not c:` body | `repeat_until(c)` |
| `while c:` body | `repeat_until(not c)` |
| `if c:` / `else:` | `if` / `if_else` |
| `elif c:` | nested `if` inside `else` |
| `score = 0` | `set_var("score", 0)` |
| `score += 1` / `score -= 1` | `change_var("score", 1)` / `change_var("score", -1)` |
| `vy -= g`, `speed *= 2`, `x /= 2`, `n %= 3` | `set_var` with `subtract`/`multiply`/`divide`/`mod` |
| `-vx` (computed) | `subtract(0, vx)` |
| `for _ in range(a, b):` | `repeat` with `count` `b - a` |
| `dx ** 2` (name or literal), `d ** 0.5` | `multiply(dx, dx)`, `sqrt(d)` |
| `str(x)`, `float(x)` | `x` (Scratch values are untyped) |
| bare `score` in an expression | `get_var("score")` |
| `"Score: " + score` | `join` (a string literal on either side selects `join`) |
| `a + 1`, `a - 1`, `a * 2`, `a / 2`, `a % 2` | `add`, `subtract`, `multiply`, `divide`, `mod` |
| `a < b`, `a > b`, `a == b` | `less_than`, `greater_than`, `equals` |
| `a != b` | `not(equals(a, b))` |
| `a <= b` / `a >= b` | `less_than` or `equals` / `greater_than` or `equals` (Scratch `or`) |
| `a and b`, `a or b`, `not a` | `and`, `or`, `not` |
| `move(10)`, `wait(0.2)` | a command block |
| `move(x_position() + 10)` | a reporter nested as an argument |
| `random(1, 10)` | `pick random`; both bounds positional |
| `sqrt(9)`, `abs(x)`, `round(n)` | the matching Scratch reporter |

- `range(n)` repeats `n` times and `range(a, b)` repeats `b - a` times; the
  loop variable must be `_` (Scratch `repeat` has no counter - keep your own
  counter variable when the body needs the index).
- `while c:` becomes `repeat_until(not c)`, exact because Scratch conditions
  are booleans. Loop counters are variables you initialize before the loop.
- `+=`, `-=`, `*=`, `/=` and `%=` all accept an expression.
- `not`, `and`, `or`, `if` and `for` are Python keywords: write `not a`,
  `a and b`, `a or b`; never `not(a)`, `and(a, b)` or `if(...)` as calls.
- Reporters nest freely: `turn_right(random(-20, 20))`,
  `set_x(x_position() + 5)`, `say("Score: " + score)`.
- `+` picks `add` or `join` from what it can see: a number literal, a
  numeric reporter (`y_position()`, `random(...)`, `timer()`, ...) or
  arithmetic (`vy * 2`) on either side means `add`; a string literal or a text
  reporter (`join`, `costume_name()`, `letter_of`) means `join`. A bare
  variable counts when THIS module shows its type (`vy = 0`, `vy -= 1`,
  `if vy < 3`, `name = "Bob"`). Two bare variables with no such evidence are
  ambiguous and rejected: write `add(a, b)` or `join(a, b)`. The project is
  never inspected to guess a type.
- `==`/`!=` compare as Scratch `equals`. Division is Scratch division; `//` is
  not supported.

### The Python you may NOT use

| Construct | Why / fix | What you will see |
|---|---|---|
| `import`/`from`; `class`; `lambda`; comprehensions; `try`/`except`; `return`; `global`/`nonlocal`; `with`/`assert`/`del`/`raise`/`yield`/`async`/`await` | Not in the subset. Use the dialect functions and control flow. | whitelist rejection naming the line and construct |
| plain `def`, nested `def` | One decorated script per behavior. Split it out and start it with `broadcast("name")` + `@on_receive("name")`. | `line {n}: a script def needs exactly one event decorator, for example @on_flag(target="Sprite1").` |
| indexing (`items[0]`) | Scratch lists are 1-based. Use `list_item(index, "items")`. | whitelist rejection; use `list_item` |
| attribute access (`obj.x`) | Use `attribute_of("x position", "Sprite1")` or `set_attribute_of`. | whitelist rejection; use `attribute_of` |
| f-strings (`f"{name}"`) | No f-strings. Use `"a " + name`. | whitelist rejection; use `"a " + name` |
| `break` / `continue` | No loop break. Use a flag variable and `while not flag:` (or `while flag == 0:` when the condition needs a comparison). | whitelist rejection; use a flag |
| `pass` | No empty body. Use `wait(0)` or `rest(0.1)`. | whitelist rejection naming the line and construct |
| chained comparisons (`a < b < c`) | Write `a < b and b < c`. | whitelist rejection; split the comparison |
| `True` / `False` as conditions | Use `touching(...)`, `key_pressed(...)`, `mouse_down()`, or a comparison (`flag == 1`). | rejection; use a boolean reporter |
| `None` | No null value. Omit the optional argument or use `0` / `""`. | rejection naming the construct |
| `//`, and `**` other than `name ** 2`/`** 3`/`** 0.5` | No power or floor-division block. Use `multiply`/`divide`/`sqrt` or a repeat loop. | rejection naming the operator |
| keyword args named like Python keywords | `random(from=1, to=10)` cannot parse. Call `random(1, 10)`. | Python syntax error on that line |
| `+` between two computed values | Ambiguous. Write `join(a, b)` or `add(a, b)`. | `line {n}: '+' between two computed values is ambiguous in Scratch: a + b. Write add(a, b) to add numbers or join(a, b) to build text.` |

Also rejected: using a command as a value (`set_x(move(10))`), calling an
unknown function (`draw_line(...)`), leaving a reporter alone as a statement
(`x_position()`), and using a variable that does not exist.

### Commands, reporters and variables

- A **command** is a statement on its own line; it cannot be a value. A
  **reporter** returns a value; nest it, never leave it alone. A **boolean**
  reporter is a condition for `if`, `while`, `repeat_until`, `wait_until`,
  `and`, `or` and `not`.
- Command/reporter names are catalog op names. Most reporters are callable by
  name (`add`, `join`, `less_than`), but `if`/`and`/`or`/`not`/`for` are Python
  keywords: use Python syntax for those.
- Variables are bare names: `score = 0`, `score += 1`, `say(score)`. A variable
  must exist in the context or be created earlier; assignment does not create
  it. `scope="global"` lives on the Stage; `scope="sprite"` needs `target`.
- A sprite sees its own locals plus globals, **not another sprite's local**.
  Use `attribute_of`/`set_attribute_of`/`change_attribute_of`, or broadcast to
  a script owned by that sprite. Do not name a variable after a function.
- `show_variable("score")`/`hide_variable("score")` take the name as a string.
  Initialize variables at green flag; they keep values until changed.
- Lists: create first; names are strings. Indices are **1-based**;
  `delete_from_list` also accepts `"last"`/`"all"`. Functions: `list_item`,
  `list_length`, `list_contains`, `list_item_number`, `add_to_list`,
  `insert_in_list`, `replace_in_list`, `show_list`, `hide_list`. Keep lists
  hidden unless asked.

---

## 6. Stage rules

The Stage is a target, but it is not a sprite:

- Stage scripts are background code, valid for timing, broadcasts, variables
  and backdrop changes.
- **Stage cannot move, turn, say/think, change size, show/hide, switch
  costume, or use the sprite-only `touching`, `distance_to`, `point_towards`,
  `goto_sprite`.** Use `switch_backdrop` for backdrops. For stage-driven
  coordination use variables, broadcasts and `set_attribute_of`.
- `@on_click` is sprite-only; use `@on_flag`, `@on_key` or `@on_receive` on the
  Stage. `@on_stage_click` is Stage-only.
- Stage costumes **are** the backdrops. `switch_backdrop` changes the selected
  one; `next_backdrop()` cycles; `backdrop_number()` reports the index.
- Stage-level variables are global. `show_variable`/`hide_variable` control the
  monitor.
- `pen_clear()` is valid on the Stage; the other pen functions are sprite-only.
- Sound/control/sensing/operator/variable functions are generally stage-safe;
  the catalog's `targets` field is authoritative.

---

## 7. Block semantics and gotchas

The catalog is authoritative for names, arguments, menus, hats and bodies.
These are the behavior notes it does not express.

### Events and scripts

- A script has exactly one hat from its decorator; never put a hat call in a
  body. `@on_flag` is the usual entry point.
- `@on_key("space")` uses the exact key menu (`space`, `up arrow`, ..., `a`..`z`,
  `0`..`9`).
- `@on_click` fires when that sprite is clicked (sprite-only);
  `@on_stage_click` when the Stage is clicked (Stage-only). `@on_clone_start`
  and clone lifecycle are in the `clones` pack.
- `@on_backdrop("stars")` fires when the Stage switches to it (Stage-only).
- `@on_timer(10)`/`@on_loudness(50)` start when the value crosses the
  threshold; edge-triggered once, not every frame.
- `@on_receive("go")` matches `broadcast("go")`; use short exact names
  (`start`, `caught`, `next_round`). `broadcast_and_wait("go")` waits.
- `stop_script()` stops the current script; `stop_all()` everything;
  `stop_other_scripts()` the other scripts in the same sprite.

### Control and timing

- `while True:` runs once per frame. Add `wait(0.05..0.5)` in movement loops
  for speed control and to avoid a jittery blur.
- `for _ in range(n):` takes a count; `repeat_until(c)`/`wait_until(c)` take a
  boolean reporter.
- `if`/`else` need a boolean reporter (comparison, `and`, `or`, `not`,
  `touching`, `key_pressed`, `mouse_down`, ...). `glide(seconds, x, y)`;
  `wait(seconds)`.

### Clones - the default for "many of the same thing"

Three or more similar actors (crabs, stars, coins, enemies, bricks, trees,
snowflakes) are **one template sprite plus clones**, not copy-pasted sprites
with copy-pasted scripts: fewer blocks, one script to revise, and
`touching("Coin")` sees every clone. Keep separate sprites only for distinct
characters with their own roles, or when the user asked for named sprites.

The essentials (the `clones` pack has the full semantics and patterns):

- `create_clone("myself")` copies the sprite **at that instant** - position,
  direction, size, costume, effects, visibility and its local variables. So
  stamp: move the template, set its locals, then clone; `hide()` the template
  when it is only a stamp, and `show()` first in `@on_clone_start`.
- Only `@on_clone_start` scripts start in a new clone, but `@on_receive`,
  `@on_key` and `@on_click` scripts run in every clone too: never spawn clones
  from those (one broadcast would double the population).
- Per-clone state (`speed`, `hp`, `scored`) is a sprite-local variable;
  globals are shared. A clone tests its own collisions
  (`if touching("Player"):`) and ends with `delete_clone()`.
- The green flag deletes every clone; at most 300 live, keep it to tens.

### Motion (sprites only)

- `move(steps)` moves along the direction; `turn_right(degrees)`/
  `turn_left(degrees)` turn; `point_in_direction(degrees)` sets it.
- `goto_xy(x, y)`, `set_x(x)`, `set_y(y)`, `change_x(dx)`, `change_y(dy)` are
  positions. `change_x` takes `dx` and `change_y` takes `dy`; neither takes
  `delta`.
- `bounce()` bounces off the edge; it is a command, not a reporter.
  `x_position()`, `y_position()`, `direction()` are reporters.
- `point_towards(target)`, `goto_sprite(target)`, `touching(target)`,
  `distance_to(target)` and `attribute_of(attribute, target)` accept
  `mouse-pointer`, `edge`, `Stage` where valid, or an existing sprite name
  (including one created earlier). The sprite must exist before the def.

### Looks

- `switch_costume(costume)` (sprite) and `switch_backdrop(backdrop)` (Stage)
  take the **name** exactly as in the context.
- `costume_name()`/`backdrop_name()` report the selected name;
  `costume_number()`/`backdrop_number()` report indices.
- `set_rotation_style(style)` takes `all around`, `left-right` or
  `don't rotate`.
- `go_to_back()`, `go_forward_layers(layers)`, `go_to_front()`,
  `go_back_layers(layers)` control draw order. `next_costume()` is sprite-only
  (two-frame walks); the Stage uses explicit `switch_backdrop` calls.
- `say(text)`, `say_for(text, seconds)`, `think(text)`,
  `think_for(text, seconds)` are sprite-only; the Stage cannot show a bubble.
- `set_size(percent)`/`change_size(delta)` use percent; `size()` reports it.
- Effects: `set_effect(effect, value)`, `change_effect(effect, delta)`,
  `clear_effects()`; effect menu values `color`, `fisheye`, `whirl`,
  `pixelate`, `mosaic`, `brightness`, `ghost`.

### Pen

- `pen_clear()` clears all trails on the stage and is valid on the Stage.
- `pen_down()`, `pen_up()`, `set_pen_size(size)`, `set_pen_hue(hue)` (0-100),
  `set_pen_shade(shade)` (0-100), `set_pen_color("#rrggbb")`,
  `change_pen_hue(delta)`, `change_pen_shade(delta)`, `change_pen_size(delta)`,
  `stamp()` (draws the current costume).
- Pen is global; multiple sprites can draw on the same trails.

### Sound

- `play_sound(sound)` uses an existing sound name; do not invent one. The
  harness cannot import sounds.
- `play_sound_until_done(sound)` waits; `stop_all_sounds()` stops everything.
- `play_note(note, beats)` takes note `0..127` and beats;
  `play_drum(drum, beats)`; `rest(beats)`; `set_instrument(instrument)`.
  Drum and instrument menus accept their integer index (drums `1..18`,
  instruments `1..128`) as well as the exact menu string.
- `set_volume(percent)` / `change_volume(delta)`; `volume()`.
  `set_tempo(bpm)` / `change_tempo(delta)`; `tempo()`.

### Sensing

- `ask(question)`/`answer()` blocks; use sparingly headless. `mouse_x()`,
  `mouse_y()`, `mouse_down()`; `key_pressed(key)` uses the key menu;
  `timer()`/`reset_timer()`.
- `attribute_of(attribute, target)` reads `x position`, `y position`,
  `direction`, `costume #`, `costume name`, `size`, `volume`; the Stage also
  has `background #` and `backdrop name`.
- `set_attribute_of(attribute, target, value)`/
  `change_attribute_of(attribute, target, delta)` write one.
- `touching(target)`/`distance_to(target)` are sprite-only; target
  `mouse-pointer`, `edge`, or a sprite name.
- `touching_color(color)` tests `#rrggbb` (`#ff0000` is red);
  `color_sees(color, color2)` compares two in-sprite colors.
- `current(part)` reports `year`, `month`, `date`, `day of week`, `hour`,
  `minute`, `second`; `days_since_2000()`; `username()` is `player`.
- The model cannot see the background. Use known colors or ask; do not guess
  shades. `loudness()`/`loud()` may need a microphone; avoid in scripted scenes.

### Operators and variables

- Arithmetic/comparison reporters take `any` and nest. `random(from, to)` is an
  integer; pass both positionally (`random(1, 10)`).
- `join(a, b)`; `letter_of(index, string)`; `string_length(string)`.
- `set_var("name", value)`, `change_var("name", delta)`, `get_var("name")`
  exist, but prefer bare names. `name` is a string there.
- A sprite sees its own variables plus globals, not another sprite's locals.
  **Never reference another sprite's local**; use `set_attribute_of`/
  `change_attribute_of`, or broadcast to that sprite. Do not copy the variable.
- Create a variable before use. Initialize at green flag; values persist until
  changed.

---

## 8. Current harness limits (plan around these)

| Limitation | Consequence | Workaround |
|---|---|---|
| Sprite targets must already exist | `touching`/`distance_to`/`goto_sprite` with a later sprite fail validation | Create the sprite before the def |
| No custom blocks | Cannot define new procedures | Reuse scripts with broadcasts; clones cover per-instance needs |
| Clones are runtime-only | Absent from context; cannot be targeted by name | Load `clones`; control them from the original |
| No sound import | Only existing sound names | Use context sounds or omit sound |
| No paint editor / generated art | Only library images | Use library costumes/backdrops or a preset |
| User scripts read-only | Cannot replace/delete them | Add a new AI script alongside |
| Max 3 costumes per `create_sprite` | Without a preset, at most 3 costumes | Use a preset, or `add_costume` afterwards |
| Prompt/media index budget | A long index may be trimmed | Prefer common assets and category-qualified names |
| Scratch 2.0 assets local-only | Imported `Scratch2/` media is not open source | Use locally; do not redistribute or suggest downloads |
| Stage has no motion/say/size/hide | Stage code is background-only | Put visual behavior on sprites |
| Module args are literals only | Cannot compute a position or name at apply time | Create at defaults, then set it in a green-flag script |

If a request truly needs a missing capability, make the best supported
approximation and note it in `notes(...)`; do not invent a function or menu
value.

---

## 9. Planning a large task in one prompt

1. **Scene graph.** List backdrops, actors, props, HUD variables, and which
   scripts each owns - as the `#` comment plan at the top of the module. Prefer at most ~80 blocks: code length is the visible
   budget. If the scene needs more, return a coherent core subset and put the
   rest in `notes(...)`.
2. **Media and names.** Pick a backdrop and 1-3 costumes per new sprite from
   the library index; use stems, never rename across files. Choose short unique
   sprite/variable/script labels; avoid `Stage` and reserved menu names.
3. **Order.** `set_backdrop` -> `create_variable`/`create_list` ->
   `create_sprite` -> `set_sprite` (optional) -> defs in source order. Create
   before use.
4. **Coordinate.** Use globals + `broadcast`/`@on_receive` for cross-sprite
   events. Direct `touching`/`distance_to`/`goto_sprite`/`point_towards` may
   name an existing sprite. Give each sprite one clear behavior.
5. **Reset.** The green flag must rebuild the start state every time: see
   "Reset on green flag" in section 10 - pen cleared, every changed sprite put
   back, every variable and list re-initialized.
6. **Keep scripts small.** One behavior per script; `while True:` + `wait` for
   continuous motion; `for _ in range(n):` for finite loops. Pen art is a few
   line/arc approximations, not one block per pixel.
7. **Self-check** section 12. **Return one fenced python block only.**

A useful default: a backdrop `set_backdrop`, one sprite per distinct role
(player, enemy type, collectible type), clones for every crowd of the same
thing, a global `score`, and a stage script only when the backdrop must change
on a timer.

A **game** request (score, lives, jumping, dodging, enemies, win/lose) should
load the `games` pack first, plus `clones` when it spawns pipes, bullets or
enemies; do not improvise landing physics without the pack.

---

## 10. Reusable patterns

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
| pen trails | `pen_clear()` (once, Stage or the drawing sprite), then `pen_up()` and the pen colour/size before any `pen_down()` |
| where a sprite is / faces | `goto_xy(x, y)`, `point_in_direction(d)` |
| size, costume, look | `set_size(p)`, `switch_costume("name")`, `clear_effects()` |
| visibility | `show()` or `hide()` - explicitly, both ways |
| speech | `say("")` |
| draw order | `go_to_front()` / `go_back_layers(n)` when layering matters |
| variables | `score = 0`, `lives = 3`, `game_over = 0` - every variable any script changes |
| lists | `delete_from_list("all", "queue")`, then refill |
| backdrop / timer | `switch_backdrop("start")`, `reset_timer()` (Stage) |

```python
@on_flag(target="Stage", label="reset_world")
def reset_world():
    pen_clear()
    switch_backdrop("stars")
    score = 0
    game_over = 0
    reset_timer()

@on_flag(target="Crab", label="crab_run")
def crab_run():
    goto_xy(-80, -60)
    point_in_direction(90)
    set_size(40)
    switch_costume("crab1-a")
    clear_effects()
    say("")
    show()
    while True:
        move(2)
        bounce()
        wait(0.1)
```

- **Reset at the top of the script that runs the loop**, before
  `while True:`. Two `@on_flag` scripts of one sprite start together, so a
  separate reset script races the loop. Reset each global in exactly one place
  (the Stage's flag script).
- **The start position lives in the script.** `create_sprite(x=...)` and
  `set_sprite(...)` place a sprite once, when the change applies; after a run
  or a drag only the flag script puts it back. On a revision that moves a
  starting point ("start lower", "put the cat on the left"), change the
  `goto_xy` in its reset - a `set_sprite` alone is undone by the next green
  flag.
- **A revision that adds state adds its reset**: a new variable, effect, pen
  drawing, costume change or hidden sprite gets its line in the flag script.
- Pen drawings start with `pen_clear()` unless the request is to keep drawing
  over earlier runs.

### Wander with edge bounce and costume animation

```python
@on_flag(target="Crab1", label="wander")
def crab1_wander():
    while True:
        move(2)
        turn_right(random(-20, 20))
        bounce()
        next_costume()
        wait(0.2)
```

### Backdrop cycle (Stage)

```python
@on_flag(target="Stage", label="backdrop_cycle")
def stage_backdrop_cycle():
    while True:
        switch_backdrop("stars")
        wait(2)
        switch_backdrop("beach-malibu")
        wait(2)
```

### Score HUD

Create `score` first (`create_variable("score", scope="global", initial=0)`):

```python
@on_flag(target="Sprite1", label="score_hud")
def score_hud():
    score = 0
    while True:
        say("Score: " + score)
        wait(0.2)
```

### Click-to-score

```python
@on_click(target="Star", label="caught")
def star_caught():
    score += 1
    play_sound("pop")
    goto_xy(random(-200, 200), random(-140, 140))
```

Only include `play_sound` if the sound name appears in that sprite's `sounds`
in the context; a new sprite has no sounds unless it was given some.

### List queue (with a counter and a while loop)

```python
create_variable("served", scope="global", initial=0)
create_list("queue", scope="global", items=["next", "go"])

@on_flag(target="Sprite1", label="queue_cycle")
def queue_cycle():
    served = 0
    while list_length("queue") > 0:
        say("Next: " + list_item(1, "queue"))
        delete_from_list(1, "queue")
        served += 1
        wait(0.5)
    say("Served: " + served)
```

### Broadcast start

```python
@on_flag(target="Stage", label="start")
def stage_start():
    broadcast("go")

@on_receive("go", target="Crab1", label="go")
def crab1_go():
    show()
    move(10)
```

---

## 11. Worked examples

### A. A beach with three wandering crabs (one sprite, clones)

```python
# plan: one Crab template (hidden stamp) -> 3 clones at different spots/sizes
# local speed is set before each create_clone, so every clone keeps its own
summary("Added a beach backdrop and three wandering crabs.")
set_backdrop("Nature/beach-malibu.jpg", select=True)
create_sprite("Crab", costumes=["Animals/crab1-a.png", "Animals/crab1-b.png"], size=40, rotation_style="left-right")
create_variable("speed", scope="sprite", target="Crab", initial=2)

@on_flag(target="Crab", label="spawn_crabs")
def spawn_crabs():
    hide()
    goto_xy(-120, -90)
    for _ in range(3):
        speed = random(1, 3)
        set_size(random(30, 45))
        create_clone("myself")
        change_x(120)

@on_clone_start(target="Crab", label="crab_wander")
def crab_wander():
    show()
    while True:
        move(speed)
        turn_right(random(-20, 20))
        bounce()
        next_costume()
        wait(0.2)
```

One sprite and two scripts instead of three sprites with three copied
scripts: "make the crabs faster" is now one `replace_script`, and
`touching("Crab")` sees all three. The library files are `crab1-a.png`,
`crab1-b.png` and `crab2.gif`. There is no `crab1.png`/`crab1.gif`; a costume
made from `crab2.gif` is named `crab2`, never `crab1`.

### B. Stage backdrop cycle with a timed round

```python
summary("Added a two-backdrop cycle.")
set_backdrop("Nature/stars.gif", select=True)
add_costume("Stage", "Nature/beach-malibu.jpg", select=False)

@on_flag(target="Stage", label="cycle")
def stage_cycle():
    while True:
        switch_backdrop("stars")
        wait(2)
        switch_backdrop("beach-malibu")
        wait(2)
```

### C. A single-sprite clicker with a global score

```python
summary("Added a clickable starfish and a score.")
create_variable("score", scope="global", initial=0)
create_sprite("Starfish", costumes=["Animals/starfish1-a.png"], x=0, y=0, direction=90, size=40, visible=True, rotation_style="all around")

@on_click(target="Starfish", label="caught")
def starfish_caught():
    score += 1
    goto_xy(random(-200, 200), random(-140, 140))

@on_flag(target="Sprite1", label="score_hud")
def score_hud():
    score = 0
    while True:
        say("Score: " + score)
        wait(0.2)
```

Check that `Animals/starfish1-a.png` exists in the media index before using it;
the index is authoritative.

---

## 12. Pre-flight checklist

Before returning the module, check:

- [ ] Every def has exactly one event decorator and an existing `target`.
- [ ] Sprites, variables and lists are created in the module **before** the
      defs that use them.
- [ ] Three or more similar actors are one template sprite plus clones, not
      copy-pasted sprites; clone templates `hide()` and their clones `show()`,
      and nothing reachable from a broadcast or key hat spawns clones.
- [ ] Every new def is an add, or carries `script_id` to replace; never a
      duplicate hat for the same purpose.
- [ ] Replacing a script whose current body matters has loaded that sprite this
      turn, or the body is intentionally discarded and `notes` say so.
- [ ] Stage defs use no motion, say/think, size, show/hide, or sprite-only
      sensing.
- [ ] Every variable is created or known from the context, and no script reads
      another sprite's local variable. Create each name once: a name already in
      the context or created earlier in the module is reused, never re-created.
- [ ] Every `+` with two non-literal operands is marked as `add(a, b)` or
      `join(a, b)`; the transpiler does not infer a variable's type from the
      project.
- [ ] Every `while True:` loop yields with a `wait`: `wait(0.03)` for player
      controls and physics (smooth, ~30 fps), `wait(0.1)`-`wait(0.3)` only for
      ambient animation such as a wandering crab.
- [ ] Colors are `#rrggbb` literals; menu values are exact; library paths are
      exact media-index paths with costume names from the file stem.
- [ ] Only dialect functions are called: no invented functions, no Python
      builtins other than `abs`/`round`/`sqrt`, and no placeholder values
      (`PLACEHOLDER_*`, `TBD`, `...`).
- [ ] `if`/`wait_until`/`repeat_until` conditions are boolean reporters.
- [ ] The green flag resets everything the project changes: `pen_clear()`
      before drawing; each changed sprite's position, direction, size,
      costume, effects, visibility and speech; every variable and list; the
      backdrop. Resets sit at the top of the looping script, and a revision
      that moves a start point edits that reset, not only `set_sprite`.
- [ ] Every `switch_costume`/`switch_backdrop` name exists on that target.
- [ ] The whole module is roughly 80 blocks or less and the reply is ONE
      fenced python block, ASCII, with no prose and no second object.

---

## 13. Repair guidance

If a turn fails, the bridge returns the transpiler's diagnostics with the
module. The canonical shapes are:

```text
line {n}: unknown function {name}(); use only the dialect functions in the reference.
line {n}: {op}() is a command block; it cannot be used as a value.
line {n}: {op}() is a reporter; it cannot stand alone - assign it to a variable or nest it inside another call.
line {n}: unknown variable '{name}'; create it first with create_variable("{name}", ...) or use a name from the project context.
line {n}: '{name}' is a local variable of sprite '{owner}'; another sprite cannot read it - use attribute_of/set_attribute_of or broadcast to a script owned by {owner}.
line {n}: '+' between two computed values is ambiguous in Scratch: a + b. Write add(a, b) to add numbers or join(a, b) to build text.
line {n}: a script def needs exactly one event decorator, for example @on_flag(target="Sprite1").
```

What each means:

- **unknown function** - a typo or invented op; use the exact dialect name.
- **command as value / reporter alone** - commands are statements; reporters
  must be nested or assigned.
- **unknown variable** - create it earlier, or use a context name.
- **another sprite's local** - do not copy it. Use `attribute_of`/
  `set_attribute_of`/`change_attribute_of`, or broadcast to that sprite.
- **duplicate or reserved name** - reuse an existing variable/list; a sprite
  cannot be named `Stage`, `edge` or `mouse-pointer`.
- **ambiguous `+`** - write `join(a, b)` or `add(a, b)`.
- **decorator** - every def needs exactly one; a nested/undecorated def should
  become its own script started by `broadcast` + `@on_receive`.

Fix only the quoted lines; do not rewrite the whole module unless several
scripts failed. Keep the other defs and module calls unchanged, and keep the
section 5 reply shape: one fenced python block, nothing before or after it.

After a module transpiles, the validator still runs. Its messages use the same
wording as the JSON contract (`unknown target`, `unknown costume`,
`unknown media`, `cannot be used on 'Stage'`, `read-only`, `already exists`).
Apply the same fixes: create the sprite earlier, use an exact library path, move
the block to a sprite, add a new AI script, or pick a new name.

---

## 14. Glossary

- **Stage** - the backdrop and global-variable owner; cannot move/say.
- **Sprite** - an actor with costumes, scripts and properties.
- **Costume / backdrop** - an image; Stage costumes are backdrops.
- **Script / stack** - a hat plus body blocks.
- **Hat** - the event block at the top of a script, supplied by a decorator.
- **Reporter** - a block that returns a value (oval).
- **Boolean** - a true/false reporter (hexagonal).
- **C-block** - a block with a body (`repeat`, `forever`, `if`).
- **Broadcast** - a named message that starts `@on_receive` scripts.
- **Global variable** - a Stage variable visible to every sprite.
- **Local variable** - a sprite variable visible only to that sprite.
- **List** - an ordered collection owned by the Stage or a sprite; 1-based.
- **Layer** - draw order among sprites.
- **Rotation style** - how the costume turns with direction.
- **AI-owned** - created by the harness; replaceable/deletable.
- **User script** - created by the user; read-only to the model.
- **Module-level change call** - `summary`/`set_backdrop`/`create_*` at module
  level; it becomes one entry in the change set.
- **Event decorator** - `@on_flag`, `@on_click`, and the other seven decorators
  that turn one def into one script and supply its hat.
- **Dialect function** - a catalog op written as a Python call; name and
  argument order come from the block catalog.
- **Diagnostic** - a line-precise rejection from the transpiler, quoted back on
  the repair turn.
