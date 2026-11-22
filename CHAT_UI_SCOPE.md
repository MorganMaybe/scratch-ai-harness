# Docked AI Chat Rail — Final

**Status:** as built and saved in `scratch/base/ScratchAiTesting.image`  
**Source:** `image/36_chat_ui_scratch.st`, `image/38_bridge_usage_ui.st`,
`image/37_chat_dock.st`  
**Rail layout version:** 17 (whole-window parity; native library right edge and
padded Scripts top-right and pristine native bottom-right corner)

The harness is a body pane on the right edge of `ScratchFrameMorph`, **below**
a native full-width top bar. The rail now has a visible native Scripts **left
edge** and **bottom-left corner**; the native stage/library right edge remains
the outer seam. The outer right is the native
`#spriteLibraryPaneFrameTransparent2` right edge (11 px), with the squared
sprites/library bottom-right corner. The rail top-right is the Scripts top-right
corner with the library outer edge padded in;
the `#topPane` corner at the top bar remains the window top-right above it.
The rail is flush at the right and overlaps the outer 6 px of the native library
right edge on the left.

**Session 26 change:** the rail now has a visible native Scripts **left edge**
and a native Scripts **bottom-left corner**. The left side is Scripts; the right
side and bottom edge stay native library. This is a deliberate change from the
v17 no-left-edge build.

**Session 27 change:** the rail is shifted 6 px left so its Scripts left edge and
bottom-left corner cover the outer 6 px of the native library right edge. The
native reservation stays 352 px; the visual rail is 358 px at `x=962`.

---

## 1. Whole-window geometry

Working frame: **1320 × 717** (wider frames are allowed; the rail is fixed).

| Element | Position | Size |
|---|---|---|
| Native top bar | 0, 0 | 1320 × 34 |
| Native column | 0, 34 | 968 × 683 |
| Rail outer | 962, 34 | 358 × 683 (6 px overlap) |
| Rail header | 962, 34 | 358 × 44 |
| Rail page | 962, 78 | 347 × 627 |
| Page bottom | — | y = 705 |
| Native frame bottom edge | — | y = 705..716 |
| Native frame right edge | — | x = 1309..1319 |

The top bar spans the full 1320 px and keeps its native `#C0C3C6` fill. The
native column is 968 px wide. The rail’s visual left edge is 962, so it overlaps
the outer 6 px of the native library right edge; its right edge is 1320. The
right 11 px and bottom 12 px are reserved for the native outer frame.

---

## 2. Native frame and outline

The rail frame is a **34 × 56** composite of native forms. It is not widened.
The left side is native Scripts; the right side and bottom edge are native
library.

- top: `#scriptPaneFrameTransparent2` top bevel (8 px)
- bottom: `#spriteLibraryPaneFrameTransparent2` bottom bevel (12 px)
- right 11 px: native `#spriteLibraryPaneFrameTransparent2` right edge
- top-right: Scripts `#scriptPaneFrameTransparent2` top-right corner, padded
  outward 6 px with the library top-right edge so the 11 px right edge matches
- bottom-right: pristine native `#spriteLibraryPaneFrameTransparent2`
  bottom-right corner, 21 × 27
- top-left: native `#scriptPaneFrameTransparent2` top-left corner
- bottom-left: native `#scriptPaneFrameTransparent2` bottom-left corner
- left edge: native `#scriptPaneFrameTransparent2` left edge, 6 px visible
- the native stage/library right edge at x=958..967 is the outer seam; the rail
  Scripts left edge occupies x=962..967, covering the outer 6 px; the page starts
  at x=962 under it
- while docked, the sprites/library bottom-right corner is the **Scripts pane
  bottom-right corner copied exactly**, padded with 6 px of transparency on the
  right so its visible 5 px edge aligns with the visible library right edge
  above. This gives the light right-hand colours and the square-outside /
  round-inside shape. The native curved form is restored on collapse

The form is `initFrontFromForm:` with `topSectionHeight: 44`, so the frame
draws **over** the content. `cornerExtent` is the native **16 × 27**.

| Side | Pixels | Colours |
|---|---|---|
| Left | 958..967 | visible native right edge 958..961, then rail Scripts left edge 962..967 (6 px); page starts 962 |
| Top | 34..41 (8 px) | `#C0C3C6`, `#B5B8BA`, `#A9ABAE`, `#86888A` ×2, `#484B4D`, `#6E7276`, `#888D91` |
| Right | 1309..1319 (11 px) | inside → outside: `#6E6F70`, `#CED0D2` ×3, `#C0C3C6`, `#ACAEB1`, `#96989B` ×3, `#535353`, `#7F7F7F` |
| Bottom | 705..716 (12 px) | `#626566`, `#D8DADB` ×2, `#D6D8DA`, `#CCCED1`, `#A2A4A7`, `#858789` ×3, `#535353`, `#7F7F7F`, `#9C9C9C` |
| Rail left edge | 962..967 (6 px) | native Scripts left edge: `#ACAEB1`, `#96989B` ×3, `#3C3E40`, `#4C4E50` |

The one rail background is a plain palette-grey `Morph` at **962, 34,
358 × 683**, painted with `ScratchFrameMorph palettePaneColor` **`#7C8083`**.
The header band at **962, 34, 358 × 44** is the native pane-header colour
**`#959A9F`**. The page, history and tab pane are transparent over these.

The native top bar is a single full-width `#topPane` skin: fill **`#C0C3C6`**,
6 px top bevel, native left/right corners. The rail starts at its bottom
(`y = 34`), so the top outline is continuous across the window.

---

## 3. Tabs

| Element | Position | Size |
|---|---|---|
| Tab strip | 977, 56 | 352 × 23 |
| Tab height | — | 23 px |
| Close button | 1290, 58 | 15 × 15 |
| Reload UI (dev) | 1212, 55 | 72 × 18 |
| Header | 962, 34 | 358 × 44 |
| Divider visible | 962, 76 | 358 × 7 (11 px form, 2 transparent rows top/bottom) |
| Page top | 962, 78 | starts below the divider |

The tab pane is **transparent**. The tab pane bar form is the native
`#dividedImageFrameBar` 1 × 11 centre column. The tabs use the native
`#tabOn` / `#tabOff` skins and `ScratchFrameMorph getFont: #Tab` (13 px).
Labels: **Chat**, **Bridge**, **Usage**. The tab strip and page share the
header/page backgrounds; the selected tab merges into the divider at the
header/page boundary; unselected tabs are covered by the bar from y76.

---

## 4. Chat page

Page: **962, 78, 347 × 627**, transparent over the rail background. The native
frame edges draw over its outer border; the page stops at x = 1309 and
y = 705 so no control is covered.

