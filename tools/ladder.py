"""Phase C ladder: the same prompts through both reply generators.

Each scenario step runs in ``json`` and ``dsl`` mode against a synthetic
project, one full audit bundle per turn lands in a dedicated directory, and
the runner prints (and stores) a per-step x mode comparison.  The automated
half measures applied-rate, repair rounds and tokens; the human half is
``docs/LADDER_RUBRIC.md``, because applied-rate does not capture whether the
resulting Scratch is any good.

    python tools\\ladder.py --dry-run                  # wiring, no network
    python tools\\ladder.py -Runs 3                    # the real thing
    python tools\\ladder.py -Runs 1 -Modes dsl
    python tools\\ladder.py -Runs 1 -Scenarios square_chain,calculator
    python tools\\audit.py score --dir <audit-dir> --group generator

Scenario chains: a chained step sees the project state its predecessor
built (sprites, variables, scripts with native tuples), exactly like a real
second turn, so revision steps exercise load_sprite/replace_script against
real ids.

    square_chain      square -> bigger_say
    beach             one scene turn
    clicker           one game turn
    platformer_chain  platformer -> revision
    calculator        the historical large-turn stress case

Bundles contain prompts and raw replies: keep them local (the ladder
directory lives under the git-ignored ``scratch\\base\\audit``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge" / "src"))

from harness.agent import Agent, _hat_name  # noqa: E402
from harness.audit import AuditSettings, AuditStore  # noqa: E402
from harness.config import resolve_config  # noqa: E402
from harness.context import ProjectContext, ScriptSummary, SpriteContext  # noqa: E402
from harness.history import ConversationHistory  # noqa: E402
from harness.llm import draw_square_response  # noqa: E402
from harness.providers.base import (  # noqa: E402
    ModelReply,
    ModelRequest,
    ProviderError,
)
from harness.validator import ValidationError  # noqa: E402


# --------------------------------------------------------------------------
# The ladder
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    """One user turn inside a scenario."""

    name: str
    prompt: str


#: Ordered scenarios. Chained steps see the state the previous step built.
SCENARIOS: dict[str, tuple[Step, ...]] = {
    "square_chain": (
        Step(
            "square",
            "Make the cat draw a square when I click the green flag.",
        ),
        Step(
            "bigger_say",
            "Make the square bigger and have the cat say Done! when the "
            "square is finished.",
        ),
    ),
    "beach": (
        Step(
            "beach",
            "Make a beach scene with a beach backdrop and three crabs that "
            "wander around the bottom of the stage and animate while they "
            "walk.",
        ),
    ),
    "clicker": (
        Step(
            "clicker",
            "Make a clicker game: a starfish that jumps to a random spot "
            "every time you click it, and a score that counts the clicks.",
        ),
    ),
    "platformer_chain": (
        Step(
            "platformer",
            "Make a small platformer game: a player that runs left and "
            "right with the arrow keys and jumps with the up arrow, on a "
            "floor with a couple of platforms, with the score shown on "
            "screen.",
        ),
        Step(
            "revision",
            "Make the player jump higher and run faster.",
        ),
        Step(
            "start_lower",
            "Now make the platforms start lower, and make the player a "
            "little smaller.",
        ),
    ),
    "calculator": (
        Step(
            "calculator",
            "Build a working calculator: number buttons 0 to 9, plus, "
            "minus, multiply and divide buttons, an equals button and a "
            "clear button, and a display that shows the current number "
            "and the result.",
        ),
    ),
}

MODES = ("json", "dsl")


def clean_context() -> ProjectContext:
    """The standard clean Cat project the release image starts with."""
    return ProjectContext(
        target="Sprite1",
        sprites={
            "Stage": SpriteContext(
                name="Stage",
                is_stage=True,
                costumes=["background1"],
            ),
            "Sprite1": SpriteContext(
                name="Sprite1",
                costumes=["costume1", "costume2"],
                sounds=["meow"],
            ),
        },
    )


def _costume_names_from_entries(entries: list[Any]) -> list[str]:
    names: list[str] = []
    for entry in entries or []:
        library = str(entry[0]) if entry else ""
        given = str(entry[1]) if len(entry) > 1 and entry[1] else ""
        stem = library.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        names.append(given or stem)
    return names


def context_after_apply(context: ProjectContext, result: Any) -> ProjectContext:
    """The project snapshot the image would send after this change set.

    Follow-up steps in a scenario chain see the state this build produced:
    created sprites, variables, lists, costumes and scripts carry native
    tuples so ``load_sprite`` detail is available.  ``set_sprite`` applies
    every compiled field (the compiled layer does not record which fields
    were omitted), which can over-report unchanged properties; revision
    steps target scripts, so the approximation does not affect them.
    """
    sprites: dict[str, SpriteContext] = {
        name: SpriteContext(
            name=sprite.name,
            variables=list(sprite.variables),
            lists=list(sprite.lists),
            costumes=list(sprite.costumes),
            sounds=list(sprite.sounds),
            scripts=[
                ScriptSummary(
                    script_id=script.script_id,
                    target=script.target,
                    label=script.label,
                    hat=script.hat,
                    block_count=script.block_count,
                    hash=script.hash,
                    owned=script.owned,
                    user_edited=script.user_edited,
                    tuples=script.tuples,
                )
                for script in sprite.scripts
            ],
            is_stage=sprite.is_stage,
            x=sprite.x,
            y=sprite.y,
            direction=sprite.direction,
            size=sprite.size,
            visible=sprite.visible,
            rotation_style=sprite.rotation_style,
            ai_owned=sprite.ai_owned,
            costume_index=sprite.costume_index,
        )
        for name, sprite in context.sprites.items()
    }
    applied = ProjectContext(
        target=context.target,
        sprites=sprites,
        stage_variables=list(context.stage_variables),
        stage_lists=list(context.stage_lists),
    )
    for change in result.compiled.changes:
        action = change.action
        if action == "create_variable":
            if change.scope == "global":
                applied.stage_variables.append(change.name)
            else:
                sprite = sprites.get(change.target)
                if sprite is not None:
                    sprite.variables.append(change.name)
        elif action == "create_list":
            if change.scope == "global":
                applied.stage_lists.append(change.name)
            else:
                sprite = sprites.get(change.target)
                if sprite is not None:
                    sprite.lists.append(change.name)
        elif action == "create_sprite":
            sprites[change.name] = SpriteContext(
                name=change.name,
                costumes=_costume_names_from_entries(change.costumes),
                x=change.x,
                y=change.y,
                direction=change.direction,
                size=change.size,
                visible=change.visible,
                rotation_style=change.rotation_style,
                ai_owned=True,
            )
        elif action == "duplicate_sprite":
            source = sprites.get(change.target)
            if source is not None:
                sprites[change.name] = SpriteContext(
                    name=change.name,
                    variables=list(source.variables),
                    lists=list(source.lists),
                    costumes=list(source.costumes),
                    sounds=list(source.sounds),
                    x=source.x,
                    y=source.y,
                    direction=source.direction,
                    size=source.size,
                    visible=source.visible,
                    rotation_style=source.rotation_style,
                    ai_owned=True,
                )
        elif action == "delete_sprite":
            sprites.pop(change.target, None)
        elif action == "add_costume":
            sprite = sprites.get(change.target)
            stem = str(change.library).rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if sprite is not None:
                sprite.costumes.append(change.name or stem)
                if change.select:
                    sprite.costume_index = len(sprite.costumes)
        elif action == "set_backdrop":
            stage = sprites.get("Stage")
            stem = str(change.library).rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if stage is not None:
                stage.costumes.append(change.name or stem)
                if change.select:
                    stage.costume_index = len(stage.costumes)
        elif action == "set_sprite":
            sprite = sprites.get(change.target)
            if sprite is not None:
                sprite.x = change.x
                sprite.y = change.y
                sprite.direction = change.direction
                sprite.size = change.size
                sprite.visible = change.visible
                sprite.rotation_style = change.rotation_style
        elif action in ("add_script", "replace_script"):
            sprite = sprites.get(change.target)
            if sprite is None:
                continue
            if action == "replace_script":
                sprite.scripts = [
                    script
                    for script in sprite.scripts
                    if script.script_id != change.script_id
                ]
            sprite.scripts.append(
                ScriptSummary(
                    script_id=change.script_id,
                    target=change.target,
                    label=change.label or change.script_id,
                    hat=_hat_name(change.stack) if change.stack else "",
                    block_count=change.block_count,
                    owned=True,
                    tuples=change.stack,
                )
            )
        elif action == "delete_script":
            for sprite in sprites.values():
                sprite.scripts = [
                    script
                    for script in sprite.scripts
                    if script.script_id != change.script_id
                ]
    if applied.target not in sprites:
        applied.target = next(
            (name for name, sprite in sprites.items() if not sprite.is_stage),
            "Stage",
        )
    return applied


# --------------------------------------------------------------------------
# Dry-run stub provider
# --------------------------------------------------------------------------

_STUB_DSL = '''summary("Added a green-flag square-drawing script.")

@on_flag(target="Sprite1", label="draw_square")
def draw_square():
    pen_clear()
    pen_down()
    for _ in range(4):
        move(100)
        turn_right(90)
    pen_up()
'''


class StubProvider:
    """Offline provider for wiring checks: one canned reply per mode.

    Every turn returns the same valid square change set, so the whole
    pipeline (audit bundles, chaining, summary) runs without a network or
    key.  Model realism is not the point of ``--dry-run``.
    """

    name = "stub"

    def complete(self, request: ModelRequest) -> ModelReply:
        usage = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
        if request.reply_format == "dsl":
            return ModelReply(
                data={},
                model="stub",
                raw_text=_STUB_DSL,
                usage=usage,
                latency_ms=5,
            )
        return ModelReply(
            data=draw_square_response(),
            model="stub",
            # The real provider always exposes the exact completion text; the
            # audit bundle's attempts/NN/raw.txt depends on it.
            raw_text=json.dumps(draw_square_response(), indent=2),
            usage=usage,
            latency_ms=5,
        )


# --------------------------------------------------------------------------
# The runner
# --------------------------------------------------------------------------


@dataclass
class Meta:
    """Bridge facts recorded in the manifest and audit bundles."""

    profile: str = "stub"
    model: str = "stub"
    base_url: str = ""


def run_step(
    provider: Any,
    store: AuditStore,
    meta: Meta,
    step: Step,
    scenario: str,
    run: int,
    mode: str,
    context: ProjectContext,
    turn_budget_s: float,
    history: ConversationHistory | None = None,
) -> tuple[dict[str, Any], Any]:
    """Run one turn, write its audit bundle, return the record and result.

    ``history`` is the scenario chain's shared store.  The agent reads it when
    it builds the prompt; the runner appends the turn at the same success point
    the server's ``#applied`` acknowledgement uses (a turn that applied).
    """
    os.environ["HARNESS_GENERATOR"] = mode
    request_id = f"{step.name}-{mode}-r{run}"
    audit = store.start_turn(
        request_id=request_id,
        prompt=step.prompt,
        target=context.target,
        context=context,
        profile=meta.profile,
        model=meta.model,
        base_url=meta.base_url,
        turn_budget_s=turn_budget_s,
        context_literal=None,
        generator=mode,
    )
    agent = Agent(provider, context, audit=audit, history=history)
    started = time.monotonic()
    outcome = "error:internal"
    error_text = ""
    attempts = 0
    changes = 0
    result: Any = None
    try:
        result = agent.handle(
            step.prompt,
            request_id,
            deadline=time.monotonic() + turn_budget_s,
        )
        outcome = "ok"
        attempts = result.attempts
        changes = len(result.compiled.changes)
        if history is not None:
            history.record_result(step.prompt, result)
    except ValidationError as exc:
        outcome = "error:validation"
        attempts = exc.attempts or 0
        error_text = "; ".join(str(issue) for issue in exc.issues)
    except ProviderError as exc:
        outcome = f"error:{exc.code}"
        error_text = exc.user_message()
    except Exception as exc:  # defensive: keep the benchmark running
        outcome = "error:internal"
        error_text = f"{type(exc).__name__}: {exc}"
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if audit is not None:
        audit.finish(
            outcome=outcome,
            attempts=attempts,
            changes=changes,
            elapsed_ms=elapsed_ms,
            error=error_text,
            result=result,
        )
    usage = dict(getattr(result, "usage", None) or {})
    record: dict[str, Any] = {
        "scenario": scenario,
        "step": step.name,
        "run": run,
        "mode": mode,
        "history": history is not None,
        "request_id": request_id,
        "dir": audit.root.name if audit is not None else "",
        "outcome": outcome,
        "attempts": attempts,
        "changes": changes,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "elapsed_ms": elapsed_ms,
        "summary": str(getattr(getattr(result, "compiled", None), "summary", "") or ""),
        "error": error_text,
    }
    return record, result


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per (step, mode) aggregates over every recorded turn."""
    rows: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in records:
        key = (record["scenario"], record["step"], record["mode"])
        rows.setdefault(key, []).append(record)
    summary: list[dict[str, Any]] = []
    for (scenario, step, mode), turns in sorted(rows.items()):
        ok_turns = [turn for turn in turns if turn["outcome"] == "ok"]
        attempts_values = [
            turn["attempts"] for turn in ok_turns if turn["attempts"]
        ]
        completion_values = [
            turn["completion_tokens"]
            for turn in ok_turns
            if turn["completion_tokens"] is not None
        ]
        elapsed_values = [turn["elapsed_ms"] for turn in ok_turns]

        def avg(values: list[int]) -> float | None:
            return round(sum(values) / len(values), 1) if values else None

        outcome_counts: dict[str, int] = {}
        for turn in turns:
            outcome_counts[turn["outcome"]] = (
                outcome_counts.get(turn["outcome"], 0) + 1
            )
        summary.append(
            {
                "scenario": scenario,
                "step": step,
                "mode": mode,
                "turns": len(turns),
                "ok": len(ok_turns),
                "avg_attempts": avg(attempts_values),
                "avg_completion_tokens": avg(completion_values),
                "total_completion_tokens": sum(completion_values),
                "avg_elapsed_ms": avg(elapsed_values),
                "outcomes": outcome_counts,
            }
        )
    return summary


