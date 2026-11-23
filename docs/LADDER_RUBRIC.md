# Phase C ladder — human rubric

**Status:** the Phase C benchmark, both halves. The automated half
(`tools\ladder.py`) measures applied-rate, repair rounds and tokens. This
document is the human half, because applied-rate does not capture whether
the resulting Scratch is any good. `HANDOFF.md` section 1a names this the
next task on the `pydsl` branch; the default flip to `generator = dsl`
waits on both halves.

Related: `PY_DSL_SCOPE.md` section 8 (the ladder definition and flip
criteria), `SCRATCH_AI_DSL_CONTEXT.md` (what the dsl mode model reads),
`TESTING.md` (the offline suite).

---

## 1. The automated half

```powershell
# wiring only: no network, no key
python tools\ladder.py --dry-run

# the real thing: 3 runs x both modes x every scenario
python tools\ladder.py -Runs 3

# focused passes
python tools\ladder.py -Runs 1 -Modes dsl
python tools\ladder.py -Runs 1 -Scenarios platformer_chain,calculator
```

Preconditions for live runs:

- `scratch\base\Media` must exist in this worktree (copy it from the main
  tree, 61 MB; HANDOFF section 1a). The tool warns when it is missing.
- The key comes from `DEEPSEEK_API_KEY` or `bridge\.deepseek_key`, exactly
  like `run_live.ps1`. It is never printed or logged.

What it does:

- Runs each scenario step through the **real agent loop** (system prompt
  with the mode-aware appendix, lazy context packs, `load_sprite`, repair
  machinery) — everything except the image's apply step.
- Chained steps see the state their predecessor built: a revision turn
  finds real script ids and `load_sprite` detail, like a live second turn.
- Writes one **full audit bundle per turn** under
  `scratch\base\audit\ladder\<stamp>` (git-ignored; prompts and raw replies
  stay local), plus `manifest.json` and `summary.json`.
- Modes are interleaved per run (json then dsl inside every run) so
  endpoint drift does not bias one mode.

Reading the results:

```powershell
python tools\audit.py score --dir scratch\base\audit\ladder\<stamp> --group generator
python tools\audit.py show scratch\base\audit\ladder\<stamp> <turn-dir>
```

`summary.json` carries a `flip_verdict` block that computes the
`PY_DSL_SCOPE.md` section-8 criteria as far as they are mechanical:
applied-rate per mode, average attempts (repair rounds), average
completion tokens, and `bad_json` final outcomes. The default flip needs
**all** of: applied-rate dsl ≥ json, repair rounds dsl ≤ json, completion
tokens per applied turn down, no `bad_json` class — **and** the rubric
below not favoring json.

---

## 2. The human half

Score one **representative ok run per mode per scenario** (the first ok
turn is the convention; note it in the log if you pick another). Two
levels, use both:

- **Bundle level (fast, always):** open the turn's
  `compiled/summary.txt` and `compiled/changeset.json`. Most items below
  are decidable there: replace-vs-add discipline, waits inside loops,
  green-flag resets, costume stems, stage legality.
- **Stage level (for the mode comparison, once per scenario):** replay the
  same prompts live through the image and watch the green flag run:

  ```powershell
  .\run_scratch.ps1                       # dev image, control server 8767
  python tools\wait_control.py
  .\run_live.ps1 -Generator <mode> -Audit full   # one bridge owns 8765
  python tools\ai_control.py send --async "<the rung prompt>" --wait
  ```

  Start each scenario from a clean Cat project. Drive the image only
  through `ai_control.py` (HANDOFF working rules). Click the green flag
  yourself and interact (arrow keys, clicks) — that is the point of the
  stage level; the bridge cannot see the stage and neither can the model.

Scoring: **0** missing or wrong, **1** works with flaws, **2** clean.
A blank cell means the run failed to apply and there is nothing to score
(that itself is ladder data; it already counts in applied-rate).

