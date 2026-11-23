# Scratch AI Harness: handoff

**Date:** 2026-11-22
**Status:** release image verified. The 407 offline tests pass on a fresh clone.
**Repo:** https://github.com/MorganMaybe/scratch-ai-harness, a fork of
[`scratchfoundation/Scratch_1.4`](https://github.com/scratchfoundation/Scratch_1.4).
**Start here:** [`README.md`](README.md) and [`QUICKSTART.md`](QUICKSTART.md).

This is the current state of the project: what works, what doesn't, and how to
pick it up. The long session-by-session history lives in
[`docs/HANDOFF-2026-11-15.md`](docs/HANDOFF-2026-11-15.md), and I've left it
alone on purpose.

## 1. Where things stand

| Piece | State |
|---|---|
| Scratch 1.4 + harness on Windows | Working |
| Docked Chat / Bridge / Usage rail | Working |
| Change sets: scripts, vars, lists, sprites, costumes, backdrops, stage | Working |
| Undo, ownership, registry reconcile | Working |
| Lazy context packs and sprite script detail | Working |
| Python bridge, validator, compiler, providers | Working |
| **Scratch-Python front end (`generator = dsl`)** | **Built on branch `pydsl`, live-verified end-to-end (bridge + image).** Output-quality iteration pending; the Phase C ladder tooling is built (`tools/ladder.py` + `docs/LADDER_RUBRIC.md`), the live measurement is not done yet; JSON stays the default. See §1a below, `PY_DSL_SCOPE.md`, `SCRATCH_AI_DSL_CONTEXT.md`. |
| **Release image (windowed, no control server)** | **Verified** |
| **Release bundle (stock media, no secrets)** | **Built, about 50.6 MB** |
| Tests | **407 passed, 2 skipped** on a fresh clone (media fixture) |
| Live model path | `opencode-go` → `deepseek-v4.1-flash` |

The Usage page's Model row also has a small switcher between the two
`opencode-go` models listed in `bridge/config.py` (`MODEL_CHOICES`). It's only
offered for that profile.

### Images

| Image | Role |
|---|---|
| `ScratchAIRelease.image` | **End-user release.** Opens in a normal 1400×900 window. The Scratch frame and rail fill the client area, with no turquoise World border. Scratch's `fillScreenOn` runs with `TakeOverScreen` off. No 8767 control server, no dev watchdog, no Reload UI. The rail has a release-only **Quit** button. Starts on a clean Cat project. |
| `ScratchAiTesting.image` | **Dev image.** Control server on 8767, dev dialog policy, Reload UI. Use `ai_control.py` and the `scope` probes here. |
| `ScratchDev.image` | Artifact of `tools\build_image.ps1`. |

Both images live in `scratch\base`, which is git-ignored. The release bundle
puts them there.

### Release mode

`image\40_release_image.st` is loaded last. It stores
`AIHarnessReleaseMode = true` and overrides `AIHarness class>>startUp`:

- skips `startDevServer` and the watchdog, and forces `devMode` to false;
- closes Squeak `SystemWindow`s and `DialogBoxMorph`s;
- calls `ScratchFrameMorph takeOverScreen: false`, then `fillScreenOn`. The
  frame fills the VM's client area and the window keeps its normal title bar.
  The Squeak Windows VM ignores the title-bar close button, which is why the
  rail has a **Quit** button and the runtime sets `EnableAltF4Quit=1`;
- keeps the async dispatcher, since chat Send depends on it;
- removes the Reload UI button;
- makes `saveReleaseAs:` clean the project, write the release pair, and defer
  the snapshot by 0.5 s so the control reply doesn't get replayed.

Build it with:

```powershell
.\tools\make_release_image.ps1 -Force
```

The builder loads `17c → 16b → 22 → 38 → 29 → 40` into a temporary copy of
`ScratchAiTesting`, so it doesn't depend on the older methods in the seed.

## 1a. Scratch-Python front end (branch `pydsl`)

All of this lives on the `pydsl` worktree branch (the sibling folder
`Scratch harness pydsl`); `main` is untouched. Run the DSL bridge from that
folder with `.\run_live.ps1 -Generator dsl` and the image from the main
folder as usual. The image's Bridge tab Start button launches the **main
folder's bridge in JSON mode** — for DSL testing, start the bridge yourself.

**Done and verified:**

- `harness/dsl/` transpiler (vocabulary generated from `SPECS`, AST
  whitelist, line-precise diagnostics), IR renderer with `load_sprite`
  dialect rendering, `python -m harness.dsl.lint`; `generator = json | dsl`
  through config, providers, prompts, the agent loop and audit; dialect
  appendix `SCRATCH_AI_DSL_CONTEXT.md`; `tools/dsl_smoke.py`;
  `tools/audit.py score --group generator`.
- Suite: 550 passed, 2 skipped (407 baseline + 143 new). Round-trip: 143
  historical audit bundles, zero mismatches; the 16 unrenderable bundles are
  original JSON-era model defects (invented ops, wrong argument names, bad
  menus) — the error classes this front end turns into parse-time rejections.
- Live (`deepseek-v4.1-flash`, dsl mode): every observed turn transpiled
  first-try with zero repairs — square 106, platformer 607–776, HUD 62–123
  completion tokens; the largest turn (11 changes plus two lazy pack loads)
  ran 7.8 s wall. JSON-era equivalents cost ~500–3,500 completion tokens
  with frequent `bad_json` retries. The platformer and triangle turns
  applied and are visible in the image; the revision flow used `script_id`
  replacement correctly once the mode-aware registry hint landed.
- **Phase C ladder tooling** (`tools\ladder.py` +
  `docs\LADDER_RUBRIC.md`): the same prompts through both generators with
  full audit bundles, scenario chaining (a revision turn sees the state its
  predecessor built, so `load_sprite`/`replace_script` are exercised),
  `manifest.json`/`summary.json` with a mechanical `flip_verdict`, and a
  per-scenario human rubric. Offline wiring test included; the suite is
  **626 passed, 2 skipped** (584 + 9 pack-dialect + 24 lint + 9 media
  ranking tests).
- **Advisory runtime lints** (`harness/lints.py`): deterministic, no model
  calls, warnings only. Flags a `forever`/`repeat_until` whose direct body
  moves the sprite with no `wait` anywhere in its subtree (drift), an
  unconditional `next_costume` at frame rate (flicker), and a newly created
  zero-initial variable read but never written in the change set or in
  AI-owned script tuples (never-written read). The canonical examples
  (key-driven motion inside `if`, the waitless spinning bat, paddle `set_x`,
  finite pen `repeat`, `switch_costume`) are deliberate exclusions. Warnings
  ride the `#result` chat lines as `warning: ...` and land in `lints.json`
  in full audit bundles; they never feed a repair.
- **Known-good media tier** (`tools\mine_media_usage.py`,
  `harness\known_media.py`, seeded `known_media.json`): `ok` audit turns are
  mined for the library references in their applied
  `create_sprite`/`add_costume`/`set_backdrop` changes, canonicalized against
  the installed media tree (so the pre-cleanup `Things/…`, `Fantasy/…` paths map
  to today's `UI/…`, `Players/…`), and rendered as a compact block beside the
  verified prop paths. `MediaLibrary.resolve`'s near matches list known-good
  paths first. With no data both consumers are exactly as before. Seed: 66
  paths, 147 uses, led by `Players/fantasy1-a.png` (20), `UI/button.gif` (8)
  and `Sports/beachball1.png` (6). Regenerate after meaningful live sessions
  with `python tools\mine_media_usage.py --dir scratch\base\audit` and commit
  the result; `--check` fails in CI when the file is stale.
- **Parse-time context and media gates** (`harness/dsl/parse.py`, 31 tests in
  `test_dsl_gates.py`): unknown script targets (`@on_flag(target="Ground")`),
  missing/unknown sprite targets on `create_variable`/`create_list` sprite
  scope, `duplicate_sprite`, `delete_sprite`, `set_sprite` and `add_costume`,
  unknown costume/sound/backdrop names in
  `switch_costume`/`play_sound`/`switch_backdrop`, and unresolvable library
  paths or sprite presets now fail during `transpile`/`lint` with line-precise
  diagnostics and did-you-mean hints instead of costing a model round trip in
  `validate_changeset`. The gates are order-aware (a sprite or costume added
  earlier in the module counts), skip cleanly without a context or an installed
  media tree, and leave the validator as defense in depth; the JSON path is
  untouched.

**Still weak — the honest part:** syntax reliability and token efficiency
are solved; **output quality is not**. Semantic quality of larger scenes
(the platformer runs but has not been critiqued), revision discipline
beyond the two observed cases, and the context packs (`games`, `clones`,
`scrolling`, `pen-3d`) are the open front. The three packs with change-set
examples are now dialect-first, with JSON twins generated from the dialect,
and the bridge filters them per generator; how much that improves pack-driven
turns is unmeasured. **The next task on this branch is running the Phase C
ladder** (`python tools\ladder.py -Runs 3`, then `tools/audit.py score
--dir <stamp-dir> --group generator`) and scoring `docs\LADDER_RUBRIC.md`
against the bundles plus one live image pass per mode (applied-rate,
repair rounds, tokens, and a human look at the resulting projects). The
default flip to `dsl` waits on that measurement.

**Runtime notes from the 2026-11-23 live session (learned the hard way):**

- The bridge console window must stay open; closing it kills the bridge.
- A fresh worktree has no `scratch\base\Media`, so the bridge builds an
  empty media/preset index and every costume reference fails validation.
  Copy `Media` from the main folder (61 MB) before live runs.
- `ScratchAiTesting.image` had gone stale — its dispatcher `step` was an
  old build, which made the Bridge tab spin on "Refreshing…", left chat
  turns completed bridge-side but never applied, while dev commands still
  answered (so the image looked healthy). Rebuilt via
  `build_image.ps1 -Out ScratchAiTesting -Seed ScratchAI11` +
  `make_clean_image.ps1`, verified with `probe_step_check.st`. Litmus when
  the tab misbehaves: load that probe and check the logged step source
  drains `processSendCompletions` and `processChatUiCompletions`.
  Immediate in-place fix: `ai_control.py load <repo>\image\38_bridge_usage_ui.st`.
- NEVER pass the same name as `-Out` and `-Seed` to `build_image.ps1` with
  `-Force`: it deletes the output (the seed) before copying it. That cost
  the old image; recovery seeds are `ScratchAI8..11` in `scratch\base`.
- Probes loaded through the dev channel must keep every statement on one
  line; multi-line message continuations silently no-op in this loader.
- The testing image's title-bar X triggers a native `Quit?!` confirm and
  hides the window; Cancel restores it. Drive the image via
  `tools\ai_control.py`, not the mouse.

## 2. Quick start (dev)

```powershell
.\setup.ps1 -Dev
.\run_scratch.ps1                 # ScratchAiTesting, control server 8767
python tools\wait_control.py
python tools\ai_control.py status
.\run_live.ps1                    # live bridge, audit off by default
# or
.\run_bridge.ps1                  # deterministic mock
```

Useful commands:

```powershell
python tools\ai_control.py send --async "make the hexagon bigger" --wait
python tools\ai_control.py undo
python tools\ai_control.py load 09_undo.st
python tools\ai_control.py doctor | errors | config | context | log
python tools\audit.py list
```

### Ports and network

- **8765**: Python chat bridge. Binds `127.0.0.1` only.
- **8767**: Squeak dev control server. The 2009 `Socket>>listenOn:` API can't
  bind loopback, so it listens on `0.0.0.0:8767` and Windows Firewall prompts.
  Don't run the dev image on an untrusted network. Set `controlServer=off` in
  `scratch\base\harness.ini` to skip it. The release image never starts it.
- Model calls are **outbound** from Python to the configured profile endpoint
  (`opencode.ai` or `api.deepseek.com`). Scratch itself never calls the model.

## 3. Model connection

Profiles live in `bridge\harness.ini`, which you create from
`harness.ini.example`:

| Profile | Model and endpoint |
|---|---|
| `opencode-go` (default) | `deepseek-v4.1-flash` at `https://opencode.ai/inference/go/openai/v1` |
| `deepseek-direct` | `deepseek-chat` at `https://api.deepseek.com` |
| `local` | Ollama or OpenAI-compatible server at `127.0.0.1:11434` |
| `mock` | offline canned scenes |

The key comes from `DEEPSEEK_API_KEY`, `OPENCODE_GO_API_KEY` or
`bridge\.deepseek_key`. It never gets written to the image, a project, a log or
a prompt.

Budgets: 120 s per attempt, 240 s per turn, 16,384 output tokens, 2 transport
retries, 2 repairs, and an 80,000-character prompt budget. Hidden reasoning is
explicitly disabled on `opencode-go`. Prefer `deepseek-v4.1-flash`, which honors
that setting.

Audit is **off** in `run_live.ps1`. Turn it on with `-Audit full` for a single
run. Bundles contain prompts and raw replies, so keep them local.

## 4. Tests

```powershell
cd bridge
$env:PYTHONPATH="src"
python -m pytest -q          # 407 passed, 2 skipped
cd ..
python tools\check_st.py     # every image/*.st
```

`bridge\tests\conftest.py` generates a small media fixture when
`scratch\base\Media` is missing, so CI and a fresh clone don't need the runtime.
`HARNESS_MEDIA_ROOT` overrides the media root.

The deterministic image path:

```powershell
python tools\mock_scene_bridge.py
python tools\ai_control.py send --async "scene test" --wait
python tools\ai_control.py undo
```

The manual release checklist is in [`TESTING.md`](TESTING.md).

## 5. Media and licensing

The public release bundle contains **stock Scratch 1.4 media only**. The
Scratch 2.0 libraries I imported locally aren't redistributed. The bundle
builder:

- excludes `Media/Scratch2`, `Media/Sounds/Scratch2` and `Costumes/Bundles`;
- drops files whose stems are listed in `tools\scratch2_only_stems.txt`;
- removes the Scratch 2.0 preset groups from the bundled `media_groups.json`;
- drops curated paths that aren't in the staged media.

The repo is GPLv2 (see `LICENSE`, `NOTICE` and `gpl-2.0.txt`). Scratch, the
Scratch logo, Scratch Cat and Gobo are trademarks, and this is an unofficial
mod. A substantially modified public build should replace the name, logo and
character art. See `TRADEMARK_POLICY`.

## 6. Working rules

1. Drive the dev image through `tools\ai_control.py`. Don't click into it or
   focus it.
2. One bridge owns 8765. Use `run_live.ps1 -Reuse`, or `tools\stop_bridge.ps1`.
3. Never Ctrl+V in the image. Use Alt+V only for a manual paste.
4. A modal wedges the dispatcher. Screenshot first, dismiss it, then retry.
5. Use the `17c_loader_fix.st` loader. `17_safe_dialogs.st` still supplies the
   dialog patches, but its older `load:` method must not be the one in use.
   Don't use the `16a_notifier.st` loader; it reports success without
   executing.
6. Run `python tools\check_st.py` before loading a changed `.st` file.
7. Never touch `Scratch.pristine.*`.
8. Keep keys out of everything: the image, projects, logs, screenshots and
   commits.
9. Rebuild the clean dev image with `.\tools\make_clean_image.ps1`.
10. Rebuild the release image with `.\tools\make_release_image.ps1 -Force`.
11. Rebuild the public bundle with
    `.\tools\make_release_bundle.ps1 -Version <x.y.z> -Force`.
12. `scratch\base\audit\`, `sessions\`, `tools\media_groups_work\` and the
    runtime media are local and git-ignored.
13. `build_image.ps1` deletes its output file before copying the seed. Never
    pass the same name as `-Out` and `-Seed` (especially with `-Force`) —
    that deletes the seed. Valid seeds are `ScratchAI8..11` in
    `scratch\base`. After any rebuild, verify with
    `probes\probe_step_check.st` (the logged step source must drain
    `processSendCompletions` and `processChatUiCompletions`).

## 7. Known gaps

What's missing, and what I'd try next, roughly in order:

1. **Editing user-created scripts with confirmation.** They're still read-only.
2. **Cross-sprite variables.** Validation rejects writing another sprite's
   local variable. That needs an appendix rule, a UI affordance, or both.
3. **Loopback control server.** Squeak 2.8 can't bind a single interface. A
   small local proxy or reverse-connect transport would remove the
   `0.0.0.0:8767` exposure and the firewall prompt.
4. **Import gaps:** sound import, `.sprite` bundle import and a sound editor.
5. **Model quality loop:** use `-Audit full`, `audit.py score`, and try a plan
   followed by per-script chunks. I haven't measured that yet. The
   `generator = json | dsl` A/B tooling now exists (`audit.py score --group
   generator`, `tools/dsl_smoke.py`, `run_live.ps1 -Generator`) but the
   Phase C ladder itself has not been run.
6. **Trademark-safe branding** before any wide public distribution.

Also not there yet: chat history in requests, exact per-turn token accounting
(the Usage page's **Last turn** is a request-count delta), and full asset
import for every PNG variant (BMP covers the round trip). The Bridge tab can
start the bridge but not stop it. Stop it by closing its launcher console, or
with `tools\stop_bridge.ps1`. Profile and audit changes still come from
`run_live.ps1` flags.

## 8. Where the detail lives

| File | What |
|---|---|
| `README.md` | overview, install, release bundle |
| `QUICKSTART.md` | tester path |
| `TESTING.md` | automated tests and the manual release checklist |
| `CONTRIBUTING.md` | dev workflow and media rules |
| `SECURITY.md` | key handling, ports, audit privacy |
| `RELEASE_NOTES.md` | what shipped in each release |
| `ARCHITECTURE.md` | design rationale and protocol |
| `SCRATCH_AI_CONTEXT.md` | model appendix sent with every prompt |
| `context/` | lazy packs: clones, games, scrolling, pen-3d |
| `SPRITE_STAGE_SCOPE.md` | sprite and stage, as built |
| `DEEPSEEK_CONNECTION_SCOPE.md` | connection package |
| `PY_DSL_SCOPE.md` | Python-subset front end: implemented (Phases A–B) with live-smoke findings; Phase C ladder pending |
| `tools/ladder.py` + `docs/LADDER_RUBRIC.md` | Phase C benchmark: both generators, audit bundles, flip verdict, human rubric |
| `tools/render_pack_json.py` + `tools/pack_examples.py` | context packs: canonical dialect examples, generated JSON twins, per-pack SETUP, `--check` sync |
| `tools/validate_packs.py` | offline validate/compile for the games, clones and scrolling examples |
| `CHAT_UI_SCOPE.md` | docked rail |
| `SCRATCH_2_FEATURE_AUDIT.md` | clones and BYOB audit |
| `docs/SQUEAK_NOTES.md` | the Squeak and Scratch traps |
| `docs/HANDOFF-2026-11-15.md` | session-22 detailed handoff (historical) |
| `docs/UI_TOUR.md` | rail ↔ native pane map |
| `image/README.md` | Squeak-side step-by-step setup |
