"""AST transpiler for the Scratch-Python dialect.

``transpile(source, context)`` parses a restricted Python reply and builds the
same :class:`~harness.block_ir.ChangeSet` the JSON path produces.  The AST
whitelist, the vocabulary gate and the variable symbol gate all live here; the
validator still runs afterwards and remains the authority on project context.
"""

from __future__ import annotations

import ast
import difflib
from typing import Any

from ..block_ir import Change, ChangeSet, IRError
from ..catalog import SPRITE_TARGET_OPS, ArgSpec, spec_for
from ..context import ProjectContext
from ..media import BACKDROP, COSTUME, MediaError, default_library
from .errors import MAX_DIAGNOSTICS, DSLError, DSLErrors
from .vocab import (
    CALLABLE_SPECS,
    COMMAND_OPS,
    CONTROL_OPS,
    EXPRESSION_OPS,
    FUNCTION_NAMES,
    HAT_SPECS,
    MODULE_CALL_SPECS,
    MODULE_KEYWORD_ALIASES,
    ModuleCallSpec,
    ModuleParam,
    arg_specs,
)

EMPTY_MESSAGE = (
    "the change set is empty; add module-level changes or at least one "
    "decorated script."
)
IMPORT_MESSAGE = (
    "imports are not part of the dialect; every capability is a dialect "
    "function from the reference."
)
NOHAT_MESSAGE = (
    "a script def needs exactly one event decorator, for example "
    '@on_flag(target="Sprite1").'
)
BADHAT_MESSAGE = (
    "unknown decorator @{name}; the event decorators are on_flag, on_key, "
    "on_click, on_stage_click, on_clone_start, on_receive, on_backdrop, "
    "on_loudness, on_timer."
)
DEFARGS_MESSAGE = "script defs take no arguments."
RETURN_MESSAGE = (
    "scripts are not functions; use stop_script() to end a script early."
)
NESTEDDEF_MESSAGE = (
    "helper functions are not supported in Scratch 1.4; split the behavior "
    'into its own decorated script and start it with broadcast("name") / '
    '@on_receive("name").'
)
LAMBDA_MESSAGE = (
    "lambdas are not part of the dialect; control flow uses for/while/if."
)
CLASS_MESSAGE = "classes are not part of the dialect."
SUBSCRIPT_MESSAGE = (
    "indexing is not part of the dialect; use list_item(index, \"list\") - "
    "Scratch list indices start at 1."
)
ATTRIBUTE_MESSAGE = (
    "attribute access is not part of the dialect; use "
    'attribute_of("x position", "sprite") to read another sprite\'s property.'
)
COMPR_MESSAGE = (
    "comprehensions are not part of the dialect; build lists with "
    "add_to_list inside for _ in range(n)."
)
FSTRING_MESSAGE = (
    "f-strings are not part of the dialect yet; join text with "
    '"Score: " + name (a string literal on either side becomes a join block).'
)
TRY_MESSAGE = (
    "try/except is not part of the dialect (Scratch has no exceptions)."
)
BREAK_MESSAGE = (
    "Scratch has no loop break/continue; use a flag variable with "
    "while not flag: (repeat until the flag is set)."
)
PASS_MESSAGE = (
    "empty bodies are not allowed; every control block must contain at least "
    "one statement."
)
UNARYMINUS_MESSAGE = "Scratch has no unary minus; write 0 - x."
CHAINCOMP_MESSAGE = (
    "chained comparisons are not supported; write a < b and b < c."
)
ISIN_MESSAGE = (
    "'in'/'is' comparisons are not part of the dialect; use "
    'list_contains("list", item) or an equality comparison.'
)
BOOLCONST_MESSAGE = (
    "True/False have no Scratch block; conditions need a boolean reporter "
    'such as touching("edge"), key_pressed("space") or a comparison.'
)
NONE_MESSAGE = "None is not part of the dialect."
CMDVALUE_MESSAGE = (
    "{op}() is a command block; it cannot be used as a value."
)
REPSTMT_MESSAGE = (
    "{op}() is a reporter; it cannot stand alone - assign it to a variable "
    "or nest it inside another call."
)
CFLOW_MESSAGE = (
    "do not call {op}() directly; use Python control flow: "
    "for _ in range(n) -> repeat, while True -> forever, "
    "while not cond -> repeat_until, if cond -> if."
)
UNKNOWNFN_MESSAGE = (
    "unknown function {name}(); use only the dialect functions in the "
    "reference."
)
BADKWARG_MESSAGE = "{op}() takes {expected}, not '{name}'."
ARITY_MESSAGE = "{op}() needs {count} argument(s): {names}."
MENU_MESSAGE = "{op}() argument '{arg}' must be one of: {values}."
UNKNOWNVAR_MESSAGE = (
    "unknown variable '{name}'; create it first with "
    'create_variable("{name}", ...) or use a name from the project context.'
)
CROSSVAR_MESSAGE = (
    "'{name}' is a local variable of sprite '{owner}'; another sprite cannot "
    "read it - use attribute_of/set_attribute_of or broadcast to a script "
    "owned by {owner}."
)
TARGET_MESSAGE = "{op} target '{name}' does not exist yet"
SPRITESCOPE_MESSAGE = (
    "{op}() with scope='sprite' needs target='SpriteName'"
)
STAGETARGET_MESSAGE = "{op} target 'Stage' is not a sprite"
UNKNOWNCOSTUME_MESSAGE = "unknown costume '{name}' for '{target}'"
UNKNOWNSOUND_MESSAGE = "unknown sound '{name}' for '{target}'"
UNKNOWNBACKDROP_MESSAGE = "unknown backdrop '{name}'"
MODASSIGN_MESSAGE = (
    "assignments at module level are not part of the dialect; create "
    'variables with create_variable(name, scope="global", initial=...).'
)
MODLITERAL_MESSAGE = (
    "module-level change calls take literal values only (numbers, strings, "
    "booleans, or lists of literals)."
)
COLLIDE_MESSAGE = (
    "variable name '{name}' collides with a dialect function; choose a "
    "different variable name."
)
STAR_MESSAGE = (
    "dialect calls take plain positional or keyword arguments only."
)
LOOPVAR_MESSAGE = (
    "the loop variable must be _ (Scratch repeat has no loop variable); to "
    'walk a list use list_item(i, "list") with a counter variable and while.'
)
RANGE2_MESSAGE = (
    "range(a, b) is not supported yet; write for _ in range(b - a) instead."
)
AMBIGPLUS_MESSAGE = (
    "'+' between two computed values is ambiguous in Scratch; write "
    "join(a, b) to build text or add(a, b) to add numbers."
)
CONDITION_MESSAGE = (
    "condition must be a boolean reporter such as touching(\"edge\"), "
    'key_pressed("space") or a comparison.'
)
SYNTAX_SUFFIX = (
    " Reply with one fenced python block containing only dialect code."
)


