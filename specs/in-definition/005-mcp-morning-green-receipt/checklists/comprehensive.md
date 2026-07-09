# Comprehensive Requirements Quality Checklist

**Feature**: 005-mcp-morning-green-receipt  
**Purpose**: Validate completeness, clarity, and consistency of all requirements before implementation  
**Created**: 2026-02-03  
**Updated**: 2026-07-08 (resolution pass — see below; further updated same day after
`send_invoice` was dropped during implementation — see the note under DEFERRED below)
**Type**: Multi-domain comprehensive review

---

## Resolution Status (2026-07-08 — scope-narrowed to the 7 invoice tools)

This checklist was authored against an over-broad, contradictory spec. After the 005
validation/rewrite (scope = 8 invoice-management tools, later 7 once `send_invoice` was
dropped during implementation — see below; receipt-parsing/webhook split to feature 017;
MCP framework = FastMCP/streamable-HTTP; flat config), items fall into three buckets:

**RESOLVED by the rewrite** (addressed in `spec.md` / `plan.md` / `artifacts/config.schema.json`):
- Auth & token lifecycle — CHK001, CHK006, CHK008, CHK042, CHK046 (JWT via `MorningAuth`,
  in-memory, refresh-before-expiry; `token_ttl_seconds`/`refresh_before_seconds` in config).
- API/endpoint mapping — CHK002, CHK009, CHK010, CHK012 (7 tool→endpoint table in spec;
  sandbox/prod URLs in `endpoints.md`; document type 305/320).
- Rate limit & retry — CHK003, CHK038, CHK099 (client-side ~3 req/s; urllib3 retry on 429/5xx).
- Tool schemas & validation — CHK013, CHK014, CHK015, CHK016 (per-tool `contracts/*.json` +
  Pydantic models; enums/required fields defined).
- Config — CHK055, CHK056, CHK057, CHK059, CHK060, CHK112 (flat schema, startup validation,
  no env vars).
- Error handling — CHK035, CHK039, CHK040, CHK041 (spec §Error Handling table; friendly
  messages, technical detail to logs).
- Data models — CHK024, CHK025, CHK028, CHK031 (Pydantic, real document shape, UTC).
- Security — CHK045, CHK052, CHK053 (config.json-only secrets, server-side only, HTTPS).
- Testing — CHK075, CHK076, CHK077, CHK079, CHK080, CHK083 (real-sandbox integration tests
  only; entry point = MCP tool; TDD RED-before-GREEN).
- I18n — CHK086, CHK089 (Hebrew/₪/DD-MM-YYYY in `formatters.py`).

**DEFERRED — out of scope for this P2 feature** (tracked, not blocking readiness):
- WhatsApp/email delivery ("send_invoice") — CHK065–CHK071, CHK117, CHK119 → **not deferred,
  dropped entirely** (2026-07-08, mid-implementation): Morning's public API has no
  documented endpoint to deliver a document at all — the only candidate
  (`/documents/{id}/distribute`) is confirmed (by diffing the full official API reference
  against the Postman collection) to be an undocumented, browser-session-only endpoint that
  consistently 400s for API-key auth. A `send_invoice` tool would only have recombined
  `get_invoice_details` + `download_invoice_pdf` with no real delivery behind it, so it was
  removed rather than shipped non-functional (see `tasks.md` T011, `spec.md` §Scope). These
  CHK items are N/A rather than deferred — there is no tool for them to apply to.
- Feature 003/004 dependencies — CHK072, CHK073, CHK123 → not applicable (app is standalone).
- Webhook / file-upload / receipt parsing — CHK004, CHK048 → moved to feature 017.
- Multi-tenant / scale / perf-SLA — CHK096–CHK105 → single sandbox tenant; revisit later.
- Runtime config hot-reload, multi-env, per-user overrides — CHK062–CHK064 → not needed now.
- Full 100+ Hebrew error-code mapping — CHK036 → map on demand from `artifacts/error_codes.json`.

**OPEN — nice-to-have, non-blocking** (address during implementation as they arise):
- Fuzzy client-name matching/thresholds — CHK017, CHK018, CHK115 → client (model) drives
  disambiguation via `add_client`/`list_invoices`; richer server-side resolution is a later
  enhancement.
- Observability depth — CHK106, CHK107, CHK108 → error-boundary logging (correlation ids,
  friendly-message mapping) done in T015; full app-wide log-file infrastructure (dedicated
  log file + per-test log files, mirroring denidin-app) queued as Phase 5 T019.

