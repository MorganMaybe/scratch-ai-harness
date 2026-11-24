# Project history

Chronological record of the harness. Raw session logs live in `sessions/`;
`HANDOFF.md` is the current state and deliberately does not repeat this.

| Session | Date | Headline |
|---|---|---|
| 1 | 2026-11-12 | Scratch image, chat pane, tuple blocks, bridge connection |
| 2 | 2026-11-12 | Replies over the socket, real context, labels, control server |
| 3 | 2026-11-12 | Headless dev mode, project files, no-dialog policy |
| 4 | 2026-11-12 | Async send/poll, text project format, build from source |
| 5 | 2026-11-12 | Connection Phases 1–3: profiles, lifecycle, isolation |
| 6 | 2026-11-12 | Connection Phases 4–6: observability, cancel, live gate |

Raw logs: `sessions/2026-11-12.md` (session 3),
`sessions/2026-11-12-session4.md`, `sessions/2026-11-12-session5.md`,
`sessions/2026-11-12-session6.md`.

---

## Sessions 1–2 — proof of the loop

- Scratch 1.4 source image runs on Windows with the official VM.
- Floating AI chat pane with editable prompt.
- Hardcoded tuple stack built with the native tuple API and inserted into the
  live sprite; the green flag draws a square.
- Squeak connects to the Python bridge over `MessageSocket`; `AILiteralReader`
  parses the bridge's Smalltalk literals.
- Chat Send works end to end against the mock: prompt → `#request` → `#result` →
  apply add/replace → `#applied` → `#ok`.
- `replace ai-1` removes the old stack and inserts the new one with no duplicate.
- Undo records inverse operations and works.
- Dev loader `AIHarness load: 'file.st'`; headless control server on 8767 that
  executes commands on the Morphic UI thread (no mouse/focus).
- `send` returns the chat-log delta, including validation errors.
- Every request carries the full project context; the bridge validates against
  it and re-syncs the registry each turn, so undo is reconciled automatically.
- Script labels persist (`draw_hexagon`, not `EventHatMorph`).
- Initials and Syntax Error dialogs are neutralised; control commands log to
  `scratch/base/ai_control.log`.

## Session 3 — headless dev image

- `harness.ini` (next to the image) selects dev mode; logs every modal instead
  of opening it; `project open/save` by absolute path with a `.meta` sidecar.
- Auto-open, auto-snapshot, and `tools/watch_st.py`.
- No-dialog policy for `DialogBoxMorph`, `FillInTheBlank`, `Object`,
  `PopUpMenu`, `Debugger` and file overwrite.

## Session 4 — async, text projects, build

- `26_async_send.st`: prepare on the UI thread, fork the bridge call, apply on
  the dispatcher; `status`/`undo` answer while a model call runs. Two sends in
  flight; project changes drop pending sends.
- `27_text_project.st`: export/import scripts, variables, lists, costumes and
  sounds to a git-diffable directory; AI ids, labels and ownership survive.
- `00_bootstrap.st` + `tools/build_image.ps1`: built `ScratchDev.image` from
  `ScratchAI8.image` and verified it.

## Session 5 — connection Phases 1–3

Connection scope created. Delivered:

- `config.py` + `bridge/harness.ini.example`: `opencode-go` (default),
  `deepseek-direct`, `local`, `mock`; CLI > env > ini > built-in resolution.
- `providers/`: taxonomy, OpenAI-compatible backend, mocks, factory; `llm.py`
  became a compatibility shim.
- Retries/backoff/`Retry-After`, 90 s per attempt, 240 s per turn,
  deadline-aware repair loop.
- Per-request `Agent` from each snapshot; 2 concurrent turns; `pending` ack
  cache with TTL; `#error` carries the request id.
- Key leaked in an earlier session was rotated and revoked; docs updated.
- 51 → 103 offline tests.

## Session 6 — connection Phases 4–6

- `obs.py`: redaction (`oc_sk_`, `Authorization`, `Bearer`, `sk-`, `api_key=`),
  structured `scratch/base/bridge.log`, `#info`.
- `tools/ai_control.py bridge-status` and `run_live.ps1 -LogFile/-Reuse`.
- Prompt budget (`HARNESS_PROMPT_BUDGET`, default 24 000 chars) with
  `[truncated N chars]` markers; context trimmed before the catalog.
