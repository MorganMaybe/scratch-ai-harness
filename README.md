# Scratch AI Harness

This is a personal project of mine: a chat panel bolted onto the side of
Scratch 1.4. You type what you want ("make the cat draw a spinning hexagon"), a
language model writes it as real Scratch blocks in the project that's open, and
you press the green flag to see whether it worked. If it didn't, there's an
Undo button.

It's an unofficial mod of [Scratch 1.4](https://github.com/scratchfoundation/Scratch_1.4)
(GPLv2). It is not affiliated with or endorsed by the Scratch Foundation.

![Scratch AI Harness in windowed release mode](docs/media/release-windowed.png)

## What it does

- A Chat / Bridge / Usage rail docked on the right side of the real Scratch
  window.
- The model replies with a JSON description of blocks. Python checks it,
  compiles it into native Scratch block tuples, and Squeak builds real
  `BlockMorph` stacks out of them.
- It can add, replace and delete scripts, variables, lists, sprites, costumes,
  backdrops and stage scripts.
- Every request carries the current project: sprites, scripts, ownership and
  media. A few optional context packs (`clones`, `games`, `scrolling`,
  `pen-3d`) are loaded only when the model asks for them.
- Undo reverts the last change set. Scripts you wrote by hand are read-only as
  far as the harness is concerned. It won't touch them.
- Sends run in the background, with a Stop button. There's token usage on the
  Usage page, an offline mock profile for testing without a network, and an
  opt-in audit log for figuring out why a model turn went wrong.

## Try the release build

If you just want to kick the tires, the [QUICKSTART](QUICKSTART.md) is the
short version of this section.

### 1. Download

