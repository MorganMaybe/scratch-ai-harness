# Squeak 2.8 / Scratch 1.4 — notes and traps

Reference extracted from the previous notes file. `HANDOFF.md` §5 has the short
list; this file is the full set. Everything here cost time once.

## The four that still bite daily

1. Do not click or focus the Scratch window; drive it with `tools\ai_control.py`.
2. A modal dialog (initials, Syntax Error, debugger) blocks the Morphic thread and
   every control command times out. Screenshot, dismiss, retry.
3. Never Ctrl+V in the image (it opens the initials modal). Alt+V only.
4. Use `17c_loader_fix.st`'s loader, never `16a_notifier.st`'s.

---

1. **Workspace compile-time globals.** A workspace compiles the entire script
   before executing it. Referring directly to a class defined in the same script
   gives `unknown variable: AIHarness`. Use:

   ```smalltalk
   (Smalltalk at: #AIHarness) ...
   ```

   or split class creation into its own DoIt.

2. **Select All before DoIt.** If only part of the workspace is selected, Squeak
   executes only that selection. This caused `key not found` when class
   definitions were omitted. Always `Alt+A`, then `Alt+D` (or right-click → do
   it).

3. **`ifEmpty:` does not exist** in this image. Use `frames isEmpty ifTrue: [...]`.

4. **`stackFromTupleList:receiver:` is an instance method** on the sprite:

   ```smalltalk
   stack := sprite stackFromTupleList: tuple receiver: sprite.
   ```

   It was a class method in an earlier source version and was later removed/moved.

5. **`blockFromTuple:receiver:` is also an instance method** in the final image.

6. **`MessageSocket` works** when given `127.0.0.1`; no need to replace it with
   raw sockets.

7. **`TextMorph` vs. `PluggableTextMorph`.** Use
   `PluggableTextMorph on: model text: #inputText accept: #inputText:` for an
   editable input. The chat UI calls `acceptInput` before reading so pending
   edits are committed.

8. **Save often, under a new name.** The image is the source of truth. Keep the
   pristine image untouched.

9. **`ScratchFrameMorph` lookup:**
   `ScratchFrameMorph allInstances select: [:m | m world notNil]`. Use
   `isEmpty ifTrue:`.

10. **Pane placement:** the Phase 0 pane is added to `World`, not the Scratch
    frame, so it stays visible even if frame layout changes. It is floating;
    final docked layout is later.

11. **Workspace compile order.** The workspace compiles the whole script before
    executing any of it. Calling a class method that the same script defines
    (e.g. `openChat`, `sendPrompt`) triggers the **Unknown selector** menu. Use
    `perform:` for the final call, or split the script into two DoIts.

12. **`ifNotNil:` takes a zero-argument block.** `x ifNotNil: [:v | ...]` gives
    `Argument must be 0-argument block`. Use `x ifNotNil: [... x ...]` or assign
    to a temporary first.

13. **`PluggableTextMorph>>accept` treats the setter result as a Boolean.** The
    accept selector (`inputText:`) must end with `^ true`; otherwise the pane
    gets `mustBeBoolean` and a debugger opens.

14. **Use the clipboard, not letter-by-letter typing.** `Alt+V` pastes exactly;
    typing 80+ lines through `pyautogui` can corrupt a quote. Select all
    (`Alt+A`) before DoIt.

15. **Saving:** turn fill screen off via Shift-click on the hidden R hotspot
    (frame `38@10`), open the World menu from the bottom-right gray strip, then
    **save as...**. The dialog accepts a bare name such as `ScratchAI3` and
    writes both image and changes.

16. **The window title can keep a stale `Quit?!` prefix.** It is cosmetic; the
    state is fine.

17. **`respondsTo:` does not exist.** Guard optional APIs another way; calling it
    opens a debugger.

18. **`FileDirectory` is missing `fullName` and `containingDirectory`.** Avoid
    navigating with `FileDirectory`; use an absolute path string instead.

19. **`FileStream readOnlyFileNamed:` accepts backslash Windows paths, not
    forward slashes.** A computed backslash path works; the VM's
    `WinFileDirectory` can still fail on some relative-path helpers, so pass an
    absolute path.

20. **`StandardFileStream>>contents` is broken in this image** (`nil max:`). Use
    `stream contentsOfEntireFile`.

21. **Use the dev loader for iteration.** Paste `10_dev_loader.st` once, then
    load any script with:

    ```smalltalk
    AIHarness load: '09_undo.st'.
    ```

    This reads `image/<name>` and calls `Compiler evaluate:`. No large clipboard
    paste per change.

