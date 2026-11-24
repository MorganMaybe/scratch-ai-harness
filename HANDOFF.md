# Scratch AI Harness: handoff

**Date:** 2026-11-24
**Status:** the `pydsl` work is merged into `main`: Scratch-Python front end,
conversation memory and the reply-envelope layer all landed. 852 offline tests
pass on a fresh clone (854 with the local audit corpus).
**Repo:** https://github.com/MorganMaybe/scratch-ai-harness, a fork of
[`scratchfoundation/Scratch_1.4`](https://github.com/scratchfoundation/Scratch_1.4).
**Start here:** [`README.md`](README.md) and [`QUICKSTART.md`](QUICKSTART.md).

This is the current state of the project: what works, what doesn't, and how to
pick it up. The session-by-session record lives in
[`docs/HISTORY.md`](docs/HISTORY.md) (sessions 1–24); the session-22 raw
detail is in [`docs/HANDOFF-2026-11-15.md`](docs/HANDOFF-2026-11-15.md).

## 1. Where things stand

| Piece | State |
|---|---|
| Scratch 1.4 + harness on Windows | Working |
| Docked Chat / Bridge / Usage rail | Working |
| Change sets: scripts, vars, lists, sprites, costumes, backdrops, stage | Working |
| Undo, ownership, registry reconcile | Working |
| Lazy context packs and sprite script detail | Working |
| Python bridge, validator, compiler, providers | Working |
| **Scratch-Python front end (`generator = dsl`)** | **Built and live-verified end to end (bridge + image).** JSON stays the default until the remaining measurement (§1a) says otherwise. See `PY_DSL_SCOPE.md`, `SCRATCH_AI_DSL_CONTEXT.md`. |
| **Conversation memory (acked turns + one-line compression)** | **Working**; first live ladder A/B done, doodle-jump image replay pending (§1a) |
| **Reply-envelope layer** | **Working**; audited-corpus replay clean, live A/B folded into the measurement in §1a |
| **Release image (windowed, no control server)** | **Verified** |
| **Release bundle (stock media, no secrets)** | **Built, about 50.6 MB** |
| Tests | **852 passed, 4 skipped** on a fresh clone (media fixture, no audit corpus); **854, 2** with the local corpus |
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

## 1a. Scratch-Python front end

`generator = dsl` makes the model answer in a checked Python subset instead
of a JSON change set; the bridge transpiles it into exactly the change set the
JSON path produces. It was built and measured on the `pydsl` branch
(2026-11-16 → 2026-11-24) and is live-verified against the real image; the
dated, evidence-level detail is in `docs/HISTORY.md` sessions 21–24. Run it
with `.\run_live.ps1 -Generator dsl`. The image's Bridge tab Start button
still launches the bridge in JSON mode, so start the bridge yourself for DSL
work.

As built (one line each):

- **Transpiler** — `harness/dsl/`: vocabulary generated from the block
  `SPECS`, AST whitelist, line-precise diagnostics that quote the offending
  source line, `python -m harness.dsl.lint`, an IR renderer for
  `load_sprite` detail, the `SCRATCH_AI_DSL_CONTEXT.md` appendix, and
  `generator = json | dsl` wired through config, providers, prompts, the
  agent loop and audit.
- **Reply envelope** — `harness/dsl/envelope.py`: pure, line-based recovery
  of sloppy reply shapes (prose around the fence, a missing close,
  `summary()`/`notes()` after the closing fence, doubled fences, CRLF/BOM).
  Recoveries cost **zero repairs** (advisory `warning:` lines plus audit
  fields); a second fenced block, module-shaped code outside the fence, or a
  prose-only reply is a fatal diagnostic naming the raw line, counted as
  non-validation so the reserved validation repair still earns. The
  `stop`-sequence plumbing exists but stays off until a live ladder A/B.
- **Parse-time gates** — unknown script/sprite targets, duplicate
  variable/list/sprite names, unknown costume/sound/backdrop names and
  unresolvable library paths fail during transpile with did-you-mean hints
  instead of costing a model round trip in `validate_changeset`.
- **Repair quality** — the ambiguous-`+` diagnostic names both operands and
  the exact `add()`/`join()` rewrite; one reserved extra repair for a full
  change set that fails validation after non-validation repairs.
- **Revision fidelity** — the appendix and registry hint teach
  load-before-replace; the bridge enforces it with a **replace echo** (one
  resend with the current bodies) and a **no-op guard** for byte-identical
  replaces, with the acknowledgment reply legal end to end.
- **Conversation memory** — `harness/history.py`: a bounded ring of **acked**
  turns rendered between request and project context (the last four
  near-verbatim, older turns as one-liners) with its own trimming ladder
  (H1/H2, 2400-char cap) running ahead of the context ladder;
  `resolve_history() = off` restores byte-identical stateless prompts.
- **Advisory lints** — deterministic warnings for waitless drift, frame-rate
  flicker and never-written reads; they ride the `#result` chat lines and
  never feed a repair.
- **Known-good media tier** — `known_media.json`, mined from `ok` audit
  turns, ranks `MediaLibrary.resolve`'s near matches by verified live use.
  Regenerate with `tools\mine_media_usage.py`; `--check` fails CI on staleness.
- **Measurement tooling** — `tools\ladder.py` (scenario chains, history
  A/B, referential rungs), `docs/LADDER_RUBRIC.md`,
  `tools\revision_fidelity.py`, and `audit.py score --group generator` with
  its `envelope:` outcome class.

**Still weak — the honest part:** syntax reliability and token efficiency are
solved; **output quality is not**. The live ladder runs (both modes, 100%
applied, dsl ahead on tokens and attempts) and the first history A/B are
encouraging but thin. The open front is **measurement**: replay the
2026-11-23 doodle-jump flow through the image with `-Audit full` (build →
"make everything smaller" → "start lower"), history on and off, both modes,
scored with `tools\revision_fidelity.py` and the `CHAT_HISTORY_SCOPE.md` §5
criteria — referential words resolve against remembered values, no identical
re-apply is narrated as a change, history-on applied rate is not worse, the
section stays under budget. The same runs measure the envelope (attempts,
completion tokens, the `envelope:` score class) and gate the `stop`-sequence
flip. Then decide the `dsl` default on that evidence. Phase C (an
LLM-maintained rolling summary) stays unbuilt until the replay shows the
deterministic one-liners actually losing intent.

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
python -m pytest -q          # 852 passed, 4 skipped on a fresh clone
cd ..
python tools\check_st.py     # every image/*.st
```

`bridge\tests\conftest.py` generates a small media fixture when
`scratch\base\Media` is missing, so CI and a fresh clone don't need the runtime.
`HARNESS_MEDIA_ROOT` overrides the media root. The two envelope-corpus tests
(`test_dsl_envelope_corpus.py`) additionally skip without the local
`scratch\base\audit` corpus — see [`TESTING.md`](TESTING.md).

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
5. **The measurement matrix:** the full A/B (history on/off × both modes,
   doodle-jump replay through the image, envelope effects) has not been run.
   The tooling exists — `run_live.ps1 -Generator/-History`,
   `tools\ladder.py`, `tools\revision_fidelity.py`,
   `audit.py score --group generator`. Run it before flipping the `dsl`
   default or the `stop`-sequence flag.
6. **Trademark-safe branding** before any wide public distribution.

Also not there yet: exact per-turn token accounting (the Usage page's **Last
turn** is a request-count delta), history persistence or a wire-side reset on
project open/new (history is process-lifetime with a caveat line), and full
asset import for every PNG variant (BMP covers the round trip). The Bridge tab
can start the bridge but not stop it. Stop it by closing its launcher console,
or with `tools\stop_bridge.ps1`. Profile and audit changes still come from
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
| `PY_DSL_SCOPE.md` | Python-subset front end: built and live-verified; the dsl-default flip awaits the measurement matrix |
| `SCRATCH_AI_DSL_CONTEXT.md` | the dialect appendix (reply contract, API reference) |
| `harness/dsl/envelope.py` | reply-envelope rule matrix (docstring) |
| `tools/ladder.py` + `docs/LADDER_RUBRIC.md` | benchmark: both generators, audit bundles, history A/B, flip verdict, human rubric |
| `tools/revision_fidelity.py` | revision scorer: dropped-op diffs + load/echo classification from ladder bundles |
| `CHAT_HISTORY_SCOPE.md` | conversation history + rolling summary: Phase A+B landed; live replay pending |
| `tools/render_pack_json.py` + `tools/pack_examples.py` | context packs: canonical dialect examples, generated JSON twins, per-pack SETUP, `--check` sync |
| `tools/validate_packs.py` | offline validate/compile for the games, clones and scrolling examples |
| `CHAT_UI_SCOPE.md` | docked rail |
| `SCRATCH_2_FEATURE_AUDIT.md` | clones and BYOB audit |
| `docs/HISTORY.md` | session-by-session record (sessions 1–24) |
| `docs/SQUEAK_NOTES.md` | the Squeak and Scratch traps |
| `docs/HANDOFF-2026-11-15.md` | session-22 detailed handoff (historical) |
| `docs/UI_TOUR.md` | rail ↔ native pane map |
| `image/README.md` | Squeak-side step-by-step setup |