def _flip_verdict(summary: list[dict[str, Any]]) -> dict[str, Any]:
    """The PY_DSL_SCOPE section-8 success criteria, as far as they compute."""
    by_mode: dict[str, list[dict[str, Any]]] = {"json": [], "dsl": []}
    for row in summary:
        by_mode.setdefault(row["mode"], []).append(row)

    def totals(mode: str) -> dict[str, Any]:
        rows = by_mode.get(mode, [])
        ok = sum(row["ok"] for row in rows)
        turns = sum(row["turns"] for row in rows)
        attempts = [
            row["avg_attempts"] for row in rows if row["avg_attempts"] is not None
        ]
        completion = [
            row["avg_completion_tokens"]
            for row in rows
            if row["avg_completion_tokens"] is not None
        ]
        bad_json = sum(
            count
            for row in rows
            for outcome, count in row["outcomes"].items()
            if outcome == "error:bad_json"
        )
        return {
            "applied_rate": round(ok / turns, 3) if turns else None,
            "ok": ok,
            "turns": turns,
            "avg_attempts": round(sum(attempts) / len(attempts), 2)
            if attempts
            else None,
            "avg_completion_tokens": round(
                sum(completion) / len(completion), 1
            )
            if completion
            else None,
            "bad_json_outcomes": bad_json,
        }

    return {"json": totals("json"), "dsl": totals("dsl")}


