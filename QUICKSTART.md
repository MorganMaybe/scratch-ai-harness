# Quick start

## 1. Extract the release bundle

Download `ScratchAIHarness-<version>.zip` from
[GitHub Releases](https://github.com/MorganMaybe/scratch-ai-harness/releases)
and extract it. Keep the folder layout: the image expects `bridge\` two levels
above `scratch\base\`.

## 2. Add your API key

```powershell
.\setup.ps1
```

Paste your key at the masked prompt. It is saved to `bridge\.deepseek_key`
(git-ignored). The default model is `deepseek-v4.1-flash` on the `opencode-go`
gateway.

Environment alternative:

```powershell
$env:DEEPSEEK_API_KEY = "..."
.\run_release.ps1
```

## 3. Launch

```powershell
.\run_release.ps1
```

Scratch opens in a normal 1400×900 window with the chat rail on the right. The
Scratch UI fills the window; there is no turquoise border. Close it with the
rail **Quit** button, **File → Quit**, or **Alt+F4**. Use
`.\run_release.ps1 -Width 1600 -Height 1000` for a different size.

## 4. Start the bridge

1. Click **Bridge** in the rail.
2. Click **Start**.
3. Wait for `bridge: ok` (both the bridge and the image are local; nothing is
   exposed to the network).

## 5. Build something

Back on **Chat**, send:

```text
make the cat draw a spinning hexagon
```

Expected result: a `when green flag clicked` script with pen setup, a `repeat
6` loop containing `move` and `turn`, on the Cat. Press the green flag.

Other good first prompts:

```text
build a simple platformer with a player, ground and coins
make a bat that flies around and a starfield backdrop
create a calculator with a display and plus/minus/equals
make a pong game with a paddle, ball and score
```

Use **Undo** in the rail to revert the last change set.

## Offline demo

No key or network:

```powershell
.\run_bridge.ps1
```

The mock bridge returns deterministic scenes from `bridge\examples\`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Scratch runtime not found` | Extract the release bundle over the repo root, or read `scratch\README.md`. |
| `No API key found` | Run `.\setup.ps1`. |
| Bridge never says `ok` | Check the `bridge_start.cmd` console window; port 8765 may already be owned by another bridge. |
| Chat says connection refused | Start the bridge from the **Bridge** tab, or run `.\run_live.ps1` in a terminal. |
| Image opens without the rail | Use `ScratchAIRelease.image`; `run_release.ps1` selects it. |
| Need to close it | Click **Quit** in the rail header, use **File → Quit**, or press **Alt+F4**. The Windows title-bar X is unreliable in this Squeak VM. |

More detail: [`README.md`](README.md), [`TESTING.md`](TESTING.md).
