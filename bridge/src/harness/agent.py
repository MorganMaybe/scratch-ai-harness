from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, replace
from typing import Any

from .block_ir import (
    Change,
    ChangeSet,
    ChangeSetParseResult,
    ContextRequest,
    IRError,
    parse_changeset_partial,
    parse_context_request,
)
from .changeset import CompiledChangeSet, compile_changeset
from .config import resolve_generator
from .context import ProjectContext, ScriptSummary, SpriteContext
from .context_doc import (
    ContextPackError,
    DEFAULT_DSL_CONTEXT_DOC,
    available_context_packs,
    load_context_doc,
    load_context_packs,
)
from .lints import lint_changeset
from .llm import LLMClient
from .prompts import (
    analyze_system_prompt,
    build_dsl_system_prompt,
    build_system_prompt,
    build_user_prompt_with_meta,
    prompt_budget_chars,
)
from .providers.base import (
    ModelReply,
    ModelRequest,
    ProviderError,
    parse_json_object,
    remaining_seconds,
)
from .script_detail import (
    resolve_sprite_name,
    sprite_detail_index,
    sprite_detail_text,
)
from .validator import ValidationError, ValidationIssue, validate_changeset


@dataclass
class CancelToken:
    """One request's cooperative cancellation flag.

    Cancellation is *cooperative*: setting the flag cannot interrupt a blocking
    HTTP call in another thread, so the agent re-checks it around every model
    attempt and repair.  ``cancelled`` is a plain bool; under CPython a store
    and a load are atomic, and the bridge's live-token map is what needs the
    lock, not this flag.
    """

    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True


def _raise_if_cancelled(token: CancelToken | None) -> None:
    if token is not None and token.cancelled:
        raise ProviderError("cancelled", "request cancelled by the client")


#: Repairing more than a few changes is not worth a second round trip; a full
#: regeneration is safer once the failure is broad.
_FRAGMENT_LIMIT = 3

#: A turn may lazily load at most this many additional context-pack calls.
_MAX_CONTEXT_LOADS = 2


def _issue_change_indices(issues: list[ValidationIssue]) -> list[int]:
    """Indices mentioned by ``changes[N]...`` validation paths."""
    found: list[int] = []
    for issue in issues:
        path = getattr(issue, "path", "") or ""
        if not path.startswith("changes["):
            continue
        end = path.find("]", len("changes["))
        if end < 0:
            continue
        try:
            index = int(path[len("changes[") : end])
        except ValueError:
            continue
        if index not in found:
            found.append(index)
    return sorted(found)


def _parse_repair_fragments(data: Any) -> list[Change]:
    """Parse the small ``{"changes": [...]}`` reply for a fragment repair."""
    if not isinstance(data, dict):
        raise IRError("fragment repair must return an object")
    allowed = {"changes", "summary", "notes"}
    unknown = set(data) - allowed
    if unknown:
        raise IRError(f"unknown fragment repair fields: {sorted(unknown)}")
    changes = data.get("changes")
    if not isinstance(changes, list) or not changes:
        raise IRError("fragment repair must contain at least one change")
    return [Change.from_dict(item) for item in changes]


def _merge_fragments(
    base: list[Change | None],
    indices: list[int],
    repaired: list[Change],
    summary: str,
    notes: str,
) -> ChangeSet:
    if len(indices) != len(repaired):
        raise IRError(
            f"fragment repair returned {len(repaired)} change(s) for "
            f"{len(indices)} failing index(es)"
        )
    merged = list(base)
    for index, change in zip(indices, repaired):
        if index < 0 or index >= len(merged):
            raise IRError(f"fragment repair index {index} is out of range")
        merged[index] = change
    if any(change is None for change in merged):
        raise IRError("fragment repair did not fill every invalid change")
    return ChangeSet(
        summary=summary,
        changes=[change for change in merged if change is not None],
        notes=notes,
    )


