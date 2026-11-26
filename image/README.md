# Scratch 1.4 image setup

This folder contains the Squeak-side harness. It does four things:

For a guided UI-region map before editing the rail, see
[`../docs/UI_TOUR.md`](../docs/UI_TOUR.md).

The rail header has a **Reload UI** button (and File > Reload UI) for fast
iteration. It reloads `36_chat_ui_scratch.st`, `38_bridge_usage_ui.st` and
`37_chat_dock.st` into the running image and rebuilds the rail. It is a source
reload, not a VM restart. Load `39_ui_reload.st` once after the UI files; the
button itself is installed by `36_chat_ui_scratch.st`.

1. Docks a Scratch-styled AI chat rail into the right edge of the live Scratch
   1.4 frame (Chat / Bridge / Usage tabs).
2. Sends prompts plus a real project-context snapshot to the Python bridge,
   parses the restricted-literal reply, and applies add/replace/delete/
   createVariable change sets as real blocks.
3. Records inverse operations and can Undo the last change set.
4. Exposes a headless control server (no mouse/focus), logs every command, and
   survives relaunch without modal dialogs.

`ScratchAiTesting.image` is the maintained clean working image (latest classes,
no scripts, cat only, cleared chat, docked rail); `ScratchAI9.image` is the
previous fallback and `ScratchDev.image` is the from-source build artifact.
Rebuild the clean image with `.\tools\make_clean_image.ps1`.

## Prerequisites

- A working Scratch 1.4 source image (`Scratch.image` + `Scratch.changes`).
- The Scratch VM (`Scratch.exe`) and `SqueakV2.sources` in the same folder.
- The Scratch source image running in dev mode.

## One-time steps

> **Use the two-phase scripts.** The all-in-one `load_harness.st` is kept for
> reference, but Squeak's workspace can evaluate only the selected text, which
> caused `key not found` errors when the class definitions were not included.

1. Start Scratch with the source image.
2. Shift-click the rounded part of the **R** in the Scratch logo (the hidden
   hotspot is near the top-left of the frame).
3. Choose **turn fill screen off**.
4. Click the gray/white area at the bottom-right of the window to open the
   Squeak World menu.
5. Choose **open...** -> **workspace**.
6. Open `01_create_classes.st`, copy the entire file, paste it into the
   workspace, select all, and **do it**. This creates the two classes.
7. Open `02_compile_and_open.st`, copy the entire file, replace the workspace
   contents, select all, and **do it**. This compiles the pane and opens it.
8. A dark **Scratch AI Harness - Phase 0** pane should appear at `60@60`.
9. Click **Insert square**. The blocks should appear in the selected sprite's
   Scripts tab.
10. Click the green flag. The cat should draw a square.

## Next: bridge ping

Once the square works, save the image as `ScratchAI.image` (World menu ->
**save as...**).

Then test the local bridge:

1. Start the mock bridge in a terminal:
   ```powershell
   .\run_bridge.ps1
   ```
2. In the Squeak workspace, run `03_bridge_ping.st`.
3. It should show a dialog like:
   `Bridge replied: #(#hello-ok 'ScratchAI/1')`
4. The pane log should also show the reply.

If it says `Bridge not reachable`, make sure `run_bridge.ps1` is still running
and that nothing else is using port 8765.

## Next: literal parser

Run `06_literal_reader.st` in the workspace. It defines `AILiteralReader` and
parses a sample bridge response. Expected dialog:

```text
Parsed: #(#'hello-ok' 'ScratchAI/1')
```

If that works, the chat pane can turn bridge responses into Squeak arrays and
symbols, which is what the change-set applier needs.

## Chat UI and Send

> **Historical (session 1).** The floating dark pane described below was
> replaced in session 18 by the docked rail (`36_chat_ui_scratch.st`,
> `38_bridge_usage_ui.st`, `37_chat_dock.st`). The old class stays compiled
> but inert for compatibility. See "Session 18" and "Session 19" near the end
> of this file.

Run `07_chat_ui.st`. It opens a dark **Scratch AI Harness - Chat** pane with:

- a chat log
- an editable prompt box
- **Test input**, **Clear**, and **Close** buttons

