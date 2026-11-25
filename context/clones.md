# Clones

> Use when: the scene has three or more similar things (crabs, fish, stars,
> coins, enemies, bricks, trees, snowflakes, asteroids), or spawns bullets,
> particles, pipes, waves or tiles - including scenes where nothing spawns
> during play. Many of the same thing = one sprite plus clones.

Clones are Scratch 2.0-style runtime copies of a sprite. In this harness they
are the **default for "many of the same thing"**: one template sprite plus one
clone script replaces N copy-pasted sprites and N copy-pasted scripts.

| | N separate sprites | 1 sprite + clones |
|---|---|---|
| Blocks to write | N x every script | every script once |
| "Make the crabs faster" | N `replace_script`s that must stay in sync | one `replace_script` |
| Collision | `touching` Crab1 or Crab2 or ... | `touching` Crab sees every clone |
| Scaling 3 -> 30 | 27 more sprites | change one loop count |
| Per-instance variety | separate scripts | set a local variable / costume / size before each clone |

Use **separate sprites** instead only when each one is a distinct character
with its own role or scripts, when the user asked for named sprites they will
edit in the sprite pane, or when another script must `point_towards`,
`goto_sprite`, `distance_to` or `attribute_of` one specific instance (those
always mean the original, never a clone).

## How a clone is made (exact semantics in this harness)

1. `create_clone` with target `myself` (or another sprite, e.g. `Enemy`)
   copies the target sprite **as it is at that instant**: x, y, direction,
   size, costume, graphic effects, **visibility**, costumes, sounds, and the
   current values of its **local** variables and lists. Global (Stage)
   variables and lists are shared, never copied.
2. The new clone is placed on the **top layer**.
3. The clone gets copies of all of the sprite's scripts, stopped. Its
   `when_clone_start` scripts start at once, and run only in that new clone -
   never in the original.
4. The clone keeps **every other hat** too: `when_receive`,
   `when_key_pressed`, `when_clicked`, `when_timer_greater` and
   `when_loudness_greater` fire in each clone as well as in the original.
   (`when_flag_clicked` never matters: the green flag deletes all clones
   first.)
5. A clone lives until it runs `delete_clone`, or the green flag / stop
   button / `stop_all` removes every clone. A clone whose scripts all ended
   stays on stage. `delete_clone` in the original does nothing.
6. At 300 live clones `create_clone` silently does nothing.
7. Clones are not project sprites: they are absent from the project context,
   the sprite pane and saved files, and cannot be named in a menu or a
   `target`. Only sprites can clone; the Stage cannot (it can `broadcast` to a
   sprite that does).
8. `create_clone` of `myself` inside a clone clones that clone (with its current
   state); `touching` still treats it as part of the original's family.

## The stamp idiom: set up, then clone

Because a clone copies the parent's state at the moment of `create_clone`,
the original works like a stamp: **move it, set its local variables, pick its
costume and size, then clone**. Each clone starts already in place with its
own values; nothing has to be handed over afterwards, so there is no timing
race. Hide the template original at the end if it should not be part of the
scene.

```python
# Crab: hidden template; three clones at fixed spots, each with its own speed
@on_flag(target="Crab", label="spawn_crabs")
def spawn_crabs():
    hide()
    set_size(40)
    goto_xy(-150, -110)
    for _ in range(3):
        speed = random(1, 3)
        create_clone("myself")
        change_x(140)


@on_clone_start(target="Crab", label="crab_wander")
def crab_wander():
    show()
    while True:
        move(speed)
        turn_right(random(-15, 15))
        bounce()
        next_costume()
        wait(0.15)
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
[
  {
    "action": "add_script",
    "target": "Crab",
    "label": "spawn_crabs",
    "hat": {
      "op": "when_flag_clicked"
    },
    "body": [
      {
        "op": "hide"
      },
      {
        "op": "set_size",
        "args": {
          "percent": 40
        }
      },
      {
        "op": "goto_xy",
        "args": {
          "x": -150,
          "y": -110
        }
      },
      {
        "op": "repeat",
        "args": {
          "count": 3
        },
        "body": [
          {
            "op": "set_var",
            "args": {
              "name": "speed",
              "value": {
                "op": "random",
                "args": {
                  "from": 1,
                  "to": 3
                }
              }
            }
          },
          {
            "op": "create_clone",
            "args": {
              "target": "myself"
            }
          },
          {
            "op": "change_x",
            "args": {
              "dx": 140
            }
          }
        ]
      }
    ]
  },
  {
    "action": "add_script",
    "target": "Crab",
    "label": "crab_wander",
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
            "op": "move",
            "args": {
              "steps": {
                "op": "get_var",
                "args": {
                  "name": "speed"
                }
              }
            }
          },
          {
            "op": "turn_right",
            "args": {
              "degrees": {
                "op": "random",
                "args": {
                  "from": -15,
                  "to": 15
                }
              }
            }
          },
          {
            "op": "bounce"
          },
          {
            "op": "next_costume"
          },
          {
            "op": "wait",
            "args": {
              "seconds": 0.15
            }
          }
        ]
      }
    ]
  }
]
```

