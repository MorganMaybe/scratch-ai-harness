# UI Tour — the harness rail and Scratch's native UI

This is the “read this before you edit the rail” guide. It explains the UI as a
Morphic object tree, maps every visible region to the method that creates or
lays it out, and shows which files own the native Scratch side.

Line numbers are current as of this guide. Method names are the stable key: if a
line moves, search for `compile: 'methodName`.

---

## 1. The 60-second mental model

Scratch 1.4 is a Squeak image. Its UI is a tree of **Morphs**. Every visible
thing is a morph with:

- `position` and `extent` (in **absolute World coordinates**, not parent-relative)
- `submorphs`
- `drawOn:` / `fullDrawOn:` for painting
- a `fixLayout` convention for recalculating child positions

The harness does **not** reimplement Scratch. It adds one morph,
`AIHarnessChatMorph`, as a child of `ScratchFrameMorph`, and patches one native
layout method, `ScratchFrameMorph>>fixLayout`, to reserve width for it.

There are two layers:

| Layer | What it is | Where it lives |
|---|---|---|
| Native Scratch UI | `topPane`, `viewerPane`, `scriptsPane`, `stageFrame`, `libraryPane`, menus, tabs | Classes inside `ScratchAiTesting.image`; decompiled copies in `scratch/base/` |
| Harness UI | The right-hand rail: frame, header, Chat/Bridge/Usage tabs, pages, transcript, input, buttons | `image/36_chat_ui_scratch.st`, `image/38_bridge_usage_ui.st`, `image/37_chat_dock.st` |

Important: `.st` files are the **source**. The running `.image` is the **binary
and the truth**. Loading a `.st` compiles its methods into the live image. A
method-only edit is visible immediately; a change to `initialize`, instance
variables, or page structure needs the rail instance rebuilt.

---

## 2. The window at a glance

Working frame: **1320 × 717**.

```text
0                                                                   1320
┌────────────────────────────────────────────────────────────────────────┐
│ native top bar: topPane, full width, 34 px                             │ y=0
├───────────────────────────────────────────────┬────────────────────────┤
│                                               │ harness rail           │
│  viewerPane   scriptsPane    stageFrame        │ AIHarnessChatMorph     │
│  (blocks)     (scripts)      ┌──────────────┐  │ 358 × 683              │
│                              │ stage        │  │                        │
│                              │ 480 × 360    │  │  header 44 px          │
│                              ├──────────────┤  │  tabs Chat/Bridge/Usage│
│                              │ libraryPane  │  │  page 347 × 627        │
│                              │              │  │  transcript            │
│                              │              │  │  input                 │
│                              │              │  │  Clear Undo    Send    │
├──────────────────────────────┴──────────────┴──┴────────────────────────┤
│ native bottom edge, 12 px                                              │ y=706
└────────────────────────────────────────────────────────────────────────┘
 x=0         x=214        x=474          x=962                          x=1320
```

Key coordinates (frame at 1320 × 717):

| Element | Bounds | Owner |
|---|---|---|
| Native top bar | `0,0 1320×34` | `ScratchFrameMorph>>fixLayout`, `37:122` |
| Native body | `0,34 968×683` | `37:127-157` |
| Rail outer | `962,34 358×683` | `37:192`, `36:216` |
| Rail header | `962,34 358×44` | `36:277-280`, `36:509` |
| Reload UI button | right of the tabs, left of close | `36:363`, `36:376` |
| Tab strip | `977,56 352×23` | `36:497-504` |
| Divider | around `y=76..82` | `topSectionHeight: 44` |
| Rail page | `962,78 347×627` | `36:492-495` |
| Page right reserve | 11 px | native library right edge |
| Page bottom reserve | 12 px | native bottom edge |
| Footer row | `y=673`, 22 px high | `36:572` |

The native column still ends at `x=968`. The rail’s visual left edge is `x=962`,
so it overlaps the outer 6 px of the native library right edge. The native
reservation is 352 px; the visual rail is 358 px.

The rail page stops at `x=1309` and `y=705` so the native 11 px right edge and
12 px bottom edge draw over empty background instead of clipping controls.

---

## 3. The morph tree, annotated

The rail looks like one giant tree when all three pages are drawn together. It
is actually a shallow shell plus **one** attached page. The pages are
alternatives, not simultaneous children (`showCurrentTab` detaches the inactive
ones at `36:783`). The split below keeps that distinction visible.

### 3.1 Window level

The harness contributes exactly one child to the native frame:

```text
ScratchFrameMorph                         the window
├─ topPane                               native top bar
├─ menuPanel / logoMorph                 File/Edit/Share menus, Scratch logo
├─ viewModeButtonsPanel                  small/large stage, presentation
├─ toolbarPanel                          green flag, stop, etc.
├─ viewerPane                            native blocks palette + sprite chooser
├─ scriptsPane                           native Scripts / Backgrounds / Sounds
│  └─ tabPane                            ScratchTabPaneMorph
├─ stageFrame                            native stage frame
│  ├─ titlePane                          green-flag stage header
│  └─ workPane                           the 480 × 360 stage itself
├─ libraryPane                           native costumes/backdrops/sounds library
├─ readoutPane                           x/y readout
└─ AIHarnessChatMorph                    the harness rail (36:216)
```

Everything above `AIHarnessChatMorph` is native Scratch UI. Everything below it
is harness code.