Type something in the prompt box and click **Test input**. The log should show
`You: <your text>`. This verifies the editable text model before connecting the
Send button to the bridge.

Then run `08_chat_send.st` (with the mock bridge running). It:

- adds `AIChangeSetApplier`
- recompiles the pane with a **Send** button
- adds `AIHarness>>sendPrompt`

Type `Draw a square with the pen.` and click **Send**. The log should show the
mock summary (`Added script 'draw_square' to Sprite1 (5 blocks).`) and
`Applied. Click the green flag to try it.` The blocks appear in the Scripts tab.

Send a second prompt (`Make it bigger and say Done!`). The mock returns the
second canned response, which **replaces** `ai-1` in place: the bottom script
becomes a 200-step square ending in `say Done!`, and there are still only two
scripts.

The mock bridge has only two canned responses; restart `run_bridge.ps1` after
two requests.

## Undo

Run `09_undo.st` (or, with the loader installed, `AIHarness load: '09_undo.st'.`).
It adds an **Undo** button and an undo stack to `AIChangeSetApplier`.

- Each applied change set is one undo unit.
- `add` → undo deletes the script.
- `replace` → undo restores the previous tuple.
- `delete` → undo re-adds the old tuple.
- `createVariable` → undo removes the variable.

Verified with a valid add: scripts go 2 → 3, then Undo returns 2, removes
`test-1` from the registry, and empties the undo stack.

## Dev loader (recommended)

Paste `10_dev_loader.st` once. It installs:

```smalltalk
AIHarness load: '09_undo.st'.
```

which reads `image/<name>` with `FileStream readOnlyFileNamed:`, uses
`contentsOfEntireFile`, and calls `Compiler evaluate:`. After that, every code
change is one short line in the workspace — no more pasting whole scripts.

The loader hardcodes this machine's `image/` path; edit it if the repository
moves. Old-image notes:

- forward-slash paths are rejected; use backslashes
- `FileDirectory>>fullName` / `containingDirectory` / `respondsTo:` are missing
- `StandardFileStream>>contents` is broken; use `contentsOfEntireFile`

### Important loading notes

- Without the loader, paste with `Alt+V` rather than typing; this preserves
  quotes and line breaks exactly.
- Select all (`Alt+A`) before `Alt+D`.
- If a dialog says **Unknown selector**, the workspace is trying to compile a
  method defined in the same script. The current scripts use `perform:` for the
  final call to avoid this.
- `inputText:` must answer `true`; `PluggableTextMorph>>accept` uses its result
  as a Boolean.
- **Never use Ctrl+V.** In this image it opens the “type your initials” modal,
  which blocks the Morphic UI thread (and the control server). Use `Alt+V` for
  manual paste, or use the headless control server.

## Headless control server

`13_dev_server.st` defines a local TCP control server and a stepping dispatcher.
`14_start_server.st` starts it on a fresh image; saved images start it from
`processStartUpList`. `ScratchAI9.image` already has it, with the session-2..4
fixes below.

```powershell
python tools\ai_control.py status
python tools\ai_control.py load 09_undo.st
python tools\ai_control.py send "make the hexagon bigger"
python tools\ai_control.py undo
python tools\ai_control.py log
python tools\ai_control.py context
python tools\ai_control.py send --async "make the hexagon bigger"
python tools\ai_control.py poll <id>
python tools\ai_control.py project-export-text scratch\base\projects\demo-text
python tools\ai_control.py project-import-text scratch\base\projects\demo-text
python tools\ai_control.py save ScratchAI10
```

The Scratch window does not need focus and the mouse is not used. The server
listens on `127.0.0.1:8767`. The live bridge on `8765` must be running for
`send`; start it with `.\run_live.ps1`.

`send` returns the chat reply (summary, change lines with ids, "Applied…", or
`error: …`). Every command is logged to `scratch\base\ai_control.log`.

## Session 2: context, labels, and dialog safety

Load in this order on a fresh image:

