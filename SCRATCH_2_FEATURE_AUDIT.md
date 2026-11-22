# Scratch 2.0 Feature Audit — Clones, BYOB, and the Rest

**Date:** 2026-11-13  
**Status (session 13):** core 2.0-style clones are **implemented** —
`image/33_clones.st` plus bridge catalog/compiler/validator. The plan below is
kept as the design record; remaining work is stress/performance and live
verification, not core wiring.
**Scope:** the AI harness in this repo (Scratch 1.4 Squeak image + Python bridge), not a
general Scratch mod.  
**Question:** how hard is it to implement Scratch 2.0-style clones in Scratch 1.4,
especially by "using the BYOB library", and what other 2.0 features are missing?

---

## 0. TL;DR

1. **Clones are not hard, and BYOB is the wrong tool for them.** The stock
   Scratch 1.4 image already contains dormant *temporary* clone machinery:
   `ScratchSpriteMorph >> cloneAndSend:`, `isClone`, `ScratchStageMorph >> allClones`,
   `deleteAllClones`, and `deleteTerminatedClones`. I verified it at runtime in the
   maintained image. It needs block specs, a "when I start as a clone" hat, and a
   few semantic fixes — not a BYOB port.
2. **BYOB is not a library.** It is a full Scratch 1.4 fork. BYOB 3.1.1's clones
   are *permanent* first-class sprites with prototype inheritance
   (`spawn`/`getSpawnOf:`), not Scratch 2.0's temporary clones. Using BYOB would
   mean rebasing the whole harness or merging a large object-model fork, then
   rewriting clone semantics anyway.
3. **Core clone blocks: ~2–4 focused days.** Closer 2.0 parity (clone-aware
   touching, limit, click/broadcast behavior, persistence rules, performance):
   **1–2 weeks**.
4. **Lists are already in Scratch 1.4.** The harness gap is exposure, not engine
   capability. That is the highest-value small feature: **2–4 days** (1 week with
   contents, undo, tests).
5. **The rest of 2.0 splits sharply.** Small blocks (costume/backdrop names, time
   blocks, stop options, rotation style, list search) are days. Custom blocks,
   vector graphics, 2.0 sound editing, video sensing, and cloud data are weeks to
   months; some are not worth doing in 1.4 at all.

---

## 1. How this harness makes feature work different

The harness is not a normal Scratch mod. A new block usually needs:

| Layer | Work |
|---|---|
| Image (`image/*.st`) | Add a block spec, a selector/method, palette visibility, tuple round-trip, sometimes a hat class; rebuild `BlockSpecDict`. |
| Bridge (`bridge/src/harness/`) | Add the op to `catalog.py`, validate targets/args in `validator.py`, map the tuple in `compiler.py`, update tests. |
| Model context | Document the block/semantics in `SCRATCH_AI_CONTEXT.md`; keep the prompt budget sane. |
| Project model | Only if the feature changes saved state: context, change-set actions, applier, undo, `.sb`/text round-trip. |

Block-only features are cheap. Features that add new project state (custom blocks,
lists if not already supported, vectors) are much more expensive.

The bridge is already catalog-driven, so most of the bridge work is data plus
validation, not new architecture.

---

## 2. Evidence: the clone engine is already in Scratch 1.4

I probed the **running** image read-only (no save) and then exercised the
primitives with a temporary sprite that was deleted afterwards.

### 2.1 Selector check

Logged from `scratch/base/probes/probe_clone_inspect.st`:

```text
PROBE cloneAndSend=true isClone=true stageAllClones=true spriteInstances=4
PROBE spriteSelectors=(... #cloneAndSend: #isClone ...)
PROBE stageSelectors=(... #deleteAllClones #allClones #deleteTerminatedClones ...)
```

So the methods exist in `ScratchAiTesting.image`, not just in the `.changes` file.

### 2.2 Runtime check

Logged from `scratch/base/probes/probe_clone_runtime.st`:

```text
PROBE2 name=ProbeCloneSrc clone isClone=true class=ScratchSpriteMorph
localVar=42 scripts=0 inSprites=false inSubmorphs=true allClones=1
srcAfterCloneVar=42 cloneAfterSet=7
spritesBefore=4 spritesAfter=4 submorphsBefore=4 submorphsAfter=4
```

That proves the important 2.0 behaviors already work:

- the clone is a real `ScratchSpriteMorph`;
- `isClone` is true;
- local variables are copied and then independent;
- the clone is **not** in the sprite pane's `sprites` list (so it is hidden from the
  corral and not saved as a project sprite);
- the clone **is** in the stage `submorphs` (so it draws, receives broadcasts, and
  can be found by `allClones`);
- cleanup restored the exact sprite/submorph counts.

### 2.3 Where the code lives

| Behavior | Code |
|---|---|
| Create clone + send an event only to it | `ScratchSpriteMorph >> cloneAndSend:` (`Scratch.changes` ~112563) |
| Clone flag | `ScratchSpriteMorph >> isClone` / `isClone:`; `ScriptableScratchMorph` ivar |
| Deep copy with receivers remapped | `ScriptableScratchMorph >> copyRecordingIn:` (~121055) |
| Copy local vars/lists/media | `copyRecordingIn:`, `copyListsFor:` |
| Exclude from sprite corral | `ScratchLibraryMorph >> step` filters `isClone` (~103456) |
| Disable editing/selecting clones | `viewBlocksAndScripts` returns early for clones |
| Stage clone collection | `ScratchStageMorph >> allClones` (~113917) |
| Stop deletes clones | `ScratchStageMorph >> stopAll` (~113884), `ScratchFrameMorph >> shoutGo` calls it |
| Auto-delete clones with no running scripts | `deleteTerminatedClones`, called by `stepProcesses` (~113848) |
| No clone blocks in palettes | `ScratchSpriteMorph class >> blockSpecs` (~112923), stage (~114236), common (~121381) |

`cloneAndSend:` is effectively dead code in stock 1.4: `grep` finds only its
definition, never a caller. It looks like a 1.4-era prototype of the feature that
later shipped in 2.0. That is why this is a "finish the wiring" job rather than a
"build a clone engine" job.

### 2.4 What the dormant code does **not** give you

- No "when I start as a clone" hat.
- No "create clone of [myself/other sprite]" or "delete this clone" blocks.
- No clone limit.
- No clone-aware `touching [sprite]?`.
- No parent/original pointer.
- Auto-deletion is the opposite of 2.0: a clone with no running scripts is deleted
  on the next step, so a one-shot clone script would vanish. Scratch 2.0 clones
  persist until "delete this clone" or stop.
- Names are `"Sprite1 clone"`, and repeated clones get repeated names.
- Deep copy is expensive: each clone duplicates scripts **and costumes/sounds**.

---

## 3. What "Scratch 2.0 clones" actually means

Reference: Scratch Wiki, *Cloning*. The 2.0 contract:

- Three blocks, all in Control: **create clone of [myself/other sprite]**,
  **when I start as a clone**, **delete this clone**.
- Clones do not appear in the sprite pane; they disappear on stop/green flag.
- `create clone of` copies position, direction, size, costume, effects, local
  variables and local lists. Global variables/lists are shared.
- A clone can run ordinary hats (key, click, broadcast), not only the clone hat.
- Other sprites can sense clones with `touching [original sprite]?`.
- Limit 300 (301 in 2.0).
- `delete this clone` on the original does nothing and stops the clone's scripts.
- Clones are runtime-only; they are not saved in the project.

The dormant 1.4 code already matches most of that. The mismatches are the list
above, plus testing.

---

## 4. Native clone implementation plan

### 4.1 Image side

**Implemented in `image/33_clones.st` (session 13).** The steps below are the
as-built list; `touching:` and the UTF8/String name fix were also needed.