### 3.2 Rail shell

```text
AIHarnessChatMorph
├─ railBackground (Morph)                #7C8083 fill (36:288)
├─ railHeader (Morph)                    #959A9F 44 px header (36:292)
├─ tabPane (ScratchTabPaneMorph)         Chat / Bridge / Usage (36:321)
├─ collapseButton                        close circle (36:349)
├─ reloadButton                          dev Reload UI (36:363)
└─ currentPage                           exactly one page is attached (36:783)
```

### 3.3 Chat page

```text
chatPage                                 BorderedMorph (36:426)
├─ historyPane                           ScrollFrameMorph2
│  └─ historyMorph                       AIHarnessChatHistoryMorph
│     ├─ AIHarnessChatBubbleMorph        user message
│     ├─ MultilineStringMorph            assistant / error
│     └─ StringMorph                     status
├─ statusMorph                           one-line status (36:443)
├─ inputFrame                            ImageFrameMorph #typein (36:454)
│  └─ inputMorph                         AIHarnessChatInputMorph (36:457)
├─ clearButton                           (36:464)
├─ undoButton                            (36:471)
└─ sendButton                            Send/Stop (36:478)
```

### 3.4 Bridge page

```text
bridgePage                               BorderedMorph (38:20)
├─ contentScroll                         ScrollFrameMorph2 (38:25)
│  └─ contentMorph                       Morph holding row morphs (38:33)
│     └─ row morphs                      heading/section/row/wide/note/gap
├─ refreshBridgeButton                   (38:38)
├─ startBridgeButton                     (38:45; page property)
└─ pingButton                            (38:53)
```

### 3.5 Usage page

```text
usagePage                                BorderedMorph (38:57)
├─ contentScroll                         ScrollFrameMorph2 (38:62)
│  └─ contentMorph                       Morph holding row morphs (38:70)
│     └─ row morphs
└─ refreshUsageButton                    (38:75)
```

The three pages share the row engine (`setPageRows:fields:rows:` and
`layoutFields:page:`), so their subtrees have the same shape. Bridge and Usage
keep their Start/Refresh/Ping buttons outside the scroller.

The rail is a `DividedImageFrameMorph`, not a plain window. That gives it the
native frame slicing and the divider bar. The rail overrides the frame's sliced
corner/edge forms directly in `36:259-267`: left side and bottom-left are native
Scripts, right side and bottom edge are native library.

---

## 4. The native UI: where those sections come from

### 4.1 The original Scratch layout, preserved in the repo

`image/37_chat_dock.st:19-93` contains `fixLayoutWithoutAIChat`, the original
`ScratchFrameMorph>>fixLayout` body, unchanged. This is the best decoder for the
native sections:

| Native element | Lines in `37_chat_dock.st` | Position rule |
|---|---|---|
| `topPane` | 27-30 | `self topLeft`, width = frame width, height from menu/logo |
| `stageFrame` | 32-35 | stage size + `(14@42)`, top of body, right = frame right |
| `workPane` | 37 | `stageFrame topLeft + (4@37)` |
| `titlePane` | 39-42 | stage top, width = stage width − 6, height 36 |
| `viewerPane` | 47-52 | body left, width from palette buttons, full body height |
| `scriptsPane` | 54-58 | right of viewer, remaining width, full body height |
| `libraryPane` | 60-62 | below the stage, width = frame right − scripts right |
| `menuPanel` | 64-66 | beside the logo, vertically centred in top bar |
| `viewModeButtonsPanel` | 68-70 | top right of the stage |
| `stageButtonsPanel` | 72-75 | inside the stage header |
| `readoutPane` | 77-82 | bottom right of the stage |
| `toolbarPanel` | 84-92 | beside the menu, or deleted if it collides |

When the rail is docked, the second method, `fixLayout` at `37:96-200`, repeats
the same body but subtracts `chatWidth`:

| Line | Change |
|---|---|
| `37:99-104` | Read `AIHarnessChat`; `chatWidth = pane width` unless collapsed |
| `37:113-118` | Clamp the rail so the Scripts pane keeps `bareMinimumWidth` |
| `37:122-125` | `topPane` stays full width |
| `37:127-130` | `stageFrame right: self right - chatWidth` |
| `37:142-147` | `viewerPane` width loses `chatWidth` |
| `37:149-153` | `scriptsPane` width loses `chatWidth` |
| `37:155-157` | `libraryPane` width loses `chatWidth` |
| `37:189-197` | Position the rail at `(self right - chatWidth - overlap) @ topPane bottom`, height = body; then mirror the rail corner into the sprites corner |
| `37:198-199` | On collapse, restore the native curved library corner |

So “the harness takes space from Scratch” is exactly those four width/right
subtractions plus the rail placement. Nothing else in the native layout moves.

### 4.2 Decompiled native classes in the repo

| File | Contents |
|---|---|
| `scratch/base/frame_source.txt` | `DividedImageFrameMorph`, `ImageFrameMorph` — how skins are cut and drawn |
| `scratch/base/native_classes_source.txt` | `ScratchTabPaneMorph`, `ScratchPaneDivider`, `ScratchScriptEditorMorph`, `ScratchViewerMorph`, `ScratchLibraryMorph` |
| `scratch/base/native_frame_source.txt` | `ScratchFrameMorph` (large), plus `ImageFrameMorph`, `DividedImageFrameMorph`, `ScratchBlockPaletteMorph` |
| `scratch/base/native_skins.txt` | Dump of skin forms and live pane bounds |
| `scratch/base/rail_geom.txt`, `live_geom.txt` | Captured rail/frame geometry |
| `scratch/base/library_skin.txt`, `topcol.txt`, `tab_order.txt` | Pixel/colour probes |

