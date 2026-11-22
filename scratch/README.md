# Scratch runtime lives here

This folder is intentionally almost empty in the source repository.

`scratch\base\` is the working directory for the Scratch 1.4 VM. It needs:

```text
Scratch.exe
ScratchPlugin.dll  UnicodePlugin.dll  Mpeg3Plugin.dll
CameraPlugin.dll   WeDoPlugin.dll
SqueakV2.sources
Scratch.ini
ScratchAIRelease.image / .changes   (end-user release image)
ScratchAiTesting.image / .changes   (optional dev image)
Media/  Help/  locale/  Projects/
```

## Easiest path

Download the release bundle from GitHub Releases and extract it over the
repository root. It already has the runtime, the release image and the stock
Scratch 1.4 media in the right places.

## From your own Scratch 1.4 install

1. Install or unpack Scratch 1.4.
2. Copy `Scratch.exe`, the plugins, `SqueakV2.sources`, `Scratch.ini`,
   `Media`, `Help`, `locale` and `Projects` into this folder.
3. Copy `ScratchAIRelease.image` and `ScratchAIRelease.changes` from the
   release download into this folder.
4. Run `..\..\run_release.ps1` from the repository root.

Never commit this folder. Everything in it except `.gitkeep` is ignored.