`speed` is a **sprite-local** variable of Crab
(`create_variable` with scope `sprite`, target `Crab`), so every clone
keeps the value the original held when that clone was made. A global
`speed` would be one shared value for all of them.

Avoid the opposite hand-off - setting a global in the parent and reading it in
`when_clone_start`: the clone script runs on a later frame, by which time the
parent may already have changed the global again.

## Rules that prevent bugs

- **Hidden template, hidden clones.** Visibility is copied: if the original is
  hidden, call `show` first thing in `when_clone_start`.
- **No clone bombs.** Never put `create_clone` of `myself` in a script that
  clones also run - `when_receive`, `when_key_pressed`, `when_clicked`, or a
  loop inside `when_clone_start` - unless you mean every clone to spawn too:
  one broadcast would double the population each time. Spawn from the
  original's `when_flag_clicked` script, or guard with a local flag (below).
- **Per-clone state is local.** Variables a clone changes for itself (`speed`,
  `life`, `hp`, `vx`, `scored`) must be sprite-local on the cloned sprite.
  Globals (`score`, `game_over`) are shared by everyone - use them for totals
  and signals.
- **Telling the original from its clones.** Give the sprite a local `is_clone`:
  the original sets `is_clone` to 0 at green flag, each clone sets
  `is_clone` to 1 in `when_clone_start`. Shared hats check it
  (if `is_clone` = 1 then `delete_clone`).
- **Collisions belong to the clone.** `touching` Coin from the player is
  true for any Coin clone but cannot tell which; let each clone test
  `touching` Player itself and react (score, sound, `delete_clone`).
- **Group commands** use `broadcast`: every clone (and the original) runs the
  matching `when_receive` - e.g. `broadcast` game_over with a
  `when_receive` game_over script doing `delete_clone` clears the field.
- **Clean up.** A clone that leaves the stage or finishes its job must
  `delete_clone`; a clone with no running script still costs memory.
- **Budget.** Each clone deep-copies costumes and scripts in Scratch 1.4.
  Keep live clones in the tens (about 60 at once is a comfortable ceiling),
  pace spawners with `wait`, and delete off-screen clones.
- Clones never appear in the project context; do not try to `replace_script`
  or `set_sprite` a clone - edit the template sprite's scripts and every
  future clone follows.

## Pattern: spawner (bullets, pipes, falling things)

```python
@on_flag(target="Bullet", label="fire")
def fire():
    hide()
    while True:
        if key_pressed("space"):
            goto_sprite("Player")
            create_clone("myself")
            wait(0.25)
        wait(0.03)


@on_clone_start(target="Bullet", label="bullet_fly")
def bullet_fly():
    show()
    point_in_direction(0)
    while not touching("edge"):
        move(10)
        wait(0.03)
    delete_clone()
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
[
  {
    "action": "add_script",
    "target": "Bullet",
    "label": "fire",
    "hat": {
      "op": "when_flag_clicked"
    },
    "body": [
      {
        "op": "hide"
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
                  "key": "space"
                }
              }
            },
            "body": [
              {
                "op": "goto_sprite",
                "args": {
                  "target": "Player"
                }
              },
              {
                "op": "create_clone",
                "args": {
                  "target": "myself"
                }
              },
              {
                "op": "wait",
                "args": {
                  "seconds": 0.25
                }
              }
            ]
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
  },
  {
    "action": "add_script",
    "target": "Bullet",
    "label": "bullet_fly",
    "hat": {
      "op": "when_clone_start"
    },
    "body": [
      {
        "op": "show"
      },
      {
        "op": "point_in_direction",
        "args": {
          "degrees": 0
        }
      },
      {
        "op": "repeat_until",
        "args": {
          "condition": {
            "op": "touching",
            "args": {
              "target": "edge"
            }
          }
        },
        "body": [
          {
            "op": "move",
            "args": {
              "steps": 10
            }
          },
          {
            "op": "wait",
            "args": {
              "seconds": 0.03
            }
          }
        ]
      },
      {
        "op": "delete_clone"
      }
    ]
  }
]
```

The hidden original moves to the player and stamps a clone; the visible clone
flies and deletes itself at the edge. The spawner stays in the original's
green-flag script, so clones never spawn clones.

## Pattern: particles with per-clone randomness