| Element | Position | Size |
|---|---|---|
| History scroller | 962, 78 | 347 × 512 |
| Status line | centred on x = 1135; y = 594 | 12 px, hidden while `Ready` |
| Input frame | 962, 611 | 347 × 54, grows to 96 |
| Input editor | 976, 621 | 319 × 42 |
| Footer row | y = 673 | 22 px high |
| Clear | 972, 673 | 64 × 22 |
| Undo | 1042, 673 | 56 × 22 |
| Send / Stop | 1223, 673 | 76 × 22 |

The footer sits 10 px above the page bottom: button bottom 695, page bottom
705, native bottom edge 705..716. No button is clipped.

The input frame is `ImageFrameMorph` with `#typein`; the editor is a
white-on-dark `MultilineStringMorph` using `#UpdatingStringField` (13 px),
growing from 54 to 96 px and scrolling at the cap. `Send` stays 76 px wide when
it becomes `Stop`.

### No default text

There is **no empty-state title, no hint text, and no input placeholder**.
Clear leaves a blank transcript and an empty input. The status line is hidden
while the state is `Ready`; it appears only for `Thinking...`, `Cancelling...`,
`Error`, or a Ping result.

### Transcript

| Role | Geometry | Style |
|---|---|---|
| Assistant | x = 976, width 303 | white `#UpdatingStringField`, 13 px, left |
| User | right edge = 1289, max text 230 | white `#talkBubbleFrame` bubble, black `#TalkBubble` |
| Status | centred on x = 1135 | white `#Label`, 12 px |
| Error | x = 976, width 303 | white `#DialogBoxMessage`, 15 px, prefix `!  Error:` |

Entries use a **7 px** gap. The right 20 px is reserved for the native
`ScratchScrollBar`. The transcript auto-scrolls to the newest entry when the
user was already at the bottom and holds at most 200 entries. The status line
above the input is transient; transcript status entries are permanent results.

---

## 5. Bridge page

Page: **962, 78, 347 × 627**, transparent over the rail background; the native
frame edges draw over it. Content scrolls in short frames.

| Element | Position | Size |
|---|---|---|
| Start | 1139, 82 | 44 × 22 |
| Refresh | 1189, 82 | 64 × 22 |
| Ping | 1259, 82 | 40 × 22 |
| Page heading | 972, 86 | `#DialogBoxMessage`, 15 px |
| Row label | x = 972 | fixed 132 px column |
| Row value | x = 1094 | 191 px wide |
| Wide value (Endpoint) | x = 972, next line | 323 px |
| Row gap | — | 5 px |
| Section gap | — | 7 px |
| Heading gap | — | 8 px |

```text
Bridge
Connection
  Status:         Online / Offline
  Protocol:       ScratchAI/1
  Profile:        opencode-go
  Model:          deepseek-v4.1-flash
  Endpoint:       https://opencode.ai/inference/go/
                  openai/v1
  Turn budget:    240 s
  Concurrent:     2
  Pending:        0
  Last error:     (none)

Options
  Auditing:       full
  Local only: prompts and raw replies. Do not share.
  Audit folder:   scratch\base\audit
  Audit keep:     100 turns
  Prompt budget:  60000 chars
  Timeout:        120 s
  Retries:        2
  Max tokens:     16384
  Thinking:       off
  Log file:       scratch\base\bridge.log
```

Long unbroken values break at a slash. Diagnostic paths are relative to
`scratch\base\`. Start/Refresh/Ping are at the top right. The key value never
appears.

**Start** writes `scratch\base\bridge_start.cmd` and opens it through
`ScratchPlugin primOpenURL:` (the image VM has no process-spawn primitive). The
script runs `run_live.ps1` when `bridge/.deepseek_key` exists and
`run_bridge.ps1` otherwise; `bridgeLaunch=live|mock` in `harness.ini` overrides
that. If the bridge already answers `#info`, Start only refreshes. Otherwise the
Status row shows `Starting...`, then `Starting (live|mock)`, and the page polls
`#info` for up to 20 s before switching to `Online` or reporting a timeout.
The launcher console stays open with the bridge output; closing it stops the
bridge.

---

## 6. Usage page

Page: **962, 78, 347 × 627**, transparent over the rail background.

| Element | Position | Size |
|---|---|---|
| Refresh | 1235, 82 | 64 × 22 |
| Page heading | 972, 86 | `#DialogBoxMessage`, 15 px |
| Row label / value | 972 / 1094 | 132 px / 191 px |
| Row gap | — | 5 px |

```text
Usage
Connection
  Status:             Online / Offline
  Model:              deepseek-v4.1-flash
  Profile:            opencode-go
  Key:                DEEPSEEK_API_KEY (configured)
  Key source:         environment variable
  The key value is never displayed.

Since bridge start
  Prompt tokens:      19,326
  Completion tokens:  186
  Total tokens:       19,512
  Requests:           1
  Last turn:          -  (or the token delta)
  Turn budget:        240 s
  Totals reset when the bridge restarts.
```

`Last turn` is always present (`-` until a request delta exists). `Turn budget`
comes from the last `#info` read. Token totals are grouped under one “Since
bridge start” heading. The key is shown only as the environment-variable name
and configured/missing status.

---

## 7. Styling sources

| Visual | Source |
|---|---|
| Top bar | native `#topPane` 30 × 28 skin, fill `#C0C3C6`, 34 px high, full width |
| Rail left/top/bottom | left edge and top/bottom-left are native Scripts; bottom edge is native library; top bevel is Scripts; the native stage/library right edge remains the outer seam |
| Rail right | native `#spriteLibraryPaneFrameTransparent2` right edge, 11 px |
| Rail corners | top-left/bottom-left native Scripts; top-right Scripts padded with the library top-right edge (22 × 27); bottom-right pristine native library corner (21 × 27) |
| Rail divider | `#dividedImageFrameBar` 1 × 11 centre column; `topSectionHeight` 44; right margin 6 |
| Rail background | `ScratchFrameMorph palettePaneColor` `#7C8083` |
| Rail header | `#959A9F` (native pane header) |
| Tabs | `ScratchTabPaneMorph` with transparent pane, `#tabOn` / `#tabOff`, `#Tab` font, drawn after the frame |
| Assistant/values/notes | white `#UpdatingStringField` (13 px) |
| Labels/sections/status | white `#Label` (12 px) |
| Page headings | white `#DialogBoxMessage` (15 px) |
| User bubble | `ScratchTalkBubbleMorph`, `#talkBubbleFrame`, no pointer |
| Input | `#typein` frame + `#UpdatingStringField` |
| Buttons | `ScratchFrameMorph buttonLabel:selector:` — `#btn` / `#btnPressed` |
| Scrollers | `ScrollFrameMorph2` + `ScratchScrollBar` |
| Close | `#deleteCircleButton` / `#deleteCircleButtonPressed` |

