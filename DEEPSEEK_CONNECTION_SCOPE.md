# DeepSeek connection — scope and architecture audit

**Status:** Phases 1–6 implemented (2026-11-12); live gate verified at bridge level  
**Date:** 2026-11-12  
**Scope:** the live model connection behind the Scratch AI harness, from the
current `DeepSeekLLM` adapter to a provider layer that is safe for long-running
headless use and easy to extend.

> Sections 2–4 record the pre-implementation audit and the plan. For what
> actually shipped, including the small deviations from this plan, see
> **§10 As-built (Phases 1–3)** and **§11 As-built (Phases 4–6)**.
>
> The original document stops at Phase 5. **Phase 6 was defined as the
> close-out gate**: opt-in live tests, a real bridge-level request, and two
> overlapping live sends, using the Phase 4 diagnostics — see §11.

---

## 1. Executive summary

The wire connection already exists and has been exercised live:

- `bridge/src/harness/llm.py` has `DeepSeekLLM`, an OpenAI-SDK client.
- `run_live.ps1` loads `bridge/.deepseek_key`, selects OpenCode Go
  (`https://opencode.ai/inference/go/openai/v1`) and model
  `deepseek-v4.1-flash`, then starts the bridge.
- The image can call it synchronously (`send`) or asynchronously
  (`send-async` + `poll`); the latter keeps `status` and `undo` responsive.
- A 3 s delayed mock proved the async path; the live path was verified in
  earlier sessions.

So the remaining work is **not "connect to DeepSeek"**. It is **productising the
connection**:

1. Make provider/model configuration explicit and testable instead of
   environment-only and partly wrong by default.
2. Bound latency and failures with retries, timeouts, and a real error taxonomy.
3. Make concurrent requests safe; the bridge currently shares one mutable
   `Agent`/context across threads.
4. Make the headless workflow diagnosable: request ids, usage, latency, redacted
   logs, a bridge health command, and clear launch failures.
5. Put a provider seam in place so a future local model, direct DeepSeek key, or
   another OpenAI-compatible endpoint is a config change, not a rewrite.

Recommended first slice: **Phases 1–3** (configuration/provider seam, request
lifecycle, concurrency isolation). That is roughly **3–4 focused days** and
removes the risks that get worse as soon as live sends overlap. Phases 4–6 are
another **2–3 days** and can follow incrementally.

---

## 2. Current-state audit

### 2.1 What works today

| Area | Current behaviour | File |
|---|---|---|
| Provider | OpenAI SDK against an OpenAI-compatible endpoint | `bridge/src/harness/llm.py:52` |
| Launcher | `.deepseek_key` → `DEEPSEEK_API_KEY`; OpenCode Go URL + `deepseek-v4.1-flash` | `run_live.ps1` |
| Model call | `chat.completions.create` with `response_format=json_object` | `llm.py:84` |
| JSON repair | Fenced-JSON stripping and brace extraction | `llm.py:116` |
| Agent loop | Up to 2 repairs, validates every reply against the context/registry | `agent.py:41` |
| Concurrency | `Bridge.handle` runs in `asyncio.to_thread` | `server.py:109` |
| Squeak async | Background worker + completion queue + poll | `image/26_async_send.st` |
| Tests | 51 passing; mock/delayed LLM coverage; no live-network test | `bridge/tests/` |
| Secret | `.deepseek_key` present (51 bytes), git-ignored | `bridge/.deepseek_key` |

### 2.2 Concrete gaps and risks

