"""Loaded-sprite memory: the store, the switch, and cross-turn prompt seeding.

Lazy sprite detail costs a model round trip per load and the load limit is per
turn, so a follow-up turn used to re-request the same bodies.  The bridge keeps
a bounded, process-local ring of **names**; bodies are always re-rendered from
the current context, never cached.  These tests pin:

* the store bound and case-insensitive de-duplication;
* ``resolve_sprite_memory`` precedence (env > ini > on);
* memory off leaving prompts byte-identical to the per-turn bridge;
* a successful load being remembered, and the next turn announcing the detail
  in its first prompt while showing the CURRENT bodies.
"""

from __future__ import annotations

import threading

import pytest

from harness.agent import Agent
from harness.config import ConfigError, resolve_sprite_memory
from harness.context import ProjectContext, ScriptSummary
from harness.llm import MockLLM, draw_square_response
from harness.server import Bridge
from harness.smalltalk import Sym
from harness.sprite_memory import MAX_SPRITES, LoadedSpriteMemory


def context_with_detail(*, steps: int = 10) -> ProjectContext:
    context = ProjectContext.demo()
    context.sprites["Sprite1"].scripts.append(
        ScriptSummary(
            script_id="ai-1",
            target="Sprite1",
            label="bounce",
            hat="EventHatMorph",
            block_count=2,
            owned=True,
            tuples=[
                [Sym("EventHatMorph"), "Scratch-StartClicked"],
                [Sym("forward:"), steps],
            ],
        )
    )
    return context


# --- the store --------------------------------------------------------------


def test_store_is_bounded_and_drops_the_oldest_names():
    memory = LoadedSpriteMemory(max_sprites=3)
    for index in range(5):
        memory.remember([f"Sprite{index}"])

    assert len(memory) == 3
    assert memory.snapshot() == ["Sprite2", "Sprite3", "Sprite4"]
    assert MAX_SPRITES == 8


def test_store_deduplicates_case_insensitively_and_moves_to_the_newest_slot():
    memory = LoadedSpriteMemory()
    memory.remember(["Bat", "Crab"])
    memory.remember(["bat"])

    assert memory.snapshot() == ["Crab", "bat"]
    assert len(memory) == 2


def test_store_ignores_blank_names_and_clear_empties_it():
    memory = LoadedSpriteMemory()
    memory.remember(["", "  ", "Bat"])
    assert memory.snapshot() == ["Bat"]

    memory.clear()
    assert memory.snapshot() == []
    with pytest.raises(ValueError):
        LoadedSpriteMemory(max_sprites=0)


def test_store_is_safe_under_concurrent_remember_and_snapshot():
    memory = LoadedSpriteMemory(max_sprites=16)
    errors: list[BaseException] = []

    def writer(prefix: str) -> None:
        try:
            for index in range(200):
                memory.remember([f"{prefix}{index}"])
        except BaseException as exc:  # pragma: no cover - only on a real bug
            errors.append(exc)

    def reader() -> None:
        try:
            for _ in range(400):
                memory.snapshot()
        except BaseException as exc:  # pragma: no cover - only on a real bug
            errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=("a",)),
        threading.Thread(target=writer, args=("b",)),
        threading.Thread(target=reader),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(memory) == 16


# --- the switch -------------------------------------------------------------


def test_resolve_sprite_memory_defaults_on(tmp_path):
    assert resolve_sprite_memory(tmp_path / "missing.ini", env={}) is True


def test_resolve_sprite_memory_reads_the_harness_section(tmp_path):
    path = tmp_path / "harness.ini"
    path.write_text("[harness]\nsprite_memory=off\n", encoding="utf-8")
    assert resolve_sprite_memory(path, env={}) is False


def test_resolve_sprite_memory_env_wins_over_ini(tmp_path):
    path = tmp_path / "harness.ini"
    path.write_text("[harness]\nsprite_memory=off\n", encoding="utf-8")
    assert resolve_sprite_memory(path, env={"HARNESS_SPRITE_MEMORY": "on"}) is True
    assert resolve_sprite_memory(path, env={"HARNESS_SPRITE_MEMORY": " OFF "}) is False
    # Blank env falls through to the file.
    assert resolve_sprite_memory(path, env={"HARNESS_SPRITE_MEMORY": "  "}) is False


