# 3D in Scratch with the pen

> Use when: 3D in Scratch: projected meshes of any shape, rotating wireframes, depth scenes, multiple drawer sprites, pen/frame limits.

Scratch has no 3D engine, no camera object, and no polygon renderer. "3D" here
means: keep points in variables and lists, transform and project them to Stage
coordinates each frame, then draw the result with pen segments, stamps, or
sprites. This pack is about the Scratch-specific machinery and limits, not
general rendering theory. 

if using only pen, hide all drawing sprites from the start. if stamps are used as well, only show the sprite to place the stamp.

## What the runtime gives you

- The Stage is 480×360: `x` is roughly `-240..240`, `y` roughly `-180..180`,
  and **y points up**. Projected points may leave the Stage; pen lines are
  clipped, but keep coordinates in a sane range.
- Scratch runs at about 30 frames per second. A `forever` loop is one pass per
  frame. A long `repeat` or a heavy frame delays the whole project.
- Animation is per frame, not per second: `change angle by 2` means two degrees
  per frame. Adding `wait` to the loop slows the rotation.
- One interpreter and one UI thread. Sprites are cooperative, not parallel
  threads. Drawing from several sprites shares the same frame budget.
- There is no GPU 3D path: projection blocks and pen segments are interpreted and
  composited by the VM, not by a 3D renderer. Large costumes and high sprite
  counts add their own cost on top of the geometry.
- Pen:
  - Each sprite has its own pen down/up, size, hue/shade and RGB state.
  - The trail layer is **global**, sits behind sprites, and is runtime-only (not
    saved with the project).
  - `pen_clear` clears every sprite's trails. There is no per-sprite clear and
    no clipping region, so you cannot erase just one drawer's old lines.
  - `pen_down` draws a segment from the sprite's previous position to the new
    one; `stamp` paints the current costume onto the same layer. A stamp is
    permanent until `pen_clear`; it is not a movable sprite.
  - One drawer's pen state does not change another's. Hiding a drawer does not
    stop its pen.
  - `pen_clear` is the only pen block the Stage can run; the Stage cannot draw.
- There is no z-buffer, no polygon fill, no sort block, and no custom blocks.
  Use parallel lists plus index arithmetic; avoid per-frame sorting of hundreds
  of items.
- Clones are runtime copies and deep-copy media in Scratch 1.4. Use a few
  drawer sprites, not one clone per vertex or segment.

## The Scratch 3D pipeline

Build the model once at setup. For an animated scene, every frame then follows
the same five steps:

1. **Clear** — one owner calls `pen_clear`.
2. **Transform** — rotate/translate/scale the model's vertices in world space.
3. **Project** — convert world points to Stage `x`/`y`.
4. **Draw** — pen segments, polylines, stamps, or billboard sprites.
5. **Order** — sequence drawers when painter order matters.

### Projection in Scratch form

```text
rotate Y:  x1 = x*cos(a) - z*sin(a)
           z1 = x*sin(a) + z*cos(a)

project:   scale = focus / (z1 + offset + focus)
           screen_x = x1 * scale
           screen_y = y  * scale
```

- `sin`/`cos` are **degrees** in Scratch's `math_function`.
- `focus` (focal length) around 200–400 suits a 480-wide Stage. Add a positive
  `offset` so the denominator cannot approach zero; skip anything with
  `z1 + offset + focus <= 20`.
- Project **once per vertex per frame**, store the result in `sx`/`sy`, then let
  every segment or polyline read those lists. Never project inside the draw
  loop.
- Apply extra axes in a fixed order (for example Y then X) and keep that order
  every frame. Store the angles in variables; compute each `sin`/`cos` once per
  frame, not once per vertex.
- Use the same scale for `x` and `y`; otherwise the scene stretches. If your
  math uses a screen-style y-down system, flip `y` once at the end.
- Clamp output to a modest margin (for example `±600`) as a safety net only.

### World space vs Stage space

Stage coordinates are **output**, not the model. Choose a world space (any
units, y-up), store object positions and a camera there, and project at the end.
A camera move subtracts `cam_x`/`cam_y`/`cam_z` from world points before
rotation; a camera turn is the inverse rotation.

Do not hard-code the Stage edges (`±240`, `±180`) as world bounds, and do not use
`bounce` or "if on edge" to keep a drawer inside the world. Clamp in world space
or skip the primitive. The Stage edge is only where the picture is cut off.

