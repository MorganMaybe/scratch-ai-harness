from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge" / "src"))

from harness.context_doc import (  # noqa: E402
    available_context_packs,
    load_context_doc,
    load_context_packs,
)
from harness.prompts import build_system_prompt, estimate_tokens  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview the system prompt (catalog + media + context appendix)"
    )
    parser.add_argument("--target", default="Sprite1", help="sprite or Stage")
    parser.add_argument("--budget", type=int, default=60000, help="character budget")
    parser.add_argument("--no-context", action="store_true", help="omit SCRATCH_AI_CONTEXT.md")
    parser.add_argument(
        "--packs",
        default="",
        help="comma-separated context packs to include (for example clones,scrolling)",
    )
    parser.add_argument("--list-packs", action="store_true", help="list available context packs")
    parser.add_argument("--out", help="write the full prompt to this file")
    parser.add_argument("--show", action="store_true", help="print the full prompt")
    args = parser.parse_args()

    if args.list_packs:
        for name, summary in available_context_packs().items():
            print(f"{name:12} {summary}")
        return

    doc = "" if args.no_context else load_context_doc()
    names = [part.strip() for part in args.packs.split(",") if part.strip()]
    extra = load_context_packs(names)
    budget = args.budget
    if extra:
        had_core = bool(doc)
        doc = f"{extra}\n\n{doc}".strip() if doc else extra
        budget += len(extra) + (2 if had_core else 0)
    prompt = build_system_prompt(
        target=args.target,
        budget_chars=budget,
        context_doc=doc,
    )

    print(f"target: {args.target}")
    print(f"budget: {budget} chars" + (f" (base {args.budget} + packs)" if extra else ""))
    print(f"context appendix: {'off' if args.no_context else f'{len(doc)} chars'}")
    if names:
        print(f"context packs: {', '.join(names)}")
    print(f"prompt: {len(prompt)} chars, ~{estimate_tokens(prompt)} tokens")
    for marker in (
        r"\[context appendix truncated \d+ chars\]",
        r"\[media index truncated \d+ chars\]",
        r"\[catalog truncated \d+ chars\]",
    ):
        if re.search(marker, prompt):
            print(f"warning: truncation marker used: {marker}")
    if "Additional Scratch context" in prompt:
        print("appendix section: present")
    else:
        print("appendix section: absent")
    if args.out:
        path = Path(args.out).expanduser().resolve()
        path.write_text(prompt, encoding="utf-8")
        print(f"wrote {path}")
    if args.show:
        print()
        print(prompt)


if __name__ == "__main__":
    main()