No hard-coded background hex values are used in code; the rail uses the named
`palettePaneColor`, the header uses the native 149/154/159 triple, and the
border is the native skin forms. Exact clean-image edge values and the version
16 audit are in `docs/NATIVE_UI_BIBLE.md` §8.

---

## 8. Behaviour preserved

- Chat / Bridge / Usage switch by detaching inactive pages; the selected tab is
  lit through `ScratchTabPaneMorph>>currentTab:`.
- Send is asynchronous; the button becomes Stop while pending. Enter sends;
  Shift+Enter inserts a newline. The UI never blocks.
- Clear empties the transcript and leaves the input alone. Undo calls
  `AIHarness class>>undoLast`.
- Bridge/Usage refresh in a background fork with a 2 s timeout; both pages
  scroll in short frames. Bridge **Start** also runs in the background: it
  writes and opens `bridge_start.cmd`, polls `#info`, and hands the result to
  the dispatcher through the completion queue (`#bridgeLaunch` / `#bridge`).
- The control server API is unchanged: `status`, `send`, `send --async`, `poll`,
  `undo`, `log`, `load`, `project-*`, `clean`.
- The rail is frontmost in the frame submorphs. `ScratchFrameMorph>>fullDrawOn:`
  skips the native-pane fast path when damage intersects the rail, so partial
  repaints redraw the rail last.
- Dev only: the rail header has a **Reload UI** button and File > Reload UI. They
  reload `36_chat_ui_scratch.st`, `38_bridge_usage_ui.st` and
  `37_chat_dock.st` and rebuild the rail, preserving the selected tab and input.
  This is a source reload, not a VM restart.
- `#info` remains nine elements; `#options` and `#usage` are additive.
- Collapse hides the pane, gives the width back to the native UI, and preserves
  the selected tab. File > AI Chat toggles it.
- The native top bar remains full width in both collapsed and expanded states.

---

## 9. Verification

Image probes (0 failures each):

- `probe_chat_ui_layout.st` — full-width top bar, rail below it, native Scripts
  left edge and bottom-left corner, native library 11 px outer right, 12 px bottom, page
  reserves right/bottom, native header, divider at the header/page boundary,
  tabs on the divider, 32 × 43 rail corner and exact Scripts right-hand sprites
  corner, padded 22 × 27 Scripts/library top-right corner, pristine native
  bottom-right corner, rail frontmost submorph, footer clearance, resize at
  1280/1500/1880, collapse/expand, tab switch.
- `probe_chat_ui_messages.st` — roles, wrapping, auto-scroll, 200 cap, no
  default Chat text, input growth, `setInputText:`/`clearInput`.
- `probe_chat_ui_bridge_usage.st` — structured rows, page fit/wrap, page
  scrollers, `Last turn` placeholder/delta, no key exposure.
- `probe_chat_ui_cancel.st` — Send/Stop and cancellation.
- `probe_chat_ui_reload.st` — triggers the Reload UI request (check the log for
  `reload ui complete`).

Direct partial-repaint check: invalidate the library at the seam and force a
display; the rail is redrawn last. Visual:
`docs/media/harness-junction-partial.png`.

Bridge suite unchanged: **290 passed, 2 skipped**. Clean image re-saved as
`ScratchAiTesting` with `scripts=0 registry=() undo=0`.

Screenshot audit: `docs/media/harness-final-v17-frame.png` (version 17). The
right edge, top-right corner, bottom-right corner and Scripts/librarian corner match
`docs/media/native-ui-clean-frame.png`; the
exact values are in `docs/NATIVE_UI_BIBLE.md` §8.

---

## 10. Native UI Bible — borders, edges and geometry

> The full reference follows. The standalone copy is
> `docs/NATIVE_UI_BIBLE.md`; the annotated pre-fix audit is
> `docs/media/native-ui-border-audit.png`, and the post-fix screenshot is
> `docs/media/native-ui-border-final.png`.
>
> **Version 17 note:** this embedded copy is the version 15 reference. The
> current right edge and bottom-right corner are the native
> `#spriteLibraryPaneFrameTransparent2` forms, not the mirrored viewer forms.
> §8 of the standalone bible has the clean-image measurements, the version 16
> recipe and the audit fixes.


**Purpose:** the reference for recreating the Scratch 1.4 frame/pane outline in a custom window, and the audit of where the harness rail differs from it.

**Status:** reference and pre-fix audit. The whole-window parity recipe in §6.2 is now implemented as rail layout version 15. Section 5 records the pre-fix state; the annotated screenshot is the pre-fix audit.

**Evidence:**
- Running image: `scratch/base/ScratchAiTesting.image`
- Window: `Scratch 1.4 (Linux) of 2-Dec-11`, 1920 × 1032 screen
- Squeak frame: **1320 × 717** at screen `(8, 31)`, displayed 1:1
- Pre-fix audit: [`docs/media/native-ui-border-audit.png`](media/native-ui-border-audit.png)
- Post-fix screenshot: [`docs/media/native-ui-border-final.png`](media/native-ui-border-final.png)
- Live geometry/colour probe: read-only `instVarNamed:` / `skinAt:` reads, no UI mutation

---

### 1. Executive summary

The pre-fix scope was wrong in five important ways (see the annotated screenshot):

1. **The native UI does not have one border.** It is a mosaic of pane skins with different visible widths:
   - top bar 6 px, viewer left 12 px, stage right 10 px, library right 11 px, bottom 12 px.
2. **Native panes are not left/right symmetric.** The Scripts pane skin is 34 × 56 with a **6 px dark left edge** and a **5 px light right edge**. A horizontal mirror of the left edge is not the native right edge.
3. **The described 9 px mirror does not exist in the built image.** The code appends 9 px, but the copy is a no-op. The rendered right edge is the native Scripts right edge, shifted 10 px inward, followed by a 9 px flat `#7C8083` gutter.
4. **The native bottom edge is 12 px, not 9 px.** It starts at `y = 705` in a 717 px frame. The footer is `685..707`, so it overlaps the frame by 2 px and is visibly clipped.
5. **The native surface is not one flat colour.** The top bar is `#C0C3C6`; pane headers are `#959A9F`; the Scripts page is `#7C8083` with a 48 × 48, 4 px vertical texture. The rail is flat `#7C8083` with no header.

The core parity problem is:

> The rail is a **Scripts-pane skin** used as the **right end of the whole window**. A pane skin cannot supply the native top-bar edge or the native outer-right edge, and appending pixels to it changes its 9-slice geometry.

---

### 2. Coordinate system and whole-window geometry

All values below are Squeak frame coordinates (1 px = 1 screen px).

Native full-width layout (the reference):

| Element | Position | Size | Notes |
|---|---|---|---|
| Frame | `0, 0` | `1320 × 717` | native canvas |
| Top bar (`topPane`) | `0, 0` | `1320 × 34` | full width |
| Viewer pane | `0, 34` | `214 × 683` | `ScratchViewerMorph` |
| Scripts pane | `214, 34` | `612 × 683` | `ScratchScriptEditorMorph` |
| Stage frame | `826, 34` | `494 × 402` | `ImageFrameMorph` + `stagePane` skin |
| Stage content (`workPane`) | `830, 71` | `480 × 360` | 4 px left, 10 px right, 37 px top, 5 px bottom inset |
| Library pane | `826, 436` | `494 × 281` | `ScratchLibraryMorph` |

Harness body composition (layout version 15):

| Element | Position | Size | Notes |
|---|---|---|---|
| Native column | `0, 34` | `968 × 683` | viewer + scripts + stage/library |
| Viewer pane | `0, 34` | `214 × 683` | unchanged |
| Scripts pane | `214, 34` | `260 × 683` | squeezed by the rail |
| Stage frame | `474, 34` | `494 × 402` | ends at the rail seam |
| Stage content (`workPane`) | `478, 71` | `480 × 360` | unchanged stage size |
| Library pane | `474, 436` | `494 × 281` | ends at the rail seam |
| Rail | `968, 34` | `352 × 683` | `AIHarnessChatMorph` |
| Rail page | `968, 78` | `340 × 627` | 12 px right / 12 px bottom reserve |

Native top-bar details:

| Element | Position | Size |
|---|---|---|
| Logo (`#scratchLogo2`) | `12, 8` | `97 × 24` |
| Menu panel | `127, 10` | `257 × 17` |
| Top bar fill | `0, 0` | height 34, `#C0C3C6` |

---

### 3. The native border system

#### 3.1 Native skins and their cut sizes

`ImageFrameMorph` cuts a skin form as follows:

```text
cornerExtent = (form extent - 1) // 2
topLeftForm = form copy: (0@0 extent: cornerExtent)
topRightForm = form copy: ((w - cornerExtent.x)@0 extent: cornerExtent)
bottomLeftForm = form copy: (0@(h - cornerExtent.y) extent: cornerExtent)
bottomRightForm = form copy: ((w - cornerExtent.x)@(h - cornerExtent.y) extent: cornerExtent)
topEdgeForm = 1 px wide x cornerExtent high
leftEdgeForm = cornerExtent wide x 1 px high
rightEdgeForm = cornerExtent wide x 1 px high
bottomEdgeForm = 1 px wide x cornerExtent high
```

The 1 px edge strips are tiled along the edge. **Changing the form size changes `cornerExtent` and silently moves every edge inward.**

| Skin | Form | `cornerExtent` | Used by |
|---|---|---|---|
| `#topPane` | `30 × 28` | `14 × 13` | top bar |
| `#blocksPaletteFrameTransparent2` | `46 × 55` | `22 × 27` | viewer pane / outer left |
| `#scriptPaneFrameTransparent2` | `34 × 56` | `16 × 27` | Scripts pane / rail |
| `#stagePane` | `55 × 94` | `27 × 46` | stage frame / outer right |
| `#spriteLibraryPaneFrameTransparent2` | `44 × 56` | `21 × 27` | library pane / outer bottom-right |
| `#dividedImageFrameBar` | `20 × 11` | — | divider under tabs |
| `#tabOn` / `#tabOff` | `42 × 25` | — | tabs |
| `#typein` | `13 × 21` | `6 × 10` | text input frame |
| `#btn` / `#btnPressed` | `13 × 13` | `6 × 6` | buttons |
| `#deleteCircleButton` | `15 × 15` | — | close button |

#### 3.2 Exact edge profiles

Colours are listed from the outside edge inward, unless stated.

##### `#scriptPaneFrameTransparent2` — 34 × 56

| Edge | Visible width | Colours (outside → inside) |
|---|---|---|
| Left | **6 px** | `#ACAEB1`, `#96989B`, `#96989B`, `#96989B`, `#3C3E40`, `#4C4E50` |
| Right | **5 px** | inside → outside: `#6B6E70`, `#CED0D2`, `#CED0D2`, `#CED0D2`, `#C8CBCD` |
| Top | **8 px** | outside → inside: `#C0C3C6`, `#B5B8BA`, `#A9ABAE`, `#86888A`, `#86888A`, `#484B4D`, `#6E7276`, `#888D91` |
| Bottom | **12 px** | inside → outside: `#6C6F71`, `#D6D8DA`, `#D6D8DA`, `#D6D8DA`, `#CCCFD1`, `#A2A4A7`, `#858789`, `#858789`, `#858789`, `#535353`, `#7F7F7F`, `#9C9C9C` |

Key fact: **left is dark, right is light.** This is a bevel, not a mirror.

##### `#blocksPaletteFrameTransparent2` — 46 × 55 (native outer left)

| Edge | Visible width | Colours (outside → inside) |
|---|---|---|
| Left | **12 px** | `#9C9C9C`, `#CED0D2` ×3, `#C8CBCD`, `#ACAEB1`, `#96989B` ×3, `#3C3E40`, `#5C5F61`, `#717578` |
| Right | **5 px** | inside → outside: `#717578`, `#CED0D2`, `#CED0D2`, `#CED1D3`, `#C8CBCD` |
| Top | **8 px** | `#C0C3C6`, `#B4B7BA`, `#A8ABAE`, `#858789` ×2, `#484B4D`, `#6E7276`, `#888D91` |
| Bottom | **12 px** | `#717578`, `#D6D8DA` ×3, `#CCCFD1`, `#A2A4A7`, `#858789` ×3, `#535353`, `#7F7F7F`, `#9C9C9C` |

##### `#stagePane` — 55 × 94 (native outer right)

| Edge | Visible width | Colours |
|---|---|---|
| Left | **4 px** | `#ACAEB1`, `#96989B` ×3 |
| Right | **10 px** | inside → outside: `#CED0D2` ×3, `#C8CBCD`, `#ACAEB1`, `#96989B` ×3, `#535353`, `#7F7F7F` |
| Top (visible header before content) | 34 px fill + 4 px bevel | `#C0C3C6` (34 px), `#A9ACAF`, `#858789` ×3, then white content |
| Bottom | **5 px** | `#D6D8DA` ×3, `#CCCFD1`, `#C0C3C6` |

