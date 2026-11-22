# Testing

## Automated (fresh clone, no Scratch runtime)

```powershell
cd bridge
$env:PYTHONPATH="src"
python -m pytest -q
```

Expected: **407 passed, 2 skipped** (the skipped tests are opt-in live model
calls). When `scratch\base\Media` is absent, `tests\conftest.py` generates a
small deterministic media tree and sets `HARNESS_MEDIA_ROOT`; a developer with
the real runtime indexes the real library.

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

Requires the dev image running (`.\run_scratch.ps1`, control server on 8767):

```powershell
python tools\mock_scene_bridge.py           # terminal 1: mock bridge on 8765
python tools\ai_control.py send --async "scene test" --wait
python tools\ai_control.py status            # scripts > 0
python tools\ai_control.py undo
```

The mock scene adds a script to `Sprite1` and exercises the real apply path
without a network call.

## Release-image checklist

1. `.\tools\make_release_image.ps1 -Force` succeeds.
2. `.\run_release.ps1` opens the image.
3. The window is `1400×900` (or the `-Width`/`-Height` you passed), has a normal
   title bar, and the Scratch frame/rail fill the client area with no turquoise
   World border.
4. `Get-NetTCPConnection -LocalPort 8767` returns nothing (control server off).
5. The rail shows **Chat / Bridge / Usage**, the Cat, one short welcome message,
   a **Quit** button, and no **Reload UI** button.
6. **File** menu has **AI Chat** but no **Reload UI**.
7. **Quit** closes the app; **Alt+F4** and **File → Quit** also work.
8. **Bridge → Start** opens a `bridge_start.cmd` console and the page reaches
   `bridge: ok`.
9. Send `make the cat draw a spinning hexagon`; blocks appear in Scripts.
10. Green flag runs the script; **Undo** removes it.
11. Relaunch: the project is clean again (Cat only), still windowed, still no
    control server.

A reference screenshot is
[`docs/media/release-windowed.png`](media/release-windowed.png).

## Test profiles

| Profile | Use |
|---|---|
| `mock` | deterministic, no network |
| `opencode-go` | default live path (`deepseek-v4.1-flash`) |
| `deepseek-direct` | your own `api.deepseek.com` key |
| `local` | Ollama / OpenAI-compatible server on 127.0.0.1:11434 |

```powershell
python -m harness.server --profile mock
python -m harness.server --profile deepseek-direct --model deepseek-chat
```

## Debugging a bad model turn

Audit is **off** by default in `run_live.ps1` so a public build does not write
prompts to disk. Opt in locally:

```powershell
.\run_live.ps1 -Audit full
python tools\audit.py list
python tools\audit.py show latest
python tools\audit.py show latest --raw
python tools\audit.py score
```

Audit bundles contain prompts and raw model output. Keep them local.