```python
@on_receive("burst", target="Spark", label="spark_burst")
def spark_burst():
    if is_clone == 0:
        for _ in range(12):
            create_clone("myself")


@on_clone_start(target="Spark", label="spark_life")
def spark_life():
    is_clone = 1
    show()
    point_in_direction(random(-180, 180))
    for _ in range(20):
        move(4)
        change_effect("ghost", 5)
        wait(0.03)
    delete_clone()
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
[
  {
    "action": "add_script",
    "target": "Spark",
    "label": "spark_burst",
    "hat": {
      "op": "when_receive",
      "args": {
        "message": "burst"
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
                "op": "get_var",
                "args": {
                  "name": "is_clone"
                }
              },
              "b": 0
            }
          }
        },
        "body": [
          {
            "op": "repeat",
            "args": {
              "count": 12
            },
            "body": [
              {
                "op": "create_clone",
                "args": {
                  "target": "myself"
                }
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "action": "add_script",
    "target": "Spark",
    "label": "spark_life",
    "hat": {
      "op": "when_clone_start"
    },
    "body": [
      {
        "op": "set_var",
        "args": {
          "name": "is_clone",
          "value": 1
        }
      },
      {
        "op": "show"
      },
      {
        "op": "point_in_direction",
        "args": {
          "degrees": {
            "op": "random",
            "args": {
              "from": -180,
              "to": 180
            }
          }
        }
      },
      {
        "op": "repeat",
        "args": {
          "count": 20
        },
        "body": [
          {
            "op": "move",
            "args": {
              "steps": 4
            }
          },
          {
            "op": "change_effect",
            "args": {
              "effect": "ghost",
              "delta": 5
            }
          },
          {
            "op": "wait",
            "args": {
              "seconds": 0.03
            }
          }
        ]
      },
      {
        "op": "delete_clone"
      }
    ]
  }
]
```

`burst` reaches the original and every live spark; the `is_clone` = 0 guard
makes only the original spawn, so twelve sparks stay twelve. The original
needs `is_clone` set to 0 (and `hide`) in its green-flag setup.

## Pattern: grid of tiles or bricks (nested stamp loops)

```python
@on_flag(target="Tile", label="build_grid")
def build_grid():
    hide()
    goto_xy(-200, 150)
    for _ in range(4):
        for _ in range(10):
            create_clone("myself")
            change_x(44)
        change_x(-440)
        change_y(-24)
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
{
  "action": "add_script",
  "target": "Tile",
  "label": "build_grid",
  "hat": {
    "op": "when_flag_clicked"
  },
  "body": [
    {
      "op": "hide"
    },
    {
      "op": "goto_xy",
      "args": {
        "x": -200,
        "y": 150
      }
    },
    {
      "op": "repeat",
      "args": {
        "count": 4
      },
      "body": [
        {
          "op": "repeat",
          "args": {
            "count": 10
          },
          "body": [
            {
              "op": "create_clone",
              "args": {
                "target": "myself"
              }
            },
            {
              "op": "change_x",
              "args": {
                "dx": 44
              }
            }
          ]
        },
        {
          "op": "change_x",
          "args": {
            "dx": -440
          }
        },
        {
          "op": "change_y",
          "args": {
            "dy": -24
          }
        }
      ]
    }
  ]
}
```

Forty bricks from six blocks; each clone's `when_clone_start` does `show`
and, for breakout, waits until `touching` Ball, adds to `score` and runs
`delete_clone`.

## Pattern: collectibles that score themselves

```python
@on_flag(target="Coin", label="place_coins")
def place_coins():
    hide()
    for _ in range(8):
        goto_xy(random(-220, 220), random(-160, 160))
        create_clone("myself")


@on_clone_start(target="Coin", label="coin_wait")
def coin_wait():
    show()
    wait_until(touching("Player"))
    score += 1
    delete_clone()
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
[
  {
    "action": "add_script",
    "target": "Coin",
    "label": "place_coins",
    "hat": {
      "op": "when_flag_clicked"
    },
    "body": [
      {
        "op": "hide"
      },
      {
        "op": "repeat",
        "args": {
          "count": 8
        },
        "body": [
          {
            "op": "goto_xy",
            "args": {
              "x": {
                "op": "random",
                "args": {
                  "from": -220,
                  "to": 220
                }
              },
              "y": {
                "op": "random",
                "args": {
                  "from": -160,
                  "to": 160
                }
              }
            }
          },
          {
            "op": "create_clone",
            "args": {
              "target": "myself"
            }
          }
        ]
      }
    ]
  },
  {
    "action": "add_script",
    "target": "Coin",
    "label": "coin_wait",
    "hat": {
      "op": "when_clone_start"
    },
    "body": [
      {
        "op": "show"
      },
      {
        "op": "wait_until",
        "args": {
          "condition": {
            "op": "touching",
            "args": {
              "target": "Player"
            }
          }
        }
      },
      {
        "op": "change_var",
        "args": {
          "name": "score",
          "delta": 1
        }
      },
      {
        "op": "delete_clone"
      }
    ]
  }
]
```

`score` is global (shared total); the touch test runs inside each clone, so
the right coin disappears.

## Testing a clone scene

- Green flag: the template hides, the expected number of clones appear, and
  they are visible (a missing `show` is the usual reason nothing appears).
- Trigger a broadcast twice and confirm the clone count does not double.
- Let clones expire or leave the stage and confirm they delete themselves.
- Press the green flag again: every old clone is gone and the scene rebuilds
  once.
