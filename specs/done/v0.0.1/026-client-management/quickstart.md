# Quickstart: Client Management (Feature 026)

Manual verification scenarios once implementation lands, covering the five user stories.
Requires: `apps/morning-mcp-app` running (dev, real sandbox) per the "ONE ENVIRONMENT SET AT A
TIME" rule and its own `run_morning_mcp.sh dev`; `apps/denidin-app` running dev with a godfather
WhatsApp number configured. **Starting either environment always needs explicit approval —
nothing below authorizes that on its own.**

## Prerequisites

- `apps/morning-mcp-app/config/config.dev.json` has real Morning sandbox credentials.
- `apps/denidin-app/config/config.dev.json`'s `mcp` block points at the running Morning server's
  status file, and the sender's WhatsApp number resolves to `godfather` or `admin`.

## US1 — List clients (read-only, no approval wait)

Send: `"מי הלקוחות שלי?"`
Expect: an immediate Hebrew reply listing existing client names (no confirmation prompt).
Verify: cross-check against `MorningClient.search_clients({})` directly (or the Morning web UI)
that the listed names match reality.

## US2 — View a specific client's details (read-only, no approval wait)

Send: `"פרטים על הלקוח <name>"` for a known client.
Expect: an immediate reply with name/email/phone/tax_id.
Edge case — no match: send a name that doesn't exist → friendly "not found" reply, no crash.
Edge case — ambiguous match: seed two similarly-named clients, send the shared substring → reply
lists both candidates and asks which one, no details returned for either.

## US3 — Add a client (approval-gated, mandatory fields)

Send: `"הוסף לקוח Quickstart Test, טלפון 050-1111111, מייל qs@example.com"`
Expect turn 1: a Hebrew confirmation question (e.g. "ליצור לקוח חדש: Quickstart Test, טלפון
050-1111111, מייל qs@example.com? (כן/לא)") — **no client created yet**.
Send turn 2: `"כן"`
Expect: confirmation the client was created.
Verify: `get_client_details` (or the Morning web UI) shows the new client — **phone must read
back as `050-1111111`** (normalized), confirming REQ-CLIENT-014/017.

Edge case — missing mandatory field: send `"הוסף לקוח Quickstart Test 2"` (no phone/email) →
expect the bot asks for the missing fields, not a confirmation prompt.
Edge case — malformed email: send with `"מייל not-an-email"` → expect a friendly validation
error before any confirmation prompt.
Edge case — decline: on turn 1's confirmation, reply `"לא"` → expect no client created, a
cancellation acknowledgement.

## US4 — Update a client (approval-gated)

Using the client created in US3:
Send: `"עדכן את הטלפון של Quickstart Test ל-050-2222222"`
Expect turn 1: a confirmation question, no change yet.
Send turn 2: `"כן"`
Expect: confirmation the phone was updated.
Verify: `get_client_details` shows the new phone (`050-2222222`), and — importantly — `email` is
still `qs@example.com` (proving the update was partial, not a full-record overwrite — the
research.md Decision 3 assumption).

## US5 — RBAC denial

From a non-godfather/admin (`client`-role) WhatsApp number, send `"מי הלקוחות שלי?"`.
Expect: a normal reply with no client data — no MCP tool was available to the model at all.
Verify: no `list_clients`/`get_client_details`/`add_client`/`update_client` call appears in logs
for that turn.

## Cleanup

Client records created during manual verification are sandbox data — no cleanup mechanism is
required (delete is out of scope for this feature, per spec.md).
