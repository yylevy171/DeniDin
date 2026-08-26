# Bugfix Spec: Hourly maintenance bugs

## Bug ID
bugfix-035-hourly-maintenance-bugs

## Title
Two defects in the hourly `SessionCleanupThread` sweep. One session can never be loaded at
all; another can never complete its transfer, so it is re-summarised — at real OpenAI cost —
**every hour, indefinitely**, writing a duplicate memory record each time. Both have been
running unattended in production for days. Filed as one bug by user decision (2026-08-09).

## Priority
**P2** — backend maintenance internals, no direct impact on user messages, per the ranking
rule set 2026-08-09.

> ⚠️ **Recommend doing this first within P2.** Unlike the other P2s this one is *actively
> accruing* — unbounded hourly cost and a memory collection that grows more polluted every
> hour it is left alone. The core fix is a one-line change.

## Status
**Open — backlogged.** No fix designed. Per Bug-Driven Development (METHODOLOGY.md §VII), next
step is human approval of the root causes before test-gap analysis.

## Date Opened
2026-08-09

## Reported By
yaronlev171, from the 7–9 Aug 2026 production review
([`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md), P2-8 + P2-12).

> **Shared session context** — how this review was run, the read-only access paths, the full
> map of bugfix-028…037, the triage decisions (including what was closed as *not* a bug), and
> the open verification items:
> [`bugfix-028` § Session Context](../done/v0.4.1/bugfix-028-invoicing-and-approval-gate-p0-cluster/bugfix-028-invoicing-and-approval-gate-p0-cluster.md#session-context-2026-08-09-production-review)
(moved to `specs/in-progress/bugfixes/` 2026-08-10, now In Progress).
> All ten bugs in that set are **fix-forward only** — existing production documents are being
> left as they are by explicit user decision.

## Affected Area
- `apps/denidin-app/src/handlers/ai_handler.py:1890` — `collection_name` derivation
- `apps/denidin-app/src/handlers/ai_handler.py:1915` — the "Verify storage" step
- `apps/denidin-app/src/managers/memory_manager.py:113` — collection-name sanitisation
- `apps/denidin-app/src/managers/session_manager.py` — `Session` deserialisation
- `apps/denidin-app/src/services/cleanup_service.py` — the hourly sweep, retry behaviour

---

## H1 · Long-term memory can never complete for a group chat — retried hourly forever *(was P2-8)*

**Two bugs in series.**

**1 — the raw name survives for groups.** `ai_handler.py:1890`:
```python
collection_name = f"memory_{session.whatsapp_chat.replace('@c.us', '')}"
```
Only `@c.us` is stripped. A **group** chat (`…@g.us`) keeps its `@`, giving
`memory_120363210094632983@g.us`.

**2 — the verify step bypasses the sanitiser.** `memory_manager.py:113` sanitises on write
(`'@' → '_at_'`), so `remember()` **succeeds** and the record really is stored. Then
`ai_handler.py:1915` does:
```python
collection = self.memory_manager.client.get_collection(name=collection_name)   # RAW name
```
— straight to the underlying Chroma client, unsanitised. It throws `NotFoundError`, the broad
`except` catches it, and **an operation that already succeeded is reported as failed.**

A verification step is corrupting the thing it verifies.

**The loop.** Because the transfer reports failure, `transferred_to_longterm` is never set, so
the next hourly sweep reprocesses the same session: fresh **billed** OpenAI summarisation,
another duplicate record, another failure.

Prod log, one iteration of 27 identical ones:
```
04:33:21  AI summarized session 17df631a…: 2010 chars          ← billed OpenAI call
04:33:21  Starting ChromaDB storage … in collection memory_120363210094632983@g.us
04:33:23  ChromaDB storage completed …: memory_id=cfdead17…    ← write SUCCEEDED
04:33:23  ERROR Failed to transfer session …: Collection [memory_120363210094632983@g.us]
                                              does not exist
04:33:23  ERROR Failed to transfer session …: transfer_error
```

Measured damage as of 2026-08-09 06:37 UTC — and still growing:
```
memory_120363210094632983_at_g.us : 27 records, ALL session 17df631a
memory_972522968679               :  2 records
```

**Impact.** (a) Tier-2 memory never completes for the group — the primary production channel.
(b) Unbounded hourly OpenAI cost. (c) 27 near-identical summaries of one session will dominate
semantic recall and crowd out everything else.

**Note:** the *recall* path (`ai_handler.py:695`) has the same `@c.us`-only strip but goes
through `MemoryManager`'s sanitising wrapper, so reads work. Only the raw `get_collection`
verify call fails. Fix both derivations anyway.

**Also fix:** the retry has no budget, no backoff, and no dead-letter. A transfer that has
failed N times should stop and be surfaced, not loop forever.

---

## H2 · A session with an unknown field can never be loaded, expired, or archived *(was P2-12)*

```
ERROR Failed to check session 0f5eaa04-6277-46ec-8e86-c9cae932170a:
      __init__() got an unexpected keyword argument 'pending_ledger_events'
```

**65 occurrences** in the Aug 7–9 slice alone — once per hourly sweep, plus on load and on
orphan recovery. Session `0f5eaa04` was written on Aug 3 with a `pending_ledger_events` field
the current `Session` model no longer accepts, so it can never be deserialised. It is stuck
permanently: never expired, never archived, never transferred, and it logs an error every hour
forever.

**Root cause.** No tolerance on the persisted session schema — an unknown key is a hard
`TypeError` rather than being ignored or migrated. Any future field rename or removal will
strand every session written before it in exactly the same way.

**Impact.** One permanently stuck session and hourly log noise today; a latent trap for every
future schema change.

---

## H3 · `expired/` accumulates stale sessions across runs, and nothing scopes a lookup to "this
run's own session" *(added 2026-08-26, not yet triaged into H1/H2's priority)*

`tests/billed/test_session_transfer.py::test_session_transfer_and_recall_after_expiration`
failed during Feature 044's closing regression sweep
(`specs/in-progress/044-ledger-event-querying/`), a run unrelated to Feature 044 itself:

```python
archived_sessions = list(expired_dir.rglob("*/session.json"))
assert len(archived_sessions) >= 1, "Session should be archived to expired/YYYY-MM-DD/ folder"

archived_session_path = archived_sessions[0]          # <-- first match, unfiltered
...
assert archived_data['session_id'] == session_id, "Archived session ID should match"
```
```
AssertionError: Archived session ID should match
assert 'bbc28e41-0518-41fb-a2fe-a4250ab64e82' == 'a46aa2e2-5600-4390-b72c-d93125cb2088'
```
The test's own `expired/` directory held more than one archived `session.json` by the time this
assertion ran, and `rglob(...)[0]` picked up a **different, pre-existing** archived session
instead of the one this specific run's `PHASE 2`/`PHASE 3` had just created and expired — not a
transfer failure in the H1/H2 sense, but the same family of symptom: session lifecycle state
(here, archived sessions on disk) accumulating unbounded and untracked between runs, this time
surfacing as a test-isolation bug rather than a production cost/log-noise one. Not investigated
further — no root cause confirmed yet, and it is not yet clear whether this is purely a test
fixture gap (the test should scope its own `expired_dir` glob to sessions matching its own
`session_id`/`chat_id`, or clean the directory before it runs) or also reflects a production-side
gap in how `expired/YYYY-MM-DD/` is meant to be bounded/rotated over time. Logged here per
explicit user decision to attribute this failure to bugfix-035 for a human read-through,
alongside H1/H2, rather than as its own separate bug.

## Expected
- Group-chat session transfer completes and marks `transferred_to_longterm`.
- The verify step uses the same name resolution as the write (or is dropped — it adds no value
  if `remember()` already returns an id).
- Retries are bounded, with a dead-letter and a visible signal on give-up.
- Session deserialisation tolerates unknown persisted fields (ignore + warn, or migrate),
  rather than failing permanently.
- (H3) Either the test suite scopes archived-session lookups to the session it itself created, or
  a production-side bound/rotation policy for `expired/YYYY-MM-DD/` is confirmed to already exist
  and this is purely a test-fixture gap — to be determined during root-cause investigation.

## Prod cleanup (separate, requires a write — not part of the fix)
The 27 duplicate records in `memory_120363210094632983_at_g.us` should be purged. Sequencing
undecided (open question 5 in the review doc). **Not to be done as a side effect of this
bugfix** — it is a production data write and needs its own explicit approval.

## Related Work
- Feature 033 / spec 024 — introduced `pending_ledger_events`, later moved out of the session
  (H2 is that migration's residue).
- `specs/done/v0.0.1/019-env-separation/` — `data_root` separation; the stuck session predates the
  current schema.
