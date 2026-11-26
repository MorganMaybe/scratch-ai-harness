# Scenes (multiple screens)

> Use when: the project has more than one screen - a title or menu screen, a
> play screen, a game over or win screen, instructions, levels that look
> completely different, rooms, story chapters or pages - or the user mentions
> scenes, screens, menus, a start button or "play again".

Scratch 1.4 has one Stage and no scene object. A "screen" is an agreement
between scripts: **one global `scene` number says which screen is active**,
and every sprite decides for itself whether it is part of that screen.

## The model

- `scene` is a **global** number, created once
  (`create_variable` named `scene`, scope `global`, initial 1). Number the
  screens and say what they are in the plan and in the `notes`, for example
  `1 title, 2 play, 3 game over`.
- **One message, `scene_changed`.** Whoever changes the screen sets `scene`
  and then broadcasts `scene_changed` - always both, always in that order.
  Never change `scene` without the broadcast; nothing would react.
- **Every sprite has one `when_receive` `scene_changed` script** that starts
  with the visibility decision: `show` when `scene` is one of its screens,
  otherwise `hide`. A sprite visible on several screens tests them all
  (`scene` = 1 or `scene` = 3).
- **The Stage's `when_receive` `scene_changed` script** switches the
  backdrop for each scene and resets the state of the scene being entered.
- **The green flag only starts the router**: the Stage's flag script resets
  the globals, runs `pen_clear`, sets `scene` to 1 and broadcasts
  `scene_changed`. Sprites do not show or hide in their own flag scripts -
  their scene handler does it - so there is no race between the flag and the
  first screen.
- **Entering a scene resets that scene.** Positions, costumes, effects and
  speech are reset at the top of the sprite's `scene_changed` branch for that
  scene, so "play again" starts as cleanly as the first run.
- **Scene loops end themselves.** A sprite's per-frame behaviour for a scene
  is a `repeat_until` loop that runs while `scene` is still 2, inside its
  handler, so it stops the moment the screen changes. A new `scene_changed`
  broadcast also restarts the handler.
- Hidden sprites cannot be clicked, so a button only works on the screens
  where it is shown; still guard the click with the scene test.

Broadcasting once beats having every sprite poll in a `forever` loop (if
`scene` = 2 then `show`): the switch happens in one frame, nothing flickers,
and no sprite burns a loop on screens it is not part of.

## Pattern: the Stage router

```python
@on_flag(target="Stage", label="start_title")
def start_title():
    pen_clear()
    score = 0
    lives = 3
    scene = 1
    broadcast("scene_changed")


@on_receive("scene_changed", target="Stage", label="scene_router")
def scene_router():
    if scene == 1:
        switch_backdrop("stars")
    elif scene == 2:
        switch_backdrop("moon")
        score = 0
        lives = 3
        while scene == 2:
            wait(1)
            score += 1
    else:
        switch_backdrop("stars")
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
[
  {
    "action": "add_script",
    "target": "Stage",
    "label": "start_title",
    "hat": {
      "op": "when_flag_clicked"
    },
    "body": [
      {
        "op": "pen_clear"
      },
      {
        "op": "set_var",
        "args": {
          "name": "score",
          "value": 0
        }
      },
      {
        "op": "set_var",
        "args": {
          "name": "lives",
          "value": 3
        }
      },
      {
        "op": "set_var",
        "args": {
          "name": "scene",
          "value": 1
        }
      },
      {
        "op": "broadcast",
        "args": {
          "message": "scene_changed"
        }
      }
    ]
  },
  {
    "action": "add_script",
    "target": "Stage",
    "label": "scene_router",
    "hat": {
      "op": "when_receive",
      "args": {
        "message": "scene_changed"
      }
    },
    "body": [
      {
        "op": "if_else",
        "args": {
          "condition": {
            "op": "equals",
            "args": {
              "a": {
                "op": "get_var",
                "args": {
                  "name": "scene"
                }
              },
              "b": 1
            }
          }
        },
        "then": [
          {
            "op": "switch_backdrop",
            "args": {
              "backdrop": "stars"
            }
          }
        ],
        "else": [
          {
            "op": "if_else",
            "args": {
              "condition": {
                "op": "equals",
                "args": {
                  "a": {
                    "op": "get_var",
                    "args": {
                      "name": "scene"
                    }
                  },
                  "b": 2
                }
              }
            },
            "then": [
              {
                "op": "switch_backdrop",
                "args": {
                  "backdrop": "moon"
                }
              },
              {
                "op": "set_var",
                "args": {
                  "name": "score",
                  "value": 0
                }
              },
              {
                "op": "set_var",
                "args": {
                  "name": "lives",
                  "value": 3
                }
              },
              {
                "op": "repeat_until",
                "args": {
                  "condition": {
                    "op": "not",
                    "args": {
                      "a": {
                        "op": "equals",
                        "args": {
                          "a": {
                            "op": "get_var",
                            "args": {
                              "name": "scene"
                            }
                          },
                          "b": 2
                        }
                      }
                    }
                  }
                },
                "body": [
                  {
                    "op": "wait",
                    "args": {
                      "seconds": 1
                    }
                  },
                  {
                    "op": "change_var",
                    "args": {
                      "name": "score",
                      "delta": 1
                    }
                  }
                ]
              }
            ],
            "else": [
              {
                "op": "switch_backdrop",
                "args": {
                  "backdrop": "stars"
                }
              }
            ]
          }
        ]
      }
    ]
  }
]
```