**Readiness verdict**: all *blocking* Completeness/Clarity/Consistency items for the 7-tool
scope are RESOLVED; remaining items are DEFERRED (out of scope) or OPEN (non-blocking).

## Implementation Status (2026-07-09)

Feature 005 is **implemented**, not just spec'd: Phases 1–3 of `tasks.md` are complete
(config/models/formatters, all 7 tools TDD'd against the real Morning sandbox, FastMCP
server verified end-to-end with a real MCP client), and Phase 4 (T015/T016 error mapping +
i18n, T017 Dockerfile + quickstart) is complete. 77/77 tests pass (unit + real-sandbox
integration, no mocks). Only `checklists` upkeep (this file) and Phase 5's queued
logging-infrastructure/start-stop-scripts/expensive-E2E-OpenAI-test follow-up remain.

---

## API Integration Requirements

### Requirement Completeness
- [ ] CHK001 - Are authentication flow requirements fully specified including JWT token refresh strategy? [Completeness, Spec §API Access]
- [ ] CHK002 - Are all 8 MCP tool-to-API endpoint mappings explicitly documented with request/response schemas? [Completeness, Gap]
- [ ] CHK003 - Are rate limit handling requirements defined (3 req/sec limit, retry strategy, backoff)? [Completeness, Spec §API Access]
- [ ] CHK004 - Are webhook callback URL requirements specified for async operations? [Gap]
- [ ] CHK005 - Are API error response handling requirements defined for all error codes? [Coverage, Exception Flow]

### Requirement Clarity
- [ ] CHK006 - Is the JWT token lifecycle (1-hour validity, refresh timing) quantified with specific timing thresholds? [Clarity, Spec §API Access]
- [ ] CHK007 - Are "case-sensitive API" validation requirements translated into specific parameter validation rules? [Clarity, Spec §Key Findings]
- [ ] CHK008 - Is the distinction between Bearer and Basic auth clearly defined for all endpoint types? [Clarity, Spec §Authentication Flow]
- [ ] CHK009 - Are sandbox vs production environment switching requirements clearly specified? [Clarity, Spec §API Access]

### Requirement Consistency
- [ ] CHK010 - Are API base URLs consistent between spec and implementation plan (use canonical sandbox `https://sandbox.d.greeninvoice.co.il/api/v1/` and production `https://api.greeninvoice.co.il/api/v1/`)? [Consistency, Spec §API Access]
- [ ] CHK011 - Are Hebrew language requirements consistent across error handling, responses, and user interactions? [Consistency, Spec §API Access]
- [ ] CHK012 - Do document type codes (305=invoice, 320=receipt) align across all tool definitions? [Consistency, Spec §Key Findings]

---

## MCP Tools Requirements

### Tool Input Schema Completeness
- [ ] CHK013 - Does each of the 8 MCP tools have complete input schema with all required and optional fields defined? [Completeness, Spec §2. MCP Tools]
- [ ] CHK014 - Are validation rules specified for all input parameters (e.g., amount > 0, date format YYYY-MM-DD)? [Gap]
- [ ] CHK015 - Are default values documented for all optional parameters? [Completeness, Spec §Tool 1-8]
- [ ] CHK016 - Are enum values exhaustively listed for status fields (paid/unpaid/overdue/cancelled)? [Completeness]

### Tool Behavior Clarity
- [ ] CHK017 - Is "client name disambiguation" behavior clearly defined with specific user interaction flow? [Clarity, Spec §Clarifications Q2]
- [ ] CHK018 - Are fuzzy matching algorithms/thresholds quantified for client name resolution? [Gap]
- [ ] CHK019 - Is the multi-step send_invoice workflow (update doc + send notification) explicitly sequenced? [Clarity, Spec §Key Findings]
- [ ] CHK020 - Are PDF download format requirements (Base64, size limits, encoding) specified? [Clarity, Spec §Tool 8]

### Tool Response Format Consistency
- [ ] CHK021 - Are response format requirements consistent across all 8 tools (Hebrew text, structured data, error messages)? [Consistency]
- [ ] CHK022 - Do success/failure response structures follow a consistent schema pattern? [Consistency]
- [ ] CHK023 - Are financial display formats (₪5,000.00 with VAT notation) consistently specified? [Consistency, Spec §Example 1]

---

## Data Models Requirements

### Model Completeness
- [ ] CHK024 - Are all Invoice model fields defined with types, constraints, and nullability? [Completeness, Spec §4. Data Models]
- [ ] CHK025 - Are Client model requirements complete including phone number (for WhatsApp delivery)? [Completeness, Spec §Clarifications Q4]
- [ ] CHK026 - Are Document model requirements specified for all document types (invoice, receipt, order)? [Coverage]
- [ ] CHK027 - Are Financial Summary model aggregation rules defined? [Gap]

