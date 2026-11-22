# Python front end for change sets ("Scratch-Python")

**Status:** plan, not started. Written 2026-11-22 against the release-verified
tree (407 tests passing).
**Idea:** let the model write in a language it is actually fluent in — a
**checked subset of Python** — and transpile that to the existing block IR
deterministically. No second model pass for conversion; the LLM is only a
repair loop, exactly as today.
**Target files:** bridge-side only (`bridge/src/harness/`). Zero Squeak work,
zero wire-protocol changes, zero image changes.

---

## 1. Problem

DeepSeek V4.1 Flash makes errors it should not make. The repair machinery and
the context appendix are a fossil record of those errors, and almost all of
them live at the **emission layer**, not in Scratch reasoning:

| Error class observed live | Evidence in repo |
|---|---|
| `bad_json` — braces, escapes, trailing commas in long JSON | §16 appendix note: a 33-change calculator turn failed 3× with `bad_json` before succeeding on the fourth attempt (3,582 completion tokens); the repair loop also carries a dedicated `finish_reason=length` path in `agent.py` |
| Vocabulary slips — wrong op, wrong arg name (`delta` vs `dx`/`dy`), placeholder values | `agent.py` `_delta_note`, §14 repair guidance, §13 "no placeholder" rule |
| Structure slips — nested reporter as a named block field; `wait` as a field of `forever` | `_unknown_fields_message` in `block_ir.py`, §14 "unknown block fields" |
| Ordering slips — sprite/variable referenced before creation | validator's top-down simulation; §14 "create it earlier" |
| Volume — JSON is token-noisy: `{"op":"move","args":{"steps":100}}` vs `move(100)` | output budget pressure on big turns |

The root cause: the model must produce a **bespoke JSON dialect** it never saw
in pretraining, governed by an 80k-character prompt. Fluency in that dialect is
prompt-deep, not pretraining-deep, so every op name, arg name, brace and comma
is a hallucination surface. Meanwhile the same model writes clean Python at
near-perfect syntactic reliability because that fluency is pretraining-deep.

The plan: change only **what the model writes**, not what the harness does with
it. The model writes a restricted Python subset; a deterministic transpiler
produces exactly the `ChangeSet` objects the JSON path produces today. The
validator, compiler, emitter, protocol, image, undo and registry are untouched.

---

## 2. Why Python (and not the alternatives)

| Candidate | Verdict | Reason |
|---|---|---|
| **Python subset** | **chosen** | Deepest model fluency; the bridge is Python, so the stdlib `ast` parses and validates it with line/column diagnostics for free; the dialect is real, transferable knowledge for users moving from blocks to text. |
| JavaScript | rejected for v1 | Comparable fluency, but no stdlib parser in a Python bridge (new dependency), no better fit to Scratch semantics. |
| Scratch-like pseudocode | rejected | Same problem as JSON IR: a format the model never saw in pretraining. |
| Smalltalk / tuple form | rejected | Worse than JSON; already explicitly excluded (`ARCHITECTURE.md` §4.5). |

The dialect is **checked, not trusted**: it is a subset of Python enforced by
an AST whitelist (section 5). "The model writes Python" and "the model can
write any Python" are very different claims; the design only makes the first.

---

## 3. The dialect, by example

Same turn as the current JSON contract. Today the model must emit:

```json
{
  "summary": "Beach with three wandering crabs.",
  "changes": [
    { "action": "set_backdrop", "library": "Nature/beach-malibu.jpg", "select": true },
    { "action": "create_variable", "name": "score", "scope": "global", "initial": 0 },
    { "action": "create_sprite", "name": "Crab1",
      "costumes": [{"library": "Animals/crab1-a.png"}, {"library": "Animals/crab1-b.png"}],
      "x": -100, "y": -80, "size": 40, "rotation_style": "left-right" },
    ...
  ]
}
```

In the dialect (module-level change calls take literals only — a
non-literal argument there is a lint error, not a runtime surprise):

```python
summary("Beach with three wandering crabs.")
set_backdrop("Nature/beach-malibu.jpg")
create_variable("score", scope="global", initial=0)
create_sprite("Crab1",
    costumes=["Animals/crab1-a.png", "Animals/crab1-b.png"],
    x=-100, y=-80, size=40, rotation="left-right")
```

And the *scripts*, where fluency pays off most — real Python control flow maps
onto the C-blocks (`while True:` → `forever`):

