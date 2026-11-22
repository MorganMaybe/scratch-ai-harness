from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

KEY_NAMES: tuple[str, ...] = (
    "any",
    "space",
    "up arrow",
    "down arrow",
    "right arrow",
    "left arrow",
    *tuple("abcdefghijklmnopqrstuvwxyz"),
    *tuple("0123456789"),
)

GRAPHIC_EFFECTS: tuple[str, ...] = (
    "color",
    "fisheye",
    "whirl",
    "pixelate",
    "mosaic",
    "brightness",
    "ghost",
)

ATTRIBUTE_NAMES: tuple[str, ...] = (
    "x position",
    "y position",
    "direction",
    "costume #",
    "costume name",
    "size",
    "volume",
    "background #",
    "backdrop name",
)

TARGET_MENU: tuple[str, ...] = ("mouse-pointer", "edge")

CURRENT_PARTS: tuple[str, ...] = (
    "year",
    "month",
    "date",
    "day of week",
    "hour",
    "minute",
    "second",
)

ROTATION_STYLES: tuple[str, ...] = (
    "all around",
    "left-right",
    "don't rotate",
)

MATH_FUNCTIONS: tuple[str, ...] = (
    "abs",
    "sqrt",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "ln",
    "log",
    "e ^",
    "10 ^",
)

LIST_INDEX_VALUES: tuple[str, ...] = ("last", "all")

#: Bridge-side color literal.  The image converts it to a real ``Color``.
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

#: Blocks whose target menu also accepts a sprite name from the live project.
SPRITE_TARGET_OPS: frozenset[str] = frozenset(
    {
        "point_towards",
        "goto_sprite",
        "touching",
        "distance_to",
        "attribute_of",
        "set_attribute_of",
        "change_attribute_of",
        "create_clone",
    }
)

