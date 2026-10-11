# User Stories: WhatsApp Export → Ledger Event "Player"

**Feature ID**: 043-production-data-setup-tooling
**Status**: Reviewed and confirmed with user, 2026-08-06 (all stories below
approved as written; superseded US3-US5 and the split US1/US2 removed per
that review — see history note at bottom)

---

## US1 — Replay a date range through the player (override, incremental, resumable)

**As** the operator, **I want** to point the player at a WhatsApp export zip
and a start/end date, and have it replay every qualifying message in that
range through DeniDin's real ledger-capture machinery exactly as if it had
just arrived live, **so that** production ledger data can be (re)built for
any range — the full history, a narrow gap, or picked up from where a
previous run left off — using one single mechanism.

- **Given** a WhatsApp export zip and a date range `[start, end]` where
  `start` defaults to (and may never be earlier than) `2025-09-01`, and
  `end` defaults to (and may never be later than) today
- **When** the player runs for that range
- **Then** every message in `[start, end]` is "played" through the same
  extraction/classification/persistence machinery live DeniDin uses,
  producing freshly (re)computed event file(s) for every qualifying message;
  every pre-existing event file that falls inside `[start, end]` but wasn't
  freshly regenerated this run is moved to the `to-delete` holding location
  (never hard-deleted); event files outside `[start, end]` are left
  completely untouched; and a run summary accounts for every processed
  message (captured / not-qualifying / flagged-for-review) with no
  unaccounted messages.
- **Note**: this single story covers what earlier drafts called "override
  mode," "incremental mode," and player controls like pause/resume/rewind —
  they're all just this same operation invoked with a different `[start,
  end]`. "Pause" = stop and note the last date processed; "resume"/"rewind"
  = re-invoke with a new `start`. No separate mechanism needed.
- **Explicitly not re-tested here**: the correctness of DeniDin's own
  text/image ledger-extraction and classification (agreements in text,
  agreements in images, bank deposits in images) — that's already covered
  by the app's existing test suite, and the player calls that same code
  unmodified. This story tests the player's own responsibilities: message
  ordering, date-range scoping, reconciliation, and orphan handling.

## US2 — Correction/cancellation linked to a prior captured event (player-only for now)

**As** the operator, **I want** a later correction message ("תוקן ל-6,000")
to be linked to the specific prior agreement it corrects, using the ledger
built up so far rather than live conversational memory, **so that** the
replayed ledger reflects the same "current state" resolution live capture
would produce, without needing a full session replay.

- **Given** a prior played message already produced a `הסכם` event for
  client X at 5,000 ₪, and a later message from the same conversation says
  "לתקן ל-6,000" naming client X (or close context implying X)
- **When** the player processes the correction message
- **Then** step 1 classifies/extracts the message standalone (no
  conversation history attached to the AI call), step 2 finds the earlier X
  event among events accumulated so far in this run (or already on disk,
  for a narrower replay range), and step 3 populates `replaces_hint` (and
  any deterministic linking field decided in plan.md) before persisting the
  new `יצירה` event describing the arrangement's updated state — the prior
  event is never edited in place.
- **Note**: this relevancy-resolution logic is expected to eventually move
  into DeniDin's *live* capture path too (tracked separately, Feature 040's
  territory — agreement cancellation/modification) — but for Feature 043 it
  lives only in the player. Not a redesign of live capture.

## US3 — Ambiguous capture flagged to a review queue, then resolved

**As** the operator, **I want** a message the live rules would normally ask
a human about to be captured-but-flagged instead of guessed or silently
skipped, and to be able to answer those flags afterward in a second pass,
**so that** replaying doesn't stall but nothing ambiguous is silently
resolved wrong.

- **Given** a played message with a genuinely ambiguous material fact (e.g.
  unclear whether a named person is the client or an intermediary payer)
- **When** the player processes that message during the main run
- **Then** it captures the event with the ambiguity noted (never guessed)
  and adds an entry to a review-queue artifact describing the open question
- **And when** the operator later answers that queue entry and re-invokes
  the player's second-pass mode
- **Then** the corresponding event is updated to reflect the answer without
  re-deriving unrelated events in the range.

## US4 — Deterministic accounting: no orphaned or unaccounted events

**As** the operator, **I want** a guarantee that every ledger event file in
the played range corresponds to something the current run actually
produced, and every qualifying message in range produced its expected
event(s), **so that** I can trust the ledger has no silently-missing or
silently-stale data.

- **Given** a completed player run for a date range
- **When** reconciliation runs at the end
- **Then** the player reports: (a) every message in range and its outcome
  (captured/not-qualifying/flagged), (b) every event file now present in
  range was produced by this run, and (c) any file that existed before the
  run but wasn't reproduced has been moved to the `to-delete` location and
  listed in the run's manifest — zero silently-unaccounted-for state either
  direction.

## US5 — Schema-versioned event records

**As** a future maintainer, **I want** every event record the player writes
to carry a schema-version marker, **so that** later re-migrations or
analyses can tell which rule-set generation produced a given record without
guessing from `captured_at` alone.

- **Given** a ledger-event rule/schema change lands after the player's first
  production run
- **When** the player is re-run in override mode
- **Then** newly-written event records carry the new schema-version value,
  making it possible to distinguish them from records written under the
  prior rule generation (still on disk until reconciled/moved by this same
  run).

## US6 — Permanent, git-tracked tooling

**As** the project, **I want** this player to live under version control
alongside the rest of `apps/denidin-app` (not as an ad-hoc one-off script),
**so that** it can be maintained and re-run whenever ledger-event
definitions evolve.

- **Given** the Ledger Event Recognition rules change again in the future
- **When** a maintainer needs to re-derive production ledger data from the
  same (or a newer) WhatsApp export
- **Then** the same player (updated as needed for the new rules, since it
  reuses live's extraction/classification machinery rather than
  reimplementing it) is available in the repo, documented, and covered by
  tests — not recreated from scratch.

---

## Review history

Reviewed sequentially with the user, 2026-08-06. Changes made during review
(all applied above, not tracked as separate stray stories):

- Original US1 ("full override migration") and US2 ("incremental date-range
  repair") merged into one US1 — user pointed out they're the same
  operation with different date-range parameters, not two modes.
- "Player" adopted as the standing name for this tool/concept, replacing
  "migration script"/"import tool" language.
- Original US3-US5 (text agreement / image agreement / image bank-deposit
  capture correctness) dropped entirely — user noted these are already
  covered by DeniDin's existing test suite, since the player calls that
  same code unmodified rather than reimplementing it. The only aspect that
  genuinely differs for a replayed (non-live) message is **timestamp
  handling** — flagged as a required audit item in spec.md, not a user
  story (see spec.md's "Player timestamp audit" open question).
- Original US6 (correction linking) kept, with a note added that this logic
  is expected to move into live capture eventually (Feature 040) but stays
  player-only for now.
- Original US7-US10 renumbered to US3-US6, unchanged in substance.