These dumps are **snapshots**, and some contain several historical versions of
the same method. The live image is authoritative. Regenerate the dump with
`scratch/base/probes/probe_native_skins.st` when you need current values.

### 4.3 How the native frame slices a skin

`ImageFrameMorph` (see `frame_source.txt`) cuts a form into:

- four corners of `cornerExtent = (form extent - 1) // 2`
- one-pixel edge strips that are tiled along each side

`DividedImageFrameMorph` adds a middle divider bar at `topSectionHeight`.
`ScratchTabPaneMorph` draws `#tabOn` / `#tabOff` tabs and a cropped
`#dividedImageFrameBar`.

The rail relies on this. It does not scale a skin. It builds a 34 × 56 form,
then **overwrites the sliced parts** with exact native pieces:

- `topLeftForm`, `topRightForm`, `bottomLeftForm`, `bottomRightForm`
- `leftEdgeForm`, `rightEdgeForm`, `topEdgeForm`, `bottomEdgeForm`

That happens in `36:259-267`. If you change a form's size, you silently change
`cornerExtent` and every edge moves. Use the sizes in
`docs/NATIVE_UI_BIBLE.md` §3.1 and the recipes in §6.

### 4.4 Where the native border measurements live

- `docs/NATIVE_UI_BIBLE.md` §3 — skin sizes, edge colour profiles, native
  surfaces, fonts.
- §6 — how to compose a whole-window outline, seam rules, verification list.
- §8 — clean-image pixel measurements for the right edge, corners, bottom
  seams, tab divider, and the version 17 audit.
- `CHAT_UI_SCOPE.md` §1-7 — the as-built rail spec.

If you are “fixing the look,” start with the screenshot + the pixel assertions
in `NATIVE_UI_BIBLE.md` §6.5 / §8.8, not with guesses from the code.

---

## 5. Code map by UI region

### 5.1 Rail shell, border, header

| UI region | Method / file:line | What it controls |
|---|---|---|
| Rail constructor | `AIHarnessChatMorph>>initialize`, `36:216` | frame forms, header, background, tabs, pages, status |
| Rail outer frame | `36:225-254` | native skin pieces, `topSectionHeight: 44`, edge forms |
| Left edge + bottom-left | `36:227`, `36:246-273` | native Scripts top-left, left edge, expanded 32 × 43 bottom-left corner |
| Right-hand corners | `36:234-262` | top-right Scripts padded with library top-right edge (22 × 27); bottom-right pristine native library corner (21 × 27) |
| Header band | `36:277-280` | plain `Morph`, colour `#959A9F` |
| Rail background | `36:273-276` | plain `Morph`, `ScratchFrameMorph palettePaneColor` `#7C8083` |
| Draw order | `drawSubmorphsOn:`, `36:404`; `fullDrawOn:`, `36:409` | content first, frame over it, tab pane last |
| Size changes | `extent:`, `36:311` | calls `fixLayout` on resize |
| Whole-rail layout | `fixLayout`, `36:487` | page rect, tab strip, close button, header, scrollers, fields, buttons |
| Docking into the window | `ScratchFrameMorph>>fixLayout`, `37:96` | reserves `chatWidth`, positions rail, expands the sprites/rail corners |
| Rail z-order | `37:189-200` | keeps the rail first in the frame submorphs so it draws last |
| Frame partial redraw | `ScratchFrameMorph>>fullDrawOn:`, `37:213` | if damage intersects the rail, skips the native-pane fast path and full-draws; rail last |
| Sprites corner | `nativeCornerOnLibrary`, `37:243`; `restoreLibrarySeam`, `37:299` | copies the Scripts right-hand corner, padded 6 px right; native curve restored on collapse |

### 5.2 Tabs and close button

| UI region | Method / file:line | What it controls |
|---|---|---|
| Tab strip creation | `buildTabs`, `36:321` | `ScratchTabPaneMorph`, `#dividedImageFrameBar`, labels |
| Tab labels | `36:340` | `#('Chat' 'Bridge' 'Usage')` |
| Close/collapse button | `36:349-356` | `#deleteCircleButton`, action `toggleCollapsed` |
| Reload UI button | `ensureReloadButton`, `36:363`; `layoutReloadButton`, `36:376` | dev source reload, left of close |
| Tab placement | `36:497-504` | 15 px left inset, 23 px tabs, y = top + 22 |
| Divider margins | `36:282-285` | `middleBarLeftMargin: 0 rightMargin: 6` |
| Tab selection | `selectTab:`, `36:775` | programmatic selection through the native tab pane |
| Page switching | `showCurrentTab`, `36:783` | detaches inactive pages, attaches one, refreshes Bridge/Usage |
| Current-tab callback | `currentCategory:`, `36:769` | native tab click entry point |

### 5.3 Chat page shell