### Model Field Clarity
- [ ] CHK028 - Is "invoice status" defined with measurable criteria for each state (paid, unpaid, overdue, cancelled)? [Clarity, Spec §Clarifications Q3]
- [ ] CHK029 - Are date/time fields specified with timezone requirements (Asia/Jerusalem)? [Clarity, Spec §Configuration]
- [ ] CHK030 - Is VAT calculation logic (17% rate, included vs excluded) explicitly defined? [Clarity, Spec §Configuration]
- [ ] CHK031 - Are currency fields specified with precision requirements (decimal places, rounding)? [Gap]

### Model Relationship Clarity
- [ ] CHK032 - Are Invoice-Client relationships clearly defined (required, optional, multiple clients)? [Clarity]
- [ ] CHK033 - Are Document-Payment linkage requirements specified? [Gap, Spec §API documentation]
- [ ] CHK034 - Are Business-Document ownership requirements defined? [Completeness, Spec §Businesses]

---

## Error Handling Requirements

### Error Scenario Coverage
- [ ] CHK035 - Are requirements defined for all API HTTP error codes (400, 401, 403, 404, 500, 429)? [Coverage, Spec §HTTP response codes]
- [ ] CHK036 - Are Hebrew error message translation/mapping requirements specified for all 100+ error codes? [Completeness, Spec §Error Codes]
- [ ] CHK037 - Are network failure recovery requirements defined (timeout, retry, circuit breaker)? [Gap, Exception Flow]
- [ ] CHK038 - Are rate limit exceeded (429) handling requirements specified with retry strategy? [Coverage, Exception Flow]

### Error Response Clarity
- [ ] CHK039 - Is the error response format structure clearly defined (errorCode + errorMessage in Hebrew)? [Clarity, Spec §Error Codes]
- [ ] CHK040 - Are user-friendly error message requirements specified for technical API errors? [Gap]
- [ ] CHK041 - Are validation error requirements defined for invalid input parameters? [Coverage]

### Error State Recovery
- [ ] CHK042 - Are token expiration recovery requirements defined (auto-refresh before 1-hour expiry)? [Gap, Recovery Flow]
- [ ] CHK043 - Are partial failure recovery requirements specified for multi-step operations? [Gap, Recovery Flow]
- [ ] CHK044 - Are requirements defined for handling API downtime/maintenance? [Gap, Exception Flow]

---

## Security Requirements

### Authentication & Authorization Completeness
- [ ] CHK045 - Are API key storage requirements defined (use `config/config.json` and organization secret injection)? [Completeness, Spec §Configuration]
- [ ] CHK046 - Are JWT token storage security requirements specified (in-memory, no persistence)? [Gap]
- [ ] CHK047 - Are authorization scope requirements defined for partner vs user API keys? [Gap, Spec §Partners]
- [ ] CHK048 - Are webhook signature verification requirements specified (X-Data-Signature HMAC SHA256)? [Completeness, Spec §Webhooks]

### Data Protection Requirements
- [ ] CHK049 - Are requirements defined for protecting sensitive client data (PII, financial info)? [Gap]
- [ ] CHK050 - Are API key rotation requirements specified? [Gap]
- [ ] CHK051 - Are requirements defined for securing PDF documents containing financial data? [Gap]

### Security Constraint Clarity
- [ ] CHK052 - Is the "CORS not supported - server-side only" constraint explicitly documented in architecture requirements? [Clarity, Spec §Key Findings]
- [ ] CHK053 - Are HTTPS-only requirements explicitly stated for all API communications? [Gap]
- [ ] CHK054 - Are requirements defined for handling compromised API keys? [Gap, Recovery Flow]

---

## Configuration Requirements

### Configuration Completeness
- [ ] CHK055 - Are all environment-specific config values defined (prod URL, sandbox URL, API keys)? [Completeness, Spec §Configuration]
- [ ] CHK056 - Are default value requirements specified for all configurable parameters? [Completeness, Spec §Configuration]
- [ ] CHK057 - Are config validation requirements defined (startup checks, missing values)? [Gap]
- [ ] CHK058 - Are MCP server registration requirements completely specified? [Completeness, Spec §MCP Server Config]