## Geometry is data, not a shape

Store local model vertices as parallel lists (`vx`, `vy`, `vz`) and keep
topology separate. Pick one representation and make the draw code generic:

- **segments** — pairs of vertex indices (`seg_a`, `seg_b`);
- **polylines** — runs of consecutive indices (`run_start`, `run_count`);
- **faces** — closed runs or index loops, used as outlines;
- **points** — a vertex list with no topology;
- **indexed faces** — triples/quads drawn as outlines; cull or order at object
  level because Scratch cannot rasterize them.

When you build paired topology lists (`ea`/`eb`, `seg_a`/`seg_b`), append both
endpoints in the same iteration and keep the lists the same length. A mismatch
silently reads past the end of one list and draws garbage; a cube needs 12
pairs.

A cube is one mesh, not the required layout: 8 corners from half-width/height/
depth; 12 unique segments for a wireframe, or 6 face loops when you draw only
visible faces. Other shapes use the same pattern:

- **pyramid** — a base loop plus an apex and connector runs;
- **cylinder / ring / torus** — rings of vertices joined by side runs;
- **sphere** — latitude rings plus longitude runs; low resolution is enough;
- **terrain / plane** — a lattice; draw rows and columns as long polylines;
- **extruded 2D shape** — the same outline at two depths plus connectors;
- **star / logo / arbitrary outline** — a point or polyline list in local space;
- **particles / dust** — a point cloud with no topology at all.

Generate vertices from dimensions or loop counters when the shape is parametric.
Do not hard-code one shape's coordinates and then reuse them for a different
request. Build only the geometry the request needs; a general-purpose engine with
clipping, sorting and face shading is overkill in Scratch and will exceed the
turn and frame budgets.

Keep a **local** mesh and place it with an object position/rotation/scale. That
lets several objects and several shapes share one set of scripts and lists. Use
global lists (Stage lists) for geometry and projected screen coordinates that
drawers share; a sprite cannot read another sprite's local lists. Use
sprite-local lists for a drawer's private object so names cannot collide.

## Drawing primitives

- **Segment:** `pen_up` → `goto` A → `pen_down` → `goto` B → `pen_up`.
- **Polyline:** `pen_up` → `goto` first point → `pen_down` → `goto` each point
  in the run → `pen_up`. Fewer pen up/down and `goto` blocks than separate
  segments.
- **Point cloud:** `pen_up` → `goto` point → `pen_down` → `pen_up` (a short
  dot), or `stamp` a small costume.
- **Billboard:** move a *visible* sprite to the projected point and `set_size`
  by `scale * 100` (size is a percent). Cheaper than many pen segments for
  stars, particles and distant props, and sprite layers give it occlusion. Use
  an existing small costume from the context or media library; if none fits, use
  pen dots.
- **Filled face:** Scratch cannot fill a polygon. Use an outline, a stamped
  costume, dense hatching, or a sprite; say it is an approximation. Do not write
  a triangle rasterizer with hundreds of pen lines per face.

## Multiple sprites drawing one scene

Multiple sprites may draw into the same scene. Each keeps its own pen state
(size/color/down), but all trails go to one shared pen layer. The Stage is
redrawn once per frame after the scripts run, so lines drawn by different
sprites in the same frame composite together. This is supported and useful; it
is not a second CPU.

Choose one architecture:

- **One drawer per object/part/shape.** Each drawer owns its local mesh and
  transform. Easiest to reason about and to give separate colors.
- **Controller + renderers.** One sprite owns the geometry and projects all
  vertices into global `sx`/`sy`; several drawers each draw a contiguous range of
  segment or polyline indices. A controller cannot read or set another sprite's
  local variables or lists, so each drawer must set its own `start`/`end` in its
  own setup, or the ranges must live in global lists indexed by drawer.
- **One drawer per depth/material band.** Far objects in one drawer, near objects
  in another; useful for both color and painter order.
- **Billboard sprites** for point-like objects, with pen reserved for lines.

Rules for multiple drawers:

- Exactly **one** owner calls `pen_clear` at the start of a frame. Drawers never
  clear; two clears erase each other's work.
- After the clear, the controller `broadcast`s `draw`. Use `broadcast_and_wait`
  only when the receivers are finite scripts; a receiver that runs `forever`
  never lets the broadcast finish.
