# Games

> Use when: the request describes a game - platformer, flappy-style, pong,
> clicker, collect/dodge, maze, shooter, racing — or asks for score, lives,
> levels, game over, or win/lose states.

Games are the largest scenes this harness builds. A playable game needs more
than actors: it needs state, feedback and a reset. Every game change set should
cover all of the list below, in priority order, and stay within the normal
~80-block turn budget. Put anything that does not fit in `notes` instead of
cramming it in.

## Game essentials checklist

1. **Controls.** Key scripts with `key_pressed` inside `forever` + `wait 0.03`
   (smooth), or `when_key_pressed` hats for one-shot actions. Name the keys in
   the reply (`up arrow`, `space`, `a`).
2. **Score / lives / timer.** A global variable, created first, reset to 0 at
   green flag, and shown: `show_variable` for a HUD, or a `say`/`join` HUD
   script on the player. Increment it where the event happens.
3. **Game over.** A global `game_over` variable (0 = playing). The main loop
   wraps in `if game_over == 0` wait-for-not style: use `repeat_until
   game_over == 1` around the loop body, or check inside `forever`. On a hit:
   set it to 1, `say` the final score (`join`), optionally `stop_other_scripts`.
   No death handling = the actor just keeps going through obstacles.
4. **Reset on green flag.** Every flag script re-initializes: position,
   costume, `game_over = 0`, `score = 0`, speed variables. The green flag is
   the restart button; a second run must behave like the first.
5. **Animation.** Two-frame walk/flap: `next_costume` inside the movement loop
   (with a `wait`), or a costume switch on the action (flap frame on jump).
6. **Sounds.** Only names already in that sprite's `sounds` context
   (`play_sound "pop"`). A newly created sprite has no sounds — omit sound
   rather than invent a name.
7. **Feel.** `wait 0.03`–`0.05` per frame in `forever` loops; gravity as a
   `vy` variable (`change_var vy delta -1` then `change_y dy <vy>`); jump/flap
   as `set_var vy <impulse>`.

## Pattern: platformer that actually lands on its platforms

The player script must reference every platform sprite it creates. A platform
sprite that appears in no `touching` test is decoration: the actor falls
through it. Landing belongs in the gravity loop, checked while falling:

```json
{
  "action": "add_script", "target": "Cat", "label": "platformer",
  "hat": { "op": "when_flag_clicked" }, "body": [
    { "op": "goto_xy", "args": { "x": -180, "y": 100 } },
    { "op": "set_var", "args": { "name": "vy", "value": 0 } },
    { "op": "forever", "body": [
      { "op": "if", "args": { "condition": { "op": "key_pressed", "args": { "key": "right arrow" } } },
        "body": [ { "op": "change_x", "args": { "dx": 4 } } ] },
      { "op": "if", "args": { "condition": { "op": "key_pressed", "args": { "key": "left arrow" } } },
        "body": [ { "op": "change_x", "args": { "dx": -4 } } ] },
      { "op": "if", "args": { "condition": {
          "op": "and",
          "args": {
            "a": { "op": "key_pressed", "args": { "key": "up arrow" } },
            "b": { "op": "equals", "args": {
                "a": { "op": "get_var", "args": { "name": "vy" } }, "b": 0 } }
          } } },
        "body": [
          { "op": "set_var", "args": { "name": "vy", "value": 10 } }
        ] },
      { "op": "change_y", "args": { "dy": { "op": "get_var", "args": { "name": "vy" } } } },
      { "op": "change_var", "args": { "name": "vy", "delta": -1 } },
      { "op": "if", "args": { "condition": {
          "op": "or",
          "args": {
            "a": { "op": "or", "args": {
                "a": { "op": "touching", "args": { "target": "Ground" } },
                "b": { "op": "touching", "args": { "target": "Platform1" } } } },
            "b": { "op": "touching", "args": { "target": "Platform2" } }
          } } },
        "body": [
          { "op": "change_y", "args": { "dy": 6 } },
          { "op": "set_var", "args": { "name": "vy", "value": 0 } }
        ] },
      { "op": "if", "args": { "condition": {
          "op": "less_than", "args": { "a": { "op": "y_position" }, "b": -140 } } },
        "body": [
          { "op": "set_y", "args": { "y": -140 } },
          { "op": "set_var", "args": { "name": "vy", "value": 0 } }
        ] },
      { "op": "wait", "args": { "seconds": 0.04 } }
    ] }
  ]
}
```

