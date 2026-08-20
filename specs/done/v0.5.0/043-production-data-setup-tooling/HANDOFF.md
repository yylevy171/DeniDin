# Handoff: Feature 043 — WhatsApp Export → Ledger Event "Player"

**Updated**: 2026-08-20 (new session, continuing after PR #232 merged
2026-08-19 — Phases 1–4/9/11 were already live on master when this session
started)
**Branch**: `feature/043-production-data-setup-tooling`

---

## 2026-08-20 (later same day): player idMessage/dedup collision - found and fixed

A second master merge (PR #235, `fa5c974`) landed a `RecentNotificationDeduper`
in `denidin.py` - in-memory, TTL-bounded (600s) de-duplication of incoming
notifications by `idMessage`, checked in `dispatch_notification` before any
handler runs (real dev incident: a Green API webhook redelivery produced two
approval prompts for one reminder). Caught (user's direct question, not
something the earlier impact review found - that review predated this PR)
that this collides badly with the player: `notification_synth.py` built
`idMessage` from a per-call-site sequence number
(`f"player-{idmessage_seq}"`) that `PlayerExportSource.start()` derived via
`enumerate(self._messages, start=1)` - always restarting at 1, since
`_dispatch_with_clarification_loop` constructs a fresh single-message
`PlayerExportSource` for the original dispatch AND every clarification
follow-up round. Net effect: every dispatch in an entire player run got the
identical `idMessage="player-1"` - with the new deduper active, only the
first would ever reach a handler; everything else within the same 10-minute
window would be silently swallowed. Would have collapsed the AHLedger-style
real-export replay from earlier this session to roughly one message
processed per 10 minutes, with no error surfaced.

**Fixed**: `idMessage` is now a real random UUID (`f"player-{uuid.uuid4()}"`),
generated inside `synthesize_notification` itself - `idmessage_seq` removed
entirely from its signature and from `PlayerExportSource.start()`. Verified
directly (not just reasoned about): 5 calls with identical arguments now
produce 5 genuinely distinct `idMessage` values (previously would have been
5 identical `"player-1"`s). 41/41 relevant unit tests + 1111/1111 full
unit+integration suite pass.

**Deferred design note (not implemented, documented in
`notification_synth.py` itself too)**: `ParsedMessage.raw_line_no` is the
real, meaningful position of a message in its source export - in principle
that, not `SessionManager`'s own session-relative `message_counter`, should
drive the persisted `Message.order_num` for a player-replayed message, so a
replayed session's ordering stays traceable back to the original export.
Would need `SessionManager.add_message` to accept an optional `order_num`
override - a bigger change, left for a future session.

## 2026-08-20 session: billed/expensive test staleness sweep + master-merge impact review

Not new feature work — a verification/hardening pass, requested explicitly:
"go over all expensive and billed tests and adapt them to THIS feature's
changes. Make sure assertions are not stale, new fields are asserted on,
etc."

### 1. Billed/expensive test staleness sweep (commit `883195f`)

Swept every file under `tests/billed/` and `tests/expensive/` against Phase
11's real, already-merged schema changes (`ab514c7`/`47f6fdf`/`ba5512f`/
`9f844ad`) — not just the files that happened to already mention them. Found
and fixed real bugs, not cosmetic staleness:

- **`tests/e2e_helpers.py`'s `assert_image_path_persisted`** checked
  `message_data["role"] == "user"` — but `role` is now the real RBAC role
  (`"admin"`/`"godfather"`/`"client"`), never literally `"user"`. This would
  have failed **every** billed/expensive test that calls it (every image/
  media test across 3 files). Fixed to check `ai_required_role` (falling
  back to `role`), matching `SessionManager`'s own switch.
- **`tests/expensive/test_ledger_event_capture_e2e.py`**'s
  `_assert_ledger_events_persisted` still asserted the removed
  `message_timestamp`/`sender` fields instead of `event_datetime` — the
  exact same bug `test_ledger_event_capture_billed.py` already caught and
  fixed on 2026-08-18; this expensive-tier copy was missed at the time.