Entering scene 2 resets `score` and `lives`, so "play again" from the game
over screen is a clean restart. The play-time score counter stops as soon as
the scene changes.

## Pattern: a button that changes the scene

```python
@on_receive("scene_changed", target="PlayButton", label="button_scene")
def button_scene():
    if scene == 1 or scene == 3:
        goto_xy(0, -80)
        go_to_front()
        show()
    else:
        hide()


@on_click(target="PlayButton", label="button_click")
def button_click():
    if scene == 1 or scene == 3:
        scene = 2
        broadcast("scene_changed")
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
[
  {
    "action": "add_script",
    "target": "PlayButton",
    "label": "button_scene",
    "hat": {
      "op": "when_receive",
      "args": {
        "message": "scene_changed"
      }
    },
    "body": [
      {
        "op": "if_else",
        "args": {
          "condition": {
            "op": "or",
            "args": {
              "a": {
                "op": "equals",
                "args": {
                  "a": {
                    "op": "get_var",
                    "args": {
                      "name": "scene"
                    }
                  },
                  "b": 1
                }
              },
              "b": {
                "op": "equals",
                "args": {
                  "a": {
                    "op": "get_var",
                    "args": {
                      "name": "scene"
                    }
                  },
                  "b": 3
                }
              }
            }
          }
        },
        "then": [
          {
            "op": "goto_xy",
            "args": {
              "x": 0,
              "y": -80
            }
          },
          {
            "op": "go_to_front"
          },
          {
            "op": "show"
          }
        ],
        "else": [
          {
            "op": "hide"
          }
        ]
      }
    ]
  },
  {
    "action": "add_script",
    "target": "PlayButton",
    "label": "button_click",
    "hat": {
      "op": "when_clicked"
    },
    "body": [
      {
        "op": "if",
        "args": {
          "condition": {
            "op": "or",
            "args": {
              "a": {
                "op": "equals",
                "args": {
                  "a": {
                    "op": "get_var",
                    "args": {
                      "name": "scene"
                    }
                  },
                  "b": 1
                }
              },
              "b": {
                "op": "equals",
                "args": {
                  "a": {
                    "op": "get_var",
                    "args": {
                      "name": "scene"
                    }
                  },
                  "b": 3
                }
              }
            }
          }
        },
        "body": [
          {
            "op": "set_var",
            "args": {
              "name": "scene",
              "value": 2
            }
          },
          {
            "op": "broadcast",
            "args": {
              "message": "scene_changed"
            }
          }
        ]
      }
    ]
  }
]
```

`UI/button.gif`, `UI/button1.png` or the `UI/button2-a.png` family make good
button costumes. The library has no text art, so put the words on a sprite
with `say` (next pattern) or into the backdrop choice.

## Pattern: text for a screen