1. **Block specs.** Recompile `ScratchSpriteMorph class >> blockSpecs` (and the
   stage version) with:
   - `('create clone of %m' - createCloneOf:)`
   - `('delete this clone' - deleteThisClone)`
   - `('when I start as a clone' L -)` (new hat flag)
   and call `ScriptableScratchMorph buildBlockSpecDictionary` after loading so
   tuples resolve.
2. **Sprite methods.**
   - `createCloneOf:`: resolve `#myself` vs a sprite object; call
     `cloneAndSend: 'Scratch-CloneEvent'`; enforce the limit; no-op on Stage.
   - `deleteThisClone`: if `isClone`, stop/delete; otherwise no-op.
   - `cloneAndSend:`: set a `#cloneParent` Morph property (no class-shape change)
     so clone-aware sensing can find the original.
3. **Clone hat.** Add `CloneEventHatMorph` as an `EventHatMorph` subclass that:
   - displays "when I start as a clone";
   - uses event name `Scratch-CloneEvent`;
   - is included in `blockFromTuple:`, `hatBlockFromTuple:`, `hatBlockType:`,
     and `eventReceived:`.
4. **Persistence semantics.** Make `deleteTerminatedClones` a no-op (or remove its
   call from `stepProcesses`). Keep `stopAll` deleting all clones. This gives 2.0
   persistence: a clone stays until explicitly deleted or the project stops.
5. **Limit.** Count `allClones`; refuse creation at 301 (or a lower 1.4-safe cap).
6. **Clone-aware touching.** In `touching:`, if the target is an original, also
   test clones whose `#cloneParent` is that target. Decide whether `distance to`
   and `go to` should remain original-only (2.0 behavior); usually yes.
7. **Optional polish.** Click-on-clone, layering, clone name/ID, delete-original
   deletes its clones.

### 4.2 Bridge side

- `catalog.py`: three specs.
  - `create_clone` command, target menu `("myself", ...sprite names)`, sprite/stage.
  - `delete_clone` command, sprite only.
  - `when_clone_start` hat, sprite only.
- `compiler.py`: `CloneEventHatMorph` for the hat; `createCloneOf:` /
  `deleteThisClone` for commands.
- `validator.py`: `myself` allowed; other target must exist; `delete_clone` and
  the hat are sprite-only; stage cannot clone itself.
- `SCRATCH_AI_CONTEXT.md`: add the three blocks, examples (particles, bullets,
  mouse trail), and the fact that clones are runtime-only and not in context.
- Tests: compiler tuples, validator targets, a mock change set, and one
  image-level apply/run/undo test.

### 4.3 Effort

| Phase | Work | Estimate |
|---|---|---|
| Core | Block specs, methods, hat, palette, tuple round-trip, bridge specs | **2–4 days** |
| Semantics | persistence, limit, clone-aware touching, click/broadcast checks, delete-original | **+3–6 days** |
| Hardening | 300-clone stress, memory, save/open, undo, text project, docs/tests | **+3–5 days** |
| Full 2.0 parity | all edge cases and performance | **1–2 weeks total** |

These are focused engineering days in this codebase, including tests. They assume
the dormant code is sound; it is old and untested, so keep contingency.

### 4.4 Main risks

- **Deep copy cost.** Each clone copies scripts, costumes, sounds, and variables.
  A few dozen clones are fine; hundreds may be slow/heavy. Scratch 2.0 shares
  immutable assets; 1.4 does not. Mitigate with a lower cap first, then
  copy-on-write media if needed.
- **Auto-delete semantics.** Forgetting to disable `deleteTerminatedClones` makes
  one-shot clones disappear and looks like a broken feature.
- **Clone-aware sensing.** `touching:` currently compares one object. Without
  the parent property, `touching [Sprite1]?` ignores Sprite1's clones.
