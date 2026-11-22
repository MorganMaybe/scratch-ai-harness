"""Inspect per-turn audit bundles written by the bridge.

Examples::

    python tools\\audit.py list
    python tools\\audit.py show latest
    python tools\\audit.py show latest --raw
    python tools\\audit.py raw latest
    python tools\\audit.py score
    python tools\\audit.py score --group generator

Audit bundles are opt-in.  Start the bridge with ``--audit full`` (or
``.\\run_live.ps1``, which defaults to full) to get prompts, raw model replies,
validation issues and compiled output under ``scratch/base/audit``.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "scratch" / "base" / "audit"


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _read_index(directory: Path) -> list[dict[str, Any]]:
    path = directory / "index.jsonl"
    entries: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return entries
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            entry = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _turn_dirs(directory: Path) -> list[Path]:
    try:
        return sorted(
            (path for path in directory.iterdir() if path.is_dir()),
            key=lambda path: path.name,
        )
    except OSError:
        return []


def _resolve_turn(directory: Path, name: str | None) -> Path | None:
    if name and name not in {"latest", "last"}:
        candidate = Path(name)
        if candidate.is_dir():
            return candidate
        candidate = directory / name
        if candidate.is_dir():
            return candidate
        return None
    index = _read_index(directory)
    if index:
        latest = index[-1].get("dir")
        if latest:
            candidate = directory / str(latest)
            if candidate.is_dir():
                return candidate
    dirs = _turn_dirs(directory)
    return dirs[-1] if dirs else None


def _text(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _short(value: Any, limit: int) -> str:
    text = _text(value).replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def cmd_list(args: argparse.Namespace) -> int:
    directory = Path(args.dir).expanduser()
    entries = _read_index(directory)
    if not entries:
        print(f"no audit turns in {directory}")
        print("start the bridge with --audit full (or .\\run_live.ps1)")
        return 0
    if args.limit > 0:
        entries = entries[-args.limit :]
    if args.json:
        print(json.dumps(entries, indent=2))
        return 0

    print(
        f"{'STARTED':24} {'OUTCOME':17} {'ATT':>3} {'CHG':>3} "
        f"{'PROMPT':>7} {'COMPL':>7} {'REASON':>7} {'CACHE':>7} {'MS':>7}  TURN"
    )
    for entry in entries:
        print(
            f"{_short(entry.get('started_at'), 24):24} "
            f"{_short(entry.get('outcome'), 17):17} "
            f"{_text(entry.get('attempts')):>3} "
            f"{_text(entry.get('changes')):>3} "
            f"{_text(entry.get('prompt_tokens')):>7} "
            f"{_text(entry.get('completion_tokens')):>7} "
            f"{_text(entry.get('reasoning_tokens')):>7} "
            f"{_text(entry.get('cached_tokens')):>7} "
            f"{_text(entry.get('elapsed_ms')):>7}  "
            f"{_short(entry.get('dir') or entry.get('turn'), 70)}"
        )
        error = entry.get("error")
        if error:
            print(f"    {_short(error, 160)}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    directory = Path(args.dir).expanduser()
    turn = _resolve_turn(directory, args.turn)
    if turn is None:
        print(f"no audit turn found in {directory}")
        return 1

    meta = _read_json(turn / "meta.json", {}) or {}
    outcome = _read_json(turn / "outcome.json", {}) or {}
    assembly = _read_json(turn / "prompts" / "assembly.json", {}) or {}
    chunks = _read_json(turn / "chunks" / "plan.json", {}) or {}
    attempts = []
    for path in sorted((turn / "attempts").glob("*/meta.json")):
        attempts.append(_read_json(path, {}) or {})

    if args.json:
        print(
            json.dumps(
                {
                    "turn": str(turn),
                    "meta": meta,
                    "outcome": outcome,
                    "assembly": assembly,
                    "attempts": attempts,
                    "chunks": chunks,
                },
                indent=2,
            )
        )
        return 0

    print(f"turn:       {turn}")
    print(f"request:    {_text(meta.get('request_id'))}")
    print(f"outcome:    {_text(outcome.get('outcome'))}")
    print(
        f"attempts:   {_text(outcome.get('attempts'))}  "
        f"changes: {_text(outcome.get('changes'))}  "
        f"elapsed: {_text(outcome.get('elapsed_ms'))} ms"
    )
    usage = outcome.get("usage") or {}
    if usage:
        print(
            "tokens:     "
            f"prompt={_text(usage.get('prompt_tokens'))} "
            f"completion={_text(usage.get('completion_tokens'))} "
            f"total={_text(usage.get('total_tokens'))}"
        )
    if outcome.get("summary"):
        print(f"summary:    {outcome['summary']}")
    if outcome.get("error"):
        print(f"error:      {outcome['error']}")
    if meta.get("target"):
        print(f"target:     {meta['target']}")
    if meta.get("model"):
        print(f"model:      {meta['model']} ({_text(meta.get('profile'))})")

    system_info = assembly.get("system") or {}
    user_info = assembly.get("user") or {}
    if system_info:
        truncations = system_info.get("truncations") or {}
        print(
            "system:     "
            f"{_text(system_info.get('chars'))} chars "
            f"(~{_text(system_info.get('estimated_tokens'))} tokens), "
            f"appendix={_text(system_info.get('has_appendix'))}, "
            f"truncations={truncations or '-'}"
        )
        packs = system_info.get("context_packs") or []
        if packs:
            print(f"packs:      {', '.join(str(p) for p in packs)}")
    if user_info:
        print(
            "context:    "
            f"level={_text(user_info.get('level'))}, "
            f"{_text(user_info.get('context_chars'))} chars, "
            f"truncated={_text(user_info.get('truncated'))}, "
            f"dropped={_text(user_info.get('dropped_chars'))}"
        )

    if attempts:
        print("attempts:")
        for attempt in attempts:
            detail = (
                f"  {_text(attempt.get('number')).rjust(2)}: "
                f"raw={_text(attempt.get('raw_available'))} "
                f"content={_text(attempt.get('content_chars'))} "
                f"reasoning={_text(attempt.get('reasoning_tokens'))} "
                f"cache={_text(attempt.get('cached_tokens'))} "
                f"issues={_text(attempt.get('issue_count'))} "
                f"finish={_text(attempt.get('finish_reason'))}"
            )
            if attempt.get("fragment"):
                detail += f" fragment={_text(attempt.get('fragment_indices'))}"
            if attempt.get("error_code"):
                detail += f" error={attempt['error_code']}"
            if attempt.get("parse_error"):
                detail += f" parse={_short(attempt['parse_error'], 80)}"
            print(detail)

    if chunks:
        print(
            f"chunks:     source={_text(chunks.get('source'))} "
            f"count={len(chunks.get('changes') or [])}"
        )
        for item in chunks.get("changes") or []:
            print(
                f"  {_text(item.get('index'))}: {_text(item.get('action'))} "
                f"{_text(item.get('target'))} / {_text(item.get('label'))} "
                f"({_text(item.get('block_count'))} blocks)"
            )

    if args.prompts:
        print("\n--- system prompt ---")
        print(_read_text(turn / "prompts" / "system.txt"))
        print("\n--- first user prompt ---")
        print(_read_text(turn / "prompts" / "user-01.txt"))

    if args.raw:
        print("\n--- raw model replies ---")
        found = False
        for path in sorted((turn / "attempts").glob("*/raw.txt")):
            found = True
            print(f"\n[{path.relative_to(turn)}]")
            print(_read_text(path))
        if not found:
            print("(no raw replies recorded; the provider or mock may not expose them)")
    return 0


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "(missing)"


def cmd_raw(args: argparse.Namespace) -> int:
    directory = Path(args.dir).expanduser()
    turn = _resolve_turn(directory, args.turn)
    if turn is None:
        print(f"no audit turn found in {directory}")
        return 1
    paths = sorted((turn / "attempts").glob("*/raw.txt"))
    if args.attempt:
        paths = [
            path
            for path in paths
            if path.parent.name == f"{int(args.attempt):02d}"
        ]
    if not paths:
        print(f"no raw model replies recorded in {turn}")
        return 0
    for path in paths:
        if len(paths) > 1:
            print(f"--- {path.relative_to(turn)} ---")
        print(_read_text(path))
    return 0


def _generator_of(directory: Path, entry: dict[str, Any]) -> str:
    """Return one turn's ``generator`` value, defaulting to ``json``.

    A missing or unreadable ``meta.json``, a non-object payload, a missing
    field or a non-string value all fall back to ``json`` so an old bundle can
    never break a grouped scan.
    """
    turn_name = entry.get("dir") or entry.get("turn")
    if not turn_name:
        return "json"
    meta = _read_json(directory / str(turn_name) / "meta.json", {})
    if not isinstance(meta, dict):
        return "json"
    value = meta.get("generator")
    if not isinstance(value, str):
        return "json"
    text = value.strip().lower()
    return text or "json"


def _score_entries(
    directory: Path, entries: list[dict[str, Any]]
) -> tuple[dict[str, Any], Counter[str], Counter[str], Counter[str]]:
    """Compute the existing score payload for a set of index entries."""
    outcomes = Counter(str(entry.get("outcome") or "unknown") for entry in entries)
    errors = Counter(
        str(entry.get("error")) for entry in entries if entry.get("error")
    )
    attempts = sum(int(entry.get("attempts") or 0) for entry in entries)
    turns = len(entries)
    prompt_tokens = sum(int(entry.get("prompt_tokens") or 0) for entry in entries)
    completion_tokens = sum(
        int(entry.get("completion_tokens") or 0) for entry in entries
    )
    reasoning_tokens = sum(
        int(entry.get("reasoning_tokens") or 0) for entry in entries
    )
    cached_tokens = sum(int(entry.get("cached_tokens") or 0) for entry in entries)
    latencies = [int(entry.get("elapsed_ms") or 0) for entry in entries]
    elapsed = sum(latencies)
    multi_attempt = sum(
        1 for entry in entries if int(entry.get("attempts") or 0) > 1
    )

    issues: Counter[str] = Counter()
    for entry in entries:
        turn_name = entry.get("dir") or entry.get("turn")
        if not turn_name:
            continue
        for path in (directory / str(turn_name) / "attempts").glob("*/validation.json"):
            items = _read_json(path, []) or []
            for item in items:
                if isinstance(item, dict) and item.get("message"):
                    issues[str(item["message"])] += 1

    payload = {
        "turns": turns,
        "outcomes": dict(outcomes),
        "errors": dict(errors),
        "attempts": attempts,
        "average_attempts": round(attempts / turns, 2) if turns else 0.0,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "elapsed_ms": elapsed,
        "average_elapsed_ms": int(elapsed / turns) if turns else 0,
        "max_elapsed_ms": max(latencies) if latencies else 0,
        "multi_attempt_turns": multi_attempt,
        "validation_issues": dict(issues.most_common(20)),
    }
    return payload, outcomes, errors, issues


def _print_score(
    payload: dict[str, Any],
    outcomes: Counter[str],
    errors: Counter[str],
    issues: Counter[str],
) -> None:
    print(f"turns:      {payload['turns']}")
    print("outcomes:   " + ", ".join(f"{key}={value}" for key, value in outcomes.most_common()))
    print(f"attempts:   {payload['attempts']} (avg {payload['average_attempts']})")
    print(
        f"tokens:     prompt={payload['prompt_tokens']} completion={payload['completion_tokens']} "
        f"reasoning={payload['reasoning_tokens']} cached={payload['cached_tokens']} "
        f"total={payload['total_tokens']}"
    )
    print(
        f"elapsed:    {payload['elapsed_ms']} ms (avg {payload['average_elapsed_ms']} ms, "
        f"max {payload['max_elapsed_ms']} ms; "
        f"multi-attempt turns {payload['multi_attempt_turns']})"
    )
    if errors:
        print("errors:")
        for message, count in errors.most_common(10):
            print(f"  {count:>3}  {_short(message, 160)}")
    if issues:
        print("validation issues:")
        for message, count in issues.most_common(10):
            print(f"  {count:>3}  {_short(message, 160)}")


def cmd_score(args: argparse.Namespace) -> int:
    directory = Path(args.dir).expanduser()
    entries = _read_index(directory)
    if not entries:
        print(f"no audit turns in {directory}")
        return 0

    if getattr(args, "group", None) == "generator":
        groups: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            groups.setdefault(_generator_of(directory, entry), []).append(entry)
        if args.json:
            payload = {
                name: _score_entries(directory, group)[0]
                for name, group in sorted(groups.items())
            }
            print(json.dumps(payload, indent=2))
            return 0
        for position, (name, group) in enumerate(sorted(groups.items())):
            if position:
                print()
            print(f"generator:  {name}")
            payload, outcomes, errors, issues = _score_entries(directory, group)
            _print_score(payload, outcomes, errors, issues)
        return 0

    payload, outcomes, errors, issues = _score_entries(directory, entries)
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    _print_score(payload, outcomes, errors, issues)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Scratch AI audit bundles")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(name: str, help_text: str) -> argparse.ArgumentParser:
        item = sub.add_parser(name, help=help_text)
        item.add_argument(
            "--dir",
            default=str(DEFAULT_DIR),
            help="audit directory (default: scratch/base/audit)",
        )
        item.add_argument("--json", action="store_true", help="print JSON")
        return item

    p = common("list", "list recent turns from index.jsonl")
    p.add_argument("--limit", type=int, default=20, help="show the last N turns (0 = all)")
    p.set_defaults(func=cmd_list)

    p = common("show", "show one turn (default: latest)")
    p.add_argument("turn", nargs="?", default="latest")
    p.add_argument("--raw", action="store_true", help="print the raw model replies")
    p.add_argument("--prompts", action="store_true", help="print the system and first user prompt")
    p.set_defaults(func=cmd_show)

    p = common("raw", "print raw model replies for one turn")
    p.add_argument("turn", nargs="?", default="latest")
    p.add_argument("--attempt", type=int, help="only this attempt number")
    p.set_defaults(func=cmd_raw)

    p = common(
        "score",
        "aggregate outcomes, tokens and validation issues "
        "(--group generator splits the report by generator)",
    )
    p.add_argument(
        "--group",
        choices=("generator",),
        help="break the score down per meta.json 'generator' value (missing = json)",
    )
    p.set_defaults(func=cmd_score)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