```python
@on_flag(target="Crab1", label="wander")
def crab1_wander():
    while True:
        move(2)
        turn_right(random(-20, 20))
        bounce()
        next_costume()
        wait(0.2)

@on_flag(target="Crab2", label="wander")
def crab2_wander():
    while True:
        move(2)
        turn_right(random(-20, 20))
        bounce()
        next_costume()
        wait(0.2)

@on_click(target="Star", label="caught")
def star_caught():
    score += 1                        # -> change_var("score", 1)
    play_sound("pop")
    goto_xy(random(-200, 200), random(-140, 140))

@on_receive("go", target="Crab1", label="go")
def crab1_go():
    show()
    move(10)

@on_flag(target="Sprite1", label="score_hud")
def score_hud():
    score = 0                         # -> set_var("score", 0)
    while True:
        say("Score: " + score)        # -> say(join("Score: ", get_var("score")))
        wait(0.2)
```

### Structure rules

- **Module level = the change set.** `summary(...)`, `notes(...)`,
  `set_backdrop`, `create_sprite`, `create_variable`, `create_list`,
  `add_costume`, `set_sprite`, `duplicate_sprite`, `delete_sprite`,
  `delete_script`, in any order. The transpiler executes them top-down into the
  change list, so *"create before use"* becomes *"write it before use"* — the
  ordering rule the JSON contract has to explain becomes natural code order.
- **One decorated `def` = one script.** The decorator names the hat; the
  function body is the script body. `label` defaults to the function name.
  `script_id="ai-4"` on the decorator turns it into a `replace_script`; without
  it, it is an `add_script` — matching the JSON contract's optional
  `script_id`.
- **Hats are the 9 catalog hats**: `on_flag`, `on_key("space")`,
  `on_click`, `on_stage_click`, `on_clone_start`, `on_receive("go")`,
  `on_backdrop("stars")`, `on_loudness(50)`, `on_timer(10)`.
- **Everything inside a body is a call, an assignment, or control flow** — no
  imports, no classes, no plain `def`, no comprehension, no subscript, no
  attribute access, no `return`, no `try`.
- **Control-channel replies stay JSON.** `{"load_context": ["games"]}` and
  `{"load_sprite": ["Bat"]}` are tiny and never failed in the field; only the
  big change-set reply becomes Python. The agent decides which shape it got
  before dispatching.

---

## 4. The semantic mapping table

This is the "lookup table" — but keyed on **AST nodes and the existing block
catalog**, not on lines of text. `harness/catalog.py` `SPECS` is the single
source of truth: the dialect's function names *are* the catalog op names
(`move`, `turn_right`, `change_x`, `touching`, `list_item`, ...), and argument
names/order come from each op's `ArgSpec` list. The transpiler's vocabulary
table and the prompt's API reference are both **generated from `SPECS`**, so
prompt and parser can never drift.