INSTRUMENTS: tuple[str, ...] = (
    "1 (Acoustic Grand Piano)",
    "2 (Bright Acoustic Piano)",
    "3 (Electric Grand Piano)",
    "4 (Honky-tonk Piano)",
    "5 (Electric Piano 1)",
    "6 (Electric Piano 2)",
    "7 (Harpsichord)",
    "8 (Clavinet)",
    "9 (Celesta)",
    "10 (Glockenspiel)",
    "11 (Music Box)",
    "12 (Vibraphone)",
    "13 (Marimba)",
    "14 (Xylophone)",
    "15 (Tubular Bells)",
    "16 (Dulcimer)",
    "17 (Drawbar Organ)",
    "18 (Percussive Organ)",
    "19 (Rock Organ)",
    "20 (Church Organ)",
    "21 (Reed Organ)",
    "22 (Accordion)",
    "23 (Harmonica)",
    "24 (Tango Accordion)",
    "25 (Acoustic Guitar 1)",
    "26 (Acoustic Guitar 2)",
    "27 (Electric Guitar 1)",
    "28 (Electric Guitar 2)",
    "29 (Electric Guitar 3)",
    "30 (Overdriven Guitar)",
    "31 (Distortion Guitar)",
    "32 (Guitar Harmonics)",
    "33 (Acoustic Bass)",
    "34 (Electric Bass 1)",
    "35 (Electric Bass 2)",
    "36 (Violin)",
    "37 (Viola)",
    "38 (Cello)",
    "39 (Contrabass)",
    "40 (Tremolo Strings)",
    "41 (Pizzicato Strings)",
    "42 (Orchestral Harp)",
    "43 (Timpani)",
    "44 (String Ensemble 1)",
    "45 (String Ensemble 2)",
    "46 (Synth Strings 1)",
    "47 (Synth Strings 2)",
    "48 (Choir Aahs)",
    "49 (Voice Oohs)",
    "50 (Synth Voice)",
    "51 (Orchestra Hit)",
    "52 (Trumpet)",
    "53 (Trombone)",
    "54 (Tuba)",
    "55 (Muted Trumpet)",
    "56 (French Horn)",
    "57 (Brass Section)",
    "58 (Synth Brass 1)",
    "59 (Synth Brass 2)",
    "60 (Soprano Sax)",
    "61 (Alto Sax)",
    "62 (Tenor Sax)",
    "63 (Baritone Sax)",
    "64 (Oboe)",
    "65 (English Horn)",
    "66 (Bassoon)",
    "67 (Clarinet)",
    "68 (Piccolo)",
    "69 (Flute)",
    "70 (Recorder)",
    "71 (Pan Flute)",
    "72 (Blown Bottle)",
    "73 (Shakuhachi)",
    "74 (Whistle)",
    "75 (Ocarina)",
    "76 (Lead 1 - Square)",
    "77 (Lead 2 - Sawtooth)",
    "78 (Lead 3 - Calliope)",
    "79 (Lead 4 - Chiff)",
    "80 (Lead 5 - Charang)",
    "81 (Lead 6 - Voice)",
    "82 (Lead 7 - Fifths)",
    "83 (Lead 8 - Bass + Lead)",
    "84 (Pad 1 - New Age)",
    "85 (Pad 2 - Warm)",
    "86 (Pad 3 - Polysynth)",
    "87 (Pad 4 - Choir)",
    "88 (Pad 5 - Bowed)",
    "89 (Pad 6 - Metallic)",
    "90 (Pad 7 - Halo)",
    "91 (Pad 8 - Sweep)",
    "92 (FX 1 - Rain)",
    "93 (FX 2 - Soundtrack)",
    "94 (FX 3 - Crystal)",
    "95 (FX 4 - Atmosphere)",
    "96 (FX 5 - Brightness)",
    "97 (FX 6 - Goblins)",
    "98 (FX 7 - Echoes)",
    "99 (FX 8 - Sci-Fi)",
    "100 (Sitar)",
    "101 (Banjo)",
    "102 (Shamisen)",
    "103 (Koto)",
    "104 (Kalimba)",
    "105 (Bagpipe)",
    "106 (Fiddle)",
    "107 (Shanai)",
    "108 (Tinkle Bell)",
    "109 (Agogo)",
    "110 (Steel Drums)",
    "111 (Woodblock)",
    "112 (Taiko Drum)",
    "113 (Melodic Tom)",
    "114 (Synth Drum)",
    "115 (Reverse Cymbal)",
    "116 (Guitar Fret Noise)",
    "117 (Breath Noise)",
    "118 (Seashore)",
    "119 (Bird Tweet)",
    "120 (Telephone Ring)",
    "121 (Helicopter)",
    "122 (Applause)",
    "123 (Gunshot)",
)

DRUM_NAMES: tuple[str, ...] = (
    "1 (Snare Drum)",
    "2 (Bass Drum)",
    "3 (Side Stick)",
    "4 (Crash Cymbal)",
    "5 (Open Hi-Hat)",
    "6 (Closed Hi-Hat)",
    "7 (Tambourine)",
    "8 (Hand Clap)",
    "9 (Claves)",
    "10 (Wood Block)",
    "11 (Cowbell)",
    "12 (Triangle)",
    "13 (Bongo)",
    "14 (Conga)",
    "15 (Cabasa)",
    "16 (Guiro)",
    "17 (Vibraslap)",
    "18 (Cuica)",
)


@dataclass(frozen=True)
class ArgSpec:
    name: str
    type: str  # number | string | any | reporter | boolean | menu
    menu: tuple[str, ...] = ()
    required: bool = True


@dataclass(frozen=True)
class BlockSpec:
    op: str
    selector: str
    category: str
    kind: str  # hat | command | reporter | boolean | cblock | ifelse
    args: tuple[ArgSpec, ...] = ()
    body: str = "none"  # none | body | then_else
    targets: tuple[str, ...] = ("sprite", "stage")
    label: str = ""
    enabled: bool = True


