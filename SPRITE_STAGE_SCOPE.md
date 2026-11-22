# Sprite, stage and backdrop work package

**Status:** implemented and verified live (two scene prompts + overlapping pair; third optional)  
**Date:** 2026-11-12  
**Depends on:** session 6 state (connection Phases 1–6 done)  
**Owner next session:** run the live scene gate, then 7.3

---

## As-built notes (read before changing the applier)

- **Size is a percent, not a scale point.** In this image
  `scalePoint: 80 @ 80` means 8000%; use
  `scalePoint: (percent / 100 @ percent / 100)`. A probe that used `100 @ 100`
  exhausted the image heap ("space is low"). `28_sprites_stage.st` also adds a
  `scale:` compatibility setter for the text importer.
- **`addAndView:` registers and renames.** It adds the sprite to
  `stage sprites` and renames it, so set `objName:` *after* `addAndView:`.
- **Media lives under a kind folder.** Wire references stay relative to
  `Media/` (`Animals/bat1-a.png`, `Nature/stars.gif`); the applier prefixes
  `Costumes/` or `Backgrounds/` by action.
- **Labels must be re-recorded.** `28` recompiles `applyChange:` and has to call
  `recordLabel:` itself; without it undo restores scripts without labels.
- **Ownership** lives in `SpriteOwners` and is written as
  `sprite|Name|owned` lines in `.sb.meta` / text `harness.meta`. Undo of
  `delete_sprite` records and re-registers script ids, labels and hashes.
- **Tests:** 186 offline + 2 opt-in live. Deterministic image gate:
  `python tools\mock_scene_bridge.py` then
  `python tools\ai_control.py send --async "scene" --wait`, `undo`.

---

## 1. Why

Today the model can only edit scripts on targets that already exist, plus create
variables. A Scratch project is not a set of scripts; it is a cast of sprites,
a stage with backdrops, and code attached to each. Until the harness can create
actors, clothe them, build a scene and attach code to any of it, it cannot do
the thing users actually ask for ("make a game where a bat chases the cat").

**Goal:** the model composes whole scenes using **only Scratch's own media
library** — no generated, downloaded or user-supplied images.

Available locally in `scratch/base/Media`:

| Library | Contents |
|---|---|
| `Costumes/` | 619 images in Animals, Fantasy, Letters, People, Things, Transportation, plus 29 `.sprite` bundles |
| `Backgrounds/` | 74 images in Indoors, Nature, Outdoors, Sports |
| `Sounds/` | Scratch's sound library (out of scope for now) |

Formats: costumes `.gif` 488, `.png` 131, `.sprite` 29; backgrounds `.jpg` 61,
`.gif` 12, `.png` 1. Ignore `scratchthumbs.db`.

---

## 2. What exists to build on

| Capability | Where | Status |
|---|---|---|
| Add/replace/delete script on any **existing** target, incl. `'Stage'` | `08_chat_send.st` `targetNamed:`; `changeset.py` | works |
| Create variable (global/sprite) | applier `createVariable:` | works |
| Full context incl. stage entry, costumes per target | `15_reply_context.st`, `context.py` | works |
| Text export/import already **creates sprites and imports costumes** | `27_text_project.st` | works — reference implementation |
| Build image from `image/*.st` | `00_bootstrap.st`, `build_image.ps1` | works |

Canonical Squeak calls discovered in the shipped Scratch 1.4 image:

```smalltalk
"create a sprite and add it (Scratch's own addSpriteMorph path)"
f  := Form fromFileNamed: 'C:\...\Media\Costumes\Animals\bat1-a.png'.
el := ImageMedia new form: (ScratchFrameMorph scaledFormForPaintEditor: f).
m  := ScratchSpriteMorph new soleCostume: el.
el mediaName: (m unusedMediaNameFromBaseName: 'bat1-a').
frame addAndView: m.          "sets centre, name, reference position, steps, selects"

"add another costume / backdrop"
media := ImageMedia new.
media form: form; rotationCenter: cx @ cy; name: cName.
target addMediaItem: media.
target lookLike: cName.       "costume switch; on the stage this is the backdrop"

"whole sprite or project from a .sprite file"
frame importSpriteOrProject: path.
```