##### `#spriteLibraryPaneFrameTransparent2` — 44 × 56 (native outer bottom-right)

| Edge | Visible width | Colours |
|---|---|---|
| Left | **7 px** | `#ACAEB1`, `#96989B` ×3, `#2F3031`, `#484A4B`, `#585A5C` |
| Right | **11 px** | inside → outside: `#6E6F70`, `#CED0D2` ×3, `#C0C3C6`, `#ACAEB1`, `#96989B` ×3, `#535353`, `#7F7F7F` |
| Top | **7 px** | `#A2A4A7`, `#858789` ×3, `#3A3B3C`, `#595B5C`, `#6E6F70` |
| Bottom | **12 px** | `#626566`, `#D8DADB`, `#D8DADB`, `#D6D8DA`, `#CCCFD1`, `#A2A4A7`, `#858789` ×3, `#535353`, `#7F7F7F`, `#9C9C9C` |

##### `#topPane` — 30 × 28 (native top bar)

| Edge | Visible width | Colours |
|---|---|---|
| Left | **6 px** | `#9E9E9E`, `#CED0D2` ×3, `#CACCCF`, `#C6C9CB`, then `#C0C3C6` |
| Right | **6 px** | `#ACADB0`, `#96989B` ×3, `#575757`, `#828282` |
| Top | **6 px** | `#ABABAB`, `#9C9C9C`, `#CED0D2`, `#CCCE...`, `#CDCFD1`, `#C4C7C9`, then `#C0C3C6` |

##### Mirrored outer edge for a custom window

The native outer left is the viewer pane's 12 px left edge. A horizontally
mirrored copy gives the custom window's outer right edge:

| Edge | Visible width | Colours (inside → outside) |
|---|---|---|
| Mirrored outer right | **12 px** | `#717578`, `#5C5F61`, `#3C3E40`, `#96989B` ×3, `#ACAEB1`, `#C8CBCD`, `#CED0D2` ×3, `#9C9C9C` |

In the 34 × 56 frame this is form x4..15 of a 16 px `rightEdgeForm` (x0..3
transparent). It lands at frame x1308..1319. The native outer right in the
unmodified app is the stage pane's 10 px right edge; the mirrored 12 px is a
deliberate whole-window symmetry choice, not the original stage skin.

#### 3.3 Native surfaces

| Surface | Colour | Notes |
|---|---|---|
| Top bar | `#C0C3C6` | 192,195,198 |
| Viewer/Scripts pane header | `#959A9F` | 149,154,159; viewer `topSectionHeight` 125, scripts 90 |
| Page / palette pane | `#7C8083` | 124,128,131 |
| Scripts page texture | 48 × 48 repeat | 4 px vertical stripes: `#66696B`, `#7D8183`, `#75787B`, `#7C8083` |
| Library page | `#6A6A6A` | 106,106,106 |
| Stage content | `#FFFFFF` | 255,255,255 |
| Selected tab | `#B9D7E5` | top `#D1E5EE`, bottom `#9CC7DB` |
| Unselected tab | `#ADADB5` | top `#C6C6CE`, bottom `#8C8C94` |
| Input (`#typein`) | `#5F6265` | 95,98,101, white text |
| Button face | `#EEEEEE` | pressed `#B4B4B4` |
| Close button | `#E8EAEB` fill | 15 × 15; X `#5E5F5F` |

#### 3.4 Typography

| Font key | Height | Used for |
|---|---|---|
| `#Tab` | 13 px (ascent 11, descent 2) | tab labels |
| `#Button` | 12 px | buttons |
| `#Label` | 12 px | labels/status |
| `#DialogBoxMessage` | 15 px | page headings |
| `#UpdatingStringField` | 13 px | text/values/assistant |
| `#Category` | 12 px | palette category buttons |
| `#TalkBubble` | 15 px | user bubble |

#### 3.5 Native pane geometry inside the Scripts pane

| Element | Position | Size |
|---|---|---|
| Scripts pane | `214, 34` | `260 × 683` |
| Tab strip | `229, 101` | `260 × 23` |
| Scripts tab | `229, 101` | `82 × 23` |
| Backgrounds tab | `295, 101` | `115 × 23` |
| Sounds tab | `394, 101` | `82 × 23` |
| Divider (`#dividedImageFrameBar`) | pane top + 90 = `124` | 11 px high |
| Page viewer top | `123` | page begins here |

Tab placement rule: first tab is `pane left + 15`; tabs overlap by 16 px: next x = previous x + previous width − 16. All tabs are 23 px high.

---

### 4. The harness rail as built (pre-fix, layout 13)

Measured from the live image before the whole-window parity change. The current
build is §6.2 (layout version 15).

| Element | Position | Size |
|---|---|---|
| Rail | `968, 0` | `352 × 717` |
| Rail background | `968, 0` | `352 × 717`, `#7C8083` |
| Rail tab pane | `983, 10` | `352 × 23` (right = 1335, clipped) |
| Chat tab | `983, 10` | `68 × 23` |
| Bridge tab | `1035, 10` | `78 × 23` |
| Usage tab | `1097, 10` | `76 × 23` |
| Close button | `1290, 12` | `15 × 15` |
| Chat page | `968, 34` | `352 × 683` |
| History scroller | `968, 34` | `352 × 568` |
| Status line | `1126, 606` | `36 × 12` |
| Input frame | `968, 623` | `352 × 54`, grows to 96 |
| Input editor | `982, 633` | `324 × 42` |
| Clear | `978, 685` | `64 × 22` |
| Undo | `1048, 685` | `56 × 22` |
| Send / Stop | `1234, 685` | `76 × 22` |

Frame construction in `image/36_chat_ui_scratch.st`:

```smalltalk
src := ScratchFrameMorph skinAt: #scriptPaneFrameTransparent2.  "34 x 56"
w := src width.                                                "34"
r := 9.
frameForm := Form extent: (w + r) @ src height depth: 32.      "43 x 56"
src displayOn: frameForm at: 0 @ 0.
0 to: r - 1 do: [:j |
    frameForm
        copyBits: ((w + j) @ 0 corner: (w + j + 1) @ src height)
        from: src
        at: (r - 1 - j) @ 0
        colorMap: nil].
self initFrontFromForm: frameForm topSectionHeight: 34.
```

Live frame parts:

| Part | Size | Consequence |
|---|---|---|
| `topLeftForm` | `21 × 27` | left edge at 968..973 (6 px dark) |
| `topRightForm` | `21 × 27` | right edge inset |
| `rightEdgeForm` | `21 × 1` | visible pixels only at columns 7..11; columns 12..20 transparent |
| `bottomRightForm` | `21 × 27` | bottom-right corner open |
| `leftEdgeForm` | `21 × 1` | columns 0..5 visible |
| `topSectionHeight` | 34 | divider under tabs at y=34 |

Current visible border in frame coordinates:

| Side | Pixels | Colours |
|---|---|---|
| Left | `968..973` | `#ACAEB1`, `#96989B` ×3, `#3C3E40`, `#4C4E50` |
| Top | `0..7` | `#C0C3C6`, `#BDBEC1`, `#B2B5B8`, `#8D8F91` ×2, `#727577`, `#5D6164`, `#7C8185`, `#8F9499` |
| Right | `1306..1310` | `#6B6E70`, `#CED0D2` ×3, `#C8CBCD` |
| Right gutter | `1311..1319` | flat `#7C8083` |
| Bottom | `705..716` | matches native Scripts bottom |
| Gutter bottom-right | `1311..1319 × 705..716` | flat `#7C8083` |

The **mirror copy is a no-op**:

```smalltalk
"source x starts at w+j, outside the 34 px source form"
(w + j) @ 0 corner: (w + j + 1) @ src height
```

The destination is `(r - 1 - j) @ 0`, but the source has no pixels there. Result: the composite is exactly the native 34 px form plus 9 transparent columns. The right-edge form proves it: columns 12..20 of `rightEdgeForm` are transparent.

---

### 5. Pre-fix differences, tied to the screenshot

Screenshot: [`docs/media/native-ui-border-audit.png`](media/native-ui-border-audit.png). Numbers below match the circles in that image. This section is the evidence trail for the state before layout version 15; the implemented geometry is §6.2.

| # | Native | Pre-fix harness | Visible error |
|---|---|---|---|
| 1 | Top bar 6 px edge, fill `#C0C3C6`, height 34, full width 1320 | Native top bar stops at x=968; rail top is Scripts-pane dark bevel | The top outline changes colour and width at x=968; the rail top-left is a fake corner |
| 2 | Scripts pane left 6 px dark, right 5 px light, top 8 px dark, bottom 12 px light | Left/top/bottom use the Scripts skin correctly; right is shifted | The pane border is not the native outline at the right |
| 3 | Native outer right is 10 px at `1310..1319` | Right edge at `1306..1310`, then `#7C8083` at `1311..1319` | A 9 px flat gutter runs the full height and across the bottom-right; the frame is open |
| 4 | Send right = 1310; border begins at 1310 | Border covers `1306..1310` | The right cap of Send is visibly clipped; the input frame and scrollbar are crossed by the same border |
| 5 | Native top edge `#ABABAB`, `#9C9C9C`, `#CED0D2`…; fill `#C0C3C6` | Rail top `#C0C3C6`, `#BDBEC1`, `#B2B5B8`, `#8D8F91`, `#727577`, `#5D6164` | Dark notch at the top of the rail; not a native window edge |
| 6 | Top-right `topPane` corner 14 × 13; bottom-right library corner 21 × 27 | Scripts-pane corners, both inset 9 px | The top-right and bottom-right corners stop 9 px short |
| 7 | Bottom edge 12 px, starts at 705 | Footer bottom 707 | Last 2 px of Clear / Undo / Send are under the frame |
| 8 | Header `#959A9F`; Scripts page `#7C8083` + 4 px texture | Rail page flat `#7C8083`, no header | The rail surface is flatter and darker than the native Scripts pane |
| 9 | One light band + one dark valley at a pane seam | Stage right outer edge + rail Scripts left edge | Two dark lines with a mid band between them: the two windows do not marry |
| 10 | Rounded outer corner mirrored from the native bottom-left | Stage-right / Scripts-bottom hybrid corner | Square notch and white wedge at the bottom-right |

Additional measured differences:

- **Left seam:** stage right border `958..967` (10 px) + rail left border `968..973` (6 px) = **16 px** seam. The native Scripts/Stage seam is `5 + 7 = 12 px`. The rail abuts the outer stage edge instead of an inner edge.
- **Tab vertical position:** rail tabs at `y=10`; native Scripts tabs at `y=101` (pane top + 67). The rail divider is at `y=34`; the native divider is at `y=124`. This is a design deviation, not a rendering bug.
- **Tab pane right end:** rail tab pane is `983..1335` (15 px past the rail right), matching the native pane's 15 px tab-pane overhang. It is clipped at 1320, so the overhang is invisible.
- **Surface texture:** native Scripts page uses `#scriptsPaneTexture` (48 × 48 repeat, 4 px vertical stripes `#66696B`, `#7D8183`, `#75787B`, `#7C8083`). The rail uses flat `#7C8083`.

---

### 6. The bible: recreate the native outline

#### 6.1 Rules

1. **Compose the native mosaic.**
   - top: `#topPane`
   - left: `#blocksPaletteFrameTransparent2`
   - native right: `#stagePane` above, `#spriteLibraryPaneFrameTransparent2` below
   - custom outer right: mirror the viewer left edge (12 px) and bottom-left corner
   - bottom: `#spriteLibraryPaneFrameTransparent2` / Scripts pane bottom
   - panel seam: the left pane's native right edge, with no extra left edge on the right pane
2. **Never append pixels to a skin to make it symmetric.** Use the native form at its native size, or mirror an entire edge/corner for a deliberate whole-window symmetry.
3. **Never scale the skin.** Draw at 1:1 and tile the 1 px edge strips.
4. **Keep the frame in front.** `initFrontFromForm:` makes the interior transparent and draws the border over the content, exactly like the native panes.
5. **Respect each pane's reserve.**
   - Native outer right: 10 px (stage) / 11 px (library).
   - Mirrored custom outer right: 12 px.
   - Native outer bottom: 12 px.
   - Native Scripts pane: left 6, right 5, top 8, bottom 12.
   - Native top bar: 6 px top/left/right.
6. **Use the native colours**, not approximations. See §3.2 and §3.3.
7. **Use the native control skins and fonts.** `#tabOn`/`#tabOff`, `#typein`, `#btn`/`#btnPressed`, `#deleteCircleButton`, `#Tab`, `#Button`, `#Label`, `#DialogBoxMessage`, `#UpdatingStringField`.
8. **Verify with pixel assertions**, not only layout probes. A layout probe that only checks `right <= page right` will not catch a double seam, a missing mirrored corner, or an extra left edge.

#### 6.2 Whole-window parity recipe (implemented in rail layout version 15)

Use this when the custom window should look like the native Scratch application outline.

