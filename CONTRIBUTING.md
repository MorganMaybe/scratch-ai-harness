# Contributing

Thanks for looking at this. It's a small project with a lot of Squeak in it, so
most of this file is about not breaking the image. The Python side is ordinary.
The image side has traps, and they're written down here so you don't have to
find them the hard way.

## Setup

```powershell
.\setup.ps1 -Dev
```

This installs the bridge in editable mode with pytest, sets up
`bridge\harness.ini`, and asks for your own API key. Never commit
`bridge\.deepseek_key`, `bridge\harness.ini`, `scratch\base\`, logs, audits or
release images. They're all git-ignored for a reason.

## Workflow

1. Keep the change focused, and match the style of the code around it.
2. Run the Python suite:

   ```powershell
   cd bridge
   $env:PYTHONPATH="src"
   python -m pytest -q
   ```

3. If you changed `image\*.st`, run `python tools\check_st.py`, then load the
   file into the dev image with `python tools\ai_control.py load <file>.st`.
4. If you changed the UI, reload it with the **Reload UI** button in the rail,
   or File → Reload UI, on the dev image. `39_ui_reload.st` installs that
   reload logic; load it once after the UI files, not as a reload trigger.
5. If you changed release behaviour, rebuild with
   `.\tools\make_release_image.ps1 -Force` and go through the release checklist
   in [`TESTING.md`](TESTING.md).

## Image sources

`image\*.st` is the source of truth. Don't hand-patch an image to fix something
that belongs in a `.st` file, because the next rebuild will throw the patch
away. The maintained dev image is `ScratchAiTesting.image`. Rebuild it with
`.\tools\make_clean_image.ps1` while it's running.

`image\40_release_image.st` is loaded last. It has to stay last in
`00_bootstrap.st`. Don't edit `Scratch.pristine.*`.

## Squeak notes

- The loader is `17c_loader_fix.st`. `17_safe_dialogs.st` still supplies the
  dialog patches, but its older `load:` method must not be the one in use;
  `17c` is loaded after it. Don't use the `16a_notifier.st` loader: it reports
  success without executing.
- A modal dialog wedges the control server. Take a screenshot, dismiss the
  dialog, then retry. Retrying before that just queues up more problems.
- Never press Ctrl+V in the image. It opens the "type your initials" modal,
  which blocks the UI thread. Use Alt+V if you have to paste by hand.
- [`docs/SQUEAK_NOTES.md`](docs/SQUEAK_NOTES.md) has the longer list of traps.
  It's long, and it's worth skimming before you touch the rail.

## Model-facing changes

`SCRATCH_AI_CONTEXT.md` goes out with every system prompt. The files in
`context/` are lazy packs that the model asks for with `load_context`. Keep
both short and actionable. Before you commit a JSON example, run it through
`validate_changeset` and `compile_changeset`, so the examples the model sees
are ones the bridge actually accepts.

## Media

The release bundle includes stock Scratch 1.4 media only. The Scratch 2.0
libraries I imported locally can't be redistributed, so
`tools\make_release_bundle.ps1` excludes them, using
`tools\scratch2_only_stems.txt`. Don't add Scratch 2.0 assets to the repository
or to a release.

## Pull requests

- Include tests for behaviour changes.
- Say which image(s) you rebuilt and which checklist items you ran. "Looked
  fine" isn't a checklist.
- Don't include API keys, prompts, audit bundles, screenshots of private
  projects, or anything in `scratch\base`.
