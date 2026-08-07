# Handoff: Feature 043 — WhatsApp Export → Ledger Event "Player"

**Written**: 2026-08-07 (end of session, user requested a fresh start —
waiting on Bina to release the `dev` env lock after finishing Feature 027;
unrelated to this feature's own work, which no longer touches `dev` at all —
see "Key things to know" below)
**Branch**: `feature/043-production-data-setup-tooling`
**Last commit**: `63f09f7` (this feature has made ZERO commits so far —
everything below is uncommitted working-tree state)
**Nothing has been pushed, no PR opened, no release cut.**

---

## What's done

### SpecKit pipeline (full, in `specs/in-progress/043-production-data-setup-tooling/`)
`spec.md`, `user-stories.md` (6 stories, reviewed/confirmed one-by-one with
the user), `research.md` (7 decision records), `plan.md`, `data-model.md`,
`contracts/{message-source,player-cli}.md`, `tasks.md` (9 phases). Read
`research.md` R3/R4 and `plan.md`'s architecture section before touching
anything — they explain *why* this feature required real production-code
changes, not just new tooling.

### Phase 1 (Setup) — done
T001 (branch confirmed), T002 (re-checked the real sample export for
system-message lines/attachment captions — found neither in the sample, but
documented why that's not proof the real full export won't have them; the
parser filters defensively anyway).

### Phase 2 (`MessageSource` abstraction) — done except T005
**The big finding this session surfaced**: `denidin.py` used to construct a
live `DeniDinGreenAPIBot` (draining real pending Green API notifications) as
a **module-import-time side effect** — meaning even `import denidin` in a
test file touched real Green API credentials. Fixed by extracting a
`MessageSource` interface (`src/sources/message_source.py`,
`src/sources/green_api_source.py`) — `GreenAPIMessageSource.connect()`
(idempotent, constructs the bot) is now separate from `.start()` (registers
+ blocks), and both are called explicitly only from `denidin.py`'s live
`__main__` entry point, never at import. `denidin.py` itself: handler
functions are now plain/undecorated, `HANDLER_REGISTRY` +
`dispatch_notification()` replace the old `@bot.router.message(...)`
decorators. `initialize_app()`/`_fetch_own_whatsapp_number()` now take an
injected `green_api` parameter (both already degrade gracefully to `None`).

Two real bugs caught and fixed *while implementing this* (by reading the
actual `whatsapp_chatbot_python` library source, not assuming):
1. The catch-all handler must be registered as `router.message()` with
   **zero kwargs**, never `type_message=None` — the library's real filter
   matching treats those differently (`None` gets evaluated and fails to
   match, silently breaking every unsupported-type message).
2. `message_types=[]` (explicitly no specific types) was incorrectly
   falling back to defaults via Python's `or` truthiness — fixed to an
   explicit `is None` check.

**T005 (manual verification that `dev` still routes identically) is
NOT done** — was gated on starting `dev`, which needs its own explicit
approval. The user then redirected verification to a real run against
`test_data/events` instead (see below), making T005 effectively moot for
this feature — but it's still unchecked in `tasks.md`; worth a final
decision on whether it's needed at all now.

### Phase 3 (timestamp fix + schema additions) — done
- **`today_timestamp`** (renamed this session from `reference_timestamp` at
  the user's request — renamed everywhere: code, tests, docs, comments,
  filenames): an optional parameter on `AIHandler._build_instructions` and
  `capture_ledger_events_from_text`, overriding wall-clock "today" (used to
  resolve "היום"/"אתמול" into ledger fields like `txn_date`) with a
  message's own historical date. This was **the one real correctness bug**
  a full audit (`research.md` R4) found — every other date-derived ledger
  field already correctly used the message's own timestamp.
  - Text-message call sites already had `AIRequest.timestamp` in scope —
    threaded via `request.timestamp`, no new object needed (the user
    specifically asked to avoid loose-scalar threading where an object
    already exists — this path already satisfied that).
  - Image/PDF path needed a 4-hop thread (`MediaHandler.
    process_media_message` → `_extract_text` → `ImageExtractor`/
    `PDFExtractor.analyze_media` → `capture_ledger_events_from_text`).
    **Deliberately NOT wrapped in an object** — `process_media_message`'s
    existing signature is already 10 loose scalar params, pre-dating this
    feature; introducing an object there would mean restructuring that
    established signature (and every test that calls it directly) for the
    sake of one integer — judged out of proportion and explicitly discussed
    with the user, who agreed.
