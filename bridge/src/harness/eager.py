"""Eager context: send on attempt 1 what the model would otherwise ask for.

The lazy protocol (``load_context`` / ``load_sprite``) costs a full model
round trip per load, and a model that skips the load and replaces a script
blind costs a *replace echo* round trip instead.  Measured live, a revision
spent 2-3 extra attempts that way.  The bridge already holds every AI-owned
script body and knows the pack index, so it can include both up front:

* **Sprite bodies** - every sprite with AI-owned, decompilable scripts is
  rendered in the generator's detail format, highest priority first (named in
  the request, named in the most recent history turns, the selected target),
  until :data:`EAGER_DETAIL_CHARS` is spent.  Sprites that do not fit stay in
  the lazy index, so nothing becomes unreachable.
* **Context packs** - a conservative keyword router maps the request (and the
  last remembered request, for referential follow-ups such as "add enemies to
  it") onto at most :data:`EAGER_MAX_PACKS` packs.

Everything here is deterministic and pure: no model call, no I/O beyond the
pack index the caller passes in.  ``eager_context = off`` restores the
lazy-only behaviour.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from .context import ProjectContext

#: Character budget for eagerly included sprite bodies.  The dialect renders
#: roughly 25-40 chars per block, so this covers ~300-450 blocks: a whole
#: typical project.  Larger projects keep their lowest-priority sprites lazy.
EAGER_DETAIL_CHARS = 14000

#: Packs are 4-8k chars in the dialect (pen-3d ~18k); two is the same cap the
#: lazy protocol enforces per load.
EAGER_MAX_PACKS = 2

#: Pack -> patterns.  Word-boundary regexes over the lower-cased request.  The
#: lists are deliberately narrow: a false positive costs a few thousand prompt
#: characters (cached after the first turn), a false negative only falls back
#: to the lazy protocol.
_PACK_PATTERNS: dict[str, tuple[str, ...]] = {
    "pen-3d": (
        r"3d",
        r"3-d",
        r"three[- ]dimension\w*",
        r"wire ?frames?",
        r"perspective",
        r"projection",
        r"cube",
        r"pyramid",
        r"mesh(es)?",
        r"polyhedr\w*",
        r"raycast\w*",
        r"ray ?tracing",
    ),
    "clones": (
        r"clones?",
        r"cloning",
        r"bullets?",
        r"projectiles?",
        r"lasers?",
        r"shoot\w*",
        r"particles?",
        r"spawn\w*",
        r"swarm",
        r"(rain|snow)(ing|fall)?",
        r"fireworks?",
        r"confetti",
        r"pipes?",
        r"asteroids?",
        r"enemies",
        r"crowds?",
        r"flocks?",
        r"herds?",
        r"schools? of",
        r"army",
        r"armies",
        r"waves? of",
        r"rows? of",
        r"grids? of",
        r"bricks",
        r"coins",
        r"snowflakes?",
        r"raindrops?",
        r"stars",
        r"meteors?",
        # "three crabs", "10 fish", "lots of trees": a crowd of one kind is
        # one template sprite plus clones.
        r"(?:three|four|five|six|seven|eight|nine|ten|twelve|twenty|"
        r"dozens?|hundreds?|[3-9]|[1-9]\d+)\s+(?:of\s+)?"
        r"(?!(?:steps?|seconds?|secs?|pixels?|px|degrees?|times?|percent|"
        r"points?|lives|levels?|frames?|blocks?|beats?|%)\b)"
        r"(?:[a-z]+\s+)?[a-z]+",
        r"(?:many|several|lots of|a lot of|a bunch of|loads of|a few|some)"
        r"\s+(?:\w+\s+)?\w+s",
    ),
    "scrolling": (
        r"scroll\w*",
        r"side[- ]?scroller",
        r"parallax",
        r"camera",
        r"tile ?maps?",
        r"long level",
        r"endless runner",
        r"runner game",
    ),
    "games": (
        r"games?",
        r"platformer",
        r"flappy",
        r"pong",
        r"breakout",
        r"snake",
        r"maze",
        r"dodge\w*",
        r"score",
        r"lives",
        r"health",
        r"game over",
        r"win(ning)?",
        r"lose",
        r"levels?",
        r"jump\w*",
        r"gravity",
        r"collect\w*",
        r"shooter",
        r"racing",
        r"clicker",
    ),
}

_COMPILED: dict[str, re.Pattern[str]] = {
    name: re.compile(r"\b(?:" + "|".join(patterns) + r")\b")
    for name, patterns in _PACK_PATTERNS.items()
}

#: When more than ``EAGER_MAX_PACKS`` match, the more specialised pack wins:
#: 3D and scrolling change the whole architecture, clones the spawn pattern,
#: and games is the broadest checklist.
_PACK_PRIORITY = ("pen-3d", "scrolling", "clones", "games")


def _pack_hits(text: str) -> dict[str, int]:
    lowered = (text or "").lower()
    hits: dict[str, int] = {}
    for name, pattern in _COMPILED.items():
        count = len(pattern.findall(lowered))
        if count:
            hits[name] = count
    return hits


def suggest_packs(
    request: str,
    available: Iterable[str],
    *,
    previous_request: str = "",
    limit: int = EAGER_MAX_PACKS,
) -> list[str]:
    """The packs a request's wording points at, most specialised first.

    ``previous_request`` is the most recent remembered user request.  It only
    contributes when the current request matched nothing itself, so a short
    follow-up ("make them faster") inherits the scene's packs while a new
    topic is routed on its own words.
    """
    names = {str(name) for name in available}
    hits = _pack_hits(request)
    if not hits and previous_request:
        hits = _pack_hits(previous_request)
    chosen = [name for name in _PACK_PRIORITY if name in hits and name in names]
    return chosen[: max(0, int(limit))]


def _mentions(text: str, name: str) -> bool:
    if not text or not name:
        return False
    return (
        re.search(r"(?<![\w-])" + re.escape(name.lower()) + r"(?![\w-])", text.lower())
        is not None
    )


def _editable(sprite: Any) -> bool:
    return any(script.owned and script.tuples for script in sprite.scripts)


def eager_sprites(
    context: ProjectContext,
    request: str,
    render: Callable[[str], str],
    *,
    recent_text: str = "",
    budget_chars: int | None = None,
) -> list[str]:
    """Sprite names whose exact bodies should ride attempt 1, in prompt order.

    ``render(name)`` returns the rendered detail for one sprite (the agent
    passes its mode-aware renderer).  Priority: sprites the request names,
    sprites the recent history names, the selected target, then the rest in
    project order.  A sprite that does not fit the remaining budget is
    skipped (a smaller, lower-priority one may still fit).
    """
    if budget_chars is None:
        budget_chars = EAGER_DETAIL_CHARS
    candidates = [
        name for name, sprite in context.sprites.items() if _editable(sprite)
    ]
    if not candidates:
        return []

    def rank(name: str) -> tuple[int, int]:
        order = candidates.index(name)
        if _mentions(request, name):
            return (0, order)
        if _mentions(recent_text, name):
            return (1, order)
        if name == context.target:
            return (2, order)
        return (3, order)

    chosen: list[str] = []
    used = 0
    for name in sorted(candidates, key=rank):
        try:
            size = len(render(name))
        except Exception:  # pragma: no cover - exotic live tuples
            continue
        if size <= 0 or used + size > budget_chars:
            continue
        chosen.append(name)
        used += size + 2
    return chosen
