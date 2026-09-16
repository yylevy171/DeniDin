# Feature Specification: Long-Term Memory Assembly — chronological daily-summary inclusion + deterministic date-anchored lookup, replacing the embedding-similarity dependency

**Feature Branch**: `feature/077-long-term-memory-assembly` (not yet created)
**Created**: 2026-09-05
**Status**: DRAFT — needs full `speckit.specify` → `speckit.clarify` → `speckit.plan` → `speckit.tasks` pipeline. This file is the initial problem statement only.
**Number note**: The user asked for "73"; `073-optimize-runtime-constitution` was already taken, so this was filed as 077 (next clean number). Rename if desired.
**Input**: During Feature 070 (rolling 14-day memory window) Stage 2 dev-migration dogfooding, the
long-term-recall half of the memory system was shown to not reliably surface the correct
`daily_summary` for a real question. This feature redesigns how long-term memory is *assembled
into a turn*, so that answering "what happened / what did we discuss / who did I ask about on/around
day X" does not depend on an embedding-similarity search ranking the right record highly.

---

## Why this is a separate feature (and not a Feature 070 fix or a bugfix)

- **Not a Feature 070 regression.** The pre-070 system stored `session_summary` records and
  recalled them through the *exact same* code path — `MemoryManager.recall()` / embedding
  similarity / `top_k` / `min_similarity`. Feature 070 changed *what* is stored (one clean
  `daily_summary` per Israel-local calendar day instead of one-or-more `session_summary` per
  session) — strictly better-structured — but did **not** touch retrieval. This weakness predates
  070; 070's dogfooding is simply the first time it was stress-tested with real "what happened on
  day X" questions against a realistically-sized history.
- **Not a bugfix.** The fix is a design change to how long-term memory is selected and assembled
  into the model's context, not a minimal correction to existing behavior. It updates the memory
  architecture that Feature 070 establishes and depends on (`daily_summary` as the long-term unit).
- **Feature 070 proceeds without waiting for this.** Per user direction 2026-09-05: "continue with
  70 assuming the current memory fetching is limited." Feature 070's migration (dev done, prod
  pending) ships with the current embedding-similarity recall as a known, documented limitation;
  this feature improves it afterward. 070's data model (regular one-per-day summaries) is exactly
  what makes this feature tractable.

## The evidence (Feature 070 Stage 2 dev, 2026-09-05)

Real godfather 1:1 WhatsApp turn in dev:

- Question: **"על מי שאלתי אותך שאלה פה בשיחה ב-15 באוגוסט?"** ("who did I ask you about, here in
  the conversation, on Aug 15?")
- The correct answer lives verbatim in that day's `daily_summary`: *"המשתמש ביקש לבדוק חשבונית
  עבור **יוסי יהושע**"*.
- Recall fired (`Added 10 recalled memories to system prompt`), `min_similarity=0.15`, `top_k=10`.
- The Aug-15 `daily_summary` scored **cosine similarity 0.2845 — rank 21 of 22** records in the
  collection (all 22 are `daily_summary`; the collection had no legacy noise). It did not make the
  top 10 and was never shown to the model.
- The 10 records the model *did* get were legitimate `daily_summary` records for **other** days
  (Aug 8 at 0.44, Aug 27 at 0.37, …) — they scored higher purely on surface/register similarity,
  not because they answered the question.
- Model answered "no record of an Aug-15 question exists" — a confident false negative.

A second turn — **"באיזה יום בדקנו את הפונקציונליות של הכפתורים?"** ("on which day did we test the
buttons feature?"), no explicit date — failed the same way ("no record").

Root observation: **an embedding of "who did I ask about on Aug 15" is not semantically close to
an embedding of a dense factual summary of that day's invoice activity**, even though the latter
is the literal correct answer. Similarity search is the wrong retrieval primitive for
date-scoped and topic-scoped conversational recall at this data shape.

## Proposed direction (to be refined by `speckit.clarify` / `speckit.plan`)

At the data volumes Feature 070 produces, retrieval-by-similarity is the wrong frame:

1. **Chronological wholesale inclusion.** One `daily_summary` ≈ 200–300 tokens. ~60 days ≈ 15k
   tokens; ~1 year ≈ 90k. A godfather turn already carries a 100k budget. For most realistic
   horizons, do not *retrieve* the right day — **include the daily summaries in date order for
   whatever window the question implies**, and let the model read them. Similarity search only
   re-enters at multi-year scale, and even then as "narrow the window", not "pick the one record".
2. **Deterministic date-anchored lookup.** When the question names or implies a date or date range
   (absolute — "15 באוגוסט"; relative — "אתמול", "לפני שבועיים"; or bounded — "בשבוע שעבר"), pull
   those days' summaries directly by the `date` metadata field. No embedding involved. The model is
   already reliable at resolving Hebrew/relative dates to ISO (proven by reminders / ledger-event
   capture) — same pattern: model resolves the date, code does an exact lookup.
3. **Keep the rolling 14-day verbatim window unchanged.** This feature only touches what is
   assembled for history *older* than the live window. The Feature 070 window / nightly roll /
   archive / migration pipeline are all out of scope.
4. **Embedding-similarity recall becomes a fallback, not the primary path** — retained only for
   genuinely unbounded topical queries with no date and no tractable window, and possibly with
   improved embedded text (date stated in prose, a recap of what was asked) as a secondary
   improvement.

## Open questions for `speckit.clarify`

- How does the code decide "the window the question implies" when the question has no explicit
  date? (model-supplied hint? always-last-N-days default? a lightweight model pre-pass?)
- Token-budget interaction: chronological inclusion must respect the acting role's `max_tokens`
  and the existing rolling-window + constitution + recalled-context ordering (prompt-cache
  prefix preservation — see `ai_handler.py` instructions assembly).
- Is wholesale inclusion done for every turn, or only turns the model/classifier flags as
  history-recall questions? (cost, latency, prompt-cache implications)
- Interaction with RBAC scope filtering (`recall_with_rbac_filter`) — the same scope/user-phone
  filters must still apply to wholesale-included summaries.
- Multi-year horizon: what's the actual cutover point to a "narrow the window" search, and how
  is that search done better than today's?
- Does this subsume or coordinate with `bugfix-051` (memory questions misrouted to
  `query_ledger_events`) — a clearer "history recall" path may reduce that misrouting.

## Out of scope

- The Feature 070 rolling window, nightly roll, archive mechanism, and migration pipeline.
- `query_ledger_events` / the financial ledger (separate tool family; `bugfix-051` tracks its own
  issue).
- Any change to how `daily_summary` records are *written* (Feature 070 owns that).

## Compliance

This spec MUST, when taken through the full pipeline, comply with CONSTITUTION.md (§I–III, §V —
no env vars, Israel local time, `pathlib.Path`, no monkey-patching, ZERO internal mocking, no
unverified third-party assumptions, tests immutable once approved) and METHODOLOGY.md (spec-first;
mandatory `user-stories.md` with Given-When-Then; Terminology Glossary; Technology Choices;
`REQ-MEM-*` requirement IDs continuing Feature 070's series or a new `REQ-LTM-*` series; "TDD" =
the `billed` acceptance tests described in plain language, code written and run once at the end).