- **`tests/expensive/test_group_b_reference_approval_e2e.py`** and
  **`tests/billed/test_denidin_vcf_contact_e2e.py`** both filtered
  persisted ledger-event files by `data.get("whatsapp_chat") == chat_id` —
  a field removed from the schema. The condition was silently always
  `False`, so `_clear_chat_test_data` never actually deleted anything
  (defeating cross-run isolation for a fixed, shared chat_id) and
  `_ledger_event_count_for_chat`'s before/after guard was a vacuous
  `0 == 0` pass that could never have caught a real false-positive ledger
  capture. Both fixed to resolve `session_id` instead — verified live via
  direct filesystem check (a mid-test event file, confirmed created via
  code-guaranteed log ordering, was confirmed gone after cleanup ran).

New-field coverage added (Phase 11 fields nothing exercised at the
persisted-record level before): `bank_number`/`bank_branch`/`bank_account`,
forced-null `payer_name`, forced `vat_status="כולל"` on both real
bank-deposit image tests; a new `assert_extracted_text_persisted` helper
wired into the DOCX/PDF expensive tests (closing the coverage gap left by
the real `PDFExtractor`/`DOCXExtractor` `extracted_text` bug Phase 11's
follow-up found and fixed at unit level, but never proved on the live E2E
document path).

**Verified live, not just reasoned about**: all 6 `test_ledger_event_capture_e2e.py`
tests, all 5 `test_media_e2e.py` tests, and 1/2 `test_denidin_vcf_contact_e2e.py`
tests pass (the other's failure — a Thai-text model artifact — and
`test_group_b_reference_approval_e2e.py`'s failure — a pre-existing
`create_receipt` argument-population gap — were both independently confirmed
unrelated to this work via direct log/filesystem inspection, not assumed).

### 2. Master-merge impact review (merge `452e01e`, uncommitted fix below)

Master had moved on significantly (Feature 054 reminders, plus a config fix)
since PR #232. Merged clean (no conflicts) and assessed impact:

- **Feature 054 (reminders)** is structurally isolated from this feature:
  `capture_ledger_event` explicitly bypasses the new `PendingLocalToolApproval`
  gate reminders use ("unlike `capture_ledger_event`, which dispatches
  immediately" — confirmed in code, not assumed). The constitution's Ledger
  Event Recognition section was confirmed to explicitly exclude
  reminder-management messages ("automatically 'Neither'"), matching
  `CLAUDE.md`'s bidirectional-cross-reference mandate. `ReminderManager`
  derives its storage path from `config.data_root` directly (same
  discipline as `LedgerEventManager`), so the player's existing
  `data_root` override already isolates it — no new gap. The reminder
  delivery scheduler is deliberately not started by `initialize_app()`
  (only `__main__`), so neither tests nor the player spawn one.
- **`c375c08`** (master) made `AppConfiguration.max_retries` a real field
  wired into the OpenAI client's own `max_retries=`, replacing a silently-
  dropped config value. Found (not yet fixed at merge time): `player/run_player.py`'s
  `_build_config_dict` hand-builds its returned dict and never included
  `max_retries` — the exact same silent-field-drop shape as the
  `data_root`/`storage_dir` gap this file's own docstring already documents
  fixing once. Invisible today only because the dataclass default (`1`)
  happens to match `config/config.player_prod.json`'s own value (also `1`).
  **Fixed** (uncommitted at merge time, committed this round): added
  `'max_retries': config.max_retries,` to the returned dict. Verified
  directly: `_build_config_dict(...)` → `AppConfiguration(**d)` →
  `.validate()` succeeds with `max_retries == 1`, no longer silently
  defaulted.
- Merge also surfaced 3 new dependencies (`icalendar`, `recurring-ical-events`,
  `APScheduler`) not yet installed in this clone's venv — installed;
  confirmed 1102/1102 unit+integration tests pass post-merge.

### 3. Random-sample live verification (12 tests: 10 billed + 2 expensive)

Using the newly-merged `scripts/run_single_test.sh` (mandatory capture
discipline, per `CLAUDE.md`) — 10 billed + 2 expensive tests chosen randomly
from the full suite (one expensive re-roll, user's choice, after the first
random draw picked an already-known-failing, already-reached-OpenAI test).
**11/12 passed**; the one failure (`test_denidin_morning_document_creation_e2e.py::test_godfather_creates_combo_document_via_whatsapp`)
was a Morning-sandbox test-client-seeding collision (`_seed_fresh_client`
exhausted 5 retry attempts against real pre-existing sandbox clients) —
unrelated to any code in this feature or this session's changes.

---

## What's done (cumulative, all phases — see `tasks.md` for the authoritative task-by-task list)

- **Phases 1–4** (Setup, `MessageSource` abstraction, timestamp fix, US1
  replay-a-date-range) — done. Phase 4 in particular is now genuinely,
  not just nominally, done: the "real run against real data" its
  checkpoint was waiting on has now actually happened twice (the
  33-message pass below, plus today's date-range run against the real,
  fixed player app).
- **Phase 9** (`player/README.md`) — done 2026-08-16, updated again this
  session (new `whatsapp_own_number` config field documented).
- **Phase 11 + Phase 11 follow-up** (ledger schema, 10 player-review
  findings, `raw_message_excerpt`→`Message.extracted_text`) — done,
  commit `9f844ad`.
- **This session** (2026-08-19) — three pieces of work, in order:
  1. Message identity-field redesign (commit `ab514c7`).
  2. A full 33-message live validation run (throwaway, not committed —
     findings written up separately).
  3. Real bugs found and fixed in the *actual* `player/run_player.py`
     itself, plus a new clarification-loop mechanism built into it
     (commit `0f6356b`).
  All three detailed below.
- **NOT started**: Phase 5 (reconciliation), Phase 6 (relevancy), Phase 7
  (review queue), Phase 8 (expensive image-path regression), Phase 10
  (player/WhatsApp equivalence tests — permanently blocked until Feature 040
  lands). See "What's left" at the bottom for what each of these actually is.

## This session's work in detail

### 1. Message identity-field redesign (commit `ab514c7`)

Triggered by the user directly reading persisted JSON during an interactive
player-review session and asking pointed questions ("why is sender not the
whatsapp number?", "where does sender_name come from?", "we don't need
whatsapp_chat, message_id+session_id is enough"). Full design was locked in
via a multi-round clarifying-question exchange before any code was touched.

**`Message` (`session_manager.py`) — every identity field redefined:**
- `role`: now the REAL role — `"admin"`/`"godfather"`/`"client"`/
  `"assistant"` (was the old structural `"user"`/`"assistant"`).
- `ai_required_role` (new): `"user"`/`"assistant"` — separately derived,
  never caller-supplied. This, not `role`, is what
  `get_conversation_history_for_session` puts in the dict handed to
  OpenAI's Responses API (which only accepts literal user/assistant/
  system/developer, never an RBAC role name — a real hard blocker
  discovered mid-design, not guessed at).
- `sender`/`recipient`: now real WhatsApp JIDs (were resolved display
  names). Feature 039's old sentinel-retirement scheme (`recipient=None`
  for a user message, `sender=None` for assistant) is **fully reversed** —
  both are always populated now: DeniDin's own number as `sender` for its
  own replies (reused the *existing* `bugfix-024` mechanism,
  `AIHandler.own_whatsapp_number`, a real `getWaSettings()` Green API call
  at startup), the group's own JID as `recipient` for any group turn
  regardless of who sent it, the other party's real number otherwise.
- `sender_name`/`recipient_name` (new): resolved display names, carrying
  what the old `sender` field used to hold.
- A new `sender_phone` parameter (distinct from the pre-existing
  `user_phone`, which for a *group* turn is the most-permissive MEMBER's
  phone per Feature 039's group-RBAC resolution — possibly a different
  person than whoever actually sent this specific message) threads the
  ACTUAL sender's phone through `get_response`/`_finalize_response`/
  `_resolve_pending_approval`/`resolve_button_tap`, so `Message.sender` is
  never wrong on a group turn governed by someone else's role.
