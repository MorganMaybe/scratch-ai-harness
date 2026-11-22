# Contributing

## Setup

```powershell
.\setup.ps1 -Dev
```

This installs the bridge editable with pytest, creates `bridge\harness.ini`,
and asks for your own API key. Never commit `bridge\.deepseek_key`,
`bridge\harness.ini`, `scratch\base\`, logs, audits or release images.

## Workflow

1. Keep the change focused and match the surrounding style.
2. Run the Python suite:

   ```powershell
   cd bridge
   $env:PYTHONPATH="src"
   python -m pytest -q
   ```

3. If you changed `image\*.st`, run `python tools\check_st.py` and load the file
   into the dev image with `python tools\ai_control.py load <file>.st`.
4. If you changed the UI, reload it with the rail's **Reload UI** button (dev
   image only) or `python tools\ai_control.py load 39_ui_reload.st`.
5. If you changed release behaviour, rebuild
   `.\tools\make_release_image.ps1 -Force` and walk the release checklist in
   [`TESTING.md`](TESTING.md).

## Image sources

`image\*.st` is the source of truth. The maintained dev image is
`ScratchAiTesting.image`; rebuild it with `.\tools\make_clean_image.ps1` while it
is running. `image\40_release_image.st` is loaded last and must stay last in
`00_bootstrap.st`.

Do not hand-patch an image for anything that belongs in a `.st` file. Do not
edit `Scratch.pristine.*`.

## Squeak notes

- The loader is `17c_loader_fix.st`, not the older `16a`/`17_safe_dialogs`
  versions.
- A modal dialog wedges the control server. Screenshot first, dismiss, retry.
- Never Ctrl+V in the image (it opens the initials modal); use Alt+V only if
  you must paste manually.
- `docs/SQUEAK_NOTES.md` has the 60-trap list.

## Model-facing changes

`SCRATCH_AI_CONTEXT.md` is sent with every system prompt. `context/*.md` are
lazy packs the model requests with `load_context`. Keep both short and
actionable; validate any JSON examples through `validate_changeset` and
`compile_changeset` before committing.

## Media

The release bundle includes stock Scratch 1.4 media only. The locally imported
Scratch 2.0 libraries are non-redistributable and are excluded by
`tools\make_release_bundle.ps1` using `tools\scratch2_only_stems.txt`. Do not
add Scratch 2.0 assets to the repository or a release.

## Pull requests

- Include tests for behaviour changes.
- Say which image(s) you rebuilt and which checklist items you ran.
- Do not include API keys, prompts, audit bundles, screenshots of private
  projects, or `scratch\base`.