- **Names.** Repeated `" clone"` names are ugly; do not put clones in menus.
- **Save/open.** Clones must stay out of `sprites`; verify `.sb` and text export.
- **Undo.** Runtime clones are not project edits; do not let undo try to restore
  them.

---

## 5. BYOB reality check

### 5.1 What BYOB is

BYOB 3.1.1 (May 2011) is a **fork of Scratch 1.4**, distributed as a Squeak image
plus changes file. It adds:

- custom blocks and first-class procedures;
- first-class lists;
- first-class sprites with prototype inheritance;
- permanent clones via `spawn` / `getSpawnOf:` / a sprite-corral "clone" menu;
- nested sprites (BYOB 2.0 heritage).

It is not a package you can `import` into another image. "Using the BYOB library"
would mean one of:

1. **Rebase the harness onto BYOB.** Copy the harness's image scripts into the
   BYOB image, reconcile class/method conflicts, rebuild the clean image, re-test
   context/applier/undo/project I/O. This is the only way to get BYOB's custom
   blocks "for free".
2. **Port BYOB code into vanilla 1.4.** BYOB's changes are spread across the core
   (`ScriptableScratchMorph` gains `customBlocks`, `deletedAttributes`,
   `prototype`, `ownerSprite`, etc.; new `BlockEditorFrameMorph`,
   `CustomBlockDefinition`, `Procedure` classes; hundreds of method changes).
   This is a surgical merge, not a drop-in.
3. **Use BYOB as a reference.** Read its `spawn`/custom-block code while writing
   native 1.4 code. Useful, but the clone semantics still differ.

### 5.2 Why BYOB does not solve clones

BYOB 3.1.1's clones are **permanent**:

```smalltalk
spawn
    | frame child |
    (frame := self ownerThatIsA: ScratchFrameMorph) ifNil: [^ nil].
    child := self fullCopy.
    child removeLocalBlockDefinitions.
    child unhinge; unhingeAll; initializeNodes.
    child prototype: self.
    frame workPane addMorphFront: child.
    frame workPane sprites addLast: child.
    ^ child
```

They appear in the sprite corral, are saved, and use prototype inheritance. There
is no "when I start as a clone", no temporary-clone lifecycle, and no 300 limit.
The Scratch Wiki explicitly notes that BYOB 3.1 predates Scratch 2.0 and had only
permanent clones; Snap! later added the temporary kind.

Ironically, BYOB still contains the same dormant `cloneAndSend:`/`isClone`
temporary-clone code inherited from 1.4. If you rebased onto BYOB for custom
blocks, you could *then* add the native 2.0 clone blocks on top. But that is a
much larger project than doing clones in vanilla 1.4.

### 5.3 Effort comparison

| Path | Clone result | Cost | Recommendation |
|---|---|---|---|
| Vanilla 1.4 + dormant primitives | True 2.0-style temporary clones | **2–4 days core; 1–2 weeks parity** | **Do this** |
| BYOB rebase | Permanent BYOB clones unless rewritten; then add 2.0 blocks | **2–4 weeks prototype; 6–10 weeks stable** | Only if custom blocks are a must |
| Port BYOB clone code | Wrong semantics; large merge | **Weeks** | No |
| BYOB as reference only | N/A | Hours | Fine |

### 5.4 Licensing/distribution

BYOB is a Scratch 1.4 derivative. Before shipping a BYOB-based build, check the
Scratch Source Code License/GPL terms and the trademark rules already noted in
`HANDOFF.md` (Scratch name/logo/cat/media must be replaced in a public build).
This is due diligence, not legal advice.

---

## 6. Other Scratch 2.0 features: audit matrix

Effort scale: **S** ≤ 2 days, **M** 3–10 days, **L** 2–6 weeks, **XL** > 6 weeks.
These are focused engineering estimates for this codebase, including tests; add
contingency for Squeak surprises.