| UI region | Method / file:line | What it controls |
|---|---|---|
| Chat page | `buildChatPage`, `36:426` | transparent page, history scroller, status, input, buttons |
| Page placement | `36:492-495`, `36:514-515` | left/top, 11 px right reserve, 12 px bottom reserve |
| History scroller | `36:432-437` | `ScrollFrameMorph2`, vertical bar only |
| Status line | `36:443-447` | `StringMorph`, white `#Label`, hidden while `Ready` |
| Page scrollers | `layoutPageScrollers`, `36:536` | Bridge/Usage scroll frame sizing |

### 5.4 Transcript

| UI region | Method / file:line | What it controls |
|---|---|---|
| Stacking messages | `AIHarnessChatHistoryMorph>>fixLayout`, `36:116` | top-to-bottom positions, 7 px gap, 20 px scrollbar reserve |
| User bubble | `AIHarnessChatBubbleMorph`, `36:60-95` | `#talkBubbleFrame`, no pointer, black text |
| Add a message | `addMessage:role text:`, `36:916` | creates entry + morph, trims, scrolls |
| Legacy text routing | `appendLog:`, `36:887` | classifies `You:`, `Error:`, `Applied`, `Undid` |
| Role-specific morph | `morphForMessage:`, `36:929` | bubble, status `StringMorph`, error multiline, assistant multiline |
| Scrolling | `layoutTranscriptScroll:`, `36:977` | width, auto-scroll to newest when at bottom |
| Clear | `clearChat`, `36:1009` | deletes message morphs, resets status (input is left alone) |
| History cap | `trimMessages`, `36:969` | keeps at most 200 entries |
| Read-only log | `logText`, `36:997` | text export used by the control server |

### 5.5 Input and footer

| UI region | Method / file:line | What it controls |
|---|---|---|
| Input frame | `buildInput`, `36:453` | `ImageFrameMorph` with `#typein` |
| Input editor | `AIHarnessChatInputMorph`, `36:141-198` | white-on-dark `MultilineStringMorph`, `#UpdatingStringField` |
| Enter / Shift+Enter | `keyStroke:`, `36:161` | Enter sends, Shift+Enter inserts newline |
| Input growth | `lineWrapFrom:`, `36:189`; `inputChanged`, `36:702` | notify rail after typing |
| Footer buttons | `buildButtons`, `36:463` | Clear / Undo / Send |
| Button wiring | `36:464-483` | targets: rail (Clear), `AIHarness` (Undo, Send) |
| Footer geometry | `layoutInputArea`, `36:562` | button row, input height 54→96, status, history height |
| Send/Stop state | `pending:`, `36:826` | swaps label and width |
| Send action | `AIHarness class>>sendFromChat`, `36:1186`; `sendOrStopFromChat`, `36:1204` | read input, clear, start or cancel |
| Input API | `acceptInput`, `36:854`; `clearInput`, `36:863`; `setInputText:`, `36:871` | control-server compatibility |

### 5.6 Bridge page

| UI region | Method / file:line | What it controls |
|---|---|---|
| Page skeleton | `buildBridgePage`, `38:18` | page, scroller, content, Refresh/Ping |
| Page contents | `applyBridgeInfo:options:error:`, `38:120` | every row: Status, Protocol, Profile, Model, Endpoint, Options |
| Row specs | `38:124-180` | `#heading`, `#section`, `#row`, `#wide`, `#note`, `#gap` |
| Status row update | `bridgeStatusField`, `38:184`; `updateBridgeStatus:`, `38:193` | live “Refreshing…” / Online / Offline |
| Refresh | `refreshBridge`, `38:202`; `fetchBridgeInfo`, `38:209` | background fork, 2 s timeout |
| Ping | `pingBridge`, `38:220`; `fetchPing`, `38:226`; `applyPingResult:`, `38:233` | ping result on the page and status line |
| Button placement | `layoutPageButtons`, `36:610` | Refresh/Ping at top right |

### 5.7 Usage page

| UI region | Method / file:line | What it controls |
|---|---|---|
| Page skeleton | `buildUsagePage`, `38:55` | page, scroller, content, Refresh |
| Page contents | `applyUsageInfo:error:`, `38:246` | model/profile/key presence/token totals/last turn |
| Token formatting | `formatCount:`, `36:1076`; `niceNumber:`, `38:97` | thousands separators, number display |
| Status row update | `usageStatusField`, `38:322`; `updateUsageStatus:`, `38:331` | live status |
| Refresh | `refreshUsage`, `38:346`; `fetchUsage`, `38:353` | background fork |
| Baseline reset | `resetUsageBaseline`, `38:340` | clears last-turn tracking |

### 5.8 Shared row layout (Bridge and Usage)

| UI region | Method / file:line | What it controls |
|---|---|---|
| Rebuild rows | `setPageRows:fields:rows:`, `36:1099` | deletes old row morphs, adds new specs |
| Create one row | `addPageRow:to:fields:`, `36:1119` | heading, section, row, wide, note, gap |
| Position rows | `layoutFields:page:`, `36:626` | 132 px label column, value column, gaps |
| Row primitives | `textOf:`, `field:`, `row:`, `shorten:`, `breakUrl:`, `pagePath:` | formatting helpers |

The same row engine renders both pages. If a Bridge label is in the wrong place,
it is almost always `layoutFields:page:` or the row `role` in
`applyBridgeInfo:options:error:`, not a hand-positioned morph.

