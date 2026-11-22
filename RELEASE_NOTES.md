# Release notes

## 0.1.0: first public release

This is the first build I'm willing to hand to other people. It's a personal
project, so expect rough edges, and the [README](README.md) lists the ones I
know about.

- **The release image opens in a window.** `ScratchAIRelease.image` runs in a
  normal 1400×900 window with a title bar. The Scratch frame and the chat rail
  fill the window, with no turquoise Squeak World border around them. Pass
  `-Width` and `-Height` to `run_release.ps1` to change the size.
- **A Quit button in the rail.** The Squeak Windows VM ignores the title-bar X,
  so the release image has a **Quit** button in the rail, and File → Quit and
  Alt+F4 also work. The bundled runtime sets `EnableAltF4Quit=1`.
- **End-user image, no dev tools.** The release image doesn't start the 8767
  control server or the dev watchdog, and it has no Reload UI button. It starts
  on a clean Cat project with the Chat / Bridge / Usage rail.
- **Portable loader.** `AIHarness load:` finds `image/` relative to the running
  image, so the repo works from any folder.
- **Setup asks for your key.** `setup.ps1` prompts for your API key with
  masking, and writes it only to `bridge\.deepseek_key`.
- **Launchers.** `run_release.ps1` starts the end-user image. `run_live.ps1`
  now has audit off by default, and it explains what to do if there's no key.
- **Dev image switch.** `controlServer=off` in `scratch\base\harness.ini` keeps
  the dev image's control server from starting. The 2009 Squeak socket API
  can't bind loopback, so when it's on, it listens on all interfaces. The
  release image never starts it.
- **Clean release bundle.** The bundle builder ships stock Scratch 1.4 media
  only. Scratch 2.0 presets and assets are excluded, and so are secrets and
  logs.
- **Tests.** 407 pass and 2 are skipped on a fresh clone. A generated media
  fixture means CI doesn't depend on the runtime.
- **CI.** GitHub Actions runs on Windows and Linux with Python 3.11 and 3.13,
  plus a static `.st` check.
- **Licensing.** GPLv2, with the upstream NOTICE and the trademark policy
  included. This is an unofficial mod, not affiliated with the Scratch
  Foundation.

### Download

`ScratchAIHarness-0.1.0.zip` (about 50.6 MB) contains the runtime, the release
and dev images, stock media, the bridge, the tools and the docs. The download
is on the [0.1.0 release page](https://github.com/MorganMaybe/scratch-ai-harness/releases/tag/v0.1.0).