| Script | What it does |
|---|---|
| `15_reply_context.st` | reply delta, project context in `#request`, non-modal apply errors; `scriptContextFor:`/`spriteContextFor:` are bootstrap-only fallbacks (25/28/35 own the live versions and a reload must not downgrade them) |
| `16_initials.st` | pin `Utilities` author initials (`ai`) |
| `16a_notifier.st` | `AIHarnessNotifier` + notifier-based `load:` — **superseded by 17c; do not load** |
| `17_safe_dialogs.st` | patch `Compiler`/`SyntaxError` so compile errors log and return text |
| `17b_syntax_detail.st` | include the failing method header in the logged error |
| `18_fix_literal_reader.st` | stop doubling quotes in parsed strings |
| `19_labels.st` | persist script labels; seed existing ones |
| `20_startup_fix.st` | reset the saved server flag at launch; start the watchdog; log startups |
| `21_startup_liveness.st` | probe 8767 in `startUp` so an in-place snapshot does not duplicate the server |

`16b_safe_control.st` adds command logging, the resilient `devServerLoop`, and
the heartbeat watchdog (already saved in `ScratchAI9`).

Dialogs no longer appear from our path:

- **“Please type your initials”** happens when the changes file is written with
  blank `AuthorInitials`; `openSourceFiles` blanks them when the image is
  renamed/moved. `startUp` now pins `ai` on every launch.
- **Syntax Error** windows suspend the dispatcher. `17_safe_dialogs.st` routes
  both notify paths to the log, and `AIHarness load:` returns
  `error: syntax: …`.

If a dialog does appear anyway, the control server will time out until it is
dismissed; take a screenshot to see it instead of retrying commands.

## Session 3: headless dev mode

| Script | What it does |
|---|---|
| `22_dev_config.st` | read `harness.ini`, `devMode` flag, `dev_errors.log`, startup integration |
| `23_dialog_policy.st` | log/answer every modal in dev mode; keep originals for `devMode=off` |
| `24_project_files.st` | `project open/save` by path, `doctor`/`errors`/`config`, auto-snapshot |
| `25_project_registry.st` | `<project>.sb.meta` sidecar; rebuild the AI registry by hash |

`scratch/base/harness.ini` (next to the image):

```ini
devMode=on
autoOpen=off
project=C:\...\scratch\base\projects\harness-demo.sb
autoSnapshot=off
snapshotEvery=10
errors=C:\...\scratch\base\dev_errors.log
```

- With `devMode=on` no dialog opens: informs/warns log, confirmations answer no,
  file overwrites delete silently, debugger reports log and suspend. Originals
  are saved as `devOriginal*` **before** patching, so `devMode=off` restores the
  real UI.
- `project-save` writes `.sb` + `.meta`; `project-open` restores ids/labels by
  content hash and resets Undo.
- `autoOpen=on` reopens `project=` on a fresh launch; `autoSnapshot=on`
  snapshots every N commands.
- `tools/watch_st.py` reloads `image/*.st` on change; `tools/check_st.py` should
  still be run on new scripts first.

Note: the meta sidecar is required for AI ownership after a project open; keep
`harness-demo.sb` and `harness-demo.sb.meta` together.

## Troubleshooting

### `Message not understood: stackFromTupleList:receiver:`

In the final Scratch 1.4 image this is an **instance** method, not a class
method. The current script calls `sprite stackFromTupleList: tuple receiver:
sprite`. Re-run `02_compile_and_open.st` to replace the old `installDemo`
method.

### `Message not understood: ifEmpty:`

Squeak 2.8 does not implement `Collection>>ifEmpty:`. The current scripts use
`frames isEmpty ifTrue: [...]` instead. Re-run `02_compile_and_open.st` to
replace the old `findFrame` method.

### `key not found` debugger

This means `Smalltalk at: #AIHarness...` was evaluated before the class was
created. Usually the workspace evaluated only the selected part of the script,
or the class definitions were not part of the selection.

1. Click **Abandon** in the debugger.
2. Run `01_create_classes.st` by itself first.
3. Then run `02_compile_and_open.st`.

### "unknown variable: AIHarness"

This was a Squeak workspace compile-time issue: the whole workspace is compiled
before it runs, so referring to a class that the script itself defines fails.
The current scripts avoid it by using `Smalltalk at: #AIHarness` and
`Smalltalk at: #AIHarnessPaneMorph` instead of direct class references.