- New `WhatsAppMessage.chat_name` field (Green API's `senderData.chatName`)
  — a group's real subject/name, feeds `recipient_name`.
- `MediaHandler._store_media_turn` got the same design, plus a **real RBAC
  role resolution** via `self.denidin.ai_handler.user_manager` — it was
  previously hardcoded `"client"` for every media sender regardless of
  actual role.
- Player gets a new optional `PlayerConfig.whatsapp_own_number` field —
  same category as `sender_map`: the player never touches live Green API,
  so `own_whatsapp_number` always resolves to `""` there on its own; this
  is the operator-supplied substitute. Documented in `player/README.md`.

**`LedgerEvent.whatsapp_chat` removed entirely** — redundant with
`session_id`/`message_id`. **Stays `schema_version=1`** — explicit human
correction after an initial (wrong) bump to 2.

**Also fixed, found along the way**: `SessionManager`'s two `json.dump`
calls never had `ensure_ascii=False` — fixed (Hebrew was coming out as
`\uXXXX` escapes on `cat`).

**Test fallout, all fixed**: 11 unit tests + 1 integration test broke from
the schema change. Full suite: **932 unit+integration tests pass. 12/12
billed ledger-capture tests pass.**

### 2. Full 33-message live validation run (throwaway, not committed)

Ran the *entire* `גביה TEST.zip` export sequentially, message 1 through 33,
**exactly once each, no re-runs at all** (explicit user instruction,
simulating real-time production). Full findings write-up:
`apps/denidin-app/.player_review_scratch/RUN_REPORT_33msgs.md` (gitignored,
NOT committed — see "Lost artifacts / where things live" below). Summary:

- **Finding A (🔴 most significant, still NOT fixed)**: a real, live Morning
  MCP ngrok tunnel outage hit mid-run (messages 19/20/21/28, all **text**
  messages — `openai.APIStatusError: 424 - Error retrieving tool list from
  MCP server: 'morning-invoices'`). When this exception propagates out of
  `AIHandler.get_response`, the user's message is **never persisted at
  all** — not as a failed record, nothing. Image messages are structurally
  immune (no Morning MCP tools attached on that path) — confirmed live,
  every image succeeded throughout the same outage window.
  **Confirmed, twice, via the real `logs/denidin.log` from this exact
  run (not inference, not a re-run)**: a real user is NOT left with
  silence. All 4 failures (`req_50312b26b068`/`req_06278ba4e21e`/
  `req_7670a957d125`/`req_e606dddf27b2`, timestamps 14:26:24/14:27:02/
  14:27:36/14:30:24) show a matching `Response sent successfully...72
  chars` / `Response sent to אילה 🦋` line at the identical timestamp. The
  mechanism (corrected after an initial wrong guess): the 424 is caught by
  `AIHandler.get_response`'s **own internal** `except APIError`
  (`ai_handler.py:1378-1386`) wrapped directly around the OpenAI call —
  NOT `denidin.py`'s outer global exception handler (confirmed 0 log
  matches for that handler's own log lines across the whole file). It
  returns a normal `AIResponse` via `_create_fallback_response(request_id,
  "Sorry, I encountered an error processing your request. Please try
  again.")` — **English**, 72 chars (matches the log), `should_reply`
  defaults `True` — so `WhatsAppHandler.send_response` sends it exactly
  like any other reply. Net effect: the *user experience* gap is small (a
  generic, English-not-Hebrew bounce, not silence); the *data* gap is the
  real one — because this return path never reaches `_finalize_response`,
  neither the user's message NOR this fallback reply is ever persisted,
  and the message's real content is gone unless the sender notices and
  resends.
- **Finding B**: `reference_hint`/`reference` linking never does
  cross-message correlation (msg 33's ₪3,000 בנק deposit from "עדו דניאל"
  almost certainly = msg 8's fee agreement for "עידו דניאל", same amount,
  near-identical name, never linked). **User's read: "fine and well
  known"** — not pursuing.
- **Findings C, D, E — reclassified this session, NOT independent
  findings**: all three are really the SAME root cause — **the model
  should have asked a clarifying question and silently guessed instead**:
  - C: message 31, three OCR name variants present (`עו"ד גלברט עפרו ו`
    garbled, `טירה עופר גלברט` garbled, `עופר גלברט` clean) — model
    picked the worst garbled one instead of asking which was right.
  - D: message 27, raw OCR has the client name punctuated two different
    ways in the same text (`ירון,יונתן` vs `ירון-יונתן`) — model silently
    picked one instead of asking.
  - E: message 30, `client_name: "מלצר עפרה וד"ר מ"` reads as cut off
    mid-word, matching the source's own truncation — model didn't flag
    the truncation as something to ask about.
  **User's explicit direction**: the constitution needs to push the model
  to ask far more readily whenever something is ambiguous/garbled/
  truncated — logged as the top real follow-up, not yet implemented (see
  "What's left" below — this is a `runtime_constitution.md` change
  affecting all live production traffic, out of scope for a quick fix).
- **Confirmed working correctly in live use**: findings #2/#3/#4/#6/#9/#10
  from the original interactive review all validated for real this run —
  `payer_name`/`vat_status` forced correctly on **15/15** real בנק events.

### 3. Real `player/run_player.py` fixes (commit `0f6356b`)

While re-running a handful of messages after the 33-message run, discovered
**the actual shipped player app has the exact same isolation bug the
throwaway `.player_review_scratch/driver.py` had already been patched
around**: `run_player.py`'s own `_build_config_dict` never overrode
`config.memory.session.storage_dir`/`.longterm.storage_dir` from
`--data-root` — so `data_root` was cosmetic, and every real player run was
silently writing session/long-term-memory data into whatever the config
file's own `memory` block said. With the bundled
`player_run_gviya_test.json` + `config/config.test.json`, that happened to
be `test_data/sessions`/`test_data/memory` — **the real, live, shared
directory the entire pytest suite uses** (confirmed: 40 pre-existing real
entries in `test_data/sessions` before this fix).

Fixed for real, in the shipped module (not scratch tooling):
- `_build_config_dict` now overrides both storage dirs from `data_root`,
  same fix already proven in `driver.py`.
- `player_run_gviya_test.json`'s `data_root` → `"player_data"` (new,
  gitignored, dedicated to player runs — added to `.gitignore`).
