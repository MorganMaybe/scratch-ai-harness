# Native Scratch UI Bible — Borders, Edges and Geometry

**Purpose:** the reference for recreating the Scratch 1.4 frame/pane outline in a custom window, and the audit of where the harness rail differs from it.

**Status:** reference and pre-fix audit. The whole-window parity recipe in §6.2 is now implemented as rail layout version 15. Section 5 records the pre-fix state; the annotated screenshot is the pre-fix audit.

**Current build note (session 26):** the rail now draws the native Scripts left
edge, top-left and bottom-left corner, so it has a visible 6 px left edge and a
rounded bottom-left. The no-left-edge descriptions in §6.2 and §8 are v17
history, not the current build.

**Evidence:**
- Running image: `scratch/base/ScratchAiTesting.image`
- Window: `Scratch 1.4 (Linux) of 2-Dec-11`, 1920 × 1032 screen
- Squeak frame: **1320 × 717** at screen `(8, 31)`, displayed 1:1
- Pre-fix audit: [`docs/media/native-ui-border-audit.png`](media/native-ui-border-audit.png)
- Post-fix screenshot: [`docs/media/native-ui-border-final.png`](media/native-ui-border-final.png)
- Live geometry/colour probe: read-only `instVarNamed:` / `skinAt:` reads, no UI mutation

---

## 1. Executive summary

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

## 2. Coordinate system and whole-window geometry

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

## 3. The native border system

### 3.1 Native skins and their cut sizes

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

### 3.2 Exact edge profiles

Colours are listed from the outside edge inward, unless stated.

#### `#scriptPaneFrameTransparent2` — 34 × 56

| Edge | Visible width | Colours (outside → inside) |
|---|---|---|
| Left | **6 px** | `#ACAEB1`, `#96989B`, `#96989B`, `#96989B`, `#3C3E40`, `#4C4E50` |
| Right | **5 px** | inside → outside: `#6B6E70`, `#CED0D2`, `#CED0D2`, `#CED0D2`, `#C8CBCD` |
| Top | **8 px** | outside → inside: `#C0C3C6`, `#B5B8BA`, `#A9ABAE`, `#86888A`, `#86888A`, `#484B4D`, `#6E7276`, `#888D91` |
| Bottom | **12 px** | inside → outside: `#6C6F71`, `#D6D8DA`, `#D6D8DA`, `#D6D8DA`, `#CCCFD1`, `#A2A4A7`, `#858789`, `#858789`, `#858789`, `#535353`, `#7F7F7F`, `#9C9C9C` |

Key fact: **left is dark, right is light.** This is a bevel, not a mirror.

#### `#blocksPaletteFrameTransparent2` — 46 × 55 (native outer left)

| Edge | Visible width | Colours (outside → inside) |
|---|---|---|
| Left | **12 px** | `#9C9C9C`, `#CED0D2` ×3, `#C8CBCD`, `#ACAEB1`, `#96989B` ×3, `#3C3E40`, `#5C5F61`, `#717578` |
| Right | **5 px** | inside → outside: `#717578`, `#CED0D2`, `#CED0D2`, `#CED1D3`, `#C8CBCD` |
| Top | **8 px** | `#C0C3C6`, `#B4B7BA`, `#A8ABAE`, `#858789` ×2, `#484B4D`, `#6E7276`, `#888D91` |
| Bottom | **12 px** | `#717578`, `#D6D8DA` ×3, `#CCCFD1`, `#A2A4A7`, `#858789` ×3, `#535353`, `#7F7F7F`, `#9C9C9C` |

#### `#stagePane` — 55 × 94 (native outer right)

| Edge | Visible width | Colours |
|---|---|---|
| Left | **4 px** | `#ACAEB1`, `#96989B` ×3 |
| Right | **10 px** | inside → outside: `#CED0D2` ×3, `#C8CBCD`, `#ACAEB1`, `#96989B` ×3, `#535353`, `#7F7F7F` |
| Top (visible header before content) | 34 px fill + 4 px bevel | `#C0C3C6` (34 px), `#A9ACAF`, `#858789` ×3, then white content |
| Bottom | **5 px** | `#D6D8DA` ×3, `#CCCFD1`, `#C0C3C6` |

#### `#spriteLibraryPaneFrameTransparent2` — 44 × 56 (native outer bottom-right)

| Edge | Visible width | Colours |
|---|---|---|
| Left | **7 px** | `#ACAEB1`, `#96989B` ×3, `#2F3031`, `#484A4B`, `#585A5C` |
| Right | **11 px** | inside → outside: `#6E6F70`, `#CED0D2` ×3, `#C0C3C6`, `#ACAEB1`, `#96989B` ×3, `#535353`, `#7F7F7F` |
| Top | **7 px** | `#A2A4A7`, `#858789` ×3, `#3A3B3C`, `#595B5C`, `#6E6F70` |
| Bottom | **12 px** | `#626566`, `#D8DADB`, `#D8DADB`, `#D6D8DA`, `#CCCFD1`, `#A2A4A7`, `#858789` ×3, `#535353`, `#7F7F7F`, `#9C9C9C` |