```python
@on_receive("scene_changed", target="Message", label="message_scene")
def message_scene():
    goto_xy(0, 40)
    if scene == 1:
        show()
        say("Dodge the falling rocks! Click the button to play.")
    elif scene == 3:
        show()
        say(join("Game over! Score: ", score))
    else:
        say("")
        hide()
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
{
  "action": "add_script",
  "target": "Message",
  "label": "message_scene",
  "hat": {
    "op": "when_receive",
    "args": {
      "message": "scene_changed"
    }
  },
  "body": [
    {
      "op": "goto_xy",
      "args": {
        "x": 0,
        "y": 40
      }
    },
    {
      "op": "if_else",
      "args": {
        "condition": {
          "op": "equals",
          "args": {
            "a": {
              "op": "get_var",
              "args": {
                "name": "scene"
              }
            },
            "b": 1
          }
        }
      },
      "then": [
        {
          "op": "show"
        },
        {
          "op": "say",
          "args": {
            "text": "Dodge the falling rocks! Click the button to play."
          }
        }
      ],
      "else": [
        {
          "op": "if_else",
          "args": {
            "condition": {
              "op": "equals",
              "args": {
                "a": {
                  "op": "get_var",
                  "args": {
                    "name": "scene"
                  }
                },
                "b": 3
              }
            }
          },
          "then": [
            {
              "op": "show"
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
          ],
          "else": [
            {
              "op": "say",
              "args": {
                "text": ""
              }
            },
            {
              "op": "hide"
            }
          ]
        }
      ]
    }
  ]
}
```

`say` with `""` clears the bubble before hiding, so it never reappears stale.

## Pattern: a sprite that only plays in one scene

```python
@on_receive("scene_changed", target="Player", label="player_scene")
def player_scene():
    if scene == 2:
        goto_xy(0, -130)
        point_in_direction(90)
        clear_effects()
        show()
        while scene == 2:
            if key_pressed("left arrow"):
                change_x(-6)
            if key_pressed("right arrow"):
                change_x(6)
            wait(0.03)
    else:
        hide()


@on_receive("scene_changed", target="Rock", label="rock_scene")
def rock_scene():
    if scene == 2:
        goto_xy(random(-200, 200), 170)
        show()
        while scene == 2:
            change_y(-6)
            if touching("Player"):
                lives -= 1
                goto_xy(random(-200, 200), 170)
                if lives < 1:
                    scene = 3
                    broadcast("scene_changed")
            if y_position() < -170:
                goto_xy(random(-200, 200), 170)
            wait(0.03)
    else:
        hide()
```
<!-- generated from the python example above by tools/render_pack_json.py; edit the python, not this -->
```json
[
  {
    "action": "add_script",
    "target": "Player",
    "label": "player_scene",
    "hat": {
      "op": "when_receive",
      "args": {
        "message": "scene_changed"
      }
    },
    "body": [
      {
        "op": "if_else",
        "args": {
          "condition": {
            "op": "equals",
            "args": {
              "a": {
                "op": "get_var",
                "args": {
                  "name": "scene"
                }
              },
              "b": 2
            }
          }
        },
        "then": [
          {
            "op": "goto_xy",
            "args": {
              "x": 0,
              "y": -130
            }
          },
          {
            "op": "point_in_direction",
            "args": {
              "degrees": 90
            }
          },
          {
            "op": "clear_effects"
          },
          {
            "op": "show"
          },
          {
            "op": "repeat_until",
            "args": {
              "condition": {
                "op": "not",
                "args": {
                  "a": {
                    "op": "equals",
                    "args": {
                      "a": {
                        "op": "get_var",
                        "args": {
                          "name": "scene"
                        }
                      },
                      "b": 2
                    }
                  }
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
                      "key": "left arrow"
                    }
                  }
                },
                "body": [
                  {
                    "op": "change_x",
                    "args": {
                      "dx": -6
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
                      "key": "right arrow"
                    }
                  }
                },
                "body": [
                  {
                    "op": "change_x",
                    "args": {
                      "dx": 6
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
        ],
        "else": [
          {
            "op": "hide"
          }
        ]
      }
    ]
  },
  {
    "action": "add_script",
    "target": "Rock",
    "label": "rock_scene",
    "hat": {
      "op": "when_receive",
      "args": {
        "message": "scene_changed"
      }
    },
    "body": [
      {
        "op": "if_else",
        "args": {
          "condition": {
            "op": "equals",
            "args": {
              "a": {
                "op": "get_var",
                "args": {
                  "name": "scene"
                }
              },
              "b": 2
            }
          }
        },
        "then": [
          {
            "op": "goto_xy",
            "args": {
              "x": {
                "op": "random",
                "args": {
                  "from": -200,
                  "to": 200
                }
              },
              "y": 170
            }
          },
          {
            "op": "show"
          },
          {
            "op": "repeat_until",
            "args": {
              "condition": {
                "op": "not",
                "args": {
                  "a": {
                    "op": "equals",
                    "args": {
                      "a": {
                        "op": "get_var",
                        "args": {
                          "name": "scene"
                        }
                      },
                      "b": 2
                    }
                  }
                }
              }
            },
            "body": [
              {
                "op": "change_y",
                "args": {
                  "dy": -6
                }
              },
              {
                "op": "if",
                "args": {
                  "condition": {
                    "op": "touching",
                    "args": {
                      "target": "Player"
                    }
                  }
                },
                "body": [
                  {
                    "op": "change_var",
                    "args": {
                      "name": "lives",
                      "delta": -1
                    }
                  },
                  {
                    "op": "goto_xy",
                    "args": {
                      "x": {
                        "op": "random",
                        "args": {
                          "from": -200,
                          "to": 200
                        }
                      },
                      "y": 170
                    }
                  },
                  {
                    "op": "if",
                    "args": {
                      "condition": {
                        "op": "less_than",
                        "args": {
                          "a": {
                            "op": "get_var",
                            "args": {
                              "name": "lives"
                            }
                          },
                          "b": 1
                        }
                      }
                    },
                    "body": [
                      {
                        "op": "set_var",
                        "args": {
                          "name": "scene",
                          "value": 3
                        }
                      },
                      {
                        "op": "broadcast",
                        "args": {
                          "message": "scene_changed"
                        }
                      }
                    ]
                  }
                ]
              },
              {
                "op": "if",
                "args": {
                  "condition": {
                    "op": "less_than",
                    "args": {
                      "a": {
                        "op": "y_position"
                      },
                      "b": -170
                    }
                  }
                },
                "body": [
                  {
                    "op": "goto_xy",
                    "args": {
                      "x": {
                        "op": "random",
                        "args": {
                          "from": -200,
                          "to": 200
                        }
                      },
                      "y": 170
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
        ],
        "else": [
          {
            "op": "hide"
          }
        ]
      }
    ]
  }
]
```