def _change_outline(changes: list[Change | None]) -> str:
    lines: list[str] = []
    for index, change in enumerate(changes):
        if change is None:
            lines.append(f"  {index}: <invalid change>")
            continue
        parts = [f"{index}: {change.action}"]
        for name in ("target", "label", "script_id", "name", "scope"):
            value = getattr(change, name, "")
            if value:
                parts.append(f"{name}={value}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _fragment_repair_prompt(
    request: str,
    context: ProjectContext,
    base_changes: list[Change | None],
    indices: list[int],
    payload: dict | None,
    issues: list[ValidationIssue],
) -> str:
    raw_changes = []
    if isinstance(payload, dict) and isinstance(payload.get("changes"), list):
        raw_changes = payload["changes"]
    failing_raw = [
        raw_changes[index] if 0 <= index < len(raw_changes) else None
        for index in indices
    ]
    issue_lines: list[str] = []
    other_lines: list[str] = []
    for issue in issues:
        path = getattr(issue, "path", "") or ""
        matched = False
        for index in indices:
            if path == f"changes[{index}]" or path.startswith(f"changes[{index}]."):
                issue_lines.append(f"- {issue}")
                matched = True
                break
        if not matched:
            other_lines.append(f"- {issue}")
    if other_lines:
        issue_lines.extend(other_lines)
    index_text = ", ".join(str(index) for index in indices)
    media_note = ""
    if any(
        "unknown costume" in str(issue) or "unknown backdrop" in str(issue)
        for issue in issues
    ):
        media_note = """
The media library is strict. Replace the missing costume/backdrop with an exact
name from the system prompt media index, or remove the decorative costume. Do
not invent a path or say "swap it if missing". If a create_sprite failed, its
later scripts are also invalid until that sprite is fixed.
"""
    var_note = ""
    if any("unknown variable" in str(issue) for issue in issues):
        var_note = """
Check whose variable it is. If it is another sprite's local variable, do not
create a copy: use set_attribute_of/change_attribute_of on that sprite, or
broadcast to a when_receive script owned by it. Only create a new variable when
the request truly needs one; global scope lives on Stage.
"""
    scope_note = ""
    if any(
        "sprite-scoped variable requires a valid target" in str(issue)
        for issue in issues
    ):
        scope_note = """
A sprite-scoped variable needs a target naming a sprite that exists at that
point in the change set. Add the target field, or make the variable global
instead.
"""
    delta_note = ""
    if any(
        "unknown argument 'delta'" in str(issue)
        or "missing argument 'dx'" in str(issue)
        or "missing argument 'dy'" in str(issue)
        for issue in issues
    ):
        delta_note = """
change_x takes dx and change_y takes dy. delta only fits change_var and
change_attribute_of. Rename the argument; do not drop the movement.
"""
    target_note = ""
    if any("unknown target sprite/stage" in str(issue) for issue in issues):
        target_note = """
Every target must exist when its change runs. Create the sprite earlier in the
same change set, or target an existing sprite/Stage. A later reference to a
sprite the set never creates is an error.
"""
    menu_note = ""
    if any(
        "this menu accepts a sprite that exists at this point in the change set"
        in str(issue)
        for issue in issues
    ):
        menu_note = """
Sprite-name menu arguments (touching, distance_to, goto_sprite, point_towards,
attribute_of) only accept a sprite that exists at that point in the change set.
Create it earlier in the set, or use mouse-pointer/edge/Stage as the block's
menu allows.
"""
    stage_note = ""
    if any("cannot be used on 'Stage'" in str(issue) for issue in issues):
        stage_note = """
The Stage cannot run motion, looks or sprite-only sensing blocks. Move that
behavior to a sprite script, or use the stage-safe equivalents: switch_backdrop,
variables, broadcast. See the Stage rules in the system prompt.
"""
    block_note = ""
    if any("unknown block fields" in str(issue) for issue in issues):
        block_note = """
Blocks take only op, args, body, then, else. Argument names go inside args. A
wait is a normal block at the end of the surrounding body list; it is
never a named field of if/forever/repeat_until. Re-emit the failing block with
the nested blocks inside the body.
"""
    return f"""Your previous change set was mostly valid, but {len(indices)} change(s)
could not be used.

User request:
{request}

Project context:
{context.summary_text()}

All changes in the set (reference only; do not rewrite the valid ones):
{_change_outline(base_changes)}

Failing changes (raw JSON):
{json.dumps(failing_raw, indent=2)}

Problems:
{chr(10).join(issue_lines) or "- invalid change"}
{media_note}{var_note}{scope_note}{delta_note}{target_note}{menu_note}{stage_note}{block_note}
Return ONLY a JSON object:
{{"changes": [ ... exactly {len(indices)} corrected change(s), in this order: {index_text} ... ]}}

Keep the same action, target, label, script_id and names unless the problem
requires changing them. Do not return the valid changes and do not add new
changes. Use only the block ops in the catalog.
"""