- `#(#cancel id)` + `CancelToken` (cooperative).
- `providers/replay.py`: record/replay/cache; `--record`, `--replay`, `--cache`.
- Phase 6 live gate: 2 live tests passed; one real request (3.0 s, 2603 tokens)
  and two overlapping real requests (3.4 s wall, distinct correct results);
  logs contained no prompts or keys.
- 162 offline + 2 opt-in live tests.

## Session 7 — bad_json repair

- Live bridge log showed two model-output failures: invalid JSON at 20:08 and an
  empty response at 22:13. Both were classified `bad_json` and previously
  escaped the repair loop.
- `Agent.handle` now treats `bad_json` as repairable model output: one correction
  prompt, bounded by the normal repair/deadline budget. Auth/rate-limit/etc. still
  fail fast.
- Added tests for bad-JSON-then-good, always-bad, and auth-no-repair.
- 186 passing, 2 skipped. Live bridge restart verified; `say_hello` added in
  3.4 s / 5,968 prompt tokens, clean structured log.

## Session 8 — sprites, stage scripts, backdrops

`SPRITE_STAGE_SCOPE.md` implemented end to end (S0–S3 core):

- `bridge/src/harness/media.py`: indexes `Media/Costumes/**` and
  `Media/Backgrounds/**`, resolves `category/name.ext`/name/stem with near
  matches, and renders a budget-trimmed prompt index.
- New change actions: `create_sprite`, `duplicate_sprite`, `delete_sprite`,
  `add_costume`, `set_backdrop`, `set_sprite`; `switch_backdrop`;
  stage scripts. Ordered validation simulates the change set; AI-created
  sprites only for delete/duplicate.
- Context 8th sprite element `#(x y direction size visible rotationStyle
  aiOwned costumeIndex)`; 7-element contexts still parse.
- `image/28_sprites_stage.st`: applier actions, `SpriteOwners`, undo of delete
  (costumes/props/vars/AI scripts/labels), `.sb.meta` + text ownership,
  `scale:` compatibility setter, costume-index round-trip.
- `tools/media_index.py`, `tools/mock_scene_bridge.py`, 21+ new tests.
- Verified live: one scene prompt (bat + spin + stars), two overlapping
  requests (Bat2 + flower-bed), clean `bridge-status`/log, undo after each.
  Mock scene through `send --async` also verified, plus `.sb` save/open and text
  export/import ownership round-trips.
- 186 offline + 2 opt-in live tests.

Maintained clean image added: `29_clean_image.st` + `ai_control.py clean` /
`save-clean` + `tools/make_clean_image.ps1`. `ScratchAiTesting.image` is now the
default launch image, with no scripts, no variables/lists, only Sprite1 (the
cat) and a cleared chat log; `run_scratch.ps1` prefers it. File > Save As is
avoided because dev mode auto-answers the name prompt with the current image
name.

Probe cost: a `scalePoint: 100 @ 100` test raised the image's low-space dialog.
Killed without saving, relaunched `ScratchAI9.image`, reopened
`harness-demo.sb`; no project data lost. Trap notes 37–42 added.

## Session 9 — model context appendix

- Added `SCRATCH_AI_CONTEXT.md`: Scratch semantics, media rules, harness
  limits, large-task playbook, patterns and examples.
- `harness/context_doc.py` loads it (mtime-cached) and `Agent.handle` appends it
  to every system prompt. Each request is stateless, so this is the hook for
  persistent guidance without chat history.
- `run_live.ps1` now uses `--prompt-budget 60000` so the full appendix fits;
  a bare bridge still defaults to 24 000 and trims it with a marker.
- `tools/prompt_preview.py` reports prompt size/token estimate and writes the
  full prompt for review.
- Full media index now fits (8,008 chars); system prompt is ~45.5k chars
  (~11.4k tokens). A real request with the appendix used ~14k prompt tokens
  (up from ~5.5k), still valid JSON.
- Live quality was mixed: several `bad_json` first attempts and one 240s
  timeout, but a large calculator request failed 3× then succeeded on the next
  send (33 changes, 3,582 completion tokens, 24.6s). The next session is the
  model-quality loop (audit bundle, plan → per-script chunking).
- Tests: 190 offline + 2 live.

## Session 10 - turn auditing and raw model capture

- Added `harness/audit.py`: opt-in per-turn bundles (`--audit off|meta|full`)
  under `scratch/base/audit`. Full bundles keep the final trimmed prompts,
  project context, every model attempt's raw text, validation issues, compiled
  tuples/apply literal, and a `chunks/` manifest.