#### `#topPane` — 30 × 28 (native top bar)

| Edge | Visible width | Colours |
|---|---|---|
| Left | **6 px** | `#9E9E9E`, `#CED0D2` ×3, `#CACCCF`, `#C6C9CB`, then `#C0C3C6` |
| Right | **6 px** | `#ACADB0`, `#96989B` ×3, `#575757`, `#828282` |
| Top | **6 px** | `#ABABAB`, `#9C9C9C`, `#CED0D2`, `#CCCE...`, `#CDCFD1`, `#C4C7C9`, then `#C0C3C6` |

#### Mirrored outer edge for a custom window

The native outer left is the viewer pane's 12 px left edge. A horizontally
mirrored copy gives the custom window's outer right edge:

| Edge | Visible width | Colours (inside → outside) |
|---|---|---|
| Mirrored outer right | **12 px** | `#717578`, `#5C5F61`, `#3C3E40`, `#96989B` ×3, `#ACAEB1`, `#C8CBCD`, `#CED0D2` ×3, `#9C9C9C` |

In the 34 × 56 frame this is form x4..15 of a 16 px `rightEdgeForm` (x0..3
transparent). It lands at frame x1308..1319. The native outer right in the
unmodified app is the stage pane's 10 px right edge; the mirrored 12 px is a
deliberate whole-window symmetry choice, not the original stage skin.

### 3.3 Native surfaces

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

### 3.4 Typography

| Font key | Height | Used for |
|---|---|---|
| `#Tab` | 13 px (ascent 11, descent 2) | tab labels |
| `#Button` | 12 px | buttons |
| `#Label` | 12 px | labels/status |
| `#DialogBoxMessage` | 15 px | page headings |
| `#UpdatingStringField` | 13 px | text/values/assistant |
| `#Category` | 12 px | palette category buttons |
| `#TalkBubble` | 15 px | user bubble |

### 3.5 Native pane geometry inside the Scripts pane

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

## 4. The harness rail as built (pre-fix, layout 13)

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

## 5. Pre-fix differences, tied to the screenshot

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

## 6. The bible: recreate the native outline

### 6.1 Rules

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

### 6.2 Whole-window parity recipe (implemented in rail layout version 17)

Use this when the custom window should look like the native Scratch application outline.
Version 17 uses the clean image's actual right edge and both right corners: the
native `#spriteLibraryPaneFrameTransparent2` 11 px right edge, its top-right
corner and its bottom-right corner. The sprites/library bottom-right corner at
the docked seam is the **Scripts pane bottom-right corner**, not the library
outer window round. Exact clean-image measurements are in §8.

| Side | Skin | Visible width | Position | Profile |
|---|---|---|---|---|
| Top | `#topPane` | 6 px | `y = 0..5` | `#ABABAB`, `#9C9C9C`, `#CED0D2`, `#CCCE...`, `#CDCFD1`, `#C4C7C9`, then `#C0C3C6` |
| Left | `#blocksPaletteFrameTransparent2` | 12 px | `x = 0..11` (below top bar) | `#9C9C9C`, `#CED0D2` ×3, `#C8CBCD`, `#ACAEB1`, `#96989B` ×3, `#3C3E40`, `#5C5F61`, `#717578` |
| Right | `#spriteLibraryPaneFrameTransparent2` right edge | 11 px | `x = 1309..1319` | inside → outside: `#6E6F70`, `#CED0D2` ×3, `#C0C3C6`, `#ACAEB1`, `#96989B` ×3, `#535353`, `#7F7F7F` |
| Bottom | `#spriteLibraryPaneFrameTransparent2` bottom edge | 12 px | `y = 705..716` | `#626566`, `#D8DADB` ×2, `#D6D8DA`, `#CCCED1`, `#A2A4A7`, `#858789` ×3, `#535353`, `#7F7F7F`, `#9C9C9C` |

Corners:

| Corner | Form | Size |
|---|---|---|
| Top-left | `#topPane` top-left (window) | `14 × 13` |
| Top-right | `#topPane` top-right (window) | `14 × 13` |
| Rail top-right | `#spriteLibraryPaneFrameTransparent2` top-right, cropped to 16 × 27 | `16 × 27` |
| Rail bottom-right | `#spriteLibraryPaneFrameTransparent2` bottom-right, cropped to 16 × 27 | `16 × 27` |

Layout:

- Top bar: full width `1320 × 34`; fill `#C0C3C6`.
- Body: starts at `y = 34`; native full width is viewer `0,34 214×683`; Scripts `214,34 612×683`; stage `826,34 494×402`; library `826,436 494×281`.
- If a rail is used, it is a **pane inside** the body, not the top bar; the body panes squeeze to the left 968 px.
- **The rail has no left edge.** The native stage/library right edge is the seam; the page starts immediately after it at `x = 968`. This is the same single light-band + dark-valley construction as the native blocks/scripts and scripts/stage seams. See §6.6.
- Reserve **11 px** on the right (native library edge) and **12 px** on the bottom. The page is `341 × 627` at `968, 78`; a 76 px Send button ends at `1299`, 10 px inside the 1309 page edge. A footer ending at 707 is not correct.
- Tabs: `983, 56` (native `pane top + topSectionHeight - tab height + 1`); close `1290, 58`; header `#959A9F`; divider `y = 76..82`; page `y = 78`.
- The divider right joint ends at x1313 (`rightMargin` 6), on the library edge inner light rim, so the bar is the native length and the outer dark rim remains.
- While docked, the sprites/library bottom-right corner is replaced by the
  **Scripts pane bottom-right corner**: the scripts 16 × 27 corner is placed in
  the right 16 columns of the library's 21 × 27 corner, with the library page
  colour filling the interior and the library bottom bevel filling rows 15..26.
  This gives the same internal corner as the native Scripts pane instead of the
  library outer window round. The native rounded library corner is restored on
  collapse. See §8.4 and §8.7.

### 6.3 Scripts-pane parity recipe

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

### 6.4 Symmetry note

The native outer window is asymmetric: left 12 px, right 10 px, top 6 px,
bottom 12 px. The native Scripts pane is also asymmetric: left 6 px dark, right
5 px light, top 8 px dark, bottom 12 px light.

The native outer window is asymmetric: left 12 px, right 10 px (stage) / 11 px
(library), top 6 px, bottom 12 px. The native Scripts pane is also asymmetric:
left 6 px dark, right 5 px light, top 8 px dark, bottom 12 px light.

Version 15 deliberately made the **outer** right a horizontal mirror of the
outer left (12 px). The clean-image audit showed that this mirror is a bevel
facing the wrong way on the right (dark inside, light outside), does not
continue the top bar's outer 6 px, and does not match the native bottom-right
corner.

Version 17 uses the native `#spriteLibraryPaneFrameTransparent2` right edge
(11 px) and bottom-right corner (21 × 27) unchanged. That gives a continuous
outer 6 px (`#ACAEB1`, `#96989B` ×3, `#535353`, `#7F7F7F`) from the top bar into
the rail, a light inner band on the correct side, and the native bottom-right
round. The outer window is therefore asymmetric, exactly like native Scratch:
left 12 px, right 11 px, top 6 px, bottom 12 px.

Do not call a broken mirror native. If a custom window must be symmetrical,
mirror the whole edge deliberately and adapt the top bar at the same time; do
not append a mirror to a pane skin. The current build chooses exact native
right-edge parity instead.

### 6.5 Verification checklist

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
outer right   x=1309..1319 y=400 -> #6E6F70, #CED0D2x3, #C0C3C6, #ACAEB1,
                                    #96989Bx3, #535353, #7F7F7F
bottom edge   y=705..716 x=1000 -> #626566, #D8DADBx2, #D6D8DA, #CCCED1,
                                    #A2A4A7, #858789x3, #535353, #7F7F7F, #9C9C9C
tab divider   y=76..82 x=968..1313 -> one cap + 7 visible rows + right joint;
                                    selected tab covers it to y=78
tab strip     x=983..1329 y=56..79 -> tabPane width 346; selected tab merges
library seam  y=705..716 x=944..984 -> continuous library bottom, no teal
left form     -> leftEdgeForm must be transparent at 0@0
right form    -> rightEdgeForm transparent at 4@0, opaque at 5@0 (11 px)
footer        send right <= 1309; send bottom <= 705
input         input right <= 1309; history right <= 1309
form          frame form width == 34; cornerExtent == 16; rightEdgeForm width == 16
bottom form   bottomEdgeForm -> library bottom, visible rows 4..15
library form  libraryPane bottomRightForm squared while docked
```

The seam must have **one** dark valley, not two. If a probe finds a second
dark valley between x=968 and x=982, the rail has accidentally drawn a left
edge again.

### 6.6 Marrying two sections with no seam

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

At the bottom, the left pane is the library, whose native skin supplies a
rounded bottom-right **window** corner at the seam. Version 17 squares that
corner while the rail is docked (library right edge to y704, then the library
bottom edge across the 21 px corner at y705..716). Without that step the
library's round turns away from the rail's straight bottom edge and leaves a
visible hook/teal notch at the seam. The rail's bottom-left has no vertical
edge; its bottom edge continues the library bottom edge at x968.

The rail's top-left and bottom-left corners keep only the top/bottom bevels;
they have no vertical left edge, so they cannot recreate the extra line.

### 6.7 Native library → harness right edge and bottom-right

The clean image's actual right edge is not a mirror. Above `y = 436` it is the
stage pane's 10 px right edge; below it is the library's 11 px right edge. The
window bottom-right is the library's 21 × 27 corner, not the viewer's
bottom-left.

Version 17 uses the `#spriteLibraryPaneFrameTransparent2` right edge and
bottom-right corner for the whole rail:

1. `rightEdgeForm` is 16 × 1: transparent x0..4, then x5..15 =
   `#6E6F70`, `#CED0D2` ×3, `#C0C3C6`, `#ACAEB1`, `#96989B` ×3, `#535353`,
   `#7F7F7F` (inside → outside). It lands at frame x1309..1319.
2. `bottomRightForm` is the rightmost 16 columns of the native library
   bottom-right corner: `16 × 27` at frame `1304..1319 × 690..716`.
3. `topRightForm` is 16 × 27: rows 0..7 are the Scripts top bevel plus the
   constant outer 6 px right edge; rows 8..26 are the library right edge. There
   is **no rounded rail top-right corner**; the `#topPane` top-right corner at
   the top bar supplies the only top-right window corner.
4. `bottomLeftForm` is 16 × 27: rows 0..14 transparent, rows 15..26 the library
   bottom bevel tiled from the 1 px centre column (`#626566`, `#D8DADB` ×2,
   `#D6D8DA`, `#CCCED1`, `#A2A4A7`, `#858789` ×3, `#535353`, `#7F7F7F`,
   `#9C9C9C`).
5. `bottomEdgeForm` is 1 × 16: rows 0..3 transparent, rows 4..15 the library
   bottom bevel. It lands at y705..716.
6. While the rail is docked, the library's own `bottomRightForm` is replaced by
   a square corner: the library right edge runs down to y704, then the library
   bottom edge spans the full 21 px at y705..716. This removes the library's
   rounded window corner from the internal seam. Restore the native rounded
   form when the rail is collapsed.

The result lands at:

- right border: **1309..1319** (11 px)
- bottom border: **705..716** (12 px)
- bottom-right corner: **1304..1319 × 690..716** (16 × 27, border pixel-identical
  to the clean image)
- page: **341 × 627** at `968, 78`

The version 15 mirrored viewer corner is retained only as history. It produced
a dark-inside/light-outside right edge, a visible step at y34 in column 1315,
and a bottom-right corner that did not match the native library corner. The
library form is the correct construction.

---

## 7. What this meant for the pre-fix scope

Implemented in layout version 15; retained as the change rationale.

- Keep: `#7C8083` page colour, native tab skins, native button skins, native input, native fonts, native bottom edge, native Scripts top bevel.
- Replace: the 43 × 56 composite and the mirror. Use the native 34 × 56 form, or the whole-window mosaic.
- Remove: the rail left edge. The native stage/library right edge is the seam; the page starts at x=968.
- Mirror: the native viewer left edge (12 px) and bottom-left corner for the harness right edge and bottom-right corner. The right border is `1308..1319`, not `1306..1310`.
- Clear: the footer bottom to `<= 705`; the current `707` overlaps the native bottom edge.
- Decide: top bar full width (`#C0C3C6`) vs split top bar. If the outline must match native, the top bar cannot stop at 968 with a Scripts-pane bevel.
- Add if matching native surfaces: `#959A9F` header and `#scriptsPaneTexture` vertical stripes.

---

## 8. Clean-image measurements — right edge, bottom seams, tabs and header edges

**Evidence:** `docs/media/native-ui-clean-reference.png` is a screenshot of the
clean image with the rail collapsed (`docs/media/native-ui-clean-frame.png` is
the 1320 × 717 frame crop at screen `(1928, 37)`, 1:1). All values below are
read from that crop and from the live skin forms. The implemented harness is
rail layout version 16 (`image/36_chat_ui_scratch.st`,
`image/37_chat_dock.st`).

### 8.1 Frame and section bounds in the clean image

| Element | Bounds | Notes |
|---|---|---|
| Frame | `0,0 1320×717` | 1:1, no scaling |
| Top bar (`topPane`) | `0,0 1320×34` | fill `#C0C3C6` from y6 |
| Viewer (`blocksPaletteFrameTransparent2`) | `0,34 214×683` | topSectionHeight 117 |
| Scripts (`scriptPaneFrameTransparent2`) | `214,34 612×683` | topSectionHeight 89 |
| Stage (`stagePane`) | `826,34 494×402` | titlePane `826,35 488×36` |
| Stage content (`workPane`) | `830,71 480×360` | white |
| Library (`spriteLibraryPaneFrameTransparent2`) | `826,436 494×281` | topSectionHeight 40 |
| Scripts tab pane | `229,101 612×23` | bottom 124 |
| Scripts divider visible | `y=121..127` | `#dividedImageFrameBar` |

### 8.2 The right edge of the window

The right edge is **three different skins**, not one border.

**Top bar right edge — `#topPane`, 6 px at x1314..1319**