| Python construct | Block IR |
|---|---|
| `while True:` body | `forever` + body |
| `for _ in range(n):` body | `repeat` with `count` (loop var must be `_`, else "Scratch repeat has no loop variable" with `list_item` hint when it looks like an index) |
| `while c:` body | `repeat_until(not(c))` — deterministic inversion; also accepted |
| `while not c:` body | `repeat_until(c)` |
| `if c:` / `if c: ... else:` | `if` / `if_else` |
| `elif` chains | nested `if` inside `else:` (deterministic expansion) |
| bare call `move(10)` | command block; reporters nest as arguments: `move(x_position() + 10)` → `add(x_position, 10)` |
| `a + b`, `a - b`, `a * b`, `a / b`, `a % b` | `add`/`subtract`/`multiply`/`divide`/`mod` when operands are unambiguously numeric (number literals or known-number reporters); **a string literal on either side of `+` → `join`** (so `say("Score: " + score)` works and a Scratch-shaped `join` appears in the blocks); both operands non-literal (e.g. two variables) → reject with "write `join(a, b)` or `add(a, b)` explicitly" |
| `a < b`, `>`, `<=`, `>=`, `==` | comparison blocks |
| `a and b`, `or`, `not a` | `and`/`or`/`not` |
| `score = 0` (bare name, inside body) | `set_var("score", 0)` |
| `score += 1` / `score -= 1` | `change_var("score", 1)` / `change_var("score", -1)` |
| bare `score` in an expression | `get_var("score")` |
| `-x` | rejected in v1: write `0 - x` (open decision #3) |
| `wait(0.2)`, `wait_until(c)`, `stop_script()`, `stop_all()`, `broadcast("go")` | direct ops, one-to-one |

Everything not in this table and not a catalog call is rejected with a
**targeted, line-precise diagnostic** naming the construct and the closest
Scratch-shaped alternative:

```text
line 14: `def helper():` — custom procedures are not supported in Scratch 1.4.
  Split the behavior into its own script and start it with broadcast("name") /
  @on_receive("name").

line 22: `break` — Scratch has no loop break. Use a flag variable and
  `while not flag:` (repeat until flag).
```

These messages are what the repair pass quotes, so the second model call (when
needed) is small, local and high-yield — much cheaper than today's JSON
re-renders.

---

## 5. Limiting pass 1 to Scratch's scope — five gates

This is the answer to "how do we stop the model going outside Scratch": the
prompt *suggests*, the transpiler *enforces*, the validator *double-checks*.

1. **Parse gate.** `ast.parse` first. A syntax error is already a
   model-legible, line-precise message. (Reply format: one fenced
   ```python block; fence-stripping reuses the existing fence logic from
   `parse_json_object`'s neighborhood in `providers/base.py`.)
2. **AST whitelist gate.** Only these node types pass: `Module`, `FunctionDef`
   (with exactly one event decorator), `For` over `range`, `While`, `If`,
   `Expr(Call)`, `Assign`/`AugAssign` (bare names only), `Compare`,
   `BoolOp`, `BinOp`, `UnaryOp`, `Constant`, `Name`, `Call`, keyword args.
   Anything else — `Import`, `ClassDef`, `Lambda`, `Subscript`, `Attribute`,
   `comprehensions`, `Return`, `Break`, `Continue`, `Try`, f-strings (v1) —
   gets the did-you-mean rejection above. This is a mechanical, testable
   whitelist, not prompt discipline.
3. **Vocabulary gate.** Every called name must be a dialect function generated
   from `SPECS` (or a module-level change call). Arity, argument names, menus
   (`key`, `rotation`, `math function`, instruments...) come straight from
   `catalog.py`'s existing tables, so the menu rules the JSON validator already
   enforces are enforced *before* IR exists, with Python line numbers.
4. **Symbol gate.** A bare `Name` in a body resolves to: the loop `_`, a
   Scratch variable created earlier in the module (or present in the project
   context), or a vocabulary function. An unresolved name is "unknown variable
   'foo' — create it with create_variable first", which is the same rule the
   validator applies to JSON today (`agent.register_applied` already maintains
   the created-variable view; reuse it).
5. **Validator gate (unchanged).** The emitted `ChangeSet` runs through the
   exact same `validate_changeset` — targets exist at each point, stage
   restrictions, media resolution, block count/depth limits, sprite-local
   variable scoping, user-script read-only rules. Defense in depth: the
   transpiler catches *Python-shaped* mistakes with line numbers; the
   validator catches *project-context* mistakes exactly as now.

Prompt-side, the JSON contract, JSON examples and the pre-flight checklist
shrink to one short section: the generated API reference (name, signature,
one-line note, from `SPECS`) plus a compact "the Python you may use" list
(the section-4 table above). The appendix sections 5, 12, 13, 14 are rewritten
in the dialect; the semantics/gotchas sections (2, 7, 8, 9, 10, 11) stay,
because those are Scratch facts, not JSON facts, and the dialect does not
make the Stage able to `say`.

---

## 6. Answers to the three design questions

**Intermediary language?** Python — the checked subset above, generated from
the existing catalog so there is exactly one vocabulary to maintain.

**Conversion by lookup table?** Yes, but structural, not textual: a
table-driven AST transpiler. A line-by-line text lookup would be brittle
(formatting, nesting, complex expressions); an AST walk is robust, exact,
offline, free and instant (~ms). The mapping table is new metadata beside
`SPECS`: op → (dialect signature, arg order, kind). The prompt's function
reference renders from the same metadata, so the model is always looking at
what the transpiler actually accepts.

**A second DeepSeek pass?** Not for conversion. An LLM converting Python →
blocks would reintroduce the JSON emission failure class we are removing, add a
120 s attempt against the 240 s turn budget, and can silently drop behavior.
The deterministic transpiler is strictly better on every axis. The LLM's second
pass remains what it is today — **repair** — but the repair prompts become far
cheaper: quote the diagnostic lines, ask for a corrected block of Python, or
fall back to fragment repair (the existing `_FRAGMENT_LIMIT = 3` machinery
maps cleanly onto "rewrite these defs"). An optional semantic-review LLM pass
(no-wait-in-forever warnings, game-feel checks) is deliberately *not* proposed:
known rules belong in a deterministic linter (phase E), and the `games`/
`clones` packs already carry the judgment parts.

---

## 7. What this does not fix (be honest in the A/B)

- **Media-name errors** — wrong library path/stem stays a prompt-index problem.
- **Semantic Scratch mistakes** — no `wait` in a `forever`, wrong axis for
  `direction`, edge-triggered hat confusion, off-by-one list indices (Scratch
  lists are 1-based; the dialect keeps `list_item(1, "queue")` explicit rather
  than inventing 0-based sugar).
- **Concurrency-model misunderstandings** — one def = one script helps, but
  "scripts run in parallel" remains an appendix fact.
- **Ambition overflow** — a 200-block request still won't fit the turn budget;
  the module makes the budget visible as code length, which may itself help
  the model self-trim.

The A/B in section 8 measures exactly these boundaries rather than assuming
the fix is total.

---

## 8. Rollout and measurement

Everything lands behind one switch, mirroring the profile/model-switch
patterns the bridge already has:

- `harness.ini`: `generator = json | dsl` (default `json` until the ladder says
  otherwise). The agent's reply parser branches on it: JSON path stays exactly
  as-is (mock scenes, replay recordings, canned tests keep working).
- `mock` provider gains canned **DSL** replies so the offline path
  (`tools\mock_scene_bridge.py`) runs end-to-end in both modes.
- Audit bundles: `attempts/NN/raw.txt` stores the Python source; add
  `attempts/NN/dsl.json` with transpile diagnostics; `parsed.json` stores the
  emitted change set as today, so `tools\audit.py` keeps reading bundles.
- `tools\audit.py score --compare json dsl`: per-turn metrics already
  derivable from bundles — `bad_json` rate, validation-error classes, repair
  rounds used, completion tokens, wall time, applied/not-applied. This is
  HANDOFF known-gap 5 (the unmeasured quality loop) with the A/B built in.

**The ladder** (same prompts, both modes, `-Audit full`, ≥3 runs each):
square → bigger+say → three-crab beach scene → clicker with score →
platformer (with `games`/`clones` pack loads) → a revision flow
(`load_sprite` then `replace_script`) → the historical calculator request that
failed 3× with `bad_json`.

**Success criteria to flip the default:** no `bad_json` class at all; repair
rounds per successful turn ≤ today's; applied-rate on the ladder ≥ JSON mode;
completion tokens per applied turn down (expected: `move(100)` vs
`{"op":"move","args":{"steps":100}}` cuts body-token noise by roughly half,
which also relieves `finish_reason=length` on large turns).

---

## 9. Read path: the dialect must be bidirectional on day one

Revision flows read existing scripts through `load_sprite`
(`script_detail.py` renders tuples → IR → compact JSON today). If the model
reads JSON but writes Python, revisions will straddle two dialects — awkward
exactly where precision matters most. So the first release also ships
`render.py`: IR → dialect text, deterministic, reusing `decompile_script`.
The loaded detail for a sprite becomes:

```python
# Sprite detail: "Crab1" (AI-created sprite; costumes=crab1-a, crab1-b)
# ai-1 "wander" [when_flag_clicked] 7 blocks (ai-owned, editable)
@on_flag(target="Crab1", label="wander")
def crab1_wander():
    while True:
        move(2)
        turn_right(random(-20, 20))
        ...
```

and the model answers with `@on_flag(script_id="ai-1", ...)` to replace it.
This also unlocks a cheap, strong regression test:
**round-trip** — for every compiled change set (including golden scripts and
historical audit bundles), `transpile(render(ir)) == ir`. Any drift between
the mapping table and the renderer shows up as a test failure, not as a
model-facing lie.

---

## 10. Phases

Rough, assuming the repo's current conventions (offline tests first, live
runs through `tools\ai_control.py`).

### Phase A — the dialect as a library (3–5 dev days)

- `harness/dsl/`: `vocab.py` (op → signature table + prompt reference
  renderer, generated from `SPECS`), `parse.py` (AST whitelist walker →
  `ChangeSet`), `render.py` (IR → dialect, for detail + round-trip),
  `errors.py` (diagnostic type carrying line/col + hint).
- CLI: `python -m harness.dsl.lint file.py` for offline checks against
  golden scripts.
- Tests: golden Python → IR; round-trip over all golden scripts **and** over
  every successful change set in existing audit bundles (retroactive
  coverage); every rejection path has a message test.
- No agent changes; JSON path untouched; suite stays green.

### Phase B — agent integration behind the switch (2–3 dev days)

- `generator = json | dsl` in `harness.ini`; reply branch in `Agent.handle`
  (control-channel JSON replies are detected first and unchanged).
- Prompt variant: generated API reference + "the Python you may use" replaces
  the JSON contract/examples; appendix sections rewritten in dialect.
- Repair prompt variant that quotes diagnostic lines; fragment repair mapped
  to "rewrite these defs".
- Mock provider DSL canned replies; audit writes `raw.txt` + `dsl.json`.
- Agent tests parameterized over both modes.

### Phase C — live A/B (1–2 dev days + ladder runs)

- Run section 8's ladder both modes with `-Audit full`; score with
  `tools\audit.py score --compare`. Iterate the appendix (the §16 note
  already suspects the appendix is too long; the dialect version should be
  smaller).

### Phase D — default flip (1 dev day)

- `generator = dsl` default; JSON stays accepted for one release (replay
  compat, escape hatch); docs updated (`SCRATCH_AI_CONTEXT.md` becomes a
  dialect document; `ARCHITECTURE.md` §4.5's "The LLM never sees Smalltalk"
  gains "it never emits JSON either").

### Phase E — data-driven sugar (ongoing, only what audits demand)

Candidates in priority order, each deterministic and round-trip tested:
f-strings with simple `{name}` slots → `join` chains; `for _ in range(a, b)`
→ `repeat(b - a)`; comparison chaining → `and` of comparisons;
`forever_if(c)` shorthand (`while True: if c:` already covers it — only add
if audits show the model reaching for it); deterministic lints
(forever-without-wait warning, uninitialized-read warning) surfaced through
the same diagnostic channel.

---

## 11. Open decisions

1. **Bare-name variables (`score += 1`) vs explicit (`change_var("score", 1)`).**
   Bare names are the biggest fluency win and the recommendation, but they
   make `set_var`'s *value* a bare-name read (`score = timer` → set score to
   timer) — fine — while `name`-as-string APIs (`delete_from_list`) still take
   strings. Both exist in v1: bare names for variables, strings for list names;
   the reference doc makes the split explicit. Cheap to reverse later because
   the transpiler, not the model, is the surface.
2. **`while c:` inversion.** Proposed: accept and expand to
   `repeat_until(not c)`. Alternative: reject with "invert the condition".
   Decide from ladder data; expansion is safe either way.
3. **Unary minus.** `-x` → `subtract(0, x)` is exact but writes odd blocks;
   rejecting pushes `0 - x`, which is what a Scratch author would write.
   Lean reject; revisit with audits.
4. **`elif` vs explicit nesting.** Proposed: accept and expand (deterministic,
   matches how a Scratch author would nest if/else). Low risk.
5. **String concatenation ambiguity** (section 4): literals decide, otherwise
   require explicit `join`/`add`. Keeps the transpiler honest without a type
   system; revisit only if ladder repairs show friction.
6. **Where `summary()`/`notes()` live.** Proposed: dialect calls at module
   top. Alternative: `# summary:` pragma comments (costs a `tokenize` pass);
   calls are simpler and already in the whitelist.

---

## 12. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Model writes out-of-subset Python; rejections burn attempts | Failed turns | did-you-mean diagnostics; short "may use" prompt section; ladder measures rejection rate before any default flip; repair rounds stay capped as today |
| Dialect renders back unclearly for revisions | Bad replace_script edits | `render.py` ships in phase A/B, not later; round-trip tests over bundles |
| Vocabulary table drifts from catalog | Prompt/parser disagree | Both generated from `SPECS`; drift is a test failure, not a behavior |
| JSON path bit-rots while behind the flag | Lost fallback/A-B | Agent tests parameterized over both modes from day one |
| Sugar grows unprincipled | Transpiler complexity | Phase E requires audit evidence per addition |
| Semantics the dialect cannot express (list mutation by index in a loop, strings as arrays) | Model frustration | Rejections point at the real block (`list_item`, `letter_of`); appendix sections 8/9 keep teaching the Scratch way |
| We optimize emission but packs/appendix still mislead | Partial win | Section 7 lists what won't move; A/B reports those classes separately |
