# Research: Fee Agreement Document Generation

## 1. Green API `sendFileByUpload` — does the installed client actually expose it?

**Decision**: Call it via `bot.api.sending.sendFileByUpload(chatId, file, fileName, caption=...)`,
mirroring how Feature 047 calls `bot.api.sending.sendInteractiveButtons` today
(`notification.answer_with_interactive_buttons` convenience wrapper) and Feature 054 calls
`bot.api.sending.sendMessage` for proactive delivery. Green API's public REST docs document a
`SendFileByUpload` endpoint (multipart form upload) as the standard way to send a document
attachment, and `whatsapp-api-client-python` (already pinned `>=0.0.53`) wraps the full REST
surface 1:1 by convention (every REST method has a same-named `sending.<method>` binding, as
already relied on for `sendInteractiveButtons`).

**Rationale**: Reuses an existing, already-proven dependency and call pattern instead of adding a
new HTTP client or hand-rolling multipart upload against Green API directly.

**Action required before trusting this in production (CONSTITUTION "NO UNVERIFIED THIRD-PARTY
ASSUMPTIONS")**: this plan does **not** treat the method's existence/signature as confirmed.
Task-list (Phase 2, `speckit.tasks`) MUST include an explicit early implementation task to
`inspect` the installed `whatsapp_api_client_python` version's `sending` module (or its own
README/CHANGELOG) for the real method name and required args, before writing
`send_document_response()` against an assumed signature. If the method is missing or shaped
differently than expected, this is a **blocking research finding**, not a silent workaround —
surface it to the human rather than substituting an alternative (e.g. a raw `requests` multipart
call) without approval, per the "no unverified assumption" and "config/behavior changes need
human sign-off" discipline running through this codebase.

**Alternatives considered**:
- Hand-rolled multipart `requests.post` directly against Green API's REST endpoint, bypassing the
  Python client entirely. Rejected for now — adds a second HTTP-calling code path alongside the
  existing client-wrapped one for no benefit, unless the client library turns out not to support
  the endpoint (fallback if the blocking task above finds a gap).
- A file-hosting/download-link approach (put the `.docx` somewhere and send a URL). Explicitly
  rejected by REQ-083-05 ("MUST NOT rely on external file hosting or complex download portals").

## 2. Live verification (Gate Zero) — when does this actually get exercised against production?

**Decision**: Same discipline as Feature 054's `send_proactive_message` — a real, live,
human-approved send is required at least once (in `dev`, with real WhatsApp) before this path is
considered production-ready, tracked as an explicit Acceptance-phase (`billed`, per METHODOLOGY
§VI) step, not assumed to work from unit tests alone (unit tests will necessarily use a fixture
notification/mock of the Green API network call per CONSTITUTION §I/§V's external-service
mocking allowance — they cannot substitute for one real live send).

**Rationale**: A `.docx` binary upload is meaningfully different from the plain-text/button sends
already proven live; formatting/encoding could silently corrupt in transit in a way no unit test
against a mocked HTTP layer would catch.

## 3. Temp file location and cleanup convention

**Decision**: `{data_root}/tmp/fee_agreements/<uuid>.docx`, deleted immediately after a
successful `sendFileByUpload` call, or after the tool-call's own retry policy (CONSTITUTION's
"retry once on 5xx/timeout after 1s, never retry 4xx") is exhausted on a failed send. No
`tempfile`/OS-temp-dir usage — keeping it under `data_root` keeps it inside the same
gitignored/environment-isolated data root every other piece of per-environment runtime state
already uses (`dev_data`/`data`), rather than introducing a second, differently-lifecycled
location.

