# Specification Quality Checklist: Client Management (Morning/Green Invoice CRM Clients)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: July 29, 2026
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — resolved across two clarification rounds
      2026-07-29 (behavior/scope, then field scope); see spec.md Clarifications.
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined (see `user-stories.md`)
- [x] Edge cases are identified
- [x] Scope is clearly bounded (In scope: list/view/add/update on exactly 4 client fields —
      `name`, `email`, `phone`, `tax_id` — via existing MCP integration; Out of scope: delete,
      `address` + richer schema fields, RBAC changes, invoice-side client referencing)
- [x] Dependencies and assumptions identified (Assumptions section — Green Invoice API
      list/update support must be verified in Phase 0 research; delete needs no such check since
      it's out of scope)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows (list, view, add-with-approval, update-with-approval,
      RBAC-denial)
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification (Technology Choice section documents the
      *integration pattern* being reused, not new implementation detail)

## Notes

- All clarifications resolved 2026-07-29 directly with the user across two rounds (see spec.md
  Clarifications):
  - Round 1: delete dropped from scope entirely; `add_client`/`update_client` both now require
    explicit approval (reversing Feature 022's `add_client` exemption); `tax_id` is freely
    editable; invoice client-referencing stays unchanged here and is split into its own backlog
    spec (`specs/backlog/027-mandatory-client-reference-invoicing/`).
  - Round 2 (field scope, grounded in the checked-in Green Invoice Postman collection): exactly
    4 fields in scope (`name`, `email`, `phone`, `tax_id`); `name`/`email`/`phone` mandatory at
    creation (AI asks for missing ones); `address` and all richer schema fields (mobile, city,
    country, contactPerson, bank details, labels, paymentTerms, category) explicitly excluded.
    Also surfaced and required a fix (REQ-CLIENT-014) for a stale code comment incorrectly
    claiming `phone` isn't supported by the real API.
  - Round 3 (format validation/normalization, grounded in Morning's full error-code catalog,
    `specs/done/005-mcp-morning-green-receipt/artifacts/error_codes.json`): email is validated
    client-side via `email-validator`/`EmailStr` (mirrors Morning's own `1102`/`1120` errors;
    already a dependency, previously unused by any write path); phone is normalized to Israeli
    local dashed format (`0XX-XXXXXXX`) since Morning documents no phone-format rule at all —
    REQ-CLIENT-015/016/017 added, plus a mandatory real-sandbox round-trip test (create → read
    back) proving the normalized phone actually persists.
- **Spec `spec.md` + `user-stories.md` are user-approved** (2026-07-29). `plan.md` and `tasks.md`
  are also complete and approved. `/speckit.clarify` was effectively a no-op since all
  clarifications were resolved inline during specification across three rounds.
- **`/speckit.analyze` remediation round** (2026-07-29): a cross-artifact consistency pass found
  2 CRITICAL coverage gaps + 3 lower-severity inconsistencies, all resolved directly with the
  user and applied across spec.md/user-stories.md/plan.md/research.md/data-model.md/contracts/
  tasks.md:
  - **F1**: `get_client_details` narrowed to name-only lookup (tax-ID lookup dropped — the real
    `Search Clients` filters don't document `taxId` support). REQ-CLIENT-002 updated.
  - **F2**: `add_client` uses "try and fail" instead of a proactive duplicate-name/tax-ID check —
    any real-API rejection surfaces to the user via the existing friendly-error mapping.
    REQ-CLIENT-007 updated.
  - **F3**: spec.md's header corrected — `apps/denidin-app` needs a small real code change
    (approval-tuple rename/extension in `ai_handler.py`), not "guidance only."
  - **F4**: stale "TBD in Phase 0 research" language in the Terminology Glossary/Assumptions
    replaced with the resolved findings (client_id is a UUID; `POST /clients/search` + `PUT
    /clients/{id}`, no GET).
  - **F5**: `tasks.md` T018a now explicitly requires a phone round-trip verification for
    `update_client`, matching T013a's standard for `add_client` (REQ-CLIENT-017).
  - **New requirement surfaced by the user during remediation**: the internal Morning `client_id`
    must never be exposed to the WhatsApp user in any reply (REQ-CLIENT-018, SC-008) — this also
    corrects existing Feature-005 code, whose current `add_client` confirmation message leaks it.
- Ready for `/speckit.implement`.
