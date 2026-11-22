"""Smoke-run the Scratch-Python generator loop.

Two turns against a synthetic project: a square, then a bigger square that
says Done!  ``--dry-run`` drives the same Agent loop with canned DSL replies
and no network or key; the live path reads ``bridge/.deepseek_key`` into the
environment (never printed) and calls the configured profile.

    python tools\\dsl_smoke.py --dry-run
    python tools\\dsl_smoke.py -Generator dsl -Profile opencode-go
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge" / "src"))

from harness.agent import Agent  # noqa: E402
from harness.context import ProjectContext, SpriteContext  # noqa: E402
from harness.providers.base import ProviderError  # noqa: E402
from harness.providers.mock import MockProvider  # noqa: E402

SQUARE_DSL = '''summary("Added a green-flag square-drawing script.")

@on_flag(target="Sprite1", label="draw_square")
def draw_square():
    pen_clear()
    pen_down()
    for _ in range(4):
        move(100)
        turn_right(90)
    pen_up()
'''

BIGGER_DSL = '''summary("Made the square bigger and added a message.")

@on_flag(target="Sprite1", label="draw_square", script_id="ai-1")
def draw_square():
    pen_clear()
    pen_down()
    for _ in range(4):
        move(150)
        turn_right(90)
    pen_up()
    say("Done!")
'''

FIRST_REQUEST = "Make the cat draw a square when I click the green flag."
SECOND_REQUEST = "Make it bigger and say Done!"


def synthetic_context() -> ProjectContext:
    """Stage plus Sprite1, built directly so the smoke run needs no image."""
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


def _usage_text(usage: dict[str, int] | None) -> str:
    if not usage:
        return "-"
    return " ".join(f"{key}={value}" for key, value in usage.items())


def _print_turn(
    generator: str,
    number: int,
    result: Any = None,
    error: Exception | None = None,
) -> bool:
    print(f"turn {number}: generator={generator}")
    if error is not None:
        code = getattr(error, "code", type(error).__name__)
        message = (
            error.user_message()
            if isinstance(error, ProviderError)
            else str(error)
        )
        print(f"  failed: error_code={code}")
        print(f"  message: {' '.join(message.split())}")
        return False
    assert result is not None
    print("  ok")
    for change in result.compiled.changes:
        details = [f"action={change.action}"]
        for name in ("target", "label", "script_id"):
            value = getattr(change, name, "")
            if value:
                details.append(f"{name}={value}")
        details.append(f"blocks={change.block_count}")
        print("  " + " ".join(details))
    print(
        "  model={} latency_ms={} usage={}".format(
            result.model or "-", result.latency_ms, _usage_text(result.usage)
        )
    )
    return True


def run_turns(llm: Any, generator: str) -> int:
    """Run both smoke turns; return the process exit code."""
    agent = Agent(llm, synthetic_context(), max_repairs=2)
    requests = (FIRST_REQUEST, SECOND_REQUEST)
    for number, request in enumerate(requests, start=1):
        try:
            result = agent.handle(request, request_id=number)
        except (ProviderError, ValueError) as exc:
            _print_turn(generator, number, error=exc)
            return 1
        if not _print_turn(generator, number, result=result):
            return 1
        agent.register_applied(result)
    print("all turns produced a compiled change set")
    return 0


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
        description="Run two Scratch-Python generator turns as a smoke test."
    )
    parser.add_argument(
        "-Generator",
        "--generator",
        default="dsl",
        choices=("json", "dsl"),
        help="reply generator for the turns (default: dsl)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="use canned DSL replies and the mock provider; no network or key",
    )
    parser.add_argument(
        "-Profile",
        "--profile",
        default="",
        help="model profile from harness.ini (default: resolve_config's choice)",
    )
    args = parser.parse_args(argv)
    os.environ["HARNESS_GENERATOR"] = args.generator

    if args.dry_run:
        if args.generator != "dsl":
            raise SystemExit(
                "--dry-run drives canned DSL replies; use -Generator dsl"
            )
        return run_turns(MockProvider([SQUARE_DSL, BIGGER_DSL]), args.generator)

    _load_key()
    from harness.config import resolve_config
    from harness.providers.openai_compat import OpenAICompatProvider

    config = resolve_config(args.profile or None)
    return run_turns(OpenAICompatProvider(config), args.generator)


if __name__ == "__main__":
    sys.exit(main())