def _print_summary(summary: list[dict[str, Any]], verdict: dict[str, Any]) -> None:
    print()
    print("step                 mode  ok     att   compl   ms")
    for row in summary:
        name = f"{row['scenario']}/{row['step']}"
        print(
            f"{name:20} {row['mode']:5} "
            f"{row['ok']}/{row['turns']:<4} "
            f"{str(row['avg_attempts']):4} "
            f"{str(row['avg_completion_tokens']):7} "
            f"{str(row['avg_elapsed_ms']):7}"
        )
        failures = {
            outcome: count
            for outcome, count in row["outcomes"].items()
            if outcome != "ok"
        }
        if failures:
            print(
                f"{'':20} {'':5} "
                + ", ".join(f"{name}={count}" for name, count in failures.items())
            )
    print()
    for mode in ("json", "dsl"):
        totals = verdict[mode]
        print(
            f"{mode}: applied {totals['ok']}/{totals['turns']}"
            f" (rate {totals['applied_rate']}), "
            f"avg attempts {totals['avg_attempts']}, "
            f"avg completion tokens {totals['avg_completion_tokens']}, "
            f"bad_json outcomes {totals['bad_json_outcomes']}"
        )


def _warn_if_media_missing() -> None:
    root = os.environ.get("HARNESS_MEDIA_ROOT")
    media = Path(root) if root else ROOT / "scratch" / "base" / "Media"
    if media.is_dir() and any(media.iterdir()):
        return
    print(
        "warning: the media library is missing or empty; costume/backdrop "
        "references will fail validation. Copy scratch/base/Media from the "
        "main tree before live runs (HANDOFF section 1a).",
        file=sys.stderr,
    )