If you still see the error, make sure you copied the **latest** scripts and
replaced the entire workspace contents before pressing Alt+D.

### The pane still does not appear

Run `image/diagnostic.st` in the workspace instead. It creates the pane
directly and puts it at `60@60` on the current World:

- If a dialog says `AIHarnessPaneMorph is not defined`, run
  `01_create_classes.st` first.
- If the pane appears with the diagnostic but not with `02_compile_and_open.st`,
  the issue is the `AIHarness open` frame lookup; click **Diagnose** in the pane
  and send the message it shows.

### Alt+D does nothing

Select all (`Alt+A`), then right-click (yellow button) in the workspace and
choose **do it** from the text menu. On some Windows setups the Squeak command
key is Ctrl instead of Alt, so `Ctrl+D` may also work.


## Saving the modified image

Turn fill screen off with Shift-click on the hidden R hotspot (frame `38@10`),
open the Squeak World menu from the gray strip at the bottom-right, then choose
**save as...**. Or run `Smalltalk saveAs.` from a workspace. Enter a bare name
such as `ScratchAI7`; Squeak writes both `ScratchAI7.image` and
`ScratchAI7.changes`. Keep the pristine `Scratch.image` untouched and keep each
image with its matching changes file.

## Session 4: async send, text projects, build from source

| Script | What it does |
|---|---|
| `17c_loader_fix.st` | robust `AIHarness load:` with prefixed temps; always answers `ok load` or `error:` |
| `26_async_send.st` | `#send-async`, `#poll`, background bridge worker, completion queue, apply on the dispatcher |
| `27_text_project.st` | `project export-text` / `import-text`, symbol-correct tuple literals, BMP import copies |
| `00_bootstrap.st` | installs the `bootstrap` command and the ordered file list |

**Async send.** `send --async` returns `ok send <id>` immediately;
`poll <id>` answers `pending` or the reply delta. The bridge runs model calls in
a worker thread. A pending send is dropped when the project changes, the image
snapshots, or is saved. Two sends use distinct clock-based ids.

**Text projects.** `manifest.txt`, `sprite-*.txt`, `costume-*.png`/`.bmp`,
`sound-*.wav`, and `harness.meta`. Import replaces scripts/vars/lists/media,
creates missing sprites, and restores AI ids/labels. The `.bmp` is the import
copy because this VM's PNG reader rejects some PNGs written by its own writer;
`.png` is kept for review.

**Build.** `tools\build_image.ps1 -Seed ScratchAI8 -Out ScratchDev -Force`
copies the seed, launches it, loads `00_bootstrap.st`, calls `bootstrap`, saves,
and stops. Nested `load:` from inside a file that is being evaluated does not
work; the `bootstrap` command runs in a method activation.

A warning learned the hard way: `16a_notifier.st`'s loader looks correct but in
this image it returns `ok load` without executing the file. `17c_loader_fix.st`
is the loader to keep. Do not load 16a after 17/17c.

## Session 7: sprites, stage scripts, backdrops

| Script | What it does |
|---|---|
| `28_sprites_stage.st` | `createSprite`, `duplicateSprite`, `deleteSprite`, `addCostume`, `setBackdrop`, `setSprite`, `createList`; AI sprite ownership; 8th context element; `scale:` compatibility setter; sprite/list ownership and undo |
| `29_clean_image.st` | `clean` / `save-clean` control commands: latest image with no scripts/variables, no pen trails, cat only, cleared chat |
| `30_color_tuples.st` | converts `#(#color r g b)` markers into Squeak `Color` objects for `touchingColor:`, `color:sees:` and `penColor:` |

Verified calls in this image (2009 Squeak):

- `ScratchSpriteMorph new soleCostume:`, `frame addAndView:` (registers the
  sprite and renames it, so set `objName:` afterwards), `sprite delete`.
- `sprite scalePoint: (percent / 100 @ percent / 100)` — `scale` is a percent,
  so `scalePoint: 80@80` means 8000%, not 80%. This caused a low-space crash
  while probing; use the percent setter.