| # | Gap | Effect | Severity |
|---|---|---|---|
| 1 | `DeepSeekLLM` defaults to `https://api.deepseek.com` and model `deepseek-flash` | Running the module directly (`python -m harness.server --live`) can hit the wrong endpoint/model. Only `run_live.ps1` knows the OpenCode Go profile. | High |
| 2 | Configuration is environment-only | Hard to test, reproduce, or switch profiles; `run_live.ps1` is the de facto config. | High |
| 3 | No explicit retry/backoff or error taxonomy | 429/5xx/network errors become one `LLMError`; retry policy is whatever the OpenAI SDK does implicitly; 401/400 are indistinguishable from transient failures. | High |
| 4 | Timeout budget is inconsistent | OpenAI client timeout 120 s × up to 3 model calls = 360 s potential; Squeak async worker waits 300 s; sync `send` waits 330 s. A repair loop can exceed both. | High |
| 5 | Shared mutable `Agent` across concurrent live calls | `Bridge.handle` is threaded, but `agent.context`/`agent.registry` are shared. Two live sends can overwrite each other's context/registry. The two-send test used preloaded mock responses and did not exercise live context replacement. | High |
| 6 | `pending` grows without cleanup | If the image never sends `#applied` (crash, timeout, dropped send), `AgentResult` entries stay in `Bridge.pending` forever. | Medium |
| 7 | No request-scoped logs or usage | Logs show connection events, not request id/model/latency/tokens/attempts. Debugging a live failure means reading raw exceptions. | Medium |
| 8 | Error reply uses id 0 | A model/validation failure in `Bridge.handle` can produce `#error 0 ...`; the async worker stores the text but the id is not the request id. | Medium |
| 9 | Prompt size is unbounded | Catalog is ~7.3k chars; real context adds scripts/assets; future tuple bodies/history would push it further. No budget or truncation marker. | Medium |
| 10 | No cancellation | A dropped pending send marks the result, but the bridge thread and HTTP call continue. Async is non-blocking for the image, not for the bridge. | Medium |
| 11 | `run_live.ps1` fails with "address already in use" | An older bridge process blocks a relaunch; no reuse/clear diagnostic. | Medium |
| 12 | Secret hygiene is manual | `.deepseek_key` is git-ignored. An earlier key was exposed and has since been rotated and revoked; logs and errors must still redact `Authorization` and `oc_sk_`. | Medium |
| 13 | No provider seam | `DeepSeekLLM` is imported directly by `server.py`; adding a local model or a second endpoint means editing server code. | Medium |
| 14 | No live smoke test | Default tests never touch the network (good), but there is no opt-in check that the key/endpoint/model still work. | Low |
| 15 | `thinking` extra body is optimistic | `reasoning_effort` is sent to any endpoint when enabled; not all providers accept it. | Low |

### 2.3 Prompt-size baseline

For the demo context:

- system prompt: ~7,333 chars (catalog is the bulk)
- user prompt: ~182 chars
- total: ~7,515 chars ≈ 1,900 tokens before history/tuple bodies

That is comfortable today. It will not stay comfortable once tuple bodies,
chat history, or more sprites are included. Budgeting belongs in the design now,
even if enforcement is a later phase.

### 2.4 Secret audit

`oc_sk_`-prefixed text appears only in:

- `bridge/.deepseek_key` (the actual key, git-ignored)
- `HANDOFF.md` (prefix/rotation note, not the value)
- `run_live.ps1` (comment)

No key value was found outside the ignored key file. Keep it that way; never
put the key in the image or in `harness.ini`.

The key that was exposed during session 4 has been rotated and revoked
(2026-11-12); `bridge/.deepseek_key` now holds the replacement.

---

## 3. Target architecture

### 3.1 Layer diagram

```text
Scratch image (Morphic)
  AIHarness sendPrompt / startSendAsync
        │  #request id prompt target context
        ▼
Control/transport (127.0.0.1:8765, Smalltalk literal framing)
        │
        ▼
Bridge server (asyncio)
  Bridge.handle(message)
        │
        ├── parse context per request
        ├── build a per-request Agent (or take a lock)
        └── provider.complete_json(ModelRequest)
                 │
                 ▼
        Provider layer
          config/profile → OpenAICompatProvider → HTTP
          mock / replay / future local model
                 │
                 ▼
        Agent validation/repair loop
                 │
                 ▼
        #result / #error with request metadata
```

