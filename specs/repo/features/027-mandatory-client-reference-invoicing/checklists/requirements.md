# Specification Quality Checklist: Mandatory Reference to an Existing Client for Invoice Creation

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: August 6, 2026
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — the Technology Choice section
      names the *reused pattern* (`_resolve_client_by_name`), not new implementation detail; no
      code-level specifics appear in Requirements/Success Criteria.
- [x] Focused on user value and business needs (real client attachment → real email delivery →
      correct per-client accounting)
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — resolved across three clarification sessions
      2026-08-06 (live API verification, 4 `/speckit.specify`-time scoping questions, and 1
      `/speckit.clarify` question on non-exact-match disclosure); see spec.md Clarifications.
- [x] Requirements are testable and unambiguous (REQ-INV-001 through REQ-INV-013, each naming a
      concrete, verifiable behavior; REQ-INV-012/013 added for Group B, see Notes)
- [x] Success criteria are measurable (SC-001 through SC-008, each stating a percentage/verifiable
      outcome)
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined (see `user-stories.md`, US1-US6)
- [x] Edge cases are identified (spec.md Edge Cases, now split Group A/Group B:
      found/not-found/ambiguous/declined-approval/concurrent-creation-race for Group A;
      preserve-real-id/refuse-on-no-id for Group B)
- [x] Scope is clearly bounded (In scope: 6 document-creation tools in two groups — Group A
      resolve-by-name-and-attach-by-id, Group B preserve-original's-id-or-refuse — reusing Feature
      026's client resolution; Out of scope: historical document migration/remediation,
      end-to-end email-delivery verification, any new tool/parameter/approval mechanism)
- [x] Dependencies and assumptions identified (Assumptions section — depends on Feature 026's
      `_resolve_client_by_name`/formatters staying stable; live API confirmation already done, not
      deferred to Phase 0 research this time)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria (cross-referenced into
      `user-stories.md`'s acceptance-criteria bullets per story)
- [x] User scenarios cover primary flows (Group A: found-unambiguous, not-found-then-created,
      ambiguous, cross-tool uniformity; RBAC-denial; Group B: preserve-real-id-or-refuse)
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- **This feature's live API research happened *before* `/speckit.specify`, not during
  `/speckit.plan`'s usual Phase 0** — the user explicitly asked to verify the placeholder spec's
  open "does the API support this" question live against the real Morning sandbox first (a real
  test client + a real test document created with `client.id` only, confirmed via both the create
  response and a fresh `GET /documents/{id}`). This is documented in Clarifications and will be
  carried into `research.md` verbatim when `/speckit.plan` runs, rather than re-investigated.
- **Scoping decisions resolved directly with the user 2026-08-06** (2 explicit questions, 2 more
  resolved via reasonable defaults consistent with Feature 026's existing patterns — see
  Clarifications for all 4):
  - All 5 document-creation tools get uniform treatment (not just `create_invoice`).
  - Client-creation-then-document-creation uses two separate existing approval turns, not a new
    combined-confirmation mechanism — this was chosen specifically because it requires zero new
    application code, falling out of the existing per-tool MCP approval gate for free.
  - Not-found handling is "fail-then-let-the-model-offer-to-create" rather than a pure either/or
    between failing and prompting inline — mirrors exactly how a human uses Morning's own UI.
  - Ambiguous-match handling reuses Feature 026's existing disambiguation behavior unchanged.
- **This spec's `Apps` header differs from the placeholder's implicit assumption**: no
  `apps/denidin-app` code change is needed at all (unlike Feature 026, which needed a small
  approval-tuple change there) — every one of this feature's 6 target tools is already
  individually listed in `AIHandler.APPROVAL_REQUIRED_MCP_TOOLS` today, so no gating change is
  required on the denidin-app side; only `apps/morning-mcp-app` changes.
- **`/speckit.clarify` completed 2026-08-06** — 1 question asked and resolved (coverage scan found
  all other taxonomy categories Clear): whether a single *non-exact* name-match resolution during
  document creation should disclose the real matched client name, require exact matches only, or
  proceed silently. Resolved as **disclose** (Option A) — reuses `get_client_details`'s existing
  `is_exact_match` disclosure pattern (Feature 026), zero new mechanism. Added REQ-INV-011/SC-007,
  updated REQ-INV-002/010, Edge Cases, and `user-stories.md` US1's acceptance criteria.
- **`/speckit.plan` scoping correction completed 2026-08-06** — re-reading the actual tool
  implementations while drafting `plan.md` found that the "5 document-creation tools, uniform
  treatment" premise was wrong: only 3 (`create_invoice`, `create_transaction_account`,
  `create_combo_document` — **Group A**) take a `client_name` to resolve by search; the other 2
  (`create_credit_note`, `create_receipt` — **Group B**) take `original_invoice_id` and derive
  their client from the already-fetched original document, dropping its `id`. A 6th tool with the
  identical Group B bug (`close_transaction_account`) wasn't named in the original problem
  description or this spec's first draft at all. Resolved directly with the user (2 questions):
  include `close_transaction_account` (now 6 tools total, 3+3); Group B refuses with a friendly
  error (not a bare-name fallback) when the linked original predates this feature and has no
  `client.id`. Added REQ-INV-012/013, SC-008, `user-stories.md` US6, split all "uniform across
  tools"/Edge-Cases language into Group A vs. Group B throughout `spec.md`/`user-stories.md`. Also
  replaced the original company-style example names ("Tech Solutions", "Acme Corp", "Tech
  Innovations") with persona names ("Danny Cohen", "Ronit Levi", "Danny Katz") throughout
  `user-stories.md`, per user request — cosmetic, no behavior change.
- Ready for `/speckit.plan` (in progress — this correction round happened as part of it, before
  `plan.md`/`research.md`/`data-model.md`/`contracts/`/`quickstart.md` were written, so those
  artifacts reflect the corrected 6-tool, two-group design from the start).