### 5.9 Send path that updates the UI

| Step | Method / file:line |
|---|---|
| Enter key or Send button | `36:161`, `36:1204` |
| Read/clear input, mark pending | `36:1186-1202` |
| Start async request | `26_async_send.st:108` |
| Append user bubble, set “Thinking…” | `26:117-120` |
| Background reply | `26:142` |
| UI-thread completion | `26:180` (`applySendCompletion:`) |
| Append assistant/status/error | `26:193-198` |
| Finish: pending false, status, refresh page | `26:199-205` |
| Queue drain | `26:256` / dispatcher |
| Message morph | `36:916` → `36:929` |

If the rail shows a message but the status never settles, inspect the `finish`
block at `26:199-205`. If messages appear in the wrong order, inspect
`AIHarnessChatHistoryMorph>>fixLayout` at `36:116`, which reverses the
front-first submorph list.

### 5.10 Docking, collapse, menu, startup

| UI region | Method / file:line | What it controls |
|---|---|---|
| Create/attach/normalise rail | `ensureDockedChat`, `37:295` | builds pane, widens a too-narrow frame to 1320, attaches, resets Chat/Ready |
| Dispatcher safety net | `ensureChatDocked`, `37:354` | re-docks if the pane vanished |
| Collapse/expand | `AIHarness class>>toggleAIChat`, `37:363` | hides/shows pane and calls `frame fixLayout` |
| Close button | `36:349` → `toggleCollapsed` → `37:363` | same path |
| File > AI Chat | `fileMenu:`, `37:253`, entry at `37:267` | reopen a collapsed rail |
| Reload UI | button `36:389`; menu `37:289`; worker `39:13-20` | reload 36/38/37 and rebuild the rail |
| Startup docking | `startUp`, `37:380` | loads config, starts server, docks rail |
| Native layout rollback | `fixLayoutWithoutAIChat`, `37:19` | original Scratch layout, no `chatWidth` |
| Clean-image reset | `cleanProject`, `29:26` | clears chat/input/pending/pages and selects Chat |

### 5.11 Native skin and form access

| Need | Code |
|---|---|
| Get a native skin form | `ScratchFrameMorph skinAt: #scriptPaneFrameTransparent2` |
| Rail composite form | `36:225-267` |
| Override sliced forms | `36:259-267` |
| Divider bar | `buildTabs`, `36:330-337` |
| Tab skins | `#tabOn` / `#tabOff`, `36:338-345` |
| Close skin | `#deleteCircleButton`, `36:350-351` |
| Input skin | `#typein`, `36:454` |
| User bubble skin | `#talkBubbleFrame`, `36:80` |

Useful skin keys: `#topPane`, `#blocksPaletteFrameTransparent2`,
`#scriptPaneFrameTransparent2`, `#stagePane`,
`#spriteLibraryPaneFrameTransparent2`, `#dividedImageFrameBar`, `#tabOn`,
`#tabOff`, `#typein`, `#btn`, `#btnPressed`, `#deleteCircleButton`,
`#talkBubbleFrame`.

---

## 6. Guided walkthrough: read the rail code in this order

### 6.1 Construction

1. `initialize` (`36:216`) — builds the frame, background, header, then calls
   `buildTabs` and `buildPages`.
2. `buildTabs` (`36:321`) — creates the native tab pane, three tabs, close
   button.
3. `buildChatPage` (`36:426`) — history scroller, status, `buildInput`,
   `buildButtons`.
4. `buildInput` (`36:453`) — `#typein` frame + multiline editor.
5. `buildButtons` (`36:463`) — Clear / Undo / Send.
6. `buildPages` (`36:395`) — calls the Bridge/Usage builders in
   `38_bridge_usage_ui.st`.
7. `fixLayout` (`36:487`) — places everything for the current rail size.
8. `showCurrentTab` (`36:783`) — attaches only the selected page.

### 6.2 Layout

1. `ScratchFrameMorph>>fixLayout` (`37:96`) computes `chatWidth`, lays out the
   native panes, positions the rail, then calls `chatPane fixLayout`.
2. `AIHarnessChatMorph>>fixLayout` (`36:487`) computes:
   - `pageTop = top + 44`
   - `pageW = width - 11`
   - `pageH = bottom - 12 - pageTop`
3. It places the tab strip, close button, header, and all three pages.
4. `layoutInputArea` (`36:562`) stacks footer → input → status → history from
   the bottom up.
5. `layoutTranscriptScroll:` (`36:977`) sizes and scrolls the history.

At 1320 × 717 this yields the documented page `962,78 347×627`, footer at
`y=673`, input `y=611`, status `y=594`, history height 512.

### 6.3 A tab click

1. `ScratchTabPaneMorph` click calls `currentTab:` on the tab pane.
2. The tab pane calls its `targetPane` (`AIHarnessChatMorph`).
3. `currentCategory:` (`36:769`) sets `currentTab`, calls `showCurrentTab` and
   `fixLayout`.
4. `showCurrentTab` deletes the inactive pages (old Morphic still draws hidden
   morphs, so detaching is deliberate), attaches the active page, repaints, and
   refreshes Bridge/Usage if needed.

### 6.4 One user message, end to end

1. `AIHarnessChatInputMorph>>keyStroke:` (`36:161`).
2. `AIHarnessChatMorph>>sendFromChat` (`36:878`) → `AIHarness class>>sendFromChat`
   (`36:1186`).
