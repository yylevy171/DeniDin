# Implementation Plan: Fee Agreement Document Generation

**Branch**: `feature/083-fee-agreement-docs` | **Date**: 2026-09-12 | **Spec**: `spec.md`
**Input**: Feature specification from `specs/repo/features/083-fee-agreement-docs/spec.md`

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I-III): no environment variables, `now_local()` (Israel local time),
  `pathlib.Path`, feature-branch git workflow, no monkey-patching, friendly user-facing errors.
- **METHODOLOGY.md** (§II, IV, VII): phased planning, Integration Contracts for the
  multi-component pieces below (AI ↔ DocTemplateEngine tool, AI ↔ self-verification tool,
  WhatsAppHandler ↔ Green API `sendFileByUpload`).

---

## Summary

A godfather/admin user asks DeniDin (in natural Hebrew/English) to draft a fee agreement. The AI
picks the right template variant, asks only for whatever data it cannot find in the CRM/ledger or
the conversation (never guessing financial/legal terms), calls a new local `generate_fee_agreement`
tool that fills a `.docx` template with `python-docx`, calls a second local
`verify_fee_agreement_document` tool to read the generated file back and confirm every placeholder
was replaced correctly, and only then sends the file to the user as a WhatsApp document attachment
via Green API's `sendFileByUpload`. The temporary `.docx` is deleted after a successful send (or
after a bounded number of failed send attempts) so nothing accumulates on disk.

## Technical Context

