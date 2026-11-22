from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .catalog import spec_for

if TYPE_CHECKING:
    from .media import SpritePreset


class IRError(ValueError):
    pass


@dataclass
class Block:
    op: str
    args: dict[str, Any] = field(default_factory=dict)
    body: list["Block"] = field(default_factory=list)
    then: list["Block"] = field(default_factory=list)
    else_: list["Block"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Any) -> "Block":
        if not isinstance(data, dict):
            raise IRError(f"block must be an object, got {type(data).__name__}")
        op = data.get("op")
        allowed = {"op", "args", "body", "then", "else"}
        unknown = set(data) - allowed
        if unknown:
            raise IRError(_unknown_fields_message(op, data, unknown))
        if not isinstance(op, str) or not op:
            raise IRError("block is missing a non-empty 'op'")
        args = data.get("args", {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise IRError(f"block '{op}' args must be an object")
        args = {key: _parse_arg(value) for key, value in args.items()}
        body = _block_list(op, data.get("body"))
        then = _block_list(op, data.get("then"))
        else_ = _block_list(op, data.get("else"))
        return cls(op=op, args=args, body=body, then=then, else_=else_)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"op": self.op}
        if self.args:
            out["args"] = {k: _arg_to_dict(v) for k, v in self.args.items()}
        if self.body:
            out["body"] = [b.to_dict() for b in self.body]
        if self.then:
            out["then"] = [b.to_dict() for b in self.then]
        if self.else_:
            out["else"] = [b.to_dict() for b in self.else_]
        return out


def _unknown_fields_message(op: Any, data: dict, unknown: set[str]) -> str:
    """One-line diagnostic that names the block and how to fix each extra field."""
    message = f"unknown block fields {sorted(unknown)} on block {op!r}"
    spec = spec_for(op) if isinstance(op, str) else None
    arg_names = {arg.name for arg in spec.args} if spec is not None else set()
    nested = sorted(
        name
        for name in unknown
        if isinstance(data.get(name), dict) and "op" in data[name]
    )
    hoisted = sorted(
        name for name in unknown if name in arg_names and name not in nested
    )
    hints: list[str] = []
    if nested:
        hints.append(
            "a nested block belongs in the body list (or then/else), "
            "not as a named field"
        )
    for name in hoisted:
        hints.append(f"argument {name!r} belongs inside 'args'")
    if len(nested) + len(hoisted) < len(unknown) or not hints:
        hints.append("blocks take only op, args, body, then, else")
    return message + "; " + "; ".join(hints)


def _block_list(op: str, value: Any) -> list[Block]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise IRError(f"block '{op}' body/then/else must be an array")
    return [Block.from_dict(item) for item in value]


def _parse_arg(value: Any) -> Any:
    if isinstance(value, dict):
        return Block.from_dict(value)
    if isinstance(value, list):
        return [_parse_arg(item) for item in value]
    return value


def _arg_to_dict(value: Any) -> Any:
    if isinstance(value, Block):
        return value.to_dict()
    if isinstance(value, list):
        return [_arg_to_dict(v) for v in value]
    return value


@dataclass
class Script:
    target: str
    hat: Block
    body: list[Block]
    label: str = ""

    @classmethod
    def from_dict(cls, data: Any) -> "Script":
        if not isinstance(data, dict):
            raise IRError("script must be an object")
        allowed = {"target", "hat", "body", "label"}
        unknown = set(data) - allowed
        if unknown:
            raise IRError(f"unknown script fields: {sorted(unknown)}")
        target = data.get("target")
        if not isinstance(target, str) or not target:
            raise IRError("script is missing a target")
        hat = Block.from_dict(data.get("hat"))
        body = _block_list("script", data.get("body"))
        label = data.get("label", "")
        if not isinstance(label, str):
            raise IRError("script label must be a string")
        return cls(target=target, hat=hat, body=body, label=label)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "target": self.target,
            "hat": self.hat.to_dict(),
            "body": [b.to_dict() for b in self.body],
        }
        if self.label:
            out["label"] = self.label
        return out


