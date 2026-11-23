from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .smalltalk import Sym


@dataclass
class ScriptSummary:
    script_id: str
    target: str
    label: str
    hat: str
    block_count: int
    hash: str = ""
    owned: bool = True
    user_edited: bool = False
    #: Native Scratch tuples for the whole script (hat first), when the image
    #: supplies them. Only AI-owned scripts are normally sent. Used by the
    #: lazy ``load_sprite`` detail blocks, never printed with the summary.
    tuples: list[Any] | None = None


@dataclass
class SpriteContext:
    name: str
    variables: list[str] = field(default_factory=list)
    lists: list[str] = field(default_factory=list)
    costumes: list[str] = field(default_factory=list)
    sounds: list[str] = field(default_factory=list)
    scripts: list[ScriptSummary] = field(default_factory=list)
    is_stage: bool = False
    x: int | float = 0
    y: int | float = 0
    direction: int | float = 90
    size: int | float = 100
    visible: bool = True
    rotation_style: str = "all around"
    ai_owned: bool = False
    costume_index: int = 1


#: Scratch stores rotation style as a symbol; the model sees the menu text.
ROTATION_DISPLAY: dict[str, str] = {
    "normal": "all around",
    "leftRight": "left-right",
    "left-right": "left-right",
    "none": "don't rotate",
    "don't rotate": "don't rotate",
    "all around": "all around",
}


def rotation_display(value: Any) -> str:
    key = _text(value)
    return ROTATION_DISPLAY.get(key, "all around")


