"""Concurrency isolation for :class:`harness.server.Bridge`.

Every ``#request`` carries its own full project snapshot, so the bridge must
build a fresh ``Agent`` per request.  These tests overlap real turns from
worker threads (the same way ``asyncio.to_thread`` does) and prove that the
request contexts/registries never leak into each other or into the template.
"""

from __future__ import annotations

import threading
import time

from harness.agent import Agent
from harness.context import ProjectContext
from harness.llm import MockLLM, draw_square_response
from harness.protocol import Sym, make_message
from harness.providers.base import ProviderError
from harness.server import Bridge
from harness.validator import ValidationError, ValidationIssue


# --- fixtures --------------------------------------------------------------


def _script(script_id: str, label: str, hat: str, block_count: int, hash_: str) -> list:
    return [script_id, label, hat, block_count, hash_, True, False]


def _context_literal(
    target: str,
    sprite: str,
    *,
    stage_variables: list[str],
    sprite_variables: list[str],
    scripts: list[tuple[str, str, str, int, str]],
) -> list:
    """Build the image's ``#(target #(sprites...))`` wire context."""
    return [
        target,
        [
            ["Stage", True, list(stage_variables), [], ["backdrop"], [], []],
            [
                sprite,
                False,
                list(sprite_variables),
                [],
                ["costume1"],
                ["pop"],
                [_script(*entry) for entry in scripts],
            ],
        ],
    ]