- `broadcast` restarts a receiver that is already running. Do not use a
  per-frame `broadcast draw` as a frame clock for a receiver that takes more
  than one frame; it will be restarted mid-loop and leave `i` and the projected
  lists half-updated. Put clear → project → draw in one `forever` loop, or use a
  `drawing` flag / `broadcast_and_wait` so the next frame waits for the previous
  draw to finish.
- The scheduler does not guarantee that independent `forever` loops run in a
  chosen order. If painter order matters, sequence finite draw scripts with
  `broadcast_and_wait` calls (one layer at a time), or use a single ordered draw
  script.
- Splitting work across sprites does **not** reduce total pen work. Total
  segments per frame is still the budget. Split for modularity, per-object
  state, and scheduler interleaving, not for free speed.
- Hide drawer sprites. Hiding does not stop the pen, but a visible drawer jumps
  between projected points.
- The pen layer is behind all sprites, and stamps land on that same layer.
  `go_to_front` does not bring pen lines in front of a sprite. Among pen lines,
  draw order is command order; sprite layers do not reorder trails. If geometry
  must cover a sprite, use visible sprites and sprite layer order.

## Frame protocol

Declare lists with `create_list` and variables with `create_variable` in the
change set; there is no runtime create-variable/list block. The setup script
clears and fills the existing lists and sets the variables.

`replace_in_list` only changes an existing line; it does not append. Before the
first draw, fill every projected list with one item per vertex:

```text
delete all of sx and sy
repeat (vertex count) [
  add_to_list 0 to sx
  add_to_list 0 to sy
]
```

A missing line is silently ignored, so an empty `sx`/`sy` makes every
`replace_in_list` a no-op and nothing is drawn.

A reliable loop:

```text
once at green flag:
  clear the existing lists (delete all)
  fill the mesh and cached segment/polyline index lists
  set pen color/size; hide the drawers

every frame:
  one owner: pen_clear
  controller: update angles/camera; project each vertex into sx/sy
  controller: broadcast draw
  each drawer: read sx/sy and draw its range
```

With one drawer per object, each drawer projects its own local vertices instead
of reading global `sx`/`sy`; the controller still owns the clear and the draw
broadcast. For a single object, keep setup and the whole clear → project → draw
loop in one script; a separate `when_receive draw` script is only for
coordinating several drawers.

- `pen_clear` before drawing; otherwise old frames accumulate.
- The project context lists names, not contents; never assume an existing list
  is initialized. Clear and refill what the frame needs.
- Do not clear and refill lists each frame. Fill them once at setup and
  `replace_in_list` the projected values. Use `delete all` only when rebuilding
  the mesh.
- If the scene is static, draw it once and leave it; clear only when it changes.
- Use `wait` (even a tiny one) in long `repeat` loops if the Stage must refresh
  between chunks of work.
- Initialize at green flag: clear and fill the existing lists, set pen state,
  clear the pen, then start the draw loop.
- Multiple green-flag setup scripts have no guaranteed order. If the controller
  clears and draws immediately, wait for a `ready` counter (or a short `wait`)
  so every drawer has its range and pen state before the first frame.

## Performance and hard limits

| Limit | What it means |
|---|---|
| 480×360 pen layer | 3D is drawn at Stage resolution; there is no high-resolution canvas. |
| ~30 fps, one thread | Every drawer, script and the redraw share one frame. A heavy frame stutters the whole project. |
| Shared pen layer | `pen_clear` is global; no per-sprite buffer or erase. |
| No z-buffer / fill | Ordering is painter order; intersecting geometry cannot resolve per pixel; faces are outlines or stamps. |
| No sort block | A full per-frame depth sort is expensive and manual; prefer fixed object/face order. |
| List access | Fine for hundreds of items; repeated insert/delete in the middle shifts entries. |
| Sprite/costume cost | Every visible sprite is composited each frame; large costumes cost more. 1.4 clones deep-copy media, so keep clones in the tens and drawers in the handful. |

Practical budget:

- Project each vertex once per frame and reuse it. This is the biggest win.
- Compute `sin`/`cos` once per angle per frame, not per vertex.
- Prefer long polylines over many separate two-point segments.
- Keep total segments in the low hundreds per frame. A 12-edge cube is trivial;
  a dense sphere is not. If it stutters, reduce vertices, cull, or use billboards.
