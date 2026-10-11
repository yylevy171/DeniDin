# Contract: `backfill_prod_creds.local.json`

**Feature**: 061-prod-morning-ledger-backfill
**Path**: `apps/prod-ledger-backfill/config/backfill_prod_creds.local.json` (gitignored — matches
the `*.local.*` convention already used elsewhere in this repo, e.g.
`config/shared_state.local.json`, `docker-compose.*.local.yml`).
**Created**: once by hand, by a human, never committed, never generated or written by any script.

**Revised 2026-08-25**: corrects both the spec's original round-2 guess AND this planning pass's
own earlier (also wrong) "correction" — see `research.md` R6. Phase 1 talks to Morning's real API
directly via `MorningClient`, never through `morning-mcp-app`'s MCP server, so this file holds raw
Green Invoice API credentials, not an MCP bearer token.

## Shape

```json
{
  "api_key_id": "REAL_PROD_GREEN_INVOICE_API_KEY_ID",
  "api_key_secret": "REAL_PROD_GREEN_INVOICE_API_KEY_SECRET",
  "auth_url": "https://api.greeninvoice.co.il",
  "base_url": "https://api.greeninvoice.co.il/api/v1"
}
```

- **`api_key_id`** / **`api_key_secret`** (string, required): real prod Green Invoice API
  credentials — the same pair `apps/morning-mcp-app/config/config.prod.json`'s `api_key_id`/
  `api_key_secret` fields hold (gitignored, not read by this feature). Copy from
  `creds/DeniDin Prod Creds.txt`, this project's existing single source of truth for pasting real
  secrets from — never from `config.prod.json` itself (read-only reference, never copy-edited).
- **`auth_url`** (string, required): the OAuth2 token host — a genuinely different host than
  `base_url` for production (`research.md` R2), cannot be derived, must be supplied explicitly.
- **`base_url`** (string, required): the Green Invoice API host. Included explicitly (even though
  `MorningClient` has a same-value default) for auditability — a human reading this file should see
  exactly which API host a real backfill run will hit, not rely on a code default they can't see.

## Validation (REQ-BACKFILL-006, cross-cutting credential-security Acceptance Scenario 2)

Before making any real Morning API call, Phase 1 MUST:
1. Fail with a clear, friendly error if this file does not exist at the expected path.
2. Fail with a clear, friendly error if it exists but is malformed JSON, or is missing any of the
   four required fields.
3. Never fall back to any other credential source (no env var, no hardcoded default, no reuse of
   `apps/morning-mcp-app/config/config.prod.json` by direct read) if this file is missing/invalid.

## Sandbox credentials for Phase 2's method-selection experiment — a SEPARATE small file, same shape

**Resolved 2026-08-25 (speckit.analyze finding I2)**: `download.py`'s creds loader understands
exactly **one** shape — the four fields above — never a second, `morning-mcp-app`-native shape.
This keeps "no code branching on environment" literally true: there is no dual-format parsing
logic anywhere.

Concretely: `apps/prod-ledger-backfill/config/backfill_sandbox_creds.local.json` is a **second,
small, gitignored file the operator hand-creates**, in this exact same four-field shape, by
transcribing values from `apps/morning-mcp-app/config/config.test.json`'s existing sandbox
credentials (`api_key_id`/`api_key_secret`/`auth_url` copy over unchanged; that file's `api_url`
field becomes this file's `base_url`). It is **not** generated or read automatically from
`config.test.json` — it is a distinct file, created once by hand, the same way
`backfill_prod_creds.local.json` is. Phase 1's script accepts a `--creds-file` override
(`contracts/cli-contract.md`) so the exact same download logic is pointed at either file
interchangeably.

## What this file deliberately does NOT contain

- No OpenAI API key — only relevant if Method B is selected for Phase 3 (`research.md` R7); if so,
  Phase 3's own, separate small creds file/mechanism is designed at that point, not bundled into
  Phase 1's Morning credentials.
- No MCP bearer token, no `mcp.*` fields of any kind — this feature never talks to
  `morning-mcp-app-prod`'s MCP server.
- No prod WhatsApp/Green API credentials — this feature never sends or receives any WhatsApp
  message (REQ-BACKFILL-008).