`27_text_project.st` already does `ScratchSpriteMorph new` + `objName:` +
`stage addMorph:` on import, and `ImageMedia` + `addMediaItem:` for costumes —
reuse those helpers rather than inventing a second path.

---

## 3. Design

### 3.1 New change actions

Flat JSON, same shape as today's change set (validated by `block_ir.py`):

```json
{"action": "create_sprite", "name": "Bat",
 "costumes": [{"library": "Animals/bat1-a.png"}],
 "x": 0, "y": 0, "direction": 90, "size": 100,
 "visible": true, "rotation_style": "all around"}

{"action": "duplicate_sprite", "target": "Sprite1", "name": "Cat2"}
{"action": "delete_sprite",   "target": "Bat"}

{"action": "add_costume", "target": "Bat",
 "library": "Animals/bat1-b.png", "name": "bat1-b", "select": false}

{"action": "set_backdrop", "library": "Nature/stars.gif",
 "name": "stars", "select": true}

{"action": "set_sprite", "target": "Bat",
 "x": 10, "y": -20, "direction": 90, "size": 80,
 "visible": true, "rotation_style": "left-right"}
```

Rules:

- `costumes` accepts 1–3 entries; the first becomes the selected costume.
- `rotation_style` ∈ `all around`, `left-right`, `don't rotate` (Scratch strings).
- `library` is **relative to `scratch/base/Media/`** and must resolve to an
  existing file; no paths, no `..`, no absolute paths, no generated assets.
- Scripts for a sprite created in the same change set are legal **if the
  create comes first** (see ordering in §3.3).
- `add_script`/`replace_script` keep working against `Stage` for "code in the
  background"; add `switch_backdrop` as the stage form of `switch_costume`.

Compiled wire items (the image applies these):

```smalltalk
#(createSprite 'Bat' #(#('Animals/bat1-a.png' 'bat1-a')) 0 0 90 100 true 'all around')
#(duplicateSprite 'Sprite1' 'Cat2')
#(deleteSprite 'Bat')
#(addCostume 'Bat' 'Animals/bat1-b.png' 'bat1-b' false)
#(setBackdrop 'Nature/stars.gif' 'stars' true)
#(setSprite 'Bat' 10 -20 90 80 true 'left-right')
```

### 3.2 Context and identity

Sprite entries grow an optional 8th element:

```smalltalk
#(name isStage vars lists costumes sounds scripts
  #(x y direction size visible rotationStyle aiOwned costumeIndex))
```

`from_literal` accepts 7 or 8 elements, so older images keep working.
`SpriteContext` gains `x, y, direction, size, visible, rotation_style,
ai_owned, costume_index`.

**Identity stays name-based** (Scratch names are unique and are what scripts and
the model target). New rules:

- Sprite names are unique **case-insensitively**; the validator rejects a clash.
- Sprites created by the harness are marked `aiOwned=true`. The image must
  persist that flag (see §3.5).
- User sprites are read-only for structural changes: the model may add scripts
  and costumes to them, but may not rename, delete, duplicate-over or recostume
  destructively. `delete_sprite`/`duplicate_sprite` are AI-sprite-only.

### 3.3 Ordered validation

A change set applies top-down, so validation must simulate it, not just check
the incoming snapshot:

1. Copy `context.sprites` into a working set.
2. `create_sprite` adds the name; later `add_script` to it validates.
3. `delete_sprite` removes the name and its scripts; a later reference is an
   error ("sprite was deleted earlier in this change set").
4. `set_backdrop`/`add_costume` update the working costume lists so a later
   `switch_costume`/`switch_backdrop` validates.
5. At the end, the compiled change set is applied in order by the image.

This is the one structural change to `validator.py`; the existing script checks
run against the working context.

### 3.4 Media library

New `bridge/src/harness/media.py`:

- Index `scratch/base/Media/Costumes/**` and `Backgrounds/**` once (ignore
  `*.db`; exclude `*.sprite` from `costumes()` for the MVP).
- `MediaAsset(category, name, path, ext)`; `resolve(kind, query)` accepts
  `Animals/bat1-a.png`, `bat1-a.png`, `bat1-a`, case-insensitively; returns one
  match or a clear error listing near matches.
- `prompt_index(kind, max_chars)` → compact grouped text for the system prompt,
  trimmed by the existing budget machinery.
- Suggest a small `tools/media_index.py` to dump/filter the library during
  development.