def _load_key() -> None:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return
    key_file = ROOT / "bridge" / ".deepseek_key"
    if not key_file.exists():
        raise SystemExit(
            "DEEPSEEK_API_KEY is not set and bridge/.deepseek_key does not exist"
        )
    key = key_file.read_text(encoding="utf-8").strip()
    if not key:
        raise SystemExit("bridge/.deepseek_key is empty")
    # Set only; never print or log the value.
    os.environ["DEEPSEEK_API_KEY"] = key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Phase C ladder: the same prompts through both reply "
            "generators, one full audit bundle per turn."
        )
    )
    parser.add_argument(
        "-Runs",
        "--runs",
        type=int,
        default=3,
        help="repetitions per mode (default: 3)",
    )
    parser.add_argument(
        "-Modes",
        "--modes",
        default="json,dsl",
        help="comma-separated subset of json,dsl (default: both)",
    )
    parser.add_argument(
        "-Scenarios",
        "--scenarios",
        default="",
        help="comma-separated subset of: "
        + ", ".join(SCENARIOS)
        + " (default: all)",
    )
    parser.add_argument(
        "-Profile",
        "--profile",
        default="",
        help="model profile from harness.ini (default: the resolved default)",
    )
    parser.add_argument(
        "-AuditDir",
        "--audit-dir",
        default="",
        help="audit directory for this session (default: a fresh stamped "
        "directory under scratch/base/audit/ladder)",
    )
    parser.add_argument(
        "-TurnBudget",
        "--turn-budget",
        type=float,
        default=240.0,
        help="seconds per turn (default: 240, like the bridge)",
    )
    parser.add_argument(
        "-PromptBudget",
        "--prompt-budget",
        type=int,
        default=0,
        help="prompt character budget (default: the bridge's own 90000)",
    )
    parser.add_argument(
        "-DryRun",
        "--dry-run",
        action="store_true",
        help="canned replies through a stub provider; no network or key",
    )
    parser.add_argument(
        "-History",
        "--history",
        choices=("on", "off"),
        default="on",
        help="carry conversation history across a scenario's steps "
        "(default: on; run both for the A/B)",
    )
    args = parser.parse_args(argv)

    if args.runs < 1:
        raise SystemExit("-Runs must be at least 1")
    modes = [mode.strip() for mode in args.modes.split(",") if mode.strip()]
    if not modes or any(mode not in MODES for mode in modes):
        raise SystemExit(f"-Modes must be a subset of: {', '.join(MODES)}")
    if args.scenarios.strip():
        wanted = [
            name.strip()
            for name in args.scenarios.split(",")
            if name.strip()
        ]
        unknown = [name for name in wanted if name not in SCENARIOS]
        if unknown:
            raise SystemExit(
                f"unknown scenario(s): {', '.join(unknown)}; available: "
                + ", ".join(SCENARIOS)
            )
        scenarios = {
            name: SCENARIOS[name] for name in wanted if name in SCENARIOS
        }
    else:
        scenarios = dict(SCENARIOS)

    if args.prompt_budget > 0:
        os.environ["HARNESS_PROMPT_BUDGET"] = str(args.prompt_budget)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.audit_dir:
        audit_dir = Path(args.audit_dir).expanduser()
    else:
        audit_dir = (
            ROOT / "scratch" / "base" / "audit" / "ladder" / stamp
        )
    audit_dir.mkdir(parents=True, exist_ok=True)
    store = AuditStore(AuditSettings(mode="full", directory=audit_dir, keep=0))

    if args.dry_run:
        provider = StubProvider()
        meta = Meta(profile="stub", model="stub", base_url="")
    else:
        _load_key()
        _warn_if_media_missing()
        config = resolve_config(args.profile or None)
        from harness.providers.openai_compat import OpenAICompatProvider

        provider = OpenAICompatProvider(config)
        meta = Meta(
            profile=config.profile,
            model=config.model,
            base_url=config.base_url,
        )

    total_turns = args.runs * len(modes) * sum(
        len(steps) for steps in scenarios.values()
    )
    history_on = args.history == "on"
    print(f"ladder audit dir: {audit_dir}")
    print(
        f"runs={args.runs} modes={','.join(modes)} "
        f"scenarios={','.join(scenarios)} turns={total_turns} "
        f"history={args.history}"
    )
    if not args.dry_run:
        estimate = total_turns * 20
        print(
            f"profile={meta.profile} model={meta.model}; "
            f"rough live duration: {estimate // 60}-{estimate * 2 // 60} min"
        )
    print()

    manifest: dict[str, Any] = {
        "started_at": stamp,
        "dry_run": bool(args.dry_run),
        "runs": args.runs,
        "modes": modes,
        "scenarios": list(scenarios),
        "turn_budget_s": args.turn_budget,
        "history": history_on,
        "profile": meta.profile,
        "model": meta.model,
        "base_url": meta.base_url,
        "turns": [],
    }
    records: list[dict[str, Any]] = []
    exit_code = 0

    def _save_progress() -> None:
        manifest["turns"] = records
        _write_json(audit_dir / "manifest.json", manifest)
        summary = _summarize(records)
        _write_json(
            audit_dir / "summary.json",
            {"summary": summary, "flip_verdict": _flip_verdict(summary)},
        )

    try:
        for run in range(1, args.runs + 1):
            for mode in modes:
                for scenario, steps in scenarios.items():
                    context = clean_context()
                    history = ConversationHistory() if history_on else None
                    failed_step: str | None = None
                    for step in steps:
                        if failed_step is not None:
                            print(
                                f"[run {run}/{args.runs} {mode}] "
                                f"{scenario}/{step.name} skipped "
                                f"({failed_step} failed)"
                            )
                            continue
                        record, result = run_step(
                            provider,
                            store,
                            meta,
                            step,
                            scenario,
                            run,
                            mode,
                            context,
                            args.turn_budget,
                            history,
                        )
                        records.append(record)
                        _save_progress()
                        if record["outcome"] == "ok":
                            context = context_after_apply(context, result)
                            completion = record["completion_tokens"]
                            print(
                                f"[run {run}/{args.runs} {mode}] "
                                f"{scenario}/{step.name} ok "
                                f"attempts={record['attempts']} "
                                f"changes={record['changes']} "
                                f"compl={completion if completion is not None else '-'} tok "
                                f"{record['elapsed_ms'] / 1000:.1f}s"
                            )
                        else:
                            failed_step = step.name
                            exit_code = 1
                            print(
                                f"[run {run}/{args.runs} {mode}] "
                                f"{scenario}/{step.name} {record['outcome']}: "
                                f"{record['error'][:120]}"
                            )
    except KeyboardInterrupt:
        print("\ninterrupted; partial manifest and summary kept")
        _save_progress()
        return 130

    _save_progress()
    summary = _summarize(records)
    verdict = _flip_verdict(summary)
    _print_summary(summary, verdict)

    print()
    print(f"manifest: {audit_dir / 'manifest.json'}")
    print(f"summary:  {audit_dir / 'summary.json'}")
    print(
        "score:    python tools\\audit.py score "
        f"--dir {audit_dir} --group generator"
    )
    print("rubric:   docs/LADDER_RUBRIC.md (the human half)")
    if exit_code:
        print("note: at least one turn failed; failures are ladder data too")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