| Rows | x1314 | x1315..1317 | x1318 | x1319 |
|---|---|---|---|---|
| y13..27 | `#ACADB0` | `#96989B` ×3 | `#575757` | `#828282` |
| y28..34 | `#ACAEB1` | `#96989B` ×3 | `#535353` | `#7F7F7F` |

**Stage right edge — `#stagePane`, 10 px at x1310..1319 (y34..435)**

| x | Colour | Role |
|---|---|---|
| 1310..1312 | `#CED0D2` ×3 | light band |
| 1313 | `#C8CBCD` | transition |
| 1314 | `#ACAEB1` | outer mid |
| 1315..1317 | `#96989B` ×3 | outer dark band |
| 1318 | `#535353` | outer dark line |
| 1319 | `#7F7F7F` | outer-most pixel |

At the stage header (y42..65) the same edge starts with `#CBCDD0`,
`#CCCED1`, `#C8CBCD` at x1310..1313. The 6 px `x1314..1319` block is identical
in the top bar and the body; that is why the outer vertical line is continuous.

**Library right edge — `#spriteLibraryPaneFrameTransparent2`, 11 px at
x1309..1319 (y436..716)**

| x | Colour | Role |
|---|---|---|
| 1309 | `#6E6F70` | inner dark line |
| 1310..1312 | `#CED0D2` ×3 | light band |
| 1313 | `#C0C3C6` | inner light rim |
| 1314 | `#ACAEB1` | outer mid |
| 1315..1317 | `#96989B` ×3 | outer dark band |
| 1318 | `#535353` | outer dark line |
| 1319 | `#7F7F7F` | outer-most pixel |

The library edge adds one pixel (`1309`) compared with the stage edge. That is
native: the library is `44×56` and 11 px wide on the right; the stage is `55×94`
and 10 px wide.

**Harness v17**

- `rightEdgeForm` is `16×1`, transparent x0..4, visible x5..15 = the library
  11 px profile. It lands at **1309..1319**.
- Page right boundary is **1309** (content paints through 1308).
- `topRightForm` is the native `#spriteLibraryPaneFrameTransparent2` top-right
  corner, cropped to 16 × 27. The rail therefore has a real rounded top-right
  panel corner below the top bar; the `#topPane` 14 × 13 corner remains the
  window top-right above it.
- Pixel check: `x1309..1319` at y400 and y690 is exactly the library profile;
  column 1315 is `#96989B` continuously from the top bar into the rail.

### 8.3 Right-hand corners

**Top-right — `#topPane` 14×13 (window corner) and library 16×27 (rail corner)**

| Layer | Row / region | Visible profile |
|---|---|---|
| Window | y0..13 | `#topPane` 14×13 corner: `#ABABAB`, `#9C9C9C`, `#CBCDCF`, `#CCCED0`, `#CDCFD1`, `#C4C7C9`; outer 6 px below |
| Window | y15..33 | outer 6 px `#ACADB0`, `#96989B` ×3, `#575757`, `#828282` (y28+ uses `#ACAEB1`/`#535353`/`#7F7F7F`) |
| Rail | y34..60 | native library top-right 16×27: rounded outer rim, inner light band, `#6E6F70`/`#C0C3C6` transition; same shape as the library corner at y436 |

The window top-right is the `#topPane` corner. The rail top-right is the
library panel corner below it; both are present. Do not flatten the rail corner
or draw a mirrored viewer corner.

**Bottom-right — `#spriteLibraryPaneFrameTransparent2` 21×27**

The corner occupies `x1299..1319, y690..716`. Border profile at key rows:

| y | x1305 | x1306 | x1307 | x1308 | x1309 | x1310 | x1311 | x1312 | x1313 | x1314 | x1315 | x1319 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 710 | `#A0A3A5` | `#9D9FA2` | `#979A9C` | `#8C8E90` | `#828486` | `#7E8082` | `#7B7D7F` | `#7C7E80` | `#6D6F70` | `#535455` | `#5A5A5A` | `#AAAAAA` |
| 714 | `#545454` | `#555555` | `#595959` | `#5F5F5F` | `#676767` | `#727272` | `#7F7F7F` | `#8E8E8E` | `#9A9A9A` | `#A4A4A4` | `#A8A8A8` | `#ABABAB` |
| 716 | `#9D9D9D` | `#9E9E9E` | `#A0A0A0` | `#A3A3A3` | `#A6A6A6` | `#A8A8A8` | `#AAAAAA` | `#AAAAAA` | `#ABABAB` | `#ABABAB` | `#ABABAB` | `#ABABAB` |

Column x1315 (outer dark band) from y690:
`#96989B` ×12 (690..701), `#949698`, `#8C8E90`, `#87898B`, `#828486`,
`#848688`, `#828486`, `#67696A`, `#535454`, `#5A5A5A`, `#757575`, `#8F8F8F`,
`#A1A1A1`, `#A8A8A8`, `#ABABAB`, `#ABABAB`.

**Harness v17**

