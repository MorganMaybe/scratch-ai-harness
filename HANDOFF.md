# Scratch AI Harness — HANDOFF

**Date:** 2026-11-22 (release prep, fork and bundle)  
**Status:** release image verified; 407 offline tests pass on a fresh clone.  
**Repo:** https://github.com/MorganMaybe/scratch-ai-harness — a fork of
[`scratchfoundation/Scratch_1.4`](https://github.com/scratchfoundation/Scratch_1.4).  
**Start here:** [`README.md`](README.md) and [`QUICKSTART.md`](QUICKSTART.md).
The previous detailed handoff (session 22) is preserved at
[`docs/HANDOFF-2026-11-15.md`](docs/HANDOFF-2026-11-15.md).

---

## 1. What is in this drop

| Piece | State |
|---|---|
| Scratch 1.4 + harness on Windows | Working |
| Docked Chat / Bridge / Usage rail | Working |
| Change sets: scripts, vars, lists, sprites, costumes, backdrops, stage | Working |
| Undo, ownership, registry reconcile | Working |
| Lazy context packs + sprite script detail | Working |
| Python bridge, validator, compiler, providers | Working |
| **Release image (windowed, no control server)** | **Verified** |
| **Release bundle (stock media, no secrets)** | **Built, ~50.6 MB** |
| Tests | **407 passed, 2 skipped** (fresh clone, media fixture) |
| Live model path | `opencode-go` → `deepseek-v4.1-flash` |

### Images

| Image | Role |
|---|---|
| `ScratchAIRelease.image` | **End-user release.** Normal window, `fillScreenOn` with `TakeOverScreen` off so the frame and rail fill the client area with no turquoise World border. No 8767 control server, no dev watchdog, no Reload UI; release-only **Quit** button. Clean Cat project, chat rail, welcome line. |
| `ScratchAiTesting.image` | **Dev image.** Control server on 8767, dev dialog policy, Reload UI. Use `ai_control.py` and `scope` probes here. |
| `ScratchDev.image` | Artifact of `tools\build_image.ps1`. |

Both images live in `scratch\base`, which is git-ignored. The release bundle
places them there.

### Release mode

`image\40_release_image.st` is loaded last. It stores
`AIHarnessReleaseMode = true` and overrides `AIHarness class>>startUp`:

- skips `startDevServer` and the watchdog;
- forces `devMode` false;
- closes Squeak `SystemWindow`s and `DialogBoxMorph`s;
- calls `ScratchFrameMorph takeOverScreen: false` then `fillScreenOn`, so the
  frame fills the VM client area but the OS title bar stays (the Squeak Windows
  VM ignores the title-bar close button, so the rail also gets a **Quit** button);
- keeps the async dispatcher (chat Send needs it);
- removes the Reload UI button;
- `saveReleaseAs:` cleans the project, writes the release pair, and defers the
  snapshot by 0.5 s so the control reply is not replayed.

Build it with:

```powershell
.\tools\make_release_image.ps1 -Force
```

The builder loads `17c → 16b → 22 → 38 → 29 → 40` into a temporary copy of
`ScratchAiTesting`, so it does not depend on the seed's older methods.

---

## 2. Quick start (dev)

```powershell
.\setup.ps1 -Dev
.\run_scratch.ps1                 # ScratchAiTesting, control server 8767
python tools\wait_control.py
python tools\ai_control.py status
.\run_live.ps1                    # live bridge, audit off by default
# or
.\run_bridge.ps1                  # deterministic mock
```

Useful:

```powershell
python tools\ai_control.py send --async "make the hexagon bigger" --wait
python tools\ai_control.py undo
python tools\ai_control.py load 09_undo.st
python tools\ai_control.py doctor | errors | config | context | log
python tools\audit.py list
```

### Ports and network

- **8765** — Python chat bridge. Binds `127.0.0.1` only.
- **8767** — Squeak dev control server. The 2009 Squeak `Socket>>listenOn:`
  API cannot bind loopback, so it listens on `0.0.0.0:8767`. Windows Firewall
  prompts. Do not run the dev image on an untrusted network. Set
  `controlServer=off` in `scratch\base\harness.ini` to skip it. The release
  image never starts it.
- Model calls are **outbound** from Python to the configured profile endpoint
  (`opencode.ai` or `api.deepseek.com`). Scratch itself does not call the model.

---

## 3. Model connection

Profiles are in `bridge\harness.ini` (copy from `harness.ini.example`):

| Profile | Model / endpoint |
|---|---|
| `opencode-go` (default) | `deepseek-v4.1-flash` at `https://opencode.ai/inference/go/openai/v1` |
| `deepseek-direct` | `deepseek-chat` at `https://api.deepseek.com` |
| `local` | Ollama/OpenAI-compatible at `127.0.0.1:11434` |
| `mock` | offline canned scenes |

The key is read from `DEEPSEEK_API_KEY` / `OPENCODE_GO_API_KEY` or
`bridge\.deepseek_key`. It is never written to the image, a project, a log or
a prompt.

Budgets: 120 s per attempt, 240 s per turn, 16 384 output tokens, 2 transport
retries, 2 repairs, 80 000-character prompt budget. Hidden reasoning is
explicitly disabled on `opencode-go`; prefer `deepseek-v4.1-flash`, which honors
it.

Audit is **off** in `run_live.ps1` for a public build. Opt in with
`-Audit full`; bundles contain prompts and raw replies, so keep them local.

---

## 4. Tests

```powershell
cd bridge
$env:PYTHONPATH="src"
python -m pytest -q          # 407 passed, 2 skipped
cd ..
python tools\check_st.py     # every image/*.st
```

`bridge\tests\conftest.py` generates a small media fixture when
`scratch\base\Media` is missing, so CI and a fresh clone do not need the
runtime. `HARNESS_MEDIA_ROOT` overrides the media root.

The deterministic image path is:

```powershell
python tools\mock_scene_bridge.py
python tools\ai_control.py send --async "scene test" --wait
python tools\ai_control.py undo
```

The manual release checklist is in [`TESTING.md`](TESTING.md).

---

## 5. Media and licensing

The public release bundle contains **stock Scratch 1.4 media only**. The
locally imported Scratch 2.0 libraries are not redistributed. The bundle
builder:

- excludes `Media/Scratch2`, `Media/Sounds/Scratch2` and `Costumes/Bundles`;
- drops files whose stems are in `tools\scratch2_only_stems.txt`;
- removes Scratch 2.0 preset groups from the bundled `media_groups.json`;
- drops curated paths that are not in the staged media.

The repo is GPLv2 (see `LICENSE`, `NOTICE`, `gpl-2.0.txt`). Scratch, the
Scratch logo, Scratch Cat and Gobo are trademarks; this is an unofficial mod.
A substantially modified public build should replace the name/logo/character
art. See `TRADEMARK_POLICY`.

---

## 6. Working rules

1. Drive the dev image through `tools\ai_control.py`; do not click/focus it.
2. One bridge owns 8765. Use `run_live.ps1 -Reuse` or `tools\stop_bridge.ps1`.
3. Never Ctrl+V in the image; use Alt+V only for manual paste.
4. A modal wedges the dispatcher. Screenshot first, dismiss, retry.
5. Use `17c_loader_fix.st`'s loader, not the old `16a`/`17_safe_dialogs` one.
6. Run `python tools\check_st.py` before loading a changed `.st`.
7. Never touch `Scratch.pristine.*`.
8. Keep keys out of everything: image, projects, logs, screenshots, commits.
9. Rebuild the clean dev image with `.\tools\make_clean_image.ps1`.
10. Rebuild the release image with `.\tools\make_release_image.ps1 -Force`.
11. Rebuild the public bundle with
    `.\tools\make_release_bundle.ps1 -Version <x.y.z> -Force`.
12. `scratch\base\audit\`, `sessions\`, `tools\media_groups_work\` and runtime
    media are local/git-ignored.

---

## 7. Next steps

1. **User-script editing with confirmation.** User scripts are still read-only.
2. **Cross-sprite variables.** Validation rejects writing another sprite's
   local variable; add an appendix rule and/or UI affordance.
3. **Control-server loopback.** Squeak 2.8 cannot bind a single interface.
   A small local proxy or reverse-connect transport would remove the
   `0.0.0.0:8767` exposure and the firewall prompt.
4. **Import gaps:** sound import, `.sprite` bundle import, sound editor.
5. **Model quality loop:** use `-Audit full`, `audit.py score`, and measure
   plan → per-script chunks.
6. **Trademark-safe branding** before a wide public distribution.

---

## 8. Where the detail lives

| File | What |
|---|---|
| `README.md` | public overview, install, release bundle |
| `QUICKSTART.md` | tester path |
| `TESTING.md` | automated + manual checklist |
| `CONTRIBUTING.md` | dev workflow and media rules |
| `SECURITY.md` | key handling, ports, audit privacy |
| `ARCHITECTURE.md` | design rationale, protocol |
| `SCRATCH_AI_CONTEXT.md` | model appendix sent every prompt |
| `context/` | lazy packs: clones, games, scrolling, pen-3d |
| `SPRITE_STAGE_SCOPE.md` | sprite/stage as-built |
| `DEEPSEEK_CONNECTION_SCOPE.md` | connection package |
| `CHAT_UI_SCOPE.md` | docked rail |
| `SCRATCH_2_FEATURE_AUDIT.md` | clones/BYOB audit |
| `docs/SQUEAK_NOTES.md` | 60 Squeak/Scratch traps |
| `docs/HANDOFF-2026-11-15.md` | session-22 detailed handoff |
| `docs/UI_TOUR.md` | rail ↔ native pane map |
| `image/README.md` | Squeak-side step-by-step |