def _line(node: ast.AST) -> int | None:
    return getattr(node, "lineno", None)


def _strip_code_fences(source: str) -> str:
    """Remove one surrounding Markdown fence from a model reply.

    Any info string is accepted (``python``, ``json``, empty).  Prose before a
    fence is deliberately left alone so the Python parser reports it as a
    syntax error at its line.
    """
    text = source.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    body = lines[1:]
    if body and body[-1].strip().startswith("```"):
        body = body[:-1]
    return "\n".join(body).strip("\n")


def _is_number_constant(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    )


def _is_scalar_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return not isinstance(node.value, (bytes, complex)) and node.value is not Ellipsis
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _is_number_constant(node.operand)
    return False


def _is_string_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _duplicate_argument(op: str, name: str, line: int | None) -> DSLError:
    return DSLError(
        f"{op}() got multiple values for argument '{name}'.",
        line=line,
        hint="pass each argument once, positionally or by keyword.",
    )


def _truncate_names(names: list[str], limit: int = 12) -> str:
    """Comma-joined sorted names, capped so a hint stays one readable line."""
    ordered = sorted(dict.fromkeys(names), key=str.casefold)
    if not ordered:
        return "none"
    if len(ordered) <= limit:
        return ", ".join(ordered)
    remaining = len(ordered) - limit
    return ", ".join(ordered[:limit]) + f", ... ({remaining} more)"


def _quote_names(names: list[str]) -> str:
    return ", ".join(repr(name) for name in names)


def _library_stem(path: str) -> str:
    """Costume/backdrop name Scratch derives from a library path."""
    name = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    stem, dot, _ = name.rpartition(".")
    return stem if dot and stem else name


def _media_error(exc: MediaError, line: int | None) -> DSLError:
    """Turn a resolver failure into a diagnostic with the suggestions as hint."""
    message = str(exc)
    hint = None
    if exc.suggestions:
        suffix = "; near matches: " + ", ".join(exc.suggestions)
        if message.endswith(suffix):
            message = message[: -len(suffix)]
        hint = "near matches: " + ", ".join(exc.suggestions)
    return DSLError(message, line=line, hint=hint)