### 3.2 Provider seam

Keep the existing `LLMClient` shape (`complete_json(system, user)`) working for
compatibility, but introduce a richer interface:

```python
@dataclass(frozen=True)
class ModelConfig:
    profile: str
    base_url: str
    model: str
    api_key_env: str          # e.g. DEEPSEEK_API_KEY
    timeout_s: float = 90.0
    max_retries: int = 2
    temperature: float = 0.2
    max_tokens: int = 8192
    thinking: str = "off"
    session_id: str = "scratch-ai-harness"

@dataclass
class ModelRequest:
    request_id: int
    system: str
    user: str
    attempt: int = 1
    deadline: float | None = None

@dataclass
class ModelReply:
    data: dict[str, Any]
    model: str
    usage: dict[str, int] | None
    latency_ms: int
    attempts: int
    finish_reason: str | None
```

`ProviderError` carries a stable code:

```text
auth | rate_limit | timeout | network | server | bad_request | bad_json | cancelled
```

and whether it is retryable. The Squeak side only needs a readable `#error`
string; the bridge keeps the code in its log and optional metadata.

### 3.3 Configuration profiles

Add `bridge/harness.ini` (same key=value style as the image config; `#`
comments). It contains **no secret**, only the environment variable name:

```ini
[model]
default=opencode-go

[profile:opencode-go]
base_url=https://opencode.ai/inference/go/openai/v1
model=deepseek-v4.1-flash
api_key_env=DEEPSEEK_API_KEY
timeout=90
retries=2
thinking=off

[profile:deepseek-direct]
base_url=https://api.deepseek.com
model=deepseek-chat
api_key_env=DEEPSEEK_API_KEY
timeout=90
retries=2
thinking=off

[profile:local]
base_url=http://127.0.0.1:11434/v1
model=qwen2.5-coder
api_key_env=LOCAL_API_KEY
timeout=120
retries=0
```

Resolution order:

1. CLI (`--profile`, `--model`, `--base-url`, `--timeout`, `--retries`)
2. environment (`DEEPSEEK_*`) for compatibility
3. `bridge/harness.ini`
4. safe built-in defaults (explicitly the OpenCode Go profile, not the wrong
   `deepseek-flash` default)

The key itself stays in the environment or `.deepseek_key` read by the
launcher. The provider layer only sees the resolved string and must never log
it.

### 3.4 Request lifecycle and time budget

Define one budget, shared by all layers:

| Layer | Budget |
|---|---|
| Squeak async worker | 300 s hard wait |
| Bridge overall turn | 240 s |
| Per model attempt | 90 s |
| Repairs | max 2, but stop when the overall deadline would be exceeded |
| OpenAI client timeout | equal to per-attempt timeout |

On timeout/429/5xx: retry with jittered exponential backoff (for example
0.5 s, 1.5 s), honouring `Retry-After`. On 401/403/400/422: fail immediately
with a stable code. On malformed JSON: use the existing repair loop, not a
transport retry.

### 3.5 Concurrency and state

The image already sends the **full project context on every request**. That
makes the bridge's registry a cache, not a source of truth. The clean design is:

- `Bridge.handle` parses the context and constructs a **per-request Agent**
  (or a request-scoped context + shared provider).
- The provider client is thread-safe or has one client per request; the OpenAI
  client is safe to share for normal use, but document it.
- `pending` stores only the result needed for the `#applied` acknowledgement,
  with a TTL (for example 10 minutes) and a periodic sweep.
- Keep a global semaphore (for example 2 concurrent model calls) so a future
  multi-client setup cannot stampede the API. For the current single-user
  headless workflow, 1–2 is enough.

This is a smaller change than it sounds: `Agent.handle` is already stateless
apart from `context`/`registry`, and every request refreshes both.

### 3.6 Headless integration

