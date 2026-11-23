# Conversation history for the bridge ("chat history + rolling summary")

**Status:** plan, not started. Written 2026-11-23 after the revision-fidelity
fix, against the 645-test tree, from the audited live sessions of that day.
**Idea:** give the model its own conversation as context — recent turns
verbatim, older turns as deterministic one-line summaries — so referential
requests ("make it *smaller*", "start *lower*") resolve against what was
actually said and done, and the chat cannot narrate the status quo as a new
change because the model remembers claiming it.
**Target files:** bridge-side only (`harness/history.py`, `prompts.py`,
`server.py`, `config.py`, tests, `tools/ladder.py` in phase B). **Zero
Squeak work, zero wire-protocol changes, zero image changes.**

---

## 1. Problem

Every bridge request is stateless: the image sends
`#(request id prompt target context)`, and the agent sees only this turn's
prompt plus the current project snapshot. Two audited live sessions
(2026-11-23) show what that costs; both are in `scratch\base\audit` /
`scratch\base\bridge.log` for re-reading:

| Symptom | Evidence |
|---|---|
| Referential language cannot resolve | "make everything smaller, and the gaps between the platforms larger" — the model cannot see that it set the gaps one turn ago, so "larger" is interpreted in the absolute and the platform count gets cut 8→6 to manufacture room |
| The model re-applies identical scripts and narrates them as new changes | req19033863: three `replace_script` bodies byte-identical to the current ones, chat summary says "Platforms start lower" — while `spawn` still starts at y=-160 exactly as in the two previous turns. The no-op guard (separate change, landing alongside this plan) catches the mechanical half; it cannot give the model the *intent* context that would have prevented the no-op in the first place |
| The model cannot remember its own prior claims | turn 3's notes describe existing behavior confidently ("the scroll script still responds to the scroll broadcast") — true, but the model had no way to *know* it was true; a model that remembers its last turn knows what it already told the user |
| Revision prompts drift into re-litigating the design | without the conversation, every revision turn re-derives what the project is from the context snapshot alone; with it, "make the platforms start lower" becomes a tweak to a known, remembered scene |

HANDOFF known-gaps already lists this ("chat history in requests"). The
sessions above turned it from a nice-to-have into the measured next blocker:
mechanical revision fidelity is fixed (load-first + echo, see HANDOFF 1a),
so the remaining quality losses on multi-turn flows are memory losses.

---

## 2. Design in one paragraph

The bridge keeps a bounded, process-local conversation store. Each
**acked** turn (the `#applied` acknowledgement path — applied work only)
appends a record: the user's words, the model's applied summary, its notes,
and a compact bridge-built outline of the applied changes (factual, from
`compiled.chat_summary()` lines — never the raw change set). When building
the next user prompt, a **"Conversation so far"** section is inserted
between the request and the project context: the last few turns rendered
near-verbatim, older turns as one line each. Trimming has its own budget
stages that run before the existing context-detail ladder, so history never
starves the targeting surface. One caveat line in the section header states
that the project context below is authoritative (undo and manual edits are
image-side; history is memory, not state).

---

## 3. The store — `bridge/src/harness/history.py`

```python
@dataclass(frozen=True)
class TurnRecord:
    request: str      # the user's words, capped (e.g. 400 chars)
    summary: str     # compiled.summary (the model's own line, capped)
    notes: str       # change-set notes, capped
    outline: tuple[str, ...]  # 1-3 factual lines from chat_summary()
    at: str          # ISO timestamp

class ConversationHistory:
    """Bounded, process-local. Thread-safe under the bridge state lock."""
    recent: list[TurnRecord]   # newest last; cap ~24 records
```

- **Ack-gated recording:** `server.py` `_handle_request` puts the result in
  `pending[request_id]`; the image acks with `#applied`, which calls
  `_take_pending`. Append to history inside `_take_pending` (under the
  existing `_state_lock`), from the `AgentResult` + the original prompt
  string (both are in scope there). Failed turns never reach `#applied`, so
  they do not enter history — deliberate for v1: failures are visible in the
  image's chat log already, and their absence keeps the section about
  *applied reality*.
- **Where the instance lives:** beside the shared template state on the
  `Bridge` (same lifetime as the process, like the accumulating registry
  the legacy/demo path uses). One bridge serves one image session, and the
  wire carries no session id — process-local is the honest v1 scope. See
  open decision 3 for resets.
- **Switch:** `resolve_history()` in `config.py`, mirroring
  `resolve_generator()` — `HARNESS_HISTORY` env > `harness.ini`
  `[harness] history` > default `on`. With history off, prompts are
  byte-identical to today (snapshot-test this like `test_budget.py` does).

## 4. Prompt rendering — `prompts.py`

Inserted section (generator-neutral prose; both modes render it
identically):