3. `acceptInput`, read `inputText`, reject empty, `clearInput`,
   `pending: true`, `status: 'Thinking...'`.
4. `sendPromptTextAsync:` → `startSendAsync:` (`26:108`).
5. `appendUser:` adds the bubble; `pending: true` swaps Send to Stop.
6. Background `runSendAsync:` (`26:142`) posts a completion.
7. Dispatcher calls `processSendCompletions` (`26:256`), then
   `applySendCompletion:` (`26:180`).
8. `appendAssistant:` / `appendStatus:` / `appendError:` → `addMessage:role text:`
   (`36:916`) → `morphForMessage:` (`36:929`).
9. `finish` sets `pending: false`, sets the status, refreshes the page
   (`26:199-205`).

That is the full UI data path. If you are debugging “why did the chat show X,”
walk these nine steps.

---

## 7. Coordinates and constants cheat sheet

| Constant | Value | Where |
|---|---|---|
| Frame | 1320 × 717 | `37:317` widens to 1320 |
| Top bar height | 34 | native, `37:125` |
| Rail width | 358 visual (`352` native reserve + `6` overlap) | `dockWidth`/`railOverlap` (`36:208-217`), applied at `36:277` |
| Rail body height | frame height − top bar | `37:193` |
| Header height / `topSectionHeight` | 44 | `36:272`, `36:348` |
| Tab height | 23 | native `#tabOn` form |
| Tab x inset | 15 | `36:502` |
| Tab y | top + 22 | `36:504` |
| Page top | rail top + 44 | `36:493` |
| Page right reserve | 11 | `36:494` |
| Page bottom reserve | 12 | `36:495` |
| Footer button height | 22 | `36:570` |
| Footer gap above bottom | 10 | `36:572` |
| Input height | 54 min, 96 max | `36:580-581` |
| Status gap | 17 above input | `36:583` |
| Transcript gap | 7 | `36:136` |
| Scrollbar reserve | 20 | `36:125`, `36:145` |
| Bridge/Usage label column | 132 | `36:636` |
| Bridge/Usage value width | page width − 156 | `36:637` |
| Max transcript entries | 200 | `36:971` |

The rail width is `dockWidth` (352 native reserve) plus `railOverlap` (6 px),
applied at `36:277`. `fixLayout` subtracts the overlap when sizing the native
column, so the native panes still end at `x=968`. Change both class constants and
the frame widening threshold at `37:315-318` if you want a different width.

---

## 8. How to make a change safely

### 8.1 Start the image

```powershell
.\run_scratch.ps1
```

This prefers `scratch/base/ScratchAiTesting.image`. The image starts its control
server on port 8767 itself. Do not click or focus Scratch; drive it headlessly.

Check health:

```powershell
python tools\ai_control.py status
python tools\ai_control.py doctor
```

### 8.2 Edit the `.st` source

| Change | File |
|---|---|
| Rail shell, tabs, Chat page, transcript, input, buttons, row layout | `image/36_chat_ui_scratch.st` |
| Bridge/Usage content, refresh, ping | `image/38_bridge_usage_ui.st` |
| Docking, native pane widths, native corner, menu, startup | `image/37_chat_dock.st` |
| Send/Stop/pending/status updates | `image/26_async_send.st` |
| Clean reset | `image/29_clean_image.st` |

### 8.3 Load the edit

For a normal method edit:

```powershell
python tools\ai_control.py load 36_chat_ui_scratch.st
```

For continuous work:

```powershell
python tools\watch_st.py
```

The watcher reloads any changed `image/*.st`. It does **not** rebuild the live
rail instance, so use the rebuild helper after constructor/structure changes.

The rail also has a **Reload UI** button and **File > Reload UI**. They reload
`36_chat_ui_scratch.st`, `38_bridge_usage_ui.st` and `37_chat_dock.st` and
rebuild the rail in one action, without the control server. Use them for the
fast visual loop; use `watch_st.py` when you want to edit and watch logs.

### 8.4 Rebuild the rail instance

`initialize`, new instance variables, new pages, or new tab structures only take
effect on a fresh `AIHarnessChatMorph`. The **Reload UI** button already does
this. From the control server, the equivalent is:

```powershell
python tools\ai_control.py load dev_rebuild_rail.st
```

(`image/dev_rebuild_rail.st` deletes the old pane and calls `ensureDockedChat`.)

Method-only edits usually need only `pane fixLayout` or a reload; the rebuild
helper is always safe. `Reload UI` is a source reload, not a VM restart: it does
not reopen the `.image` file. Use `tools\make_clean_image.ps1` or restart Scratch
when you need a fresh image process.

### 8.5 Verify with probes

Probes are executable assertions. Load them by **absolute path**; a missing
relative name can open a file chooser.

```powershell
python tools\ai_control.py load "C:\Users\petes\Documents\opencode projects\Scratch harness\scratch\base\probes\probe_chat_ui_layout.st"
python tools\ai_control.py load "C:\Users\petes\Documents\opencode projects\Scratch harness\scratch\base\probes\probe_chat_ui_messages.st"
python tools\ai_control.py load "C:\Users\petes\Documents\opencode projects\Scratch harness\scratch\base\probes\probe_chat_ui_bridge_usage.st"
python tools\ai_control.py load "C:\Users\petes\Documents\opencode projects\Scratch harness\scratch\base\probes\probe_chat_ui_cancel.st"
python tools\ai_control.py load "C:\Users\petes\Documents\opencode projects\Scratch harness\scratch\base\probes\probe_chat_ui_reload.st"
python tools\ai_control.py log
```

