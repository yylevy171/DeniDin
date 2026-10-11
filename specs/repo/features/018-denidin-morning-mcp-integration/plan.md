# Implementation Plan: DeniDin ↔ Morning MCP Integration — Feature 018

**Feature**: 018-denidin-morning-mcp-integration
**Branch**: `feature/018-denidin-morning-mcp-integration`
**Spec**: `./spec.md` · **User stories**: `./user-stories.md`
**Status**: Ready for Task Generation
**Estimated Duration**: 4–7 days
**Updated**: July 12, 2026

**Compliance**: CONSTITUTION.md (§I no env vars, §II UTC, §III git workflow, §V real-E2E
integration tests, §VIII test immutability, §X friendly errors, §XVII no monkey-patching) and
METHODOLOGY.md (§I spec-first, §VI TDD, §VII integration contracts). Note decision #5:
pre-production, so no new feature flags and no backward-compat old-path retention — the
Chat-Completions call sites are replaced, not gated.

---

## Summary

Bring Feature 005's proven "OpenAI Responses API → remote MCP → Morning sandbox over ngrok"
path into denidin's live WhatsApp reply flow. Replace all denidin Chat-Completions calls with
the Responses API; on the conversational reply, attach the Morning server as a remote MCP tool
for godfather/admin, using the current tunnel URL discovered from a shared status file the
Morning app publishes, authenticated by a shared bearer token. Degrade gracefully when the
server is down. Teach the model tool scope + confirmation via the runtime constitution. Cover
everything with real-API E2E tests through the real Green API webhook router.

## Technical Context

- **Language/Version**: Python 3.11 (denidin-app).
- **Primary Dependencies**: existing `openai` SDK (Responses API), `tenacity` (retry),
  `green-api` bot router. No new runtime deps expected (the `ngrok` CLI is only needed by the
  expensive tests, as in Feature 005).
- **Storage**: none new (status file is transient runtime state, not persisted app data).
- **Testing**: real-API E2E only (`@pytest.mark.expensive`), entry point = Green API webhook
  through `@bot.router.message`; independent sandbox verification via `MorningClient`.
- **Target Platform**: existing denidin runtime (local + Docker + docker-compose).
- **Constraints**: no env vars; UTC; `pathlib.Path`; no monkey-patching; friendly errors;
  no cross-app imports; tests immutable once approved.

## Constitution Check (pre-Phase 0)

- **No env vars** — PASS: new `mcp` block in `config/config.json`, loaded via
  `AppConfiguration`; bearer token + status-file path + label come from config.
- **UTC** — PASS: status-file `updated_at` and freshness check use `datetime.now(timezone.utc)`.
- **Feature branch** — PASS: `feature/018-denidin-morning-mcp-integration`.
- **Feature flags** — N/A by decision #5 (pre-production, no gating). This is an explicit,
  documented deviation from §I's feature-flag guidance, justified by "not in production" and
  tracked in Complexity Tracking below.
- **Real-E2E tests / ZERO-MOCKING** — MUST ADHERE: every story gets a failing real-API E2E test
  approved before implementation; no mocks; independent sandbox verification.
- **No monkey-patching** — PASS: `MorningMcpLocator` injected into `AIHandler`; no runtime
  attribute/method replacement.
- **Test immutability** — PASS: once approved, tests are not rewritten during buildout.

## Integration Contracts (METHODOLOGY §VII)

### Morning app ↔ DeniDin — status file
- **Morning app MUST**: on tunnel-up, atomically write
  `{"server_url": "<https>/mcp", "updated_at": "<UTC ISO>"}` to `mcp.status_file`; remove/clear
  it on shutdown. Never write a URL without the `/mcp` suffix.
- **Morning app PROVIDES**: a file whose `server_url` is currently reachable and whose
  `updated_at` reflects when the tunnel was (re)established.
- **DeniDin EXPECTS**: a readable JSON file; treats missing/unparseable/stale (per
  `url_max_age_seconds`) as "server down".

### `MorningMcpLocator` ↔ `AIHandler`
- **AIHandler MUST**: call `locator.current_server_url()` before building the reply request;
  attach the MCP tool only if it returns a non-None URL **and** role ∈ {godfather, admin}.