Grab the latest **`ScratchAIHarness-<version>.zip`** from
[GitHub Releases](https://github.com/MorganMaybe/scratch-ai-harness/releases)
(0.1.0 is about 50.6 MB). Or build it yourself; see [Development](#development).

The bundle contains:

```text
Scratch.exe + plugins        the Scratch 1.4 Squeak VM
ScratchAIRelease.image       clean, windowed, no dev tools
ScratchAiTesting.image       dev image with the 8767 control server
Media / Help / locale        stock Scratch 1.4 assets
bridge/                      local model bridge (Python)
tools/                       control, audit, media and image helpers
```

### The release image

`ScratchAIRelease.image` is the end-user version. It opens in a normal
1400×900 window with a title bar. The Scratch frame and the chat rail fill the
window, and no turquoise Squeak World border shows around them. To pick a
different size:

```powershell
.\run_release.ps1 -Width 1600 -Height 1000
```

The release image has no 8767 control server, no dev watchdog and no Reload UI.
It starts with the Cat in a clean project and nothing else.

To close it, use the rail's **Quit** button, **File → Quit**, or Alt+F4. The
Squeak Windows VM ignores the title-bar X, so please don't rely on it. (The
bundled runtime sets `EnableAltF4Quit=1`, which is why Alt+F4 works.)

### 2. Add your own API key

The image never contains a key. Store yours once:

```powershell
.\setup.ps1
```

`setup.ps1` installs the Python bridge dependencies and asks for your key. The
key is masked as you type it and written to `bridge\.deepseek_key`, which is
git-ignored. You can also set `DEEPSEEK_API_KEY` (or `OPENCODE_GO_API_KEY`) in
the environment if you'd rather not have a file.

The default profile is **`opencode-go` → `deepseek-v4.1-flash`**. I tuned the
limits for this harness: hidden reasoning off, 120 seconds per attempt, 240
seconds per turn, 16,384 output tokens and an 80,000-character prompt budget.
If you have a direct DeepSeek key, use `-Profile deepseek-direct`. For a local
Ollama server, use `-Profile local`.

### 3. Run

```powershell
.\run_release.ps1
```

Then:

1. Click the **Bridge** tab in the right rail.
2. Click **Start**. The bridge listens on `127.0.0.1:8765`.
3. Go back to **Chat**, type a request, and press **Send**.

Some prompts to start with:

```text
make the cat draw a spinning hexagon
build a simple platformer with a player, ground and coins
make a bat that flies around and a starfield backdrop
create a calculator with buttons, a display and plus/minus/equals
make a pong game with a paddle, ball and score
```

The blocks show up in the Scripts pane. Click the green flag to run them. If a
change goes sideways, **Undo** in the rail reverts the last change set. Expect
to go back and forth a bit; that's the job.

### Offline test (no key, no network)

```powershell
.\run_bridge.ps1      # deterministic mock bridge on 8765
```

The Chat rail then plays back canned scenes from `bridge/examples/`. This is
the quickest way to check that the image, the rail and the apply path all work
before you spend any tokens.

## Development

```powershell
git clone https://github.com/MorganMaybe/scratch-ai-harness.git
cd scratch-ai-harness
.\setup.ps1 -Dev
```

`-Dev` installs the bridge in editable mode along with pytest, and sets up
`bridge\harness.ini` from the example. See [CONTRIBUTING.md](CONTRIBUTING.md)
before you change anything.

### Runtime

`scratch\base` is git-ignored on purpose. It holds the Scratch VM, the media
and the images, and none of that belongs in the repo. You have two options:

- Use the release bundle. It already has the runtime and both images.
- Copy your own Scratch 1.4 runtime into `scratch\base`. See
  [`scratch/README.md`](scratch/README.md).

### Images

| Image | Purpose |
|---|---|
| `ScratchAiTesting.image` | dev image: control server on 8767, dev dialogs, Reload UI |
| `ScratchAIRelease.image` | end-user image: windowed, frame and rail fill the window, rail Quit button, no control server |
| `ScratchDev.image` | artifact from `tools\build_image.ps1` |

Rebuild the clean dev image while it's running:

```powershell
.\tools\make_clean_image.ps1
```

Rebuild the release image from the clean dev image:

```powershell
.\tools\make_release_image.ps1 -Force
```

`image\40_release_image.st` is where release mode lives. It is loaded last, and
it stores a flag that makes `AIHarness class>>startUp` skip the 8767 server and
the dev watchdog. It closes the Squeak tool windows and calls Scratch's
`fillScreenOn` with `TakeOverScreen` **off**. That's the native Scratch
mechanism for laying the frame out across the window. With takeover off, the
frame fills the normal window instead of the whole display. Release mode also
adds the release-only **Quit** button to the rail and keeps the chat rail and
the async dispatcher.

### Build the image from source

```powershell
# close the running image first (8767 must be free)
.\tools\build_image.ps1 -Seed ScratchAiTesting -Out ScratchDev -Force
.\run_scratch.ps1 -Image ScratchDev.image
```

### Drive the dev image headlessly

```powershell
python tools\ai_control.py status
python tools\ai_control.py send --async "make the hexagon bigger" --wait
python tools\ai_control.py undo
python tools\ai_control.py doctor
```

Ports: **8765** is the chat bridge. **8767** is the dev control server. Never
expose 8767. [SECURITY.md](SECURITY.md) explains why, and it's worth reading
before you run the dev image anywhere that isn't your own desk.

### Tests

```powershell
cd bridge
$env:PYTHONPATH="src"
python -m pytest -q

cd ..
python tools\check_st.py        # static check every image/*.st
```

The bridge tests generate a small media fixture when `scratch\base\Media` is
missing, so they run on a fresh clone and in CI. The live model tests are
opt-in:

```powershell
python -m pytest -q -m live
```

[TESTING.md](TESTING.md) covers the deterministic mock scene and the manual
release checklist.

## How it works

```text
Scratch image (Morphic)                     Python bridge (asyncio)
  chat rail / async worker   --8765-->   parse request + project context
  apply change set on UI     <--         validate -> repair -> compile -> literal
        |                                    |
        +-- undo / registry                  +-- model provider (OpenAI-compatible)
```

Every request carries a full project snapshot. The model never sees Python or
Smalltalk. It emits a JSON block change set, and validation runs against the
live project, so undo and manual edits get reconciled on the next turn.

Further reading, in roughly the order you'd want it:

- Design and protocol: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Where things stand right now: [`HANDOFF.md`](HANDOFF.md)
- Sprite and stage work: [`SPRITE_STAGE_SCOPE.md`](SPRITE_STAGE_SCOPE.md)
- Connection layer: [`DEEPSEEK_CONNECTION_SCOPE.md`](DEEPSEEK_CONNECTION_SCOPE.md)
- Chat rail: [`CHAT_UI_SCOPE.md`](CHAT_UI_SCOPE.md)
- Squeak traps: [`docs/SQUEAK_NOTES.md`](docs/SQUEAK_NOTES.md)
- Model appendix: [`SCRATCH_AI_CONTEXT.md`](SCRATCH_AI_CONTEXT.md)

## Repository layout

```text
bridge/                  Python bridge: agent, providers, IR, validator, compiler, server, tests
image/                   Squeak-side harness and release-mode sources
context/                 lazy model context packs
tools/                   control client, audit, media index, image builders, .st checker
docs/                    Squeak notes, UI map, history, release screenshot
scratch/base/            local Scratch runtime (git-ignored)
setup.ps1                one-time Python + API-key setup
run_release.ps1          launch and size the windowed release image
run_live.ps1             launch the live bridge
run_bridge.ps1           launch the deterministic mock bridge
run_scratch.ps1          launch a dev image (control server)
```

## Known limitations

- User-created scripts are read-only. Editing them needs a confirmation flow
  that doesn't exist yet.
- Custom blocks, sound import and `.sprite` bundle import aren't exposed to the
  harness.
- The title-bar X in the release image doesn't close the app. Use **Quit**,
  **File → Quit** or Alt+F4.
- The dev control server listens on all interfaces. See
  [SECURITY.md](SECURITY.md).
- This is a 2009 Squeak image wearing a new hat. It works, but it has opinions
  about modal dialogs, and it doesn't like being pasted into with Ctrl+V.

## Licensing and trademarks

- The harness is released under **GPLv2**, matching the Scratch 1.4 source it
  modifies. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
- Scratch, the Scratch logo, Scratch Cat and Gobo are trademarks of the Scratch
  Foundation. This project is an unofficial mod. See
  [`TRADEMARK_POLICY`](TRADEMARK_POLICY).
- The release bundle contains **stock Scratch 1.4 media only**. The Scratch 2.0
  sprite, costume and sound libraries I imported locally aren't redistributed,
  and the bundle builder excludes them. See [`NOTICE`](NOTICE).
- Your API key goes in `bridge\.deepseek_key` or the environment. Never put it
  in the image, a project, a log, a screenshot or a commit.

## Status

The end-to-end loop has been run live: chat → project context → bridge →
validate → apply real blocks → reply → undo. The Python suite has 407 offline
tests and 2 opt-in live tests, and it passes on a fresh clone. CI runs on
Windows and Linux with Python 3.11 and 3.13, and it's green. The static `.st`
check runs there too.

For what's done, what's missing and what I'd do next, see
[`HANDOFF.md`](HANDOFF.md). Release history is in
[`RELEASE_NOTES.md`](RELEASE_NOTES.md).