Look for `PROBE ... PASS` and `summary failures=0`. The reload probe returns
`requested`; check the log for `reload ui complete` a few seconds later.

What each probe covers:

| Probe | Covers |
|---|---|
| `probe_chat_ui_layout.st` | rail attached below top bar, right/bottom alignment, native 11 px edge, 12 px bottom, header, divider, tabs, exact Scripts right-hand sprites corner, padded top-right and pristine bottom-right corners, resize, collapse, tab switch |
| `probe_chat_ui_messages.st` | roles, wrapping, auto-scroll, 200 cap, no default text, input growth |
| `probe_chat_ui_bridge_usage.st` | page switching, row fit/wrap, scrollers, offline fallback, no key exposure |
| `probe_chat_ui_cancel.st` | Send/Stop and cancellation |
| `probe_chat_ui_reload.st` | triggers Reload UI; log should show `reload ui complete` |

### 8.6 Screenshot

```powershell
python tools\scratch_gui.py shot docs\media\my-ui-change.png --window
```

Use `--window` for the Scratch window only; omit it for the whole screen.

### 8.7 Save

- Keep project state and UI edits in place: `python tools\ai_control.py snapshot`
- Update the maintained clean baseline (clears scripts/chat, selects Chat):
  `.\tools\make_clean_image.ps1`
- Save under a new name: `python tools\ai_control.py save ScratchAI12`

The image is the source of truth. Keep the pristine `Scratch.image` untouched.

### 8.8 Roll back

- Collapse the rail: File > AI Chat, or the close button.
- Restore the native layout without the rail: call
  `ScratchFrameMorph>>fixLayoutWithoutAIChat` (`37:19`). This does not delete the
  rail; it just lays out the native panes as if the rail were absent.
- Delete the pane and rebuild from the loaded classes with
  `image/dev_rebuild_rail.st`.

---

## 9. Common edits, and exactly where to make them

| I want to… | Edit |
|---|---|
| Move Clear/Undo/Send | `36:570-578` in `layoutInputArea` |
| Make the input taller | `36:580-582` (`inputH` min/max) |
| Change transcript spacing | `36:136` in `AIHarnessChatHistoryMorph>>fixLayout` |
| Change user bubble width | `36:936` (`maxW min: 230`) |
| Change assistant font/colour | `36:957-966` in `morphForMessage:` |
| Change status line behaviour | `36:812` (`status:`) and `36:826` (`pending:`) |
| Change button labels | `36:464-483` in `buildButtons` |
| Add/rename a tab | `36:340`, plus `currentTab` handling in `36:769-804` |
| Add a page | new `buildXPage` in 38, add an ivar in `36:203`, `buildPages` at `36:395`, `showCurrentTab` at `36:783`, `fixLayout` at `36:516-521` |
| Change Bridge rows | `38:120-182` in `applyBridgeInfo:options:error:` |
| Change Usage rows | `38:246-320` in `applyUsageInfo:error:` |
| Change row column widths | `36:636-638` in `layoutFields:page:` |
| Change header/background colours | `36:286-295` in `initialize` |
| Change rail width | `36:208-217` (`dockWidth` + `railOverlap`), `37` native reservation, and the right/bottom reserves |
| Change native pane widths | `37:127-157` in `fixLayout` |
| Fix the right border/seam | `36:225-285`, then `docs/NATIVE_UI_BIBLE.md` §3/§6/§8 |
| Change tab divider | `36:282-285`, `36:330-337`, `topSectionHeight: 44` |
| Change collapse behaviour | `36:842` → `37:363` |
| Add a reload control | button `36:389`; menu `37:289`; worker `39:13-20` |
| Change the reopen menu item | `37:253-282` |

---

## 10. Gotchas that will bite you

1. **Coordinates are absolute World coordinates.** `position:` is not relative
   to the parent. The rail code constantly uses `self left`, `self top`,
   `pageLeft`, etc. to compensate. Do not assume a nested origin.

2. **`ifNil:` / `ifNotNil:` blocks are zero-argument in this image.** Write
   `x ifNotNil: [... x ...]`, never `x ifNotNil: [:v | ...]`.

3. **Hidden morphs still draw in old Morphic.** That is why `showCurrentTab`
   detaches inactive pages instead of hiding them. Follow that pattern for a
   new page.

4. **The frame is drawn in front of content.** `fullDrawOn:` (`36:409`) draws
   the content, then `drawFrameOn:`, then the tab pane. Anything under the 11 px
   right edge or 12 px bottom edge is visually clipped. Reserve space; do not
   move controls into the border.

5. **The tab pane is drawn last on purpose.** That lets the selected tab cover
   the divider and the unselected tabs sit under the bar. If tabs vanish behind
   a page, you broke `fullDrawOn:` / `drawSubmorphsOn:`.

6. **Never scale a skin.** `cornerExtent` is derived from the form size, so
   scaling silently moves every edge. Cut, tile, or mirror native forms at 1:1.

