# Scrolling worlds

> Use when: side-scrolling platformers, long levels, camera-follow scenes,
> parallax backgrounds, or tiled maps larger than the 480×360 stage.

Scratch's Stage is fixed. A scrolling world is an illusion: keep a **camera**
position and draw every world object at `world_position - camera_position`.
Never try to move the Stage or the backdrop.

## Coordinate model

- World coordinates are unbounded logical positions (`world_x`, `world_y`).
- Screen coordinates are what the sprite block uses (`-240..240`, `-180..180`).
- `screen_x = world_x - cam_x`
- `screen_y = world_y - cam_y`

Use global `cam_x` (and `cam_y` for vertical scrolling). Use a local variable
for each object's fixed world position; do not overwrite it every frame.

## Minimal left-right camera

Global variables: `cam_x`, `player_x`.

Player sprite:

```json
{
  "action": "add_script",
  "target": "Player",
  "label": "move_and_camera",
  "hat": { "op": "when_flag_clicked" },
  "body": [
    { "op": "set_var", "args": { "name": "player_x", "value": 0 } },
    { "op": "set_var", "args": { "name": "cam_x", "value": 0 } },
    { "op": "forever", "body": [
      { "op": "if", "args": { "condition": {
        "op": "key_pressed", "args": { "key": "right arrow" } } }, "body": [
        { "op": "change_var", "args": { "name": "player_x", "delta": 5 } }
      ] },
      { "op": "if", "args": { "condition": {
        "op": "key_pressed", "args": { "key": "left arrow" } } }, "body": [
        { "op": "change_var", "args": { "name": "player_x", "delta": -5 } }
      ] },
      { "op": "set_var", "args": { "name": "cam_x", "value": {
        "op": "get_var", "args": { "name": "player_x" } } } },
      { "op": "set_x", "args": { "x": 0 } },
      { "op": "set_y", "args": { "y": -40 } }
    ] }
  ]
}
```

The player stays at screen x = 0 because the camera follows it exactly. The
world moves under the player.

## Scrolling tiles with clones

Tile sprite local variable: `tile_x` (create it first with
`create_variable`, `scope: "sprite"`). Global: `cam_x`, `spawn_index`.

```json
[
  {
    "action": "add_script",
    "target": "Tile",
    "label": "build_tiles",
    "hat": { "op": "when_flag_clicked" },
    "body": [
      { "op": "set_var", "args": { "name": "spawn_index", "value": 0 } },
      { "op": "repeat", "args": { "count": 24 }, "body": [
        { "op": "create_clone", "args": { "target": "myself" } },
        { "op": "change_var", "args": { "name": "spawn_index", "delta": 1 } }
      ] }
    ]
  },
  {
    "action": "add_script",
    "target": "Tile",
    "label": "tile_follow",
    "hat": { "op": "when_clone_start" },
    "body": [
      { "op": "set_var", "args": { "name": "tile_x", "value": {
        "op": "*", "args": { "a": {
          "op": "get_var", "args": { "name": "spawn_index" } },
          "b": 40 } } } },
      { "op": "set_y", "args": { "y": -150 } },
      { "op": "forever", "body": [
        { "op": "set_x", "args": { "x": {
          "op": "-", "args": { "a": {
            "op": "get_var", "args": { "name": "tile_x" } },
            "b": { "op": "get_var", "args": { "name": "cam_x" } } } } } }
      ] }
    ]
  }
]
```

`spawn_index` is the hand-off channel. Each clone copies it into its own
`tile_x` on its first frame, so later changes to `spawn_index` do not move
existing tiles.

There is no stock grass/ground **costume** in the Scratch 1.4 library (searching
for `grass` finds only grasshoppers). Do not invent `Nature/grass1.png` or any
other path. Use a costume that actually appears in the media index — a wide
shape or line is fine — or make the ground part of a backdrop. If no suitable
tile exists, use a simple broad costume and note the approximation.

## Tile maps from a list

Instead of one clone per column, use a global list `map` containing `0`/`1` per
tile. In the parent loop, test `list_item` and only clone where the value is 1:

```json
{ "op": "if", "args": { "condition": {
  "op": "=", "args": { "a": {
    "op": "list_item", "args": { "index": {
      "op": "get_var", "args": { "name": "spawn_index" } },
      "list": "map" } }, "b": 1 } } }, "body": [
  { "op": "create_clone", "args": { "target": "myself" } }
] }
```

Use `list_length` for the loop count. Keep lists to a few hundred entries.

## Parallax backgrounds

The Stage backdrop cannot scroll. Emulate layers with wide sprites:

- far layer: `set x to -(cam_x * 0.2)`
- mid layer: `set x to -(cam_x * 0.5)`
- near layer: `set x to -cam_x`

Use one costume per layer, duplicate the art horizontally if it would show an
edge, and keep the layer sprites behind the level. Do not put a layer on the
Stage.

## Vertical scrolling

Same pattern with `cam_y`:

- player script updates `cam_y`.
- every object sets `y` to `object_world_y - cam_y`.
- clamp `cam_y` at the level's top and bottom if the level is bounded.

## Common mistakes

- Moving the Stage, or expecting `switch_backdrop` to scroll. It just swaps
  images.
- Moving originals instead of clones: the original is the spawn template.
  Hide/park it and let clones be the visible objects.
- Two scripts setting the same sprite's `x` each frame — one for movement, one
  for camera — causes jitter. Prefer one script that owns `x`.
- Using `if on edge, bounce` in a scrolling world: the edge is the screen, not
  the level. Clamp world positions instead.
- Creating a clone per pixel or per list item when a handful of wide costumes
  would do.
- Forgetting that `touching` sees screen positions. If two objects use the same
  `cam_x`, collisions are consistent; if one lags a frame, collisions flicker.

## Checklist

- [ ] Camera updated once per frame.
- [ ] Each visible object stores its world position in a local variable.
- [ ] Every object subtracts the same `cam_x`/`cam_y`.
- [ ] Original templates are hidden or off-screen.
- [ ] Clone count stays modest and clones are deleted when off-screen.
- [ ] Player bounds are clamped in world coordinates, not by the screen edge.