CHANGE_ACTIONS: frozenset[str] = frozenset(
    {
        "add_script",
        "replace_script",
        "delete_script",
        "create_variable",
        "create_list",
        "create_sprite",
        "delete_sprite",
        "duplicate_sprite",
        "add_costume",
        "set_backdrop",
        "set_sprite",
    }
)

ROTATION_STYLES: tuple[str, ...] = ("all around", "left-right", "don't rotate")

DEFAULT_SPRITE_PROPS: dict[str, Any] = {
    "x": 0,
    "y": 0,
    "direction": 90,
    "size": 100,
    "visible": True,
    "rotation_style": "all around",
}


@dataclass(frozen=True)
class CostumeRef:
    """One library costume for ``create_sprite``."""

    library: str
    name: str = ""

    @classmethod
    def from_value(cls, value: Any, path: str = "costumes") -> "CostumeRef":
        if isinstance(value, str):
            return cls(library=value)
        if not isinstance(value, dict):
            raise IRError(f"{path} entries must be strings or objects")
        allowed = {"library", "name"}
        unknown = set(value) - allowed
        if unknown:
            raise IRError(f"unknown {path} fields: {sorted(unknown)}")
        library = value.get("library")
        if not isinstance(library, str) or not library.strip():
            raise IRError(f"{path} entry is missing a non-empty 'library'")
        return cls(library=library.strip(), name=_str(value.get("name", ""), "costume name"))


@dataclass
class Change:
    action: str
    script_id: str = ""
    target: str = ""
    label: str = ""
    hat: Block | None = None
    body: list[Block] = field(default_factory=list)
    name: str = ""
    scope: str = "global"
    initial: Any = 0
    items: list[Any] = field(default_factory=list)
    costumes: list[CostumeRef] = field(default_factory=list)
    x: int | float | None = None
    y: int | float | None = None
    direction: int | float | None = None
    size: int | float | None = None
    visible: bool | None = None
    rotation_style: str = ""
    library: str = ""
    preset: str = ""
    select: bool = False

    @classmethod
    def from_dict(cls, data: Any) -> "Change":
        if not isinstance(data, dict):
            raise IRError("change must be an object")
        allowed = {
            "action",
            "script_id",
            "target",
            "label",
            "hat",
            "body",
            "name",
            "scope",
            "initial",
            "items",
            "costumes",
            "x",
            "y",
            "direction",
            "size",
            "visible",
            "rotation_style",
            "library",
            "preset",
            "select",
        }
        unknown = set(data) - allowed
        if unknown:
            raise IRError(f"unknown change fields: {sorted(unknown)}")
        action = data.get("action")
        if action not in CHANGE_ACTIONS:
            raise IRError(f"unknown change action: {action!r}")
        hat = Block.from_dict(data["hat"]) if data.get("hat") is not None else None
        body = _block_list("change", data.get("body"))
        scope = data.get("scope", "global")
        if scope not in {"global", "sprite"}:
            raise IRError("variable scope must be 'global' or 'sprite'")
        initial = data.get("initial", 0)
        select = data.get("select", action == "set_backdrop")
        if not isinstance(select, bool):
            raise IRError("select must be true or false")
        rotation_style = _str(data.get("rotation_style", ""), "rotation_style")
        if rotation_style and rotation_style not in ROTATION_STYLES:
            raise IRError(
                "rotation_style must be one of " + ", ".join(repr(v) for v in ROTATION_STYLES)
            )
        return cls(
            action=action,
            script_id=_str(data.get("script_id", ""), "script_id"),
            target=_str(data.get("target", ""), "target"),
            label=_str(data.get("label", ""), "label"),
            hat=hat,
            body=body,
            name=_str(data.get("name", ""), "name"),
            scope=scope,
            initial=initial,
            items=_list_items(data.get("items")),
            costumes=_costume_refs(data.get("costumes"), "costumes"),
            x=_optional_number(data.get("x"), "x"),
            y=_optional_number(data.get("y"), "y"),
            direction=_optional_number(data.get("direction"), "direction"),
            size=_optional_number(data.get("size"), "size"),
            visible=_optional_bool(data.get("visible"), "visible"),
            rotation_style=rotation_style,
            library=_str(data.get("library", ""), "library"),
            preset=_str(data.get("preset", ""), "preset"),
            select=select,
        )

    def sprite_props(self, preset: SpritePreset | None = None) -> dict[str, Any]:
        """Concrete sprite properties, applying preset and creation defaults."""
        props = dict(DEFAULT_SPRITE_PROPS)
        if preset is not None:
            props["direction"] = preset.direction
            props["size"] = preset.size
            props["rotation_style"] = preset.rotation_style
        for key in ("x", "y", "direction", "size", "visible", "rotation_style"):
            value = getattr(self, key)
            if value is not None and value != "":
                props[key] = value
        return props

    def to_script(self) -> Script:
        if self.hat is None:
            raise IRError(f"change '{self.action}' is missing a hat")
        return Script(self.target, self.hat, self.body, self.label)