| Side | Skin | Visible width | Position | Profile |
|---|---|---|---|---|
| Top | `#topPane` | 6 px | `y = 0..5` | `#ABABAB`, `#9C9C9C`, `#CED0D2`, `#CCCE...`, `#CDCFD1`, `#C4C7C9`, then `#C0C3C6` |
| Left | `#blocksPaletteFrameTransparent2` | 12 px | `x = 0..11` (below top bar) | `#9C9C9C`, `#CED0D2` ×3, `#C8CBCD`, `#ACAEB1`, `#96989B` ×3, `#3C3E40`, `#5C5F61`, `#717578` |
| Right | mirrored viewer left edge | 12 px | `x = 1308..1319` | inside → outside: `#717578`, `#5C5F61`, `#3C3E40`, `#96989B` ×3, `#ACAEB1`, `#C8CBCD`, `#CED0D2` ×3, `#9C9C9C` |
| Bottom | `#spriteLibraryPaneFrameTransparent2` / Scripts bottom | 12 px | `y = 705..716` | `#626566`, `#D8DADB` ×2, `#D6D8DA`, `#CCCFD1`, `#A2A4A7`, `#858789` ×3, `#535353`, `#7F7F7F`, `#9C9C9C` |

Corners:

| Corner | Form | Size |
|---|---|---|
| Top-left | `#topPane` top-left (window) | `14 × 13` |
| Top-right | `#topPane` top-right (window) | `14 × 13` |
| Rail top-right | mirrored `#blocksPaletteFrameTransparent2` top-left, cropped to the right 16 columns | `16 × 27` |
| Rail bottom-right | mirrored `#blocksPaletteFrameTransparent2` bottom-left, cropped to the right 16 columns | `16 × 27` |

Layout:

- Top bar: full width `1320 × 34`; fill `#C0C3C6`.
- Body: starts at `y = 34`; native full width is viewer `0,34 214×683`; Scripts `214,34 612×683`; stage `826,34 494×402`; library `826,436 494×281`.
- If a rail is used, it is a **pane inside** the body, not the top bar; the body panes squeeze to the left 968 px.
- **The rail has no left edge.** The native stage/library right edge is the seam; the page starts immediately after it at `x = 968`. This is the same single light-band + dark-valley construction as the native blocks/scripts and scripts/stage seams. See §6.6.
- Reserve **12 px** on the right and **12 px** on the bottom for the frame. The page is `340 × 627` at `968, 78`; a 76 px Send button ends at `1298`, 10 px inside the 1308 page edge. A footer ending at 707 is not correct.
- Tabs: `983, 44`; close `1290, 46`; header `#959A9F`; divider `y = 68`; page `y = 78`.

#### 6.3 Scripts-pane parity recipe

Use this when the custom window is supposed to be a native Scripts pane, not the whole application.

| Property | Value |
|---|---|
| Skin | `#scriptPaneFrameTransparent2`, 34 × 56 |
| Corner extent | 16 × 27 |
| Left / right | 6 px dark / 5 px light |
| Top / bottom | 8 px dark / 12 px light |
| `topSectionHeight` | 90 for a real Scripts pane; 34 for a compact rail |
| Divider | `#dividedImageFrameBar`, 11 px, at `pane top + topSectionHeight` |
| Tabs | `pane left + 15`, `pane top + 67`, 23 px high |
| Page | starts at `pane top + 89` (measured page viewer top 123 with pane top 34) |
| Header | `#959A9F`, from pane top to page top |
| Page | `#7C8083` + `#scriptsPaneTexture` 4 px vertical stripes |
| Content reserve | left 6, right 5, top 8, bottom 12 |

Example placement for the rail at `968,34 352×683` if it is treated as a Scripts pane:

- Left border `968..973`
- Top border `34..41`
- Right border `1315..1319` (5 px)
- Bottom border `705..716` (12 px)
- Tabs at `983, 101`; divider at `y=124`; page at `y=123`
- No 9 px mirror; no 43 px form.

The current whole-window build does **not** use this left edge; it leaves the
rail left open and lets the native stage/library right edge form the seam
(§6.6). It also mirrors the outer left edge for the 12 px right border (§6.7).

#### 6.4 Symmetry note

The native outer window is asymmetric: left 12 px, right 10 px, top 6 px,
bottom 12 px. The native Scripts pane is also asymmetric: left 6 px dark, right
5 px light, top 8 px dark, bottom 12 px light.

The whole-window build deliberately makes the **outer** right a horizontal
mirror of the outer left (12 px), including the mirrored bottom-left corner.
That gives the outer window a symmetrical 12 px left/right and a smooth
bottom-right corner. The internal Scripts pane remains asymmetric; that is
native and intentional.

If exact unmodified native outer-right parity is required instead, use the
stage pane's 10 px right edge. Do not call a broken mirror native; the pre-fix
build did that, and the mirror was both non-native and broken.

#### 6.5 Verification checklist

Use these pixel checks against a 1320 × 717 frame at 1:1.

```text
top edge      y=0..5   x=600    -> #ABABAB, #9C9C9C, #CED0D2, #CCCE.., #CDCFD1, #C4C7C9
top fill      y=20     x=600    -> #C0C3C6
left edge     x=0..11  y=400    -> #9C9C9C, #CED0D2x3, #C8CBCD, #ACAEB1, #96989Bx3,
                                    #3C3E40, #5C5F61, #717578
scripts left  x=214..219 y=400  -> #ACAEB1, #96989Bx3, #3C3E40, #4C4E50
scripts right x=469..473 y=400  -> #6B6E70, #CED0D2x3, #C8CBCD
harness seam  x=958..967 y=400  -> #CED0D2x3, #C8CBCD, #ACAEB1, #96989Bx3,
                                    #535353, #7F7F7F; page starts x=968
outer right   x=1308..1319 y=400 -> #717578, #5C5F61, #3C3E40, #96989Bx3,
                                    #ACAEB1, #C8CBCD, #CED0D2x3, #9C9C9C
bottom edge   y=705..716 x=600  -> #626566/#6C6F71, #D8DADBx2, #D6D8DA, #CCCFD1,
                                    #A2A4A7, #858789x3, #535353, #7F7F7F, #9C9C9C
left form     -> leftEdgeForm must be transparent at 0@0
right form    -> rightEdgeForm transparent at 3@0, opaque at 4@0
footer        send right <= 1308; send bottom <= 705
input         input right <= 1308; history right <= 1308
form          frame form width == 34; cornerExtent == 16; rightEdgeForm width == 16
```

The seam must have **one** dark valley, not two. If a probe finds a second
dark valley between x=968 and x=982, the rail has accidentally drawn a left
edge again.

