# MCP → Morning (Green Invoice) — Feature 005 (Invoice Management)

This directory is the **single authoritative** location for Feature 005: an MCP server
exposing **8 invoice-management tools** over the Morning (Green Invoice) API, implemented in
`apps/morning-mcp-app/`.

**Status**: Ready for Implementation (P2). Start from `tasks.md` under the TDD gates in
`.github/METHODOLOGY.md` and `.github/TDD-ENFORCEMENT.md`.

## Canonical artifacts
- `spec.md` — functional spec, 8 tools, flat config, technology choice, testing strategy.
- `plan.md` — technical plan, phases, integration contracts, constitution checks.
- `tasks.md` — single ordered task list (TDD A/B; real-sandbox tests only).
- `user-stories.md` — Given-When-Then; entry point = MCP tool call (not `@bot.router`).
- `data-model.md` — Pydantic models mapping the real Morning document shape.
- `contracts/` — JSON contracts for the 8 invoice tools + `morning_token_exchange`.
- `artifacts/config.schema.json` — **flat** config schema (matches the real app config).
- `endpoints.md`, `research.md`, `quickstart.md`, `checklists/comprehensive.md`.

## Key constraints
- **No environment variables** — all runtime config from flat `config/config.json`
  (`api_key_id`/`api_key_secret`/`api_url` at top level), validated against
  `artifacts/config.schema.json` (CONSTITUTION §I).
- **Real-sandbox integration tests only** — no mocks, no mock-based unit tests
  (CONSTITUTION §V + ZERO-MOCKING).
- **Self-contained** — no dependency on `apps/denidin-app/`.

## Related / out of scope
- **Receipt parsing / file-upload / webhook** product → split to
  `specs/in-definition/017-mcp-morning-receipt-parsing/`.
- **WhatsApp delivery from denidin-app's number** → future feature, architecture TBD
  (see `spec.md` §Future Work). `send_invoice` here uses Morning's native send only.

## History
- Pre-consolidation snapshots are preserved under `specs/archive/005-mcp-morning-green-receipt/`
  (historical record — never edited or deleted).