22. **`Compiler evaluate:` compiles the whole file before executing it.** The
    same unknown-selector rule applies; end scripts with `perform:` when they
    call selectors defined in the same file.

23. **Ctrl+V is not paste in this image — it opens the "type your initials"
    modal.** That modal blocks the Morphic UI thread, so the control server's
    stepping dispatcher stops responding and every socket command times out.
    Use **Alt+V** only for manual paste, or use the control server. If the
    dialog appears, dismiss it (Cancel/Escape) or enter initials once.

24. **Headless control server.**
    - `image/13_dev_server.st` defines the dispatcher, socket server, and
      commands.
    - `image/14_start_server.st` starts it on a fresh image; saved images start
      it from `processStartUpList`.
    - `tools/ai_control.py` is the client:
      ```powershell
      python tools\ai_control.py status
      python tools\ai_control.py load 09_undo.st
      python tools\ai_control.py send "make the hexagon bigger"
      python tools\ai_control.py undo
      python tools\ai_control.py log
      python tools\ai_control.py context
      python tools\ai_control.py save ScratchAI9
      ```
    - `send` returns the chat reply delta, including validation errors.
    - The live bridge must be running on 8765; if `run_live.ps1` reports
      "address already in use", an older bridge process is still alive.
    - Do not load `13_dev_server.st` while a modal dialog is open; the dispatcher
      runs on the UI thread.

25. **"Please type your initials:" is a modal and wedges everything.**
    `Utilities class>>authorInitials` loops on that dialog while `AuthorInitials`
    is empty, and `SystemDictionary>>openSourceFiles` blanks it whenever
    `imageName ~= LastImageName`. Any compile then prompts. `startUp` now calls
    `Utilities setAuthorInitials: 'ai'` on every launch. If it ever appears, type
    initials and click Accept; until it is dismissed every control command times
    out.

26. **Syntax Error windows are worse than the initials dialog.**
    `Compiler>>notify:at:` with `requestor == nil` calls
    `SyntaxError class>>errorInClass:…`, which opens a window and **suspends the
    process**. `ClassDescription>>compile:classified:` passes a `SyntaxError`
    instance, whose `notify:at:in:` does the same. `image/17_safe_dialogs.st`
    patches both paths to log and return nil; `AIHarness load:` then returns
    `error: syntax: …`.

27. **"Name already used in this class"** in a class-side method means a
    **temporary** (or block temp) collides with an instance variable of the
    class object (e.g. `name`, `format`, `subclasses`). Rename the temp
    (`soundName` was the fix in `spriteContextFor:`). Arguments are exempt; temps
    are not.

28. **Method source is nested inside a `.st` file.** Every quote inside a
    `compile: '…'` method string must be doubled, including quotes around
    characters/brackets like `' ['`. One missed pair terminates the outer string
    and the whole file fails to compile. Run
    `python tools\check_st.py image\<file>.st` before loading.

29. **The saved server flag lies after a snapshot.** `AIHarnessDevServerRunning`
    and `AIHarnessDevWatchdogRunning` are globals saved as `true`, but the
    processes do not survive a relaunch. `startUp` probes 8767 with
    `serverAlive`; on a fresh launch it resets the flags and starts the server +
    watchdog (`image/20_startup_fix.st`, `image/21_startup_liveness.st`), and on
    an in-place `snapshot` it leaves the live loop alone.

30. **Do not let the socket loop die on a late reply.** If a client times out and
    disconnects, `ms sendMessage:` can raise and kill the old loop. The rewritten
    `devServerLoop` swallows send errors, rebinds, and updates a heartbeat;
    `startDevWatchdog` restarts it after 20 s without a heartbeat (after a
    liveness probe, so long model calls are not mistaken for death).

31. **Never use Ctrl+C to inspect Squeak text.** It copies to the OS clipboard,
    not a private buffer — and the clipboard may contain the API key. (Use
    screenshots or the log file; never Ctrl+V.)

32. **Identify a blocked image with a screenshot**, not with more commands. The
    dialog/window is visible; the control server cannot respond while it is up.
    `tools\ai_control.py` has no way to dismiss it.

33. **Do not use `16a_notifier.st`'s loader in this image.** Its
    `Compiler>>evaluate:in:to:notifying:ifFail:` path returns `ok load` without
    executing the file. `17c_loader_fix.st` is the robust loader (prefixed temps,
    `Compiler evaluate:`, syntax global) and must be loaded after 17.