| Need | Design |
|---|---|
| Launch | `run_live.ps1` checks port 8765; reuses a healthy bridge with `-Reuse`, otherwise fails with the owning PID and a clear message. |
| Health | `tools/ai_control.py bridge-status` calls the bridge `#ping` and prints profile/model/base URL, never the key. |
| Diagnosis | `doctor` on the image remains image-side; add a small host-side `tools/bridge_doctor.py` for model/endpoint/last-error checks. |
| Logs | `scratch/base/bridge.log`: request id, profile, model, attempt, latency, usage, outcome; redact prompts and keys. |
| Async | Keep `send --async` + `poll`; add `--timeout` to `poll` and a clear `pending`/`error` result. |
| Cancellation | Optional Phase 5: `#cancel <id>` from the image, bridge marks the request cancelled and closes the HTTP call if possible. |

No Squeak layout changes are needed for the provider work. The existing
`#send`, `#send-async`, `#poll`, and `#error` paths are sufficient.

---

## 4. Work packages

### Phase 1 — Provider seam and configuration (1–1.5 days)

**Deliverables**

- `bridge/src/harness/config.py`: config dataclasses + `harness.ini` loader.
- `bridge/src/harness/providers/`:
  - `base.py` — `ModelProvider`, `ModelRequest`, `ModelReply`, `ProviderError`
  - `openai_compat.py` — current `DeepSeekLLM` behavior behind the new interface
  - `mock.py` — `MockLLM`, `DelayedLLM` (move or re-export)
- `llm.py` becomes a compatibility shim so existing imports/tests keep working.
- `server.py`: `--profile`, `--config`, `--model`, `--base-url`, `--timeout`,
  `--retries`; `default_bridge` resolves a profile instead of constructing
  `DeepSeekLLM` directly.
- `run_live.ps1`: use `--profile opencode-go`; detect/reuse an existing 8765
  listener; print profile/model/base URL (no key).
- `bridge/harness.ini.example` with the three profiles above.

**Acceptance**

- `python -m harness.server --profile mock` works without a key.
- `--profile deepseek-direct` and `--profile opencode-go` resolve the correct
  base URL/model.
- Missing key produces one clear `auth` error, not a stack trace.
- All existing tests pass unchanged (via the `llm.py` shim).

### Phase 2 — Robust request lifecycle (1–2 days)

**Deliverables**

- `ModelRequest`/`ModelReply` metadata and latency/usage capture.
- `ProviderError` taxonomy + retry/backoff + `Retry-After`.
- Per-attempt timeout and overall deadline; repair loop respects the deadline.
- JSON parse errors map to `bad_json`; validation errors keep the existing
  repair prompt.
- Bridge `#error` preserves the request id and a safe message; full detail goes
  to the log.
- `pending` TTL cleanup.

**Acceptance**

- Fault-injection tests: 429, 500, 401, timeout, malformed JSON, fenced JSON,
  empty content.
- A simulated 3-call repair loop finishes within the overall budget or returns a
  clear timeout error.
- No retry on 401/400.
- Token usage and latency appear in the structured log.

### Phase 3 — Concurrency isolation (1–1.5 days)

**Deliverables**

- Per-request `Agent` (or request-scoped context/registry) in `Bridge.handle`.
- Concurrency limit/semaphore; document `pending` as ack-only state.
- Test: two overlapping requests with different contexts produce the right
  change sets and do not corrupt registry/context.
- Test: two sends in flight with the real image still pass.

**Acceptance**

- No shared mutable model state between requests.
- `#applied` for request A cannot affect request B's context.
- The existing two-send async test still passes.

### Phase 4 — Headless observability (1 day)

**Deliverables**

- Structured bridge log with redaction.
- `tools/ai_control.py bridge-status` (or `tools/bridge_doctor.py`).
- `run_live.ps1` reuse/fail diagnostics.
- Opt-in live smoke test (`pytest -m live`) that checks hello + one cheap model
  call.