- `bottomRightForm` = the rightmost 16 columns of the native library corner,
  `16×27` at frame `1304..1319 × 690..716`. This corner is final; do not change it.
- Border pixels in that region are **0 diffs** against the clean image (the
  interior differs only because the rail page is `#7C8083` and the native
  library page is `#6A6A6A`).
- The rail's bottom-left has no vertical edge; the library bottom edge continues
  at x968. The sprites/library bottom-right corner is replaced by the Scripts
  pane bottom-right corner while docked; §8.4.

### 8.4 Bottom edge and seamless section connections

**Common outer 7 rows — y710..716, all sections**

| y | Colour |
|---|---|
| 710 | `#A2A4A7` |
| 711..713 | `#858789` ×3 |
| 714 | `#535353` |
| 715 | `#7F7F7F` |
| 716 | `#9C9C9C` |

The bottom border is the same for viewer, scripts, stage and library from y710
outward. Each section supplies its own top 5 rows:

| Section | y705 | y706 | y707 | y708 | y709 |
|---|---|---|---|---|---|
| Viewer (`#blocksPaletteFrameTransparent2`) | `#717578` | `#D6D8DA` | `#D6D8DA` | `#D6D8DA` | `#CCCFD1` |
| Scripts (`#scriptPaneFrameTransparent2`) | `#6C6F71` | `#D6D8DA` | `#D6D8DA` | `#D6D8DA` | `#CCCFD1` |
| Stage (`#stagePane`) | `#626566` | `#D8DADB` | `#D8DADB` | `#D6D8DA` | `#CCCED1` |
| Library (`#spriteLibraryPaneFrameTransparent2`) | `#626566` | `#D8DADB` | `#D8DADB` | `#D6D8DA` | `#CCCED1` |

At a vertical seam, the section-specific 5 rows stop, and the common 7 rows
continue without a vertical line. This is the seamless bottom connection: **the
bottom border is one continuous 7-row rail; only the 5 px above it belongs to
the section.**

**Harness v17**

- `bottomEdgeForm` is `1×16`: rows 0..3 transparent, rows 4..15 = the library
  bottom (`#626566`, `#D8DADB` ×2, `#D6D8DA`, `#CCCED1`, `#A2A4A7`,
  `#858789` ×3, `#535353`, `#7F7F7F`, `#9C9C9C`). It lands at y705..716.
- `bottomLeftForm` is `16×27`: only rows 11..26 are visible, tiled from the
  1 px library centre column. No custom corner and no Y patch.
- **Offset measurement:** the Scripts-style 5 px corner starts its curve at
  x963, while the library right edge is 11 px and begins at x957: a **6 px**
  horizontal offset. The curve is moved left by 6 px by using the native
  library 21 × 27 corner, whose curve starts at x957 and matches the 11 px
  vertical edge exactly. This is why the native corner, not the Scripts
  5 px corner, is the correct form for the sprites box.
- While docked, the library bottom-right form is a copy of the native library
  corner with the transparent area **outside the outer rim** flood-filled with
  the rail page colour `#7C8083`. The fill starts at the form's bottom-right
  pixel and stops at the opaque rim, so the library page inside the corner is
  untouched. The result is one smooth line running around the sprites box:
  11 px vertical edge → curved corner → 12 px bottom edge, with rail page
  outside and library page inside.
- No teal world shows through, and the corner is flush with the dividing line
  at x968 (last sprites pixel x967). On collapse, the unfilled native corner
  is restored for the window outer bottom-right.
- Pixel check: no teal in the seam; the corner's curve starts at the same
  x as the vertical edge; the rail bottom-right corner is untouched and still
  has **0 border diffs**.

### 8.5 The bar below the tabs

**Skin:** `#dividedImageFrameBar`, `20×11`.

The centre column x10 is the reusable 1×11 `barForm`:

| bar row | Colour | Visible? |
|---|---|---|
| 0 | — | transparent |
| 1 | — | transparent |
| 2 | `#888D91` | yes |
| 3 | `#D6D8DA` | yes |
| 4 | `#CCCFD1` | yes |
| 5 | `#A2A4A7` | yes |
| 6 | `#858789` | yes |
| 7 | `#2A2B2C` | yes |
| 8 | `#484A4B` | yes |
| 9 | — | transparent |
| 10 | — | transparent |

**Native Scripts pane**

- Pane top 34, `topSectionHeight` 89. `DividedImageFrameMorph>>drawDividerOn:`
  draws the 11 px form at `top + 89 - 4 = 119`; visible rows **121..127**, page
  top **123**. The divider straddles the header/page boundary (2 px above, 5 px
  below).
- Left joint: 12 px at `x214..225`, form columns 0..11:
  `#C0C3C6`, `#B7BABD`, `#A6A8AB`, `#949698`, `#949799`, `#999B9E`,
  `#9A9C9E`, `#9EA1A3`, `#A2A4A7` ×4 (row y124 / form row 5).