Notes: the `touching`-or-chain is the landing test; the y-floor is only a
safety net for open ground. If the actor sinks into a platform, raise the
`change_y` nudge. For one-way feel, land only while falling: wrap the
landing `if` in `vy < 0`.

## Pattern: flappy-style with clone pipes

One Bird + one Pipe sprite; the pipes are clones of Pipe (load the `clones`
pack too). Clones copy the original's position, costume, effects, visibility
and locals, so keep the original **visible** and parked off-stage — a hidden
original spawns hidden clones. Score once per pipe as it passes the bird,
using a per-clone `scored` flag (locals copy to clones):

```json
{ "action": "create_sprite", "name": "Pipe",
  "costumes": [ { "library": "Geometry/line.png" } ],
  "x": 300, "y": 0, "direction": 90, "size": 140, "visible": true,
  "rotation_style": "don't rotate" }
```

```json
{ "action": "add_script", "target": "Pipe", "label": "spawn",
  "hat": { "op": "when_flag_clicked" }, "body": [
    { "op": "forever", "body": [
      { "op": "create_clone", "args": { "target": "myself" } },
      { "op": "wait", "args": { "seconds": 1.6 } }
    ] }
  ] }
```

```json
{
  "action": "add_script",
  "target": "Pipe",
  "label": "pipe_travel",
  "hat": {
    "op": "when_clone_start"
  },
  "body": [
    {
      "op": "goto_xy",
      "args": {
        "x": 260,
        "y": {
          "op": "random",
          "args": {
            "from": -120,
            "to": 120
          }
        }
      }
    },
    {
      "op": "set_var",
      "args": {
        "name": "scored",
        "value": 0
      }
    },
    {
      "op": "repeat_until",
      "args": {
        "condition": {
          "op": "less_than",
          "args": {
            "a": {
              "op": "x_position"
            },
            "b": -280
          }
        }
      },
      "body": [
        {
          "op": "change_x",
          "args": {
            "dx": -4
          }
        },
        {
          "op": "if",
          "args": {
            "condition": {
              "op": "and",
              "args": {
                "a": {
                  "op": "less_than",
                  "args": {
                    "a": {
                      "op": "x_position"
                    },
                    "b": {
                      "op": "attribute_of",
                      "args": {
                        "attribute": "x position",
                        "target": "Bird"
                      }
                    }
                  }
                },
                "b": {
                  "op": "equals",
                  "args": {
                    "a": {
                      "op": "get_var",
                      "args": {
                        "name": "scored"
                      }
                    },
                    "b": 0
                  }
                }
              }
            }
          },
          "body": [
            {
              "op": "change_var",
              "args": {
                "name": "score",
                "delta": 1
              }
            },
            {
              "op": "set_var",
              "args": {
                "name": "scored",
                "value": 1
              }
            }
          ]
        },
        {
          "op": "wait",
          "args": {
            "seconds": 0.04
          }
        }
      ]
    },
    {
      "op": "delete_clone"
    }
  ]
}
```

```json
{
  "action": "add_script",
  "target": "Bird",
  "label": "fly",
  "hat": {
    "op": "when_flag_clicked"
  },
  "body": [
    {
      "op": "goto_xy",
      "args": {
        "x": -120,
        "y": 0
      }
    },
    {
      "op": "set_var",
      "args": {
        "name": "vy",
        "value": 0
      }
    },
    {
      "op": "repeat_until",
      "args": {
        "condition": {
          "op": "equals",
          "args": {
            "a": {
              "op": "get_var",
              "args": {
                "name": "game_over"
              }
            },
            "b": 1
          }
        }
      },
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
              "op": "set_var",
              "args": {
                "name": "vy",
                "value": 8
              }
            },
            {
              "op": "switch_costume",
              "args": {
                "costume": "dove1-b"
              }
            }
          ]
        },
        {
          "op": "change_y",
          "args": {
            "dy": {
              "op": "get_var",
              "args": {
                "name": "vy"
              }
            }
          }
        },
        {
          "op": "change_var",
          "args": {
            "name": "vy",
            "delta": -1
          }
        },
        {
          "op": "if",
          "args": {
            "condition": {
              "op": "or",
              "args": {
                "a": {
                  "op": "touching",
                  "args": {
                    "target": "Pipe"
                  }
                },
                "b": {
                  "op": "or",
                  "args": {
                    "a": {
                      "op": "touching",
                      "args": {
                        "target": "Ground"
                      }
                    },
                    "b": {
                      "op": "less_than",
                      "args": {
                        "a": {
                          "op": "y_position"
                        },
                        "b": -170
                      }
                    }
                  }
                }
              }
            }
          },
          "body": [
            {
              "op": "set_var",
              "args": {
                "name": "game_over",
                "value": 1
              }
            },
            {
              "op": "say",
              "args": {
                "text": {
                  "op": "join",
                  "args": {
                    "a": "Game over! Score: ",
                    "b": {
                      "op": "get_var",
                      "args": {
                        "name": "score"
                      }
                    }
                  }
                }
              }
            }
          ]
        },
        {
          "op": "wait",
          "args": {
            "seconds": 0.04
          }
        }
      ]
    }
  ]
}
```