**Acceptance**

- One command reports image control, bridge health, profile/model, and last
  error.
- Launching twice gives a clear message, not "address already in use".
- Logs contain request id/latency/usage but no key or prompt bodies.

### Phase 5 — Budgets, cancellation, future hooks (1–2 days, optional)

- Prompt/context budget and truncation markers; catalog filtering by target.
- `#cancel <id>` and cooperative cancellation.
- Chat history/session memory (only if it improves results; measure first).
- Replay fixtures and response caching for deterministic development.
- Local Ollama profile is already just a config profile; add a smoke test.

---

## 5. Architecture impact by module

| Module | Impact | Notes |
|---|---|---|
| `llm.py` | Split into `providers/`; keep a shim | Existing tests and examples keep importing `MockLLM`, `DeepSeekLLM`, `DelayedLLM`. |
| `server.py` | Provider factory + config CLI + request ids | `Bridge.handle` becomes request-scoped; `default_bridge` no longer env-only. |
| `agent.py` | Accept request metadata/deadline; per-request instance | Repair loop unchanged in behavior, bounded in time. |
| `prompts.py` | Optional budget/catalog filtering | Keep current prompt text; add a size check first. |
| `protocol.py` | Unchanged | `#error` already carries text; optional extra metadata can be added later without breaking the parser. |
| `context.py` | Unchanged | Already parses full context per request. |
| Squeak `26_async_send.st` | No change for Phases 1–3 | Optional `#cancel`/`#bridge-status` later. |
| `ai_control.py` | `bridge-status`, `poll --timeout` | No change to existing commands. |
| `run_live.ps1` | Profile/health/reuse | Keep the key file out of the image. |
| Tests | New provider/fault/concurrency tests | Default suite stays offline. |
| Docs | Config + troubleshooting | Update HANDOFF/README/ARCHITECTURE. |

### Backward compatibility

- Keep `DeepSeekLLM` importable from `harness.llm`.
- Keep `MockLLM`/`DelayedLLM` behavior identical.
- Keep the existing `run_bridge.ps1` mock path.
- Keep `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` working as
  environment overrides for one release.
- Do not change the image protocol; the Squeak side should not need a reload
  for the provider work.

---

## 6. Test plan

**Offline (default suite)**

- Config resolution: CLI > env > ini > defaults; missing key; unknown profile.
- Provider error mapping: 400/401/403/404/422/429/500/503, network error,
  timeout, invalid JSON, empty content, fenced JSON.
- Retry behavior: retryable vs terminal; backoff count; `Retry-After`.
- Deadline: repair loop stops at the budget.
- Redaction: key, Authorization header, prompt body not in logs.
- Concurrency: two overlapping contexts/requests; pending TTL.
- Compatibility: `MockLLM`/`DeepSeekLLM` imports; existing 51 tests.

**Opt-in live (`pytest -m live`)**

- `hello`/`ping` against a running bridge.
- One tiny prompt with a deliberately small `max_tokens`; assert a valid JSON
  object or a clean error.
- Skip when `DEEPSEEK_API_KEY` is absent; never print the key.

**Manual headless checks**

- `send --async` with a 3 s delayed mock; `status` responsive; poll; undo.
- `send` live from the image; verify `Applied…` and undo.
- Kill/relaunch; `bridge-status`; missing-key error; port-in-use message.

---

## 7. Decisions needed

1. **Default profile.** Keep **OpenCode Go** (`oc_sk_` key,
   `deepseek-v4.1-flash`) as the default, with `deepseek-direct` as an explicit
   profile? Recommended: yes, because that is the verified live path.
2. **Concurrency.** Per-request Agent (recommended) vs a single lock. Per-request
   is more future-proof; a lock is a one-line stopgap.
3. **Streaming.** Defer. The model emits a complete JSON change set; partial
   JSON is not useful to the block applier. Stream only optional progress text
   later if desired.