- Centre: tiled from x226 to x813 with the 1 px column.
- Right joint: 12 px at `x814..825`, form columns 8..19; its last pixel is
  `#C0C3C6` at x825, on the Scripts right edge.
- Tabs: `ScratchTabPaneMorph` at `229,101 612×23`; Scripts `229..311`,
  Backgrounds `295..410`, Sounds `394..476`, all 23 px high, overlap 16 px.
- `ScratchTabPaneMorph>>drawSubmorphsOn:` draws the same 1×11 `barForm` under
  the selected tab at `(tabPane left - 13) @ (selected tab bottom - 5)`, clipped
  to the tab pane minus 20 px right. The selected tab therefore covers the
  divider down to its bottom (123); the divider shows below it at 124..127.
  Unselected tabs are covered by the bar from 121..127, so they appear 20 px
  tall. **This is the selected-tab merge.**

**Harness v17**

- `topSectionHeight` = **44**. Pane top 34; divider drawn at `34+44-4 = 74`;
  visible rows **76..82**; page top **78**. This is the same 2-above/5-below
  straddle as native.
- `leftMargin` 0, `rightMargin` 6. The left joint is the full native cap at
  `968..979`; the centre is `980..1301`; the right joint is `1302..1313`. The
  last `#C0C3C6` lands on the library right edge's `#C0C3C6` at x1313, and the
  outer 6 px `1314..1319` is untouched. The bar therefore reaches the inner
  light rim of the rounded top-right corner; it is not clipped by the tab pane
  or the corner.
- Tab pane: `983,56 346×23`. `width = pane width - 6` so the tab pane's own bar
  clip stops at x1309, not inside the 11 px right edge.
- Tabs: Chat `983..1051`, Bridge `1035..1113`, Usage `1097..1173`; close
  `1290,58 15×15`; all labels use `#Tab` 13 px.
- The tab pane's `barForm` is the native 1×11 column again (not a transparent
  form). The selected Chat tab covers the bar to y78; the bar shows at 79..82.
  Bridge/Usage are covered by the bar from y76, so they end at y75. This is the
  native selected-tab merge and the native 20 px unselected tab.
- The tab pane is drawn **after** the pane frame (`AIHarnessChatMorph>>fullDrawOn:`
  draws `tabPane` last, and `drawSubmorphsOn:` skips it), exactly like
  `ScratchScriptEditorMorph>>fullDrawOn:`. Without that layer order the frame's
  divider paints over the selected tab and all tabs look 23 px tall.

### 8.6 Internal edges of header sections — the green-flag stage header

The stage header is the reference for a pane header section with controls.

| Edge | Bounds | Profile |
|---|---|---|
| Top bevel | y34..41 | `#C0C3C6`, `#B4B7BA`, `#A8ABAE`, `#858789` ×2, `#545759`, `#6F7376`, `#888D91` |
| Header fill | y42..65 | `#959A9F` |
| Bottom internal edge | y66..73 | `#6E7276`, `#B6B9BA`, `#CFD1D4`, `#A9ACAF`, `#858789`, `#7D7D7E`, `#BDBDBE`, `#EEEEEF`; then `#FFFFFF` content |
| Left inner edge (y50) | x826..833 | `#ACAEB1`, `#949799`, `#909294` ×2, `#5C5E5F`, `#7C8185`, `#82868A`, `#92979C` |
| Right inner edge (y50) | x1308..1313 | `#92979C`, `#888C90`, `#CBCDD0` ×2, `#CCCED1`, `#C8CBCD` |
| Green flag | `1251..1269 × 46..56` | border `#464646`, fill `#02BB02` |
| Stop | `1279..1295 × 49..57` | border `#464543`, fill `#C70000` |

The green flag and stop sit on `#959A9F`; the header's bottom bevel is the
internal edge between the header and the white stage content. The header's
left/right inner edges are the pane frame's own bevels, not separate lines.

**Harness v16 rail header**

The rail is a tabbed pane, so its internal bottom edge is the divider bar, not
the stage header's 8 px bevel:

| Edge | Bounds | Profile |
|---|---|---|
| Top bevel | y34..41 | Scripts top: `#C0C3C6`, `#B5B8BA`, `#A9ABAE`, `#86888A` ×2, `#484B4D`, `#6E7276`, `#888D91` |
| Header fill | y42..75 | `#959A9F` |
| Internal bottom edge | y76..82 | `#888D91`, `#D6D8DA`, `#CCCFD1`, `#A2A4A7`, `#858789`, `#2A2B2C`, `#484A4B`; selected tab covers 76..78 |
| Left | x958..967 seam | native stage/library right edge; rail has no vertical left edge |
| Right | x1309..1319 | native library right edge (11 px) |
| Close | `1290,58 15×15` | `#deleteCircleButton` |

