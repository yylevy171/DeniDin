# Contract: Reaction judgment tuning harness

**Human decision (2026-09-12)**: this feature ships with NO fixed `billed`/`expensive` acceptance
scenarios asserting a specific expected emoji — emoji/reaction *choice* is a taste judgment, not
something a hard assertion should pin down. This harness replaces that acceptance-test layer for
the purpose of Phase -1's requirement (METHODOLOGY.md §VI.a/§IV) — instead of a fixed,
human-approved scenario list run once as a final acceptance pass, this feature uses a rotating,
repeatable capture-and-review loop that the AI agent runs and evaluates itself, iterating on the
constitution's wording until judgment is consistently sound across a broad, rotating sample.
Deterministic plumbing (tool wiring, dispatch, gating, message-id resolution, flip mechanics) is
still covered by ordinary hard-assertion unit/integration tests, unaffected by this decision.

## Scenario pool

`tests/billed/reaction_judgment_pool.py` / `tests/expensive/reaction_judgment_pool.py` — plain
data, not test functions: a list of representative conversational scenarios, each with enough
context (chat history, message content, role) to run through the real `AIHandler` pipeline. Not
exhaustive — designed for variety across user stories and edge cases, expanded over time as new
misses are found during tuning.

**Billed pool (~12 scenarios)**:
1. Action command → clean success (e.g. "צור חשבונית ל-2,000 ש״ח ל[לקוח אמיתי]")
2. Action command → blocked/ambiguous client
3. Action command → clarification needed mid-flow
4. `react_to_message` with no explicit target (model reacts to the current turn on its own)
5. `react_to_message` flipping an earlier message's reaction (multi-turn)
6. Ambient group chatter, variant A (two people planning lunch)
7. Ambient group chatter, variant B (a debate unrelated to DeniDin)
8. Trivial 1:1 acknowledgment, variant A ("ok thanks")
9. Trivial 1:1 acknowledgment, variant B (a lone emoji reply from the user)
10. Gratitude ("תודה רבה, עבודה מצוינת")
11. Holiday greeting (rotate across at least 2 different holidays across runs)
12. Light banter/joke turn (checks against over-reacting to humor)

**Expensive pool (~6-8 scenarios, real vision calls)**:
1. Clean fee-agreement upload → full resolution to ✅
2. Unreadable/garbled document → resolution to ❌/⚠️
3. Document requiring multi-turn clarification before resolving
4. Document workflow explicitly abandoned by the user mid-flow
5. Document uploaded inside a group chat (addressed to DeniDin)
6. A second document type (e.g. a receipt/photo, not a PDF) — avoids over-fitting the model's
   (and the tuning process's own) judgment to one document shape

## Capture mechanism — no hard assertions on emoji choice

Each scenario runs through the real pipeline (real `AIHandler`, real tool attachment, real
constitution text) with **`send_reaction()` stubbed at the Green API boundary only** — permitted
per CONSTITUTION §V (external services may be mocked in tests; only internal components may not).
The stub records, per call: which tool/path triggered it (fast-path hook vs. `react_to_message`),
the resolved `chat_id`/`id_message`, and the `reaction` emoji — appended to a structured JSON
judgment log (`logs/reaction_tuning/<timestamp>.json`), one entry per scenario, including scenarios
that produced **zero** reaction calls (a deliberate silence is a valid, loggable outcome, not a
gap).

The **only hard assertions** in these test files are on deterministic plumbing that doesn't depend
on taste:
- Ambient group scenarios (6, 7 above) assert **zero** `send_reaction` calls — REQ-084-005/SC-003
  remain a hard, zero-tolerance requirement, not a judgment call.
- The flip scenario (5) asserts the second call's `id_message` matches the first's — flip-not-stack
  targeting correctness is plumbing, not taste.
- Every other scenario asserts nothing about the emoji itself — only that the run completed, the
  turn produced a normal reply either way, and the judgment log entry was written.

## Rotation

`scripts/run_reaction_tuning.sh` (proposed, mirrors `scripts/run_sanity.sh`'s selection/state
pattern): each invocation selects a fresh subset (10-15 scenarios by default) from the combined
pool, preferring scenarios least-recently run (tracked in a small state file, e.g.
`logs/reaction_tuning/rotation_state.tsv`, same idea as `sanity_state.tsv`), so repeated tuning
rounds build broad coverage over time rather than re-exercising the same handful of examples.
`--billed-only` restricts a round to the billed pool (runs freely, no approval needed);
`--include-expensive N` adds up to N expensive scenarios to the round (each such round needs its
own fresh human go-ahead before running, batched as one approval covering that round's expensive
scenarios — not one approval per individual scenario, since they're all part of one tuning pass).

## The tuning loop (performed by the AI agent, not a human)

1. Run a round (billed-only for early iterations; include expensive once billed judgment looks
   stable, with explicit approval for that round).
2. Read the round's judgment log.
3. Evaluate each entry against the classics list and the `## Reaction Management` etiquette rules
   (`contracts/group-discretion-gating.md`) — flag misses: wrong register (e.g. ✅ when ⚠️ fit
   better), an obscure/non-classic emoji reached for without real occasion-specificity, a missed
   obvious flip, an unwanted reaction on a scenario that should have stayed silent, or a silence
   where a reaction was clearly warranted.
4. If misses are found, adjust the constitution's wording to address the specific pattern observed
   (not a speculative rewrite) and note the change + rationale in a short running log,
   `logs/reaction_tuning/tuning_log.md` (mirrors `TEST_RUN_LOG.md`'s pattern — one entry per round:
   date, scenarios run, misses found, wording change made).
5. Run another round with a different rotated subset. Repeat.

**Stopping point**: not a hard pass/fail threshold — a judgment call itself, made when a couple of
consecutive rounds across different rotated subsets (including at least one round with expensive/
document scenarios) show no real misses. Documented in `tuning_log.md`'s final entry rather than
asserted by any test.

## Testing

This contract's own "testing" is the loop itself — see above. The scenario pool files, the
capture-stub mechanism, and `scripts/run_reaction_tuning.sh`'s rotation/state logic are themselves
plain code and DO get ordinary unit tests (state file rotation picks least-recently-run correctly,
the stub correctly intercepts and records `send_reaction` calls, the judgment log is written in
the documented shape) — only the *content* of what the loop produces (which emoji, sensible or
not) is exempt from hard assertions, per the human decision recorded at the top of this contract.