def _cmd(op: str, selector: str, category: str, *args: ArgSpec, targets=("sprite", "stage"), label="") -> BlockSpec:
    return BlockSpec(op, selector, category, "command", args, "none", targets, label)


def _rep(op: str, selector: str, category: str, *args: ArgSpec, targets=("sprite", "stage"), label="") -> BlockSpec:
    return BlockSpec(op, selector, category, "reporter", args, "none", targets, label)


def _bool(op: str, selector: str, category: str, *args: ArgSpec, targets=("sprite", "stage"), label="") -> BlockSpec:
    return BlockSpec(op, selector, category, "boolean", args, "none", targets, label)


def _hat(op: str, selector: str, category: str, *args: ArgSpec, targets=("sprite", "stage"), label="") -> BlockSpec:
    return BlockSpec(op, selector, category, "hat", args, "none", targets, label)


SPECS: tuple[BlockSpec, ...] = (
    # Events
    _hat("when_flag_clicked", "EventHatMorph", "events", label="when green flag clicked"),
    _hat("when_key_pressed", "KeyEventHatMorph", "events", ArgSpec("key", "menu", KEY_NAMES), label="when key pressed"),
    _hat("when_clicked", "MouseClickEventHatMorph", "events", targets=("sprite",), label="when sprite clicked"),
    _hat("when_clone_start", "whenCloneStart", "events", targets=("sprite",), label="when I start as a clone"),
    _hat("when_receive", "EventHatMorph", "events", ArgSpec("message", "string"), label="when I receive"),
    _hat("when_stage_clicked", "whenStageClicked", "events", targets=("stage",), label="when stage clicked"),
    _hat(
        "when_backdrop_switches",
        "whenBackdropSwitches:",
        "events",
        ArgSpec("backdrop", "string"),
        targets=("stage",),
        label="when backdrop switches",
    ),
    _hat(
        "when_loudness_greater",
        "whenLoudnessGreater:",
        "events",
        ArgSpec("value", "number"),
        label="when loudness >",
    ),
    _hat(
        "when_timer_greater",
        "whenTimerGreater:",
        "events",
        ArgSpec("value", "number"),
        label="when timer >",
    ),
    # Control
    _cmd("wait", "wait:elapsed:from:", "control", ArgSpec("seconds", "number"), label="wait"),
    BlockSpec("repeat", "doRepeat", "control", "cblock", (ArgSpec("count", "number"),), "body", label="repeat"),
    BlockSpec("forever", "doForever", "control", "cblock", (), "body", label="forever"),
    BlockSpec("if", "doIf", "control", "cblock", (ArgSpec("condition", "boolean"),), "body", label="if"),
    BlockSpec("if_else", "doIfElse", "control", "ifelse", (ArgSpec("condition", "boolean"),), "then_else", label="if else"),
    _cmd("wait_until", "doWaitUntil", "control", ArgSpec("condition", "boolean"), label="wait until"),
    BlockSpec("repeat_until", "doUntil", "control", "cblock", (ArgSpec("condition", "boolean"),), "body", label="repeat until"),
    BlockSpec("forever_if", "doForeverIf", "control", "cblock", (ArgSpec("condition", "boolean"),), "body", label="forever if"),
    _cmd("broadcast", "broadcast:", "control", ArgSpec("message", "string"), label="broadcast"),
    _cmd("broadcast_and_wait", "doBroadcastAndWait", "control", ArgSpec("message", "string"), label="broadcast and wait"),
    _cmd("stop_script", "doReturn", "control", label="stop script"),
    _cmd("stop_all", "stopAll", "control", label="stop all"),
    _cmd("stop_other_scripts", "stopOtherScripts", "control", targets=("sprite",), label="stop other scripts in sprite"),
    _cmd(
        "create_clone",
        "createCloneOf:",
        "control",
        ArgSpec("target", "clone_target"),
        targets=("sprite",),
        label="create clone of",
    ),
    _cmd("delete_clone", "deleteThisClone", "control", targets=("sprite",), label="delete this clone"),
    # Motion
    _cmd("move", "forward:", "motion", ArgSpec("steps", "number"), targets=("sprite",), label="move steps"),
    _cmd("turn_right", "turnRight:", "motion", ArgSpec("degrees", "number"), targets=("sprite",), label="turn right"),
    _cmd("turn_left", "turnLeft:", "motion", ArgSpec("degrees", "number"), targets=("sprite",), label="turn left"),
    _cmd("point_in_direction", "heading:", "motion", ArgSpec("degrees", "number"), targets=("sprite",), label="point in direction"),
    _cmd("point_towards", "pointTowards:", "motion", ArgSpec("target", "menu", TARGET_MENU + ("Stage",)), targets=("sprite",), label="point towards"),
    _cmd("goto_xy", "gotoX:y:", "motion", ArgSpec("x", "number"), ArgSpec("y", "number"), targets=("sprite",), label="go to x y"),
    _cmd("goto_sprite", "gotoSpriteOrMouse:", "motion", ArgSpec("target", "menu", TARGET_MENU), targets=("sprite",), label="go to"),
    _cmd("glide", "glideSecs:toX:y:elapsed:from:", "motion", ArgSpec("seconds", "number"), ArgSpec("x", "number"), ArgSpec("y", "number"), targets=("sprite",), label="glide"),
    _cmd("change_x", "changeXposBy:", "motion", ArgSpec("dx", "number"), targets=("sprite",), label="change x by"),
    _cmd("set_x", "xpos:", "motion", ArgSpec("x", "number"), targets=("sprite",), label="set x to"),
    _cmd("change_y", "changeYposBy:", "motion", ArgSpec("dy", "number"), targets=("sprite",), label="change y by"),
    _cmd("set_y", "ypos:", "motion", ArgSpec("y", "number"), targets=("sprite",), label="set y to"),
    _cmd("bounce", "bounceOffEdge", "motion", targets=("sprite",), label="if on edge bounce"),
    _rep("x_position", "xpos", "motion", targets=("sprite",), label="x position"),
    _rep("y_position", "ypos", "motion", targets=("sprite",), label="y position"),
    _rep("direction", "heading", "motion", targets=("sprite",), label="direction"),
    _cmd(
        "set_rotation_style",
        "setRotationStyle:",
        "motion",
        ArgSpec("style", "menu", ROTATION_STYLES),
        targets=("sprite",),
        label="set rotation style",
    ),
    # Pen (the Stage has no pen palette; these are sprite-only)
    _cmd("pen_clear", "clearPenTrails", "pen", label="clear"),
    _cmd("pen_down", "putPenDown", "pen", targets=("sprite",), label="pen down"),
    _cmd("pen_up", "putPenUp", "pen", targets=("sprite",), label="pen up"),
    _cmd("set_pen_color", "penColor:", "pen", ArgSpec("color", "color"), targets=("sprite",), label="set pen color to RGB"),
    _cmd("set_pen_hue", "setPenHueTo:", "pen", ArgSpec("hue", "number"), targets=("sprite",), label="set pen color to number"),
    _cmd("change_pen_hue", "changePenHueBy:", "pen", ArgSpec("delta", "number"), targets=("sprite",), label="change pen color by"),
    _cmd("set_pen_shade", "setPenShadeTo:", "pen", ArgSpec("shade", "number"), targets=("sprite",), label="set pen shade to"),
    _cmd("change_pen_shade", "changePenShadeBy:", "pen", ArgSpec("delta", "number"), targets=("sprite",), label="change pen shade by"),
    _cmd("set_pen_size", "penSize:", "pen", ArgSpec("size", "number"), targets=("sprite",), label="set pen size to"),
    _cmd("change_pen_size", "changePenSizeBy:", "pen", ArgSpec("delta", "number"), targets=("sprite",), label="change pen size by"),
    _cmd("stamp", "stampCostume", "pen", targets=("sprite",), label="stamp"),
    # Looks
    _cmd("switch_costume", "lookLike:", "looks", ArgSpec("costume", "string"), targets=("sprite",), label="switch to costume"),
    _cmd("switch_backdrop", "showBackground:", "looks", ArgSpec("backdrop", "string"), targets=("stage",), label="switch backdrop to"),
    _cmd("next_backdrop", "nextBackground", "looks", targets=("stage",), label="next backdrop"),
    _rep("backdrop_number", "backgroundIndex", "looks", targets=("stage",), label="backdrop number"),
    _cmd("next_costume", "nextCostume", "looks", targets=("sprite",), label="next costume"),
    _rep("costume_number", "costumeIndex", "looks", targets=("sprite",), label="costume number"),
    _rep("costume_name", "costumeName", "looks", targets=("sprite",), label="costume name"),
    _rep("backdrop_name", "backgroundName", "looks", targets=("stage",), label="backdrop name"),
    _cmd("say", "say:", "looks", ArgSpec("text", "any"), targets=("sprite",), label="say"),
    _cmd("say_for", "say:duration:elapsed:from:", "looks", ArgSpec("text", "any"), ArgSpec("seconds", "number"), targets=("sprite",), label="say for"),
    _cmd("think", "think:", "looks", ArgSpec("text", "any"), targets=("sprite",), label="think"),
    _cmd("think_for", "think:duration:elapsed:from:", "looks", ArgSpec("text", "any"), ArgSpec("seconds", "number"), targets=("sprite",), label="think for"),
    _cmd("change_effect", "changeGraphicEffect:by:", "looks", ArgSpec("effect", "menu", GRAPHIC_EFFECTS), ArgSpec("delta", "number"), targets=("sprite",), label="change effect by"),
    _cmd("set_effect", "setGraphicEffect:to:", "looks", ArgSpec("effect", "menu", GRAPHIC_EFFECTS), ArgSpec("value", "number"), targets=("sprite",), label="set effect to"),
    _cmd("clear_effects", "filterReset", "looks", targets=("sprite",), label="clear graphic effects"),
    _cmd("change_size", "changeSizeBy:", "looks", ArgSpec("delta", "number"), targets=("sprite",), label="change size by"),
    _cmd("set_size", "setSizeTo:", "looks", ArgSpec("percent", "number"), targets=("sprite",), label="set size to"),
    _rep("size", "scale", "looks", targets=("sprite",), label="size"),
    _cmd("show", "show", "looks", targets=("sprite",), label="show"),
    _cmd("hide", "hide", "looks", targets=("sprite",), label="hide"),
    _cmd("go_to_front", "comeToFront", "looks", targets=("sprite",), label="go to front"),
    _cmd("go_to_back", "goToBack", "looks", targets=("sprite",), label="go to back"),
    _cmd("go_back_layers", "goBackByLayers:", "looks", ArgSpec("layers", "number"), targets=("sprite",), label="go back layers"),
    _cmd("go_forward_layers", "goForwardByLayers:", "looks", ArgSpec("layers", "number"), targets=("sprite",), label="go forward layers"),
    # Sound
    _cmd("play_sound", "playSound:", "sound", ArgSpec("sound", "string"), label="play sound"),
    _cmd("play_sound_until_done", "doPlaySoundAndWait", "sound", ArgSpec("sound", "string"), label="play sound until done"),
    _cmd("stop_all_sounds", "stopAllSounds", "sound", label="stop all sounds"),
    _cmd("play_drum", "drum:duration:elapsed:from:", "sound", ArgSpec("drum", "menu", DRUM_NAMES), ArgSpec("beats", "number"), label="play drum"),
    _cmd("rest", "rest:elapsed:from:", "sound", ArgSpec("beats", "number"), label="rest"),
    _cmd("play_note", "noteOn:duration:elapsed:from:", "sound", ArgSpec("note", "number"), ArgSpec("beats", "number"), label="play note"),
    _cmd("set_instrument", "midiInstrument:", "sound", ArgSpec("instrument", "menu", INSTRUMENTS), label="set instrument"),
    _cmd("change_volume", "changeVolumeBy:", "sound", ArgSpec("delta", "number"), label="change volume by"),
    _cmd("set_volume", "setVolumeTo:", "sound", ArgSpec("percent", "number"), label="set volume to"),
    _rep("volume", "volume", "sound", label="volume"),
    _cmd("change_tempo", "changeTempoBy:", "sound", ArgSpec("delta", "number"), label="change tempo by"),
    _cmd("set_tempo", "setTempoTo:", "sound", ArgSpec("bpm", "number"), label="set tempo to"),
    _rep("tempo", "tempo", "sound", label="tempo"),
    # Sensing
    _cmd("ask", "doAsk", "sensing", ArgSpec("question", "string"), label="ask and wait"),
    _rep("answer", "answer", "sensing", label="answer"),
    _rep("mouse_x", "mouseX", "sensing", label="mouse x"),
    _rep("mouse_y", "mouseY", "sensing", label="mouse y"),
    _bool("mouse_down", "mousePressed", "sensing", label="mouse down"),
    _bool("key_pressed", "keyPressed:", "sensing", ArgSpec("key", "menu", KEY_NAMES), label="key pressed"),
    _bool("touching", "touching:", "sensing", ArgSpec("target", "menu", TARGET_MENU), targets=("sprite",), label="touching"),
    _bool("touching_color", "touchingColor:", "sensing", ArgSpec("color", "color"), targets=("sprite",), label="touching color"),
    _bool("color_sees", "color:sees:", "sensing", ArgSpec("color", "color"), ArgSpec("color2", "color"), targets=("sprite",), label="color is touching color"),
    _rep("distance_to", "distanceTo:", "sensing", ArgSpec("target", "menu", TARGET_MENU), targets=("sprite",), label="distance to"),
    _cmd("reset_timer", "timerReset", "sensing", label="reset timer"),
    _rep("timer", "timer", "sensing", label="timer"),
    _rep("attribute_of", "getAttribute:of:", "sensing", ArgSpec("attribute", "menu", ATTRIBUTE_NAMES), ArgSpec("target", "menu", TARGET_MENU + ("Stage",)), label="attribute of"),
    _cmd(
        "set_attribute_of",
        "setAttribute:of:to:",
        "sensing",
        ArgSpec("attribute", "menu", ATTRIBUTE_NAMES),
        ArgSpec("target", "menu", ("Stage",)),
        ArgSpec("value", "any"),
        label="set attribute of",
    ),
    _cmd(
        "change_attribute_of",
        "changeAttribute:of:by:",
        "sensing",
        ArgSpec("attribute", "menu", ATTRIBUTE_NAMES),
        ArgSpec("target", "menu", ("Stage",)),
        ArgSpec("delta", "number"),
        label="change attribute of",
    ),
    _rep("current", "current:", "sensing", ArgSpec("part", "menu", CURRENT_PARTS), label="current"),
    _rep("days_since_2000", "daysSince2000", "sensing", label="days since 2000"),
    _rep("username", "username", "sensing", label="username"),
    _rep("loudness", "soundLevel", "sensing", label="loudness"),
    _bool("loud", "isLoud", "sensing", label="loud"),
    # Operators
    _rep("add", "+", "operators", ArgSpec("a", "any"), ArgSpec("b", "any"), label="add"),
    _rep("subtract", "-", "operators", ArgSpec("a", "any"), ArgSpec("b", "any"), label="subtract"),
    _rep("multiply", "*", "operators", ArgSpec("a", "any"), ArgSpec("b", "any"), label="multiply"),
    _rep("divide", "/", "operators", ArgSpec("a", "any"), ArgSpec("b", "any"), label="divide"),
    _rep("mod", "\\\\", "operators", ArgSpec("a", "any"), ArgSpec("b", "any"), label="mod"),
    _rep("round", "rounded", "operators", ArgSpec("n", "any"), label="round"),
    _rep("abs", "abs", "operators", ArgSpec("n", "any"), label="abs"),
    _rep("sqrt", "computeFunction:of:", "operators", ArgSpec("n", "any"), label="sqrt"),
    _rep("math_function", "computeFunction:of:", "operators", ArgSpec("function", "menu", MATH_FUNCTIONS), ArgSpec("n", "any"), label="math function"),
    _rep("random", "randomFrom:to:", "operators", ArgSpec("from", "number"), ArgSpec("to", "number"), label="pick random"),
    _bool("less_than", "<", "operators", ArgSpec("a", "any"), ArgSpec("b", "any"), label="less than"),
    _bool("equals", "=", "operators", ArgSpec("a", "any"), ArgSpec("b", "any"), label="equals"),
    _bool("greater_than", ">", "operators", ArgSpec("a", "any"), ArgSpec("b", "any"), label="greater than"),
    _bool("and", "&", "operators", ArgSpec("a", "boolean"), ArgSpec("b", "boolean"), label="and"),
    _bool("or", "|", "operators", ArgSpec("a", "boolean"), ArgSpec("b", "boolean"), label="or"),
    _bool("not", "not", "operators", ArgSpec("a", "boolean"), label="not"),
    _rep("join", "concatenate:with:", "operators", ArgSpec("a", "any"), ArgSpec("b", "any"), label="join"),
    _rep("letter_of", "letter:of:", "operators", ArgSpec("index", "number"), ArgSpec("string", "any"), label="letter of"),
    _rep("string_length", "stringLength:", "operators", ArgSpec("string", "any"), label="length of string"),
    # Lists
    _cmd("add_to_list", "append:toList:", "list", ArgSpec("item", "any"), ArgSpec("list", "list"), label="add to list"),
    _cmd("delete_from_list", "deleteLine:ofList:", "list", ArgSpec("index", "list_index"), ArgSpec("list", "list"), label="delete from list"),
    _cmd("insert_in_list", "insert:at:ofList:", "list", ArgSpec("item", "any"), ArgSpec("index", "number"), ArgSpec("list", "list"), label="insert in list"),
    _cmd("replace_in_list", "setLine:ofList:to:", "list", ArgSpec("index", "number"), ArgSpec("list", "list"), ArgSpec("item", "any"), label="replace in list"),
    _rep("list_item", "getLine:ofList:", "list", ArgSpec("index", "number"), ArgSpec("list", "list"), label="item of list"),
    _rep("list_length", "lineCountOfList:", "list", ArgSpec("list", "list"), label="length of list"),
    _bool("list_contains", "list:contains:", "list", ArgSpec("list", "list"), ArgSpec("item", "any"), label="list contains"),
    _rep("list_item_number", "itemNumOf:inList:", "list", ArgSpec("item", "any"), ArgSpec("list", "list"), label="item number in list"),
    _cmd("show_list", "showList:", "list", ArgSpec("list", "list"), label="show list"),
    _cmd("hide_list", "hideList:", "list", ArgSpec("list", "list"), label="hide list"),
    # Variables (custom tuple builders)
    BlockSpec("set_var", "changeVariable", "variables", "command", (ArgSpec("name", "string"), ArgSpec("value", "any")), label="set variable"),
    BlockSpec("change_var", "changeVariable", "variables", "command", (ArgSpec("name", "string"), ArgSpec("delta", "number")), label="change variable"),
    BlockSpec("get_var", "readVariable", "variables", "reporter", (ArgSpec("name", "string"),), label="variable"),
    _cmd("show_variable", "showVariable:", "variables", ArgSpec("name", "string"), label="show variable"),
    _cmd("hide_variable", "hideVariable:", "variables", ArgSpec("name", "string"), label="hide variable"),
)