- **New clarification-loop mechanism, built directly into `run_player.py`**
  (not the throwaway driver): after each dispatched message, if no ledger
  event was produced and the model's reply contains "?", the player
  answers with a fixed, uninformative filler
  ("אין לי עוד מידע, תעשה הכי טוב שאתה מבין.") and loops — bounded at 5
  rounds — until a terminal outcome: an event captured, or a plain
  declarative reply with no further "?" (decided not to create one).
  Every round is logged to `<data_root>/needs_clarification.jsonl`.

**Verified live**: `python3 -m player.run_player player/player_run_gviya_test.json
--start 2026-08-02 --end 2026-08-02` (note: player granularity is by
calendar day, not individual message — this naturally replayed messages
15–20, all falling on that date) dispatched 6 messages into a fresh
`player_data/`, confirmed fully isolated from `test_data/` and from
`.player_review_scratch/`'s own throwaway session. 10 ledger events
captured, one clarification round logged and resolved. Real model
non-determinism observed directly: the same message text ("אורית בנימין /
מקורות / שעתיים") asked a clarifying question about the date in the
33-message run's session, but was captured directly (inferring the date
from the message's own send date) in this run — different session context,
different outcome, neither one "wrong."

## Billed test verification — still 12/12 passing after the redesign

Re-verified after the schema changes (same 12 tests as the prior session's
sweep) — all pass. No further action needed unless new tests get added.

## Where things live now (read this before hunting for files — locations changed this session)

- **`apps/denidin-app/.player_review_scratch/`** (gitignored, in-repo, NOT
  `/tmp`) — the interactive-review scratch tooling and its own throwaway
  output:
  - `RUN_REPORT_33msgs.md` — the 33-message run's full findings write-up.
  - `throwaway_data/` — real persisted messages/events from that run
    (session `7d3e5293-cbda-41c3-8f92-a91d0fed808e`), plus 4 messages
    (19/20/21/28) re-dispatched into the SAME session later the same day,
    appended after message 33 in dispatch order (not re-inserted
    chronologically) — flagged, not hidden.
  - `driver.py` / `dispatch_and_diff.sh` / `rerun_specific.py` — one-off
    review/rerun harnesses. **Not the production player** — see below.
  - `for_review.jsonl` — **4 entries** (messages 1, 6, 11, 20) where the
    model asked a genuine clarifying question during the 33-message run
    or its follow-up reruns.
  - `state.json` — `{"next_index": 33}` (fully consumed).
- **`apps/denidin-app/player_data/`** (gitignored, NEW this session,
  **not** the same thing as `.player_review_scratch/`) — output of the
  real, fixed `player/run_player.py` (today's `--start 2026-08-02 --end
  2026-08-02` run): `sessions/` (session
  `beac81d4-75b0-4e7e-a335-f0468e5d31c2`), `memory/`, `events/` (10
  events), `needs_clarification.jsonl` (1 entry, message 19). This is the
  location any future real player run should keep using/extending — it's
  the actual production player's own dedicated data root now, isolated
  from `test_data/` for good.

None of `.player_review_scratch/`'s contents are required to continue
Feature 043's real work — it's one-off review tooling. `player_data/` and
the `run_player.py` fix, by contrast, ARE real production-code state/output
going forward.

## What's left — scope decided 2026-08-19 (see `tasks.md` for the full record)

- **Phase 5 (reconciliation), Phase 6 (relevancy), Phase 7 (review
  queue)** — **deprioritized, not removed**: skip for now, human call
  ("not needed right now"). May resume later.
- **Phase 8 (image-path replay regression, `expensive` tier)** —
  **checked against the real 33-message run and found NOT actually
  proven**, despite that run including 15 real vision messages: all 15
  were bank screenshots with explicit absolute dates, never relative-date
  language ("אתמול"/"היום") — grepped every image's `extracted_text`
  across all 33 messages, zero matches. Phase 3's vision-path
  `today_timestamp` threading is built but still end-to-end unverified.
  **Still open** — needs `T020a` (write the test) + explicit approval to
  actually run it (expensive tier, one at a time).
- **Phase 10 (player/WhatsApp equivalence tests)** — **removed entirely**,
  not deprioritized: the model's confirmed non-determinism (this exact
  session: "אורית בנימין/מקורות/שעתיים" produced two genuinely different
  real outcomes across two separate real runs — one asked about the date,
  one inferred and captured directly) makes an equivalence assertion
  between two paths fundamentally unreliable as a premise, not just
  currently low-priority.

## Suggested next steps for a fresh session

Nothing is currently being actively pursued. What remains open:

1. **Phase 8** — write `tests/expensive/test_player_image_replay.py`
   (T020a) and, with fresh explicit approval, run it once. This is the
   only remaining phase-tracked work item.
2. **The model-should-ask-more-often gap (Findings C/D/E's real root
   cause)** — outside the phase structure. A `runtime_constitution.md`
   change, affecting all live production traffic, not just the player.
   Needs its own explicit design pass, not a quick patch, and human
   sign-off before any change.
3. **Finding A (message-loss-on-exception)** — outside the phase
   structure, still not fixed, still real. Persisting the user's own
   message before attempting the OpenAI call (or wrapping just the AI
   call in its own try/except) would close it. Needs human sign-off —
   real behavior change to the core message pipeline.
4. Finding B — user's call: "fine and well known," not pursuing.
5. The 4 `for_review.jsonl` entries (messages 1, 6, 11, 20) and the 1
   `player_data/needs_clarification.jsonl` entry (message 19) are real
   candidates if a human wants to actually resolve the ambiguity behind
   them.
6. Phases 5-7, whenever/if reprioritized.
7. **Nothing should be committed/pushed/PR'd without asking** for whatever
   comes next. When Feature 043 as a whole is ready to close out, that's
   what `haleluya` is for — only when explicitly invoked.