4. **Chat history.** Defer until the provider layer is stable and there is
   evidence it improves multi-turn results.
5. **Budget.** Proposed: 90 s/attempt, 240 s/turn, 2 attempts, 2 repairs max.
6. **Key location.** Keep `bridge/.deepseek_key` + environment; never in
   `harness.ini` or the image. (Rotation already done 2026-11-12.)

---

## 8. Recommended first slice

Do **Phase 1 + Phase 2 + Phase 3** in that order, in one branch:

1. `config.py` + `providers/` + `harness.ini.example` + server CLI.
2. Retry/timeout/error taxonomy + structured logs.
3. Per-request Agent + concurrency test.

Then stop and verify with the real image:

```powershell
.\run_live.ps1
python tools\ai_control.py send --async "make the hexagon bigger" --wait
python tools\ai_control.py undo
```

Only after that add `bridge-status`, live smoke tests, and the optional budget/
cancellation work. This order avoids baking the current shared-`Agent` race into
the async path and gives every later provider feature a stable seam.

---

## 9. Non-goals for this package

- A multi-agent system.
- Streaming token-by-token JSON into Scratch.
- Automatic model selection based on prompt content.
- A full chat history UI.
- Hosting the bridge beyond `127.0.0.1`.
- Putting API keys in the Scratch image or project files.

---

## 10. As-built (Phases 1–3)

Implemented 2026-11-12. Baseline was 51 offline tests; now **103 passing**.

**New modules**

| File | Purpose |
|---|---|
| `bridge/src/harness/config.py` | `ModelConfig`, ini/env/CLI resolution, safe `describe()` |
| `bridge/src/harness/providers/base.py` | `ProviderError` taxonomy, `ModelRequest`, `ModelReply`, JSON repair |
| `bridge/src/harness/providers/openai_compat.py` | OpenAI-compatible backend with retry/backoff/deadline |
| `bridge/src/harness/providers/mock.py` | `MockLLM`, `DelayedLLM`, `MockProvider` |
| `bridge/src/harness/providers/factory.py` | profile → provider |
| `bridge/harness.ini.example` | three profiles, no secrets |

**Changed**

- `llm.py` is a compatibility shim; `DeepSeekLLM`, `MockLLM`, `DelayedLLM`,
  `LLMError` and `parse_json_object` still import from it.
- `server.py`: `--profile/--config/--model/--base-url/--timeout/--retries`;
  `default_bridge` resolves a profile; per-request `Agent`; 2-way semaphore;
  `pending` TTL; `#error` preserves the request id; `turn_budget_s = 240`.
- `run_live.ps1`: `--profile opencode-go`, clear port-owner message, `-Reuse`.
- `agent.py`: `handle(..., *, deadline=None)`, rich `ModelRequest` calls,
  metadata on `AgentResult`, deadline stops the repair loop.

**Deviations / decisions taken**

1. The turn deadline is enforced in `Bridge` (`turn_budget_s`) and passed into
   `Agent.handle`, rather than in `protocol.py`. `protocol.py` is untouched.
2. The socket layer no longer answers `#error 0` for a request it cannot parse
   or handle; it recovers the id from the message when possible and returns a
   generic message for unexpected exceptions (detail stays in the log).
3. Context-less clients (the offline mock demos) keep an accumulating registry,
   because they have no snapshot to rebuild from. Snapshot-carrying requests —
   i.e. the real image — always get a fresh registry. This preserves
   `run_bridge.ps1`/`examples/` while fixing the live race.
4. Transport retries live in the provider; the OpenAI SDK's own retries are
   disabled (`max_retries=0`) so there is exactly one retry budget.
5. Structured logging at Phase 3 meant one INFO line per attempt/request on the
   standard logger. Phase 4 added the redacting file log (`obs.py`); see §11.
6. `ProviderError.attempts` records transport attempts and is logged; the wire
   message stays short.

**Verification**

