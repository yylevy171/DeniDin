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

## 4. Approval-gate shape: does anything about this flow get a human `PendingLocalToolApproval`?

**Decision (human-confirmed 2026-09-12)**: There IS a human approval step, but it gates the
**collected details**, not the finished document. Before `generate_fee_agreement` is called, the
AI's proposed placeholder values (client name, fee amount, scope, dates, etc.) are presented to
the user as a normal `PendingLocalToolApproval` typed-reply/button confirmation — the same UX
Reminders already use — so the human confirms "yes, these are the right numbers" before a single
byte of the document is generated. Once approved, `generate_fee_agreement` →
`verify_fee_agreement_document` → send proceeds with **no further human gate**: the AI's own
self-verification (REQ-083-04) is the sole release gate for the document itself, exactly as the
spec states. If the user is unhappy with the *finished document* after delivery, the resolution is
a fresh regeneration request in a new turn (potentially with corrected details, going through the
same details-approval gate again) — never a way to edit or re-approve the already-sent file.

**Rationale**: Matches the existing approval-gate pattern (confirm-before-acting) for the part
that's genuinely still fallible — the AI's data collection/interpretation — while keeping REQ-083-04's
explicit intent that the document's own correctness is machine-verified, not human-gated
line-by-line (a human re-reading full legal boilerplate on WhatsApp before every send would defeat
the point of automating this at all).

**Local tool schema/flow update**: `generate_fee_agreement` now creates a `PendingLocalToolApproval`
(same manager as reminders — see `handlers/ai_handler.py`'s existing pattern) instead of
dispatching immediately as `doc-template-engine.md`'s original contract said. `contracts/` is
updated accordingly.

## 5. Sourcing the N template variants (REQ-083-01)

**Decision (human-confirmed 2026-09-12): creating the templates is an implementation task for
this agent, not something deferred to the human.** This clone has no read access to the prod
media corpus (`~/denidin-winprod-data/media` is a root-clone-only sshfs mount, not set up here,
and per CLAUDE.md is real client data an agent should not mine unsupervised regardless). The three
variants named in `user-stories.md` Stage 1 — `hourly_consultation`, `retainer_agreement`,
`fixed_price_project` — were authored from scratch as generic, standard legal-services fee
agreement boilerplate (parties, scope, fee terms, signature block), with `{{PLACEHOLDER}}` tokens,
via `python-docx`. These are checked into `config/fee_agreement_templates/` (see plan.md's Project
Structure) alongside `manifest.json`. They are a deliberately generic starting point — the human
can swap in prod-derived language/branding later (a template-content change, not a
placeholder-contract change) without touching any code.

**Addendum (human feedback, 2026-09-12): a 4th variant, `multi_component_agreement`, was added**
to distinguish a single, simple fee arrangement (one rate/fee, one scope — what the original 3
variants already cover) from a multi-component engagement, where the client's request describes
several distinct, separately-priced fee items in one agreement (e.g. "a retainer plus hourly
overage past X hours," or "a one-time setup fee plus a monthly fee").

**Second addendum (same day, human correction): "the multi variant should apply for any N>1."**
The first draft of this variant capped the fee table at 3 pre-declared component slots
(`COMPONENT_1/2/3_*`), which does not satisfy "any N" — a 4th, 5th, etc. real component would
have had nowhere to go. Replaced with a **repeating-row design**: the template `.docx` declares
exactly ONE generic table row (`{{COMPONENT_NAME}}`/`{{COMPONENT_DESCRIPTION}}`/`{{COMPONENT_FEE}}`),
and `generate_fee_agreement` takes a `components` list (any length ≥ 2) instead of N indexed
placeholder groups; `DocTemplateEngine.generate()` clones that one row once per list entry at
generation time. See `data-model.md`'s "Variable-length component rows" section and the
`doc-template-engine.md` contract's updated `generate()` signature (`components:
list[dict[str,str]] | None`) for the full design. Each of the 4 variants' `selection_cues` in
`manifest.json` now explicitly states its single-vs-multi-component character, so the AI's
variant-selection judgment call has this distinction available directly from the manifest content
it already reads, rather than needing separate constitution-level guidance to infer it.

**Rationale**: REQ-083-01 requires N variants to exist and be selectable; it does not require them
to be verbatim derivations of specific historical documents. Given no accessible corpus from this
clone, a correct, generic starting set unblocks the rest of the pipeline (selection, generation,
verification, delivery) without waiting on a human curation pass that isn't this feature's
critical path.

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
