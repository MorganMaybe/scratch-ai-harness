from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .block_ir import Change, ChangeSet, IRError
from .compiler import compile_script
from .context import ProjectContext, ScriptSummary
from .media import BACKDROP, COSTUME, MediaLibrary, default_library
from .smalltalk import Sym, to_literal


@dataclass
class CompiledChange:
    action: str
    script_id: str = ""
    target: str = ""
    label: str = ""
    stack: list[list[Any]] | None = None
    name: str = ""
    scope: str = "global"
    initial: Any = 0
    items: list[Any] = field(default_factory=list)
    block_count: int = 0
    costumes: list[list[str]] = field(default_factory=list)
    library: str = ""
    select: bool = False
    x: int | float = 0
    y: int | float = 0
    direction: int | float = 90
    size: int | float = 100
    visible: bool = True
    rotation_style: str = "all around"


@dataclass
class CompiledChangeSet:
    summary: str
    changes: list[CompiledChange]
    notes: str = ""

    def change_lines(self) -> list[str]:
        """The factual one-line description of every change (no summary/notes)."""
        lines: list[str] = []
        for change in self.changes:
            name = change.label or change.script_id
            if change.action == "add_script":
                lines.append(
                    f"Added script {name!r} to {change.target} ({change.block_count} blocks, id {change.script_id})."
                )
            elif change.action == "replace_script":
                lines.append(
                    f"Updated script {name!r} ({change.block_count} blocks, id {change.script_id})."
                )
            elif change.action == "delete_script":
                lines.append(f"Deleted script {name!r}.")
            elif change.action == "create_variable":
                lines.append(f"Created {change.scope} variable {change.name!r} = {change.initial!r}.")
            elif change.action == "create_list":
                count = len(change.items)
                lines.append(
                    f"Created {change.scope} list {change.name!r} with {count} item(s)."
                )
            elif change.action == "create_sprite":
                costumes = []
                for entry in change.costumes:
                    library = entry[0]
                    costume_name = entry[1] if len(entry) > 1 else ""
                    stem = library.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    if costume_name and costume_name != stem:
                        costumes.append(f"{costume_name!r} (from {library})")
                    else:
                        costumes.append(repr(costume_name or stem))
                lines.append(
                    f"Created sprite {change.name!r} with costumes "
                    + ", ".join(costumes)
                    + "."
                )
            elif change.action == "delete_sprite":
                lines.append(f"Deleted sprite {change.target!r}.")
            elif change.action == "duplicate_sprite":
                lines.append(f"Duplicated sprite {change.target!r} as {change.name!r}.")
            elif change.action == "add_costume":
                library = change.library
                stem = library.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                source = (
                    f" (from {library})"
                    if change.name and change.name != stem
                    else ""
                )
                lines.append(
                    f"Added costume {(change.name or stem)!r} to {change.target!r}{source}."
                )
            elif change.action == "set_backdrop":
                library = change.library
                stem = library.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                source = (
                    f" (from {library})"
                    if change.name and change.name != stem
                    else ""
                )
                lines.append(f"Set the backdrop to {(change.name or stem)!r}{source}.")
            elif change.action == "set_sprite":
                lines.append(f"Updated the position/size of sprite {change.target!r}.")
        return lines

    def chat_summary(self) -> str:
        lines = [self.summary.strip()]
        lines.extend(self.change_lines())
        if self.notes:
            lines.append(self.notes.strip())
        return "\n".join(lines)

    def apply_structure(self, request_id: int) -> list[Any]:
        items: list[Any] = []
        for change in self.changes:
            if change.action == "add_script":
                items.append([Sym("add"), change.script_id, change.target, change.stack, change.label])
            elif change.action == "replace_script":
                items.append([Sym("replace"), change.script_id, change.target, change.stack, change.label])
            elif change.action == "delete_script":
                items.append([Sym("delete"), change.script_id])
            elif change.action == "create_variable":
                items.append(
                    [
                        Sym("createVariable"),
                        change.name,
                        Sym(change.scope),
                        change.initial,
                        change.target or "Stage",
                    ]
                )
            elif change.action == "create_list":
                items.append([Sym("createList"), change.name, change.target, change.items])
            elif change.action == "create_sprite":
                items.append(
                    [
                        Sym("createSprite"),
                        change.name,
                        change.costumes,
                        change.x,
                        change.y,
                        change.direction,
                        change.size,
                        change.visible,
                        change.rotation_style,
                    ]
                )
            elif change.action == "duplicate_sprite":
                items.append([Sym("duplicateSprite"), change.target, change.name])
            elif change.action == "delete_sprite":
                items.append([Sym("deleteSprite"), change.target])
            elif change.action == "add_costume":
                items.append(
                    [
                        Sym("addCostume"),
                        change.target,
                        change.library,
                        change.name,
                        change.select,
                    ]
                )
            elif change.action == "set_backdrop":
                items.append(
                    [Sym("setBackdrop"), change.library, change.name, change.select]
                )
            elif change.action == "set_sprite":
                items.append(
                    [
                        Sym("setSprite"),
                        change.target,
                        change.x,
                        change.y,
                        change.direction,
                        change.size,
                        change.visible,
                        change.rotation_style,
                    ]
                )
        return [Sym("apply"), request_id, items]

    def apply_literal(self, request_id: int) -> str:
        return to_literal(self.apply_structure(request_id))


