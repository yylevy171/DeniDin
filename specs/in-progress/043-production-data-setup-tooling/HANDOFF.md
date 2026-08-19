# Handoff: Feature 043 — WhatsApp Export → Ledger Event "Player"

**Written**: 2026-08-19 (end of session, user requested commit+push+handoff to start fresh)
**Branch**: `feature/043-production-data-setup-tooling`
**Committed and pushed this session**: commit `ab514c7` (this session's work,
described in full below), on top of `9f844ad` (prior session's Phase 11
follow-up, already covered by that commit's own message — not repeated
here). `git log --oneline -5` to orient.

---

## What's done (cumulative, all phases)

- **Phases 1–4** (Setup, `MessageSource` abstraction, timestamp fix, US1
  replay-a-date-range) — done, per earlier handoffs.
- **Phase 9** (`player/README.md`) — done 2026-08-16, updated again this
  session (new `whatsapp_own_number` config field documented).
- **Phase 11 + Phase 11 follow-up** (ledger schema, 10 player-review
  findings, `raw_message_excerpt`→`Message.extracted_text`) — done,
  commit `9f844ad`.
- **This session** (2026-08-19) — commit `ab514c7`: a real Message
  identity-field redesign (role/sender/recipient/etc.), `LedgerEvent.
  whatsapp_chat` removed, and a full 33-message live validation run. Detail
  below.
- **NOT started**: Phase 5 (reconciliation), Phase 6 (relevancy), Phase 7
  (review queue), Phase 8 (expensive image-path regression), Phase 10
  (player/WhatsApp equivalence tests — permanently blocked until Feature 040
  lands).

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
  at startup — no new plumbing needed, I initially wrongly told the user
  this didn't exist and had to correct myself), the group's own JID as
  `recipient` for any group turn regardless of who sent it, the other
  party's real number otherwise.
- `sender_name`/`recipient_name` (new): resolved display names, carrying
  what the old `sender` field used to hold.
- A new `sender_phone` parameter (distinct from the pre-existing
  `user_phone`, which for a *group* turn is the most-permissive MEMBER's
  phone per Feature 039's group-RBAC resolution — possibly a different
  person than whoever actually sent this specific message) threads the
  ACTUAL sender's phone through `get_response`/`_finalize_response`/
  `_resolve_pending_approval`/`resolve_button_tap`, so `Message.sender` is
  never wrong on a group turn governed by someone else's role. This was a
  real bug I would have introduced without catching it myself mid-design.
- New `WhatsAppMessage.chat_name` field (Green API's `senderData.chatName`
  — already present on every real notification, never parsed before) — a
  group's real subject/name, feeds `recipient_name`.
- `MediaHandler._store_media_turn` got the same design, plus a **real RBAC
  role resolution** via `self.denidin.ai_handler.user_manager` — it was
  previously hardcoded `"client"` for every media sender regardless of
  actual role, a latent bug that became visible (and worth fixing, low
  cost given reachability) only once `role` started carrying real meaning.
- Player (`player/run_player.py` AND the interactive review driver) gets a
  new optional `PlayerConfig.whatsapp_own_number` field — same category as
  `sender_map`: the player never touches live Green API, so
  `own_whatsapp_number` always resolves to `""` there on its own; this is
  the operator-supplied substitute. Documented in `player/README.md`.

**`LedgerEvent.whatsapp_chat` removed entirely** — redundant with
`session_id` (the session it points at already carries its own
`whatsapp_chat`) and `message_id`, both already sufficient traceability.
**Stays `schema_version=1`** — explicit human correction after I initially
bumped it to 2; the reasoning (v1 has never been deployed to real dev/prod
data, same reset-safety logic as the original Phase 11 reset) folds this
into the same baseline rather than incrementing.

**Also fixed, found along the way**: `SessionManager`'s two `json.dump`
calls (message + session persistence) never had `ensure_ascii=False` —
unlike `LedgerEventManager`, which already did — so every persisted
message file was unreadable via a raw `cat` (Hebrew came out as `\uXXXX`
escapes). This is exactly what the user hit when asking to see message
JSONs directly; fixed by adding the flag to both call sites.

**Test fallout, all fixed**: 11 unit tests + 1 integration test broke from
the schema change (mostly `role == "user"` checks needing to become
`ai_required_role == "user"`, and the old sentinel-retirement test class
needing a full rewrite to test the *opposite* — sender/recipient always
populated). `test_ledger_event_manager.py` needed ~85 mechanical
`whatsapp_chat="..."` removals from call sites plus a field-count/
schema-version test update. Full suite: **932 unit+integration tests
pass. 12/12 billed ledger-capture tests pass** (verified — see below).

### 2. Full 33-message live validation run (not committed — throwaway)

After the redesign, ran the *entire* `גביה TEST.zip` export sequentially,
message 1 through 33, **exactly once each, no re-runs at all** (explicit
user instruction, simulating real-time production — a message that fails
stays failed, never retried). Full JSON of every persisted message +
ledger event shown for each of the 33 messages in this session's chat
transcript (not reproduced here — see the transcript, or re-derive by
reading `.player_review_scratch/throwaway_data/` directly if it still
exists — see "Lost artifacts" below).