The prompt then teaches: sprite creation, costume/backdrop by library name,
stage scripts, and that the stage cannot move/say/size.

### 3.5 Image applier and undo

New `AIChangeSetApplier` methods:

| Action | Implementation sketch |
|---|---|
| `createSprite:` | `Form fromFileNamed:` → `scaledFormForPaintEditor:` → `ImageMedia` → `ScratchSpriteMorph new soleCostume:` → extra costumes via `addMediaItem:` → set `objName:`, position/centre, direction, size, visible, rotation → `workPane addMorphFront:` + `workPane sprites addLast:` + `startStepping` (mirror `addAndView:` but with a deterministic name) |
| `deleteSprite:` | record spec (name, costume library refs, props, owned script ids) → `sprite delete` → drop its stacks from `Scripts` |
| `duplicateSprite:` | copy spec + `media deepCopy` each costume (do **not** copy scripts) |
| `addCostume:` | `ImageMedia new form:` → `name:` → `addMediaItem:` → optional `lookLike:` |
| `setBackdrop:` | stage `addMediaItem:` + `lookLike:` |
| `setSprite:` | `referencePosition:`/`gotoX:y:`, `setDirection:`, `setSizeTo:`, `setVisible:`, `rotationStyle:` |

Undo:

- inverse of `createSprite` = delete it (and its scripts);
- inverse of `deleteSprite` = recreate from the recorded spec + re-add its
  AI-owned scripts;
- inverse of `duplicateSprite` = delete the copy;
- inverse of `addCostume`/`setBackdrop` = remove the media and restore the
  previous selection;
- inverse of `setSprite` = restore the previous properties.

Ownership persistence: `.sb` does not store `aiOwned`. Extend the `.meta`
sidecar (or a new `.sprites` sidecar) with `sprite|Name|owned` lines and restore
by name on `project open`, falling back to "scripts present but no owned flag"
when the sidecar is missing. Text export/import already round-trips sprites and
costumes; add the ownership flag to `manifest.txt` or `harness.meta`.

### 3.6 Deliberate limits

- No paint editor, no image generation, no downloads, no uploads.
- No rename of user sprites; no deletion of user sprites.
- No `.sprite` import in the MVP (whole sprites with scripts are a second
  design problem); individual images only.
- No sound import, no list contents, no custom blocks.
- Max 3 costumes on `create_sprite`.

---

## 4. Work packages

### Step 0 - probe the image (½ hour, do first) — DONE

Before writing applier code, prove each call in the live image through
`tools/ai_control.py load`:

1. `Form fromFileNamed:` on a PNG and a JPG from Media.
2. `ScratchFrameMorph scaledFormForPaintEditor:` scaling a large image.
3. `ScratchSpriteMorph new soleCostume:` + deterministic `objName:` + add to
   `workPane` (and whether `view:` is needed).
4. `addMediaItem:` + `lookLike:` on a sprite and on the stage.
5. `delete` on a sprite; does `workPane sprites` update?
6. `rotationStyle:`, `setSizeTo:`, `setDirection:`, `setVisible:`.

Record the exact working calls in the new `.st` file; several may differ in this
2009 image.

### S1 - bridge model, validation, media index (1-1.5 days) — DONE

- `block_ir.py`: new actions/fields.
- `context.py`: sprite properties + `ai_owned`; accept 7/8-element entries.
- `media.py`: index, resolve, prompt index.
- `validator.py`: ordered working context; media/name/ownership rules.
- `changeset.py`: compile the new apply items; summaries like
  `Created sprite 'Bat' with costume bat1-a in Animals (1 AI script).`
