# Feature Specification: WhatsApp Export → Ledger Event "Player"

**Feature Branch**: `feature/043-production-data-setup-tooling`
**Feature ID**: 043-production-data-setup-tooling
**Priority**: TBD
**Created**: August 5, 2026
**Status**: In progress — Phases 1–4, 9, 11 (+ follow-up) implemented and
merged via PR #232 (2026-08-19). Phase 8 still open (checked against a real
33-message run and found unproven — see tasks.md/HANDOFF.md); Phases 5–7
deprioritized, not removed; Phase 10 removed entirely (bad premise given
confirmed model non-determinism). A follow-up PR #236 (2026-08-20) fixed stale
billed/expensive test assertions against Phase 11's real schema (found via a
full test-suite sweep, not a new phase) plus a real `max_retries` config-drop
gap in the player's own `_build_config_dict` (found during a master-merge
impact review). A further follow-up PR #237 (same day) fixed a real,
serious collision between the player's synthesized `idMessage` and a
second, concurrently-landed master change (`RecentNotificationDeduper`) that
would have silently swallowed most of a player run's dispatches — see
HANDOFF.md for detail. Feature not yet fully complete — stays in
`specs/in-progress/`, not moved to `specs/done/`.
**Input**: User request, 2026-08-05/06 (see Origin + Clarifications below)

---

**MANDATORY REQUIREMENT MET**: See `user-stories.md` (this directory) for
Given-When-Then user stories, per METHODOLOGY.md §I/§II. All 6 stories were
walked through and confirmed individually with the user (see that file's
"Review history" section for what changed during review).

**This spec complies with**:
- **CONSTITUTION.md** §I (config/dependency handling — no env vars, all
  config via `AppConfiguration`), §V (real internal code paths, mocks only
  for third-party network services), §XVII (no monkey-patching).
- **METHODOLOGY.md** §I (user stories mandatory), §II (template structure).

---

## Origin