def compile_changeset(
    changeset: ChangeSet,
    context: ProjectContext,
    registry: dict[str, ScriptSummary] | None = None,
    media: MediaLibrary | None = None,
) -> CompiledChangeSet:
    registry = registry if registry is not None else context.registry()
    library = media if media is not None else default_library()
    used_ids = set(registry)
    next_id = 1

    def new_id() -> str:
        nonlocal next_id
        while f"ai-{next_id}" in used_ids:
            next_id += 1
        script_id = f"ai-{next_id}"
        used_ids.add(script_id)
        next_id += 1
        return script_id

    compiled: list[CompiledChange] = []
    for change in changeset.changes:
        if change.action == "add_script":
            script_id = new_id()
            stack = compile_script(change.to_script())
            compiled.append(
                CompiledChange(
                    action="add_script",
                    script_id=script_id,
                    target=change.target,
                    label=change.label,
                    stack=stack,
                    block_count=len(stack),
                )
            )
        elif change.action == "replace_script":
            existing = registry.get(change.script_id)
            if existing is None:
                raise IRError(f"cannot replace unknown script {change.script_id!r}")
            target = change.target or existing.target
            script = change.to_script()
            script.target = target
            stack = compile_script(script)
            compiled.append(
                CompiledChange(
                    action="replace_script",
                    script_id=change.script_id,
                    target=target,
                    label=change.label or existing.label,
                    stack=stack,
                    block_count=len(stack),
                )
            )
        elif change.action == "delete_script":
            existing = registry.get(change.script_id)
            if existing is None:
                raise IRError(f"cannot delete unknown script {change.script_id!r}")
            compiled.append(
                CompiledChange(
                    action="delete_script",
                    script_id=change.script_id,
                    target=existing.target,
                    label=existing.label,
                )
            )
        elif change.action == "create_variable":
            compiled.append(
                CompiledChange(
                    action="create_variable",
                    target=change.target,
                    name=change.name,
                    scope=change.scope,
                    initial=change.initial,
                )
            )
        elif change.action == "create_list":
            target_name = "Stage" if change.scope == "global" else change.target
            compiled.append(
                CompiledChange(
                    action="create_list",
                    target=target_name,
                    name=change.name,
                    scope=change.scope,
                    items=list(change.items),
                )
            )
        elif change.action == "create_sprite":
            preset = library.resolve_sprite(change.preset) if change.preset else None
            props = change.sprite_props(preset)
            costumes: list[list[object]] = []
            if preset is not None:
                for entry in preset.costumes:
                    asset = library.resolve(COSTUME, entry.library)
                    center_x, center_y = entry.pixel_center
                    costumes.append(
                        [asset.library, entry.name, center_x, center_y]
                    )
            else:
                for ref in change.costumes:
                    asset = library.resolve(COSTUME, ref.library)
                    costumes.append([asset.library, ref.name.strip() or asset.name])
            compiled.append(
                CompiledChange(
                    action="create_sprite",
                    name=change.name,
                    costumes=costumes,
                    x=props["x"],
                    y=props["y"],
                    direction=props["direction"],
                    size=props["size"],
                    visible=props["visible"],
                    rotation_style=props["rotation_style"],
                )
            )
        elif change.action == "duplicate_sprite":
            compiled.append(
                CompiledChange(
                    action="duplicate_sprite",
                    target=change.target,
                    name=change.name,
                )
            )
        elif change.action == "delete_sprite":
            compiled.append(
                CompiledChange(action="delete_sprite", target=change.target, name=change.target)
            )
        elif change.action == "add_costume":
            target = context.sprites.get(change.target)
            kind = BACKDROP if target is not None and target.is_stage else COSTUME
            asset = library.resolve(kind, change.library)
            compiled.append(
                CompiledChange(
                    action="add_costume",
                    target=change.target,
                    library=asset.library,
                    name=change.name.strip() or asset.name,
                    select=change.select,
                )
            )
        elif change.action == "set_backdrop":
            asset = library.resolve(BACKDROP, change.library)
            compiled.append(
                CompiledChange(
                    action="set_backdrop",
                    library=asset.library,
                    name=change.name.strip() or asset.name,
                    select=change.select,
                )
            )
        elif change.action == "set_sprite":
            sprite = context.sprites.get(change.target)
            props = {
                "x": change.x if change.x is not None else (sprite.x if sprite else 0),
                "y": change.y if change.y is not None else (sprite.y if sprite else 0),
                "direction": change.direction
                if change.direction is not None
                else (sprite.direction if sprite else 90),
                "size": change.size if change.size is not None else (sprite.size if sprite else 100),
                "visible": change.visible
                if change.visible is not None
                else (sprite.visible if sprite else True),
                "rotation_style": change.rotation_style
                or (sprite.rotation_style if sprite else "all around"),
            }
            compiled.append(
                CompiledChange(
                    action="set_sprite",
                    target=change.target,
                    x=props["x"],
                    y=props["y"],
                    direction=props["direction"],
                    size=props["size"],
                    visible=props["visible"],
                    rotation_style=props["rotation_style"],
                )
            )
    return CompiledChangeSet(changeset.summary, compiled, changeset.notes)