def _run_concurrently(calls: list[tuple[str, object]]) -> dict[str, object]:
    """Run named callables in threads and return their results."""
    results: dict[str, object] = {}
    errors: dict[str, BaseException] = {}

    def worker(name: str, fn) -> None:
        try:
            results[name] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised below as a test failure
            errors[name] = exc

    threads = [threading.Thread(target=worker, args=(name, fn)) for name, fn in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert not any(thread.is_alive() for thread in threads), "worker thread did not finish"
    assert not errors, errors
    return results


class _ContextProvider:
    """Answer for whichever request context is in the prompt.

    The barrier holds both turns inside the provider at the same time, so a
    passing test cannot be explained by lucky serialization.
    """

    name = "scripted"

    def __init__(self, expected: int = 2, delay: float = 0.05):
        self.barrier = threading.Barrier(expected, timeout=10)
        self.delay = delay
        self.calls: list[str] = []

    def complete_json(self, system: str, user: str) -> dict:
        self.calls.append(user)
        target = next(t for t in ("CatA", "DogB") if f"Target: {t}" in user)
        self.barrier.wait()
        time.sleep(self.delay)
        suffix = "a" if target == "CatA" else "b"
        return {
            "summary": f"Added the {suffix} script for {target}.",
            "changes": [
                {
                    "action": "add_script",
                    "target": target,
                    "label": f"add_{suffix}",
                    "hat": {"op": "when_flag_clicked"},
                    "body": [{"op": "pen_down"}],
                }
            ],
        }


class _RaisingProvider:
    """Raise a chosen exception from inside the agent turn."""

    name = "raising"

    def __init__(self, exc: BaseException):
        self.exc = exc

    def complete_json(self, system: str, user: str) -> dict:
        raise self.exc


class _ConcurrencyProbe:
    """Record how many provider calls are in flight at once."""

    name = "probe"

    def __init__(self, barrier: threading.Barrier | None = None, delay: float = 0.0):
        self.barrier = barrier
        self.delay = delay
        self._lock = threading.Lock()
        self.active = 0
        self.peak = 0
        self.calls = 0

    def complete_json(self, system: str, user: str) -> dict:
        with self._lock:
            self.active += 1
            self.calls += 1
            self.peak = max(self.peak, self.active)
        try:
            if self.barrier is not None:
                self.barrier.wait()
            if self.delay:
                time.sleep(self.delay)
            return draw_square_response()
        finally:
            with self._lock:
                self.active -= 1


# --- overlapping requests --------------------------------------------------


def test_overlapping_requests_with_distinct_contexts_are_isolated():
    ctx_a = _context_literal(
        "CatA",
        "CatA",
        stage_variables=["scoreA"],
        sprite_variables=["speedA"],
        scripts=[("ai-1", "script_a", "EventHatMorph", 3, "hash-a")],
    )
    ctx_b = _context_literal(
        "DogB",
        "DogB",
        stage_variables=["scoreB"],
        sprite_variables=["speedB"],
        scripts=[("ai-7", "script_b", "EventHatMorph", 4, "hash-b")],
    )
    demo = ProjectContext.demo()
    bridge = Bridge(Agent(_ContextProvider(), demo))

    results = _run_concurrently(
        [
            ("a", lambda: bridge.handle([Sym("request"), 101, ["Add a script."], "CatA", ctx_a])),
            ("b", lambda: bridge.handle([Sym("request"), 102, ["Add a script."], "DogB", ctx_b])),
        ]
    )

    result_a = results["a"][0]
    result_b = results["b"][0]

    # Each reply belongs to its own request and its own snapshot.
    assert result_a[0] == Sym("result")
    assert result_a[1] == 101
    assert "CatA" in result_a[2][0]
    assert all("DogB" not in line for line in result_a[2])
    apply_a = result_a[3]
    assert apply_a[0] == Sym("apply")
    assert apply_a[1] == 101
    assert apply_a[2][0][1] == "ai-2"  # CatA's registry already contains ai-1
    assert apply_a[2][0][2] == "CatA"

    assert result_b[0] == Sym("result")
    assert result_b[1] == 102
    assert "DogB" in result_b[2][0]
    assert all("CatA" not in line for line in result_b[2])
    apply_b = result_b[3]
    assert apply_b[0] == Sym("apply")
    assert apply_b[1] == 102
    assert apply_b[2][0][1] == "ai-1"  # DogB's registry only contains ai-7
    assert apply_b[2][0][2] == "DogB"

    # The acknowledgement state also holds the right turn for each id.
    assert bridge.pending[101][0].request_id == 101
    assert bridge.pending[101][0].compiled.changes[0].target == "CatA"
    assert bridge.pending[102][0].request_id == 102
    assert bridge.pending[102][0].compiled.changes[0].target == "DogB"

    # Nothing leaked into the template's original demo context.
    assert demo.target == "Sprite1"
    assert demo.stage_variables == []
    assert demo.registry() == {}
    assert set(demo.sprites) == {"Sprite1", "Stage"}
    assert demo.sprites["Sprite1"].variables == []
    assert not demo.sprites["Sprite1"].scripts

    # The compatibility view is a private snapshot, never a live request object.
    assert bridge.agent.context is not demo
    assert bridge.agent.context.target in {"CatA", "DogB"}


def test_applied_for_request_a_cannot_change_request_b_snapshot():
    ctx_a = _context_literal(
        "CatA",
        "CatA",
        stage_variables=["scoreA"],
        sprite_variables=[],
        scripts=[("ai-1", "script_a", "EventHatMorph", 3, "hash-a")],
    )
    ctx_b = _context_literal(
        "DogB",
        "DogB",
        stage_variables=["scoreB"],
        sprite_variables=[],
        scripts=[("ai-7", "script_b", "EventHatMorph", 4, "hash-b")],
    )
    provider = MockLLM(
        [
            {
                "summary": "Added a script for CatA.",
                "changes": [
                    {
                        "action": "add_script",
                        "target": "CatA",
                        "label": "add_a",
                        "hat": {"op": "when_flag_clicked"},
                        "body": [{"op": "pen_down"}],
                    }
                ],
            },
            {
                "summary": "Updated the DogB script.",
                "changes": [
                    {
                        "action": "replace_script",
                        "script_id": "ai-7",
                        "target": "DogB",
                        "label": "script_b",
                        "hat": {"op": "when_flag_clicked"},
                        "body": [{"op": "pen_up"}],
                    }
                ],
            },
        ]
    )
    bridge = Bridge(Agent(provider, ProjectContext.demo()))

    first = bridge.handle([Sym("request"), 1, ["Add a script."], "CatA", ctx_a])[0]
    assert first[0] == Sym("result")
    assert bridge.handle([Sym("applied"), 1]) == [[Sym("ok"), 1]]
    # The template cache reflects A, for backwards compatibility only.
    assert "ai-2" in bridge.agent.registry

    # B still validates/compiles against B's own snapshot (ai-7 exists there,
    # and A's ai-2 does not).
    second = bridge.handle([Sym("request"), 2, ["Update my script."], "DogB", ctx_b])[0]
    assert second[0] == Sym("result")
    assert second[1] == 2
    apply_b = second[3]
    assert apply_b[2][0][0] == Sym("replace")
    assert apply_b[2][0][1] == "ai-7"
    assert apply_b[2][0][2] == "DogB"


# --- pending acknowledgement state / TTL -----------------------------------


def test_pending_ttl_sweeps_and_expired_applied_is_only_acknowledged():
    now = [100.0]
    bridge = Bridge(
        Agent(MockLLM([draw_square_response()]), ProjectContext.demo()),
        pending_ttl_s=10.0,
        clock=lambda: now[0],
    )

    response = bridge.handle([Sym("request"), 1, ["Draw a square."], "Sprite1"])[0]
    assert response[0] == Sym("result")
    entry = bridge.pending[1]
    assert isinstance(entry, tuple) and len(entry) == 2
    assert entry[1] == 100.0

    now[0] = 111.0  # 11 s old: older than the 10 s TTL
    assert bridge.handle([Sym("ping")]) == [[Sym("pong")]]  # any message sweeps
    assert 1 not in bridge.pending

    assert bridge.handle([Sym("applied"), 1]) == [[Sym("ok"), 1]]
    assert "ai-1" not in bridge.agent.registry
    assert bridge.handle([Sym("applied"), 999]) == [[Sym("ok"), 999]]


# --- concurrency limit -----------------------------------------------------


def _two_requests(bridge: Bridge) -> dict[str, object]:
    return _run_concurrently(
        [
            ("one", lambda: bridge.handle([Sym("request"), 1, ["Draw a square."], "Sprite1"])),
            ("two", lambda: bridge.handle([Sym("request"), 2, ["Draw a square."], "Sprite1"])),
        ]
    )


def test_max_concurrent_one_serializes_turns():
    probe = _ConcurrencyProbe(delay=0.15)
    bridge = Bridge(Agent(probe, ProjectContext.demo()), max_concurrent=1)

    results = _two_requests(bridge)

    assert probe.calls == 2
    assert probe.peak == 1
    assert all(result[0][0] == Sym("result") for result in results.values())


def test_max_concurrent_two_allows_overlap():
    probe = _ConcurrencyProbe(barrier=threading.Barrier(2, timeout=10), delay=0.05)
    bridge = Bridge(Agent(probe, ProjectContext.demo()), max_concurrent=2)

    results = _two_requests(bridge)

    assert probe.calls == 2
    assert probe.peak == 2
    assert all(result[0][0] == Sym("result") for result in results.values())


# --- request-scoped error replies ------------------------------------------


def test_validation_error_preserves_request_id():
    issue = ValidationIssue("changes[0]", "unknown block 'not_a_block'")
    bridge = Bridge(Agent(_RaisingProvider(ValidationError([issue])), ProjectContext.demo()))

    response = bridge.handle([Sym("request"), 77, ["Do something."], "Sprite1"])[0]

    assert response[0] == Sym("error")
    assert response[1] == 77
    assert "changes[0]: unknown block 'not_a_block'" in response[2]


def test_multi_issue_validation_reply_is_one_encodable_line():
    issues = [
        ValidationIssue("changes[0]", "unknown block 'not_a_block'"),
        ValidationIssue("changes[1]", "unknown target 'Ghost'"),
    ]
    bridge = Bridge(Agent(_RaisingProvider(ValidationError(issues)), ProjectContext.demo()))

    response = bridge.handle([Sym("request"), 79, ["Do something."], "Sprite1"])[0]

    assert response[0] == Sym("error")
    assert response[1] == 79
    assert "\n" not in response[2]
    assert "changes[0]" in response[2]
    assert "changes[1]" in response[2]
    # This is the exact call that used to raise for a multi-line error string.
    assert make_message(*response).startswith("#(")


def test_provider_error_preserves_request_id_without_secret_or_traceback():
    secret = "oc_sk_test_secret_value"
    provider = _RaisingProvider(
        ProviderError(
            "auth",
            "the endpoint rejected the API key",
            status=401,
            detail=f"Authorization: Bearer {secret}",
        )
    )
    bridge = Bridge(Agent(provider, ProjectContext.demo()))

    response = bridge.handle([Sym("request"), 78, ["Do something."], "Sprite1"])[0]

    assert response[0] == Sym("error")
    assert response[1] == 78
    assert "model error (auth, HTTP 401)" in response[2]
    assert secret not in response[2]
    assert "Traceback" not in response[2]


# --- unchanged basics ------------------------------------------------------


def test_normal_request_applied_round_trip_and_hello_ping():
    bridge = Bridge(Agent(MockLLM([draw_square_response()]), ProjectContext.demo()))

    assert bridge.handle([Sym("hello"), "token", "ScratchAI/1"]) == [[Sym("hello-ok"), "ScratchAI/1"]]
    assert bridge.handle([Sym("ping")]) == [[Sym("pong")]]

    result = bridge.handle([Sym("request"), 5, ["Draw a square."], "Sprite1"])[0]
    assert result[0] == Sym("result")
    assert result[1] == 5
    assert any("draw_square" in line for line in result[2])

    assert bridge.handle([Sym("applied"), 5]) == [[Sym("ok"), 5]]
    assert "ai-1" in bridge.agent.registry
    assert 5 not in bridge.pending