- `cd bridge; $env:PYTHONPATH="src"; python -m pytest -q` → 103 tests at the
  Phase 3 checkpoint (162 offline + 2 opt-in live after Phases 4–5).
- `python -m harness.server --profile mock` + a raw socket client:
  hello → request → result → applied → ok → ping, twice in a row.
- `python -m harness.server --profile opencode-go` with no key → one
  `auth` line, exit 2, no traceback.
- Live re-verification from the image (`run_live.ps1`, `send --async ... --wait`,
  `undo`) is still the required manual gate before relying on it.

---

## 11. As-built (Phases 4–6)

Phase 6 is not in the original plan; it was defined here as the close-out gate.

**Phase 4 — headless observability**

| File | Purpose |
|---|---|
| `bridge/src/harness/obs.py` | `redact`, `RedactingFormatter`, `setup_logging`, `log_event`, `bridge_info` |
| `bridge/tests/test_observability.py` | 17 tests |
| `bridge/tests/test_live_smoke.py` | opt-in `@pytest.mark.live` |

- Default log `scratch/base/bridge.log`; `--log-file`, `--no-log-file`.
- Redaction covers `oc_sk_…`, `Authorization`/`Bearer`, `sk-…` and
  `api_key=…`, including tracebacks. Banned fields (`prompt`, `system`,
  `context`, `user`, `authorization`, `api_key`) cannot be emitted by
  `log_event`.
- `#(#info)` → `#(info 'ScratchAI/1' profile model base_url turn_budget
  max_concurrent pending last_error)`, built by `obs.bridge_info`.
- `python tools\ai_control.py bridge-status` reads that (plus `--json`).
- `run_live.ps1` gained `-LogFile` and prints the log path.

**Phase 5 — budgets, cancellation, future hooks**

- `prompts.py`: `build_system_prompt(target, *, budget_chars=None)`,
  `build_user_prompt(request, context, *, budget_chars=None)`,
  `prompt_budget_chars()` (`HARNESS_PROMPT_BUDGET`, default 24 000),
  `estimate_tokens()`. Context is trimmed before the catalog; script
  ids/labels/ownership always survive; explicit truncation markers.
- `agent.py`/`server.py`: `CancelToken`, `Bridge.cancel(id)`,
  `#(#cancel id)`; checks before each attempt, after the reply, and before each
  repair. Cancelled turns never publish a result or touch `pending`.
- `providers/replay.py`: `RecordingProvider`, `ReplayProvider`,
  `CachingProvider`; JSONL fixtures store a prompt hash + reply only.
  CLI: `--record`, `--replay`, `--cache`.
- `--prompt-budget` sets the budget for a run.

**Phase 6 — live gate (verified 2026-11-12)**

```text
pytest -q -m live                      -> 2 passed (1 tiny completion + 1 auth-path call)
bridge-status (opencode-go)            -> profile/model/base_url correct
one live request                       -> #result, change set valid, 3.0 s, 2603 tokens
two overlapping live requests          -> both #result, 3.4 s wall for ~3.1 s + ~3.4 s
log                                    -> request/attempt lines with latency+usage,
                                          no prompt text, no key, no Authorization
```

**Deviations / notes**

1. `#info` and `#cancel` are additive message types; `protocol.py` is unchanged
   and old clients are unaffected.
2. Cancellation is cooperative; HTTP calls in flight are not aborted. The Squeak
   async worker does not expose a Cancel button yet — the bridge API is complete
   and tested from Python.
3. `Bridge` gained `profile`/`model`/`base_url`/`last_error` fields defaulting to
   `""` so hand-built test bridges never invent values.
4. Live tests are marked and skipped without `DEEPSEEK_API_KEY`; the default
   suite stays fully offline (162 passed, 2 skipped).
5. Still image-side: the full gate through the Scratch UI
   (`send --async … --wait`, `undo`) and a docked pane (HANDOFF §7.3).