@pytest.mark.parametrize("value", ["yes", "true", "1", "sometimes"])
def test_resolve_sprite_memory_rejects_unknown_values(tmp_path, value):
    with pytest.raises(ConfigError):
        resolve_sprite_memory(
            tmp_path / "missing.ini", env={"HARNESS_SPRITE_MEMORY": value}
        )
    path = tmp_path / "harness.ini"
    path.write_text(f"[harness]\nsprite_memory={value}\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        resolve_sprite_memory(path, env={})


# --- prompts ----------------------------------------------------------------


def test_memory_off_leaves_prompts_identical_to_today():
    context = context_with_detail()
    baseline = MockLLM([draw_square_response()])
    Agent(baseline, context).handle("Make it bounce faster.", 1)

    off = MockLLM([draw_square_response()])
    memory = LoadedSpriteMemory()
    memory.remember(["Sprite1"])
    Agent(off, context, sprite_memory=None).handle("Make it bounce faster.", 1)

    assert off.calls[0] == baseline.calls[0]
    assert "# Loaded sprite detail" not in off.calls[0][0]
    assert "now included in the system prompt" not in off.calls[0][1]
    # A turn with the feature off never writes the shared store.
    assert memory.snapshot() == ["Sprite1"]


def test_a_successful_load_is_remembered():
    memory = LoadedSpriteMemory()
    provider = MockLLM(
        [{"load_sprite": ["Sprite1"], "reason": "need the bounce body"},
         draw_square_response()]
    )

    Agent(provider, context_with_detail(), sprite_memory=memory).handle(
        "Make it bounce faster.", 1
    )

    assert memory.snapshot() == ["Sprite1"]


def test_second_turn_seeds_detail_and_announces_it():
    memory = LoadedSpriteMemory()
    first = MockLLM(
        [{"load_sprite": ["Sprite1"]}, draw_square_response()]
    )
    Agent(first, context_with_detail(steps=10), sprite_memory=memory).handle(
        "Make it bounce faster.", 1
    )
    assert memory.snapshot() == ["Sprite1"]

    second = MockLLM([draw_square_response()])
    Agent(second, context_with_detail(steps=10), sprite_memory=memory).handle(
        "Now make it bounce slower.", 2
    )

    system, user = second.calls[0]
    assert "# Loaded sprite detail: Sprite1" in system
    assert '"steps":10' in system
    # The first user prompt carries the same "included" header a real load uses.
    assert "now included in the system prompt" in user
    assert "sprite detail: Sprite1" in user
    assert "Now make it bounce slower." in user


def test_seeded_bodies_reflect_the_current_context():
    memory = LoadedSpriteMemory()
    first = MockLLM(
        [{"load_sprite": ["Sprite1"]}, draw_square_response()]
    )
    Agent(first, context_with_detail(steps=10), sprite_memory=memory).handle(
        "Make it bounce faster.", 1
    )

    # The image edited the script between turns (undo/manual edit/replace).
    second = MockLLM([draw_square_response()])
    Agent(second, context_with_detail(steps=42), sprite_memory=memory).handle(
        "Now make it bounce slower.", 2
    )

    system = second.calls[0][0]
    assert '"steps":42' in system
    assert '"steps":10' not in system


def test_remembered_names_without_ai_scripts_are_dropped_for_the_turn():
    memory = LoadedSpriteMemory()
    memory.remember(["Sprite1", "Ghost"])
    provider = MockLLM([draw_square_response()])

    Agent(provider, ProjectContext.demo(), sprite_memory=memory).handle(
        "Draw a square.", 1
    )

    system, user = provider.calls[0]
    # The demo Sprite1 has no AI-owned body and Ghost does not exist, so the
    # turn starts exactly like the per-turn bridge.
    assert "# Loaded sprite detail" not in system
    assert "now included in the system prompt" not in user


def test_bridge_shares_one_memory_across_requests():
    bridge = Bridge(
        Agent(MockLLM([{"load_sprite": ["Sprite1"]}, draw_square_response()]),
              context_with_detail()),
        sprite_memory_enabled=True,
    )

    response = bridge.handle(
        [Sym("request"), 1, ["Make it bounce faster."], "Sprite1"]
    )[0]

    assert response[0] == Sym("result")
    assert bridge.sprite_memory is not None
    assert bridge.sprite_memory.snapshot() == ["Sprite1"]


def test_bridge_switch_off_disables_the_shared_memory():
    bridge = Bridge(
        Agent(MockLLM([{"load_sprite": ["Sprite1"]}, draw_square_response()]),
              context_with_detail()),
        sprite_memory_enabled=False,
    )

    bridge.handle([Sym("request"), 1, ["Make it bounce faster."], "Sprite1"])

    assert bridge.sprite_memory is not None
    assert bridge.sprite_memory.snapshot() == []