Honesty notes:

- The scorer knows which mode produced which bundle (the names say so).
  Score the bundles before re-watching the stage runs to keep the block
  level honest, and note any place where the stage changed your mind.
- Single machine, single model, one prompt phrasing per rung. Treat
  small deltas as noise; the ladder is for class-level differences.

---

## 3. Per-scenario items

### square_chain — square, then bigger_say

| # | Item | Bundle level? |
|---|---|---|
| 1 | Closed square: four sides, right angles, returns to start | bundle |
| 2 | Pen cleared first, pen up at the end (re-running the flag is clean) | bundle |
| 3 | Size sensible on the 480×360 stage | bundle |
| 4 | bigger_say: the same script is replaced (the ai-1 id, no duplicate hat) | bundle |
| 5 | bigger_say: "Done!" appears after the drawing, not during | bundle |
| 6 | The revision is a `replace_script`/`script_id` flow, not a second script | bundle |

### beach

| # | Item | Bundle level? |
|---|---|---|
| 1 | A beach backdrop is selected (a real beach image, not stars/abstract) | bundle |
| 2 | Three distinct crabs; costume stems are real files (crab1-a/crab1-b, crab2), not renamed across files | bundle |
| 3 | Wander stays on stage (bounce or bounds), no corner-stuck crabs | stage |
| 4 | Walk animation cycles costumes with a wait (no jitter blur) | bundle |
| 5 | Crabs placed in the lower half of the stage (sensible y) | bundle |

### clicker

| # | Item | Bundle level? |
|---|---|---|
| 1 | Clicking the starfish scores and it jumps to a new random spot | stage |
| 2 | The random spot stays on stage | bundle |
| 3 | Score resets to 0 at green flag | bundle |
| 4 | The score is readable (monitor or say-HUD; not spamming say without wait) | bundle |
| 5 | One clean clicker script, no decorative leftovers (unused sprites/vars) | bundle |

### platformer_chain — platformer, then revision

| # | Item | Bundle level? |
|---|---|---|
| 1 | Left/right running on arrow keys | stage |
| 2 | Up-arrow jump; gravity brings the player back down | stage |
| 3 | Lands on the floor/platforms; no falling through, no floating ascent | stage |
| 4 | Green flag resets position, direction and score | bundle |
| 5 | A score exists **and something in the game changes it** (the prompt leaves the scoring event open — note what the model chose) | bundle |
| 6 | revision: the movement script is replaced by id (load_sprite first is ideal; a blind-but-correct replace is acceptable; a duplicate add_script is a fail) | bundle |
| 7 | revision: jump is observably higher and run observably faster on stage, with the rest of the game intact | stage |

### calculator (the stress rung)

| # | Item | Bundle level? |
|---|---|---|
| 1 | Digits 0–9 exist as clickable sprites (or an equivalent working layout) | bundle |
| 2 | A display shows the current number | bundle |
| 3 | Plus/minus/multiply/divide all do something correct | stage |
| 4 | Equals computes; clear resets | stage |
| 5 | The whole thing applies at all — historically this class of request produced 33 changes, 3× `bad_json` in json mode; failures are expected data here | bundle |

---

## 4. Results log

Append a dated section per ladder session. Keep the automatic verdict
(paste from `summary.json`) **and** the rubric table. The flip decision
quotes both.

```markdown
### 2026-11-23 — <profile/model>, 3 runs x both modes

audit dir: scratch\base\audit\ladder\<stamp>
flip_verdict: json applied=..., dsl applied=..., avg attempts=...,
              avg completion=..., bad_json=...

| scenario          | json /max | dsl /max | notes |
|-------------------|-----------|----------|-------|
| square_chain      |           |          |       |
| beach             |           |          |       |
| clicker           |           |          |       |
| platformer_chain  |           |          |       |
| calculator        |           |          |       |

Stage-level observations: ...
Verdict: (flip / no flip / needs another session)
```
