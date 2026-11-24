# Testing

There are three layers: the Python tests (which need no Scratch runtime), a
short deterministic check against the dev image, and a manual checklist for
the release image. The automated layers run in CI. The manual one is the one I
actually trust, so don't skip it before a release.

## Automated (fresh clone, no Scratch runtime)

```powershell
cd bridge
$env:PYTHONPATH="src"
python -m pytest -q
```

Expected: **854 passed, 2 skipped** on the `pydsl` branch with the local
audit corpus present (407 on `main`, which does not carry the dialect,
lints, ranking, history or envelope work). On a fresh clone the two
envelope-corpus tests skip as well (**852 passed, 4 skipped**): they
verify the cube-turn regression and replay every DSL reply in
`scratch\base\audit`, which is local and git-ignored. The two other skips
are the opt-in live model calls. When `scratch\base\Media` is absent,
`tests\conftest.py` generates a small, deterministic media tree and points
`HARNESS_MEDIA_ROOT` at it. If you have the real runtime, the tests index the
real library instead.

Static check of every Squeak source file:

```powershell
python tools\check_st.py
```

Live model smoke test (uses your key, two tiny calls):

```powershell
cd bridge
$env:PYTHONPATH="src"
python -m pytest -q -m live
```

## Deterministic image test (no model)

This needs the dev image running (`.\run_scratch.ps1`, control server on 8767):

```powershell
python tools\mock_scene_bridge.py           # terminal 1: mock bridge on 8765
python tools\ai_control.py send --async "scene test" --wait
python tools\ai_control.py status            # scripts > 0
python tools\ai_control.py undo
```

The mock scene adds a script to `Sprite1`. It goes through the real apply path
without touching the network, so it's a good first check after a UI change.

## Release-image checklist

Run this before tagging a release, and after anything that touches
`image\40_release_image.st` or the release bundle.

1. `.\tools\make_release_image.ps1 -Force` succeeds.
2. `.\run_release.ps1` opens the image. Try it once with the defaults and once
   with `-Width` and `-Height`.
3. The window is `1400×900` (or whatever size you passed). It has a normal
   title bar, and the Scratch frame and rail fill the client area with no
   turquoise World border.
4. `Get-NetTCPConnection -LocalPort 8767` returns nothing. The control server
   is off.
5. The rail shows **Chat / Bridge / Usage**, the Cat, one short welcome
   message and a **Quit** button. There's no **Reload UI** button.
6. The **File** menu has **AI Chat** and no **Reload UI**.
7. **Quit** closes the app. Alt+F4 and **File → Quit** also close it.
8. **Bridge → Start** opens a `bridge_start.cmd` console, and the page reaches
   `bridge: ok`.
9. Send `make the cat draw a spinning hexagon`. Blocks appear in Scripts.
10. The green flag runs the script, and **Undo** removes it.
11. Relaunch. The project is clean again (Cat only), the window is still
    windowed, and there's still no control server.

A reference screenshot is
[`docs/media/release-windowed.png`](docs/media/release-windowed.png).

## Test profiles

| Profile | Use |
|---|---|
| `mock` | deterministic, no network |
| `opencode-go` | default live path (`deepseek-v4.1-flash`) |
| `deepseek-direct` | your own `api.deepseek.com` key |
| `local` | Ollama or another OpenAI-compatible server on 127.0.0.1:11434 |

```powershell
python -m harness.server --profile mock
python -m harness.server --profile deepseek-direct --model deepseek-chat
```

## Debugging a bad model turn

Audit is **off** by default in `run_live.ps1`, so a normal run doesn't write
prompts to disk. When you need the details, turn it on for one run:

```powershell
.\run_live.ps1 -Audit full
python tools\audit.py list
python tools\audit.py show latest
python tools\audit.py show latest --raw
python tools\audit.py score
```

Audit bundles contain prompts and raw model output, so keep them on your own
machine. Don't attach them to an issue or a release.