@dataclass
class ProjectContext:
    target: str
    sprites: dict[str, SpriteContext] = field(default_factory=dict)
    stage_variables: list[str] = field(default_factory=list)
    stage_lists: list[str] = field(default_factory=list)

    @classmethod
    def demo(cls) -> "ProjectContext":
        return cls(
            target="Sprite1",
            sprites={
                "Sprite1": SpriteContext(
                    name="Sprite1",
                    costumes=["costume1", "costume2"],
                    sounds=["pop"],
                ),
                "Stage": SpriteContext(name="Stage", is_stage=True),
            },
        )

    @classmethod
    def from_literal(cls, value: Any) -> "ProjectContext":
        """Build a context from the image's wire format.

        ``#(target #(sprite...))`` where each sprite is
        ``#(name isStage vars lists costumes sounds scripts)`` and each script is
        ``#(id label hat blockCount hash owned userEdited)``. Newer images append
        an optional eighth element
        ``#(x y direction size visible rotationStyle aiOwned costumeIndex)``;
        seven-element contexts from older images keep working.
        """
        if not isinstance(value, list) or len(value) < 2:
            raise ValueError("context must be #(target sprites)")
        context = cls(target=_text(value[0]))
        sprites = value[1]
        if not isinstance(sprites, list):
            raise ValueError("context sprites must be an array")
        for raw in sprites:
            if not isinstance(raw, list) or len(raw) < 7:
                raise ValueError(
                    "sprite entry must be #(name isStage vars lists costumes sounds scripts)"
                )
            name = _text(raw[0])
            is_stage = raw[1] is True
            variables = [_text(v) for v in _items(raw[2])]
            lists = [_text(v) for v in _items(raw[3])]
            costumes = [_text(v) for v in _items(raw[4])]
            sounds = [_text(v) for v in _items(raw[5])]
            scripts: list[ScriptSummary] = []
            for entry in _items(raw[6]):
                if not isinstance(entry, list) or len(entry) < 7:
                    raise ValueError(
                        "script entry must be #(id label hat blockCount hash owned userEdited)"
                    )
                scripts.append(
                    ScriptSummary(
                        script_id=_text(entry[0]),
                        target=name,
                        label=_text(entry[1]),
                        hat=_text(entry[2]),
                        block_count=int(entry[3]) if isinstance(entry[3], (int, float)) else 0,
                        hash=_text(entry[4]),
                        owned=entry[5] is True,
                        user_edited=entry[6] is True,
                        tuples=entry[7] if len(entry) >= 8 and isinstance(entry[7], list) else None,
                    )
                )
            props: dict[str, Any] = {}
            if len(raw) >= 8 and isinstance(raw[7], list):
                prop = raw[7]
                props = {
                    "x": _number(prop, 0, 0),
                    "y": _number(prop, 1, 0),
                    "direction": _number(prop, 2, 90),
                    "size": _number(prop, 3, 100),
                    "visible": prop[4] is not False if len(prop) > 4 else True,
                    "rotation_style": rotation_display(prop[5]) if len(prop) > 5 else "all around",
                    "ai_owned": prop[6] is True if len(prop) > 6 else False,
                    "costume_index": int(_number(prop, 7, 1)),
                }
            context.sprites[name] = SpriteContext(
                name=name,
                variables=variables,
                lists=lists,
                costumes=costumes,
                sounds=sounds,
                scripts=scripts,
                is_stage=is_stage,
                **props,
            )
            if is_stage:
                context.stage_variables = variables
                context.stage_lists = lists
        if not context.sprites:
            raise ValueError("context contains no sprites")
        if context.target not in context.sprites:
            context.target = next(
                (name for name, sprite in context.sprites.items() if not sprite.is_stage),
                next(iter(context.sprites)),
            )
        return context

    def target_context(self) -> SpriteContext:
        return self.sprites.get(self.target) or SpriteContext(self.target)

    def sprite_names(self) -> list[str]:
        return [name for name, sprite in self.sprites.items() if not sprite.is_stage]

    def variable_names(self, target: str | None = None) -> list[str]:
        target = target or self.target
        names = list(self.stage_variables)
        sprite = self.sprites.get(target)
        if sprite is not None:
            names.extend(sprite.variables)
        return sorted(set(names))

    def list_names(self, target: str | None = None) -> list[str]:
        target = target or self.target
        names = list(self.stage_lists)
        sprite = self.sprites.get(target)
        if sprite is not None:
            names.extend(sprite.lists)
        return sorted(set(names))

    def costume_names(self, target: str | None = None) -> list[str]:
        return list((self.sprites.get(target or self.target) or SpriteContext(target or self.target)).costumes)

    def sound_names(self, target: str | None = None) -> list[str]:
        return list((self.sprites.get(target or self.target) or SpriteContext(target or self.target)).sounds)

    def registry(self) -> dict[str, ScriptSummary]:
        result: dict[str, ScriptSummary] = {}
        for sprite in self.sprites.values():
            for script in sprite.scripts:
                result[script.script_id] = script
        return result

    def summary_text(self, generator: str = "json") -> str:
        lines = [f"Target: {self.target}"]
        lines.append("Sprites: " + ", ".join(self.sprites.keys()))
        if self.stage_variables:
            lines.append("Global variables: " + ", ".join(self.stage_variables))
        if self.stage_lists:
            lines.append("Global lists: " + ", ".join(self.stage_lists))
        for name, sprite in self.sprites.items():
            if sprite.is_stage:
                continue
            parts = []
            parts.append(
                f"x={sprite.x} y={sprite.y} direction={sprite.direction} "
                f"size={sprite.size} visible={str(sprite.visible).lower()} "
                f"rotation={sprite.rotation_style}"
            )
            if sprite.ai_owned:
                parts.append("AI-created sprite")
            else:
                parts.append("user sprite, read-only structure")
            if sprite.variables:
                parts.append("variables=" + ", ".join(sprite.variables))
            if sprite.lists:
                parts.append("lists=" + ", ".join(sprite.lists))
            if sprite.costumes:
                selected = ""
                if 1 <= sprite.costume_index <= len(sprite.costumes):
                    selected = f" (selected {sprite.costumes[sprite.costume_index - 1]})"
                parts.append("costumes=" + ", ".join(sprite.costumes) + selected)
            if sprite.sounds:
                parts.append("sounds=" + ", ".join(sprite.sounds))
            if parts:
                lines.append(f"{name}: " + "; ".join(parts))
        stage = self.sprites.get("Stage")
        if stage is not None and stage.costumes:
            selected = ""
            if 1 <= stage.costume_index <= len(stage.costumes):
                selected = f" (selected {stage.costumes[stage.costume_index - 1]})"
            lines.append("Backdrops: " + ", ".join(stage.costumes) + selected)
        if self.registry():
            if generator == "dsl":
                lines.append(
                    "Scripts (replace_script rewrites the WHOLE script; load "
                    "its sprite's detail first when the current body matters; "
                    "delete_script(script_id) removes):"
                )
            else:
                lines.append(
                    "Scripts (use the id for replace_script/delete_script):"
                )
            for script in self.registry().values():
                if script.owned:
                    owner = "ai-owned"
                else:
                    owner = "user-created, read-only"
                if script.user_edited:
                    owner += ", edited outside the harness"
                lines.append(
                    f"  {script.script_id}: {script.target} / {script.label} / "
                    f"{script.hat} / {script.block_count} blocks / {owner}"
                )
        return "\n".join(lines)


def _text(value: Any) -> str:
    if isinstance(value, Sym):
        return value.name
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return ""
    return str(value)


def _items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    raise ValueError(f"expected an array, got {type(value).__name__}")


def _number(value: list[Any], index: int, default: int | float) -> int | float:
    if index >= len(value):
        return default
    raw = value[index]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return default
    return raw