**Full findings write-up**: `apps/denidin-app/.player_review_scratch/
RUN_REPORT_33msgs.md` (gitignored, NOT part of the commit — see "Lost
artifacts"). Summary of what it contains:

- **Finding A (🔴 most significant)**: a real, live Morning MCP ngrok
  tunnel outage hit mid-run (messages 19/20/21/28, all **text** messages —
  `openai.APIStatusError: 424 - Error retrieving tool list from MCP
  server: 'morning-invoices'`). The consequential discovery: when this
  exception propagates out of `get_response`, the user's message is
  **never persisted at all** — not as a failed record, nothing. Real
  production content (fee agreements, hourly work) is silently lost
  unless the sender notices and manually re-sends. Image messages are
  structurally immune (they don't attach Morning MCP tools at all) —
  confirmed live, every image succeeded throughout the same outage
  window. **Not fixed** — purely observed and reported per explicit
  instruction ("no changing anything").
- **Finding B**: `reference_hint`/`reference` linking is inconsistent on
  "העברה נוספת" phrasing (sometimes fires, sometimes doesn't, no evident
  distinguishing feature between cases) and **never does cross-message
  correlation** — message 33 (בנק deposit, ₪3,000, "עדו דניאל") is almost
  certainly message 8's actual fee-agreement payment (same amount,
  near-identical name) but was never linked. This is a real capability
  gap, not a bug — the constitution never asked for amount/name
  cross-referencing across persisted events.
- **Finding C**: name-garbling (finding #7 from the original review)
  recurred on message 31 — three OCR name variants present, model picked
  the worst garbled one despite a clean variant ("עופר גלברט") sitting
  right there in the same text.
- **Finding D/E**: minor, low-severity — punctuation drift between raw
  OCR and persisted `client_name` (msg 27), a possibly source-truncated
  name (msg 30).
- **Confirmed working correctly in live use**: findings #2/#3/#4/#6/#9/#10
  from the original interactive review all validated for real this run —
  most notably `payer_name`/`vat_status` forced correctly on **15/15**
  real בנק events (was 14/15 wrong before the fix), and finding #3's check
  handling correctly asked-then-declined rather than mis-capturing.

## Billed test verification — still 12/12 passing after the redesign

Re-verified after the schema changes (same 12 tests as the prior
session's sweep, `test_ledger_event_capture_billed.py` +
`test_ledger_event_capture_text_billed.py`) — all pass. No further action
needed here unless new tests get added.

## Lost artifacts (informational, not blocking, but read this before hunting for files)

`.player_review_scratch/` (gitignored, in-repo, NOT `/tmp` — this was the
whole point of moving it there in an earlier session) should still contain,
as of end-of-session:
- `RUN_REPORT_33msgs.md` — the full findings write-up (summarized above).
- `throwaway_data/` — the real persisted messages/events from the 33-message
  run (session `7d3e5293-cbda-41c3-8f92-a91d0fed808e`), useful if you want
  to re-inspect a specific message's JSON without re-running anything.
- `driver.py` — the one-message-at-a-time review harness, now with the
  automated clarifying-question fallback mechanism (logs to
  `for_review.jsonl`, answers with a fixed uninformative filler, gives the
  model exactly one more chance, never re-asks).
- `dispatch_and_diff.sh` — a thin wrapper around `driver.py` that also
  diffs+prints newly-created message/event files per dispatch; used for
  the 33-message run.
- `for_review.jsonl` — 3 entries from the 33-message run (messages 1, 6,
  11) where the model asked a genuine clarifying question the automated
  filler couldn't resolve — real candidates for a human to actually answer
  if this review continues.
- `state.json` — sits at `{"next_index": 33}` (fully consumed) after the
  last run in this session.

None of this is required to continue Feature 043's actual work — it's
observational tooling and its own output, not a dependency. If it's gone
(this machine, this clone), that's fine; the actionable findings are
already written up in this document.

## Suggested next steps for a fresh session

1. **Finding A (message-loss-on-exception) is the most concrete, most
   actionable finding from this whole session** — worth deciding whether
   it's in scope for Feature 043 or its own bugfix. At minimum, persisting
   the user's own message *before* attempting the OpenAI call (or in a
   try/except around just the AI call, independent of storage) would
   close this gap. Needs human sign-off before any code change, per
   standing discipline — this is a real behavior change to the core
   message pipeline, not a minor fix.
2. Findings B/C/D/E are lower-priority, mostly informational — worth
   deciding whether any warrant constitution tweaks or are accepted as
   inherent model variance (same "not every finding needs a fix" spirit
   as `specs/not_reproducible/bugfixes/`).
3. The 3 outstanding `for_review.jsonl` entries (messages 1, 6, 11) are
   real candidates if the interactive review continues — they represent
   genuine ambiguity a human should actually resolve, not a bug.
4. Continue Phase 5–8, 10 whenever prioritized (unchanged — reconciliation,
   relevancy, review queue, expensive-tier regression, Feature-040-blocked
   equivalence tests).
5. **Nothing should be committed/pushed/PR'd without asking** for whatever
   comes next — this session's own work (the redesign) already IS
   committed+pushed (`ab514c7`), per explicit request. When Feature 043 as
   a whole is ready to close out, that's what `haleluya` is for — only
   when explicitly invoked.