SPEC_BY_OP: dict[str, BlockSpec] = {spec.op: spec for spec in SPECS}

CATEGORY_ORDER: tuple[str, ...] = (
    "events",
    "control",
    "motion",
    "looks",
    "pen",
    "sound",
    "sensing",
    "operators",
    "list",
    "variables",
)


def spec_for(op: str) -> BlockSpec | None:
    return SPEC_BY_OP.get(op)


def enabled_specs(categories: set[str] | None = None, target: str | None = None) -> list[BlockSpec]:
    result = []
    for spec in SPECS:
        if not spec.enabled:
            continue
        if categories is not None and spec.category not in categories:
            continue
        if target is not None and target not in spec.targets:
            continue
        result.append(spec)
    return result


def _arg_type_text(spec: BlockSpec, arg: ArgSpec) -> str:
    if spec.op == "create_clone" and arg.name == "target":
        return "myself or sprite"
    if spec.op in SPRITE_TARGET_OPS and arg.name == "target":
        return "sprite"
    if arg.type == "color":
        return "#rrggbb"
    if arg.type == "list":
        return "list name"
    if arg.type == "list_index":
        return "1|last|all"
    return arg.type


def catalog_summary(categories: set[str] | None = None, target: str | None = None) -> str:
    """Compact text catalog for an LLM prompt."""
    lines: list[str] = []
    for category in CATEGORY_ORDER:
        specs = [s for s in enabled_specs(categories, target) if s.category == category]
        if not specs:
            continue
        lines.append(f"{category}:")
        for spec in specs:
            args = ", ".join(
                f"{a.name}: {_arg_type_text(spec, a)}" for a in spec.args
            )
            body = ""
            if spec.body == "body":
                body = " { ... }"
            elif spec.body == "then_else":
                body = " { ... } else { ... }"
            lines.append(f"  {spec.op}({args}){body}  # {spec.label}")
    return "\n".join(lines)