- `sprite visibility: 100|0`, `heading:`, `rotationStyle: #normal|#leftRight|#none`.
- `stage addMediaItem:` + `stage lookLike: name` for backdrops.
- Media paths are relative to `scratch/base/Media` but live under
  `Costumes/` or `Backgrounds/`; the applier prefixes the folder by action.


## Session 12: block pack, hats, presets

| Script | What it does |
|---|---|
| `31_block_gaps.st` | current/days/username, costume/backdrop names, rotation style, set/change attribute, item #, show/hide list, stop-other, layers, any key. Session 12: `aiProcesses` uses `processesToRun`; `aiTopBlock` lets `stopOtherScripts` match the script owner. |
| `32_hats.st` | when stage clicked / backdrop / loudness / timer hats; event wiring; enabled condition stepping. |
| `33_clones.st` | Scratch 2.0-style clones: create/delete/hat, 300 limit, persistence, parent pointer, clone-aware `touching`. |
| `34_variable_targets.st` | target-aware sprite-scoped `create_variable` and undo; keeps old 4-element literals working. Delegates the other undo actions to the installed `28` methods instead of replacing them; load 09 → 28 → 34. |
| `35_script_detail.st` | appends AI-owned script tuples as an optional 8th context element for lazy `load_sprite` detail; sanitises colors for the literal writer. |
| `28_sprites_stage.st` | also applies optional costume rotation centres (`ImageMedia rotationCenter:`) for Scratch 2.0 sprite presets. |

Runtime checks (session 12): timer, loudness, stage-click dispatch and backdrop
hats fired through temporary stacks; `stop other scripts in sprite` stops the
other scripts owned by the sprite; preset `Dog Puppy` (copied PNG) and `0-Glow`
(SVG-rasterized) apply with correct rotation centres and undo cleanly.
`ScratchAiTesting.image` is the rebuilt clean image; `run_scratch.ps1` prefers it.

## Session 18: docked Scratch-style chat rail

| Script | What it does |
|---|---|
| `36_chat_ui_scratch.st` | `AIHarnessChatMorph` (right rail), `AIHarnessChatHistoryMorph`, `AIHarnessChatBubbleMorph`, `AIHarnessChatInputMorph`, `AIHarnessChatMessage`; Chat page, role-aware transcript, input, Scratch buttons; compatibility API (`appendLog:`, `logText`, `acceptInput`, `clearInput`, `setInputText:`). |
| `38_bridge_usage_ui.st` | Bridge and Usage pages; `#info`/`#options`/`#usage` fetch on a background fork; completion queue drained by the dispatcher; no key value shown. The Usage page's Model row has a DeepSeek / HY4 Flash Free switcher (`#selectModel`). |
| `37_chat_dock.st` | `ScratchFrameMorph>>fixLayout` with the `chatWidth` term (old body kept as `fixLayoutWithoutAIChat`); `ensureDockedChat`, File > AI Chat collapse/expand, `startUp` docking, dispatcher safety net. |
| `scratch/base/probes/probe_chat_ui_layout.st` | geometry/tabs/collapse probe (all PASS, 0 failures). |
| `scratch/base/probes/probe_chat_ui_messages.st` | roles/wrapping/scroll/200-cap/`logText`/input probe. |
| `scratch/base/probes/probe_chat_ui_bridge_usage.st` | tab/page switching, `#info`/`#options`/`#usage`, offline fallback, no-key-exposure probe. |

The rail is 352 px wide and the frame widens to 1320 px on first dock. The pane
is a `DividedImageFrameMorph` with `blocksPaletteFrameTransparent2` and
`palettePaneColor`, `ScratchTabPaneMorph` tabs with `#tabOn`/`#tabOff`, white
`ScratchTalkBubbleMorph` user cards, white `MultilineStringMorph` assistant text,
a `#typein`-framed dark input, and `buttonLabel:selector:` buttons. Send is
asynchronous. These probes live in `scratch/base/probes/`; load them by absolute
path (`ai_control.py load "C:\...\scratch\base\probes\....st"`), because a bare
relative name is resolved under `image/` and a missing file can open a modal
file chooser.

