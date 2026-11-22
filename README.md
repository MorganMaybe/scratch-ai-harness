# Scratch AI Harness

A conversational coding harness built into **Scratch 1.4**. Chat with an AI
agent, have it edit real Scratch blocks in the live project, run the project,
and iterate — without leaving Scratch.

This is an unofficial mod of [Scratch 1.4](https://github.com/scratchfoundation/Scratch_1.4)
(GPLv2). It is not affiliated with or endorsed by the Scratch Foundation.

![Scratch AI Harness in windowed release mode](docs/media/release-windowed.png)

## What it does

- A Scratch-styled **Chat / Bridge / Usage** rail docked into the real Scratch
  frame.
- The model returns a JSON block IR; Python validates it, compiles it to native
  Scratch tuples, and Squeak builds real `BlockMorph` stacks.
- Add / replace / delete scripts, variables, lists, sprites, costumes,
  backdrops and stage scripts.
- Per-turn project context (sprites, scripts, ownership, media) plus lazy
  context packs (`clones`, `games`, `scrolling`, `pen-3d`).
- Undo the last change set; user-created scripts stay read-only.
- Async send/stop, token usage, an offline mock profile, record/replay and an
  opt-in audit bundle for model debugging.

## Try the release build

### 1. Download

Grab the latest **`ScratchAIHarness-<version>.zip`** from
[GitHub Releases](https://github.com/MorganMaybe/scratch-ai-harness/releases),
or build it locally (see *Development*).

The bundle contains:

```text
Scratch.exe + plugins        the Scratch 1.4 Squeak VM
ScratchAIRelease.image       clean, windowed, no dev tools
ScratchAiTesting.image       dev image with the 8767 control server
Media / Help / locale        stock Scratch 1.4 assets
bridge/                      local model bridge (Python)
tools/                       control, audit, media and image helpers
```

The release image is an **end-user** image: it opens in a normal 1400×900
window (configurable in `run_release.ps1`), the Scratch frame and chat rail fill
the window client area with no turquoise World border, and the local control
server and source-reload tools are off. It leaves only the Cat in a clean
project. Close it with the rail **Quit** button, **File → Quit**, or **Alt+F4**.

### 2. Add your own API key

The image never contains a key. Store yours once:

```powershell
.\setup.ps1
```

`setup.ps1` installs the Python bridge dependencies and asks for a masked key.
It writes `bridge\.deepseek_key`, which is git-ignored. You can also set
`DEEPSEEK_API_KEY` (or `OPENCODE_GO_API_KEY`) in the environment.

The default profile is **`opencode-go` → `deepseek-v4.1-flash`**, tuned for this
harness: hidden reasoning disabled, 120 s per attempt, 240 s per turn, 16 384
output tokens, 80 000-character prompt budget. A direct DeepSeek key works with
`-Profile deepseek-direct`; a local Ollama server works with `-Profile local`.

### 3. Run

```powershell
.\run_release.ps1
```

Then:

1. Click the **Bridge** tab in the right rail.
2. Click **Start**. The bridge runs on `127.0.0.1:8765`.
3. Go back to **Chat**, type a request, and press **Send**.

Try one of these first:

```text
make the cat draw a spinning hexagon
build a simple platformer with a player, ground and coins
make a bat that flies around and a starfield backdrop
create a calculator with buttons, a display and plus/minus/equals
```

Blocks appear in the Scripts pane. Click the green flag to run them. Use
**Undo** in the rail to revert the last change set.

### Offline test (no key, no network)

```powershell
.\run_bridge.ps1      # deterministic mock bridge on 8765
```

The Chat rail then gets canned scenes from `bridge/examples/`.

## Development

```powershell
git clone https://github.com/MorganMaybe/scratch-ai-harness.git
cd scratch-ai-harness
.\setup.ps1 -Dev
```

`-Dev` installs the bridge in editable mode with pytest and copies
`bridge\harness.ini.example` to `bridge\harness.ini`.

### Runtime

`scratch\base` is intentionally ignored by git. Either:

- use the release bundle (it already has the runtime and both images), or
- copy your own Scratch 1.4 runtime into `scratch\base`; see
  [`scratch/README.md`](scratch/README.md).

### Images

| Image | Purpose |
|---|---|
| `ScratchAiTesting.image` | dev image: control server on 8767, dev dialogs, reload UI |
| `ScratchAIRelease.image` | end-user image: windowed, fills the window, rail Quit button, no control server |
| `ScratchDev.image` | artifact from `tools\build_image.ps1` |

Rebuild the clean dev image while it is running:

```powershell
.\tools\make_clean_image.ps1
```

Rebuild the release image from a clean dev image:

```powershell
.\tools\make_release_image.ps1 -Force
```

`image\40_release_image.st` implements release mode: a stored flag makes
`AIHarness class>>startUp` skip the 8767 server and the dev watchdog, close
Squeak tool windows, call `fillScreenOn` with `TakeOverScreen` **off** (so the
frame fills the normal window, not the whole display), add a release-only
**Quit** button to the rail, and keep the chat rail plus the async dispatcher.

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

Ports: **8765** = chat bridge, **8767** = local dev control. Never expose 8767.

### Tests

```powershell
cd bridge
$env:PYTHONPATH="src"
python -m pytest -q

cd ..
python tools\check_st.py        # static check every image/*.st
```

The bridge tests generate a small media fixture when `scratch\base\Media` is
missing, so they run on a fresh clone and in CI. Live model tests are opt-in:

```powershell
python -m pytest -q -m live
```

See [`TESTING.md`](TESTING.md) for the deterministic mock scene and the manual
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
Smalltalk; it emits a JSON block IR change set. Validation is against the live
context, so undo and manual edits reconcile on the next turn.

- Deep design: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Current as-built state and traps: [`HANDOFF.md`](HANDOFF.md)
- Sprite/stage work package: [`SPRITE_STAGE_SCOPE.md`](SPRITE_STAGE_SCOPE.md)
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

## Licensing and trademarks

- The harness is released under **GPLv2**, matching the Scratch 1.4 source it
  modifies. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
- Scratch, the Scratch logo, Scratch Cat and Gobo are trademarks of the Scratch
  Foundation. This project is an unofficial mod; see
  [`TRADEMARK_POLICY`](TRADEMARK_POLICY).
- The release bundle contains **stock Scratch 1.4 media only**. The locally
  imported Scratch 2.0 sprite/costume/sound libraries are not redistributed;
  the bundle builder excludes them. See [`NOTICE`](NOTICE).
- Your API key belongs in `bridge\.deepseek_key` or the environment. Never put
  it in the image, a project, a log, a screenshot or a commit.

## Status

The end-to-end loop is verified live: chat → project context → bridge →
validate → apply real blocks → reply → undo. The Python suite has 407 offline
tests (2 opt-in live tests) and passes on a fresh clone. See
[`HANDOFF.md`](HANDOFF.md) for the current work package.
