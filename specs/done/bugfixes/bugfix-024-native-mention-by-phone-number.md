# Bugfix Spec: Real WhatsApp native @-mention of DeniDin itself gets silently ignored (no-reply)

## Bug ID
bugfix-024-native-mention-by-phone-number

## Title
When a user @-mentions DeniDin via WhatsApp's own native `@` mention picker (the
primary, ordinary way anyone mentions someone in WhatsApp), the message is silently
dropped (`[[NO_REPLY]]`) instead of getting a reply - even though the message was
genuinely, unambiguously addressed to DeniDin.

## Priority
P0 - this breaks the single most common real-world way a user actually addresses
DeniDin by name in a group (the native mention picker), silently, with no error and
no visible signal to the sender that anything went wrong. Found in production-bound
manual testing immediately after deploying Feature 039 to `dev`.

## Status
**Done - Merged to master (PR #186), fixed and verified live (2026-08-05)** - all 8
cases in `tests/billed/test_group_etiquette_billed.py` pass against the real Green
API/OpenAI pipeline, including the new case7 reproducing the exact real failure.

## Date Opened
2026-08-05

## Reported By
yaronlev171 (found during manual `denidin-app-dev` testing, immediately after
deploying Feature 039)

## Affected Area
- `apps/denidin-app/src/handlers/ai_handler.py` - `AIHandler.create_request` (where
  the fix's normalization is applied), new `_normalize_self_mentions` function, new
  `AIHandler.own_whatsapp_number` instance attribute.
- `apps/denidin-app/denidin.py` - new `_fetch_own_whatsapp_number()` helper, wired
  into `initialize_app()`.
- `apps/denidin-app/config/runtime_constitution.md`'s "Group Conversation Etiquette"
  section and the Feature 039 `"@Name"` text-pattern design it implements (US7) - the
  underlying design flaw this bug traces back to; not itself modified by this fix
  (the fix works entirely upstream of the model, in code).
- Test-isolation bug found and fixed as a side effect of investigating this
  (unrelated to the root cause below): `tests/integration/test_group_conversation_routing.py`'s
  `_stub_external_boundaries` mutated a shared, process-global `MediaHandler` singleton's
  methods via raw attribute assignment with no teardown, which leaked into
  `tests/integration/test_media_webhook_routing.py::test_image_message_user_gets_response`
  under random test ordering (that test observed this file's canned stub response
  instead of its own expected download-failure error). Fixed by switching to pytest's
  `monkeypatch` fixture (auto-reverted per test).

## Description
Live sequence observed in `denidin-app-dev` (real WhatsApp group, real Green API,
real OpenAI):

The user, whose phone has DeniDin's dev WhatsApp number saved as contact "דנידין dev",
used WhatsApp's own native `@` mention picker to tag that contact and sent:
`"@972559723730 מי אתה?"` ("who are you?"). The bot's own `text_content` for this
message - the exact text delivered by the real Green API webhook - was literally
`"@972559723730 מי אתה?"`, never containing the string "דנידין" or "DeniDin" anywhere.
The model, following the constitution's "@Name" addressee-recognition rule (does this
message name someone, and is that name DeniDin or a close variant?), correctly found
no name resembling "DeniDin" in the text (there wasn't one - only digits) and returned
`[[NO_REPLY]]`. The message was dropped with no reply, even though the sender had
genuinely and explicitly addressed DeniDin via the native mention feature.

## Root Cause
Feature 039's spec (`specs/done/039-group-conversation-support/spec.md`, Clarifications
section) stated as a settled Decision: "A real WhatsApp @-mention still inserts visible
`"@DisplayName"` text into the message body." This was never verified against a real,
live WhatsApp message - it was inferred from reviewing Green API's documented webhook
schema fields (confirming no *structured* mention metadata exists), which is a
different claim from what the mention *text itself* looks like. The two were
conflated.

Verified for real (2026-08-05, per the newly-added CONSTITUTION.md "NO UNVERIFIED
THIRD-PARTY ASSUMPTIONS" policy this incident established): a real native `@`-mention
picker selection inserts the mentioned contact's raw phone number into the message
text (e.g. `"@972559723730"`), not a display name - regardless of what name that
contact is saved as on the sender's own phone (that mapping is local-device-only
rendering, invisible to the message content Green API delivers). The entire `"@Name"`
text-pattern recognition mechanism (US7) - spec, constitution wording, and the billed
tests' hand-typed `"@Name"` fixtures alike - was built on the unverified assumption,
so nothing in the existing spec/implementation/test pipeline could have caught this;
it was found live, by a human, in manual post-deploy testing.

## Steps to Reproduce
1. Save DeniDin's WhatsApp number as any contact name on a phone that can message it.
2. In a group DeniDin is in, use WhatsApp's native `@` mention picker (not manual
   typing) to select that contact, and send any message.
3. Observe: no reply is sent. The model received the raw phone number in the text,
   never a name, and (correctly, per its instructions) treated an unrecognized
   `@<digits>` as "addressed to someone else."

## Fix (2026-08-05)
A deterministic, code-level check performed BEFORE the text ever reaches the model -
not a prompt/constitution change, and not something left to model judgment (per the
same CONSTITUTION.md policy):