class _Transpiler:
    """One reply's walk over the AST."""

    def __init__(self, context: ProjectContext | None):
        self.context = context
        self.errors: list[DSLError] = []
        self.changes: list[Change] = []
        self.summary = "Updated the project."
        self.notes = ""
        #: True once a module-level ``summary``/``notes`` call was seen, so a
        #: metadata-only module is a legal acknowledgment instead of EMPTY.
        self.saw_reply_metadata = False
        self.created_globals: set[str] = set()
        self.created_sprite_vars: dict[str, set[str]] = {}
        #: Costume/backdrop names this module already added, per target.
        self.created_costumes: dict[str, set[str]] = {}
        self.sprite_names: set[str] = set(
            context.sprite_names() if context is not None else ()
        )
        self.current_target = ""

    # -- collection ------------------------------------------------------

    def _full(self) -> bool:
        return len(self.errors) >= MAX_DIAGNOSTICS

    def _add(self, error: DSLError) -> None:
        if not self._full():
            self.errors.append(error)

    def _emit(self, data: dict[str, Any], line: int | None) -> bool:
        try:
            change = Change.from_dict(data)
        except IRError as exc:
            self._add(DSLError(str(exc), line=line))
            return False
        self.changes.append(change)
        return True

    def run(self, module: ast.Module) -> ChangeSet:
        for node in module.body:
            if self._full():
                break
            try:
                self._module_stmt(node)
            except DSLError as exc:
                self._add(exc)
        if not self.changes and not self.errors and not self.saw_reply_metadata:
            self.errors.append(DSLError(EMPTY_MESSAGE))
        if self.errors:
            raise DSLErrors(self.errors)
        return ChangeSet(summary=self.summary, changes=self.changes, notes=self.notes)

    # -- module level ----------------------------------------------------

    def _module_stmt(self, node: ast.stmt) -> None:
        if isinstance(node, ast.Expr):
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return  # module docstring
            if isinstance(value, ast.Call):
                self._module_call(value)
                return
            self._expr(value)  # surface a precise sub-expression diagnostic
            raise DSLError(
                "only change calls and decorated script defs are allowed at "
                "module level.",
                line=_line(value),
            )
        if isinstance(node, ast.FunctionDef):
            self._def(node)
            return
        if isinstance(node, ast.AsyncFunctionDef):
            raise DSLError(
                "async scripts are not part of the dialect; use a plain "
                "decorated def.",
                line=node.lineno,
            )
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            raise DSLError(MODASSIGN_MESSAGE, line=node.lineno)
        if isinstance(node, (ast.For, ast.While, ast.If)):
            raise DSLError(
                "control flow belongs inside a decorated script def.",
                line=node.lineno,
            )
        raise self._statement_rejection(node)

    def _module_call(self, call: ast.Call) -> None:
        func = call.func
        if not isinstance(func, ast.Name):
            raise self._expression_rejection(func)
        name = func.id
        spec = MODULE_CALL_SPECS.get(name)
        if spec is None:
            if name in CONTROL_OPS:
                raise DSLError(
                    "control flow belongs inside a decorated script def.",
                    line=call.lineno,
                )
            if name in CALLABLE_SPECS:
                raise DSLError(
                    f"{name}() is a script block; put it inside a decorated "
                    "script def.",
                    line=call.lineno,
                )
            if name in HAT_SPECS:
                raise DSLError(
                    f"@{name} is an event decorator; it cannot be called.",
                    line=call.lineno,
                )
            raise DSLError(
                UNKNOWNFN_MESSAGE.format(name=name), line=call.lineno
            )
        values, raw = self._bind_module(spec, call)
        if not spec.action:
            self.saw_reply_metadata = True
            if name == "summary":
                self.summary = values["text"]
            else:
                self.notes = values["text"]
            return
        if spec.action == "create_variable":
            variable = values["name"]
            if variable in FUNCTION_NAMES:
                raise DSLError(
                    COLLIDE_MESSAGE.format(name=variable), line=call.lineno
                )
        self._check_module_target(spec, values, call.lineno)
        self._check_module_media(spec, values, raw, call.lineno)
        data: dict[str, Any] = {"action": spec.action}
        for param in spec.params:
            if param.name in values and values[param.name] is not None:
                data[param.name] = values[param.name]
        if not self._emit(data, call.lineno):
            return
        if spec.action == "create_variable":
            scope = values.get("scope", "global")
            target = values.get("target")
            if scope == "sprite" and target:
                self.created_sprite_vars.setdefault(target, set()).add(variable)
            else:
                self.created_globals.add(variable)
        elif spec.action == "create_sprite":
            self.sprite_names.add(values["name"])
            self.created_costumes[values["name"]] = self._created_costume_names(
                values
            )
        elif spec.action == "duplicate_sprite":
            self.sprite_names.add(values["name"])
            self.created_costumes[values["name"]] = set(
                self._known_costumes(values["target"])
            )
        elif spec.action == "delete_sprite":
            self.sprite_names.discard(values["target"])
            self.created_costumes.pop(values["target"], None)
        elif spec.action == "add_costume":
            name = values.get("name") or _library_stem(values["library"])
            self.created_costumes.setdefault(values["target"], set()).add(name)
        elif spec.action == "set_backdrop":
            name = values.get("name") or _library_stem(values["library"])
            self.created_costumes.setdefault("Stage", set()).add(name)

    def _bind_module(
        self, spec: ModuleCallSpec, call: ast.Call
    ) -> tuple[dict[str, Any], dict[str, ast.expr]]:
        names = [param.name for param in spec.params]
        by_name = {param.name: param for param in spec.params}
        if len(call.args) > len(names):
            raise DSLError(
                ARITY_MESSAGE.format(
                    op=spec.name, count=len(names), names=", ".join(names)
                ),
                line=call.lineno,
            )
        raw: dict[str, ast.expr] = {}
        for index, node in enumerate(call.args):
            if isinstance(node, ast.Starred):
                raise DSLError(STAR_MESSAGE, line=_line(node))
            raw[names[index]] = node
        for keyword in call.keywords:
            if keyword.arg is None:
                raise DSLError(STAR_MESSAGE, line=call.lineno)
            keyword_name = MODULE_KEYWORD_ALIASES.get(
                keyword.arg, keyword.arg
            )
            if keyword_name not in by_name:
                raise DSLError(
                    BADKWARG_MESSAGE.format(
                        op=spec.name,
                        expected=", ".join(names),
                        name=keyword.arg,
                    ),
                    line=call.lineno,
                )
            if keyword_name in raw:
                raise _duplicate_argument(
                    spec.name, keyword_name, call.lineno
                )
            raw[keyword_name] = keyword.value
        missing = [
            param.name
            for param in spec.params
            if param.required and param.name not in raw
        ]
        if missing:
            raise DSLError(
                f"{spec.name}() needs a value for {', '.join(missing)}.",
                line=call.lineno,
            )
        values: dict[str, Any] = {}
        for param in spec.params:
            if param.name not in raw:
                continue
            literal = self._module_literal(raw[param.name])
            values[param.name] = self._check_module_type(
                spec, param, literal, raw[param.name]
            )
        return values, raw

    def _module_literal(self, node: ast.expr) -> Any:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (bytes, complex)) or node.value is Ellipsis:
                raise DSLError(MODLITERAL_MESSAGE, line=_line(node))
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(
            node.op, (ast.USub, ast.UAdd)
        ):
            if _is_number_constant(node.operand):
                number = node.operand.value
                return -number if isinstance(node.op, ast.USub) else number
            raise DSLError(MODLITERAL_MESSAGE, line=_line(node))
        if isinstance(node, ast.List):
            values: list[Any] = []
            for item in node.elts:
                if isinstance(item, ast.Starred):
                    raise DSLError(STAR_MESSAGE, line=_line(item))
                value = self._module_literal(item)
                if isinstance(value, list):
                    raise DSLError(MODLITERAL_MESSAGE, line=_line(item))
                values.append(value)
            return values
        raise DSLError(MODLITERAL_MESSAGE, line=_line(node))

    def _check_module_type(
        self,
        spec: ModuleCallSpec,
        param: ModuleParam,
        value: Any,
        node: ast.expr,
    ) -> Any:
        line = _line(node)
        if value is None:
            if param.required:
                raise DSLError(
                    f"{spec.name}() needs a value for {param.name}.", line=line
                )
            return None
        if param.type in {"scope", "rotation"}:
            if not isinstance(value, str) or value not in param.menu:
                raise DSLError(
                    MENU_MESSAGE.format(
                        op=spec.name,
                        arg=param.name,
                        values=", ".join(param.menu),
                    ),
                    line=line,
                )
            return value
        if param.type == "string":
            if not isinstance(value, str):
                raise DSLError(
                    f"{spec.name}() argument '{param.name}' must be a string.",
                    line=line,
                )
        elif param.type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DSLError(
                    f"{spec.name}() argument '{param.name}' must be a number.",
                    line=line,
                )
        elif param.type == "bool":
            if not isinstance(value, bool):
                raise DSLError(
                    f"{spec.name}() argument '{param.name}' must be true or "
                    "false.",
                    line=line,
                )
        elif param.type == "strings":
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise DSLError(
                    f"{spec.name}() argument '{param.name}' must be a list of "
                    "strings.",
                    line=line,
                )
        elif param.type == "literals":
            if not isinstance(value, list) or not all(
                isinstance(item, (str, int, float, bool)) for item in value
            ):
                raise DSLError(
                    f"{spec.name}() argument '{param.name}' must be a list of "
                    "literals.",
                    line=line,
                )
        elif param.type == "any":
            if isinstance(value, list):
                raise DSLError(
                    f"{spec.name}() argument '{param.name}' must be a single "
                    "literal value.",
                    line=line,
                )
        return value

    # -- context and media gates -----------------------------------------

    def _valid_targets(self) -> list[str]:
        names = ["Stage"]
        names.extend(
            sorted(
                (name for name in self.sprite_names if name != "Stage"),
                key=str.casefold,
            )
        )
        return names

    def _sprites_hint(self, name: str | None = None) -> str:
        valid = sorted(self.sprite_names, key=str.casefold)
        parts: list[str] = []
        if name is not None:
            close = difflib.get_close_matches(name, valid, n=3, cutoff=0.6)
            if close:
                parts.append("did you mean " + _quote_names(close) + "?")
            else:
                parts.append(
                    f"create it first with create_sprite({name!r}, ...)."
                )
        parts.append("valid sprite targets: " + _truncate_names(valid) + ".")
        return " ".join(parts)

    def _target_hint(self, name: str) -> str:
        valid = self._valid_targets()
        close = difflib.get_close_matches(name, valid, n=3, cutoff=0.6)
        if close:
            first = "did you mean " + _quote_names(close) + "?"
        else:
            first = f"create it first with create_sprite({name!r}, ...)."
        return first + " valid targets: " + _truncate_names(valid) + "."

    def _check_module_target(
        self, spec: ModuleCallSpec, values: dict[str, Any], line: int | None
    ) -> None:
        """Reject module changes aimed at a sprite the project does not have."""
        if self.context is None:
            return
        if spec.action in {"create_variable", "create_list"}:
            if values.get("scope", "global") != "sprite":
                return
            target = values.get("target")
            if not target:
                raise DSLError(
                    SPRITESCOPE_MESSAGE.format(op=spec.name),
                    line=line,
                    hint=self._sprites_hint(),
                )
            self._require_known_sprite(target, line, f"{spec.name}()")
            return
        if spec.action in {
            "duplicate_sprite",
            "delete_sprite",
            "set_sprite",
            "add_costume",
        }:
            self._require_known_sprite(
                values["target"],
                line,
                f"{spec.name}()",
                allow_stage=spec.action == "add_costume",
            )

    def _require_known_sprite(
        self, name: str, line: int | None, op: str, allow_stage: bool = False
    ) -> None:
        if self.context is None:
            return
        if name.casefold() == "stage":
            if allow_stage:
                return
            raise DSLError(
                STAGETARGET_MESSAGE.format(op=op),
                line=line,
                hint=self._sprites_hint(),
            )
        if name in self.sprite_names:
            return
        raise DSLError(
            TARGET_MESSAGE.format(op=op, name=name),
            line=line,
            hint=self._target_hint(name),
        )

    def _check_module_media(
        self,
        spec: ModuleCallSpec,
        values: dict[str, Any],
        raw: dict[str, ast.expr],
        default_line: int | None,
    ) -> None:
        """Resolve library paths and presets while the module call is parsed."""
        jobs: list[tuple[str, str, int | None]] = []
        if spec.action == "create_sprite":
            costumes = raw.get("costumes")
            for index, path in enumerate(values.get("costumes") or []):
                line = default_line
                if isinstance(costumes, ast.List) and index < len(costumes.elts):
                    line = _line(costumes.elts[index])
                jobs.append((COSTUME, path, line))
            preset = values.get("preset")
            if preset is not None:
                jobs.append(("preset", preset, _line(raw["preset"])))
        elif spec.action == "add_costume" and values.get("library"):
            target = str(values.get("target", ""))
            kind = BACKDROP if target.casefold() == "stage" else COSTUME
            jobs.append((kind, values["library"], _line(raw["library"])))
        elif spec.action == "set_backdrop" and values.get("library"):
            jobs.append(
                (BACKDROP, values["library"], _line(raw["library"]))
            )
        if not jobs:
            return
        if not self._has_media_knowledge():
            return
        library = default_library()
        if not library.assets():
            return
        for kind, query, line in jobs:
            try:
                if kind == "preset":
                    library.resolve_sprite(query)
                else:
                    library.resolve(kind, query)
            except MediaError as exc:
                raise _media_error(exc, line) from None

    def _has_media_knowledge(self) -> bool:
        """Whether the context reports costumes/sounds to compare against.

        A live project always does. A context built for a script-only replay
        (the historical round-trip corpus) does not, and its media names come
        from a different stock library generation, so resolving them against
        the installed tree would report false failures.
        """
        if self.context is None:
            return True
        return any(
            sprite.costumes or sprite.sounds
            for sprite in self.context.sprites.values()
        )

    def _created_costume_names(self, values: dict[str, Any]) -> set[str]:
        names = {_library_stem(path) for path in values.get("costumes") or []}
        preset_name = values.get("preset")
        if preset_name:
            try:
                preset = default_library().resolve_sprite(preset_name)
            except MediaError:
                pass
            else:
                names.update(entry.name for entry in preset.costumes)
        return names

    def _known_costumes(self, target: str) -> set[str]:
        known = set(self.created_costumes.get(target, ()))
        if self.context is not None:
            sprite = self.context.sprites.get(target)
            if sprite is not None:
                known.update(sprite.costumes)
        return known

    def _known_sounds(self, target: str) -> set[str]:
        if self.context is None:
            return set()
        sprite = self.context.sprites.get(target)
        return set(sprite.sounds) if sprite is not None else set()

    def _known_backdrops(self) -> set[str]:
        return self._known_costumes("Stage")

    def _known_hint(
        self, label: str, known: set[str], name: str
    ) -> str:
        pool = sorted(known, key=str.casefold)
        close = difflib.get_close_matches(name, pool, n=3, cutoff=0.55)
        listing = f"{label}: {_truncate_names(pool)}."
        if close:
            return "did you mean " + _quote_names(close) + "? " + listing
        return listing

    def _check_command_name(
        self, op: str, arg: str, value: str, line: int | None
    ) -> None:
        if self.context is None:
            return
        if op == "switch_costume" and arg == "costume":
            known = self._known_costumes(self.current_target)
            if known and value not in known:
                raise DSLError(
                    UNKNOWNCOSTUME_MESSAGE.format(
                        name=value, target=self.current_target
                    ),
                    line=line,
                    hint=self._known_hint(
                        f"costumes of '{self.current_target}'", known, value
                    ),
                )
        elif op in {"play_sound", "play_sound_until_done"} and arg == "sound":
            known = self._known_sounds(self.current_target)
            if known and value not in known:
                raise DSLError(
                    UNKNOWNSOUND_MESSAGE.format(
                        name=value, target=self.current_target
                    ),
                    line=line,
                    hint=self._known_hint(
                        f"sounds of '{self.current_target}'", known, value
                    ),
                )
        elif op == "switch_backdrop" and arg == "backdrop":
            known = self._known_backdrops()
            if known and value not in known:
                raise DSLError(
                    UNKNOWNBACKDROP_MESSAGE.format(name=value),
                    line=line,
                    hint=self._known_hint("Stage backdrops", known, value),
                )

    # -- decorated defs --------------------------------------------------

    def _def(self, node: ast.FunctionDef) -> None:
        if len(node.decorator_list) != 1:
            raise DSLError(NOHAT_MESSAGE, line=node.lineno)
        decorator = node.decorator_list[0]
        name = _decorator_name(decorator)
        if name not in HAT_SPECS:
            raise DSLError(
                BADHAT_MESSAGE.format(name=name), line=_line(decorator)
            )
        if self._has_annotations(node):
            raise DSLError(
                "annotations are not part of the dialect; remove the "
                "annotation.",
                line=node.lineno,
            )
        if _has_arguments(node.args):
            raise DSLError(DEFARGS_MESSAGE, line=node.lineno)
        target, label, script_id, hat = self._decorator(
            decorator, name, node.name
        )
        self.current_target = target
        try:
            body = self._body(node.body)
        finally:
            self.current_target = ""
        has_script_id = script_id is not None
        data: dict[str, Any] = {
            "action": "replace_script" if has_script_id else "add_script",
            "target": target,
            "label": label,
            "hat": hat,
            "body": body,
        }
        if has_script_id:
            data["script_id"] = script_id
        self._emit(data, node.lineno)

    @staticmethod
    def _has_annotations(node: ast.FunctionDef) -> bool:
        arguments = node.args
        every = [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ]
        if arguments.vararg is not None:
            every.append(arguments.vararg)
        if arguments.kwarg is not None:
            every.append(arguments.kwarg)
        return node.returns is not None or any(
            arg.annotation is not None for arg in every
        )

    def _decorator(
        self, decorator: ast.expr, name: str, def_name: str
    ) -> tuple[str, str, str | None, dict[str, Any]]:
        op = HAT_SPECS[name]
        specs = arg_specs(op)
        hat_names = [arg.name for arg in specs]
        reserved = ["target", "label", "script_id"]
        allowed = [*hat_names, *reserved]
        if isinstance(decorator, ast.Call):
            args = decorator.args
            keywords = decorator.keywords
        else:
            args = []
            keywords = []
        line = _line(decorator)
        if len(args) > len(hat_names):
            raise DSLError(
                ARITY_MESSAGE.format(
                    op=name,
                    count=len(hat_names),
                    names=", ".join(hat_names),
                ),
                line=line,
            )
        raw: dict[str, ast.expr] = {}
        for index, node in enumerate(args):
            if isinstance(node, ast.Starred):
                raise DSLError(STAR_MESSAGE, line=_line(node))
            raw[hat_names[index]] = node
        for keyword in keywords:
            if keyword.arg is None:
                raise DSLError(STAR_MESSAGE, line=line)
            if keyword.arg not in allowed:
                raise DSLError(
                    BADKWARG_MESSAGE.format(
                        op=name,
                        expected=", ".join(allowed),
                        name=keyword.arg,
                    ),
                    line=line,
                )
            if keyword.arg in raw:
                raise _duplicate_argument(name, keyword.arg, line)
            raw[keyword.arg] = keyword.value
        missing = [hat_name for hat_name in hat_names if hat_name not in raw]
        if missing:
            raise DSLError(
                ARITY_MESSAGE.format(
                    op=name,
                    count=len(hat_names),
                    names=", ".join(hat_names),
                ),
                line=line,
            )
        target_node = raw.pop("target", None)
        if target_node is None:
            raise DSLError(
                f'{name}() needs target="SpriteName".', line=line
            )
        target = self._decorator_string(name, "target", target_node)
        if target.casefold() == "stage":
            target = "Stage"
        elif self.context is not None and target not in self.sprite_names:
            raise DSLError(
                TARGET_MESSAGE.format(op=f"@{name}()", name=target),
                line=_line(target_node),
                hint=self._target_hint(target),
            )
        label = def_name
        if "label" in raw:
            label = self._decorator_string(name, "label", raw["label"])
        script_id: str | None = None
        if "script_id" in raw:
            script_id = self._decorator_string(
                name, "script_id", raw["script_id"]
            )
        hat: dict[str, Any] = {"op": op}
        args_out: dict[str, Any] = {}
        for spec in specs:
            if spec.name not in raw:
                continue
            args_out[spec.name] = self._hat_value(
                name, spec.name, spec.type, spec.menu, raw[spec.name]
            )
        if args_out:
            hat["args"] = args_out
        return target, label, script_id, hat

    def _decorator_string(
        self, decorator: str, field: str, node: ast.expr
    ) -> str:
        value = self._module_scalar(node)
        if not isinstance(value, str):
            raise DSLError(
                f"{decorator}() {field} must be a string literal.",
                line=_line(node),
            )
        return value

    def _hat_value(
        self,
        decorator: str,
        arg_name: str,
        arg_type: str,
        menu: tuple[str, ...],
        node: ast.expr,
    ) -> Any:
        value = self._module_scalar(node)
        if arg_type == "menu":
            if not isinstance(value, str) or (menu and value not in menu):
                raise DSLError(
                    MENU_MESSAGE.format(
                        op=decorator, arg=arg_name, values=", ".join(menu)
                    ),
                    line=_line(node),
                )
        elif arg_type == "string":
            if not isinstance(value, str):
                raise DSLError(
                    f"{decorator}() argument '{arg_name}' must be a string.",
                    line=_line(node),
                )
        elif arg_type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DSLError(
                    f"{decorator}() argument '{arg_name}' must be a number.",
                    line=_line(node),
                )
        return value

    def _module_scalar(self, node: ast.expr) -> Any:
        value = self._module_literal(node)
        if isinstance(value, list):
            raise DSLError(MODLITERAL_MESSAGE, line=_line(node))
        return value

    # -- statements ------------------------------------------------------

    def _body(self, statements: list[ast.stmt]) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for node in statements:
            if self._full():
                break
            try:
                block = self._stmt(node)
            except DSLError as exc:
                self._add(exc)
                continue
            if block is not None:
                blocks.append(block)
        return blocks

    def _stmt(self, node: ast.stmt) -> dict[str, Any] | None:
        if isinstance(node, ast.Expr):
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return None  # inner docstring
            if isinstance(value, ast.Call):
                return self._expr_stmt(value)
            self._expr(value)  # surface a precise sub-expression diagnostic
            raise DSLError(
                "an expression cannot stand alone; assign it to a variable "
                "or call a command.",
                line=_line(value),
            )
        if isinstance(node, ast.Assign):
            return self._assign(node)
        if isinstance(node, ast.AugAssign):
            return self._augassign(node)
        if isinstance(node, ast.For):
            return self._for(node)
        if isinstance(node, ast.While):
            return self._while(node)
        if isinstance(node, ast.If):
            return self._if_block(node)
        raise self._statement_rejection(node)

    def _expression_rejection(self, node: ast.AST) -> DSLError:
        line = _line(node)
        if isinstance(node, ast.Subscript):
            return DSLError(SUBSCRIPT_MESSAGE, line=line)
        if isinstance(node, ast.Attribute):
            return DSLError(ATTRIBUTE_MESSAGE, line=line)
        if isinstance(
            node,
            (
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
            ),
        ):
            return DSLError(COMPR_MESSAGE, line=line)
        if isinstance(node, ast.JoinedStr):
            return DSLError(FSTRING_MESSAGE, line=line)
        if isinstance(node, ast.Lambda):
            return DSLError(LAMBDA_MESSAGE, line=line)
        if isinstance(node, ast.Starred):
            return DSLError(STAR_MESSAGE, line=line)
        if isinstance(node, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
            return DSLError(
                "lists, tuples and dictionaries are not values in the "
                "dialect; use a Scratch list (create_list, list_item) instead.",
                line=line,
            )
        if isinstance(node, ast.IfExp):
            return DSLError(
                "conditional expressions are not part of the dialect; use "
                "if/else with a variable.",
                line=line,
            )
        if isinstance(node, ast.NamedExpr):
            return DSLError(
                "assignment expressions are not part of the dialect.",
                line=line,
            )
        if isinstance(node, (ast.Yield, ast.YieldFrom, ast.Await)):
            return DSLError(
                "generators and async are not part of the dialect.",
                line=line,
            )
        return DSLError(
            f"{type(node).__name__} is not part of the dialect.", line=line
        )

    def _statement_rejection(self, node: ast.stmt) -> DSLError:
        line = _line(node)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return DSLError(IMPORT_MESSAGE, line=line)
        if isinstance(node, ast.ClassDef):
            return DSLError(CLASS_MESSAGE, line=line)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return DSLError(NESTEDDEF_MESSAGE, line=line)
        if isinstance(node, ast.Return):
            return DSLError(RETURN_MESSAGE, line=line)
        if isinstance(node, (ast.Break, ast.Continue)):
            return DSLError(BREAK_MESSAGE, line=line)
        if isinstance(node, (ast.Try, ast.TryStar)):
            return DSLError(TRY_MESSAGE, line=line)
        if isinstance(node, ast.Pass):
            return DSLError(PASS_MESSAGE, line=line)
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return DSLError(
                "global/nonlocal statements are not part of the dialect.",
                line=line,
            )
        if isinstance(node, ast.Raise):
            return DSLError(
                "raise is not part of the dialect (Scratch has no "
                "exceptions).",
                line=line,
            )
        if isinstance(node, ast.Assert):
            return DSLError(
                "assert is not part of the dialect; use if not cond: instead.",
                line=line,
            )
        if isinstance(node, ast.Delete):
            return DSLError(
                "del is not part of the dialect; use delete_from_list or "
                "delete_sprite at module level.",
                line=line,
            )
        if isinstance(node, (ast.With, ast.AsyncWith)):
            return DSLError(
                "with blocks are not part of the dialect.", line=line
            )
        if isinstance(node, (ast.AnnAssign,)):
            return DSLError(
                "annotations are not part of the dialect.", line=line
            )
        if isinstance(node, ast.Match):
            return DSLError(
                "match statements are not part of the dialect; use if/elif.",
                line=line,
            )
        return DSLError(
            "this statement is not part of the dialect.", line=line
        )

    def _expr_stmt(self, call: ast.Call) -> dict[str, Any]:
        func = call.func
        if not isinstance(func, ast.Name):
            raise self._expression_rejection(func)
        name = func.id
        if name in CONTROL_OPS:
            raise DSLError(CFLOW_MESSAGE.format(op=name), line=call.lineno)
        if name in COMMAND_OPS:
            spec = CALLABLE_SPECS[name]
            args = self._bind_op_args(name, spec.args, call)
            block: dict[str, Any] = {"op": name}
            if args:
                block["args"] = args
            return block
        if name in EXPRESSION_OPS:
            raise DSLError(REPSTMT_MESSAGE.format(op=name), line=call.lineno)
        if name in MODULE_CALL_SPECS:
            raise DSLError(
                f"{name}() is a module-level change call; move it outside "
                "the script def.",
                line=call.lineno,
            )
        if name in HAT_SPECS:
            raise DSLError(
                f"@{name} is an event decorator; it cannot be called inside "
                "a script.",
                line=call.lineno,
            )
        raise DSLError(UNKNOWNFN_MESSAGE.format(name=name), line=call.lineno)

    def _assign(self, node: ast.Assign) -> dict[str, Any]:
        if len(node.targets) != 1:
            raise DSLError(
                "chained assignment is not part of the dialect; assign one "
                "variable at a time.",
                line=node.lineno,
            )
        name = self._assignment_target(node.targets[0])
        value = self._expr(node.value)
        return {"op": "set_var", "args": {"name": name, "value": value}}

    def _augassign(self, node: ast.AugAssign) -> dict[str, Any]:
        name = self._assignment_target(node.target)
        if isinstance(node.op, ast.Add):
            return {
                "op": "change_var",
                "args": {"name": name, "delta": self._expr(node.value)},
            }
        if isinstance(node.op, ast.Sub):
            if _is_number_constant(node.value):
                return {
                    "op": "change_var",
                    "args": {"name": name, "delta": -node.value.value},
                }
            raise DSLError(
                "augmented subtraction only accepts a number literal; write "
                f"{name} = {name} - expr instead.",
                line=node.lineno,
                hint=(
                    f"use set_var with the subtract block: {name} = {name} - "
                    "expr"
                ),
            )
        symbol, block_name = _AUGMENTED_OPERATORS.get(
            type(node.op), ("?", "operator")
        )
        raise DSLError(
            f"augmented assignment with '{symbol}' is not supported.",
            line=node.lineno,
            hint=(
                f"write {name} = {name} {symbol} 2 (set_var with the "
                f"{block_name} block)"
            ),
        )

    def _assignment_target(self, node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return self._variable_name(node)
        if isinstance(node, ast.Subscript):
            raise DSLError(SUBSCRIPT_MESSAGE, line=_line(node))
        if isinstance(node, ast.Attribute):
            raise DSLError(ATTRIBUTE_MESSAGE, line=_line(node))
        if isinstance(node, (ast.Tuple, ast.List)):
            raise DSLError(
                "tuple unpacking is not part of the dialect; assign one "
                "variable at a time.",
                line=_line(node),
            )
        if isinstance(node, ast.Starred):
            raise DSLError(STAR_MESSAGE, line=_line(node))
        raise DSLError(
            "this assignment target is not part of the dialect.",
            line=_line(node),
        )

    def _for(self, node: ast.For) -> dict[str, Any]:
        target = node.target
        if not isinstance(target, ast.Name) or target.id != "_":
            raise DSLError(LOOPVAR_MESSAGE, line=_line(target) or node.lineno)
        call = node.iter
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "range"
        ):
            raise DSLError(
                "for loops only support range(n); to walk a list use "
                'list_item(i, "list") with a counter variable and while.',
                line=_line(call) or node.lineno,
            )
        if call.keywords or len(call.args) != 1:
            raise DSLError(RANGE2_MESSAGE, line=call.lineno)
        count = self._expr(call.args[0])
        body = self._body(node.body)
        return {"op": "repeat", "args": {"count": count}, "body": body}

    def _while(self, node: ast.While) -> dict[str, Any]:
        body = self._body(node.body)
        test = node.test
        if isinstance(test, ast.Constant) and test.value is True:
            return {"op": "forever", "body": body}
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            condition = self._expr(test.operand)
        else:
            condition = {
                "op": "not",
                "args": {"a": self._expr(test)},
            }
        return {
            "op": "repeat_until",
            "args": {"condition": condition},
            "body": body,
        }

    def _if_block(self, node: ast.If) -> dict[str, Any]:
        condition = self._condition(node.test)
        body = self._body(node.body)
        if not node.orelse:
            return {"op": "if", "args": {"condition": condition}, "body": body}
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            nested = self._if_block(node.orelse[0])
            return {
                "op": "if_else",
                "args": {"condition": condition},
                "then": body,
                "else": [nested],
            }
        return {
            "op": "if_else",
            "args": {"condition": condition},
            "then": body,
            "else": self._body(node.orelse),
        }

    def _condition(self, node: ast.expr) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            raise DSLError(BOOLCONST_MESSAGE, line=_line(node))
        value = self._expr(node)
        if self._is_boolean(value):
            return value
        raise DSLError(CONDITION_MESSAGE, line=_line(node))

    @staticmethod
    def _is_boolean(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        spec = spec_for(value.get("op", ""))
        return spec is not None and spec.kind == "boolean"

    # -- expressions -----------------------------------------------------

    def _expr(self, node: ast.expr) -> Any:
        if isinstance(node, ast.Call):
            return self._expr_call(node)
        if isinstance(node, ast.Name):
            return self._name(node)
        if isinstance(node, ast.Constant):
            return self._constant(node)
        if isinstance(node, ast.Compare):
            return self._compare(node)
        if isinstance(node, ast.BoolOp):
            return self._boolop(node)
        if isinstance(node, ast.UnaryOp):
            return self._unary(node)
        if isinstance(node, ast.BinOp):
            return self._binop(node)
        raise self._expression_rejection(node)

    def _expr_call(self, call: ast.Call) -> Any:
        func = call.func
        if not isinstance(func, ast.Name):
            raise self._expression_rejection(func)
        name = func.id
        if name in CONTROL_OPS:
            raise DSLError(CFLOW_MESSAGE.format(op=name), line=call.lineno)
        if name in COMMAND_OPS:
            raise DSLError(CMDVALUE_MESSAGE.format(op=name), line=call.lineno)
        if name in CALLABLE_SPECS:
            spec = CALLABLE_SPECS[name]
            args = self._bind_op_args(name, spec.args, call)
            block: dict[str, Any] = {"op": name}
            if args:
                block["args"] = args
            return block
        if name in MODULE_CALL_SPECS:
            raise DSLError(
                f"{name}() is a module-level change call; it cannot be used "
                "as a value.",
                line=call.lineno,
            )
        if name in HAT_SPECS:
            raise DSLError(
                f"@{name} is an event decorator; it cannot be used as a "
                "value.",
                line=call.lineno,
            )
        raise DSLError(UNKNOWNFN_MESSAGE.format(name=name), line=call.lineno)

    def _name(self, node: ast.Name) -> dict[str, Any]:
        name = node.id
        if name == "_":
            raise DSLError(
                "_ is only a loop placeholder; read a named variable instead.",
                line=_line(node),
            )
        if name in FUNCTION_NAMES:
            if name in HAT_SPECS:
                raise DSLError(
                    f"@{name} is an event decorator; did you mean "
                    f"@{name}(...)?",
                    line=_line(node),
                )
            raise DSLError(
                f"'{name}' is a dialect function; did you mean {name}(...)?",
                line=_line(node),
            )
        self._check_variable(name, _line(node))
        return {"op": "get_var", "args": {"name": name}}

    def _variable_name(self, node: ast.Name) -> str:
        name = node.id
        if name == "_":
            raise DSLError(
                "the name _ is reserved for loop targets; choose a real "
                "variable name.",
                line=_line(node),
            )
        if name in FUNCTION_NAMES:
            raise DSLError(
                f"'{name}' is a dialect function, not a variable; did you "
                f"mean {name}(...)?",
                line=_line(node),
            )
        self._check_variable(name, _line(node))
        return name

    def _check_variable(self, name: str, line: int | None) -> None:
        if self.context is None:
            return
        if name in self._known_variables():
            return
        owner = self._local_owner(name)
        if owner is not None:
            raise DSLError(
                CROSSVAR_MESSAGE.format(name=name, owner=owner), line=line
            )
        raise DSLError(UNKNOWNVAR_MESSAGE.format(name=name), line=line)

    def _known_variables(self) -> set[str]:
        known = set(self.created_globals)
        if self.context is not None:
            known.update(self.context.stage_variables)
            stage = self.context.sprites.get("Stage")
            if stage is not None:
                known.update(stage.variables)
            sprite = self.context.sprites.get(self.current_target)
            if sprite is not None:
                known.update(sprite.variables)
        known.update(self.created_sprite_vars.get(self.current_target, set()))
        return known

    def _local_owner(self, name: str) -> str | None:
        if self.context is not None:
            for sprite_name, sprite in self.context.sprites.items():
                if sprite_name in {"Stage", self.current_target}:
                    continue
                if name in sprite.variables:
                    return sprite_name
        for target, names in self.created_sprite_vars.items():
            if target != self.current_target and name in names:
                return target
        return None

    def _constant(self, node: ast.Constant) -> Any:
        value = node.value
        if isinstance(value, bool):
            raise DSLError(BOOLCONST_MESSAGE, line=_line(node))
        if value is None:
            raise DSLError(NONE_MESSAGE, line=_line(node))
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            return value
        raise DSLError(
            "only numbers, strings and true/false are literals in the "
            "dialect.",
            line=_line(node),
        )

    def _compare(self, node: ast.Compare) -> dict[str, Any]:
        if len(node.ops) != 1:
            raise DSLError(CHAINCOMP_MESSAGE, line=_line(node))
        op = node.ops[0]
        if isinstance(op, (ast.In, ast.NotIn, ast.Is, ast.IsNot)):
            raise DSLError(ISIN_MESSAGE, line=_line(node))
        left = self._expr(node.left)
        right = self._expr(node.comparators[0])
        if isinstance(op, ast.Lt):
            return {"op": "less_than", "args": {"a": left, "b": right}}
        if isinstance(op, ast.Gt):
            return {"op": "greater_than", "args": {"a": left, "b": right}}
        if isinstance(op, ast.Eq):
            return {"op": "equals", "args": {"a": left, "b": right}}
        if isinstance(op, ast.NotEq):
            return {
                "op": "not",
                "args": {
                    "a": {"op": "equals", "args": {"a": left, "b": right}}
                },
            }
        if isinstance(op, ast.LtE):
            return {
                "op": "or",
                "args": {
                    "a": {"op": "less_than", "args": {"a": left, "b": right}},
                    "b": {"op": "equals", "args": {"a": left, "b": right}},
                },
            }
        if isinstance(op, ast.GtE):
            return {
                "op": "or",
                "args": {
                    "a": {
                        "op": "greater_than",
                        "args": {"a": left, "b": right},
                    },
                    "b": {"op": "equals", "args": {"a": left, "b": right}},
                },
            }
        raise DSLError(
            "this comparison is not part of the dialect.", line=_line(node)
        )

    def _boolop(self, node: ast.BoolOp) -> dict[str, Any]:
        op = "and" if isinstance(node.op, ast.And) else "or"
        result = self._expr(node.values[0])
        for value in node.values[1:]:
            result = {
                "op": op,
                "args": {"a": result, "b": self._expr(value)},
            }
        return result

    def _unary(self, node: ast.UnaryOp) -> Any:
        if isinstance(node.op, ast.Not):
            return {"op": "not", "args": {"a": self._expr(node.operand)}}
        if isinstance(node.op, (ast.USub, ast.UAdd)):
            if _is_number_constant(node.operand):
                number = node.operand.value
                return -number if isinstance(node.op, ast.USub) else number
            raise DSLError(UNARYMINUS_MESSAGE, line=_line(node))
        raise DSLError(
            "Scratch has no bitwise operators; write 0 - x for a negation.",
            line=_line(node),
        )

    def _binop(self, node: ast.BinOp) -> dict[str, Any]:
        if isinstance(node.op, ast.Add):
            if _is_string_constant(node.left) or _is_string_constant(node.right):
                return {
                    "op": "join",
                    "args": {
                        "a": self._expr(node.left),
                        "b": self._expr(node.right),
                    },
                }
            if not _is_scalar_literal(node.left) and not _is_scalar_literal(
                node.right
            ):
                raise DSLError(AMBIGPLUS_MESSAGE, line=_line(node))
            return {
                "op": "add",
                "args": {"a": self._expr(node.left), "b": self._expr(node.right)},
            }
        binary = _BINARY_OPERATORS.get(type(node.op))
        if binary is not None:
            return {
                "op": binary,
                "args": {"a": self._expr(node.left), "b": self._expr(node.right)},
            }
        raise DSLError(
            "Scratch has no power/floor-div/bit operator; use multiply or the "
            "math_function blocks.",
            line=_line(node),
        )

    # -- call arguments --------------------------------------------------

    def _bind_op_args(
        self, op: str, specs: tuple[ArgSpec, ...], call: ast.Call
    ) -> dict[str, Any]:
        names = [spec.name for spec in specs]
        if len(call.args) > len(names):
            raise DSLError(
                ARITY_MESSAGE.format(
                    op=op, count=len(names), names=", ".join(names)
                ),
                line=call.lineno,
            )
        raw: dict[str, ast.expr] = {}
        for index, node in enumerate(call.args):
            if isinstance(node, ast.Starred):
                raise DSLError(STAR_MESSAGE, line=_line(node))
            raw[names[index]] = node
        for keyword in call.keywords:
            if keyword.arg is None:
                raise DSLError(STAR_MESSAGE, line=call.lineno)
            if keyword.arg not in names:
                raise DSLError(
                    BADKWARG_MESSAGE.format(
                        op=op,
                        expected=", ".join(names),
                        name=keyword.arg,
                    ),
                    line=call.lineno,
                )
            if keyword.arg in raw:
                raise _duplicate_argument(op, keyword.arg, call.lineno)
            raw[keyword.arg] = keyword.value
        missing = [name for name in names if name not in raw]
        if missing:
            raise DSLError(
                ARITY_MESSAGE.format(
                    op=op, count=len(names), names=", ".join(names)
                ),
                line=call.lineno,
            )
        return {
            spec.name: self._arg_value(op, spec, raw[spec.name])
            for spec in specs
        }

    def _arg_value(self, op: str, spec: ArgSpec, node: ast.expr) -> Any:
        if spec.type == "menu":
            if not isinstance(node, ast.Constant) or not isinstance(
                node.value, str
            ):
                raise DSLError(
                    MENU_MESSAGE.format(
                        op=op,
                        arg=spec.name,
                        values=", ".join(self._menu_values(op, spec)),
                    ),
                    line=_line(node),
                )
            value = node.value
            if value not in self._menu_values(op, spec):
                raise DSLError(
                    MENU_MESSAGE.format(
                        op=op,
                        arg=spec.name,
                        values=", ".join(self._menu_values(op, spec)),
                    ),
                    line=_line(node),
                )
            return value
        if spec.type in {"string", "color", "list", "list_index", "clone_target"}:
            if not isinstance(node, ast.Constant):
                raise DSLError(
                    f"{op}() argument '{spec.name}' must be a literal "
                    "value, not a reporter.",
                    line=_line(node),
                )
            value = node.value
            if isinstance(value, bool) or value is None:
                raise DSLError(
                    f"{op}() argument '{spec.name}' must be a literal "
                    "value.",
                    line=_line(node),
                )
            if spec.type in {
                "string",
                "color",
                "list",
                "clone_target",
            } and not isinstance(value, str):
                raise DSLError(
                    f"{op}() argument '{spec.name}' must be a string.",
                    line=_line(node),
                )
            if spec.type == "list" and not value:
                raise DSLError(
                    f"{op}() argument '{spec.name}' must be a list name.",
                    line=_line(node),
                )
            if spec.type == "list_index":
                if isinstance(value, str):
                    if value not in {"last", "all"}:
                        raise DSLError(
                            MENU_MESSAGE.format(
                                op=op, arg=spec.name, values="last, all"
                            ),
                            line=_line(node),
                        )
                elif value < 1:
                    raise DSLError(
                        "list index must be at least 1.", line=_line(node)
                    )
            if isinstance(value, str):
                self._check_command_name(op, spec.name, value, _line(node))
            return value
        return self._expr(node)

    def _menu_values(self, op: str, spec: ArgSpec) -> tuple[str, ...]:
        values = list(spec.menu)
        if spec.name == "target" and op in SPRITE_TARGET_OPS:
            for name in sorted(self.sprite_names):
                if name not in values:
                    values.append(name)
        return tuple(values)


#: Augmented-assignment symbols for the hint text.
_AUGMENTED_OPERATORS: dict[type[ast.operator], tuple[str, str]] = {
    ast.Mult: ("*", "multiply"),
    ast.Div: ("/", "divide"),
    ast.Mod: ("%", "mod"),
    ast.Pow: ("**", "math_function"),
    ast.FloorDiv: ("//", "divide"),
    ast.BitAnd: ("&", "and"),
    ast.BitOr: ("|", "or"),
    ast.BitXor: ("^", "or"),
    ast.LShift: ("<<", "multiply"),
    ast.RShift: (">>", "divide"),
}

#: Plain operator nodes that map one-to-one onto catalog reporter blocks.
_BINARY_OPERATORS: dict[type[ast.operator], str] = {
    ast.Sub: "subtract",
    ast.Mult: "multiply",
    ast.Div: "divide",
    ast.Mod: "mod",
}


def _decorator_name(decorator: ast.expr) -> str:
    if isinstance(decorator, ast.Call):
        return ast.unparse(decorator.func)
    return ast.unparse(decorator)


def _has_arguments(arguments: ast.arguments) -> bool:
    return bool(
        arguments.posonlyargs
        or arguments.args
        or arguments.vararg is not None
        or arguments.kwonlyargs
        or arguments.kwarg is not None
    )


def transpile(
    source: str, context: ProjectContext | None = None
) -> ChangeSet:
    """Transpile one Scratch-Python reply into a :class:`ChangeSet`."""
    text = _strip_code_fences(source)
    try:
        module = ast.parse(text)
    except SyntaxError as exc:
        raise DSLError(
            f"Python syntax error: {exc.msg}.{SYNTAX_SUFFIX}",
            line=exc.lineno,
            col=exc.offset,
        ) from None
    return _Transpiler(context).run(module)


def lint(source: str, context: ProjectContext | None = None) -> list[str]:
    """Return formatted diagnostics; empty when the reply is clean."""
    try:
        transpile(source, context)
    except DSLErrors as exc:
        return [error.format() for error in exc.errors]
    except DSLError as exc:
        return [exc.format()]
    return []