- Raw completions survive malformed JSON: `ModelReply.raw_text` and
  `ProviderError.raw_text` are populated by the OpenAI-compatible provider.
- Prompt assembly metadata records budget level, truncation markers and dropped
  chars, so a turn shows what the model actually received.
- Fixed multi-issue validation replies: they were joined with newlines, which
  `to_literal()` rejects, disconnecting the image instead of reporting issues.
  They now use one line (`"; "`), and response serialization has a final
  fallback.
- Added `tools/audit.py list|show|raw|score`; `run_live.ps1` defaults to
  `-Audit full` with `-AuditDir` / `-AuditKeep`.
- `chunks/` currently records the model's one-shot decomposition; the plan ->
  per-script chunk generator is the next model-quality change.
- Root-caused a live calculator `bad_json`: DeepSeek V4.1 Flash spent the whole
  8192 completion budget on hidden reasoning and returned empty content
  (`finish_reason=length`). `OpenAICompatProvider` now sends
  `thinking: {"type": "disabled"}` for `thinking=off`, with a compatibility
  fallback. A 16 384 output cap and 120 s attempt timeout give large scenes
  headroom; live calculator/pong/bat turns took 24.8 s / 13.8 s / 8.0 s with
  zero reasoning tokens.
- Fragment-level repair: a bad change or script is regenerated alone (prompt
  contains only the failing changes and the full-set outline), then merged and
  revalidated; broad or top-level failures fall back to a full repair.
- Sprite-name target menus: `touching`, `distance_to`, `goto_sprite`,
  `point_towards` and `attribute_of` now accept existing sprite names (created
  earlier in the same change set). Verified live through the real image:
  `createSprite MenuTarget` followed by `goto_sprite`/`point_towards`/
  `touching`/`distance_to MenuTarget` applied and undid cleanly.
- Color sensing and RGB pen color: added `touching_color`, `color_sees` and
  `set_pen_color`; colors use `#rrggbb` strings. `image/30_color_tuples.st`
  converts the bridge's `#(#color r g b)` marker into real Squeak `Color`
  objects before `stackFromTupleList:`. Verified live: `penColor: Color red`
  and `touchingColor: Color red` applied and undid cleanly.
- Block-coverage audit against the live image's `blockSpecs`: added Stage
  `next_backdrop`/`backdrop_number`, `show_variable`/`hide_variable`, Stage
  `ask`/`answer`, and canonical `showBackground:` for `switch_backdrop`;
  `pen_clear` is Stage-safe but other pen blocks are sprite-only. Lists, WeDo
  motor/sensor blocks, obsolete 1.4 blocks and most generic math functions
  remain unexposed.
- Lists: `create_list` plus `add_to_list`, `delete_from_list`,
  `insert_in_list`, `replace_in_list`, `list_item`, `list_length`,
  `list_contains`. Sprite/global list names are carried in context; creation is
  undoable. Generic math functions are exposed as `math_function`
  (abs/sqrt/trig/ln/log/e^/10^).
- Verified through the real image: create a global list with items, then a
  script using all seven list blocks and `math_function abs`; applied and undid
  cleanly.
- Tests: 236 offline + 2 live.

## Session 11 - block gaps, 2.0 hats, Scratch 2.0 assets

- Checked the claimed small-block gaps: lists and the generic math menu were
  already present; the remaining gaps were real. Added `current`,
  `days since 2000`, `username`, costume/backdrop names, rotation style,
  set/change attribute of sprite, item # in list, show/hide list,
  stop-other-scripts, go to back/forward layers, and key `any`.
  Image side: `image/31_block_gaps.st`; bridge catalog/validator/compiler+tests.
- Added `when stage clicked`, `when backdrop switches`, `when loudness >`, and
  `when timer >` hats in `image/32_hats.st`, with event wiring and enabled
  condition stepping.
- Saved the working image as `ScratchAI11`. `ScratchAiTesting` is stale and
  must be rebuilt. Tests: 239 offline + 2 live.
- Imported the Scratch 2.0 offline library locally: 370 sprite presets, 705
  sprite costumes, 472 sprite sounds, 705 costume-library assets, 103
  backdrops, 239 sounds, via `tools/scratch2_assets.py` + `resvg`. Added
  `Media/Scratch2/sprites.json` and a non-redistribution warning in
  `ATTRIBUTION.md`.
