# Scratch runtime lives here

This folder is almost empty in the source repository on purpose. It's where the
Scratch 1.4 VM and its images go, and none of that gets committed.

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
4. From the repository root, run `.\run_release.ps1`.

## Keep it out of git

Never commit this folder. Everything in it except `.gitkeep` is git-ignored, and
it should stay that way. Images and media are big, and the Scratch 2.0 material
in particular can't be redistributed.