7. **`leftMargin` vs `middleBarLeftMargin:`.** `DividedImageFrameMorph` has
   `leftMargin` / `rightMargin`; the rail calls
   `middleBarLeftMargin:rightMargin:` (`36:285`). The probe asserts
   `rightMargin = 6`, not `leftMargin`.

8. **`layoutVersion` guards are migration shims, not the current version.**
   The rail is version 17. `36:1255` checks 15, `38:429` checks 13, and
   `37:304` checks 17. They only rebuild old panes. If you bump the layout,
   update the guard in 37 if you rely on `ensureDockedChat` to rebuild.

9. **Rail width is two numbers.** `dockWidth` is the 352 px native reserve;
   `railOverlap` is the 6 px visual overlap. The visual rail is 358 px at
   `36:277`, and `fixLayout` subtracts the overlap for the native column. Change
   both constants if you resize the rail.

10. **Some fields are legacy or dead.** `placeholderMorph` is always nil
    (`36:460`), `inputScroller` is never assigned, `showEmptyState` /
    `hideEmptyState` are never called, and `AIHarnessChatPaneMorph` is the old
    floating pane kept inert. Do not chase them while fixing the rail.

11. **Clear does not clear the input.** `clearChat` (`36:1009`) only empties the
    transcript and resets status. `cleanProject` (`29:59-70`) separately calls
    `clearInput`. If you “fix” Clear to clear input, that is a behaviour change.

12. **Buttons need both target and selector.** `ScratchFrameMorph
    buttonLabel:selector:` does not wire the target for you. Clear targets the
    rail; Undo and Send target `AIHarness` (`36:464-483`).

13. **Send is asynchronous.** The UI must not block. The button becomes Stop
    while `pending` is true. If the status sticks, inspect `26:199-205` and
    `36:826`.

14. **Bridge/Usage fetch on a background fork.** Never touch morphs from that
    fork. Results go through `AIHarnessChatCompletions`, drained by
    `processChatUiCompletions` (`36:1225`) in the dispatcher (`38:395`).

15. **Protocol indices are 1-based and fixed.** `#info` has 9 elements,
    `#options` has 10, `#usage` has 9. If you add a field, update the apply
    method and the bridge tests together.

16. **Load order for a full rebuild is 36 → 38 → 37.** 37 patches
    `ScratchFrameMorph` and runs `ensureDockedChat`; it must be last.

17. **A modal dialog wedges the dispatcher.** Never use Ctrl+V in the image; it
    opens the initials dialog. Use Alt+V if you must paste manually. Prefer the
    control server.

18. **The running image is authoritative.** The decompiled `native_*_source.txt`
    dumps are snapshots and can contain duplicate historical methods. Regenerate
    with probes when in doubt.

19. **Reload UI is a source reload, not an image reload.** It reloads
    36/38/37, rebuilds the pane, and preserves the selected tab and input text.
    It clears the transcript and does not reload 39 or restart the VM. If the
    rail is broken, use File > Reload UI; if the whole frame is broken, restart
    Scratch.

---

## 11. File ownership summary

| File | Owns |
|---|---|
| `image/36_chat_ui_scratch.st` | `AIHarnessChatMorph`, tabs, Chat page, transcript, input, buttons, shared row layout |
| `image/38_bridge_usage_ui.st` | Bridge and Usage page contents, refresh/ping, background request, completion drain |
| `image/39_ui_reload.st` | dev Reload UI worker: reload 36/38/37 and rebuild the rail |
| `image/37_chat_dock.st` | docked `ScratchFrameMorph>>fixLayout`, native seam/corner, `ensureDockedChat`, collapse, File menu, startup |
| `image/26_async_send.st` | async send/cancel and the status/pending updates the UI displays |
| `image/29_clean_image.st` | clean-image UI reset |
| `image/00_bootstrap.st` | full load order |
| `docs/NATIVE_UI_BIBLE.md` | native borders, skins, geometry, pixel assertions |
| `CHAT_UI_SCOPE.md` | as-built rail layout spec |
| `docs/SQUEAK_NOTES.md` | Squeak 2.8 traps |
| `scratch/base/probes/*.st` | executable UI assertions |
| `scratch/base/frame_source.txt` | decompiled `ImageFrameMorph` / `DividedImageFrameMorph` |
| `scratch/base/native_classes_source.txt` | decompiled tab pane, script editor, viewer, library |
| `scratch/base/native_frame_source.txt` | decompiled `ScratchFrameMorph` and related classes |
| `scratch/base/native_skins.txt`, `rail_geom.txt`, `live_geom.txt` | captured forms and geometry |

---

## 12. Suggested first exercise

If you want to learn by changing one thing, try this:

1. Open `image/36_chat_ui_scratch.st` and find `layoutInputArea` (`36:562`).
2. Change the footer button gap from `10` to `14` at `36:572`.
3. Save the file, then press **Reload UI** in the rail header (or File >
   Reload UI). The button loads the edited source and rebuilds the rail.
4. If you prefer the control server:
   `python tools\ai_control.py load 36_chat_ui_scratch.st`.
5. Run `probe_chat_ui_layout.st` and `probe_chat_ui_messages.st`.
6. Screenshot and compare with the previous image.

That exercise touches the layout path without changing the frame, tabs, or
native integration. Once that is comfortable, try moving the Send button, then
adding a row to the Bridge page, then changing the rail width.