- Open: runtime hats/`stop other scripts`, the `looks` palette probe, wiring
  `preset:` into `create_sprite`, 2009 PNG compatibility, context/docs, clean
  image rebuild. Details: `sessions/2026-11-13-session11.md`.

## Session 12 - hat runtime checks, stop-other fix, presets

- Runtime-verified the timer, loudness, stage-click and backdrop hats through
  non-blocking probes; stage click was tested through the real event dispatch.
- Fixed `stop other scripts in sprite`: `aiProcesses` used a non-existent
  `processes` ivar instead of `processesToRun`, and `includesReceiver:` is dead
  in 1.4.0 (no `receiver` on stack frames). The block now matches the process's
  `aiTopBlock scriptOwner`.
- Verified every palette category with the real `blocksFor:` path; the
  session-11 `looks` failure was a wedged probe, not a bad spec.
- Wired Scratch 2.0 sprite presets into `create_sprite` (`preset: "Dog Puppy"`):
  media index/resolve, validation, compile, prompt section, schema, tests.
- Applied costume rotation centres in the image and recorded per-costume
  `rotation_center_scales` in `sprites.json` (SVG 2x vs copied bitmap 1x).
  Verified a copied PNG preset and an SVG-rasterized preset, including undo.
- Updated `SCRATCH_AI_CONTEXT.md`, rebuilt `ScratchAiTesting` clean, and made
  `run_scratch.ps1` prefer it. Tests: 244 offline + 2 live.
- Details: `sessions/2026-11-13-session12.md`.

## Session 13 - Scratch 2.0-style clones

- Finished the dormant 1.4 clone engine instead of importing BYOB:
  `image/33_clones.st` adds `create clone of [myself/other sprite]`,
  `delete this clone`, `when I start as a clone`, and the `%M` target menu.
- 2.0 semantics: 300-clone limit, clones persist until deleted/stop (the stock
  auto-delete helper is disabled), clones are runtime-only and absent from
  `sprites`/context/save, clone-aware `touching`, parent pointer through
  `#cloneParent`, clone-of-clone roots at the original.
- Fixed UTF8/String name resolution (`coerceSpriteArg:`) so AI literals like
  `"Sprite1"` resolve in this image.
- Bridge catalog/compiler/validator updated, tests added, context appendix and
  docs refreshed.
- Verified in the image: clone hat, local-variable copying, persistence,
  normal hats on clones, `touching` against a clone, clone of another sprite,
  limit, `delete this clone`, stop-all cleanup.
- Details: `sessions/2026-11-13-session13.md`.

## Session 14 - lazy context packs

- Split the always-on appendix into a core guide plus optional topic packs under
  `context/`: `clones`, `scrolling`, `pen-3d`.
- Added the `{"load_context": ["clones"]}` protocol: the agent loads the pack,
  rebuilds the system prompt, and asks for the change set. Unknown/duplicate
  names, mixed `load_context`+`changes`, and more than two loads are repaired.
- Pack text is placed before the core guide and the prompt budget is extended by
  the loaded pack size, so packs do not displace core guidance; packs are
  mtime-cached and recorded in audit metadata.
- Added `--packs`/`--list-packs` to `tools/prompt_preview.py`, context-pack
  tests and agent lazy-load tests. The core doc now points to the packs and no
  longer carries the full clone/scroll/3D guidance.
- Tests: 261 offline + 2 live. Details: `sessions/2026-11-13-session14.md`.
- Follow-up hardening: category-aware media suggestions and strict media repair
  notes (the "Nature/grass1.png" validation failure), plus target-aware
  sprite-scoped `create_variable` and undo (`34_variable_targets.st`).

## Session 15 - session-12 re-verification and undo fix

- Re-ran the session-12 checks against the real image rather than relying on
  earlier logs: palette categories build (looks 25), all four 2.0 hats fire,
  `stop other scripts` stops only its sibling, and preset sprites apply with
  correct PNG/SVG rotation centres and undo.
- Found a regression: `34_variable_targets.st` recompiled the undo methods from
  stale `09_undo` copies and erased `28_sprites_stage.st`'s sprite/costume/
  backdrop undo, so preset undo failed. 34 now delegates to the installed
  methods. Load order is 09 -> 28 -> 34.
- Added a consolidated self-cleaning hat/stop probe, an undo diagnostic, a
  backdrop cleanup probe and `tools/probe_presets.py` (generates the preset
  probe from the real bridge compile path).