**Rationale for immediate deletion over TTL/background sweep**: unlike sessions/reminders, a
generated fee agreement has no reason to be re-read later by the app itself — once delivered
(or irrecoverably failed to deliver) it is genuinely disposable. SC-003 ("no permanent files are
leaked") is best satisfied by deleting at the point of use rather than adding a second
sweeper service to clean up after a leak.

**Alternatives considered**: A dedicated `services/*_cleanup_service.py` sweep (mirroring the old
pre-070 `cleanup_service.py` pattern). Rejected as unnecessary complexity for a file whose whole
lifecycle (create → verify → send → delete) fits inside a single tool-call chain within one turn.

## 4. Approval-gate shape: does `generate_fee_agreement` need a `PendingLocalToolApproval`?

**Decision**: No. `generate_fee_agreement` dispatches immediately (like `list_reminders`,
`query_ledger_events` — read/generate-only, no external side effect yet), and the *actual* release
gate is REQ-083-04's self-verification step: the document is not sent to the user until the model
has called `verify_fee_agreement_document` and explicitly determined it's correct. Only the send
step is a real, irreversible external action (delivering a file to the client over WhatsApp) —
and per REQ-083-04 that step's gate is model self-verification, not a typed-reply/button human
approval like Reminders/Morning MCP mutations use.

**Rationale**: Spec language ("A document is only 'Released' (sent) once the model itself
approves it as correct") explicitly assigns the gate to the model's own verification, not a human
approval step — this is a deliberate, different UX from the existing `PendingApprovalManager`/
`PendingLocalToolApprovalManager` gates, not an oversight to fix. This should be called out
plainly in `runtime_constitution.md`'s new "Fee Agreement Generation" section so it isn't
mistaken for a corner cut.

**Open question flagged for the human (not resolved unilaterally)**: should sending the finished
`.docx` to the client *also* require a typed/button human approval (matching every other
external-facing action's UX in this codebase), on top of the AI's own self-verification? The spec
as written does not require it, but every other mutating/dispatching tool in this codebase does
have a human approval gate. Recommend raising this explicitly during `speckit.clarify`/`tasks`
review before implementation, rather than deciding it here.

## 5. Sourcing the N template variants from the historical prod corpus (REQ-083-01)

**Decision**: This is a **human-curated** step, not something this plan automates. Prod media
lives read-only at `~/denidin-winprod-data/media` (per CLAUDE.md's Windows-prod mount) and
contains real client documents — an agent should not unsupervised mine, rewrite, or template-ize
real client files. The task list will include a task to work *with* the human to select 3
representative historical fee agreements (or however many the human decides), manually redact
them into reusable `.docx` templates with `{{PLACEHOLDER}}`-style tokens, and hand those to
`config/fee_agreement_templates/` alongside a `manifest.json` describing each variant's
placeholders and selection cues (the three named in `user-stories.md` Stage 1 —
`hourly_consultation`, `retainer_agreement`, `fixed_price_project` — are a reasonable starting
set, but the exact count/N is confirmed with the human, not assumed fixed at exactly 3).

**Rationale**: REQ-083-01 says "derived from the historical corpus," not "auto-generated from
it" — human review before turning a real client's paperwork into a reusable template is the safer
and more defensible reading, especially since regenerated documents carry legal/financial
consequences (REQ-083-02's own anti-hallucination framing already treats this domain as
high-stakes).

## 6. Placeholder / self-verification format

**Decision**: `{{PLACEHOLDER_NAME}}` tokens inside the `.docx` (Word run-level find/replace via
`python-docx`, same library the existing `DOCXExtractor` already depends on for the reverse
direction — extraction). Verification reads the generated document's full text back
(`python-docx`'s own paragraph/table iteration — the same technique `DOCXExtractor` already uses)
and confirms (a) no `{{...}}` token remains and (b) every value the AI intended to insert appears
verbatim — exposed to the model as a tool result (extracted text + a structured "any placeholders
left?" boolean) so the *model* makes the final judgment call, per REQ-083-04's "AI self-verifies"
requirement, rather than the tool unilaterally deciding pass/fail.

**Rationale**: Reuses proven extraction machinery instead of adding a second DOCX-parsing
approach; keeps the actual accept/reject judgment with the model as the spec requires.