```text
User request:
{request}

Conversation so far (older turns compressed; the project context below is
authoritative — undo and manual edits are not reflected here):
<older one-liners, oldest first, up to ~8>
  "make everything smaller..." -> Shrank the player and platforms... (2 sprites, 4 scripts)
Most recent turns:
You: make the platforms start lower, and they should only move together...
Assistant: Platforms start lower and scroll down together...
  - Updated script 'spawn' (5 blocks, id ai-3)
  - Updated script 'play' (2 blocks, id ai-2)
  notes: ...

Project context:
...
```

Budget ladder — history gets its own stages **before** the existing
context levels in `build_user_prompt_with_meta`:

- **H1:** render only the last 2 turns verbatim, compress the rest to one-liners.
- **H2:** drop one-liners oldest-first until the section fits.
- Then the existing levels 1→3 and `_hard_user_fit` run unchanged.

`_user_meta` gains `history_turns`, `history_chars`, `history_dropped` so
the audit (`prompts/assembly.json`) records what the model actually saw.
Typical size: ≤ ~1200 chars; hard cap ~2400.

## 5. Phases

### Phase A — store, rendering, recording behind the switch (2–3 dev days)

- `harness/history.py` (store + rendering helpers, stdlib only).
- `config.py` `resolve_history()`; `prompts.py` section + trimming stages +
  meta; `server.py` recording in `_take_pending`.
- Tests (`bridge/tests/test_history.py`): record shape and caps; ack-gated
  append (drive `_handle_request` twice like the server tests do, assert
  the second prompt contains the first turn); trimming stages H1/H2;
  history-off byte-identity; mode-neutrality (json/dsl render the same
  section); lock safety under concurrent sends.

### Phase B — measurement (1 dev day)

- `tools/ladder.py`: maintain the same history across a scenario's steps
  (the runner drives `Agent` directly, so it records at the same success
  point the server would). Add a third step to `square_chain` or
  `platformer_chain` with deliberately referential wording ("now make it
  *smaller* again", "start them *lower*") so the ladder measures reference
  resolution, not just first-turn quality.
- Extend `docs/LADDER_RUBRIC.md`'s revision items: the referential step
  must produce either a real delta or an honest acknowledgment — never an
  identical re-apply narrated as a change.
- A/B history on/off on the same ladder scenarios; record in the rubric
  results log.

### Phase C — optional, only with evidence (later)

An LLM-maintained rolling summary replacing the deterministic one-liners
when the store exceeds the verbatim window — better intent retention over
long sessions at +1 cheap model call per N turns. Do not build it until
phase B shows deterministic compression actually losing intent (the
success criteria below define "losing").

**Success criteria for A+B:** replay the 2026-11-23 doodle-jump flow
(build → "make everything smaller" → "start lower"): "smaller"/"lower"
resolve against remembered values (the change either happens for real or
the model says it is already so); the chat never claims an identical
re-apply as a change; ladder referential steps show history-on ≥ history-off
applied-rate with fewer misinterpretations; history section stays under
budget on every measured turn.

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| Prompt growth eats context room | Own trimming stages before the context ladder; hard caps; audit meta records drops |
| History lies after undo / manual edits (both happen image-side) | Caveat line in the section header; the per-turn project context stays authoritative; reconcile-on-undo is a later, wire-side idea |
| Topic switch mid-session (project open/new) leaves stale history | v1: caveat line; open decision 3 |
| Store grows unbounded | Cap records (~24); oldest silently pruned from the store, not just the render |
| Privacy | History is prompt content; the audit already records prompts under the same local-only rules (SECURITY.md) |

---

## 7. Open decisions

1. **Verbatim window size** — proposed 4 turns; adjust from phase-B token
   measurements.
2. **Do failed turns appear as one-liners?** ("attempted X, failed: <code>")
   Proposed v1: no (see ack-gated recording). Revisit if the model repeats
   a known-bad approach across turns.
3. **When does history reset?** A `project open`/`new` wire event could
   clear the store — the control server already sends project lifecycle
   messages to the bridge? (It does not today; this would be the first
   wire addition and is NOT required for v1.) Until then: process-lifetime
   history with the caveat line.
4. **Per-target sprite summaries in history outlines** — the factual lines
   already name targets; nothing extra needed unless phase B shows the
   model asking for the same sprite repeatedly.

---

## 8. How to start

1. Read `PY_DSL_SCOPE.md` sections 1 and 8 for the format this plan follows
   and the switch/measure conventions already proven on this branch.
2. Read `bridge/src/harness/server.py` `_handle_request` and
   `_take_pending`, and `bridge/src/harness/prompts.py`
   `build_user_prompt_with_meta` + `_hard_user_fit` — those are the three
   functions this plan touches; everything else is additive.
3. Implement Phase A behind the switch, suite green (expect ~15 new tests),
   then Phase B's ladder step and one live replay of the doodle-jump flow
   with `-Audit full` before trusting it.
