# Feature 069 — test-helper purge & consolidation (2026-09-10)

Directive: **use existing helpers as much as possible**; every *new* test helper
needs explicit approval. This is the record of what was removed, what replaced
it, and every test file that had to adapt (for the re-run / review pass).

All changes are test-only. `src/` untouched. Verified: full `pytest --collect-only`
clean (1468 collected, 0 errors); `tests/unit/` + media/reminder integration =
1402 passed; `tests/integration/test_ledger_client_resolution_routing.py` = 18/19
(the 1 fail, `test_us2_morning_create_captured_that_turn_from_tool_result`, is the
pre-existing US2 synchronous-חשבונית schema gap tracked in
`HANDOFF-2026-09-07-us2-and-morning-fulldoc.md` — a `src` persist refusal, not
helper plumbing; the other 18 share the same rewritten cleanup fixture).

---

## a. Helpers removed → what is used instead

| # | Removed | Lived in | Now uses |
|---|---------|----------|----------|
| 1 | `_check_generated(field, value, kind, ev, *, trigger_epoch, session_id)` | `tests/billed/_ledger_069_acceptance.py` | Inlined into `_check_field`'s `"generated"` branch (same per-kind rules, one fewer function + signature). |
| 2 | `reset_chat_session(session_manager, chat_id)` | `tests/e2e_helpers.py` | **New** `wipe_chat_messages_on_disk(sessions_storage_dir, chat_id)` — pure filesystem: resolve `chat → session_id` via the SQLite chat index (`chat_index.db`), delete that session's `messages/` + `archived/` JSON, rewrite the 4 bookkeeping fields in `session.json`. **No `SessionManager` call, no live-object mutation, no `_save_session`.** `SessionManager._load_session` re-reads `session.json` per `get_session`, so the next turn sees the emptied session. ⚠️ **new helper — see "New helpers" below.** |
| 3 | 2nd copy of `create_real_notification` + `get_response` (incl. the inline `track_answer_with_interactive_buttons`) | `tests/billed/denidin_mcp_e2e_helpers.py` | The single implementation in `tests/e2e_helpers.py`, re-imported at the top of `denidin_mcp_e2e_helpers.py` (that stub already dual-writes the Feature-047 button body into `_test_sent_messages`). Also dropped the now-unused `SimpleNamespace` import there. |
| 4 / 10 | `ledger_events_for_chat(denidin_app, chat_id)` **and** `events_reader(denidin_app)` (069) + `_events_for_chat` staticmethod × 3 (pre-069, byte-identical) | `_ledger_069_acceptance.py`, `_ledger_069_post_turn_base.py`, `test_ledger_event_capture_billed.py`, `test_ledger_event_capture_text_billed.py`, `test_ledger_event_capture_e2e.py` | **One** reader: `tests/e2e_helpers.py::persisted_ledger_events_for_chat(denidin_app, chat_id)` (moved the 069 body — tolerant sort `(captured_at, event_id)` — into the shared module). The 3 staticmethods become `_events_for_chat = staticmethod(persisted_ledger_events_for_chat)` (name kept so their call-sites don't move). `_ledger_069_post_turn_base` keeps a 1-line `_events_for(denidin_app)` closure only because `converse_until_ledger_events_captured` wants a `callable(chat_id)`. |
| 6 | `assert_ledger_event_matches_manifest_two_hop(extractor_output, persisted_events, manifest, …)` | `_ledger_069_acceptance.py` | Folded into `assert_ledger_event_matches_manifest(…, extractor_output=None)` — pass `extractor_output=` and it runs Hop 1 (OCR carried every `tested` value) first, then the existing per-field check. Hop-1 logic kept as private `_assert_extractor_carried_tested_values`. |
| 9 | `_geresh_normalise` + `_GERESH` / `_APOSTROPHES` / `_BIDI_CONTROLS`; `_norm_date`; `_norm_percent` | `_ledger_069_acceptance.py` | `_normalize_hebrew_geresh` in `denidin_mcp_e2e_helpers.py` — **enhanced** to be the one canonical name-compare normaliser: `None`-safe + NFC + strips bidi/format controls, on top of its existing apostrophe→geresh (strictly-additive; the 4 other billed Morning suites that use it compare ASCII-apostrophe names, unaffected). `_norm_date`/`_norm_percent` collapsed into branches of the single `_norm_field`. `_norm` (whitespace/number canonicalisation) kept — no pre-existing equivalent. |

### Not removed (with reasons)
- `_component_discriminator` / `_match_component` (`_ledger_069_acceptance.py`) — you confirmed keep (#7, #8). An agreement persists one file per fee tier; these match a persisted file to its manifest component.
- `drive_capture_conversation` / `drive_capture_from_image` (`_ledger_069_post_turn_base.py`) — thin `(events, transcript, event_epoch)` wrappers over the one shared `converse_until_ledger_events_captured`. `drive_capture_from_image` is **new this feature** (Phase 1) — see below.
- `converse_until_ledger_events_captured` (`tests/e2e_helpers.py`) — the shared multi-turn driver; extended (not duplicated) with `pre_sent_first_turn=` for the media case, replacing the deleted `_run_detour_until_captured` reinvention.
- Local `track_answer_with_interactive_buttons` nested defs in `test_reminder_conversation_routing.py` + `test_reminder_lifecycle_billed.py` — a separate, older duplication (reminder feature, not 069). Out of this scope; flagged as a follow-up candidate.

---

## New helpers introduced (need your sign-off)

1. **`wipe_chat_messages_on_disk(sessions_storage_dir, chat_id)`** — `tests/e2e_helpers.py`.
   The mandated from-the-outside replacement for `reset_chat_session` (your #2/#5:
   "you write the TEST code that cleans up … DONT USE DENIDIN FOR THAT"). Filesystem
   + a read of the `chat_index.db` SQLite file only. Callers pass the sessions root
   as `denidin_app.ai_handler.session_manager.storage_dir` (a read-only `.storage_dir`
   attribute lookup — same read-only pattern as `persisted_ledger_events_for_chat`;
   no method call, no mutation).
2. **`persisted_ledger_events_for_chat(denidin_app, chat_id)`** — `tests/e2e_helpers.py`.
   Not really new — the surviving copy of 5 identical readers, relocated to the
   shared module and renamed (your #10 said remove the *name* `ledger_events_for_chat`).
3. **`drive_capture_from_image(...)`** — `tests/billed/_ledger_069_post_turn_base.py`
   (added in Phase 1, before this message). 15-line wrapper mirroring the existing
   `drive_capture_conversation`, for the media tests whose turn 1 is an image the
   caller already sent. If you'd rather the 5 media tests call
   `converse_until_ledger_events_captured` directly, I'll inline it.
4. **`converse_until_ledger_events_captured(..., pre_sent_first_turn=...)`** — new
   optional param on the existing shared driver (Phase 1), not a new function.

Still **not done, needs your call** (your list #2/#5 said remove the autouse
fixture entirely): `clean_069_chat_history` still exists as an autouse fixture in
`_ledger_069_post_turn_base.py` — but it now calls only `wipe_chat_messages_on_disk`
(filesystem). If you want it gone as a *fixture* (inlined per-test), say so.

---

## b. Tests that had to adapt

### Helper modules (no tests, but imported everywhere)
| File | Change |
|---|---|
| `tests/e2e_helpers.py` | `reset_chat_session` → `wipe_chat_messages_on_disk`; added `persisted_ledger_events_for_chat`; (`converse_until_ledger_events_captured` + `create_real_notification` button support were Phase 1). |
| `tests/billed/_ledger_069_acceptance.py` | `_check_generated` inlined; `_two_hop` folded into `extractor_output=` param; `_geresh_normalise`/`_norm_date`/`_norm_percent` removed; `ledger_events_for_chat` removed; imports `_normalize_hebrew_geresh` + `persisted_ledger_events_for_chat`. |
| `tests/billed/_ledger_069_post_turn_base.py` | `reset_069_chat` → `clean_069_chat_history` (filesystem cleanup); `events_reader` → 1-line `_events_for` closure over the shared reader; drop `_ledger_069_acceptance` import. |
| `tests/billed/denidin_mcp_e2e_helpers.py` | `create_real_notification`/`get_response` now re-imported from `e2e_helpers`; `_normalize_hebrew_geresh` enhanced (None/NFC/bidi); `SimpleNamespace` import dropped; `import unicodedata` added. |

### Test files
| File | Tier | Adaptation |
|---|---|---|
| `tests/billed/test_e2e_ledger_069_text_billed.py` | billed | `reset_069_chat` → `clean_069_chat_history` import. |
| `tests/billed/test_e2e_ledger_069_docx_billed.py` | billed | fixture rename; `assert_..._two_hop(...)` → `assert_ledger_event_matches_manifest(events, manifest, …, extractor_output=extractor_output)`; `ledger_events_for_chat` → `persisted_ledger_events_for_chat` (import + 2 call-sites). Test name `test_us10_..._two_hop` left as-is (immutable). |
| `tests/billed/test_e2e_ledger_069_morning_create_billed.py` | billed | fixture rename; reader import + 1 call-site swapped. |
| `tests/billed/test_ledger_event_capture_billed.py` | billed (pre-069) | `_events_for_chat` staticmethod body → `staticmethod(persisted_ledger_events_for_chat)`; import added. |
| `tests/billed/test_ledger_event_capture_text_billed.py` | billed (pre-069) | same as above. |
| `tests/expensive/test_ledger_event_capture_e2e.py` | expensive (pre-069) | same reader swap; `reset_chat_session` → `wipe_chat_messages_on_disk` in the cleanup helper. |
| `tests/expensive/test_e2e_media_client_resolution.py` | expensive | `reset_chat_session` → `wipe_chat_messages_on_disk` in `_clean_ledger`; 5× `assert_..._two_hop(...)` → `assert_ledger_event_matches_manifest(..., extractor_output=...)`; drop `ledger_events_for_chat` import. |
| `tests/expensive/test_group_b_reference_approval_e2e.py` | expensive (pre-069) | `reset_chat_session` → `wipe_chat_messages_on_disk` in the per-test cleanup. |
| `tests/integration/test_ledger_client_resolution_routing.py` | integration | `reset_chat_session` → `wipe_chat_messages_on_disk` (module import + `_clean_state` fixture). |

### Fixture data
| File | Change |
|---|---|
| `tests/fixtures/ledger_069/deposit_exact_match.manifest.json` | US7d: per the manifest's own `_incomplete` instruction, filled `bank_number`/`bank_branch`/`bank_account` from the extractor's legible read on the 2026-09-07 run (`31` / `109` / `105542585`). `reference` stays null (model renders `3263` into the free-text description, not the field). Renamed the note `_incomplete` → `_transcription_note`. |

---

## Round 2 (2026-09-10, after API-surface review)

| Change | Detail |
|---|---|
| `ResolveClientNameError` deleted | `denidin_mcp_e2e_helpers.py` — `_classify` now raises plain `AssertionError`. No test caught the custom type. (Feature 059 code.) |
| `drive_capture_conversation` + `drive_capture_from_image` → **one `drive_capture`** | `drive_capture(denidin_app, answer_bank, *, id_prefix, first_text=None, image_reply=None, base_ts=None, max_turns=6)` — exactly one of `first_text` / `image_reply` (text turn-1 the driver sends vs. an image turn-1 the caller already sent). They only ever differed by which turn-1 kwarg they passed to `converse_until_ledger_events_captured`. 7 text call-sites + 5 media call-sites updated. |

## Round 3 (2026-09-10) — manifest normalisation + answer bank into the drivers

Every 069 acceptance test is now **seed / drive / assert**, three lines, no answer
bank and no manifest plumbing in the test body.

### Manifests — ONE uniform schema (12 files)
- The 3 non-uniform `client_resolution` shapes → one `resolution: {mode, …}` block.
  Modes: `exact` (name) · `pick_existing` (stated, resolves_to) · `new_client`
  (name, email, phone) · `store_as_stated` (name) · `none` (US2 — approval gate
  only, no client detour).
- `agreement_new_client` split → `agreement_new_client` (US4) + **new**
  `agreement_store_anyway` (US8).
- **new** `morning_create_us2.manifest.json` — replaces the code-built
  `_us2_manifest(amount=…)` in `test_e2e_ledger_069_morning_create_billed.py`.
- Every `client_name` rule → `{"tested": "$client"}`. `$client` resolves via
  `resolved_client_name_from(manifest)` (mode → name / resolves_to).
- `$unique` / `$email` sentinels (US2/US4/US8) — bound **once per test** to a
  minted real name / ASCII email in `load_manifest` (memoised; autouse fixture
  clears via `reset_manifest_cache`). One `$unique` shared by `resolution.*` +
  every `seed_clients` entry.
- `seed_clients` (with `phone`) added to the fixed-name manifests
  (`agreement_us1`, `agreement_us6`, `deposit_exact_match`, `morning_create_us2`).
- Cruft stripped: `client_resolution`, `_incomplete`, `scenario`,
  `operator_picks`, `operator_stated_name`, `morning_name_after_resolution`.

### Helpers
| Change | Detail |
|---|---|
| `load_manifest(name)` memoised + sentinel-binding | `_MANIFEST_CACHE`; `reset_manifest_cache()` hook called by the `clean_069_chat_history` autouse fixture. |
| `resolution_answer_bank` → **private** `_new_client_answer_bank` | plus new `_answer_bank_for(resolution)` — builds the generic-flow bank from `resolution.mode`. Called inside `drive_capture`; tests never see it. |
| `assert_ledger_event_matches_manifest` signature | now `(denidin_app, events, manifest_name, trigger_epoch)` — derives `session_id`, `$client`, and (media `source_kind`) the Hop-1 extractor output itself. Dropped `session_id` / `resolved_client_name` / `extractor_output` params. |
| `_extractor_output_for_chat` | one copy in `_ledger_069_acceptance.py` (was duplicated in the media + docx test files as `_extractor_output_for_chat` / `_docx_stash_text_for_chat`). Auto-runs Hop 1 for `source_kind in {image, document}`. |
| `drive_capture(denidin_app, manifest_name, …)` | was `(denidin_app, answer_bank, …)`. Loads the manifest, builds the bank, and for `mode == "exact"` asserts no detour. |
| new `seed_scenario(denidin_app, manifest_name)` | seeds every `seed_clients` entry; returns the bound manifest. Re-exported from `_ledger_069_post_turn_base`. |

### Test files collapsed
`test_e2e_ledger_069_text_billed.py` (8 tests), `..._docx_billed.py` (US10 — the
inline `_process_media_message` + `while not events` loop folded into
`drive_capture(image_reply=…)`), `..._morning_create_billed.py` (US2),
`tests/expensive/test_e2e_media_client_resolution.py` (US7a–d, US9 — via one
`_run()` seed+image+drive helper). All hand-built `ClarificationAnswerBank`s and
`load_manifest`/`session_id_for_chat`/`resolution_answer_bank` calls removed from
the test bodies.

Verified: `pytest --collect-only` clean (1468 collected, same as baseline);
`tests/unit/` + integration = 1412 passed, 1 failed
(`test_us2_morning_create_captured_that_turn_from_tool_result` — the same
pre-existing US2 `src`-side חשבונית persist refusal, unchanged).

## Suggested next step
Re-run Batch 1 (the 15 billed/expensive 069 acceptance tests) to verify the
normalisation end-to-end. Billed portion is free; expensive portion has your
standing authorization from earlier this session. `scripts/run_parallel_tests.sh`
`-n 6`.