| 2.0 feature | Scratch 1.4 engine | Harness today | Effort | Verdict / easiest path |
|---|---|---|---|---|
| **Clones** | Dormant temporary clone code | No blocks | **S–M** | Native dormant primitives; 2–4 days core, 1–2 weeks parity. |
| **Custom blocks** | Absent | Absent | **XL** | Native 2.0 subset 3–6 weeks. BYOB rebase 2–4 weeks prototype. Cheap workaround: broadcast-and-wait + variables, or bridge-side macros. |
| **Lists** | Full lists, list blocks, watchers | Not exposed | **S** | Expose; highest ROI. 2–4 days; 1 week with contents/undo. |
| **List search / delete all / show-hide** | Mostly absent | Absent | **S** | Add `list contains`, `item # of`, `delete all`, `show/hide list`; 1–2 days. |
| **Costume name / backdrop name** | Data exists (`mediaName`, `costumeNames`) | No reporters | **S** | Add two reporters; ~1 day. |
| **Rotation style block** | `rotationStyle` exists on sprite | No block | **S** | Add block spec; ~0.5 day. |
| **Stop this script / other scripts** | `doReturn`, `stopAll` exist; "other scripts" missing | No block | **S** | Add menu block; 1–2 days. |
| **When stage clicked / any key** | Stage click path exists; key hats exist | Absent | **S** | Add one hat + "any" option; 1–2 days. |
| **Set/change attribute of sprite** | Attribute getter exists | Read-only `attribute_of` | **S–M** | Add setters/changers for x, y, direction, costume, size, volume; 2–3 days. |
| **When backdrop switches to** | No event | Absent | **M** | Broadcast on backdrop change + menu hat; 2–4 days. |
| **When loudness > / when timer >** | Loudness/timer exist; `WhenHatBlockMorph` exists but disabled | Absent | **M** | Polling hats; re-enable carefully; 2–4 days. |
| **Current time / days since 2000** | Squeak `Date`/`Time` | Absent | **S** | Add reporters; ~1 day. |
| **Username** | Mesh `userName` only | Absent | **S** | Offline placeholder (`player`/OS user); not authentic accounts. |
| **Sound import** | `SoundMedia` supports WAV/AIFF | Not exposed | **S** | Add `add_sound`; 1–2 days. |
| **`.sprite` bundle import** | `importSpriteOrProject:` exists | Not exposed | **S–M** | Add action + ownership/undo; 1–2 days. |
| **Sound editor (2.0 effects)** | Basic wave editor exists | Not exposed | **M–L** | 1.4 editor has rate/volume/file I/O; 2.0 adds fade/reverse/echo/robot and cut/copy/paste. 1–2 weeks, or external sox/ffmpeg. |
| **Vector graphics** | Bitmap `Form` only | Not applicable | **XL** | 1–3 months: vector media, renderer, editor, hit testing, serialization. Use high-res bitmaps or rasterize SVG externally. |
| **Video sensing** | `CameraPlugin`, `CameraMedia`, `VideoSensorPlugin` exist; no user blocks | Absent | **M–L** | 1–3 weeks: blocks/hats, preview/transparency, threshold UX; hardware risk. |
| **Cloud data** | No | No | **L / not practical offline** | Needs a server/accounts; local file/HTTP fake is not 2.0 cloud. |
| **Backpack** | No | No | **M** | Local asset library over `.sprite`/media import; 1–2 weeks. |
| **Record project video** | No | No | **M** | External screen capture; low priority. |
| **Zoom scripts area** | No obvious support | No | **S–M** | Morphic scale UI; low priority. |
| **Website/community** (studios, following, accounts, notes) | N/A | N/A | **N/A** | Out of scope for a local harness. |

### 6.1 Notes on the surprising ones

- **Lists are not missing from 1.4.** `ScriptableScratchMorph` has `lists`,
  `ScratchListMorph`, add/delete/insert/replace/item/length, local/global lists,
  and watchers. `HANDOFF.md` line 538 is correct that the **change set** does not
  expose them; `SCRATCH_AI_CONTEXT.md` line 41 says the same. This is a harness
  gap, not an engine gap.