The stage header and the rail header are adjacent sections with different
`topSectionHeight`s. Their internal bottom edges meet the same vertical seam at
different heights; that is native (the native viewer, scripts and library
headers also have different heights). The rail's top bevel is the Scripts
8 px bevel because the rail is a Scripts-style tabbed pane; at the seam the
native stage top-right bevel is pixel-identical to the rail's rightmost 18
columns, so the outer top edge is continuous.

### 8.7 Version 17 audit fixes (what the screenshot pass found)

1. **Right edge was inverted.** The 12 px mirror of the viewer left edge put
   the dark inner lines (`#717578`, `#5C5F61`, `#3C3E40`) on the inside and the
   light rim `#9C9C9C` on the outside. Native right edges are light inside and
   dark outside. Replaced with the native library 11 px right edge.
2. **Top-right corner was flat / on the wrong layer.** The rail had no rounded
   top-right, so the header met the right edge with a straight step and the tab
   bar looked short. Restored the native library top-right 16 × 27 corner as
   part of the frame. The topPane window corner remains above it.
3. **Bottom-right corner was a mirrored viewer corner.** Replaced with the
   native library bottom-right corner; border pixels now match exactly. This
   corner is final; do not touch it.
4. **Divider gap and double bar.** The rail's divider was at 66..72, the page at
   78, leaving a 5 px header band below the bar; the tab pane's own bar was
   transparent, so the selected tab did not merge and unselected tabs were not
   covered. Set `topSectionHeight` 44, tabs at 56, restored the native 1×11
   `barForm`, and drew the tab pane after the frame.
5. **Bottom profile was Scripts, not library.** The rail bottom used
   `#6C6F71`/`#D6D8DA` and did not marry the library's `#626566`/`#D8DADB`.
   Rebuilt from the library bottom edge.
6. **Sprites/library bottom-right corner was the outer window round.** The
   library is no longer the window outer right when the rail is docked. Replace
   its bottom-right form with the **Scripts pane bottom-right corner** (16 × 27
   in the right 16 columns of the 21 × 27 library corner, library page and
   bottom bevel filling the rest). This gives the same internal corner as the
   native Scripts pane. No Y patch, no top-layer morph, no corner squaring.
7. **Bottom-left gradient.** A 16 px slice of the library corner leaked the
   corner gradient into the rail's bottom-left (`#575A5B`, `#737577`, …).
   Rebuilt from the 1 px centre column for a uniform bottom.
8. **Divider right joint overpainted the outer edge.** A light joint ran to
   x1319 and replaced the dark outer rim. Set `rightMargin` 6 so the joint ends
   at x1313 on the library edge's `#C0C3C6`; the outer 6 px stays intact and
   the bar reaches the inner rim of the rounded corner.

### 8.8 Pixel assertions for the version 17 build

```text
top-right window      x1305..1319 y0..20   -> 0 diffs vs clean frame
rail top-right        x1304..1319 y34..60  -> native library top-right 16x27
right edge            x1309..1319 y400    -> #6E6F70, #CED0D2x3, #C0C3C6,
                                              #ACAEB1, #96989Bx3, #535353, #7F7F7F
right edge            x1309..1319 y690    -> same library profile
bottom-right border   x1304..1319 y690..716 (border pixels) -> 0 diffs
bottom edge           y705..716 x1000     -> #626566, #D8DADBx2, #D6D8DA,
                                              #CCCED1, #A2A4A7, #858789x3,
                                              #535353, #7F7F7F, #9C9C9C
library corner        native library 21x27; outside rim flood-filled #7C8083
library corner offset 0 px (curve starts at x957 with the 11 px edge)
rail bottom-left      straight bottom bevel; no custom corner, no patch
tab divider           y76..82 x968..1313  -> cap + 7 rows + joint
selected tab          y56..78 x1000       -> #B9D7E5, bottom #C0DCE8 at y78
unselected tab        y56..75 x1070       -> #ADADB5, bar covers 76..82
left joint            y79 x968..975       -> #C0C3C6, #B7BABD, #A6A8AB,
                                              #949698, #949799, #999B9E,
                                              #9A9C9E, #9EA1A3
right joint           y79 x1309..1313     -> #BBBEC1, #C0C3C6, #C1C4C7,
                                              #BEC1C4, #C0C3C6
outer edge at divider y79 x1314..1319     -> #ACAEB1, #96989Bx3, #535353, #7F7F7F
form                  frame 34x56; cornerExtent 16x27; rightEdge 16x1;
                      bottomEdge 1x16; topRight 16x27; bottomRight 16x27
layout                page 968,78 341x627; tabs 983,56; divider 76..82;
                      close 1290,58; send right 1299; send bottom 695
library seam          native library 21x27 corner with outside flood-filled
                      #7C8083 while docked; native corner restored on collapse
```

The only intentional surface differences from the clean image are content
colours: the rail page is `#7C8083` where the native library page is `#6A6A6A`,
and the rail header is the tabbed `#959A9F` band where the native library has
its own `New sprite:` band. The border pixels requested above are exact.