- `prompts.py`: capabilities, media index, examples (including "code in the
  background").
- `catalog.py`: `switch_backdrop` (`lookLike:` on stage), stage-safe checks.

**Acceptance (offline):**

- create + script in one change set compiles in order.
- unknown media → one clear validation error with near matches.
- deleting a user sprite / naming a sprite `Stage` / backdrop on a sprite →
  rejected.
- motion block on the stage → rejected; stage script with `switch_backdrop` →
  accepted.
- media index stays within the prompt budget and is trimmed with a marker.
- all 162 existing tests still pass.

### S2 - image applier, context, undo (1.5-2 days) — DONE

- New `image/28_sprites_stage.st` (loaded by `00_bootstrap.st`).
- Context: 8th sprite element with properties + `ai_owned`; stage backdrops.
- Applier actions + undo + registry bookkeeping for sprite scripts.
- `switch_backdrop` block works when built by `stackFromTupleList:` on the
  stage.
- `.meta`/text persistence for sprite ownership.
- Rebuild `ScratchDev.image` from `ScratchAI9` and keep the old image.

**Acceptance (headless image tests):**

- `send "add a bat that spins"` creates `Bat` with a costume and script;
  green flag runs it; `undo` removes sprite, script and costume.
- `send "put stars in the background"` adds and selects `stars.gif`.
- `send "make the stage switch backdrops every 2 seconds"` creates a stage
  script; it compiles and runs.
- `status` / `context` show the new sprite with properties and `owned`.
- delete/undo of an AI sprite restores costume + AI scripts.

### S3 - media UX, scenes, verification (1 day) — DONE (two live scenes + overlap; third optional)

- `tools/media_index.py` (search/inspect the library).
- Scene prompts and examples ("beach scene with a cat and two bats").
- Text export/import round-trip with new sprites, backdrops and ownership.
- `project-save`/`project-open` round-trip with the ownership sidecar.
- Live runs: 3 scenes, undo after each, two overlapping create requests.
- Update `HANDOFF.md`, `docs/HISTORY.md`, add a session log.

**Acceptance:** three different scene prompts produce correct projects; undo
after each restores the previous project; text round-trip preserves sprites,
backdrops, scripts and ownership; logs stay clean.

---

## 5. Test plan

**Offline (bridge):** new-action parsing, ordered validation, media resolution
(exact, alias, near-miss, traversal rejection), ownership rules, stage-restricted
blocks, summary text, prompt budget with the media index, backwards compatibility
with 7-element contexts.

**Image (headless, no model):** call each applier action through the control
server with a fixed literal; assert `status`/`context` and undo. Then repeat
through the mock bridge.

**Live:** three scene prompts, undo each, two overlapping sends, check
`bridge-status` and `bridge.log` (no prompt/key leakage).

---

## 6. Decisions needed before S1

1. **Media source:** individual images only for the MVP (recommended), or also
   `.sprite` bundles? Bundles carry scripts, which complicates ownership.
2. **Naming:** library file stem as the costume name (recommended); sprite names
   case-insensitive unique.
3. **Deletion:** AI-created sprites only (recommended); user sprites read-only.
4. **Stage code:** allowed, with `switch_backdrop` as the only new stage block
   (recommended).
5. **Undo of delete:** full recreate for AI sprites (recommended) vs. disallow
   deletion.
6. **Costume cap:** 3 per `create_sprite` (recommended).
7. **Media index in the prompt:** full compact list (~693 image names,
   budget-trimmed) vs. categories + a short sample. Recommend the full list; it
   is the only way the model reliably knows the names.

---

## 7. Risks

- **Image API drift.** This is a 2009 Squeak image; `addAndView:` renames and
  selects the sprite, `scaledFormForPaintEditor:` may clamp sizes, and some
  Morphic methods differ. Step 0 exists to find this out cheaply.
- **Identity collisions.** Sprite names are the identity; a user rename or a
  duplicate name breaks targeting. Enforce uniqueness and re-read context every
  turn (already guaranteed).
- **Ownership persistence.** `.sb` drops `aiOwned`; the sidecar is the only
  bridge across save/load. Losing it makes AI sprites read-only, which is safe
  but annoying.
- **Undo complexity.** Delete/recreate must restore costumes and AI scripts;
  cross-sprite undo entries are more state than today's per-stack undo.
- **Licensing/trademarks.** The media library ships with Scratch; a public
  distribution must respect Scratch's trademark and asset terms (already flagged
  in `HANDOFF.md` §7.3).
- **Prompt growth.** The media index costs tokens on every turn. Measure
  `prompt_tokens` before and after; the budget trims it, but the quality of name
  choices will depend on the list being present.

---

## 8. Non-goals

- Generating or downloading art; using non-Scratch assets.
- Sound library import (a natural follow-up).
- Renaming or deleting user sprites.
- Custom blocks, list contents, watchers. (Clones were added in session 13.)
- Multi-frame animation authoring beyond 3 costumes.
- A drag-and-drop scene editor in the pane.