@dataclass
class AgentResult:
    request_id: int
    summary: str
    changeset: ChangeSet
    compiled: CompiledChangeSet
    apply_literal: str
    attempts: int = 1
    issues: list[ValidationIssue] = field(default_factory=list)
    model: str = ""
    usage: dict[str, int] | None = None
    latency_ms: int = 0
    finish_reason: str | None = None
    reasoning_tokens: int | None = None
    cached_tokens: int | None = None
    #: Advisory runtime lints.  They never block a turn or feed a repair.
    lint_warnings: list[str] = field(default_factory=list)


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        context: ProjectContext,
        registry: dict[str, ScriptSummary] | None = None,
        max_repairs: int = 2,
        cancel_token: CancelToken | None = None,
        audit: Any = None,
    ):
        self.llm = llm
        self.context = context
        self.registry = registry if registry is not None else context.registry()
        self.max_repairs = max_repairs
        #: Optional cooperative cancellation flag for this turn.  The bridge
        #: constructs one token per request; ``handle`` also accepts an explicit
        #: override for direct agent use.
        self.cancel_token = cancel_token
        #: Optional ``harness.audit.TurnAudit``.  It is deliberately typed as
        #: ``Any`` so this module has no dependency on the audit writer and
        #: tests can pass a simple recording double.
        self.audit = audit

    def use_context(self, context: ProjectContext) -> None:
        """Adopt the context sent by the image and rebuild the registry from it.

        Every request carries a fresh snapshot, so local image changes (undo,
        manual edits) are reconciled automatically.
        """
        self.context = context
        self.registry = context.registry()

    def _loaded_sprite_detail(
        self, names: list[str], generator: str = "json"
    ) -> str:
        parts: list[str] = []
        for name in names:
            canonical = resolve_sprite_name(self.context, name)
            if canonical is None:
                continue
            sprite = self.context.sprites[canonical]
            if generator == "dsl":
                from .dsl import render_sprite_detail

                body = render_sprite_detail(sprite)
            else:
                body = sprite_detail_text(sprite)
            parts.append(f"# Loaded sprite detail: {canonical}\n" + body)
        return "\n\n".join(parts)

    def _lint(self, changeset: ChangeSet) -> list[str]:
        """Advisory runtime lints; a lint bug must never fail the turn."""
        try:
            return lint_changeset(changeset, self.context, self.registry)
        except Exception as exc:  # pragma: no cover - defensive
            logging.getLogger("harness.lints").warning(
                "event=lints.failed error=%s", type(exc).__name__
            )
            return []

    def _system_prompt(
        self,
        packs: list[str],
        sprites: list[str] | None = None,
        generator: str = "json",
    ) -> str:
        """Build the system prompt with the core appendix and loaded context.

        Loaded packs and sprite detail blocks extend the character budget by
        their own size, so asking for specialized context does not consume room
        from the core guide, media index or catalog. The sprite index appears
        only when at least one AI-owned script has a body to show; the exact
        bodies appear only after the model requests them.

        ``generator = dsl`` swaps the dialect appendix and the generated
        Scratch-Python reference in; the control-channel index is unchanged.
        """
        if generator == "dsl":
            core = load_context_doc(DEFAULT_DSL_CONTEXT_DOC) or load_context_doc()
        else:
            core = load_context_doc()
        extra = load_context_packs(packs, generator)
        detail = self._loaded_sprite_detail(sprites or [], generator)
        loaded = "\n\n".join(part for part in (extra, detail) if part)
        index = sprite_detail_index(self.context)
        budget = prompt_budget_chars()
        if loaded:
            # Requested blocks go first so a base-budget trim would keep the
            # detail the model explicitly asked for; the extra budget then
            # preserves the normal room for everything else.
            budget += len(loaded) + 2
        parts = [part for part in (loaded, index, core) if part]
        doc = "\n\n".join(parts)
        builder = build_dsl_system_prompt if generator == "dsl" else build_system_prompt
        return builder(
            target=self.context.target,
            budget_chars=budget,
            context_doc=doc,
        )

    def handle(
        self,
        request: str,
        request_id: int = 1,
        *,
        deadline: float | None = None,
        cancel_token: CancelToken | None = None,
    ) -> AgentResult:
        token = cancel_token if cancel_token is not None else self.cancel_token
        # Cancellation wins over everything else: a token set before the turn
        # means we must not call the provider at all.
        _raise_if_cancelled(token)
        # Resolve once per turn so tests (and the smoke runner) can flip the
        # environment between turns without restarting the bridge.
        generator = resolve_generator()
        loaded_packs: list[str] = []
        loaded_sprites: list[str] = []
        context_loads = 0
        system = self._system_prompt(loaded_packs, loaded_sprites, generator)
        user, user_meta = build_user_prompt_with_meta(
            request, self.context, generator=generator
        )
        if self.audit is not None:
            system_info = analyze_system_prompt(system)
            system_info["context_packs"] = list(loaded_packs)
            system_info["sprite_details"] = list(loaded_sprites)
            self.audit.write_prompts(
                system,
                user,
                system_info=system_info,
                user_info=user_meta,
            )
        last_payload: dict | None = None
        last_issues: list[ValidationIssue] = []
        fragment_base: list[Change | None] | None = None
        fragment_indices: list[int] = []
        fragment_summary = ""
        fragment_notes = ""
        fragment_mode = False
        # Repairs are capped separately from model calls so a lazy context load
        # does not silently consume a repair attempt.
        repairs_used = 0
        attempt = 0

        for attempt in range(1, self.max_repairs + 2 + _MAX_CONTEXT_LOADS):
            # Before every model attempt (including the first one).
            _raise_if_cancelled(token)
            left = remaining_seconds(deadline)
            if left is not None and left < 1.0:
                error = ProviderError(
                    "timeout",
                    f"turn budget exhausted after {attempt - 1} attempt(s)",
                )
                if self.audit is not None:
                    self.audit.write_attempt(
                        attempt,
                        user_prompt=user,
                        error=error,
                        fragment=fragment_mode,
                        fragment_indices=fragment_indices if fragment_mode else None,
                    )
                raise error

            try:
                reply = self._complete(
                    system, user, request_id, attempt, deadline, generator
                )
            except ProviderError as exc:
                if self.audit is not None:
                    self.audit.write_attempt(
                        attempt,
                        user_prompt=user,
                        error=exc,
                        fragment=fragment_mode,
                        fragment_indices=fragment_indices if fragment_mode else None,
                    )
                # A malformed/empty model payload is a model-output problem, not
                # a transport failure: the provider deliberately does not retry
                # it, so give the model one more chance with a repair prompt.
                if exc.code != "bad_json":
                    raise
                detail = exc.message
                if getattr(exc, "finish_reason", None) == "length":
                    detail += " (finish_reason=length, output budget exhausted)"
                reasoning_tokens = getattr(exc, "reasoning_tokens", None)
                if (
                    isinstance(reasoning_tokens, int)
                    and not isinstance(reasoning_tokens, bool)
                    and reasoning_tokens > 0
                ):
                    detail += (
                        f"; {reasoning_tokens} tokens went to hidden reasoning "
                        "before any JSON"
                    )
                last_issues = [ValidationIssue("json", detail)]
                if fragment_mode:
                    # The fragment reply was unusable; fall back to a full
                    # repair against the best full change set we have.
                    fragment_mode = False
                else:
                    last_payload = None
                if repairs_used >= self.max_repairs:
                    break
                repairs_used += 1
                _raise_if_cancelled(token)
                if generator == "dsl":
                    user = _dsl_repair_prompt(
                        request, self.context, "", last_issues
                    )
                else:
                    user = _repair_prompt(
                        request, self.context, last_payload, last_issues
                    )
                continue

            # The provider may have answered while the client was cancelling:
            # discard that reply before it can become a result or touch state.
            _raise_if_cancelled(token)

            # In DSL mode the reply payload is a raw Scratch-Python module.
            # A JSON object is still accepted (control channel or a model
            # fallback to the JSON change set); it goes through the existing
            # JSON flow untouched.
            dsl_source: str | None = None
            dsl_changeset: ChangeSet | None = None
            dsl_diagnostics: list[str] = []
            if not reply.data and generator == "dsl" and reply.raw_text:
                raw = str(reply.raw_text).strip()
                json_fallback: dict | None = None
                if raw.startswith("{"):
                    try:
                        candidate = parse_json_object(raw)
                    except ProviderError:
                        candidate = None
                    if isinstance(candidate, dict):
                        json_fallback = candidate
                if json_fallback is not None:
                    reply = replace(reply, data=json_fallback)
                else:
                    from .dsl import DSLError, DSLErrors, transpile

                    dsl_source = raw
                    fragment_mode = False
                    try:
                        dsl_changeset = transpile(raw, self.context)
                    except DSLErrors as exc:
                        dsl_diagnostics = [error.format() for error in exc.errors]
                    except DSLError as exc:
                        dsl_diagnostics = [exc.format()]

            # Lazy context: a reply may ask for optional topic docs and/or exact
            # sprite script bodies instead of a change set. Load them, rebuild
            # the prompt, and ask again. This is a model call, not a repair.
            context_issue: ValidationIssue | None = None
            packs_to_load: list[str] = []
            sprites_to_load: list[str] = []
            try:
                context_request = parse_context_request(reply.data)
            except IRError as exc:
                context_request = None
                context_issue = ValidationIssue("load_context", str(exc))
            if context_request is not None:
                available = available_context_packs()
                available_sprites = [
                    name
                    for name, sprite in self.context.sprites.items()
                    if any(script.owned and script.tuples for script in sprite.scripts)
                ]
                problems: list[str] = []
                unknown = [
                    name for name in context_request.packs if name not in available
                ]
                if unknown:
                    problems.append(
                        "unknown context pack(s): "
                        + ", ".join(unknown)
                        + "; available: "
                        + ", ".join(sorted(available))
                    )
                resolved_sprites: list[str] = []
                for name in context_request.sprites:
                    canonical = resolve_sprite_name(self.context, name)
                    if canonical is None:
                        problems.append(
                            f"unknown sprite {name!r}; sprites with script detail: "
                            + (", ".join(available_sprites) or "none")
                        )
                    elif not any(
                        script.owned and script.tuples
                        for script in self.context.sprites[canonical].scripts
                    ):
                        problems.append(
                            f"no editable script detail for sprite {canonical!r}; "
                            "sprites with script detail: "
                            + (", ".join(available_sprites) or "none")
                        )
                    else:
                        resolved_sprites.append(canonical)
                new_packs = [
                    name for name in context_request.packs if name not in loaded_packs
                ]
                new_sprites = [
                    name for name in resolved_sprites if name not in loaded_sprites
                ]
                if problems:
                    context_issue = ValidationIssue(
                        "load_context", "; ".join(problems)
                    )
                elif not new_packs and not new_sprites:
                    context_issue = ValidationIssue(
                        "load_context",
                        "that context is already loaded; return the change set",
                    )
                elif context_loads >= _MAX_CONTEXT_LOADS:
                    context_issue = ValidationIssue(
                        "load_context",
                        f"context load limit reached ({_MAX_CONTEXT_LOADS}); "
                        "return the change set",
                    )
                else:
                    packs_to_load = new_packs
                    sprites_to_load = new_sprites
            if context_issue is not None:
                last_issues = [context_issue]
                if self.audit is not None:
                    self.audit.write_attempt(
                        attempt,
                        user_prompt=user,
                        reply=reply,
                        parse_error=str(context_issue),
                        issues=last_issues,
                    )
                if repairs_used >= self.max_repairs:
                    break
                repairs_used += 1
                _raise_if_cancelled(token)
                user = _context_error_prompt(request, self.context, last_issues)
                continue
            if packs_to_load or sprites_to_load:
                loaded_packs.extend(packs_to_load)
                loaded_sprites.extend(sprites_to_load)
                context_loads += 1
                fragment_mode = False
                system = self._system_prompt(loaded_packs, loaded_sprites, generator)
                user = _context_loaded_prompt(
                    request, self.context, packs_to_load, sprites_to_load
                )
                if self.audit is not None:
                    system_info = analyze_system_prompt(system)
                    system_info["context_packs"] = list(loaded_packs)
                    system_info["sprite_details"] = list(loaded_sprites)
                    self.audit.write_prompts(
                        system,
                        user,
                        system_info=system_info,
                        user_info={
                            "context_packs": list(loaded_packs),
                            "sprite_details": list(loaded_sprites),
                            "level": 0,
                            "context_chars": len(self.context.summary_text()),
                        },
                    )
                    self.audit.write_attempt(attempt, user_prompt=user, reply=reply)
                continue

            if dsl_diagnostics:
                last_issues = [
                    ValidationIssue("dsl", text) for text in dsl_diagnostics
                ]
                if self.audit is not None:
                    self.audit.write_attempt(
                        attempt,
                        user_prompt=user,
                        reply=reply,
                        parse_error="; ".join(dsl_diagnostics),
                        issues=last_issues,
                        dsl_errors=dsl_diagnostics,
                    )
                if repairs_used >= self.max_repairs:
                    break
                repairs_used += 1
                _raise_if_cancelled(token)
                user = _dsl_repair_prompt(
                    request, self.context, dsl_source or "", last_issues
                )
                continue

            if fragment_mode and generator == "json":
                fragment_error = None
                merged: ChangeSet | None = None
                try:
                    repaired = _parse_repair_fragments(reply.data)
                    merged = _merge_fragments(
                        fragment_base or [],
                        fragment_indices,
                        repaired,
                        fragment_summary,
                        fragment_notes,
                    )
                    last_issues = validate_changeset(
                        merged, self.context, self.registry
                    )
                except Exception as exc:
                    fragment_error = exc
                    last_issues = [ValidationIssue("json", str(exc))]
                if self.audit is not None:
                    self.audit.write_attempt(
                        attempt,
                        user_prompt=user,
                        reply=reply,
                        parse_error=fragment_error,
                        issues=last_issues,
                        fragment=True,
                        fragment_indices=fragment_indices,
                    )
                fragment_mode = False
                if merged is not None and not last_issues:
                    compiled = compile_changeset(
                        merged, self.context, self.registry
                    )
                    warnings = self._lint(merged)
                    if self.audit is not None:
                        self.audit.write_compiled(merged, compiled)
                        self.audit.write_chunks(merged, compiled)
                        self.audit.write_lints(warnings)
                    return AgentResult(
                        request_id=request_id,
                        summary=compiled.summary,
                        changeset=merged,
                        compiled=compiled,
                        apply_literal=compiled.apply_literal(request_id),
                        attempts=attempt,
                        model=reply.model,
                        usage=reply.usage,
                        latency_ms=reply.latency_ms,
                        finish_reason=reply.finish_reason,
                        reasoning_tokens=reply.reasoning_tokens,
                        cached_tokens=reply.cached_tokens,
                        lint_warnings=warnings,
                    )
                if merged is not None:
                    last_payload = merged.to_dict()
                if repairs_used >= self.max_repairs:
                    break
                repairs_used += 1
                _raise_if_cancelled(token)
                user = _repair_prompt(
                    request, self.context, last_payload, last_issues
                )
                continue

            if dsl_changeset is not None:
                changeset = dsl_changeset
                last_issues = validate_changeset(
                    changeset, self.context, self.registry
                )
                if self.audit is not None:
                    # Store the emitted change set as parsed.json, as the JSON
                    # path does, while raw.txt keeps the module source.
                    self.audit.write_attempt(
                        attempt,
                        user_prompt=user,
                        reply=replace(reply, data=changeset.to_dict()),
                        issues=last_issues,
                    )
                if not last_issues:
                    compiled = compile_changeset(
                        changeset, self.context, self.registry
                    )
                    warnings = self._lint(changeset)
                    if self.audit is not None:
                        self.audit.write_compiled(changeset, compiled)
                        self.audit.write_chunks(changeset, compiled)
                        self.audit.write_lints(warnings)
                    return AgentResult(
                        request_id=request_id,
                        summary=compiled.summary,
                        changeset=changeset,
                        compiled=compiled,
                        apply_literal=compiled.apply_literal(request_id),
                        attempts=attempt,
                        model=reply.model,
                        usage=reply.usage,
                        latency_ms=reply.latency_ms,
                        finish_reason=reply.finish_reason,
                        reasoning_tokens=reply.reasoning_tokens,
                        cached_tokens=reply.cached_tokens,
                        lint_warnings=warnings,
                    )
            else:
                last_payload = reply.data
                fragment_base = None
                fragment_indices = []
                parsed: ChangeSetParseResult = parse_changeset_partial(reply.data)
                if parsed.top_level_error is not None:
                    last_issues = [
                        ValidationIssue("json", str(parsed.top_level_error))
                    ]
                    if self.audit is not None:
                        self.audit.write_attempt(
                            attempt,
                            user_prompt=user,
                            reply=reply,
                            parse_error=parsed.top_level_error,
                            issues=last_issues,
                        )
                elif parsed.problems:
                    last_issues = [
                        ValidationIssue(f"changes[{index}]", str(error))
                        for index, error in parsed.problems
                    ]
                    if self.audit is not None:
                        self.audit.write_attempt(
                            attempt,
                            user_prompt=user,
                            reply=reply,
                            parse_error="; ".join(str(error) for _, error in parsed.problems),
                            issues=last_issues,
                        )
                    if generator == "json" and len(parsed.problems) <= _FRAGMENT_LIMIT:
                        fragment_base = parsed.changes
                        fragment_indices = [index for index, _ in parsed.problems]
                        fragment_summary = parsed.summary
                        fragment_notes = parsed.notes
                else:
                    changeset = ChangeSet(
                        summary=parsed.summary,
                        changes=[
                            change for change in parsed.changes if change is not None
                        ],
                        notes=parsed.notes,
                    )
                    last_issues = validate_changeset(
                        changeset, self.context, self.registry
                    )
                    if self.audit is not None:
                        self.audit.write_attempt(
                            attempt,
                            user_prompt=user,
                            reply=reply,
                            issues=last_issues,
                        )
                    if not last_issues:
                        compiled = compile_changeset(
                            changeset, self.context, self.registry
                        )
                        warnings = self._lint(changeset)
                        if self.audit is not None:
                            self.audit.write_compiled(changeset, compiled)
                            self.audit.write_chunks(changeset, compiled)
                            self.audit.write_lints(warnings)
                        return AgentResult(
                            request_id=request_id,
                            summary=compiled.summary,
                            changeset=changeset,
                            compiled=compiled,
                            apply_literal=compiled.apply_literal(request_id),
                            attempts=attempt,
                            model=reply.model,
                            usage=reply.usage,
                            latency_ms=reply.latency_ms,
                            finish_reason=reply.finish_reason,
                            reasoning_tokens=reply.reasoning_tokens,
                            cached_tokens=reply.cached_tokens,
                            lint_warnings=warnings,
                        )
                    indices = _issue_change_indices(last_issues)
                    if (
                        generator == "json"
                        and indices
                        and len(indices) <= _FRAGMENT_LIMIT
                    ):
                        fragment_base = list(changeset.changes)
                        fragment_indices = indices
                        fragment_summary = changeset.summary
                        fragment_notes = changeset.notes

            if repairs_used >= self.max_repairs:
                break
            repairs_used += 1
            # Before each repair (the next loop iteration also re-checks).
            _raise_if_cancelled(token)
            if dsl_source is not None:
                user = _dsl_repair_prompt(
                    request, self.context, dsl_source, last_issues
                )
            elif fragment_base is not None and fragment_indices:
                fragment_mode = True
                user = _fragment_repair_prompt(
                    request,
                    self.context,
                    fragment_base,
                    fragment_indices,
                    last_payload,
                    last_issues,
                )
            else:
                user = _repair_prompt(
                    request, self.context, last_payload, last_issues
                )

        raise ValidationError(
            last_issues
            or [ValidationIssue("agent", "failed to produce a valid change set")],
            attempts=attempt,
        )

    def _complete(
        self,
        system: str,
        user: str,
        request_id: int,
        attempt: int,
        deadline: float | None,
        generator: str = "json",
    ) -> ModelReply:
        """One model call through the rich interface, with a legacy fallback."""
        complete = getattr(self.llm, "complete", None)
        if callable(complete):
            return complete(
                ModelRequest(
                    request_id=request_id,
                    system=system,
                    user=user,
                    attempt=attempt,
                    deadline=deadline,
                    reply_format=generator,
                )
            )

        # Old test doubles only implement ``complete_json``. Keep them working.
        started = time.monotonic()
        data: dict[str, Any] = self.llm.complete_json(system, user)
        return ModelReply(
            data=data,
            model=str(getattr(self.llm, "model", "") or ""),
            latency_ms=int((time.monotonic() - started) * 1000),
            attempts=attempt,
        )

    def register_applied(self, result: AgentResult) -> None:
        """Update the bridge-side registry after Scratch confirms the change set."""
        for change in result.compiled.changes:
            if change.action in {"add_script", "replace_script"}:
                self.registry[change.script_id] = ScriptSummary(
                    script_id=change.script_id,
                    target=change.target,
                    label=change.label or change.script_id,
                    hat=_hat_name(change.stack),
                    block_count=change.block_count,
                    owned=True,
                )
            elif change.action == "delete_script":
                self.registry.pop(change.script_id, None)
            elif change.action == "create_variable":
                if change.scope == "global":
                    if change.name not in self.context.stage_variables:
                        self.context.stage_variables.append(change.name)
                else:
                    sprite = self.context.sprites.get(change.target)
                    if sprite is not None and change.name not in sprite.variables:
                        sprite.variables.append(change.name)
            elif change.action == "create_list":
                if change.scope == "global":
                    if change.name not in self.context.stage_lists:
                        self.context.stage_lists.append(change.name)
                else:
                    sprite = self.context.sprites.get(change.target)
                    if sprite is not None and change.name not in sprite.lists:
                        sprite.lists.append(change.name)
            elif change.action == "create_sprite":
                self.context.sprites[change.name] = SpriteContext(
                    name=change.name,
                    costumes=[name for _, name in change.costumes],
                    ai_owned=True,
                    costume_index=1,
                    x=change.x,
                    y=change.y,
                    direction=change.direction,
                    size=change.size,
                    visible=change.visible,
                    rotation_style=change.rotation_style,
                )
            elif change.action == "delete_sprite":
                self.context.sprites.pop(change.target, None)
                for script_id in [
                    script_id
                    for script_id, script in self.registry.items()
                    if script.target == change.target
                ]:
                    self.registry.pop(script_id, None)
            elif change.action == "duplicate_sprite":
                source = self.context.sprites.get(change.target)
                if source is not None:
                    self.context.sprites[change.name] = SpriteContext(
                        name=change.name,
                        variables=list(source.variables),
                        costumes=list(source.costumes),
                        sounds=list(source.sounds),
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
                sprite = self.context.sprites.get(change.target)
                if sprite is not None and change.name not in sprite.costumes:
                    sprite.costumes.append(change.name)
                    if change.select:
                        sprite.costume_index = len(sprite.costumes)
            elif change.action == "set_backdrop":
                stage = self.context.sprites.get("Stage")
                if stage is not None:
                    if change.name not in stage.costumes:
                        stage.costumes.append(change.name)
                    stage.costume_index = stage.costumes.index(change.name) + 1
            elif change.action == "set_sprite":
                sprite = self.context.sprites.get(change.target)
                if sprite is not None:
                    sprite.x = change.x
                    sprite.y = change.y
                    sprite.direction = change.direction
                    sprite.size = change.size
                    sprite.visible = change.visible
                    sprite.rotation_style = change.rotation_style


def _hat_name(stack) -> str:
    if not stack:
        return ""
    first = stack[0]
    if not first:
        return ""
    return str(getattr(first[0], "name", first[0]))


def _repair_prompt(request: str, context: ProjectContext, payload: dict | None, issues: list[ValidationIssue]) -> str:
    previous = json.dumps(payload, indent=2) if payload is not None else "(no valid JSON)"
    problems = "\n".join(f"- {issue}" for issue in issues)
    budget_note = ""
    if any(
        "output budget" in str(issue) or "finish_reason=length" in str(issue)
        for issue in issues
    ):
        budget_note = """
The previous reply ran out of output tokens before it could finish. Return a
complete but smaller change set: fewer scripts and fewer blocks. Do not repeat
the entire scene if it does not fit; prioritise the core behavior and note what
was omitted. For pen drawings, use a simple approximation (a handful of lines or
arcs), never one block per pixel or point.
"""
    if any("hidden reasoning" in str(issue) for issue in issues):
        budget_note += """
Hidden reasoning consumed the output budget before any JSON was emitted. Reply
with a small, final change set immediately as JSON with no step-by-step planning;
if reasoning cannot be disabled here, very large scenes will not fit in one turn.
"""
    media_note = ""
    if any(
        "unknown costume" in str(issue) or "unknown backdrop" in str(issue)
        for issue in issues
    ):
        media_note = """
The media library is strict: every costume/backdrop must be an exact file that
appears in the system prompt's media index. Do not invent a path or write
"swap this if the file is missing"; choose a listed asset now, or omit the
decorative sprite/costume and note the omission. If the media index is
truncated, use a name that is visible in it.
"""
    var_note = ""
    if any("unknown variable" in str(issue) for issue in issues):
        var_note = """
Check whose variable it is. If it is another sprite's local variable, do not
create a copy: use set_attribute_of/change_attribute_of on that sprite, or
broadcast to a when_receive script owned by it. Only create a new variable when
the request truly needs one; global scope lives on Stage.
"""
    scope_note = ""
    if any(
        "sprite-scoped variable requires a valid target" in str(issue)
        for issue in issues
    ):
        scope_note = """
A sprite-scoped variable needs a target naming a sprite that exists at that
point in the change set. Add the target field, or make the variable global
instead.
"""
    delta_note = ""
    if any(
        "unknown argument 'delta'" in str(issue)
        or "missing argument 'dx'" in str(issue)
        or "missing argument 'dy'" in str(issue)
        for issue in issues
    ):
        delta_note = """
change_x takes dx and change_y takes dy. delta only fits change_var and
change_attribute_of. Rename the argument; do not drop the movement.
"""
    target_note = ""
    if any("unknown target sprite/stage" in str(issue) for issue in issues):
        target_note = """
Every target must exist when its change runs. Create the sprite earlier in the
same change set, or target an existing sprite/Stage. A later reference to a
sprite the set never creates is an error.
"""
    menu_note = ""
    if any(
        "this menu accepts a sprite that exists at this point in the change set"
        in str(issue)
        for issue in issues
    ):
        menu_note = """
Sprite-name menu arguments (touching, distance_to, goto_sprite, point_towards,
attribute_of) only accept a sprite that exists at that point in the change set.
Create it earlier in the set, or use mouse-pointer/edge/Stage as the block's
menu allows.
"""
    stage_note = ""
    if any("cannot be used on 'Stage'" in str(issue) for issue in issues):
        stage_note = """
The Stage cannot run motion, looks or sprite-only sensing blocks. Move that
behavior to a sprite script, or use the stage-safe equivalents: switch_backdrop,
variables, broadcast. See the Stage rules in the system prompt.
"""
    block_note = ""
    if any("unknown block fields" in str(issue) for issue in issues):
        block_note = """
Blocks take only op, args, body, then, else. Argument names go inside args. A
wait is a normal block at the end of the surrounding body list; it is
never a named field of if/forever/repeat_until. Re-emit the failing block with
the nested blocks inside the body.
"""
    return f"""Your previous response was not a valid change set.

User request:
{request}

Project context:
{context.summary_text()}

Previous response:
{previous}

Problems:
{problems}
{budget_note}{media_note}{var_note}{scope_note}{delta_note}{target_note}{menu_note}{stage_note}{block_note}
Return a corrected JSON change set only. Keep the same schema and use only the
block ops in the catalog. Do not repeat the previous mistakes.
"""


def _dsl_repair_prompt(
    request: str,
    context: ProjectContext,
    raw_source: str,
    messages: list[Any],
) -> str:
    """The full-module repair prompt for a rejected Scratch-Python reply."""
    problems = "\n".join(f"- {message}" for message in messages) or "- invalid module"
    media_note = ""
    if any(
        "unknown costume" in str(message) or "unknown backdrop" in str(message)
        for message in messages
    ):
        media_note = """
The media library is strict: every costume/backdrop must be an exact file that
appears in the system prompt's media index. Replace the missing name with a
listed asset, or omit the decorative sprite/costume and note the omission. Do
not invent a path.
"""
    var_note = ""
    if any("unknown variable" in str(message) for message in messages):
        var_note = """
Check whose variable it is. If it is another sprite's local variable, do not
create a copy: use attribute_of/set_attribute_of/change_attribute_of on that
sprite, or broadcast to a script owned by it. Create a variable before its
first use in the module.
"""
    target_note = ""
    if any("unknown target" in str(message) for message in messages):
        target_note = """
Every decorator target must exist when its def runs. Create the sprite earlier
in the same module, or target an existing sprite/Stage. A later reference to a
sprite the module never creates is an error.
"""
    stage_note = ""
    if any("cannot be used on 'Stage'" in str(message) for message in messages):
        stage_note = """
The Stage cannot run motion, looks or sprite-only sensing blocks. Move that
behavior to a sprite script, or use the stage-safe equivalents: switch_backdrop,
variables, broadcast. See the Stage rules in the system prompt.
"""
    return f"""Your previous Scratch-Python module could not be used.

User request:
{request}

Project context:
{context.summary_text()}

Previous module:
{raw_source or "(no module)"}

Problems:
{problems}
{media_note}{var_note}{target_note}{stage_note}
Return the complete corrected module as ONE fenced python block. Fix every
quoted line and keep the valid defs and module calls unchanged; do not switch
to a JSON change set. Use only the dialect functions in the API reference.

Control-channel replies stay JSON: when you need more context, return only
{{"load_context": [...]}} or {{"load_sprite": [...]}} with a reason, never
together with a module. Do not repeat the previous mistakes.
"""


def _context_loaded_prompt(
    request: str,
    context: ProjectContext,
    packs: list[str],
    sprites: list[str] | None = None,
) -> str:
    loaded: list[str] = []
    if packs:
        loaded.append("context pack(s): " + ", ".join(packs))
    if sprites:
        loaded.append("sprite detail: " + ", ".join(sprites))
    names = "; ".join(loaded)
    return f"""The requested context is now included in the system prompt: {names}.

User request:
{request}

Project context:
{context.summary_text()}

Use the loaded context where it applies, then return the JSON change set now.
"""


def _has_sprite_detail(context: ProjectContext) -> bool:
    return any(
        script.owned and script.tuples
        for sprite in context.sprites.values()
        for script in sprite.scripts
    )


def _context_error_prompt(
    request: str,
    context: ProjectContext,
    issues: list[ValidationIssue],
) -> str:
    problems = "\n".join(f"- {issue}" for issue in issues)
    if _has_sprite_detail(context):
        tail = (
            "Return either a JSON change set, or a lazy-context request naming only\n"
            "available context packs or sprites. Do not combine it with changes."
        )
    else:
        tail = (
            "No sprite script detail is available in this turn. Do not return\n"
            "load_sprite again; use the script ids, labels and block counts in the\n"
            "project context and return a change set now."
        )
    return f"""Your load_context/load_sprite request was not usable.

User request:
{request}

Project context:
{context.summary_text()}

Problems:
{problems}

{tail}
"""