Exactly one place (the Rock's collision) moves the game to scene 3, so the
game over transition cannot fire twice.

## Rules that prevent bugs

- **Every sprite needs a scene handler.** A sprite without one shows on every
  screen. When a revision adds a sprite to a scene project, add its
  `scene_changed` handler in the same module.
- **Set, then broadcast.** set `scene` to 3, then
  `broadcast` `scene_changed`; never the broadcast first.
- **One owner per transition.** Let one script decide each change (the button
  for 1 -> 2, the collision for 2 -> 3). Several scripts racing to change
  `scene` cause double transitions.
- **Clones and scenes.** Clones receive `scene_changed` too, and
  `delete_clone` does nothing in the original, so a clone template can do
  `delete_clone` when `scene` is not 2 at the top of its handler (load the
  `clones` pack for the template rules). Spawn clones from the original's
  scene branch with an `is_clone` guard, never from a handler every clone
  runs unguarded.
- **Variable monitors** belong to a screen too: `show_variable` `score` in the
  play branch, `hide_variable` elsewhere.
- **Levels vs scenes.** Levels that keep the same sprites and rules are a
  `level` variable inside the play scene; a new scene is for a different
  screen (title, shop, boss room, ending).
- Add each scene's backdrop at module level once
  (`set_backdrop` `Space/moon.jpg` with `select` false) and switch to it only
  from the Stage router.

## Testing a scene project

- Green flag shows only the title screen's sprites, with no stale speech
  bubbles or pen trails.
- Every button and transition shows exactly the next screen's sprites.
- Game over -> play again behaves exactly like the first play (score, lives,
  positions reset on entry).
- A second green flag in the middle of play returns cleanly to the title.