- Rebuilt and re-launched `ScratchAiTesting`; verified the fixes persist.
- Details: `sessions/2026-11-13-session15.md`.

## Session 16 - lazy sprite script detail

- Revisions were blind: context carried script metadata but not blocks, so the
  model often added a second green-flag script instead of editing the existing
  one.
- `image/35_script_detail.st` appends AI-owned script tuples as an optional 8th
  context element; `harness/script_detail.py` decompiles them to change-set IR.
- Added the `load_sprite` lazy protocol: the prompt lists sprites with detail,
  and only the requested sprite's exact bodies extend the budget, mirroring
  context packs.
- Prompt rules now direct revisions to `replace_script` with the existing id and
  rebuilds to `delete_sprite` obsolete AI sprites instead of creating `Bat2`.
- Verified against the live calculator context and a clean-image round-trip;
  image rebuilt/relaunched. The calculator project was preserved as
  `scratch/base/Projects/calculator.sb`.
- Tests: 277 offline + 2 live. Details: `sessions/2026-11-14-session16.md`.

## Session 17 - validation/media hardening

- A scrolling request failed after four attempts because the model invented
  `Nature/grass1.png` (a backdrop category used as a costume) and ignored repair
  instructions.
- Media errors now suggest assets from the requested category or explain that
  the category belongs to the other library kind. Full/fragment repair prompts
  add a strict media note: exact names, no invented paths, no "swap if missing".
- `context/scrolling.md` now states there is no stock grass/ground costume.
- Fixed `chat_summary()` for 4-element preset costumes (audit summary write
  failed with "too many values to unpack").
- Sprite-scoped `create_variable` now carries its target through the apply
  literal and undo (`34_variable_targets.st` delegation preserved).
- Re-ran the same request: loaded `scrolling`, repaired ordering, applied
  successfully. Tests: 277 offline + 2 live. Details:
  `sessions/2026-11-14-session17.md`.






## Session 18 - docked Scratch-style chat rail

- Replaced the floating dark `AIHarnessChatPaneMorph` with a right rail docked
  into `ScratchFrameMorph`, implemented to `CHAT_UI_SCOPE.md`.
- New image files: `36_chat_ui_scratch.st` (rail classes, Chat page, message
  roles, `#typein` input, Scratch buttons, compatibility API),
  `38_bridge_usage_ui.st` (Bridge/Usage pages and the background fetch queue),
  `37_chat_dock.st` (`fixLayout` chatWidth term, `fixLayoutWithoutAIChat`
  rollback, `ensureDockedChat`, File > AI Chat, startup docking).
- Bridge additions: `#options` (audit mode/folder/keep, prompt budget, model
  options, log file) and `#usage` (cumulative token totals, key presence/source)
  keep the nine-element `#info` contract unchanged. 11 new tests.
- Send is now always async from the UI: `pending`/`Thinking...`, role-aware
  assistant/status/error appends, and a Bridge/Usage refresh after each turn.
- Handled old-Morphic constraints: no `show`/`hide`/`visible:`, absolute
  positions, zero-argument `ifNil:ifNotNil:`, no `removeAll`/`ifEmpty:`, and
  hidden parents still draw children (tab pages are detached).
- Verified: three new probes (layout, messages, bridge/usage) with 0 failures;
  live async sends from the Send button and the control server; undo/clear;
  resize/collapse; token usage (2 requests, 36 663 prompt / 462 completion).
- Clean image rebuilt with the rail docked; tests 288 offline + 2 live.
  Details: `sessions/2026-11-14-session18.md`.

## Session 19 - UI wiring fixes and Send/Stop

- Fixed the rail's tab strip: `ScratchTabPaneMorph` is filled with the palette
  grey, removing the black/stale gap after Usage.
- Typing now notifies the rail through `lineWrapFrom:`: the placeholder hides,
  the `#typein` frame grows with the editor, and the editor no longer extends
  under the button row.
- Bridge/Usage fields use wrapped `MultilineStringMorph`s; long endpoint,
  audit, log, error and key-source values fit the 340 px rail.
- Bridge/Usage have their own status rows: Refresh shows `Refreshing...`, Ping
  shows `Online (pong)`/`Offline (no reply)` on the Bridge page, not only on the
  detached Chat status line.
- `ensureDockedChat` normalises to Chat/Ready and repaints; `selectTab:` is the
  programmatic tab path.