## Session 19: UI wiring fixes and Send/Stop

- `36_chat_ui_scratch.st`: tab pane filled with `palettePaneColor` (removes the
  black/stale gap after Usage); input typing hook (`lineWrapFrom:` →
  `inputChanged`); `layoutInputArea`; placeholder/growth fixes; wrapped
  Bridge/Usage fields with `#fullText`; centred status; `selectTab:`; Send/Stop
  label; status history `fitContents`; live-pane repair.
- `38_bridge_usage_ui.st`: per-page Status rows, `Refreshing...`, Ping result
  on the Bridge page, wrapped long values, Usage last-turn request delta,
  `resetUsageBaseline`.
- `37_chat_dock.st`: `ensureDockedChat` normalises to Chat/Ready and repaints.
- `26_async_send.st`: current send id, cancelled-send set, `cancelCurrentSend`,
  `sendCancelFor:`, and cancelled-completion handling in
  `applySendCompletion:`.
- `29_clean_image.st`: clean now resets pending/usage/page readouts/cancel state
  and selects Chat.
- `scratch/base/probes/probe_chat_ui_layout.st`,
  `probe_chat_ui_messages.st`, `probe_chat_ui_bridge_usage.st` were extended;
  `probe_chat_ui_cancel.st` is new.

## Session 22: whole-window parity (layout version 15)

- `37_chat_dock.st`: the native top bar spans the full 1320 px; the rail is a
  352 x 683 body pane at `968, 34`. `topPane` width is no longer reduced by
  `chatWidth`; only the body panes lose the rail width.
- `36_chat_ui_scratch.st`: frame is a native 34 x 56 composite with **no left
  edge**; the native stage/library right edge is the seam. The outer right is a
  12 px mirror of the native viewer left edge at `1308..1319`; the top-right and
  bottom-right corners are mirrored viewer corners cropped to 16 x 27. The page
  is `340 x 627` at `968, 78`, reserving 12 px right and 12 px bottom; header
  is `#959A9F`; tabs/close are at `y + 10/+12` inside the body rail.
- `probe_chat_ui_layout.st`: updated for full-width top bar, body-pane top,
  transparent left edge/native seam, 12 px mirrored outer right, page
  right/bottom reserves, header colour, and resize checks.
- `CHAT_UI_SCOPE.md`: as-built geometry is version 15 and now carries the
  native UI bible. Pre-fix audit: `docs/NATIVE_UI_BIBLE.md` and
  `docs/media/native-ui-border-audit.png`; post-fix screenshot:
  `docs/media/native-ui-border-final.png`.

## Session 23: native right edge, corners and bottom Y (layout version 17)

- `36_chat_ui_scratch.st`: the rail frame now uses the native
  `#spriteLibraryPaneFrameTransparent2` right edge (11 px) and bottom-right
  corner (21 x 27) instead of a 12 px mirror of the viewer left edge. The rail
  top-right is straight; the top bar supplies the only window top-right corner.
  `topSectionHeight` is 44, so the divider sits at the header/page boundary
  (`y=76..82`) and the native tab pane bar is restored (not transparent). The
  tab pane is drawn after the frame so the selected tab covers the divider;
  unselected tabs are covered by the bar. Page is `341 x 627` at `968, 78`;
  right reserve 11 px, bottom reserve 12 px.
- `37_chat_dock.st`: while docked, the library's own bottom-right corner is
  kept as the native 21 x 27 library corner with its outside flood-filled
  with the rail page. The unfilled native corner is restored on collapse.
  `layoutVersion` is 16.
- `probe_chat_ui_layout.st`: checks the native library right edge, page right
  `pane right - 11`, divider at `topSectionHeight` 44, tabs at `pane top + 22`,
  selected/unselected tab overlay, and the native rounded corner on the library seam.
- `docs/NATIVE_UI_BIBLE.md` §8: clean-image pixel values for the right edge,
  both right corners, the bottom section seams, the tab divider and the stage
  header internal edges, plus the version 17 audit fixes.
- Clean image re-saved as `ScratchAiTesting`; all four chat UI probes pass.
  Screenshot audit: `docs/media/harness-final-v17-frame.png`; clean native
  reference: `docs/media/native-ui-clean-frame.png`.

