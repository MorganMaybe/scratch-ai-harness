from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .block_ir import Block, Change, CostumeRef, ChangeSet, Script
from .catalog import (
    ATTRIBUTE_NAMES,
    COLOR_RE,
    GRAPHIC_EFFECTS,
    KEY_NAMES,
    LIST_INDEX_VALUES,
    SPRITE_TARGET_OPS,
    TARGET_MENU,
    spec_for,
)
from .context import ProjectContext, ScriptSummary, SpriteContext
from .media import BACKDROP, COSTUME, MediaError, MediaLibrary, default_library


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}" if self.path else self.message


class ValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue], attempts: int = 0):
        self.issues = issues
        #: Model attempts consumed by the failed turn.  The server records this
        #: in the audit outcome so a rejected turn is not reported as 0
        #: attempts when its attempt folders show otherwise.
        self.attempts = attempts
        super().__init__("\n".join(str(issue) for issue in issues))


MAX_BLOCKS = 160
MAX_DEPTH = 24


def validate_script(script: Script, context: ProjectContext, path: str = "script") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if script.target not in context.sprites:
        issues.append(ValidationIssue(path, f"unknown target sprite/stage: {script.target!r}"))
        return issues
    target_sprite = context.sprites[script.target]
    target_kind = "stage" if target_sprite.is_stage else "sprite"

    hat_spec = spec_for(script.hat.op)
    if hat_spec is None:
        issues.append(ValidationIssue(f"{path}.hat", f"unknown hat: {script.hat.op!r}"))
    else:
        if hat_spec.kind != "hat":
            issues.append(ValidationIssue(f"{path}.hat", f"{script.hat.op!r} is not a hat block"))
        if target_kind not in hat_spec.targets:
            issues.append(
                ValidationIssue(
                    f"{path}.hat",
                    f"{script.hat.op!r} cannot be used on {script.target!r}",
                )
            )
        issues.extend(_validate_args(script.hat, context, script.target, f"{path}.hat"))

    count = 0

    def walk(blocks: list[Block], prefix: str, depth: int) -> None:
        nonlocal count
        if depth > MAX_DEPTH:
            issues.append(ValidationIssue(prefix, f"nesting depth exceeds {MAX_DEPTH}"))
            return
        for index, block in enumerate(blocks):
            count += 1
            if count > MAX_BLOCKS:
                issues.append(ValidationIssue(prefix, f"script exceeds {MAX_BLOCKS} blocks"))
                return
            block_path = f"{prefix}[{index}]"
            spec = spec_for(block.op)
            if spec is None:
                issues.append(ValidationIssue(block_path, f"unknown block: {block.op!r}"))
                continue
            if spec.kind == "hat":
                issues.append(ValidationIssue(block_path, "hat blocks are only allowed at the top of a script"))
                continue
            if target_kind not in spec.targets:
                issues.append(
                    ValidationIssue(
                        block_path,
                        f"{block.op!r} cannot be used on {script.target!r}",
                    )
                )
            issues.extend(_validate_args(block, context, script.target, block_path))
            if spec.body == "body":
                if block.then or block.else_:
                    issues.append(ValidationIssue(block_path, f"{block.op!r} only takes a 'body'"))
                walk(block.body, f"{block_path}.body", depth + 1)
            elif spec.body == "then_else":
                if block.body:
                    issues.append(ValidationIssue(block_path, f"{block.op!r} takes 'then'/'else', not 'body'"))
                walk(block.then, f"{block_path}.then", depth + 1)
                walk(block.else_, f"{block_path}.else", depth + 1)
            else:
                if block.body or block.then or block.else_:
                    issues.append(ValidationIssue(block_path, f"{block.op!r} does not take a body"))

    walk(script.body, path, 0)
    return issues