- Cull back faces when you draw face outlines; also skip off-screen primitives
  and anything behind the camera. A transparent wireframe usually draws all
  edges.
- Avoid deep reporter nesting: copy `list_item` results into variables before
  using them in several expressions.
- Change pen color/size at the start of a drawer or a run, not per segment.
- Never use a clone per vertex or segment.
- Keep the change set near the turn budget (~80 blocks): setup once, one
  projection loop, one draw loop per drawer. Do not emit a script per vertex,
  segment or shape.

## Depth, order and shortcuts

- There is no per-pixel depth. Draw far objects first, near objects last; that is
  the only reliable ordering.
- Sorting every segment per frame is usually not worth it. Prefer fixed object
  order, face order, or separate depth-band drawers. For a wireframe, overlap
  reads acceptably; do not build a z-buffer.
- Fake depth with pen size and shade: far lines thinner/darker, near lines
  thicker/brighter. Use `set_pen_color` for exact RGB; `set_pen_hue` and
  `set_pen_shade` for hue/shade ramps. A dark backdrop and a bright wireframe
  read well.
- Pen lines are rasterized at Stage resolution; size 1 shimmers on motion. Use
  size 2–3 for a stable wireframe.
- Use billboard sprites for points and particles; `set_size` from `scale * 100`
  gives cheap depth and sprite layers give occlusion between billboards.
- Sprites always sit in front of the pen layer. A far billboard still covers a
  near pen line, so mixing billboards and pen geometry breaks depth. Use one
  technique per overlapping region, or accept the layering.
- A camera move is a subtraction before projection, or a rotation of the world;
  the Stage itself never moves. Do not scroll the backdrop for 3D.
- Pen trails are pixels: there is no depth, intersection, or collision query for
  them. Use math for 3D collisions; `touching_color` can test pen colors, and
  `touching`/`distance_to` test sprite costumes, not wireframes.

## Common mistakes

- Hard-coding a cube (or its edge pairs) when the request is another shape.
  Treat shape as data and keep the draw routine generic.
- One sprite per vertex or per edge; use one or a few drawers.
- Projecting inside the draw loop, or recomputing `sin`/`cos` for every vertex.
- Forgetting `pen_up` between shapes; stray lines join them.
- Leaving `sx`/`sy` empty and expecting `replace_in_list` to create items;
  `replace_in_list` only changes existing lines.
- Building `ea`/`eb` separately and giving them different lengths; append both
  endpoints together.
- Broadcasting `draw` every frame to a receiver that is still drawing; the
  broadcast restarts it and the lists end up half-updated.
- Two drawers both calling `pen_clear`; the scene flickers or disappears.
- Assuming independent scripts start in order or run in parallel. They do not.
- Using `go to [sprite]` for a vertex; use projected coordinates.
- Using Stage edges, `bounce`, or `if on edge` as world bounds. Keep a world
  space and clamp there.
- Using radians; Scratch's trig is in degrees.
- Trying to fill polygons or draw every face of a solid.
- Letting `z1 + offset + focus` approach zero; points explode.
- Clearing and refilling every list each frame, or deleting items one by one.
- Drawing before setup finishes; sequence with a broadcast or a short wait.
- Expecting pen trails to be saved, or that `pen_clear` affects only one sprite.

## Checklist

- [ ] Shape is a mesh (vertices + topology), not a hard-coded model.
- [ ] One projection pass per frame; screen coordinates cached in lists.
- [ ] `sx`/`sy` have one item per vertex before the first `replace_in_list`.
- [ ] Paired topology lists have equal length and valid 1-based indices.
- [ ] World/camera space is separate from Stage coordinates; no Stage-edge
      bounds.
- [ ] One `pen_clear` owner; drawers only draw.
- [ ] No per-frame broadcast restarts a draw receiver that is still running.
- [ ] Drawer sprites are hidden; pen state is set once per drawer/run.
- [ ] Draw order is explicit when it matters (broadcast or `broadcast_and_wait`
      with finite receivers).
- [ ] Segment and vertex counts are within the frame budget.
- [ ] No per-vertex clones, no per-segment pen-state changes, no per-frame list
      rebuilds.
- [ ] Depth is faked with order/size/shade; no z-buffer or polygon fill.