### Configuration Clarity
- [ ] CHK059 - Is the config file format (JSON) and schema clearly defined with examples? [Clarity, Spec §Configuration]
- [ ] CHK060 - Are `config/config.json` field naming conventions clearly specified? [Clarity, Spec §MCP Server Config]
- [ ] CHK061 - Is the distinction between user config and system defaults clearly defined? [Gap]

### Configuration Flexibility
- [ ] CHK062 - Are requirements specified for runtime config updates without restart? [Gap]
- [ ] CHK063 - Are multi-environment config requirements defined (dev, staging, prod)? [Gap]
- [ ] CHK064 - Are per-user config override requirements specified? [Gap]

---

## WhatsApp Integration Requirements

### Delivery Method Completeness
- [ ] CHK065 - Are WhatsApp delivery requirements completely specified (phone number required, no email fallback)? [Completeness, Spec §Clarifications Q4]
- [ ] CHK066 - Are PDF attachment requirements defined for WhatsApp delivery? [Gap]
- [ ] CHK067 - Are notification message format requirements specified (Hebrew text templates)? [Gap]
- [ ] CHK068 - Are requirements defined for handling missing phone numbers? [Completeness, Spec §Clarifications Q4]

### Integration Flow Clarity
- [ ] CHK069 - Is the DeniDin WhatsApp bot integration flow clearly sequenced? [Gap, Spec §Phase 5]
- [ ] CHK070 - Are invoice status notification trigger requirements clearly defined? [Gap, Spec §Phase 5]
- [ ] CHK071 - Is the send_invoice tool's WhatsApp delivery mechanism explicitly defined? [Gap]

### Integration Dependencies
- [ ] CHK072 - Are Feature 004 (MCP WhatsApp Server) integration requirements explicitly documented? [Completeness, Spec §Dependencies]
- [ ] CHK073 - Are Feature 003 (Media Processing) integration requirements for PDF handling documented? [Completeness, Spec §Dependencies]
- [ ] CHK074 - Are dependency version/compatibility requirements specified? [Gap]

---

## Testing Requirements

### Test Coverage Completeness
- [ ] CHK075 - Are sandbox environment testing requirements completely specified? [Completeness, Spec §API Access]
- [ ] CHK076 - Are test data requirements defined (sample invoices, clients, amounts)? [Gap]
- [ ] CHK077 - Are integration test requirements specified for all 8 MCP tools? [Gap, Spec §Implementation Plan]
- [ ] CHK078 - Are performance test requirements defined (rate limit testing, concurrent requests)? [Gap]

### Test Scenario Coverage
- [ ] CHK079 - Are happy path test scenarios defined for all 8 use cases? [Coverage, Spec §Use Cases]
- [ ] CHK080 - Are error scenario test requirements specified (API failures, validation errors)? [Coverage, Exception Flow]
- [ ] CHK081 - Are edge case test requirements defined (large amounts, special characters in Hebrew)? [Coverage, Edge Case]
- [ ] CHK082 - Are boundary condition test requirements specified (max 200 line items per document)? [Coverage, Edge Case, Spec §Error 2431]

### Test Environment Requirements
- [ ] CHK083 - Are sandbox account setup requirements clearly defined? [Clarity, Spec §API Access]
- [ ] CHK084 - Are test credit card requirements specified (5000 ILS limit for sandbox)? [Clarity, Spec §API Access]
- [ ] CHK085 - Are requirements defined for isolating test data from production? [Gap]

---

## User Experience Requirements

### Hebrew Language Requirements
- [ ] CHK086 - Are Hebrew response requirements consistently specified across all tools? [Consistency, Spec §Clarifications Q5]
- [ ] CHK087 - Are Hebrew error message display requirements defined? [Completeness, Spec §Error Codes]
- [ ] CHK088 - Are RTL (right-to-left) formatting requirements specified for text responses? [Gap]
- [ ] CHK089 - Are Hebrew number/currency formatting requirements defined (₪5,000.00)? [Clarity, Spec §Example 1]

### Natural Language Interaction
- [ ] CHK090 - Are natural language parsing requirements specified for invoice creation requests? [Gap]
- [ ] CHK091 - Are conversational response format requirements defined? [Gap]
- [ ] CHK092 - Are requirements specified for handling ambiguous user requests? [Gap]

### Response Format Requirements
- [ ] CHK093 - Are success message format requirements consistently defined across all tools? [Consistency]
- [ ] CHK094 - Are financial summary formatting requirements specified (readable tables, totals)? [Gap, Spec §Tool 6]
- [ ] CHK095 - Are date/time display format requirements defined (Hebrew locale)? [Gap]

---

## Non-Functional Requirements