**Language/Version**: Python 3.11 (existing `apps/denidin-app` codebase)
**Primary Dependencies**: `python-docx>=1.0.0` (already a dependency, used today only for
*extraction* by `DOCXExtractor` — this feature is its first *generation* use), OpenAI Responses
API (`ai_handler.py`, local `type: "function"` tools — same pattern as reminders/ledger tools),
`whatsapp-api-client-python` (`bot.api.sending` — NEEDS CLARIFICATION: confirm the installed
version's `sending` module actually exposes a `sendFileByUpload` (or equivalently-named) call
before relying on it; Green API's own REST API documents this endpoint, but per CONSTITUTION's
"no unverified third-party assumption" rule this must be confirmed against the real installed
client/library and, ultimately, a real live send (Gate Zero — same discipline Feature 054 applied
to `send_proactive_message`) before being trusted in production).
**Storage**: New — a small, git-tracked template directory
(`apps/denidin-app/config/fee_agreement_templates/`, mirrors `runtime_constitution.md`'s
"shared, git-tracked config content" pattern, not per-environment `data_root`) holding the N
`.docx` template variants plus a manifest describing each variant's placeholders and the
natural-language cues the AI should use to select it. Temporary generated `.docx` files live
under `{data_root}/tmp/fee_agreements/` (NEEDS CLARIFICATION in research.md: exact temp-path
convention, and confirming no other feature already claims a `tmp/` root under `data_root`).
**Testing**: `pytest` unit tests for `DocTemplateEngine` (real `python-docx` calls against a
small fixture template — no mocking of internal code, per CONSTITUTION §I/§V), unit tests for the
verification tool's placeholder-detection logic; `billed` Acceptance-phase tests (per METHODOLOGY
§VI's TDD redefinition) for the full ask → clarify → generate → self-verify → send conversation
flow, one per UAT stage in `user-stories.md`.
**Target Platform**: Existing `denidin-app` Docker container (dev/prod), no new deployable.
**Project Type**: Single project — all changes are inside `apps/denidin-app/`.
**Performance Goals**: Not latency-sensitive beyond the existing OpenAI/tool-call turn budget;
`python-docx` fill + verify of a single-page template is sub-second.
**Constraints**: No permanent files left behind (SC-003) — the temp `.docx` must be deleted
after dispatch (success or a final failure), never relying on OS temp-dir GC. No hallucinated
financial/legal values ever reach the template (REQ-083-02) — enforced by tool contract
(`generate_fee_agreement` requires every placeholder value as an explicit argument; the AI
cannot omit one and have the tool silently default it).
**Scale/Scope**: RBAC-gated to godfather/admin only (same tier as reminders/Morning tools);
4 initial template variants (`hourly_consultation`, `retainer_agreement`, `fixed_price_project` —
each a single, simple fee arrangement — plus `multi_component_agreement`, added per human
feedback 2026-09-12 for engagements with several distinct, separately-priced fee items in one
agreement), authored as generic boilerplate by this implementation (no access to the prod media
corpus from this clone — see Research #5), checked into `config/fee_agreement_templates/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **No env vars**: template directory path and temp-file root come from `AppConfiguration`
  (`config.fee_agreements` block), not env vars. ✅ planned.
- **Israel local time**: any timestamp embedded in a generated document (e.g. a "date" field) or
  logged around this feature uses `now_local()`. ✅ planned.
- **No monkey-patching**: `DocTemplateEngine` is a new class instantiated and injected the same
  way `ReminderManager`/`LedgerEventManager` are — no runtime patching of `python-docx` or the
  Green API client. ✅ planned.
- **`pathlib.Path`**: template lookup and temp-file paths use `Path`. ✅ planned.
- **Feature flag**: new behavior gated under `config.feature_flags.fee_agreement_docs`, default
  `false`; when disabled, no new tools are attached and the AI behaves exactly as before. ✅
  planned.
- **RBAC**: `generate_fee_agreement`/`verify_fee_agreement_document` tools are attached only for
  godfather/admin roles, mirroring reminders/ledger tools. ✅ planned.
- **Human approval gate (human-confirmed 2026-09-12)**: `generate_fee_agreement` creates a
  `PendingLocalToolApproval` over the *collected placeholder values* (same UX as reminders) —
  the human confirms the data before any document is generated. The generated document itself is
  gated only by the AI's own self-verification (REQ-083-04) — no second human approval on the
  finished file. See research.md #4. ✅ planned.
- **Runtime constitution boundaries (CLAUDE.md "EVERY NEW TOOL-BEARING FEATURE...")**: a new
  "Fee Agreement Generation" section in `runtime_constitution.md` is REQUIRED — scope (when this
  applies), explicit non-scope (this is not a general document-editing or general-DOCX-creation
  tool; not used for invoices/receipts — those stay Morning MCP tools; not used for reminders),
  and a restatement that ambiguous short replies mid-flow answer the pending clarification
  question in this same context, never a reinterpretation into another tool domain. Every other
  tool-bearing section (Reminders, Ledger, Morning MCP) needs a one-line cross-reference back
  excluding fee-agreement generation from their own scope. ✅ planned — tracked as an explicit
  Phase 1 task in `tasks.md` (speckit.tasks), not optional polish.
- **Integration Contracts (METHODOLOGY §VII)**: multi-component — AI ↔ `DocTemplateEngine` tool,
  AI ↔ self-verification tool, `WhatsAppHandler` ↔ Green API `sendFileByUpload`. See `contracts/`.

No violations requiring Complexity Tracking at this stage.

## Project Structure

### Documentation (this feature)

```text
specs/repo/features/083-fee-agreement-docs/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   ├── doc-template-engine.md
│   ├── fee-agreement-verification.md
│   └── whatsapp-file-delivery.md
└── tasks.md              # Phase 2 output (speckit.tasks — not this command)
```

### Source Code (repository root)

```text
apps/denidin-app/
├── config/
│   ├── fee_agreement_templates/         # NEW — N .docx template variants + manifest.json
│   │   ├── manifest.json                # variant id -> {filename, placeholders[], selection_cues}
│   │   ├── hourly_consultation.docx
│   │   ├── retainer_agreement.docx
│   │   └── fixed_price_project.docx
│   └── runtime_constitution.md          # NEW "Fee Agreement Generation" section +
│                                          # cross-references from Reminders/Ledger/Morning MCP
├── src/
│   ├── managers/
│   │   └── doc_template_engine.py       # NEW — loads a variant, fills placeholders via
│   │                                      # python-docx, writes temp .docx, exposes a
│   │                                      # verify() read-back for the self-verification tool
│   ├── handlers/
│   │   ├── ai_handler.py                # NEW local tools: generate_fee_agreement (creates a
│   │   │                                  # PendingLocalToolApproval over the collected values,
│   │   │                                  # same UX as reminders), verify_fee_agreement_document
│   │   │                                  # (dispatches immediately, read-only). Both RBAC-gated,
│   │   │                                  # godfather/admin only. The document itself is gated
│   │   │                                  # only by AI self-verification (REQ-083-04) - no
│   │   │                                  # second human approval on the finished file.
│   │   └── whatsapp_handler.py          # NEW send_document_response() path using Green
│   │                                      # API sendFileByUpload; deletes the temp file after
│   │                                      # a successful send or after retry exhaustion
│   └── models/
│       └── fee_agreement.py             # NEW — FeeAgreementVariant / GeneratedDocument
│                                          # dataclasses
└── tests/
    ├── unit/
    │   ├── test_doc_template_engine.py       # NEW
    │   └── test_whatsapp_handler.py          # extended for document-send path
    └── billed/
        └── test_fee_agreement_generation_flow.py  # NEW — Acceptance-phase, per UAT Stages 1-4
```

**Structure Decision**: Single project, all within `apps/denidin-app/`. No changes to
`apps/morning-mcp-app/` — fee agreements are not Morning/Green-Invoice documents, and REQ-083-02
explicitly allows (but does not require) *reading* the ledger/CRM for known values, which already
goes through existing `LedgerEventManager`/Morning MCP read tools the AI already has access to
when godfather/admin.

## Complexity Tracking

*No Constitution Check violations at this stage — table intentionally empty.*