- `LedgerEventManager`: `CURRENT_SCHEMA_VERSION` (=1) + `schema_version`
  field (11th internal field, written by both live and player, never
  retro-applied to old files); two new additive methods,
  `resolve_replaced_event_id()` (US2) and `apply_review_answer()` (US3).

### Phase 4 (US1 — replay a date range) — done through T014b
New package `player/`:
- **`export_parser.py`** (T009) — WhatsApp export zip → `List[ParsedMessage]`.
  Confirmed against a real sample this session. Caught and fixed a real bug
  while implementing: a system notice mid-conversation (no "Name:" colon
  structure) could get glued onto the **prior real message** as a bogus
  continuation line — fixed with a two-stage date-prefix/system-check
  before attempting the sender:text split.
- **`notification_synth.py`** (T010) — `ParsedMessage` → Green-API-shaped
  `(event, type_message)` tuple, or `None` for unsupported attachment types.
- **`media_server.py`** (T011) — `LocalMediaServer`, OS-assigned port.
- **`export_source.py`** (T012) — `PlayerExportSource(MessageSource)`,
  iterates messages, synthesizes + dispatches, tracks per-message
  `outcomes` (dispatched / unmapped-sender / unsupported-type).
- **`config_safety.py`** (T013) — `validate_data_root()`: `--data-root`
  required (no default anywhere), production-path values need an explicit
  `--confirm-production-data-root` override.
- **`run_player.py`** (T014b) — CLI + `run_replay()` driver, ties everything
  together: `import denidin` (safe now, see Phase 2) →
  `initialize_app(config_dict, green_api=None)` → parse/filter export →
  `LocalMediaServer` → `PlayerExportSource.start(denidin.dispatch_notification)`.
  **This is the main-loop core only** — no reconciliation/relevancy/
  review-queue wiring yet (that's T015+, not started).

**T014a (a synthetic `billed`-tier E2E test) was explicitly skipped** — the
user pointed out a real run against their own export file (see below) would
be redundant end-to-end verification, so I went straight to making the
driver ready for that instead.

### Test fixture
User provided a real export zip (dates in July–Aug 2026 — a recent test/
demo conversation, not real historical Sep 2025 data), placed at
`apps/denidin-app/tests/fixtures/whatsapp_exports/גביה TEST.zip`, and
**explicitly authorized committing it to git** (supersedes this feature's
earlier "synthetic fixtures only" default — that default still applies to
*new* test fixtures written for the parser's own unit tests, which stay
synthetic; this one real file is a deliberate, cleared exception). It's
`git add`-ed already (not committed). Validated directly against the real
parser (scratch dir, nothing written to `test_data`): **33 messages parse
correctly** (18 text, 15 image — all 15 attachment files resolve to real,
existing files on disk), single sender throughout (`אילה 🦋`).

### Test status (whole suite, both apps unaffected — denidin-app only)
**845/845 unit+integration tests pass** (re-confirmed fresh after the
`today_timestamp` rename, not just before it). Whole-project pylint ~9.1+/10
(above the 7.0 threshold, no regression vs. baseline throughout). mypy clean
on every touched file (only pre-existing, unrelated missing-stub warnings
remain elsewhere).

## A prepared (but NOT executed) real run

Everything is wired to run this for real against `test_data/events` the
moment it's approved:

```bash
cd apps/denidin-app
python3 player/run_player.py \
    --export-zip "tests/fixtures/whatsapp_exports/גביה TEST.zip" \
    --chat-id "120363999999999999@g.us" \
    --sender-map <path to a JSON file: {"אילה 🦋": "972501234567@c.us"}> \
    --data-root test_data \
    --config config/config.test.json
```

- `--chat-id`: synthetic, ends in `@g.us` — user said the real chat is a
  **group**, and gave permission to invent any chat id (no need for the
  real one).
- Sender phone: user said "her number is same as godfather" —
  `config.test.json`'s `godfather_phone` is `+972501234567`, which
  normalizes (via `UserManager._normalize_phone`, strips non-digits) to the
  same digits as `972501234567@c.us` regardless of `+`/JID formatting, so
  RBAC resolves her as godfather correctly.
- Group RBAC note: since the player has no live Green API connection,
  `GroupMembershipResolver.resolve()` will fail internally (caught,
  returns `None`) and degrade to sender-only RBAC — which still correctly
  resolves godfather role here since she *is* the godfather, so this
  degrade doesn't affect correctness for this specific fixture.
- This has **not been run** — it costs real OpenAI calls (33 messages: 18
  text + 15 vision) and writes real files into `test_data/events/` (which
  already has 29 unrelated pre-existing files from other test sessions —
  no ID collision expected, purely additive since reconciliation isn't
  built yet). **Needs fresh, explicit approval to actually execute**, same
  as any other real-money/real-write action.
- The sender-map JSON file referenced above doesn't exist yet on disk —
  needs creating (one line) before this command can run.

## Explicitly NOT done — needs a human decision or more work, not autonomous action

1. **T005** (manual `dev` live-behavior verification) — unchecked, possibly
   moot now given the pivot to test-env verification; worth an explicit
   decision on whether to still do it before this feature is considered
   done, or drop it from tasks.md since T004's automated tests + the real
   test-env run together substitute for it in practice.
2. **T015–T017 (US4 reconciliation, US2 relevancy)** — not started.
   `run_player.py`'s current loop has no orphan-detection/`to-delete`
   moving, and no `replaces_hint`-resolution linking yet.
3. **T018–T019 (US3 review queue)** — not started. No ambiguity-flagging,
   no `--reapply-review` mode yet (the CLI flag doesn't even exist in
   `run_player.py` yet — only plain replay is wired).
4. **T020 (expensive-tier image-replay regression test)** — not started;
   needs its own fresh approval per the expensive-test rules when it
   happens (one at a time, never a bare sweep).
5. **T021 (`player/README.md`)** — not written yet.
6. **The prepared real run above** — not executed, needs explicit approval.
7. **Nothing committed** — the user's own standing rule (confirmed
   elsewhere in this session) is unit/integration test judgment calls are
   delegated to me for this feature, but committing/pushing/PR/merge are
   not — those still need their own explicit asks, unchanged.