## Session 24: fast Reload UI button

- `36_chat_ui_scratch.st`: `ensureReloadButton` / `layoutReloadButton` create a
  72 x 18 **Reload UI** button in the rail header, left of the close button.
- `37_chat_dock.st`: File > **Reload UI** is the fallback when the rail is
  collapsed or broken.
- `39_ui_reload.st`: `processUiReloadRequest` runs on the dev dispatcher; it
  reloads 36/38/37, deletes the rail, and calls `ensureDockedChat`. The selected
  tab, input text and transcript are preserved. This is a source reload, not a
  VM restart.
- `probe_chat_ui_layout.st`: checks the button exists and clears the close
  button. `probe_chat_ui_reload.st` triggers the reload and logs
  `reload ui complete`.

## Session 26: native Scripts left edge and rounded bottom-left

- `36_chat_ui_scratch.st`: the rail left side now uses the native Scripts
  top-left corner, left edge and bottom-left corner. The left edge is 6 px
  visible at `x=968..973`; the bottom-left is a real rounded corner. The right
  side and bottom edge remain native library.
- `37_chat_dock.st`: after `nativeCornerOnLibrary`, `fixLayout` forces the rail
  to the front of the frame submorphs so native panes cannot draw over it.
- `probe_chat_ui_layout.st`: now checks the visible Scripts left edge and the
  native Scripts bottom-left corner. The old transparent-left-edge check was
  replaced.
- Visual check: `docs/media/harness-bottomleft-rail-zoom.png`.

## Session 27: 6 px rail/native overlap

- `36_chat_ui_scratch.st`: added `AIHarnessChatMorph class>>railOverlap` (6 px).
  `dockWidth` is now the 352 px native reservation; the visual rail is
  `dockWidth + railOverlap` = 358 px.
- `37_chat_dock.st`: `fixLayout` subtracts the overlap for the native column, so
  the native panes still end at `x=968`; the rail starts at `x=962` and covers
  the outer 6 px of the native library right edge.
- `probe_chat_ui_layout.st`: native-pane clear checks now allow the 6 px overlap.
- Visual check: `docs/media/harness-overlap-junction-zoom.png`.

## Session 28: straight outer corner with inner sprites fillet

- `37_chat_dock.st`: `nativeCornerOnLibrary` builds the library bottom-right
  form from the native right-edge and bottom-edge forms. The outer edge is
  square: above the bottom band only the right-edge columns are opaque, and the
  bottom 12 rows use the bottom edge across the full width.
- The old inner fillet is then copied back from the native original for rows
  0..14, left of the right edge. That restores the curve between the straight
  outer corner and the sprites page background.
- Cached as `#straightCornerWithFilletOnLibrary`; collapse still restores
  `#nativeBottomRightForm`.
- `probe_chat_ui_layout.st`: checks `#straightCornerWithFilletOnLibrary`.
- Visual check: `docs/media/harness-junction-final.png`.

## Session 29: partial-repaint draw order

- `37_chat_dock.st`: overrides `ScratchFrameMorph>>fullDrawOn:` with a
  rail-aware guard. If the damage rectangle intersects the rail, it skips the
  native-pane fast path and calls `super fullDrawOn:`, so the rail is drawn last.
  This stops partial library repaints from painting the native right edge over
  the overlapping rail left edge.
- `probe_chat_ui_layout.st`: checks `frame submorphs first == pane`.
- Visual check after a forced partial library repaint:
  `docs/media/harness-junction-partial.png`.

## Session 30: copy the Scripts right-hand corner to the sprites corner

- `36_chat_ui_scratch.st`: rail `bottomLeftForm` is **32 × 43**, with the
  expanded square-outside / round-inside Scripts curve.
- `37_chat_dock.st`: `nativeCornerOnLibrary` now copies the **Scripts pane
  bottom-right corner exactly** into the library `bottomRightForm`. The form is
  padded with 6 px of transparency on the right so the 5 px visible Scripts
  edge lands in the same strip as the visible library right edge above; the
  rail covers the padding.