`touching Pipe` sees the original and every clone. Score `+1` per pipe is
fair; for harder scoring, count only clean passes.

## Game props (verified library files)

The library has no literal "platform" or "pipe" art. These read as game
geometry and are all real paths:

- Flat bar / beam / pipe body: ALWAYS `Geometry/line.png` — a plain red
  bar. Use `direction: 0` for a vertical pipe, `90` for a horizontal beam;
  scale with `set_size` / the create_sprite `size` field as needed. Never use
  `Players/fantasy1-a.png` (or another `Players/fantasy1-*` character) or any
  character art for pipes, platforms or walls — those are cartoon creatures,
  not game geometry.
- Letter blocks (tile platforms): `Letters/Block/a.png` ...
  `Letters/Block/z.png`.
- Rocky chunk: `Scenery/rock.png`.
- Bounce pad: `Sports/trampoline.png`.
- Paddle (pong/squash): `GameItems/paddle.png`.
- HUD frame: `UI/scoreboard.gif` as a HUD sprite, or just
  `show_variable`.
- Two-frame flier: `Animals/dove1-a.png` + `Animals/dove1-b.png`.
- Game backdrops: `Outdoors/brick-wall1.jpg`, `Outdoors/boardwalk.jpg`,
  `Space/stars.gif`.

The only line file is `Geometry/line.png` — use that full path; the grouped
media index may be trimmed, but the verified prop paths are listed in the
system prompt above it.

## Pong-style in three scripts

Paddle 1 (`when_key_pressed up/down` hats + `change_y`), Paddle 2 mirrors,
Ball: `when_flag` → random direction, `forever`: `move`, `bounce`, `if
touching Paddle1/Paddle2 → turn_right 180`, `if x < -230 → change_var p2
delta 1` (and mirror). Score via `show_variable`. Ball art:
`Sports/beachball.png`, `Sports/ball-soccer.png`, or preset `"Ball"`.

## Win / lose / rounds

- Lose: `game_over` as above, or `lives` counting down on hits; at 0 show the
  message.
- Win: same gating with a `won` variable set when the goal fires
  (`touching` a Goal sprite, `score` reaching a target with
  `greater_than`).
- Rounds/timer: a Stage script `forever` + `wait 1` incrementing `time`, or
  `broadcast "next_round"` to receivers that reposition and speed up
  (raise the move step or lower the spawn `wait`).

## Rules that prevent bugs

- Create every variable before the scripts that use it; reset them all in a
  flag script.
- A `wait` is a block in the body list — never a named field of another
  block. `{ "op": "wait", "args": { "seconds": 0.04 } }` inside the body,
  not `"wait": {...}` beside it.
- Do not run the whole game in one giant script: one script per actor, one
  Stage script for spawning/rounds. Broadcasts start/stop actors.
- `repeat_until game_over == 1` stops that actor's loop; other actors still
  need their own checks. `stop_all` ends everything (green flag restarts).
- Clones are runtime-only: never put a clone name in a menu, never target
  one directly — control from the original (see the `clones` pack).
- Keep the core loop under ~80 blocks. Pipes/enemies/collectibles are
  clones of one sprite, not many sprites.
- Scrolling worlds: load the `scrolling` pack instead of guessing camera
  math.