34. **Nested `AIHarness load:` from inside a file being evaluated aborts the
    outer evaluation.** That is why `00_bootstrap.st` only installs a `bootstrap`
    command; the actual loop runs in a method activation.

35. **Very large embedded methods can abort silently.** Splitting
    `importSpriteText:` into `importCostumeRecord:`, `importSoundRecord:` and
    `importScriptRecord:` fixed a compile that returned `ok load` but never
    updated the method. If a method in the methodDict still has old literals,
    suspect this.

36. **Pass a bare image name to `Scratch.exe`.** An absolute path with spaces
    makes the VM miss the image and open a Windows file picker.
    `run_scratch.ps1` passes `ScratchAI9.image`/`ScratchDev.image` with
    `scratch/base` as the working directory.

37. **`scalePoint:` is a fraction, `scale` is a percent.** `scalePoint: 80 @ 80`
    sets `scale` to 8000. Use `scalePoint: (percent / 100 @ percent / 100)`.
    There is no `setSizeTo:` on this image's sprite. A 100 @ 100 probe tried to
    build a 10000% form and raised the "space is low" dialog.

38. **`addAndView:` registers and renames the sprite.** It adds it to
    `stage sprites` and gives it `SpriteN`, so set `objName:` *after*
    `addAndView:`. `sprite delete` removes it from the world; `stage sprites`
    still needs `remove:ifAbsent:`.

39. **`true`/`false` inside a hand-written `#(...)` are symbols.** The compiler
    turns `#(#createSprite ... true ...)` into `#true`, not the boolean, which
    fails `ifTrue:`. Wire literals are different: `AILiteralReader` converts bare
    `true`/`false`/`nil` tokens. Build direct test arrays with
    `OrderedCollection`/`Array with:` and a real `true`.

40. **An empty string inside a method source needs four quotes.** In the `.st`
    file write `['''']` (which becomes `['']` in the method), not `['']`. The
    latter ends the outer string; the loader may answer `ok load` while the
    method keeps its old body. If a change seems ignored, check
    `sourceCodeAt:`.

41. **Any recompiled `applyChange:` must keep label recording.** `19_labels.st`
    records `recordLabel:` before `addScript:`; a new override that forgets it
    makes every new script's label empty (and undo restores an empty label).

42. **Avoid `name` as a block argument in an `AIHarness` class method.** It can
    raise "Name already used in this class"; use `eachName`/`aName`. The same
    symptom appears for a genuine method syntax error, so check the source
    before assuming a naming clash.

43. **File > Save As is unusable in dev mode.** The "New File Name?" request is
    auto-answered with the current image name (`ScratchAI9`), which is already
    in use, so it opens a debugger instead of a save dialog. Use
    `python tools\ai_control.py save <name>` or
    `python tools\ai_control.py save-clean <name>`; the latter cleans the
    project first and overwrites a stale target safely.

44. **This Squeak's `ifNotNil:` only takes a zero-argument block.**
    `(expr) ifNotNil: [:value | ...]` is a compile error, even though block
    arguments are fine for `do:`/`collect:`. Use a temporary and a zero-arg
    block, or `ifNil:ifNotNil:` with zero-arg blocks.

45. **`ScratchStageMorph` has `runningBlocks`, not `processes`, in 1.4.0.**
    `^ processes` compiles as a nil temporary, so a stage process accessor
    silently answers nil. Use `processesToRun`, or map `runningBlocks` to
    `scratchProc`.

46. **`ScratchProcess >> includesReceiver:` is dead code in 1.4.0.**
    `ScratchStackFrame` has no `receiver`, so `includesReceiver:` always
    answers false. To find a script's owner, compare the process's top block:
    `p aiTopBlock scriptOwner == self` (add an `aiTopBlock` getter).

47. **UTF8 sprite names are not equal to plain Strings in one direction.**
    Original `objName` values are `UTF8`; `'Sprite1' = sprite objName` is false
    while `sprite objName = 'Sprite1'` is true. `coerceSpriteArg:` used the
    failing direction, so AI literals (plain Strings) could not resolve an
    original sprite by name. Use `asString caseInsensitiveEqual:` for name
    comparisons.

