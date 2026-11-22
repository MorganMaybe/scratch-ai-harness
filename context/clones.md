# Clones

> Use when: spawning bullets, particles, enemies, tiled scenery, trails, or any
> request that needs many temporary copies of a sprite.

Clones are Scratch 2.0-style temporary copies. They are runtime-only: they are
not in the project context, the sprite pane, the media library, or a save file.
The core blocks are:

- `create_clone` with `target`: `"myself"` or an existing sprite name.
- `delete_clone`: removes the clone that runs it. On an original sprite it does
  nothing.
- `when_clone_start`: hat that runs once in each new clone.

## Lifecycle

1. `create_clone` copies the source sprite: position, direction, size, costume,
   graphic effects, local variables and local lists. Global (Stage) variables
   and lists are shared, not copied.
2. Copied scripts are stopped. The clone does **not** continue the original's
   running scripts.
3. The clone's `when_clone_start` script starts. That is where its own setup and
   lifetime belong.
4. The clone stays alive until `delete_clone` runs or the project stops. Green
   flag / `stop_all` deletes every clone. A clone whose script simply ends stays
   alive.
5. Creation past 300 clones is ignored.

## Rules that prevent bugs

- Do not put clones in menus or target them by name. They are not in the project
  context, and their internal names are not stable. Create and control them from
  the original.
- `touching [sprite]?` is true when touching that original **or any of its
  clones**. `distance_to`, `goto_sprite` and `point_towards` use the original.
- `delete this clone` is not a sprite deletion. Do not use it to remove the
  original.
- A clone can run ordinary hats too (click, key, receive), not just the clone
  hat. Use broadcasts for group commands.
- Each clone deep-copies costumes, sounds and scripts in Scratch 1.4. Keep the
  live count in the tens, not hundreds, even though the 2.0 limit is 300.
- Always delete clones at the end of their useful life. A clone with no script
  still persists.

## Pattern: bullets

Two scripts on the bullet sprite:

```json
[
  {
    "action": "add_script",
    "target": "Bullet",
    "label": "fire",
    "hat": { "op": "when_flag_clicked" },
    "body": [
      { "op": "forever", "body": [
        { "op": "create_clone", "args": { "target": "myself" } },
        { "op": "wait", "args": { "seconds": 0.35 } }
      ] }
    ]
  },
  {
    "action": "add_script",
    "target": "Bullet",
    "label": "clone_life",
    "hat": { "op": "when_clone_start" },
    "body": [
      { "op": "goto_xy", "args": { "x": 0, "y": -140 } },
      { "op": "repeat", "args": { "count": 40 }, "body": [
        { "op": "change_y", "args": { "dy": 8 } }
      ] },
      { "op": "delete_clone" }
    ]
  }
]
```

The original bullet should be hidden or parked off-screen if it should not be
visible; the clones carry the visible action.

## Pattern: particles with per-clone randomness

`when_clone_start` is a good place for `random`:

```json
{
  "action": "add_script",
  "target": "Spark",
  "label": "spark_life",
  "hat": { "op": "when_clone_start" },
  "body": [
    { "op": "set_var", "args": { "name": "life", "value": 30 } },
    { "op": "repeat", "args": { "count": 30 }, "body": [
      { "op": "change_x", "args": { "dx": {
        "op": "random", "args": { "from": -3, "to": 3 } } } },
      { "op": "change_y", "args": { "dy": -2 } },
      { "op": "change_var", "args": { "name": "life", "delta": -1 } }
    ] },
    { "op": "delete_clone" }
  ]
}
```

Use a local variable (`scope: "sprite"`) for per-clone state such as `life`.
Global variables are shared by every clone.

## Pattern: tiled scenery with clones

To build a row of tiles, use a parent loop with a global `spawn_index`, create a
clone per tile, and have each clone read that index in `when_clone_start` into a
local variable:

```json
[
  {
    "action": "add_script",
    "target": "Tile",
    "label": "build_row",
    "hat": { "op": "when_flag_clicked" },
    "body": [
      { "op": "set_var", "args": { "name": "spawn_index", "value": 0 } },
      { "op": "repeat", "args": { "count": 12 }, "body": [
        { "op": "create_clone", "args": { "target": "myself" } },
        { "op": "change_var", "args": { "name": "spawn_index", "delta": 1 } }
      ] }
    ]
  },
  {
    "action": "add_script",
    "target": "Tile",
    "label": "tile_place",
    "hat": { "op": "when_clone_start" },
    "body": [
      { "op": "set_var", "args": { "name": "tile_index", "value": {
        "op": "get_var", "args": { "name": "spawn_index" } } } },
      { "op": "set_x", "args": { "x": {
        "op": "*", "args": { "a": {
          "op": "get_var", "args": { "name": "tile_index" } },
          "b": 40 } } } }
    ]
  }
]
```

Make `tile_index` a sprite-local variable. The global `spawn_index` is only the
hand-off channel.

## Testing a clone scene

- Run the green flag, let it create one clone, and confirm `delete_clone` runs.
- Check that the original is still present and the clone count returns to zero.
- Confirm a clone can receive a broadcast and stop itself.
- If nothing appears, look for a missing `when_clone_start` script, a clone that
  is immediately deleted, or a hidden original/costume.
