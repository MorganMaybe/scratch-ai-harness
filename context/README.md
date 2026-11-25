# Context packs

Optional, lazily loaded model context. The always-on guide is
`../SCRATCH_AI_CONTEXT.md`; specialized detail lives here so the core prompt
stays small.

The model requests a pack by returning:

```json
{ "load_context": ["clones"], "reason": "the user wants particle clones" }
```

instead of a change set. The bridge appends the pack to the system prompt and
asks for the change set again. Each pack extends the prompt budget by its own
size, so it does not displace the core guide. Requests for unknown names are
repaired; packs are never loaded twice in one turn.

Examples are written in the Scratch-Python dialect (`generator = dsl`); each
one has a generated JSON twin for `generator = json`, so the bridge shows the
model only the dialect it is expected to write.

| Pack | Use when |
|---|---|
| `clones.md` | any scene with three or more similar things (the default over copy-pasted sprites); spawners, particles, grids, collectibles; exact clone semantics |
| `games.md` | score/HUD, game over and reset, platformer and flappy physics, prop art |
| `scrolling.md` | side-scrolling levels, camera-follow, parallax, tiled maps |
| `pen-3d.md` | 3D projection and meshes in Scratch, multiple drawer sprites, depth effects, pen/frame limits |

Add a new pack by dropping `<name>.md` in this folder and adding one line to the
context-pack index near the top of `SCRATCH_AI_CONTEXT.md`. The loader discovers
the file automatically; unknown names still fail validation.