1. **`denidin.py`'s new `_fetch_own_whatsapp_number()`**, called once from
   `initialize_app()` (never per-message): calls the real Green API
   `bot.api.account.getWaSettings()` (reusing the existing module-level `bot` - never
   constructs a second `GreenAPIBot`, since its constructor has a real side effect of
   draining pending incoming notifications from the live instance). Verified live
   (2026-08-05) to return `{"phone": "<bare digits>", ...}`, e.g. `"972559723730"`.
   Never raises - a failed/unreachable call degrades to `""` (self-mention-by-number
   detection unavailable that run; everything else unaffected), matching this
   codebase's fail-open convention for non-critical startup data.
2. **`AIHandler.own_whatsapp_number`**: new instance attribute (default `""`), set by
   `initialize_app()` after construction.
3. **`AIHandler._normalize_self_mentions(text, own_whatsapp_number)`**: a new pure
   function, a plain substring replace (`text.replace(f"@{own_whatsapp_number}",
   "@DeniDin")`) - not a regex. An initial version used a regex with digit-stripping
   normalization to tolerate a hypothetical "+"-prefixed number format; reconsidered
   and simplified (2026-08-05, same day) because no verified case ever showed that
   format - both the real `getWaSettings` response and the real captured mention text
   use the identical bare-digit format, so handling an unconfirmed variant wasn't
   justified (the same "verify, don't assume" principle this bug itself established,
   just pointed at unnecessary defensive code instead of an unverified claim). The
   plain replace rewrites the self-mention to `@DeniDin` - the name-shaped form the
   model's existing, already-verified addressee judgment already knows how to
   recognize correctly (same mechanism case6's manually-typed `"@DeniDin"` billed test
   already proves works) - and, since it only ever searches for the exact self-mention
   substring, structurally cannot touch a mention of any other phone number (the model
   already correctly treats an unrecognized `@<digits>` as "not me" - case5a/case5b -
   so only the self-mention case needed normalizing).
4. **`AIHandler.create_request`** now builds `user_prompt` via
   `_normalize_self_mentions(message.text_content, self.own_whatsapp_number)` instead
   of using `message.text_content` directly - applied once, upstream of both the
   OpenAI call and the persisted session-history storage (which stores this same
   `user_prompt`), so a re-read of the conversation history later also consistently
   shows `"@DeniDin"` rather than the raw digits.

## Verification
- New unit tests (fast, no network) - `tests/unit/test_ai_handler_self_mention_normalization.py`
  (9 tests: the pure `_normalize_self_mentions` function directly, plus
  `AIHandler.create_request` actually wiring `own_whatsapp_number` in) and
  `tests/unit/test_denidin_own_whatsapp_number.py` (4 tests: `_fetch_own_whatsapp_number`'s
  success/failure/exception paths, mocking only the Green API call boundary itself).
  All 13 passing.
- New billed test (real Green API + real OpenAI, no mocking) -
  `tests/billed/test_group_etiquette_billed.py::test_case7_native_mention_by_own_phone_number_gets_substantive_reply`:
  reproduces the exact real failure shape using `denidin_app.ai_handler.own_whatsapp_number`
  itself (the actually-resolved number from a real startup call, never a hardcoded
  guess - per CONSTITUTION.md's new policy), asserts a substantive reply. **PASSED live
  (2026-08-05)** against the real pipeline, along with the other 7 pre-existing cases
  in the same file (all 8 green).
  - Getting this test to actually run for real (rather than self-skip) surfaced two
    further findings, both fixed: (1) this file's own `config` fixture loaded
    `config/config.json` instead of `config.test.json` like every other billed test
    file - that instance turned out to be unauthorized (`stateInstance:
    "notAuthorized"`, no phone linked), confirmed live, so `own_whatsapp_number` always
    failed open and case7 always self-skipped; fixed by switching the fixture to
    `config.test.json`. (2) `denidin.py`'s module-level `bot` (built once at import
    time from the literal path `config/config.json`) is what `_fetch_own_whatsapp_number`
    actually calls - completely independent of whichever config a test's own
    `initialize_app(config_dict)` call uses, so fix (1) alone wasn't sufficient. The
    real host-checkout `config/config.json` file itself pointed to the same
    unauthorized instance (`7105257767`) - confirmed, per explicit human direction,
    that this file must never be loaded for real content (it's a stale placeholder;
    real deployments get the correct env-specific config bind-mounted onto that exact
    container-internal path by `docker-compose.<env>.yml`, never by editing this file).
    Fixed by replacing `apps/denidin-app/config/config.json` with a symlink to
    `config.test.json` (both already gitignored) - keeps the module-level import-time
    load from crashing (`sys.exit(2)` on `FileNotFoundError`) while guaranteeing its
    content can never silently drift from the one config host test runs actually rely
    on. This also, incidentally, fixes the same host-run limitation for the
    pre-existing `GroupMembershipResolver` (Feature 039), which relies on the same
    module-level `bot`.
- Full non-billed suite re-run clean after the fix and the unrelated test-isolation
  fix: 745 passed (confirmed stable across two different random-order seeds).
- `pylint`/`mypy` clean on both modified production files (no new findings).