- Usage `Last turn` is now a request-count delta with first-observation and
  bridge-restart resets instead of showing the cumulative total.
- The Send button becomes Stop while a turn is pending. The image records the
  current send id, marks cancellations, sends `#(#cancel <id>)`, discards a late
  completion, and appends `Status: Cancelled.`. No bridge changes.
- `cleanProject` resets pending, usage, page readouts and cancel state.
- Probes: layout/messages/bridge-usage extended; new
  `probe_chat_ui_cancel.st`; all 0 failures. Live successful send/undo and live
  Stop verified. Bridge tests unchanged at 288 passed, 2 skipped.
  Details: `sessions/2026-11-15-session19.md`.

## Session 20 - project-context downgrade repair

- Diagnosed a live revision failure: `load_sprite` was rejected for every
  sprite because the image's project context had reverted to 7 elements (no
  sprite props, no script bodies, no labels).
- Root cause: session 18 reloaded `image/15_reply_context.st` after
  `25_project_registry`/`28_sprites_stage`/`35_script_detail`, and its old
  fallback `scriptContextFor:`/`spriteContextFor:` overwrote the current
  builders. Bridge tests could not see this image-side regression.
- `15_reply_context.st` now installs those two builders only when absent
  (`includesSelector:` guards); a reload can no longer downgrade them.
- Reloaded `28` -> `34` -> `35`, saved `ScratchAiTesting`, and confirmed the
  8-element context survives a VM restart and another `15` reload.
- The live prompt now loads `KickButton`/`Ball` detail on attempt 1 and revises
  `ai-2` on attempt 2; undo restored the original script.
- Prompt hardening: `load_sprite` only for indexed sprites; a no-detail repair
  tells the model to return a change set instead of retrying. The audit now
  records the real attempt count for validation failures.
- New probe `probe_context_methods.st`; bridge suite 290 passed, 2 skipped.
  Details: `sessions/2026-11-15-session20.md`.

## Sessions 21-24 - the Scratch-Python front end (2026-11-16 to 2026-11-24)

Developed on the `pydsl` branch (17 commits from the `main` baseline),
merged back into `main` on 2026-11-24. Scope docs: `PY_DSL_SCOPE.md`
(the dialect), `CHAT_HISTORY_SCOPE.md` (memory), `SCRATCH_AI_DSL_CONTEXT.md`
(the model appendix); the session-22 raw detail is in
`docs/HANDOFF-2026-11-15.md`. Suite growth: 407 -> 852 on a fresh clone.

- **Transpiler (sessions 21-22):** `harness/dsl/` - vocabulary generated from
  the block `SPECS`, AST whitelist, line-precise diagnostics, IR renderer with
  `load_sprite` rendering, `python -m harness.dsl.lint`;
  `generator = json | dsl` through config, providers, prompts, the agent loop
  and audit. Round-trip: 143 historical audit bundles, zero mismatches (the
  16 unrenderable ones were original JSON-era model defects). Live
  (`deepseek-v4.1-flash`, dsl): every observed turn transpiled first-try with
  zero repairs - square 106, platformer 607-776, HUD 62-123 completion tokens,
  largest turn 7.8 s wall, against JSON-era ~500-3,500 tokens with frequent
  `bad_json` retries. 550 passed at that point.
- **Ladder, lints, media tier (sessions 22-23):** `tools/ladder.py` +
  `docs/LADDER_RUBRIC.md` (both generators, audit bundles, scenario chaining,
  `flip_verdict`); advisory runtime lints (`harness/lints.py`) for waitless
  drift, frame-rate flicker and never-written reads; known-good media tier
  (`tools/mine_media_usage.py`, `harness/known_media.py`, seeded 66 paths /
  147 uses) ranking `MediaLibrary.resolve` near matches by verified live use.
- **Parse-time context and media gates (2026-11-23):** unknown script
  targets, missing/unknown sprite targets on scoped calls, unknown
  costume/sound/backdrop names and unresolvable library paths fail during
  `transpile`/`lint` with did-you-mean hints instead of costing a validation
  round trip; order-aware, JSON path untouched.