## Key things to know before continuing

- **The whole point of this feature is that the player never touches Green
  API or a live/dev/prod environment at all** (`research.md` R3) — it only
  needs OpenAI + local files. The "waiting for Bina to release dev" reason
  this session paused is about a *different* concern (the multi-clone `dev`
  lock, per this repo's CLAUDE.md) and doesn't actually block anything in
  this feature's own critical path — worth confirming with the user next
  session whether that's understood, since nothing here needs `dev`.
- **User delegated unit/integration test judgment calls to me for this
  feature specifically** ("I dont care about unit tests. They are yours.")
  — but explicitly wants to be told/asked before `billed`/`expensive` tier
  tests run (though `billed` needs no special approval per CLAUDE.md
  either way — just flag it happening).
- **`today_timestamp`, not `reference_timestamp`** — already renamed
  everywhere as of this session; if you see `reference_timestamp` anywhere,
  that's stale and should be caught/fixed.
- **Don't add object-wrapping for the image/PDF path's scalar threading** —
  this was explicitly discussed and rejected as disproportionate (see
  Phase 3 section above). The text-message path already uses
  `AIRequest`/`.timestamp` as-is.
- **The review-queue mechanism (US3) must never touch `LEDGER_EVENT_TOOL`'s
  live schema** — user explicitly rejected a `needs_review` tool-schema
  field ("This is an external accounting piece of info, not the source").
  Whatever US3 ends up being (T018-T019) must stay entirely external to the
  ledger event record.
- **`test_data/events/` already has 29 unrelated files** from other test
  sessions before this feature touched anything — don't assume an empty
  directory when reasoning about what a real run will produce.
- Real WhatsApp export format, confirmed twice now against real samples: see
  `research.md` R1 for the full write-up (date-prefix parsing, bidi control
  chars, attachment lines, no reliable caption-on-attachment-line evidence
  yet).

## Suggested next steps for a fresh session

1. Confirm whether the "waiting for Bina/dev" blocker actually applies to
   this feature (it shouldn't, per above) — if it doesn't, the real run is
   ready to go pending approval.
2. Create the sender-map JSON file, get explicit approval, run the prepared
   command above against `test_data/events`.
3. Review the actual captured events for correctness (dates match the
   historical messages, not wall-clock "today" — this is the real
   confirmation the Phase 3 fix works end-to-end).
4. Decide on T005's fate (drop vs. still do it later against `dev`).
5. Continue Phase 4: T015-T017 (reconciliation + relevancy), T018-T019
   (review queue), T020 (expensive image-replay test, needs fresh
   approval), T021 (README).
6. Nothing should be committed/pushed/PR'd without asking, per standing
   project rules — this whole session's work is still sitting uncommitted.
