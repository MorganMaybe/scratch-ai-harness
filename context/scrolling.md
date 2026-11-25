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

```python
@on_flag(target="Player", label="move_and_camera")
def move_and_camera():
    player_x = 0
    cam_x = 0
    while True:
        if key_pressed("right arrow"):
            player_x += 5
        if key_pressed("left arrow"):
            player_x -= 5
        cam_x = player_x
        set_x(0)
        set_y(-40)
        wait(0.03)
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
{
  "action": "add_script",
  "target": "Player",
  "label": "move_and_camera",
  "hat": {
    "op": "when_flag_clicked"
  },
  "body": [
    {
      "op": "set_var",
      "args": {
        "name": "player_x",
        "value": 0
      }
    },
    {
      "op": "set_var",
      "args": {
        "name": "cam_x",
        "value": 0
      }
    },
    {
      "op": "forever",
      "body": [
        {
          "op": "if",
          "args": {
            "condition": {
              "op": "key_pressed",
              "args": {
                "key": "right arrow"
              }
            }
          },
          "body": [
            {
              "op": "change_var",
              "args": {
                "name": "player_x",
                "delta": 5
              }
            }
          ]
        },
        {
          "op": "if",
          "args": {
            "condition": {
              "op": "key_pressed",
              "args": {
                "key": "left arrow"
              }
            }
          },
          "body": [
            {
              "op": "change_var",
              "args": {
                "name": "player_x",
                "delta": -5
              }
            }
          ]
        },
        {
          "op": "set_var",
          "args": {
            "name": "cam_x",
            "value": {
              "op": "get_var",
              "args": {
                "name": "player_x"
              }
            }
          }
        },
        {
          "op": "set_x",
          "args": {
            "x": 0
          }
        },
        {
          "op": "set_y",
          "args": {
            "y": -40
          }
        },
        {
          "op": "wait",
          "args": {
            "seconds": 0.03
          }
        }
      ]
    }
  ]
}
```

The player stays at screen x = 0 because the camera follows it exactly. The
world moves under the player.

## Scrolling tiles with clones

Tile sprite local variable: `tile_x` (create it first with
`create_variable(..., scope="sprite")`). Global: `cam_x`.

```python
@on_flag(target="Tile", label="build_tiles")
def build_tiles():
    hide()
    set_y(-150)
    tile_x = 0
    for _ in range(24):
        create_clone("myself")
        tile_x += 40


@on_clone_start(target="Tile", label="tile_follow")
def tile_follow():
    show()
    while True:
        set_x(tile_x - cam_x)
        wait(0.03)
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
[
  {
    "action": "add_script",
    "target": "Tile",
    "label": "build_tiles",
    "hat": {
      "op": "when_flag_clicked"
    },
    "body": [
      {
        "op": "hide"
      },
      {
        "op": "set_y",
        "args": {
          "y": -150
        }
      },
      {
        "op": "set_var",
        "args": {
          "name": "tile_x",
          "value": 0
        }
      },
      {
        "op": "repeat",
        "args": {
          "count": 24
        },
        "body": [
          {
            "op": "create_clone",
            "args": {
              "target": "myself"
            }
          },
          {
            "op": "change_var",
            "args": {
              "name": "tile_x",
              "delta": 40
            }
          }
        ]
      }
    ]
  },
  {
    "action": "add_script",
    "target": "Tile",
    "label": "tile_follow",
    "hat": {
      "op": "when_clone_start"
    },
    "body": [
      {
        "op": "show"
      },
      {
        "op": "forever",
        "body": [
          {
            "op": "set_x",
            "args": {
              "x": {
                "op": "subtract",
                "args": {
                  "a": {
                    "op": "get_var",
                    "args": {
                      "name": "tile_x"
                    }
                  },
                  "b": {
                    "op": "get_var",
                    "args": {
                      "name": "cam_x"
                    }
                  }
                }
              }
            }
          },
          {
            "op": "wait",
            "args": {
              "seconds": 0.03
            }
          }
        ]
      }
    ]
  }
]
```

The template sets its own local `tile_x` and then clones: each clone is born
with the `tile_x` the template held at that instant (local variables are
copied), so later changes do not move existing tiles and there is no timing
race. Never hand a value over through a global read in `@on_clone_start` - the
clone runs a frame later and may see the next value.

There is no stock grass/ground **costume** in the Scratch 1.4 library (searching
for `grass` finds only grasshoppers). Do not invent `Nature/grass1.png` or any
other path. Use a costume that actually appears in the media index — a wide
shape or line is fine — or make the ground part of a backdrop. If no suitable
tile exists, use a simple broad costume and note the approximation.

## Tile maps from a list

Instead of one clone per column, use a global list `map` containing `0`/`1` per
tile. The parent loop walks the list, tests `list_item`, and only clones where
the value is 1:

```python
@on_flag(target="Tile", label="build_from_map")
def build_from_map():
    hide()
    set_y(-150)
    spawn_index = 1
    tile_x = 0
    for _ in range(list_length("map")):
        if list_item(spawn_index, "map") == 1:
            create_clone("myself")
        spawn_index += 1
        tile_x += 40
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
{
  "action": "add_script",
  "target": "Tile",
  "label": "build_from_map",
  "hat": {
    "op": "when_flag_clicked"
  },
  "body": [
    {
      "op": "hide"
    },
    {
      "op": "set_y",
      "args": {
        "y": -150
      }
    },
    {
      "op": "set_var",
      "args": {
        "name": "spawn_index",
        "value": 1
      }
    },
    {
      "op": "set_var",
      "args": {
        "name": "tile_x",
        "value": 0
      }
    },
    {
      "op": "repeat",
      "args": {
        "count": {
          "op": "list_length",
          "args": {
            "list": "map"
          }
        }
      },
      "body": [
        {
          "op": "if",
          "args": {
            "condition": {
              "op": "equals",
              "args": {
                "a": {
                  "op": "list_item",
                  "args": {
                    "index": {
                      "op": "get_var",
                      "args": {
                        "name": "spawn_index"
                      }
                    },
                    "list": "map"
                  }
                },
                "b": 1
              }
            }
          },
          "body": [
            {
              "op": "create_clone",
              "args": {
                "target": "myself"
              }
            }
          ]
        },
        {
          "op": "change_var",
          "args": {
            "name": "spawn_index",
            "delta": 1
          }
        },
        {
          "op": "change_var",
          "args": {
            "name": "tile_x",
            "delta": 40
          }
        }
      ]
    }
  ]
}
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