- **Revision fidelity, replace echo (2026-11-23, measured):** live bundles
  showed dsl revisions replacing scripts blind (a "jump higher and run faster"
  revision dropped `touching`, `next_costume` and `set_x`). The appendix and
  registry hint now teach load-before-replace, and the bridge enforces it with
  one replace echo showing current bodies. Re-measured with
  `tools/ladder.py -Runs 3 -Scenarios platformer_chain`: 3/3 blind with 5-6
  dropped ops -> 0/3 blind, 0 dropped, ~2-3 extra attempts per revision.
- **No-op replace guard + acknowledgment replies (2026-11-23):** from the
  audited doodle-jump turn that re-sent three byte-identical scripts while
  claiming "Platforms start lower". Fully no-op turns get one guard round
  with two outs; mixed turns strip no-ops with a warning; the empty-`changes`
  acknowledgment is legal end to end in both generators.
- **Conversation history, Phase A+B (2026-11-23):** `harness/history.py` - a
  24-record ring of acked turns recorded in `_take_pending` on `#applied`,
  rendered between request and project context (4 verbatim + 8 one-liners,
  H1/H2 trimming before the context ladder, 2400-char cap),
  `resolve_history()` mirrors the generator switch. `tools/ladder.py` carries
  history across chains and takes `-History on|off`; a referential
  `start_lower` rung joined `platformer_chain`. First live A/B (dsl, one run
  each): 3/3 applied both ways, referential rung resolved with real deltas;
  history-on 1.33 attempts / 460.3 completion tokens vs 2.0 / 496.3 off,
  section 1209 chars, nothing dropped. 695 passed at that point.
- **Line-quoted DSL repairs + numeric menus (2026-11-23):** from the audited
  doodle-jump first turn (`py = py + vy` failing three times while the repair
  prompt never quoted the line). Diagnostics now carry the module text, the
  repair prompt quotes `line 34: py = py + vy` exactly, and numeric menu
  values (`play_drum(1, 0.1)`) are accepted where the image accepts indices.
  Replay of the same request applies on attempt 2.
- **Parse-time name gates + operand quoting (2026-11-24):** from the audited
  rotating-cube turn that spent its last repair on duplicate variables and a
  sprite named `Edge`. `create_variable`/`create_list`/`create_sprite`/
  `duplicate_sprite` names are gated against context and earlier module calls;
  the ambiguous-`+` diagnostic names both operands and the exact
  `add()`/`join()` rewrites. Audit data kept the literal-sugar rule: 1,015
  bare `+` in 108 DSL modules, 1,005 with a literal side, 10
  computed/computed. 714 passed.
- **One reserved repair for change-set validation (2026-11-24):** a full
  change set or module that fails `validate_changeset` earns exactly one
  extra repair when earlier repairs went to non-validation failures; all
  validation repairs keep the normal cap; fragment refinement keeps it.
  Generator-neutral. 719 passed.
- **Reply-envelope layer (2026-11-24):** the motivating evidence was attempt
  1 of the rotating-cube turn - `notes(...)` after the closing fence, the old
  `_strip_code_fences` only stripping a fence on the last line, `ast.parse`
  dying at the stray fence and hiding five real content diagnostics.
  `harness/dsl/envelope.py` is a pure line-based
  `normalize(raw) -> NormalizedReply(module_text, actions, fatal)`: prose
  before the fence is skipped, a missing close recovers at EOF,
  `summary()`/`notes()` after the close are appended as metadata, trailing
  prose is dropped, tag variants/indented or doubled fences/CRLF/BOM
  normalize; a second fenced block, module-shaped code outside the fence,
  or a prose-only reply (classified after `ast` rejects the text, so
  `import`/`class` keep their dialect diagnostics) is fatal with the raw
  line. Recoveries cost zero repairs - they ride the success as
  `warning: reply envelope: ...` lines plus audit `envelope_actions` fields;
  fatals count as non-validation so the reserved validation repair still
  earns. `audit.py score` gained an `envelope:` outcome class; the appendix
  gained an exact reply-shape template; the `stop` sequence
  (`"\n```"` on dsl completions, `HARNESS_STOP_SEQUENCE` /
  `run_live.ps1 -StopSequence`) is plumbed but off pending a live A/B.
  Verification: 105-test unit matrix, corpus replay over every DSL reply in
  `scratch/base/audit` (9 turns, 24 attempts - no fence-line syntax error
  survives; 3 envelope fatals: 2 prose-only, 1 two-block), and the cube
  attempt-1 regression now surfacing the name and ambiguous-`+`
  diagnostics. Suite 854 passed, 2 skipped with the corpus (852 + 4 skips
  on a fresh clone).