#### 6.6 Marrying two sections with no seam

The native app never draws a free-standing vertical line between two panes. A
seam is a deliberate two-edge bevel: the **left pane's right edge** supplies the
light band, and the **right pane's left edge** supplies the dark valley. Both
frames are drawn in front of their content. One light band and one dark valley
is the whole construction.

**Blocks → Scripts** at `y = 400` (frame coordinates):

| x | Colour | Role |
|---|---|---|
| 192..208 | `#7C8083` | viewer page |
| 209 | `#717578` | viewer inner shadow |
| 210..211 | `#CED0D2` | viewer right light band |
| 212 | `#CED1D3` | viewer right light band |
| 213 | `#C8CBCD` | viewer right transition |
| 214 | `#ACAEB1` | scripts left mid |
| 215..217 | `#96989B` | scripts left dark band |
| 218 | `#3C3E40` | scripts left inner line |
| 219 | `#4C4E50` | scripts left inner line |
| 220+ | `#7C8083` + texture | scripts page |

The scripts pane starts at x=214. Its 6 px left edge is the dark valley. The
viewer's 5 px right edge is the light band. Total visible seam: **11 px**.

**Scripts → Play window** at `y = 400`:

| x | Colour | Role |
|---|---|---|
| 460..468 | `#7C8083` texture | scripts page |
| 469 | `#6B6E70` | scripts right inner line |
| 470..472 | `#CED0D2` | scripts right light band |
| 473 | `#C8CBCD` | scripts right transition |
| 474 | `#ACAEB1` | stage left mid |
| 475..477 | `#96989B` | stage left dark band |
| 478 | `#7D7D7E` | stage left inner shadow |
| 479 | `#BDBDBE` | stage left highlight |
| 480 | `#EEEEEF` | stage left highlight |
| 481+ | `#FFFFFF` | stage content |

The scripts right edge is 5 px; the stage left edge is 7 px. Total seam:
**12 px**. Again: light band first, dark valley second, then the right page.

Rules for a no-seam marriage:

1. Use the **right edge of the left pane** and the **left edge of the right
   pane**. Do not stack two outer edges.
2. Never put a pane's left edge against another pane's **outer** right edge
   unless you remove one of them. Two outer edges produce two dark valleys.
3. Draw both edges in front of the content so the bevel is continuous over the
   tab strip, page and scrollbars.
4. Terminate the seam at the top/bottom corners. Do not let a vertical left
   edge run into a top or bottom bevel; that creates a square notch.
5. The right page starts immediately after the dark valley.

**Harness deviation (current build):**

The rail has **no left edge**. The native stage/library right edge is the only
seam, at frame x=958..967:

| x | Colour |
|---|---|
| 958..960 | `#CED0D2` |
| 961 | `#C8CBCD` |
| 962 | `#ACAEB1` |
| 963..965 | `#96989B` |
| 966 | `#535353` |
| 967 | `#7F7F7F` |
| 968+ | `#7C8083` rail page |

This is one light band + one dark valley, and it is why the extra line between
the native UI and the harness is gone. It is a one-edge seam rather than the
two-edge native seam. If two-edge native parity is required instead, replace the
stage/library outer right edge with the Scripts right edge (5 px light) and keep
a Scripts left edge (6 px dark) on the rail. The current whole-window build
chooses the single native edge because it is the cleanest no-seam marriage.

The rail's top-left and bottom-left corners keep only the top/bottom bevels;
they have no vertical left edge, so they cannot recreate the extra line.

#### 6.7 Native bottom-left → harness bottom-right

The native bottom-left corner is the **viewer pane** corner, not the Scripts
pane. `#blocksPaletteFrameTransparent2` is 46 × 55 with a 22 × 27 bottom-left
corner. Its construction:

- Left edge: 12 px, `#9C9C9C`, `#CED0D2` ×3, `#C8CBCD`, `#ACAEB1`,
  `#96989B` ×3, `#3C3E40`, `#5C5F61`, `#717578`.
- Bottom edge: 12 px, `#717578`, `#D6D8DA` ×3, `#CCCFD1`, `#A2A4A7`,
  `#858789` ×3, `#535353`, `#7F7F7F`, `#9C9C9C`.
- The outer light rim turns the corner continuously; the inner dark line turns
  with it; the page grey is inside the dark line.
- The corner is a native 22 × 27 quarter-round. It is not a square cut and not a
  separate decorative line.

To reproduce it on the right:

1. Copy the viewer **top-left** and **bottom-left** corners (22 × 27).
2. Flip each horizontally (`flipBy: #horizontal centerAt: center`).
3. Crop the rightmost **16 × 27** columns. This keeps the 12 px mirrored right
   edge and the bottom edge inside a 34 × 56 frame.
4. Build the 16 px `rightEdgeForm` with transparent x0..3 and the mirrored
   viewer left edge at x4..15:
   `#717578`, `#5C5F61`, `#3C3E40`, `#96989B` ×3, `#ACAEB1`, `#C8CBCD`,
   `#CED0D2` ×3, `#9C9C9C` (inside → outside).
5. Keep the Scripts top bevel (8 px) and Scripts bottom bevel (12 px). Keep the
   left/top-left/bottom-left of the rail open as described in §6.6.

The result lands at:

- right border: **1308..1319** (12 px)
- bottom border: **705..716** (12 px)
- bottom-right corner: **1304..1319 × 690..716** (16 × 27)
- page: **340 × 627** at `968, 78`

The previous build used the stage right edge plus the Scripts bottom bevel. That
hybrid did not have the viewer corner's continuous outer rim and inner dark
line, so it produced a square step and a white wedge at the bottom-right. The
mirrored viewer corner is the correct construction.

---

### 7. What this meant for the pre-fix scope

Implemented in layout version 15; retained as the change rationale.

- Keep: `#7C8083` page colour, native tab skins, native button skins, native input, native fonts, native bottom edge, native Scripts top bevel.
- Replace: the 43 × 56 composite and the mirror. Use the native 34 × 56 form, or the whole-window mosaic.
- Remove: the rail left edge. The native stage/library right edge is the seam; the page starts at x=968.
- Mirror: the native viewer left edge (12 px) and bottom-left corner for the harness right edge and bottom-right corner. The right border is `1308..1319`, not `1306..1310`.
- Clear: the footer bottom to `<= 705`; the current `707` overlaps the native bottom edge.
- Decide: top bar full width (`#C0C3C6`) vs split top bar. If the outline must match native, the top bar cannot stop at 968 with a Scripts-pane bevel.
- Add if matching native surfaces: `#959A9F` header and `#scriptsPaneTexture` vertical stripes.