def catalog_json_schema() -> dict[str, Any]:
    """A permissive schema; semantic validation is done by the validator."""
    return {
        "type": "object",
        "required": ["summary", "changes"],
        "properties": {
            "summary": {"type": "string"},
            "notes": {"type": "string"},
            "changes": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["action"],
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "add_script",
                                "replace_script",
                                "delete_script",
                                "create_variable",
                                "create_sprite",
                                "delete_sprite",
                                "duplicate_sprite",
                                "add_costume",
                                "set_backdrop",
                                "set_sprite",
                            ],
                        },
                        "script_id": {"type": "string"},
                        "target": {"type": "string"},
                        "label": {"type": "string"},
                        "hat": {"$ref": "#/definitions/block"},
                        "body": {"type": "array", "items": {"$ref": "#/definitions/block"}},
                        "name": {"type": "string"},
                        "scope": {"type": "string", "enum": ["global", "sprite"]},
                        "initial": {},
                        "costumes": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "required": ["library"],
                                "properties": {
                                    "library": {"type": "string"},
                                    "name": {"type": "string"},
                                },
                            },
                        },
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "direction": {"type": "number"},
                        "size": {"type": "number"},
                        "visible": {"type": "boolean"},
                        "rotation_style": {
                            "type": "string",
                            "enum": ["all around", "left-right", "don't rotate"],
                        },
                        "library": {"type": "string"},
                        "preset": {"type": "string"},
                        "select": {"type": "boolean"},
                    },
                },
            },
        },
        "definitions": {
            "block": {
                "type": "object",
                "required": ["op"],
                "properties": {
                    "op": {"type": "string"},
                    "args": {"type": "object"},
                    "body": {"type": "array", "items": {"$ref": "#/definitions/block"}},
                    "then": {"type": "array", "items": {"$ref": "#/definitions/block"}},
                    "else": {"type": "array", "items": {"$ref": "#/definitions/block"}},
                },
            }
        },
    }