The user provides periodic WhatsApp chat exports (a zip: one chat-history
text file + the referenced media files) covering the full history of a real
production WhatsApp conversation, from the beginning of time. Production
ledger-event data (`{data_root}/events/*.json`, Feature 033's schema) needs
to be built/kept current from these exports, applying the *same* Ledger
Event Recognition rules (`config/runtime_constitution.md`'s "Ledger Event
Recognition" section) DeniDin already applies to live messages — not a
parallel or looser interpretation.

## The "player" framing (settled during review, 2026-08-06)

This tool is a **player**: it replays historical WhatsApp messages through
DeniDin's real ledger-capture machinery *as if they had just arrived live*,
rather than being a bespoke reimplementation of the extraction/
classification rules. Concretely this means:

- Text/image classification correctness (agreements in text, agreements in
  images, bank deposits in images) is **not** re-tested by this feature —
  it's already covered by DeniDin's existing test suite, and the player
  calls that exact same code, unmodified. See "Player timestamp audit"
  below for the one place a replayed message genuinely differs from a live
  one.
- The player's own responsibilities are: parsing the export, sequencing
  messages, scoping to a date range, running each message through the real
  pipeline, relevancy/reconciliation bookkeeping, and never leaving
  orphaned or unaccounted-for state.
- There is **one operation, not two "modes."** Earlier drafts of this spec
  described separate "override" and "incremental" modes; the user pointed
  out during review these are the same operation with different `[start,
  end]` date-range parameters — see US1. "Pause," "resume," and "rewind"
  are likewise just this same operation re-invoked with a different `start`
  — no separate mechanism needed.

Two distinct needs:

1. **Part 1 (this feature's first deliverable)**: run the player once
   against the current export to (re)build production ledger events for the
   date range of interest (default: **September 1, 2025 → latest message in
   the export, never later than today**) — since ledger event *definitions*
   are expected to keep evolving, re-deriving from source on demand is the
   model, not a one-time script never touched again.
2. **Part 2**: the player itself is permanent, git-tracked project tooling
   (`apps/denidin-app/scripts/`, evolving alongside the ledger-event schema
   as Feature 033/043-descendant work continues) — not a throwaway
   migration script. The same single operation also serves narrower replays
   (e.g. DeniDin was down for a couple of days and live capture never ran
   for them) by simply narrowing `[start, end]`.

## Scope

**In scope:**
- Parsing a WhatsApp chat-export zip (chat-history text + media files) into
  an ordered sequence of messages with resolved timestamps, senders, text
  content, and attached media file paths.
- A `[start, end]` date range parameter: `start` defaults to (and may never
  be earlier than) `2025-09-01`; `end` defaults to (and may never be later
  than) today.
- Playing each in-range message through the **same underlying
  extraction/classification/persistence machinery** DeniDin's live path
  uses (`LEDGER_EVENT_TOOL`'s schema, `ImageExtractor`'s document/ledger
  classification, `LedgerEventManager`'s normalization/persistence) — not a
  reimplementation of those rules. See US1.
- A **relevancy/reference-resolution step** (US2): after a message's own
  standalone classification call, cross-reference the ledger events already
  accumulated so far (this run's own output, chronologically, or already on
  disk for a narrower replay) to resolve what a correction/cancellation/
  `replaces_hint` refers to — deliberately *not* a full conversational
  session replay (see Clarifications).
- Deterministic `event_id` assignment identical in scheme to live
  (`{letter}{DDMMYY}{HHMM}{seq}`), so re-running against the same export/date
  range is idempotent in principle.
- Reconciliation for the played range: nothing in `[start, end]` may be left
  un-accounted-for (no orphans) — every pre-existing event file in range not
  freshly regenerated this run is moved (never hard-deleted) to a
  `to-delete` holding location, with a manifest explaining why (US1, US4).
- **Two-pass ambiguity handling** (US3): a material ambiguity that live
  rules would normally ask the user about instead produces a flagged,
  queued review item; the player supports a second pass that re-applies
  operator answers back into the ledger without re-deriving everything from
  scratch.
- A new **schema-version field** on every persisted ledger event record
  (US5), so future re-migrations and analyses can tell which rule-set
  generation produced a given record.
- The player is permanent, reusable, git-tracked tooling (US6) — plus any
  shared library code it needs, factored the same way `LedgerEventManager`
  already is — designed to be run again whenever ledger-event definitions
  evolve or a gap needs backfilling, not deleted after first use.

**Out of scope (explicitly deferred, per user's clarifying answers):**
- Redefining or improving the Ledger Event Recognition rules themselves —
  this feature applies whatever the *current* constitution rules are at run
  time. Any rule/schema evolution is a separate, prior change to
  `runtime_constitution.md` (and if needed, `LEDGER_EVENT_TOOL`/
  `LedgerEventManager`), done before invoking a replay.
- Any change to how DeniDin captures ledger events **live** — the player
  reuses that machinery, it doesn't modify it. The one exception noted
  during review: the correction/cancellation relevancy-resolution logic in
  US2 is expected to eventually move into live capture too, but that's
  tracked under Feature 040 (agreement cancellation/modification), not
  here — for 043 it lives only in the player.
- Re-verifying text/image ledger-extraction *correctness* — already covered
  by DeniDin's existing test suite (see "player framing" above).
- Morning/Green-Invoice reconciliation (invoice status, `H`-type events) —
  unrelated to this feature; those fields stay `null` as they already are.
- Actually running the player against real production data — that is a
  separate, explicit approval gate at execution time (see "Environment /
  data safety" below), not something this spec authorizes.

## Clarifications (resolved with user, 2026-08-05/06)

- **Q: How does the player handle a material ambiguity the live rules would
  normally ask the user about?**
  **A: Two-pass review queue** (US3). The run never blocks interactively.
  Every message that the classification step flags as materially ambiguous
  is captured as usual (per the constitution's existing "notes-flagging is
  the fallback when asking isn't practical" philosophy) but *additionally*
  written to a separate review-queue artifact. After the run, a human
  answers the open questions; a second invocation re-applies those answers,
  producing corrected event(s) without re-deriving the whole range.
- **Q: Does the player replay each chat as one continuous synthetic session
  (full conversational memory, like live), to resolve corrections/
  `replaces_hint`?**
  **A: No — independent-message classification + a separate deterministic
  (or AI-assisted, TBD at plan stage) relevancy step against the
  already-accumulated ledger** (US2). Concretely, a 3-step per-message
  pipeline:
  1. Send the current message (text or image) to the AI for analysis, using
     the same extraction rules/tool schema as live — but as a *standalone*
     call, with no prior conversation turns attached.
  2. Scan the ledger events already captured so far (this run, or already
     on disk for a narrower replay) for events plausibly relevant to this
     message's classification (same client/matter, prior amount, etc.).
  3. Apply that relevancy (i.e., populate `replaces_hint`/link a correction
     to what it replaces) before persisting the new event.
  Steps 2–3 *can* use AI but don't have to — they're largely deterministic
  matching; plan.md decides which, and may keep this simple for v1 with room
  to strengthen later. This logic is expected to migrate into live capture
  eventually (Feature 040), but stays player-only for 043.
- **Q: Is redefining the ledger-event rules themselves in scope?**
  **A: No — tooling only.** Rule changes are separate, prior edits to
  `runtime_constitution.md`.
- **Q: What happens to a stale file left over from a message that now
  correctly produces a different set of events than what's on disk?**
  **A: Moved, never hard-deleted.** Orphaned/stale files go to a designated
  `to-delete` holding location (exact path decided in plan.md — e.g. a
  sibling `{data_root}/events/_to_delete/<run_timestamp>/` — with a manifest
  of what was moved and why), so a human can review/permanently remove them
  later. This satisfies "no orphans left in the live `events/` directory"
  without the player ever performing an unrecoverable delete on production
  data.
- **Q: Are US3 ("text agreement"), US4 ("image agreement"), US5 ("image bank
  deposit") capture-correctness stories needed?**
  **A: No, dropped.** DeniDin's existing test suite already covers this;
  the player reuses that exact code path unmodified. The one thing that
  genuinely differs for a replayed (non-live) message is **timestamp
  handling** — see "Player timestamp audit" below, the real reason these
  stories were dropped rather than kept as regression coverage.

## Player timestamp audit (open question, must resolve before /tasks)

Because the player "plays" old messages through live code paths, every
place that code path currently uses **wall-clock `datetime.now()`** instead
of the message's own timestamp needs auditing — using real wall-clock time
for something that should reflect the message's historical moment would
silently corrupt the replay (e.g. relative-date resolution like
"היום"/"אתמול" in a historical message must resolve against *that message's
date*, not the day the player happens to run). Known candidate, unverified:
`ai_handler.py`'s "today's UTC date" injection into `instructions`
(`ai_handler.py:363-368`), used for resolving relative dates — needs
confirming whether this must be swapped to the message's own date when
played. `LedgerEventManager.add_ledger_event`'s `captured_at` field is
believed correct to stay wall-clock (it means "when this record was
written," which is genuinely now, during the player run) — needs
confirming, not assuming, same as everything else in this audit. This audit
is a prerequisite for plan.md/tasks.md, not something to resolve by
inspection alone — CONSTITUTION's "no unverified third-party assumptions"
discipline applies to internal code behavior here too: verify by reading
the actual code path, not by memory of how it "should" work.

## Open questions for plan.md (not blocking spec approval, but must be
resolved before /tasks)

- The full player timestamp audit above.
- Exact shape/location of the schema-version field (e.g. `schema_version:
  "2026-08"` vs. an integer) and whether it's retro-applied to pre-existing
  (non-migrated) event files or only written going forward by the player
  and by live capture.
- Exact relevancy-matching algorithm for US2's step 2/3 (deterministic
  heuristic vs. AI-assisted) and its confidence threshold for
  auto-linking vs. flagging for review.
- Review-queue artifact format/location, and the second-pass CLI contract
  for re-applying operator answers.
- How WhatsApp's export text format encodes message boundaries, timestamps,
  senders, and media-file references (needs one real sample export file to
  confirm — CONSTITUTION's "no unverified third-party assumptions" rule
  applies here too, even though WhatsApp export format isn't a live network
  call).
- Whether/how the player needs to resolve `sender`/JID the same way live
  Green API messages do, given a chat export identifies senders by display
  name/phone rather than a Green API webhook payload.
- Cost/rate-limiting posture for a run covering ~11 months of chat history
  (potentially many OpenAI vision calls) — batching, checkpointing/resume,
  and dry-run cost estimation before a real run.

## Environment / data safety

This feature produces a player that **writes to real production ledger
data**. Per project rules (see CLAUDE.md's environment-start and
config-freeze banners): building and testing this tool happens against
`test_data/`/`dev_data/` fixtures only; any run against real `data/events/`
requires explicit, separate human approval at execution time, is not
authorized by this spec's approval alone, and is never run by the agent on
its own initiative.
