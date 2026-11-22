# Quick start

The shortest path from the zip to a spinning hexagon. The longer story is in
[README.md](README.md).

## 1. Extract the release bundle

Download `ScratchAIHarness-<version>.zip` from
[GitHub Releases](https://github.com/MorganMaybe/scratch-ai-harness/releases)
and extract it. Keep the folder layout as it is. The image expects `bridge\` to
sit two levels above `scratch\base\`, and it finds things by that layout.

## 2. Add your API key

```powershell
.\setup.ps1
```

Paste your key at the masked prompt. It's saved to `bridge\.deepseek_key`,
which is git-ignored. The default model is `deepseek-v4.1-flash` on the
`opencode-go` gateway.

If you'd rather use an environment variable:

```powershell
$env:DEEPSEEK_API_KEY = "..."
.\run_release.ps1
```

## 3. Launch

```powershell
.\run_release.ps1
```

Scratch opens in a normal 1400×900 window with the chat rail on the right. The
Scratch frame and rail fill the window, with no turquoise border around them.

To close it, click the rail's **Quit** button, use **File → Quit**, or press
Alt+F4. The title-bar X doesn't work in this Squeak VM.

For a different size:

```powershell
.\run_release.ps1 -Width 1600 -Height 1000
```

## 4. Start the bridge

1. Click **Bridge** in the rail.
2. Click **Start**.
3. Wait for `bridge: ok`.

The bridge and the image both run on your machine. The bridge listens only on
loopback; when you send a prompt it makes an outbound HTTPS call to the model
endpoint. Nothing is listening for inbound traffic from the network.

## 5. Build something

Back on **Chat**, send:

```text
make the cat draw a spinning hexagon
```

You should get a `when green flag clicked` script with pen setup and a
`repeat 6` loop containing `move` and `turn`, all on the Cat. Press the green
flag to run it.

Other prompts to try:

```text
build a simple platformer with a player, ground and coins
make a bat that flies around and a starfield backdrop
create a calculator with a display and plus/minus/equals
make a pong game with a paddle, ball and score
```

If something goes wrong, **Undo** in the rail reverts the last change set.

## Offline demo

No key and no network:

```powershell
.\run_bridge.ps1
```

The mock bridge plays back deterministic scenes from `bridge\examples\`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Scratch runtime not found` | Extract the release bundle over the repo root, or read `scratch\README.md`. |
| `No API key found` | Run `.\setup.ps1`. |
| Bridge never says `ok` | Check the `bridge_start.cmd` console window. Port 8765 may already belong to another bridge. |
| Chat says connection refused | Start the bridge from the **Bridge** tab, or run `.\run_live.ps1` in a terminal. |
| Image opens without the rail | Use `ScratchAIRelease.image`. `run_release.ps1` selects it. |
| Need to close it | Click **Quit** in the rail header, use **File → Quit**, or press Alt+F4. The title-bar X is unreliable in this VM. |

More detail is in [README.md](README.md) and [TESTING.md](TESTING.md).