- **Video sensing is less impossible than it looks.** 1.4 ships `CameraMedia`
  with camera frames, motion history, and color tracking via `VideoSensorPlugin`.
  What is missing is the 2.0 block set, preview/transparency, and hat UX. Still
  hardware-dependent and not a quick win.
- **Sound editing is partially present.** `ScratchSoundEditor` is a wave editor
  with rate, volume, file read/write. Scratch 2.0's editor adds effects and
  cut/copy/paste. Call it "extend", not "build from zero".
- **Vector is the real wall.** Everything visual in 1.4 is bitmap `Form`/
  `ImageMedia`; `touching`, pen, rotation, and scaling all assume bitmaps. A
  vector layer is a separate media subsystem, not a block addition.

---

## 7. Easier ways to get the important behavior without BYOB

### 7.1 Clones

Use the native dormant primitives. This is the recommended path and is described
in §4. Nothing in BYOB is needed.

The obvious alternatives are worse:

- **Runtime `duplicateNoAttach`** creates a permanent sprite in the corral,
  saves it, and gives it a visible name; it is not a 2.0 clone.
- **Stamps** are pixels, not scriptable objects.
- **Pre-created sprite pools** are fixed at edit time and cannot be created
  dynamically; they also appear in the corral.
- **BYOB `spawn`** is a permanent prototype child, not a temporary clone.

### 7.2 Lists

Expose the existing engine. Add change actions for:
`create_list`, `delete_list`, `set_list`/`clear_list`, `add_to_list`,
`insert_at`, `replace_item`, `delete_item`, `show_list`, `hide_list`.
Then add `list contains`, `item # of`, and `delete all` block specs. This is the
single best value-for-effort item in the audit.

### 7.3 Custom blocks without custom blocks

If the goal is AI code reuse rather than a visible `define` block:

- **Broadcast procedure:** `when I receive [name]` + `broadcast [name] and wait`,
  with parameters in global/local variables. Ugly, but works today and is easy
  for the model to generate.
- **Bridge macro:** let the change set define a named block template and have the
  compiler inline/expand calls. No image support, no user editing, but reduces
  model output and repeats. This is a bridge feature, not a Scratch feature.
- **AI-only procedure registry:** store definitions in the `.meta` sidecar and
  expand them on apply. Same caveat: the user cannot edit them as real blocks.

Only pursue native custom blocks if the user-visible `define`/call UI is a hard
requirement. Then compare "native 2.0 subset" (3–6 weeks) vs "BYOB rebase"
(2–4 weeks prototype, much more for stability).

### 7.4 Media gaps

- **Sound import:** use the existing `SoundMedia` import; no BYOB.
- **`.sprite` import:** use `importSpriteOrProject:`; no BYOB.
- **Vector:** rasterize SVG to high-resolution PNG/BMP outside Scratch and import
  as a bitmap. Not true vector, but visually close for many projects.
- **Sound effects:** process with `sox`/`ffmpeg` outside Scratch, import the WAV.
- **Video:** use `CameraPlugin`/`VideoSensorPlugin` if you must; otherwise an
  external OpenCV process could feed sensor values, but that is more moving parts
  than native blocks.

### 7.5 Cloud and backpack

- **Cloud data:** a local file/HTTP service can emulate shared variables, but it
  is not Scratch 2.0 cloud data (no accounts, no moderation, no website). Treat
  as a separate product decision.
- **Backpack:** a local asset library over the existing `.sprite`/media import is
  the pragmatic version.

---

## 8. Recommended roadmap

### P0 — one week, low risk, high AI value

1. Expose lists (create/list actions, context, list blocks, watchers).
2. Small block pack: costume name, backdrop name, rotation style, stop
   this/other scripts, when stage clicked, any key, list search, current time,
   days since 2000.
3. Update `SCRATCH_AI_CONTEXT.md` and add compiler/validator tests.