- Cached as `#scriptRightCornerPaddedOnLibrary`; collapse restores
  `#nativeBottomRightForm`.
- `probe_chat_ui_layout.st`: checks the exact Scripts right-hand corner.
- Visual check: `docs/media/harness-junction-final.png`.

## Session 31: padded top-right, pristine native bottom-right

- `36_chat_ui_scratch.st`: rail `topRightForm` is now **22 × 27**: the exact
  Scripts top-right corner padded outward 6 px with the library top-right edge,
  so the 11 px rail right edge does not step at the corner.
- The rail `bottomRightForm` was reverted to the **pristine native library
  bottom-right corner** (21 × 27), copied from `#spriteLibraryPaneFrameTransparent2`.
- `probe_chat_ui_layout.st`: checks the 22 × 27 top-right corner and the
  21 × 27 pristine native bottom-right corner.
- Visual checks: `docs/media/harness-topright-final.png`,
  `docs/media/harness-bottomright-final.png`.

## What is intentionally missing

- Editing user-created scripts (read-only by design until a confirmation flow
  exists).
- Chat history in the request.
- Exact per-turn token accounting; Usage `Last turn` is the request-count delta.
- Full asset import for every PNG variant; BMP covers the round trip.
- Stopping/reconfiguring the Python bridge from the Bridge tab. **Start** is in
  place; stopping is closing the launcher console or `tools\stop_bridge.ps1`.
  Profile/audit changes still come from `run_live.ps1` flags.

## Session 32: Start the bridge from the Bridge page

- `38_bridge_usage_ui.st`: the Bridge page has a 44 x 22 **Start** button left of
  Refresh. `startBridge` forks `launchBridge`, which writes
  `scratch\base\bridge_start.cmd` (CRLF) and opens it with
  `ScratchPlugin primOpenURL:` — the VM has no process-spawn primitive. The
  script runs `run_live.ps1` when `bridge/.deepseek_key` exists (or
  `bridgeLaunch=live`), else `run_bridge.ps1` (`bridgeLaunch=mock` forces it).
  The page shows `Starting...`, polls `#info` for up to 20 s on a background
  fork, then applies the normal `#bridge` refresh through the completion queue.
  Already-running bridges are refreshed, never duplicated.
- `36_chat_ui_scratch.st`: `layoutPageButtons` places the button; the completion
  drain handles `#bridgeLaunch`. The button lives on a page property
  (`#startBridgeButton`) so a live UI reload needs no class-shape change.
- `probe_bridge_start.st`: button geometry, action and launcher content.
- Verified live: Start brought up `run_live.ps1` on 8765, the Bridge page went
  `Online`, and a second Start reused the same PID.
- `harness.ini.example`: new `bridgeLaunch=auto|live|mock` key.

## Session 33: Usage-page model switcher

- `38_bridge_usage_ui.st`: the Usage page's Model row is followed by a
  DeepSeek / HY4 Flash Free button pair. The active model gets a `*` suffix.
  `selectModelAt:` forks a short `#selectModel <index>` request; the completion
  queue runs `applyModelSwitch:` on the UI thread and refreshes the page.
  Switching is disabled (no buttons) while the bridge is offline.
- `36_chat_ui_scratch.st`: `addPageRow:` accepts a composite `Morph` row, and
  the completion drain handles `#modelSwitch`.
- Bridge: `#models` lists `(id, label)` pairs and the active id;
  `#selectModel <1-based index>` replaces the shared provider's `ModelConfig`.
  Choices live in `bridge/config.py` (`MODEL_CHOICES`) and are offered only for
  the `opencode-go` profile. `#info` and `#usage` reflect the switch at once.
- `bridge/tests/test_model_switch.py`: listing, switching, wrapper pass-through,
  bad index, disabled profiles, literal round-trip, and the unchanged
  nine-element `#info`.
- `probes/probe_model_switcher.st`: button geometry, active marker, targets,
  composite-row rebuild, and refresh (0 failures).

Headless dev mode, no-dialog logging, project files by path, registry restore,
auto-open/auto-snapshot, live `.st` reload, async send/poll, text projects, the
docked chat rail and the from-source build are in place.
