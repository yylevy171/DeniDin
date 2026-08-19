# Feature Specification: Stabilize Tests and Create a Sanity Testing Suite

**Feature Branch**: `feature/059-stabilize-tests-sanity-suite`
**Created**: 2026-08-20
**Status**: Placeholder — not yet clarified/specced. Captured from a 2026-08-20 request;
run `speckit.specify` + `speckit.clarify` before starting implementation.

## Input

User description: "create a backlog feature 59 - stabilize tests and create a sanity testing
suite" — raised directly after a Feature 054 (reminders) hardening session that surfaced several
distinct, real test-reliability problems in quick succession, none of them actual application
bugs, all of them costing real time to tell apart from ones that were.

## Context that prompted this

Several distinct classes of test-infrastructure fragility were hit back-to-back during Feature
054's finish-up (2026-08-19/20), each requiring real investigation to rule out before it could be
dismissed:

1. **Time-of-day-fragile assertions.** A billed test (`test_modify_single_occurrence_of_recurring_reminder`)
   compared occurrences by hardcoded list index, assuming index 0 always meant "tomorrow's
   occurrence" — true only if the test happens to run after today's own reminder time has already
   passed. Running the same test near midnight made a correctly-behaving system look broken.
   Fixed for this one test (date-based matching, not index-based) but the pattern likely exists
   elsewhere untested.
2. **Persistent `test_data`/`dev_data` schema drift.** `test_data/reminders/reminders.db` and
   `dev_data/reminders/reminders.db` both silently kept their pre-migration schema (`CREATE TABLE
   IF NOT EXISTS` never adds a new column to an existing file) after a `delivery_chat_id` column
   was added — producing `sqlite3.OperationalError: no such column` failures that looked like
   real regressions until traced. Separately, `test_data/sessions/` held session JSON written
   before a `ai_required_role` field existed, causing an unrelated integration test
   (`test_group_image_processed_normally_with_resolved_sender_name`) to fail with a `KeyError`
   after a master merge — confirmed via a throwaway `git worktree` check that the exact same test
   passes cleanly on a fresh checkout. No mechanism currently detects "this persisted test
   fixture predates a schema change" before it manifests as a confusing failure.
3. **Real external rate-limiting mimicking real bugs.** A billed test failed with the app's own
   `"I'm currently at capacity"` fallback message after real `429 Too Many Requests` responses -
   correct, working behavior under genuine OpenAI rate-limit pressure, but indistinguishable at a
   glance from an actual defect until the raw HTTP log was read. Investigating this also surfaced
   a real, separate bug (see reference below) - two unrelated retry mechanisms (the OpenAI SDK's
   own default `max_retries` and this app's own `tenacity` decorators) were silently stacking,
   turning what should be a ~5s retry into ~100s and *worsening* rate-limit pressure on every
   sequential billed-test run.
4. **A stale test asserting a removed field.** An `expensive` test
   (`test_given_real_bank_deposit_image_then_full_fields_correctly_persisted`) asserts against
   `message_timestamp`, a field a documented, deliberate schema change ("Phase 11 schema v2→v1
   reset", 2026-08-16) stopped persisting - the test was never updated to match, so a real
   OpenAI-billed run failed for a reason that had nothing to do with the code under test.
5. **A flaky shared test helper.** `_seed_fresh_client` (`tests/billed/denidin_mcp_e2e_helpers.py`)
   failed to seed a "genuinely fresh" client after 5 attempts - every randomly-generated candidate
   name fuzzy-matched an existing Morning sandbox client closely enough to trigger a disambiguation
   question the helper's own retry logic (a bare `"כן"`) can't correctly answer. Plausibly the
   sandbox has simply accumulated too many prior test-run clients over time for random-name
   collision avoidance to keep working reliably.
6. **No CI at all, until just now.** `.github/workflows/ci.yml` existed and ran on every PR into
   `master`, entirely unbeknownst to the user ("since when does a merge do CI?!?!?! this is
   completely new to me") - and had been failing at the collection stage since its earliest
   recorded runs (`import denidin` at module scope triggers `denidin.py`'s config-loading
   `sys.exit(2)`, since `config/config.json` is correctly gitignored and never present on a CI
   runner). Removed per explicit instruction (2026-08-20) rather than fixed, since its existence
   and behavior were both a surprise.

## Notes captured so far

- **"Stabilize tests" and "sanity testing suite" may be two related but distinct halves.** Scope
  not yet defined - open questions for `speckit.specify`/`speckit.clarify`:
  - Does "stabilize" mean auditing/fixing the SPECIFIC fragility classes found above across the
    whole suite (not just the one test each was first noticed in), or building a general
    mechanism/convention that prevents this whole category of issue going forward (e.g. a
    documented/enforced rule that persisted fixture directories get wiped on schema-affecting
    changes, or a lint/CI-adjacent check for time-of-day-dependent test assumptions)?
  - What is a "sanity testing suite" here — a small, fast, high-confidence subset of tests meant
    to be run frequently/casually to answer "is anything obviously broken," distinct from the
    full unit/integration/billed/expensive tiers? If so: what belongs in it, how is it triggered
    (a new script? a pytest marker?), and does it overlap with or replace the now-removed CI
    workflow's intent (minus that workflow's specific `config.json`-availability bug)?
  - Should CI be reinstated in some form as part of this feature (now that its prior, silent
    failure mode is understood and its existence is no longer a surprise), or is that explicitly
    out of scope / a separate decision?
- **`_seed_fresh_client`'s sandbox-clutter theory is unconfirmed** - worth investigating directly
  (e.g. counting how many clients currently exist in the Morning sandbox) before assuming that's
  the actual cause rather than the helper's own "כן"-only disambiguation handling being wrong.

## References

- Feature 054 (`specs/done/054-reminders-functionality-mgmt/`) - the session all six incidents
  above were found during, none of them Feature 054 code defects.
- The OpenAI-retry-double-stacking bug (item 3 above) was fixed directly as part of Feature 054's
  own branch (`AppConfiguration.max_retries`, `denidin.py`'s `OpenAI(...)` construction,
  `ai_handler.py`'s tenacity-decorator removal) since it was concrete and narrow enough to fix in
  place rather than defer - see that feature's git history for the exact commit. Everything else
  in this list is unfixed as of this spec's creation.