def _validate_args(block: Block, context: ProjectContext, target: str, path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    spec = spec_for(block.op)
    if spec is None:
        return issues
    expected = {arg.name for arg in spec.args}
    actual = set(block.args)
    missing = expected - actual
    extra = actual - expected
    for name in sorted(missing):
        issues.append(ValidationIssue(path, f"missing argument {name!r}"))
    for name in sorted(extra):
        issues.append(ValidationIssue(path, f"unknown argument {name!r}"))

    for arg_spec in spec.args:
        if arg_spec.name not in block.args:
            continue
        value = block.args[arg_spec.name]
        menu = arg_spec.menu
        sprite_target = False
        if (
            arg_spec.type == "menu"
            and arg_spec.name == "target"
            and block.op in SPRITE_TARGET_OPS
        ):
            # Scratch's target menus include the project's sprites; the static
            # catalog cannot know them, so add the current top-down context.
            menu = tuple(dict.fromkeys((*menu, *context.sprite_names())))
            sprite_target = True
        issues.extend(
            _validate_arg(
                value,
                arg_spec.type,
                menu,
                context,
                target,
                f"{path}.{arg_spec.name}",
                sprite_target=sprite_target,
            )
        )

    op = block.op
    if op in {"set_var", "change_var", "get_var", "show_variable", "hide_variable"}:
        name = block.args.get("name")
        if isinstance(name, str) and name not in context.variable_names(target):
            issues.append(
                ValidationIssue(
                    f"{path}.name",
                    f"unknown variable {name!r}; add a create_variable change first",
                )
            )
    elif op in {"list_item", "insert_in_list", "replace_in_list"}:
        index = block.args.get("index")
        if (
            isinstance(index, (int, float))
            and not isinstance(index, bool)
            and index < 1
        ):
            issues.append(ValidationIssue(f"{path}.index", "list index must be at least 1"))
    elif op == "switch_costume":
        name = block.args.get("costume")
        available = context.costume_names(target)
        if isinstance(name, str) and available and name not in available:
            issues.append(
                ValidationIssue(
                    f"{path}.costume",
                    f"unknown costume {name!r}; available: {', '.join(available)}",
                )
            )
    elif op in {"switch_backdrop", "when_backdrop_switches"}:
        name = block.args.get("backdrop")
        available = context.costume_names("Stage")
        if isinstance(name, str) and available and name not in available:
            issues.append(
                ValidationIssue(
                    f"{path}.backdrop",
                    f"unknown backdrop {name!r}; available: {', '.join(available)}",
                )
            )
    elif op in {"set_attribute_of", "change_attribute_of"}:
        name = block.args.get("attribute")
        if isinstance(name, str) and name not in ATTRIBUTE_NAMES:
            issues.append(
                ValidationIssue(
                    f"{path}.attribute",
                    f"unknown attribute {name!r}; use one of {', '.join(ATTRIBUTE_NAMES)}",
                )
            )
    elif op in {"play_sound", "play_sound_until_done"}:
        name = block.args.get("sound")
        available = context.sound_names(target)
        if isinstance(name, str) and available and name not in available:
            issues.append(
                ValidationIssue(
                    f"{path}.sound",
                    f"unknown sound {name!r}; available: {', '.join(available)}",
                )
            )
    elif op == "create_clone":
        name = block.args.get("target")
        if not isinstance(name, str) or not name.strip():
            issues.append(ValidationIssue(f"{path}.target", "create_clone needs 'myself' or a sprite name"))
        elif name.casefold() == "stage":
            issues.append(ValidationIssue(f"{path}.target", "the Stage cannot be cloned"))
        elif name.casefold() != "myself" and name not in context.sprites:
            issues.append(
                ValidationIssue(
                    f"{path}.target",
                    f"unknown clone target {name!r}; use 'myself' or an existing sprite name",
                )
            )
    elif op == "attribute_of":
        name = block.args.get("attribute")
        if isinstance(name, str) and name not in ATTRIBUTE_NAMES:
            issues.append(
                ValidationIssue(
                    f"{path}.attribute",
                    f"unknown attribute {name!r}; use one of {', '.join(ATTRIBUTE_NAMES)}",
                )
            )
    elif op == "when_key_pressed" or op == "key_pressed":
        key = block.args.get("key")
        if isinstance(key, str) and key not in KEY_NAMES:
            issues.append(ValidationIssue(f"{path}.key", f"unknown key {key!r}"))
    elif op in {"set_effect", "change_effect"}:
        effect = block.args.get("effect")
        if isinstance(effect, str) and effect not in GRAPHIC_EFFECTS:
            issues.append(
                ValidationIssue(
                    f"{path}.effect",
                    f"unknown effect {effect!r}; use one of {', '.join(GRAPHIC_EFFECTS)}",
                )
            )
    return issues


def _validate_arg(
    value: Any,
    arg_type: str,
    menu: tuple[str, ...],
    context: ProjectContext,
    target: str,
    path: str,
    sprite_target: bool = False,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if isinstance(value, Block):
        spec = spec_for(value.op)
        if spec is None:
            return [ValidationIssue(path, f"unknown reporter: {value.op!r}")]
        if spec.kind not in {"reporter", "boolean"}:
            return [ValidationIssue(path, f"{value.op!r} is a command, not a reporter")]
        if arg_type in {"menu", "string", "color", "list", "list_index", "clone_target"}:
            issues.append(ValidationIssue(path, f"{arg_type} arguments must be literal values, not reporters"))
        if arg_type == "boolean" and spec.kind != "boolean":
            issues.append(ValidationIssue(path, f"expected a boolean reporter, got {value.op!r}"))
        issues.extend(_validate_args(value, context, target, path))
        return issues

    if isinstance(value, str) and ("\n" in value or "\r" in value):
        issues.append(ValidationIssue(path, "string arguments must be single-line"))

    if arg_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            issues.append(ValidationIssue(path, f"expected a number, got {type(value).__name__}"))
    elif arg_type == "string":
        if not isinstance(value, str):
            issues.append(ValidationIssue(path, f"expected a string, got {type(value).__name__}"))
    elif arg_type == "color":
        if not isinstance(value, str) or COLOR_RE.match(value) is None:
            issues.append(
                ValidationIssue(path, "expected a color as a '#rrggbb' string")
            )
    elif arg_type == "list":
        if not isinstance(value, str) or not value:
            issues.append(ValidationIssue(path, "expected a list name"))
        elif value not in context.list_names(target):
            issues.append(
                ValidationIssue(
                    path,
                    f"unknown list {value!r}; add a create_list change first",
                )
            )
    elif arg_type == "list_index":
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            issues.append(ValidationIssue(path, "list index must be a number, 'last' or 'all'"))
        elif isinstance(value, str) and value not in LIST_INDEX_VALUES:
            issues.append(
                ValidationIssue(path, "list index string must be 'last' or 'all'")
            )
        elif isinstance(value, (int, float)) and value < 1:
            issues.append(ValidationIssue(path, "list index must be at least 1"))
    elif arg_type == "boolean":
        if not isinstance(value, bool):
            issues.append(ValidationIssue(path, f"expected a boolean, got {type(value).__name__}"))
    elif arg_type == "menu":
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            issues.append(ValidationIssue(path, f"expected a menu value, got {type(value).__name__}"))
        elif menu and isinstance(value, str) and value not in menu:
            if sprite_target:
                # A missing sprite is not a forbidden menu word: say so, and
                # point at the top-down rule the model has to satisfy.
                issues.append(
                    ValidationIssue(
                        path,
                        f"unknown sprite {value!r}; this menu accepts a sprite that exists "
                        f"at this point in the change set (create it earlier), or one of "
                        f"{', '.join(menu)}",
                    )
                )
            else:
                issues.append(ValidationIssue(path, f"expected one of {', '.join(menu)}, got {value!r}"))
    elif arg_type == "clone_target":
        if not isinstance(value, str) or not value.strip():
            issues.append(ValidationIssue(path, "expected 'myself' or a sprite name"))
    elif arg_type == "any":
        if isinstance(value, (dict, list, tuple)):
            issues.append(ValidationIssue(path, "arguments must be literals or reporter blocks"))
    else:
        issues.append(ValidationIssue(path, f"unsupported argument type {arg_type!r}"))
    return issues


def _media_library(media: MediaLibrary | None) -> MediaLibrary:
    return media if media is not None else default_library()


def _name_key(name: str) -> str:
    return name.strip().casefold()


def _sprite_name_issues(name: str, working: ProjectContext, path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    text = name.strip()
    if not text:
        return [ValidationIssue(path, "sprite name is required")]
    key = _name_key(text)
    if key == "stage":
        issues.append(ValidationIssue(path, "a sprite cannot be named 'Stage'"))
    if key in {item.casefold() for item in TARGET_MENU}:
        issues.append(
            ValidationIssue(
                path,
                f"sprite name {text!r} is a Scratch menu value; choose another name",
            )
        )
    for existing in working.sprites:
        if existing.casefold() == key:
            issues.append(ValidationIssue(path, f"sprite {text!r} already exists"))
            break
    return issues


def _property_issues(change: Change, path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if change.size is not None and change.size <= 0:
        issues.append(ValidationIssue(f"{path}.size", "size must be greater than 0"))
    return issues


def _resolve_media(
    media: MediaLibrary,
    kind: str,
    library: str,
    path: str,
) -> tuple[Any | None, list[ValidationIssue]]:
    try:
        return media.resolve(kind, library), []
    except MediaError as exc:
        return None, [ValidationIssue(path, str(exc))]


def _costume_name(ref: CostumeRef, asset: Any) -> str:
    return ref.name.strip() or asset.name


def _add_costume_to(
    sprite: SpriteContext,
    name: str,
    path: str,
    select: bool,
) -> list[ValidationIssue]:
    if any(existing.casefold() == name.casefold() for existing in sprite.costumes):
        return [ValidationIssue(path, f"costume {name!r} already exists on {sprite.name!r}")]
    sprite.costumes.append(name)
    if select:
        sprite.costume_index = len(sprite.costumes)
    return []


def validate_changeset(
    changeset: ChangeSet,
    context: ProjectContext,
    registry: dict[str, ScriptSummary] | None = None,
    media: MediaLibrary | None = None,
) -> list[ValidationIssue]:
    import copy

    library = _media_library(media)
    issues: list[ValidationIssue] = []
    working_context = copy.deepcopy(context)
    working_registry = dict(registry if registry is not None else context.registry())
    # An empty change set is the acknowledgment reply shape: the request is
    # already satisfied.  It validates cleanly and applies nothing.
    for index, change in enumerate(changeset.changes):
        path = f"changes[{index}]"
        if change.action == "add_script":
            if not change.target:
                issues.append(ValidationIssue(path, "add_script requires a target"))
                continue
            if change.hat is None:
                issues.append(ValidationIssue(path, "add_script requires a hat"))
                continue
            script_issues = validate_script(change.to_script(), working_context, path)
            issues.extend(script_issues)
        elif change.action == "replace_script":
            if not change.script_id:
                issues.append(ValidationIssue(path, "replace_script requires script_id"))
            elif change.script_id not in working_registry:
                issues.append(ValidationIssue(path, f"unknown script_id {change.script_id!r}"))
            elif not working_registry[change.script_id].owned:
                issues.append(
                    ValidationIssue(
                        path,
                        f"script {change.script_id!r} was not created by the harness and is "
                        "read-only; add a new script instead",
                    )
                )
            if change.hat is None:
                issues.append(ValidationIssue(path, "replace_script requires a hat"))
            if not change.target and change.script_id in working_registry:
                change.target = working_registry[change.script_id].target
            if change.target:
                script_issues = validate_script(change.to_script(), working_context, path)
                issues.extend(script_issues)
                if not script_issues and change.script_id:
                    existing = working_registry.get(change.script_id)
                    if existing is not None:
                        working_registry[change.script_id] = ScriptSummary(
                            script_id=change.script_id,
                            target=change.target,
                            label=change.label or existing.label,
                            hat=change.hat.op,
                            block_count=len(change.body) + 1,
                        )
        elif change.action == "delete_script":
            if not change.script_id:
                issues.append(ValidationIssue(path, "delete_script requires script_id"))
            elif change.script_id not in working_registry:
                issues.append(ValidationIssue(path, f"unknown script_id {change.script_id!r}"))
            elif not working_registry[change.script_id].owned:
                issues.append(
                    ValidationIssue(
                        path,
                        f"script {change.script_id!r} was not created by the harness and is "
                        "read-only; add a new script instead",
                    )
                )
            else:
                working_registry.pop(change.script_id, None)
        elif change.action == "create_variable":
            if not change.name:
                issues.append(ValidationIssue(path, "create_variable requires a name"))
            if change.scope == "sprite":
                if not change.target or change.target not in working_context.sprites:
                    issues.append(ValidationIssue(path, "sprite-scoped variable requires a valid target"))
                elif working_context.sprites[change.target].is_stage:
                    issues.append(ValidationIssue(path, "sprite-scoped variable cannot target the stage"))
            if change.name in working_context.variable_names(change.target or None):
                issues.append(ValidationIssue(path, f"variable {change.name!r} already exists"))
            elif change.name:
                if change.scope == "global":
                    working_context.stage_variables.append(change.name)
                elif change.target in working_context.sprites:
                    working_context.sprites[change.target].variables.append(change.name)
        elif change.action == "create_list":
            name = change.name.strip()
            if not name:
                issues.append(ValidationIssue(path, "create_list requires a name"))
            target = None
            if change.scope == "sprite":
                target = working_context.sprites.get(change.target)
                if target is None:
                    issues.append(ValidationIssue(path, "sprite-scoped list requires a valid target"))
                elif target.is_stage:
                    issues.append(ValidationIssue(path, "sprite-scoped list cannot target the stage"))
            if name:
                if change.scope == "global":
                    exists = name in working_context.stage_lists
                else:
                    exists = (
                        target is not None and name in target.lists
                    ) or name in working_context.stage_lists
                if exists:
                    issues.append(ValidationIssue(path, f"list {name!r} already exists"))
                elif change.scope == "global":
                    working_context.stage_lists.append(name)
                elif target is not None:
                    target.lists.append(name)
        elif change.action == "create_sprite":
            # Register the sprite only when *this* change is clean.  `issues`
            # also carries earlier changes' failures, and gating on all of it
            # used to hide every later sprite after one unrelated error, so
            # scripts for those sprites failed with a bogus unknown target.
            base = len(issues)
            issues.extend(_sprite_name_issues(change.name, working_context, f"{path}.name"))
            preset = None
            if change.preset:
                try:
                    preset = library.resolve_sprite(change.preset)
                except MediaError as exc:
                    issues.append(ValidationIssue(f"{path}.preset", str(exc)))
                if change.costumes:
                    issues.append(
                        ValidationIssue(
                            f"{path}.costumes",
                            "use either 'preset' or 'costumes', not both",
                        )
                    )
            elif not 1 <= len(change.costumes) <= 3:
                issues.append(ValidationIssue(f"{path}.costumes", "create_sprite needs 1-3 costumes"))
            props = change.sprite_props(preset)
            issues.extend(_property_issues(change, path))
            costume_names: list[str] = []
            if preset is not None:
                for costume_index, entry in enumerate(preset.costumes):
                    asset, asset_issues = _resolve_media(
                        library,
                        COSTUME,
                        entry.library,
                        f"{path}.preset.costumes[{costume_index}]",
                    )
                    issues.extend(asset_issues)
                    if asset is not None:
                        costume_name = entry.name or asset.name
                        if any(
                            existing.casefold() == costume_name.casefold()
                            for existing in costume_names
                        ):
                            issues.append(
                                ValidationIssue(
                                    f"{path}.preset.costumes[{costume_index}]",
                                    f"duplicate costume name {costume_name!r}",
                                )
                            )
                        costume_names.append(costume_name)
            else:
                for costume_index, ref in enumerate(change.costumes):
                    asset, asset_issues = _resolve_media(
                        library, COSTUME, ref.library, f"{path}.costumes[{costume_index}].library"
                    )
                    issues.extend(asset_issues)
                    if asset is not None:
                        costume_name = _costume_name(ref, asset)
                        if any(
                            existing.casefold() == costume_name.casefold()
                            for existing in costume_names
                        ):
                            issues.append(
                                ValidationIssue(
                                    f"{path}.costumes[{costume_index}].name",
                                    f"duplicate costume name {costume_name!r}",
                                )
                            )
                        costume_names.append(costume_name)
            if len(issues) == base:
                working_context.sprites[change.name] = SpriteContext(
                    name=change.name,
                    costumes=costume_names,
                    ai_owned=True,
                    costume_index=1,
                    x=props["x"],
                    y=props["y"],
                    direction=props["direction"],
                    size=props["size"],
                    visible=props["visible"],
                    rotation_style=props["rotation_style"],
                )
        elif change.action == "delete_sprite":
            sprite = working_context.sprites.get(change.target)
            if sprite is None:
                issues.append(ValidationIssue(path, f"unknown sprite {change.target!r}"))
            elif sprite.is_stage:
                issues.append(ValidationIssue(path, "the stage cannot be deleted"))
            elif not sprite.ai_owned and sprite.scripts:
                issues.append(
                    ValidationIssue(
                        path,
                        f"sprite {change.target!r} is a user sprite with scripts and cannot be deleted",
                    )
                )
            else:
                working_context.sprites.pop(change.target, None)
                for script_id in [
                    script_id
                    for script_id, script in working_registry.items()
                    if script.target == change.target
                ]:
                    working_registry.pop(script_id, None)
        elif change.action == "duplicate_sprite":
            source = working_context.sprites.get(change.target)
            if source is None:
                issues.append(ValidationIssue(path, f"unknown sprite {change.target!r}"))
            elif source.is_stage:
                issues.append(ValidationIssue(path, "the stage cannot be duplicated"))
            elif not source.ai_owned:
                issues.append(
                    ValidationIssue(
                        path,
                        f"sprite {change.target!r} is a user sprite and cannot be duplicated",
                    )
                )
            issues.extend(_sprite_name_issues(change.name, working_context, f"{path}.name"))
            if source is not None and not source.is_stage and source.ai_owned:
                working_context.sprites[change.name] = SpriteContext(
                    name=change.name,
                    variables=list(source.variables),
                    costumes=list(source.costumes),
                    sounds=list(source.sounds),
                    is_stage=False,
                    x=source.x,
                    y=source.y,
                    direction=source.direction,
                    size=source.size,
                    visible=source.visible,
                    rotation_style=source.rotation_style,
                    ai_owned=True,
                    costume_index=source.costume_index,
                )
        elif change.action == "add_costume":
            target = working_context.sprites.get(change.target)
            if target is None:
                issues.append(ValidationIssue(path, f"unknown target {change.target!r}"))
            if not change.library:
                issues.append(ValidationIssue(path, "add_costume requires library"))
            if target is not None and change.library:
                kind = BACKDROP if target.is_stage else COSTUME
                asset, asset_issues = _resolve_media(
                    library, kind, change.library, f"{path}.library"
                )
                issues.extend(asset_issues)
                if asset is not None:
                    name = change.name.strip() or asset.name
                    issues.extend(_add_costume_to(target, name, f"{path}.name", change.select))
        elif change.action == "set_backdrop":
            stage = working_context.sprites.get("Stage")
            if stage is None:
                issues.append(ValidationIssue(path, "the project has no stage"))
            if not change.library:
                issues.append(ValidationIssue(path, "set_backdrop requires library"))
            if stage is not None and change.library:
                asset, asset_issues = _resolve_media(
                    library, BACKDROP, change.library, f"{path}.library"
                )
                issues.extend(asset_issues)
                if asset is not None:
                    name = change.name.strip() or asset.name
                    if not any(item.casefold() == name.casefold() for item in stage.costumes):
                        stage.costumes.append(name)
                    stage.costume_index = next(
                        (
                            position
                            for position, item in enumerate(stage.costumes, start=1)
                            if item.casefold() == name.casefold()
                        ),
                        1,
                    )
        elif change.action == "set_sprite":
            target = working_context.sprites.get(change.target)
            if target is None:
                issues.append(ValidationIssue(path, f"unknown sprite {change.target!r}"))
            elif target.is_stage:
                issues.append(ValidationIssue(path, "the stage has no motion properties"))
            else:
                issues.extend(_property_issues(change, path))
                if change.x is not None:
                    target.x = change.x
                if change.y is not None:
                    target.y = change.y
                if change.direction is not None:
                    target.direction = change.direction
                if change.size is not None:
                    target.size = change.size
                if change.visible is not None:
                    target.visible = change.visible
                if change.rotation_style:
                    target.rotation_style = change.rotation_style
    return issues


def validate_or_raise(
    changeset: ChangeSet,
    context: ProjectContext,
    registry: dict[str, ScriptSummary] | None = None,
) -> None:
    issues = validate_changeset(changeset, context, registry)
    if issues:
        raise ValidationError(issues)