### P1 — one to two weeks

1. Native clones: blocks, hat, palette, bridge specs, persistence, limit.
2. Clone-aware touching and click/broadcast checks.
3. Mock scene tests: particle trail, bullets, clone piano; undo/stop.
4. Document "clones are runtime-only; use local variables for per-clone state."

### P2 — two to four weeks, as product needs

1. Sound import + `.sprite` import.
2. When backdrop/loudness/timer hats; set/change attribute of sprite.
3. Sound-editor effects or external processing.
4. Video sensing if camera hardware is in scope.

### P3 — strategic only

1. Custom blocks: native subset vs BYOB rebase vs macro workaround.
2. Vector graphics: likely "no" in 1.4; consider a future Scratch 3.0/Snap! port.
3. Cloud/backpack: product decisions, not block work.

### Do not do

- Do not port BYOB to get clones.
- Do not add clones without disabling `deleteTerminatedClones`; one-shot clones
  will vanish.
- Do not let clones into `sprites` or they will appear in the corral and be saved.
- Do not attempt vector graphics as a "block addition"; it is a media subsystem.

---

## 9. Decision points

1. **Clone fidelity:** is the 300 limit required, or is a lower 1.4-safe cap
   acceptable? Does `touching [original]?` need to see clones on day one?
2. **Custom blocks:** required user-visible feature, or just AI code reuse? The
   answer changes the path from "2–4 days of macros" to "weeks".
3. **Vector/sound/video/cloud:** which are actually in scope? If several are, a
   future move to Scratch 3.0/Snap! may be more sensible than extending 1.4.
4. **Distribution/licensing:** BYOB and Scratch assets have license/trademark
   constraints; decide before building on BYOB.

---

## 10. References and evidence

### Repo

- `HANDOFF.md` — project state, known limitations (lists/clones/custom blocks not
  exposed; list contents/sound import/`.sprite` import missing).
- `SCRATCH_AI_CONTEXT.md` — model contract; session 13 updates it with clones
  (runtime-only, 300 limit) and keeps custom blocks unsupported
  and lists are not exposed; §9 limitations.
- `scratch/base/Scratch.changes` — stock 1.4 source. Key areas:
  - clone ops ~112563; stage clones ~113917; `copyRecordingIn:` ~121055;
    corral filter ~103456; `stepProcesses` ~113848; `stopAll` ~113884;
    `shoutGo` ~99718.
  - block specs: sprite ~112923, stage ~114236, common ~121381.
  - `WhenHatBlockMorph` ~156464; `processWhenConditions` disabled ~251183.
  - `CameraMedia` ~11592; `VideoSensorPlugin` ~153165.
  - `ScratchSoundEditor` ~110167.
  - list ops ~119154.
- `scratch/base/probes/probe_clone_inspect.st` — read-only selector probe.
- `scratch/base/probes/probe_clone_runtime.st` — temporary sprite clone test;
  cleans up after itself.
- `scratch/base/ai_control.log` — `PROBE` / `PROBE2` lines with the results above.

### External

- Scratch Wiki, *Cloning*: temporary clones, 300/301 limit, touching original,
  local variables/lists copied.
- Scratch Wiki, *Scratch 2.0*: feature list (backdrop name, backpack, cloning,
  cloud data, custom blocks, show/hide lists, sound editor, current/days since
  2000, username, vector editor, video sensing, when backdrop switches).
- Scratch Wiki, *Snap!*: BYOB history; BYOB 3.1's first-class sprites and
  permanent clones; Snap! 4.1 added temporary/permanent distinction.
- Archived BYOB 3.1.1 distribution (`snap.berkeley.edu/old_site/`): inspected
  `BYOB.changes`; `spawn`/`getSpawnOf:`, `customBlocks`, `BlockEditorFrameMorph`,
  `CustomBlockDefinition`, `prototype`; no 2.0 temporary clone blocks.
