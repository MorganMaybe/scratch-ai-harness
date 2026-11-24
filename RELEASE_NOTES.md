# Release notes

## 0.2.0: scratch-python, chat memory and fewer repair rounds

This one is mostly bridge work. The model can now answer in a small checked subset of Python, the bridge remembers what was said earlier in the chat, and sloppy replies get fixed up without burning a repair round. It's still a personal project, so the rough edges are still there, and I've listed the ones I know about below.

- **Scratch-Python front end.** Set `generator = dsl` in `bridge\harness.ini`, or pass `run_live.ps1 -Generator dsl`. The model writes one fenced Python module instead of a JSON change set, and the bridge turns it into the same block IR. I ran it live end to end. In the runs I looked at it used fewer tokens and needed fewer retries than JSON.
- **JSON is still the default.** I haven't run a proper live A/B yet, so I'm not going to flip the default on vibes. The DSL is opt-in until the numbers say otherwise.
- **Conversation memory.** The bridge keeps the last 24 acknowledged turns and puts a trimmed history section into each prompt. Recent turns go in close to verbatim, older ones get squashed to one line. So "make it smaller" finally means the thing we were just talking about.
- **Turn it off with `run_live.ps1 -History off`** if the history starts confusing the model. I'd like to hear about it if you need to.
- **Sloppy replies get recovered.** Prose around the code fence, a missing closing fence, notes after the fence, CRLF line endings and a BOM are all handled mechanically. If the reply really is unrecoverable, you get a clear diagnostic instead of a silent retry.
- **Repair prompts quote the exact bad line.** The model gets the offending source line back, not a vague "something was wrong".
- **Parse-time gates.** Duplicate variable and sprite names, and unknown targets or media, are caught before they cost a model round trip.
- **One extra repair for change-set validation.** There's a single reserved repair round for JSON change-set validation failures. It's one, not a loop.
- **Tests: 852 pass on a fresh clone** (up from 407), and 854 with the local audit corpus. The live tests are still opt-in.
- **HANDOFF is rewritten** as a short current-state doc. The long session history moved to `docs/HISTORY.md`.
- **Known rough edges:** the DSL still needs a live A/B before I trust it as the default, and the model still gets Scratch semantics wrong sometimes. The release image and the Squeak side didn't change.

### Upgrade

There's no new zip for 0.2.0. The 0.1.0 bundle runs the same image, and this release is bridge side plus docs. If you already have 0.1.0, `git pull` in the repo folder and keep using the existing runtime. Check the 0.1.0 zip is still in `scratch\base` and nothing else is needed.

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
