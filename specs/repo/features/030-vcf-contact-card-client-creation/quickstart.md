# Quickstart: vCard Contact Card → Client Creation (Feature 030)

Manual verification scenarios once implementation lands, covering US1-US3. Requires:
`apps/morning-mcp-app` running (dev, real sandbox) per the "ONE ENVIRONMENT SET AT A TIME" rule
and its own `run_morning_mcp.sh dev`; `apps/denidin-app` running dev with a godfather WhatsApp
number configured. **Starting either environment always needs explicit approval — nothing below
authorizes that on its own.**

## Prerequisites

- `apps/morning-mcp-app/config/config.dev.json` has real Morning sandbox credentials.
- `apps/denidin-app/config/config.dev.json`'s `mcp` block points at the running Morning server's
  status file, and the sender's WhatsApp number resolves to `godfather` or `admin`.
- A phone contact (in the tester's own device address book) with a name not already a Morning
  client, ideally one **with** an email saved (to exercise US1) — most real contacts won't have
  one saved (per the real fixture used in automated tests), so this may need to be added to the
  test device's contact app first.

## US1 — Share a complete contact card (name + phone + email)

Share a WhatsApp contact card for the prepared contact (name + phone + email all present).
Expect turn 1: a Hebrew confirmation question naming the parsed name/phone/email — **no
`add_client` call yet**.
Send turn 2: `"כן"`.
Expect: confirmation the client was created.
Verify: `get_client_details`/Morning web UI shows the new client with phone normalized to Israeli
local dashed format (`0XX-XXXXXXX`) regardless of how it was saved on the device.

## US2 — Share a contact card missing an email

Share a WhatsApp contact card for a contact with **no email saved** (the common case).
Expect: the bot asks specifically for the missing email — **no confirmation prompt, no tool
call** yet.
Reply with an email address.
Expect: proceeds exactly as US1 (confirmation → "כן" → creation).

## US3 — Share multiple contacts at once

In WhatsApp, select 2+ contacts and share them together in one message.
Expect: an immediate friendly reply asking to share contacts one at a time — **no confirmation
prompt, no OpenAI call, nothing created**. This should be near-instant (no AI round-trip).

## Notes

- All three scenarios are also covered by automated tests: US1/US2 by real-API E2E tests in
  `apps/denidin-app/tests/billed/` (`@pytest.mark.billed` — Feature 029 tier, text-only OpenAI
  calls, runs freely with no per-run approval, unlike the stricter `expensive` tier), US3 by a
  plain integration test (no OpenAI call needed at all, so not even `billed`).
- If US1/US2's confirmation prompt never appears and `add_client` fires immediately instead,
  that's a regression of the inherited Feature 026 approval gate — check
  `AIHandler.APPROVAL_REQUIRED_MCP_TOOLS` still contains `"add_client"` before assuming this
  feature's own code is at fault.