- **Locator PROVIDES**: `current_server_url() -> Optional[str]` (fresh URL or None); never
  raises to the caller (internal errors → None + WARNING log).
- **Locator EXPECTS**: a config `mcp` dict (path, max age, label, token). No network calls —
  purely file-based (the URL is exercised by OpenAI, not pinged by denidin).

### `AIHandler` ↔ OpenAI Responses API
- **AIHandler MUST**: send `instructions` (system prompt) + `input` (history + user message);
  pass the MCP `tools` list when authorized; read `output_text` + `usage`.
- **OpenAI PROVIDES**: `response.output` (incl. `mcp_call` items), `response.output_text`,
  `response.usage`. Orchestrates the tool round-trip within the single `create()` call.

## Project Structure

### Source (denidin-app)
```text
apps/denidin-app/
├── config/config.example.json            # + mcp{} block
├── denidin.py                            # register mcp field in inline filter; wire locator
├── src/
│   ├── models/config.py                 # + mcp dataclass field + defaults + validate
│   ├── handlers/
│   │   ├── morning_mcp_locator.py       # NEW — status-file → current URL (or None)
│   │   ├── ai_handler.py                # Responses API reply + summarization; MCP tool attach
│   │   └── extractors/image_extractor.py# Responses API vision (input_image)
│   └── ...
├── data/constitution/runtime_constitution.md   # + tool-usage + confirmation section
└── tests/expensive/
    ├── denidin_mcp_e2e_helpers.py       # NEW — ngrok tunnel + morning-server subprocess + webhook helpers
    └── test_denidin_morning_mcp_e2e.py  # NEW — full matrix + scenarios
```

### Source (morning-mcp-app)
```text
apps/morning-mcp-app/
├── config/{config.example.json, config.schema.json}   # + mcp.status_file
├── run_morning_mcp.sh · docker-entrypoint.sh          # publish/clear status file on tunnel up/down
└── (a helper to write the status JSON, reusing the existing URL fetch)
```

**Structure Decision**: `MorningMcpLocator` is a new thin handler injected into `AIHandler`
(dependency injection, no globals). The Responses migration is localized to `ai_handler.py` +
`image_extractor.py`. The Morning-side change is confined to the tunnel scripts + one small
status-writer + a config field — the server code is untouched.

## Phased Execution

### Phase 0 — Research (DONE)
The end-to-end path (`responses.create` + remote MCP + ngrok + bearer + sandbox verification)
is already proven by Feature 005 T021. The denidin call sites, config-loading behavior (unknown
-key stripping), RBAC role resolution, and router dispatch are mapped (see exploration in the
approved plan). **Checkpoint**: no unknowns block implementation.

### Phase 1 — Config + Locator + Morning status publishing (foundation)
denidin `mcp` config field + `MorningMcpLocator`; Morning-app status-file publishing. These are
prerequisites the E2E tests need to point denidin at the running server.

### Phase 2 — Responses API migration (per call site, TDD)
Replace reply, summarization, and vision calls with the Responses API. Reply path gains
role-gated MCP tool attachment. Existing approved tests coupled to Chat Completions get a
single §VIII-approved migration up front.

### Phase 3 — Runtime constitution + E2E matrix (TDD, real API)
Add the runtime-constitution tool section; author the full E2E matrix (per-tool positive +
negative, RBAC/scope/degrade, multi-turn scenarios), each RED-then-approved-then-GREEN.

### Phase 4 — Polish
Audit logging (REQ-SEC-002), README/quickstart notes for running both apps together
(docker-compose: shared token + status file + tunnel), config.example updates.

## Complexity Tracking

- **Deviation**: no feature flags / no backward-compat old-path retention (normally required by
  CONSTITUTION §I/§VI). **Justification**: app is pre-production (explicit user decision #5);
  retaining dual paths adds untested complexity with no production consumer to protect. The
  invariant that replaces it is test immutability (§VIII) — approved tests do not churn.
- No other deviations (no env vars, no DB, no mocks, no monkey-patching).