48. **A later `.st` that recompiles `undoRecordFor:`/`undoRecord:` can erase
    sprite undo.** `09_undo.st` only knows scripts and variables;
    `28_sprites_stage.st` extends both methods with `createSprite`,
    `deleteSprite`, `duplicateSprite`, costumes, backdrops and `setSprite`.
    Loading 09 (or a copy of its methods) after 28 silently removes those
    actions: `undoRecordFor:` answers nil, `undoLast` fails, and the preset
    sprites stay. `34_variable_targets.st` now saves the installed methods as
    `baseVariableUndoRecordFor:`/`baseVariableUndoRecord:` and delegates
    everything except target-aware `createVariable`. Load order is
    09 → 28 → 34.

49. **`addMediaItem:` may select the new Stage backdrop.** A probe that adds
    `stars` to test `when backdrop switches to` must switch back to the original
    first; otherwise the later `lookLike: 'stars'` is a no-op and the hat never
    fires. The runtime probe now normalises the backdrop before installing the
    hat.

50. **Double quotes inside a header comment terminate the comment.** A `.st`
    header such as `... with {"load_sprite": ["Name"]} ...` ends at the first
    inner `"`, so the rest of the line is compiled as code and the load answers
    `error: syntax: syntax error compiling in UndefinedObject` even though
    `check_st.py` reports the embedded methods as fine. Keep JSON examples in
    header comments quote-free, or put them in a Markdown file instead.






51. **`Morph` has no `show`, `hide` or `visible:` in this build.** Use
    `isHidden:` and `isHidden`. `delete` sets the hidden flag, so a morph that
    is removed and re-added must be shown again with `isHidden: false`. A hidden
    **parent** still draws its children here, so switch tab pages by detaching
    the inactive pages instead of hiding them.

52. **Submorph positions are absolute, not parent-relative.** `self position`
    is the world coordinate and child layout must add the owner's `left`/`top`
    (this is why Scratch's own code writes `self position + (37@16)`). New UI
    layout code that assumes relative coordinates will be offset by the owner's
    position.

53. **`ifNil:ifNotNil:` blocks take zero arguments in this image.**
    `ifNotNil: [:x | ...]` does not work; the load answers
    `error: syntax: syntax error compiling in UndefinedObject` and the file is
    abandoned. Assign into a temp inside a zero-argument block, or use an
    explicit `nil` check.

54. **`OrderedCollection>>removeAll` and `String>>ifEmpty:` are missing.**
    Use `removeAllSuchThat: [:each | true]` (or assign a new collection) and an
    explicit `isEmpty ifTrue:`.

55. **`MultilineStringMorph` is a `BorderedMorph` and draws a 1 px border by
    default.** Set `borderWidth: 0` for borderless assistant text and chat
    input, or the message looks like a card.

56. **A missing relative `.st` name can open a modal file chooser.**
    `AIHarness load:` prefixes a bare name with `<repo>\image\`; if the file is
    absent, this image may open a file chooser, which wedges the dispatcher
    until it is dismissed. Load probes and scratch files by absolute path
    (a path containing `:`).

57. **`sourceCodeAt:` is instance-side only.** `SomeClass sourceCodeAt: #foo`
    fails for class-side methods; use `SomeClass class sourceCodeAt: #foo`.

58. **`ScrollFrameMorph2` forces its contents to fill the visible extent.**
    `updateContentsExtent` grows the contents to at least the pane size, so it
    is unsuitable for an auto-growing input editor. Put the `#typein`-framed
    `MultilineStringMorph` directly in the frame and shift it up when the text
    overflows; the frame clips it.


59. **A snapshot taken inside a dispatcher command is replayed on the next
    launch.** `#snapshot` and in-place `#save-clean` used to call
    `Smalltalk snapshot: true andQuit: false` while the dispatcher step was
    still handling the request. The saved image resumed mid-command, re-logged
    the command, snapshotted again, and left the VM's "Quit?!" window title up.
    Both now fork a 0.5 s delayed snapshot so the reply is sent first; `startUp`
    also re-applies `updateProjectName` one second later to clear a stale title.
    Wait for the snapshot before killing the VM.

60. **Reloading `15_reply_context.st` used to downgrade the project context.**
    `15` still carried fallback copies of `scriptContextFor:` and
    `spriteContextFor:`. Reloading it after `25`/`28`/`35` recompiled those
    selectors with the old 7-element bodies, silently dropping sprite props,
    script labels and AI-owned script tuples; `load_sprite` then failed with
    “no editable script detail”. Both builders are now guarded with
    `includesSelector:` so a reload only installs them when absent. If an image
    already lost the detail, reload `28` → `34` → `35`; verify with
    `probe_context_methods.st` (`spriteElements=8`, `scriptElements=8`).
