# Release notes

## 0.1.0 — first public release

- Full-screen **release image** with no 8767 control server, no dev watchdog
  and no Reload UI. Clean Cat project, Chat / Bridge / Usage rail.
- Portable image loader: `AIHarness load:` resolves `image/` relative to the
  running image, so the repo works from any folder.
- `setup.ps1` asks for your own API key (masked) and writes only
  `bridge\.deepseek_key`.
- `run_release.ps1` launches the end-user image; `run_live.ps1` now defaults
  audit off and gives a clear key-setup message.
- `controlServer=off` switch for the dev image. The 2009 Squeak socket API
  cannot bind loopback; the release image never starts the server.
- Release bundle builder: stock Scratch 1.4 media only, Scratch 2.0 presets
  and assets excluded, no secrets/logs.
- Tests: 407 passed, 2 skipped on a fresh clone; a media fixture keeps CI
  independent of the runtime.
- CI on Windows and Linux, Python 3.11 and 3.13; static `.st` check.
- GPLv2 license, upstream NOTICE and trademark policy included.

### Download

`ScratchAIHarness-0.1.0.zip` — runtime, release/dev images, stock media,
bridge, tools and docs.