### Performance Requirements
- [ ] CHK096 - Are response time requirements quantified for each MCP tool? [Gap, Measurability]
- [ ] CHK097 - Are concurrent request handling requirements specified? [Gap]
- [ ] CHK098 - Are caching strategy requirements defined for frequently accessed data? [Gap]
- [ ] CHK099 - Are rate limit adherence requirements specified to avoid 429 errors? [Completeness, Spec §API Access]

### Reliability Requirements
- [ ] CHK100 - Are uptime/availability requirements specified? [Gap, Non-Functional]
- [ ] CHK101 - Are failover/fallback requirements defined for API unavailability? [Gap, Recovery Flow]
- [ ] CHK102 - Are data consistency requirements specified across retries? [Gap]

### Scalability Requirements
- [ ] CHK103 - Are multi-user support requirements defined? [Gap]
- [ ] CHK104 - Are requirements specified for handling high invoice volume? [Gap]
- [ ] CHK105 - Are resource limit requirements defined (memory, connections)? [Gap]

### Monitoring & Observability
- [ ] CHK106 - Are logging requirements specified for API calls and errors? [Gap]
- [ ] CHK107 - Are metrics/telemetry requirements defined? [Gap]
- [ ] CHK108 - Are audit trail requirements specified for invoice operations? [Gap]

---

## Deployment Requirements

### Deployment Environment
- [ ] CHK109 - Are MCP server deployment requirements completely specified? [Gap, Spec §Implementation Plan]
- [ ] CHK110 - Are Python environment requirements defined (version, dependencies)? [Gap]
- [ ] CHK111 - Are Claude Desktop integration requirements specified? [Completeness, Spec §MCP Server Config]

### Configuration Management
- [ ] CHK112 - Is configuration management via `config/config.json` (including secret injection process) defined? [Completeness, Spec §MCP Server Config]
- [ ] CHK113 - Are secrets management requirements specified (API key storage)? [Gap]
- [ ] CHK114 - Are deployment validation requirements defined (health checks)? [Gap]

---

## Ambiguities & Conflicts

### Identified Ambiguities
- [ ] CHK115 - Is "fuzzy matching" for client names quantified with specific algorithm/threshold? [Ambiguity, Spec §Tool 5]
- [ ] CHK116 - Is "financial summary" aggregation logic explicitly defined? [Ambiguity, Spec §Tool 6]
- [ ] CHK117 - Is the behavior of send_invoice when both email and phone exist clearly defined? [Ambiguity]
- [ ] CHK118 - Are "bulk operations" requirements clearly scoped (limits, transaction handling)? [Ambiguity, Spec §Use Case 8]

### Potential Conflicts
- [ ] CHK119 - Is there consistency between "WhatsApp-first delivery" and API email capabilities? [Conflict, Spec §Clarifications Q4]
- [ ] CHK120 - Are document type requirements (invoice vs receipt) consistently applied across tools? [Consistency]
- [ ] CHK121 - Is the relationship between "Best subscription required" and testing requirements clear? [Gap]

---

## Dependencies & Assumptions

### External Dependencies
- [ ] CHK122 - Are Morning API availability assumptions validated? [Assumption, Spec §Phase 0]
- [ ] CHK123 - Are Feature 004 (MCP WhatsApp) completion requirements explicitly stated? [Dependency, Spec §Dependencies]
- [ ] CHK124 - Are third-party library dependencies documented? [Gap]

### System Assumptions
- [ ] CHK125 - Is the assumption of "single active business per account" validated? [Assumption, Spec §Businesses]
- [ ] CHK126 - Are timezone assumptions (Asia/Jerusalem) explicitly documented? [Assumption, Spec §Configuration]
- [ ] CHK127 - Are currency assumptions (ILS only) validated against requirements? [Assumption, Spec §Configuration]

---

**Summary Statistics**:
- Total Items: 127
- Requirement Completeness: 36 items
- Requirement Clarity: 32 items
- Requirement Consistency: 14 items
- Coverage (Scenarios/Edge Cases): 19 items
- Gaps Identified: 58 items
- Ambiguities/Conflicts: 8 items

**Next Steps** (superseded by the Resolution Status section at the top, 2026-07-08):
- Blocking items for the 8-tool scope are resolved in `spec.md`/`plan.md`; out-of-scope
  items are explicitly deferred (WhatsApp → future; receipt-parsing → feature 017;
  scale/perf → later). Proceed to implementation via `tasks.md` under the TDD gates.

> Note: the original 127-item statistics below reflect the pre-rewrite over-broad spec and
> are retained for history; see the Resolution Status section for the current disposition.