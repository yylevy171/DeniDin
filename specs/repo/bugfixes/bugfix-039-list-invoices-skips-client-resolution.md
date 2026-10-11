# Bugfix Spec: Morning-tool client-name resolution doesn't cover real nickname/spelling variants

## Bug ID
bugfix-039-list-invoices-skips-client-resolution

## Title
Originally: `list_invoices`' `client_name` filter is forwarded raw to Morning's `/documents/search`,
bypassing client resolution entirely. **Expanded 2026-08-11** (user decision, mid-fix): the same
root problem — no code path in this app tolerates a genuine single-letter name variant (nickname,
nearby spelling) — also existed in `create_invoice`/`create_transaction_account`/
`create_combo_document`'s own "resolution", which *did* run but silently created a real document
against the guessed match instead of confirming it first. Both are now fixed by the same
mechanism. See "Session Handoff" below for the full story.

## Priority
**P1** — user-facing, direct impact on real financial answers/actions. A wrong "not found" on an
invoice-status question, or a document silently created against the wrong client, are both
directly harmful, not just annoying.

## Status
**Done - Merged to master (PR #211).** Root cause investigated and approved by user
(yaronlev171, 2026-08-10); scope expanded by explicit user decision (2026-08-11, round 1) after a
test surfaced a much bigger, related problem; round 2 (2026-08-11) added constitution guidance and
permanent T1/T2 fixtures per user review; round 3 (2026-08-11, same day) was a full rewrite of the
resolution algorithm itself, driven by the user directly specifying a deterministic
word-by-word/letter-by-letter matching procedure after finding a real production bug in `list_invoices`
during the denidin-app billed-test sweep.

**Final verification (2026-08-12)**: the three sandbox integration files flagged as not-yet-verified
in round 3's handoff are now confirmed against the final round-3 code —
`test_morning_sandbox_get_client_details_tool.py` 4/4, `test_morning_sandbox_list_invoices_tool.py`
9/9, `test_morning_sandbox_update_client_tool.py` 13/14 (the one remaining failure is an external
Morning sandbox rate limit — a bare `403` on `/api/v1/account/token` before any application code
runs, the same documented self-clearing class hit twice earlier in this bug's own history — accepted
as a known external flake, not a code issue). `morning-mcp-app` billed: 5/5. The denidin-app billed
sweep resumed from the top: test 6 (`get_client_details` not-found) needed a genuine test fix — it
over-specified which tool the model must call and the exact reply wording; loosened to check intent
(a real "no client found" answer, reached by actually querying Morning) instead, per explicit user
direction. Test 7 (`update_client`) surfaced a real, separate, out-of-scope finding — a wrong MCP
parameter name can cause a silent tool failure with no clear disclosure to the user — logged here for
the record but intentionally not fixed as part of this bug (out of scope: this bug is about client-name
resolution, not general tool-failure disclosure; see "Related Work" below for how it connects to the
pre-existing, unmerged `bugfix-028` B5 item, which already designed a fix for this exact class of gap).

## Date Opened
2026-08-10

## Reported By
yaronlev171, from a live production incident the same day — found via prod log analysis at the
user's request ("read prod logs and data... report back your findings"), missed in the first pass
of that analysis and flagged explicitly by the user afterward. Scope expansion (2026-08-11) also
user-driven, from a real billed-test failure encountered while writing this bug's own regression
test.

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` — round 3 rewrote the entire client-name
  resolution mechanism. Current functions: `resolve_client_by_name` (THE one mechanism, new),
  `_grow_word` (new), `_bag_equal_words` (new), `_levenshtein` (new), `_search_word_prefix` (new),
  `_sorted_by_distance` (new), `_resolve_client_final` (new), `_COMMON_WORD_DISCOVERY_CAP` (new
  constant, =10), `_resolve_client_by_name` (old whole-string search, KEPT — reused by Step 0/Step
  Final), `_resolve_client_for_document_creation` (rewired to delegate to `resolve_client_by_name`),
  `list_invoices` (rewired — this is where today's real bug lived), `get_client_details` (rewired,
  newly covered by multi-word matching for the first time). REMOVED entirely:
  `_resolve_client_by_name_words`, `_search_word_with_truncation`, `_WORD_TRUNCATION_MIN_LENGTH` (all
  three were round-1's mechanism, now fully superseded). `_is_exact_name_match` still exists (still
  has its own passing unit tests) but is no longer called by anything — dead code, deliberately left
  in rather than deleted to avoid breaking those tests without sign-off.
- `apps/morning-mcp-app/src/denidin_mcp_morning/formatters.py` —
  `format_client_name_confirmation_question` (round 1/2, unchanged in round 3).
- Prototype (NOT part of the repo, scratchpad only — see "Session Handoff, round 3" for exact paths):
  `client_resolution_prototype.py`, `test_client_resolution_prototype.py` (25 tests),
  `show_test_table.py` (Hebrew ground-truth table generator). Built and iterated on FIRST, before
  touching real code, per explicit user instruction.
- Tests updated/added (round 1+2+3 combined): `tests/unit/test_tools_client_resolution.py`,
  `tests/unit/test_tools_client_management.py`,
  `tests/integration/test_morning_sandbox_list_invoices_tool.py`,
  `tests/integration/test_morning_sandbox_create_invoice_client_resolution.py`,
  `tests/integration/test_morning_sandbox_update_client_tool.py`,
  `tests/billed/test_openai_invokes_mcp_e2e.py` (morning-mcp-app);
  `apps/denidin-app/tests/billed/test_denidin_morning_invoice_creation_e2e.py`,
  `apps/denidin-app/tests/billed/denidin_mcp_e2e_helpers.py`,
  `apps/denidin-app/tests/billed/GROUND_TRUTH_CLIENTS.md` (denidin-app). **Not yet touched by round
  3, needs checking**: `tests/integration/test_morning_sandbox_get_client_details_tool.py` (this
  tool's resolution changed in round 3 for the first time ever — likely has stale assumptions, same
  class of issue already fixed in the other three integration files this round).
- `apps/denidin-app/config/runtime_constitution.md` — added explicit model-facing guidance for the
  confirmation-question reply (round 2, unchanged in round 3).
- **Not touched, flagged as a candidate follow-up, not part of this bug**: none remaining —
  `update_client` was brought into line in round 2.
- `specs/done/v0.0.1/031-fuzzy-client-lookup-by-name/` — the feature that investigated the original
  `list_invoices` question and closed 2026-07-30 with "no code change needed"; that conclusion is
  now known to be incomplete (see "Original root cause" below).

---

## Session Handoff (2026-08-11) — read this first if picking this up fresh

**TL;DR**: The fix works and is fully tested (unit + real-sandbox integration + real conversational
billed tests, all green). What's left is: (1) human review of the diff, (2) decide whether to bring
`update_client` in line too, (3) finalize this spec's `Expected`/close it out, (4) run `/haleluya`
**only when explicitly told to** — do not do this unprompted, ever, per standing user instruction.

### The story, in order
1. **Original finding (2026-08-10)**: `list_invoices`' `client_name` filter is passed raw to
   Morning's `/documents/search`, which does whole-string substring matching only — a real admin
   query (`"דוד אדלר"`) missed a real invoice stored under a nickname variant (`"דודי אדלר"`),
   producing two confident wrong "not found" answers before the model gave up and scanned
   unfiltered. Traced to a live production incident. See "Original root cause" below for the full
   original writeup (kept for the record — the core diagnosis there is correct, but its proposed
   fix, "route through the existing `_resolve_client_by_name`," turned out to be insufficient; see
   next point).
2. **First fix attempt failed its own test**: routing `list_invoices` through the existing
   `_resolve_client_by_name` (used by the creation tools) didn't work, because a **live probe against
   the real sandbox** showed that endpoint has the *exact same* whole-string-prefix limitation —
   `/clients/search`'s `name` param also can't handle a multi-word query where an earlier word isn't
   the literal stored spelling. This meant the "smart" resolution the creation tools already used
   was never actually smart enough for this case either — an assumption from the original writeup
   that had never been empirically verified. Built `_resolve_client_by_name_words`: decomposes a
   multi-word query, searches each word individually (Morning's single-word prefix search is
   reliable), and intersects the per-word candidate sets client-side. `list_invoices` was updated to
   use it (multi-word queries only — single-word queries are deliberately left alone, since a bare
   word like "Cohen" is a legitimate partial search, not a full-name lookup, and re-resolving it
   risks a false "ambiguous" refusal against unrelated clients).
3. **User caught a live production bug this same investigation had missed**: while testing, an
   *existing* billed test (`test_create_document_for_similarly_named_existing_client`) failed. Root
   cause turned out to be that test's own random-name generator colliding with 4-day-old sandbox
   residue (a *known* failure class — see `_fresh_nonexistent_client_name`'s docstring, "a real,
   observed 2026-08-07 failure") — not a real bug. But investigating it, the user pushed further:
   *"Another word does not count as 'similar'"* — the old test's "drop a whole trailing word" case
   was too easy (already handled by plain whole-string prefix matching) and never actually exercised
   a genuine nickname/spelling variant. The user specified two real regression cases directly:
   - **T2**: `seed "אדלר דודי" → invoice for "אדלר דוד"` (one letter *removed* at the end of a word,
     not the first letter) — the exact shape of the original production incident.
   - **T1**: `seed "זהבית צור" → invoice for "זהבית צורן"` (one letter *added* at the end) — the
     mirror direction, which turned out to need genuinely new code (see next point).
4. **Scope expansion, by explicit user decision**: the user also pointed out that `create_invoice`
   was, at the time, creating a real document against a guessed non-exact match and only disclosing
   which client it used *after the fact* — too late for the user to catch a wrong guess. Asked to
   expand the fix "to wherever the confirmation is to be expected, but not to where there is no
   confirmation required, i.e. AI found the client and the user requested name matches the client
   name in the system." User also specified the desired UX precisely: a closed
   `"מצאתי לקוח בשם X - האם לזה התכוונת? אישור - כן/לא?"` question, and that this must **create
   nothing** until confirmed.
5. **T1 required new capability**: Morning's prefix search only covers "query is a prefix of a
   longer stored word" (confirmed live: `"Yoss"` finds `"Yossef"`). It does **not** cover the mirror
   direction — a query with an *extra* trailing letter beyond a real, shorter stored word (confirmed
   live: `"צורן"` finds nothing when the real client is `"צור"`). Built
   `_search_word_with_truncation`: retries a word search with progressively shorter right-truncations
   (floor of 2 characters) until something matches — closes this gap using only real Morning prefix
   searches, no invented fuzzy/edit-distance matching.
6. **Rewired `_resolve_client_for_document_creation`** (shared by `create_invoice`/
   `create_transaction_account`/`create_combo_document`): a non-exact single match now refuses (same
   shape as the existing ambiguous/not-found refusals) with the new confirmation question, and
   creates nothing. `ClientResolution.disclosure_name` — no longer meaningful, since only exact
   matches proceed now — was removed entirely, and the three creation functions' now-dead
   "disclose after creating" branches were deleted along with it.
7. **Discovered mid-implementation, worth knowing**: the real dev `morning-mcp-app` Docker container
   is **not** rebuilt automatically by `run_morning_mcp.sh` (it only does `docker compose up -d`) —
   this was already documented in CLAUDE.md but got missed twice this session before being caught by
   `docker exec ... grep` sanity checks. If you're verifying anything against the live dev tunnel,
   confirm the container's `tools.py` actually has your changes first.
8. **Hit an external blocker mid-session**: Morning's real sandbox returned a blanket `403 Forbidden`
   at the AWS load-balancer level (not even reaching the app) for a while, almost certainly a
   rate-limit trip from this session's very heavy real-API test volume. Not a code issue — cleared on
   its own after a ~15min poll-and-wait. If you see a bare `403` with no JSON body on
   `/api/v1/account/token`, this is probably it — wait rather than debug the code.
9. **A billed-test design limitation worth knowing, not a bug**: the T1/T2 billed conversational
   tests (`test_create_document_t1_single_letter_added_to_stored_name` /
   `..._t2_single_letter_removed_from_stored_name`) seed the real client in the *same live
   conversation*, immediately before asking. The model sometimes already has the real name in
   recent context and self-corrects before ever calling `create_invoice` with the wrong one — a
   fine outcome, but it means these two tests can't reliably force the new refuse-then-reask branch
   specifically; they verify the end result (right client, one document, nothing created for a
   wrong guess) rather than the exact mechanism. The mechanism itself is unambiguously proven by the
   sandbox-level tests in `test_morning_sandbox_create_invoice_client_resolution.py`, which call
   `create_invoice` directly with no surrounding conversation to leak context from.

### Final test status (all green, last run 2026-08-11)
| Suite | Result |
|---|---|
| `morning-mcp-app` unit | 243/243 |
| `morning-mcp-app` integration (real sandbox, incl. new T1/T2 + confirmation-question tests) | 96/96 |
| `denidin-app` unit | 733/733 |
| `denidin-app` billed — T1, T2, exact-match sibling (against a freshly rebuilt dev container, confirmed via `docker exec ... grep` to actually have the final code) | 3/3 |
| `morning-mcp-app` billed — all 5 (3 pre-existing + 2 new for `list_invoices`) | 5/5, run earlier in the session |

### Explicit next steps for whoever picks this up
1. Review the diff (`git diff` on branch `bugfix/039-list-invoices-skips-client-resolution`) —
   nothing has been committed yet.
2. Decide on `update_client` (see "Affected Area" above) — bring it in line with the same
   refuse-and-ask treatment, or explicitly leave it out of this bug.
3. Decide whether `CLAUDE.md`'s pending diff (prod data/log access quick-reference, added earlier
   in this session, unrelated to this bug) should ride along in the same commit/PR or be split out
   — it's a genuinely separate, unrelated change that happens to be sitting in the same working tree.
4. Once approved, this still needs the full haleluya treatment (spec status/PR-number update, one
   commit, push, PR, merge) — **do not run it without the user explicitly saying so**, per standing
   instruction (this applies regardless of how "done" the work looks).

## Session Handoff (2026-08-11, round 2) — user review of the above raised two follow-ups

The user reviewed the round-1 summary above and pushed back on two points. Both were resolved via
explicit user decision (not assumed) before any code changed:

1. **"Refusal" was confusing UX-wise.** The user's first instinct was that create tools should take
   a `client_id` so they could "always create" once resolved. Investigation surfaced a real
   conflict: REQ-CLIENT-018 (feature 026) forbids ever exposing the internal Morning `client_id` to
   the model at all, specifically because the model has been observed relaying tool output verbatim
   into user-facing replies — adding `client_id` as a tool parameter would be the first time ever
   that ID reaches the model's context, reopening exactly the leak REQ-CLIENT-018 exists to prevent.
   Surfaced this tradeoff explicitly; user's decision: **keep the refuse-then-reask-by-name mechanism
   exactly as implemented in round 1** (no `client_id` parameter, no REQ-CLIENT-018 change) — the
   real gap was that nothing told the *model* this is a continuing conversation rather than a dead
   end. Fixed by adding an explicit rule to `runtime_constitution.md`'s Invoice Management section:
   a "מצאתי לקוח בשם X - האם לזה התכוונת?" reply must be relayed as a question, and on "כן" the model
   must retry the same document-creation request with the confirmed exact name — mirroring the
   existing not-found/ambiguous instructions already there, which had this exact same "retry, don't
   give up" framing but never got extended to cover the new non-exact-match case. Same rule applies
   to `list_invoices`.
2. **The T1/T2 billed-test seed cost.** The user asked to source the "already exists" client from
   an existing Morning client instead of a fresh `add_client` conversation per run (fewer OpenAI
   calls). Clarified that `list_clients` (an MCP tool, reached the same way as every other tool)
   does NOT actually cross the app-wall — the wall is about denidin-app test *code* never importing
   `MorningClient`/hitting Morning's REST API directly, and `list_clients` is just another
   conversational tool call, same as `get_client_details` already used by
   `_fresh_nonexistent_client_name`. But a *different* problem remained even so: an untargeted
   `list_clients` lookup doesn't let you control which real client comes back, so there's no safe
   way to guarantee the single-letter-edit relationship T1/T2 need without colliding with some
   unrelated real client's similar spelling. Given that, user's decision: **use the one-time
   permanent-fixture approach** (same established pattern as bugfix-014's `דורית אשכנזי`) — two new
   ground-truth clients, `זהבית צור` (T1) and `כרמלי דודי` (T2), seeded once, ever, referenced by
   hardcoded exact name from then on, zero seeding OpenAI calls on every subsequent run. Both
   fixtures' "anchor" word (`זהבית`/`כרמלי`) is verified absent from `_unique_client_name()`'s random
   pool, so no randomly-generated test client can ever collide with either one regardless of the
   *other* (deliberately real, pool-member) word in the pair. Per the user's explicit follow-up ask
   ("I need a list of all these 'permanent' clients that we depend on"), also wrote
   `apps/denidin-app/tests/billed/GROUND_TRUTH_CLIENTS.md` — a full registry of every such fixture
   this suite depends on (including the two pre-existing ones, `דורית אשכנזי` and the invoice-lifecycle
   test's `Test Client DENIDIN_TEST_1770474207`, plus the retired `יוסי שמואלי`), so a future sandbox
   wipe/reset has a documented recreation path instead of silent test breakage.

**Not yet done — needs explicit go-ahead before it can be true**: `זהבית צור` and `כרמלי דודי` do
not exist in the sandbox yet. T1/T2 will fail on a genuine (correct, expected) "client not found"
until they're seeded — see `GROUND_TRUTH_CLIENTS.md`'s "(Re)seeding" section for the exact one-time
step. This is a real mutating write against the sandbox and, per standing practice, needs the user's
explicit go-ahead before it's actually run — not done as part of this round.

A useful side effect of dropping the per-run seed: the T1/T2 conversation no longer has an
`add_client` turn immediately before the ask, so the real client name never appears as recent
context the model could "already know" and self-correct from — the caveat in round 1's point 9
above (billed tests couldn't reliably force the refuse-then-reask branch specifically) should be
meaningfully less likely now, though this hasn't been re-verified against a live run yet (blocked on
the seeding step above).

**Seeding done (2026-08-11), `update_client` also brought into line (2026-08-11)**: both new
ground-truth clients seeded directly against the sandbox (`MorningClient`, no OpenAI). Also, per
explicit user decision, `update_client` now shares `_resolve_client_for_document_creation` (given a
`tool_name` param so audit-log refusal entries still say `update_client`, not a misleading
`document_creation`) — same refuse-then-confirm treatment as the three creation tools, same
"Affected Area" entry closed out. Its stale unit test
(`test_update_client_non_exact_match_discloses_resolved_name`, asserting the old
create-then-disclose phrasing) and sandbox integration test
(`test_update_client_tool_discloses_non_exact_match`) were rewritten to assert the new
refuse/confirm/nothing-mutated shape, plus a new sandbox test for the confirmed-retry half of the
flow. `morning-mcp-app` unit: 243/243. `morning-mcp-app` integration: individually, all update_client
tests pass (verified file-by-file); a **full** `tests/unit/ + tests/integration/` run in one go hit a
bare `403 Forbidden` at `/api/v1/account/token` partway through (20 failures, all after the block
started) — the same external, self-clearing sandbox rate-limit class documented in round 1 point 8
above, not a regression (confirmed: the exact same tests pass individually before/after the run that
triggered it). Still blocked as of this note; needs a wait-and-retry, not a code fix, per that same
precedent.

---

## Session Handoff (2026-08-11, round 3) — read this first, this is the freshest state

**TL;DR**: mid-round-3, user asked to stop and hand off cleanly rather than continue verifying.
Round 3 is a full rewrite of the resolution algorithm itself (word-order independence, deterministic
letter-by-letter matching, Levenshtein-ordered candidates), driven by the user directly specifying
the algorithm step by step after a real production-shaped bug was caught mid-session. Core
implementation is done and unit-tested (243/243); one real-sandbox test file is fully green (7/7);
three more sandbox integration files still need verifying (blocked earlier by an external rate limit
that **has since cleared** — confirmed reachable again as of this note, not yet re-tested); the
original 82-test denidin-app billed sweep (from the "investigate the bug" thread) never resumed past
test #20, the very test that led to finding this whole round-3 rewrite was needed.

### The story, in order

1. **Round 1/2 recap**: see the two handoff sections above — `list_invoices`/create-tools/`update_client`
   got a "resolve, then confirm-if-not-exact" treatment using `_resolve_client_by_name_words` (per-word
   intersection) + `_search_word_with_truncation` (full word, truncate-on-failure).
2. **User asked to resume the interrupted 82-test denidin-app billed sweep** ("wait... poll every
   minute. continue only integration tests that failed... after integration testing is all green -
   run morning billed, denidin unit+integration, ALL denidin billed ONE BY ONE, stop on fail"). Did
   exactly that: morning-mcp-app integration/unit/billed all verified green, denidin-app
   unit+integration 762/762, then started the billed sweep. **Test #20 of 87** (not 82 — an earlier
   miscount in this same sweep, corrected mid-sweep — see the sweep's own transcript if picking this
   up from chat history) — `test_receipt_request_with_exact_invoice_amount_resolves_correctly` —
   FAILED. Per standing instruction ("stop on fail means stop"), the sweep halted there and has
   **not resumed since**.
3. **Root cause investigated** (user said "investigate"): `list_invoices`'s multi-word branch called
   `_resolve_client_by_name_words` **unconditionally**, without ever trying the direct whole-string
   search first — so *any* multi-word query, even a perfectly exact one, got treated as non-exact and
   got an endless "did you mean X?" loop (the model kept re-asking an already-answered question,
   never reaching `create_receipt`). Confirmed via two real client names from the failing test's own
   output: `מרסל אלמו` and `עובדיה פרלמן` — both exact, both got the confirmation loop.
4. **User rejected the proposed minimal patch and instead specified the real algorithm directly**,
   step by step (verbatim, paraphrased slightly for flow): loop over query words one at a time; within
   each word, grow the prefix letter by letter; if a *single* candidate is returned, check the FULL
   word matches AND all other words match exactly — if so, exact match; if more than one is returned,
   keep growing; zero at any point means no exact match via this path; word exhausted with >1 still
   left means move to the next word; exhausting all words means no exact match. Emphasized this
   mirrors what a human does searching Morning's own UI, and is deterministic, not a guess.
5. **Several rounds of clarification, each catching a real design flaw before any code was touched**:
   - User: don't touch code yet — build a **standalone prototype** with a fake in-memory client list
     first, and "unit test the hell out of it until satisfaction."
   - First prototype draft had "Phase A" (exactness) and "Phase B" (discovery) as two **separate
     sequential sweeps** over the word list. User: **"There is a single pass. SINGLE PHASE."**
     Rewritten into one `for word in words:` loop that does both jobs per word, same iteration.
   - First discovery draft used the OLD `_search_word_with_truncation` shape (full word, truncate on
     failure) as a second mechanism. User: **"why 2 mechanisms?? DO NOT DIVERGE!"** — growth-with-
     early-stop alone already covers both directions (it never needs to overshoot into a 0-match
     prefix, because it stops the moment a shorter real word already makes it unique) — truncation
     was solving a problem that doesn't exist. Removed entirely, one mechanism only.
   - User clarified discovery must search **every query word fully independently**, unconstrained by
     the others (a "David Abu Zikri" vs. lookalike "Vavid Babu Zikri" example: the lookalike shares
     NOTHING with "David"/"Abu", only "Zikri" — searched on its own — can ever surface it), AND must
     not require per-word uniqueness (if one word alone matches multiple candidates, all belong in the
     list, not just a unique one).
   - Confirmed explicitly: **the candidate list is never relevance-filtered** — independent per-word
     discovery surfacing an "unrelated" candidate that only shares one common word with the query is
     intentional, demonstrated live with the real Hebrew patronymic/surname-prefix concern (בן/כהן/לוי,
     first names like דוד) as a known-but-deferred future refinement... **then, later in round 3, this
     got un-deferred** (see optimizations below) once it started breaking real sandbox tests sooner
     than expected.
   - Step 0 (whole-string fast path) and Step Final (post-loop fresh-data re-confirmation) confirmed
     as simple one-shot checks bookending the real loop, not "phases" themselves.
   - Final ask: **order candidates by Levenshtein distance to the query** (closest first) so a long,
     unfiltered list still shows the most plausible read on top.
6. **Prototype built and proven**, now committed under `specs/bugfixes/bugfix-039-artifacts/`
   (moved there from session scratchpad specifically so it survives into a fresh session — scratchpad
   is per-session and would otherwise have been unreachable):
   `client_resolution_prototype.py` (the algorithm),
   `test_client_resolution_prototype.py` (25 hand-picked adversarial cases — word-order independence,
   false-early-unique-prefix traps, discoverability-via-one-word-only, genuine ambiguity, not-found,
   repeated words, dedup), `show_test_table.py` (built a rich, all-Hebrew ground-truth fixture per
   user request — **real names from today's actual production incident and today's actual billed-test
   failure**, not invented ones: `דודי אדלר`/`דוד אדלר` (the literal 2026-08-10 incident), `זהבית
   צור`/`כרמלי דודי` (the live sandbox ground-truth clients), `מרסל אלמו`/`עובדיה פרלמן` (today's
   billed-test failure's own client names) — plus 300 realistic random-noise clients drawn from the
   app's own `hebrew_first_names.txt`/`hebrew_family_names.txt` pool, all coexisting in ONE unified
   fixture (an earlier per-test-curated-fixture draft was rejected by the user as unrealistic — a real
   Morning account is one single database every query hits, not a hand-picked subset per test). All
   25 unit tests + the full Hebrew table passed before any real code was touched.
7. **Real implementation** in `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` (see "Affected
   Area" above for the exact function list) — `resolve_client_by_name` is now THE one client-name
   mechanism, wired into `list_invoices` (the actual bug fix: an exact match now resolves and the
   search proceeds, instead of always asking), `_resolve_client_for_document_creation` (covers
   create_invoice/create_transaction_account/create_combo_document/update_client), and
   `get_client_details` (newly covered by multi-word matching for the first time — it only ever had
   the plain whole-string search before).
8. **A real bug the prototype never caught, only found testing against the live sandbox**: `_grow_word`
   was re-intersecting each letter's search results against its OWN previous letter's results, not
   just the externally-passed pool. Harmless against the prototype's `FakeMorning` (which returns
   complete, unpaginated results), but the real Morning `/clients/search` paginates (confirmed live:
   25 items/page even when the true total is in the thousands — `"Test"` alone matched 1,460 real
   clients in the sandbox from months of accumulated test fixtures) — so an earlier letter's own
   returned page was an arbitrary, incomplete sample, and filtering a later, more specific letter's
   real results against that incomplete sample silently dropped genuine candidates, including, in one
   directly-reproduced case, the actual freshly-seeded target client itself. Fixed: every letter now
   filters against the one original external pool, never a self-accumulated running set.
9. **Two further optimizations, user-specified, applied together with the bug fix**:
   - Start growth at 2 letters, not 1 (a single letter always matches too broadly to narrow anything
     — real sandbox observed: `"D"` alone → 1,479 matches — pure wasted call); a query word shorter
     than 2 letters is skipped entirely, for both the intersecting chain and discovery.
   - **The deferred common-word concern from point 5 got un-deferred**: if a word, grown to its FULL
     length, still matches more than `_COMMON_WORD_DISCOVERY_CAP` (=10) real clients, none of its
     matches are added as discovery candidates — a deterministic threshold (not relevance scoring),
     specifically to stop generic Hebrew name-parts (patronymic "בן", common surnames "כהן"/"לוי",
     common first names "דוד") and this test suite's own accumulated "Test"/"Client" filler words
     from flooding the candidate list. Applies ONLY to discovery — the intersecting exactness chain
     still uses every word normally, since a common word CAN still correctly narrow to a genuine exact
     match once combined with another word (e.g. "בן" + "גוריון").
10. **Verification so far**: `morning-mcp-app` unit 243/243 (no regressions). Real sandbox
    `test_morning_sandbox_create_invoice_client_resolution.py`: **7/7 green**, including the two
    tests that were failing purely from "Test"/"Client" word-noise before the >10 cap was added.
    `test_client_resolution_prototype.py`: 25/25 (updated to match the final bug-fixed/optimized
    algorithm). Then hit the SAME external rate-limit class as round 2 (bare 403 on
    `/api/v1/account/token`/`/api/v1/clients`) while starting to verify
    `test_morning_sandbox_get_client_details_tool.py` +
    `test_morning_sandbox_list_invoices_tool.py` + `test_morning_sandbox_update_client_tool.py`
    together — **confirmed cleared again as of this note** (polled every 60s, cleared on the 3rd
    attempt), but those three files have NOT been re-run since the clear.

### Explicit next steps for whoever picks this up

1. **Re-run the three not-yet-verified sandbox integration files** (rate limit is clear as of this
   note, but confirm again before running — it could recur):
   `test_morning_sandbox_get_client_details_tool.py`,
   `test_morning_sandbox_list_invoices_tool.py`,
   `test_morning_sandbox_update_client_tool.py`. Expect the SAME class of stale-assumption failures
   already fixed once in `test_morning_sandbox_create_invoice_client_resolution.py` this round (tests
   asserting a clean single/zero candidate result that will now legitimately include extra noise
   candidates unless the >10 cap already filters them, or tests whose premise silently changed because
   `list_invoices`/`get_client_details` no longer behave the old way) — investigate each on its own
   merits, don't assume they're all the same fix.
2. **`get_client_details`'s own sandbox test file has never been checked against the round-3
   algorithm at all** — this tool's resolution changed for the first time in round 3 (previously
   whole-string-only, no multi-word fallback whatsoever), so this is the least-proven of the three.
3. Run the full `tests/unit/ + tests/integration/` combined suite once all three files above are
   individually green, to catch anything cross-file.
4. Re-run the 5 `morning-mcp-app` billed tests (last verified green BEFORE round 3's tools.py
   rewrite — should still pass since the model-facing contract/message shapes are unchanged, but
   hasn't been confirmed against the new implementation).
5. **Resume the original 82-test denidin-app billed sweep from test #21**
   (`test_receipt_request_for_already_paid_invoice_handled_sensibly`, in
   `test_denidin_morning_document_creation_e2e.py`) — test #20 is the one whose investigation led to
   this entire round-3 rewrite; it has not been re-run since the fix. Consider re-running #20 itself
   first (not previously reached OpenAI in a way that used the fixed code) to directly confirm the
   original failure is resolved before continuing past it. Per standing "stop on fail" instruction:
   every failure from here is its own stop point, full report, wait for explicit direction — no
   fix-and-continue, no matter how similar to something already fixed this round.
6. Consider adding **dedicated unit tests for `resolve_client_by_name` directly** (currently only
   exercised indirectly through its callers' existing tests, all of which still pass, but there's no
   unit-level test of the new function's own contract the way `test_tools_client_resolution.py` had
   for the old `_resolve_client_for_document_creation`/`_resolve_client_by_name_words`) — not done
   yet, the prototype's 25 tests are the closest thing that exists, but they test the prototype, not
   the real `tools.py` code.
7. Decide whether to delete the now-fully-dead `_is_exact_name_match` (still has its own passing unit
   tests, called by nothing) — left in deliberately this round to avoid touching tests without
   sign-off; not resolved either way.
8. Once everything above is green, this still needs the full haleluya treatment (spec status/PR-number
   update, one commit, push, PR, merge) — **do not run it without the user explicitly saying so**.
9. CLAUDE.md's unrelated pending diff (prod data/log access quick-reference) — round 2 decision was
   to ride it along in the same PR; still applies, nothing further needed on it.

---

## Original root cause (2026-08-10 writeup, kept for the record)

### Live incident, 2026-08-10 ~07:54 Israel time (req_e27446592a99, req_953c605962c7, req_7e53824b6d74)
An admin asked DeniDin to verify an invoice had been issued for **דוד אדלר**, ₪5,000:
```
07:54:34  MCP calls: [{'name': 'list_invoices', 'arguments': '{"client_name":"דוד אדלר"}',
                       'output': 'לא נמצאו חשבוניות התואמות את החיפוש.'}]
          → DENIDIN: "לא נמצאה במערכת חשבונית מס/קבלה עבור דוד אדלר בסך 5,000 ₪."
07:55:28  MCP calls: [{'name': 'list_invoices',
                       'arguments': '{"client_name":"דוד אדלר","from_date":"2026-08-10",...}',
                       'output': 'לא נמצאו חשבוניות התואמות את החיפוש.'}]
          → DENIDIN: "חיפשתי שוב... ולא נמצאה חשבונית..." (fabricated extra confidence — it was
             the same failing filter, just with a date range added)
07:55:59  MCP calls: [{'name': 'list_invoices',
                       'arguments': '{"from_date":"2026-08-10","to_date":"2026-08-10"}',  ← no
                       client_name filter at all
                       'output': 'נמצאו 1 חשבוניות:\n\nחשבונית #112301\nלקוח: "דודי אדלר"...'}]
          → DENIDIN: "...זו הייתה טעות שלי... במערכת רשומה תחת 'דודי אדלר'..."
```
The invoice was real, paid, dated today, ₪5,000 — and existed the whole time. It was only found
once the model gave up on the `client_name` filter entirely and scanned the full day's documents
by eye. Two authoritative-sounding "not found" answers were given to an admin about a real
financial record before that happened.

### Root cause
`_map_list_invoices_filters` (`tools.py`) forwards `client_name` **raw** as Morning's `clientName`
search param:
```python
if client_name:
    params["clientName"] = client_name
```
Every other tool that accepts a free-text client name resolves it first via
`_resolve_client_by_name` (`create_invoice`, `create_transaction_account`,
`create_combo_document` via `_resolve_client_for_document_creation`; `get_client_details`,
`update_client` directly). `list_invoices` is the one exception — confirmed by reading every
client-name-accepting function in `tools.py`; `create_credit_note`/`create_receipt`/
`close_transaction_account` don't take a name at all (they inherit the client from the original
document), and `get_invoice_details`/`update_invoice_status`/`download_invoice_pdf` are keyed by
`invoice_id`, not name.

**This was already investigated once, in Feature 031 (`specs/done/v0.0.1/031-fuzzy-client-lookup-by-name/`),
and closed 2026-07-30 with "no code change needed."** That closure is the reason this bug had sat
live in production for over a week — and it rested on an **incomplete confirmation**:

Feature 031's research (`research.md` Decision 1) probed Morning's `/documents/search` `clientName`
param with **six single-token substrings of one exact stored name** ("Yossi", "Cohen", "Ltd", a
unique marker, a lowercase variant) — all six matched, correctly establishing that the param does
case-insensitive substring matching. But **none of the six probes were multi-word queries, and
none used a word that was a spelling/nickname *variant* rather than a literal substring of the
stored name.** That is exactly the real query shape from the incident: `"דוד אדלר"` (two words)
against stored `"דודי אדלר"`. Each word individually *would* substring-match (`"דוד"` is literally
a substring of `"דודי"`; `"אדלר"` is exact) — but the two-word query string `"דוד אדלר"` (with a
space) is **not** a contiguous substring of `"דודי אדלר"`, because `"דוד"` is followed by `"י"` in
the stored name, not a space. Feature 031 never tested this, because every one of its probes
queried a single already-correct substring of the one target name.

*(Note, added 2026-08-11: the original writeup here went on to claim `_resolve_client_by_name`
"doesn't have this gap" — that claim was never actually verified and turned out to be wrong; see
"Session Handoff" point 2 above.)*

### Why this matters beyond the original incident
`list_invoices` is the single most commonly exercised read path — "was this invoiced?" is the
natural follow-up to every payment. Any two-word name where the caller doesn't have the exact
stored spelling (nicknames, transliteration variants, a client renamed since) reproduces this — and
the same underlying gap turned out to affect document creation too (see "Session Handoff").

## Expected (as actually implemented)
- ✅ `list_invoices`' multi-word `client_name` queries resolve through `_resolve_client_by_name_words`
  (per-word + truncation matching) when the direct whole-string search finds nothing; single-word
  queries are left as plain substring search (unchanged, deliberately — see point 2 above).
- ✅ A multi-word query resolving to exactly one non-exact real client returns a closed yes/no
  confirmation question naming that client — never silently searches under the guessed name, never
  silently says "not found."
- ✅ A multi-word query resolving to more than one candidate returns the existing disambiguation
  refusal (unchanged).
- ✅ The same treatment now applies to `create_invoice`/`create_transaction_account`/
  `create_combo_document`: a non-exact single match refuses with the confirmation question and
  creates nothing (previously: created immediately, disclosed only afterward).
- ✅ Feature 031's `research.md` Decision 1 gap is now documented here (see note above) rather than
  edited in place — `specs/done/v0.0.1/031-fuzzy-client-lookup-by-name/` itself was left untouched
  (historical record of what was actually tested at the time).
- ✅ `runtime_constitution.md` now explicitly instructs the model that a non-exact-match confirmation
  question is a continuing conversation (relay it, wait for "כן", retry with the confirmed exact
  name) — not a dead end (round 2, user review).
- ✅ T1/T2 (`test_create_document_t1_...`/`test_create_document_t2_...`) now reference permanent
  ground-truth clients instead of seeding fresh per run — see `GROUND_TRUTH_CLIENTS.md` (round 2,
  user review). ⏸️ The two new fixtures themselves still need to actually be seeded in the sandbox
  (pending explicit go-ahead) before these two tests can pass again.
- ⏸️ Renaming `list_invoices` → `list_docs` (it returns all document types, not just invoices) —
  raised by the user as a related polish item, not blocking, not done.
- ⏸️ `update_client` bringing into line — see "Affected Area" / "Explicit next steps" above.

## Related Work
- `specs/done/v0.0.1/031-fuzzy-client-lookup-by-name/` — the feature whose incomplete confirmation left
  this open; this bugfix effectively reopens its core question with cases its probes didn't cover.
- `specs/done/v0.4.1/bugfix-028-invoicing-and-approval-gate-p0-cluster.md` B4 — the
  creation-tool-side client-matching defect (word-prefix matching rejecting a valid search-tool
  output); different code path, same root category (client-name matching isn't robust enough). B1
  (closed-question phrasing to avoid parser misses) directly informed this fix's confirmation
  question wording.
- `specs/bugfixes/bugfix-029-conversation-quality-p1-cluster.md` P1-2 — the same "confident wrong
  answer, corrected only after user pushback" shape, different underlying mechanism.
- The same original production turn also surfaced an unrelated, already-tracked defect (bugfix-028
  B5 / bugfix-034 L3: a separate combo-document request in the same conversation window produced a
  silently-empty reply) — not part of this bug; noted only because it's the same admin, same
  session, same morning.
- **Independently rediscovered during this bug's own final billed-test verification (2026-08-12)**:
  `test_godfather_updates_client_via_whatsapp` failed because the model called `update_client` with
  a wrong MCP parameter name (`new_phone` instead of `phone` — plausibly primed by the tool's own
  inconsistent schema, where `new_name` is the only field carrying a `new_` prefix), the call
  silently failed, the model self-corrected with a second, differently-approved call in the same
  turn, but the user-facing confirmation text gave no indication anything had failed — the exact
  same shape as bugfix-028's B5 ("non-empty reply that says nothing about a real failure"). Root
  cause traced further: **bugfix-028's actual code fix (including B5's guard) was never merged to
  master** — only its spec/docs were (PR #208, "specs only"); the real fix commits
  (`dcbde7e`/`ee574b3`) exist only on the still-open `bugfix/028-invoicing-and-approval-gate-p0-cluster`
  branch, which has no PR at all. Per explicit user decision, this finding is logged here for the
  record rather than spun into a new bugfix spec — out of this bug's scope (client-name resolution,
  not general tool-failure disclosure) — but the next time anyone picks up bugfix-028, this is a
  second, independent confirmation that its B5 fix is worth landing.
