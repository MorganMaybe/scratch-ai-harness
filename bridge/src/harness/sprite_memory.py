"""Bounded, process-local memory of sprites whose script detail was loaded.

Lazy sprite detail costs a full model round trip per load, and the load limit is
per turn.  A follow-up ("now make it smaller") therefore used to re-request the
same bodies from scratch.  This module remembers *names* only: the names whose
AI-owned script bodies a previous turn asked for and saw.

It deliberately stores no bodies.  Every prompt re-renders the detail from the
request's own :class:`~harness.context.ProjectContext`, so a remembered name can
never serve stale blocks; a sprite that lost its AI scripts is filtered out at
prompt-build time.  The store is bounded and stdlib-only so it can be imported
by the server without pulling in the agent or the provider stack.
"""

from __future__ import annotations

import threading
from typing import Iterable

#: Cap on remembered names.  Eight is far more sprites than one scene's active
#: editing surface, and prompt space is the only cost of an entry.
MAX_SPRITES = 8


class LoadedSpriteMemory:
    """Bounded, process-local ring of sprite names, oldest dropped first.

    Thread-safe on its own (the bridge also calls it under its state lock), so
    concurrent turns and their acknowledgements cannot interleave badly: one
    request remembering a load can never corrupt another request's snapshot.
    """

    def __init__(self, max_sprites: int = MAX_SPRITES):
        if max_sprites < 1:
            raise ValueError("max_sprites must be at least 1")
        self.max_sprites = int(max_sprites)
        #: Oldest first.  Public for tests and diagnostics; use ``snapshot`` for
        #: a stable copy to seed a turn from.
        self.sprites: list[str] = []
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self.sprites)

    def snapshot(self) -> list[str]:
        """A stable copy of the remembered names, oldest first."""
        with self._lock:
            return list(self.sprites)

    def clear(self) -> None:
        with self._lock:
            self.sprites.clear()

    def remember(self, names: Iterable[str]) -> list[str]:
        """Remember ``names`` as the newest entries, pruning the oldest at the cap.

        Matching is case-insensitive: a sprite is one sprite even if the model
        capitalises it differently.  Re-remembering an existing name moves it to
        the newest position and keeps the spelling the caller just supplied
        (the agent passes the canonical context name).  Blank names are ignored.
        """
        added: list[str] = []
        with self._lock:
            for raw in names:
                name = str(raw or "").strip()
                if not name:
                    continue
                key = name.casefold()
                self.sprites = [
                    existing
                    for existing in self.sprites
                    if existing.casefold() != key
                ]
                self.sprites.append(name)
                added.append(name)
            overflow = len(self.sprites) - self.max_sprites
            if overflow > 0:
                del self.sprites[:overflow]
        return added