def _str(value: Any, name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise IRError(f"{name} must be a string")
    return value


def _optional_number(value: Any, name: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IRError(f"{name} must be a number")
    return value


def _optional_bool(value: Any, name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise IRError(f"{name} must be true or false")
    return value


def _list_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise IRError("items must be an array")
    items: list[Any] = []
    for item in value:
        if isinstance(item, bool) or isinstance(item, (int, float)):
            items.append(item)
        elif isinstance(item, str):
            if "\n" in item or "\r" in item:
                raise IRError("list items must be single-line strings")
            items.append(item)
        else:
            raise IRError("list items must be strings, numbers, or booleans")
    return items


def _costume_refs(value: Any, name: str) -> list[CostumeRef]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise IRError(f"{name} must be an array")
    return [CostumeRef.from_value(item, name) for item in value]


@dataclass(frozen=True)
class ContextRequest:
    """A model request to load optional context before answering.

    ``packs`` names topic docs (``context/*.md``); ``sprites`` names project
    sprites whose exact script bodies should be appended. Either or both may be
    requested in one reply.
    """

    packs: tuple[str, ...] = ()
    sprites: tuple[str, ...] = ()
    reason: str = ""


def _context_names(
    value: Any, field: str, *, lowercase: bool, limit: int
) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise IRError(f"{field} must be a string or an array of strings")
    if not all(isinstance(item, str) for item in values):
        raise IRError(f"{field} entries must be strings")
    names: list[str] = []
    seen: set[str] = set()
    for value in values:
        name = value.strip()
        if lowercase:
            name = name.lower()
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        names.append(name)
    if not names:
        raise IRError(f"{field} must name at least one entry")
    if len(names) > limit:
        raise IRError(f"load at most {limit} entries in {field} at once")
    return names


def parse_context_request(data: Any) -> ContextRequest | None:
    """Return a lazy-context request, or ``None`` for an ordinary reply.

    The contract is a separate top-level object:

    ``{"load_context": ["clones"], "reason": "..."}``
    ``{"load_sprite": ["Bat"], "reason": "..."}``

    It must not be combined with a change set. Unknown fields and bad names are
    rejected so the agent can ask for a corrected reply.
    """
    if not isinstance(data, dict) or (
        "load_context" not in data and "load_sprite" not in data
    ):
        return None
    allowed = {"load_context", "load_sprite", "reason"}
    unknown = set(data) - allowed
    if unknown:
        raise IRError(
            "load_context/load_sprite replies may only contain load_context, "
            f"load_sprite and reason; unknown fields: {sorted(unknown)}"
        )
    packs = (
        _context_names(data["load_context"], "load_context", lowercase=True, limit=6)
        if "load_context" in data
        else []
    )
    sprites = (
        _context_names(data["load_sprite"], "load_sprite", lowercase=False, limit=6)
        if "load_sprite" in data
        else []
    )
    if not packs and not sprites:
        raise IRError("name at least one context pack or sprite")
    reason = data.get("reason", "")
    if not isinstance(reason, str):
        raise IRError("load_context reason must be a string")
    return ContextRequest(tuple(packs), tuple(sprites), reason)


@dataclass
class ChangeSetParseResult:
    """A change set parsed one change at a time.

    ``changes`` keeps valid entries and ``None`` for entries that failed to
    parse, so the agent can repair just the bad fragments.  A malformed
    top-level envelope (missing summary/changes) cannot be fragmented and is
    reported in ``top_level_error``.
    """

    summary: str = ""
    notes: str = ""
    changes: list[Change | None] = field(default_factory=list)
    problems: list[tuple[int, IRError]] = field(default_factory=list)
    top_level_error: IRError | None = None

    @property
    def complete(self) -> bool:
        return self.top_level_error is None and not self.problems


def parse_changeset_partial(data: Any) -> ChangeSetParseResult:
    """Parse as much of a change set as possible without raising per change."""
    if not isinstance(data, dict):
        return ChangeSetParseResult(
            top_level_error=IRError("change set must be an object")
        )
    allowed = {"summary", "changes", "notes"}
    unknown = set(data) - allowed
    if unknown:
        return ChangeSetParseResult(
            top_level_error=IRError(f"unknown change-set fields: {sorted(unknown)}")
        )
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary:
        return ChangeSetParseResult(
            top_level_error=IRError("change set is missing a summary")
        )
    raw_changes = data.get("changes")
    if not isinstance(raw_changes, list) or not raw_changes:
        return ChangeSetParseResult(
            top_level_error=IRError("change set must contain at least one change")
        )
    notes = data.get("notes", "")
    if not isinstance(notes, str):
        return ChangeSetParseResult(
            summary=summary,
            top_level_error=IRError("notes must be a string"),
        )

    parsed: list[Change | None] = []
    problems: list[tuple[int, IRError]] = []
    for index, item in enumerate(raw_changes):
        try:
            parsed.append(Change.from_dict(item))
        except IRError as exc:
            parsed.append(None)
            problems.append((index, exc))
        except Exception as exc:  # pragma: no cover - defensive
            parsed.append(None)
            problems.append((index, IRError(str(exc))))
    return ChangeSetParseResult(
        summary=summary,
        notes=notes,
        changes=parsed,
        problems=problems,
    )


@dataclass
class ChangeSet:
    summary: str
    changes: list[Change]
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Any) -> "ChangeSet":
        result = parse_changeset_partial(data)
        if result.top_level_error is not None:
            raise result.top_level_error
        if result.problems:
            index, error = result.problems[0]
            raise IRError(f"changes[{index}]: {error}") from error
        return cls(
            summary=result.summary,
            changes=[change for change in result.changes if change is not None],
            notes=result.notes,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"summary": self.summary, "changes": []}
        for change in self.changes:
            item: dict[str, Any] = {"action": change.action}
            if change.script_id:
                item["script_id"] = change.script_id
            if change.target:
                item["target"] = change.target
            if change.label:
                item["label"] = change.label
            if change.hat is not None:
                item["hat"] = change.hat.to_dict()
            if change.body:
                item["body"] = [b.to_dict() for b in change.body]
            if change.name:
                item["name"] = change.name
            if change.action == "create_variable":
                item["scope"] = change.scope
                item["initial"] = change.initial
            if change.action == "create_list":
                item["scope"] = change.scope
                item["items"] = list(change.items)
            if change.costumes:
                item["costumes"] = [
                    {"library": ref.library, "name": ref.name} if ref.name else {"library": ref.library}
                    for ref in change.costumes
                ]
            for key in ("x", "y", "direction", "size"):
                value = getattr(change, key)
                if value is not None:
                    item[key] = value
            if change.visible is not None:
                item["visible"] = change.visible
            if change.rotation_style:
                item["rotation_style"] = change.rotation_style
            if change.library:
                item["library"] = change.library
            if change.select:
                item["select"] = True
            out["changes"].append(item)
        if self.notes:
            out["notes"] = self.notes
        return out
