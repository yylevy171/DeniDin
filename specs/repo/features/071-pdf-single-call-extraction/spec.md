# Feature Specification: Single-Call PDF Extraction

**Feature Branch**: `feature/f64-f66-f71-f99-f100-b72-b73` (bundle)
**Created**: 2026-08-31 · **Specified**: 2026-10-09
**Status**: Specified (acceptance scenarios approved 2026-10-09) - `speckit.clarify` / `plan` pending
**Origin**: split out of Feature 069 (done), which brought images and DOCX into the client-resolution-before-ledger gate and deferred PDF here.

## Problem
A PDF is converted page by page to images and each page gets its own vision call. That is slow, costly for long files, fragments content that spans pages, and discards the ledger recognition per page - so a PDF fee agreement never reaches the ledger.

## Requirements
- **REQ-071-01 (One call)**: The whole PDF is read in one model call using OpenAI's native PDF input; the per-page conversion mechanism and its code are deleted.
- **REQ-071-02 (Model & prompt)**: The call uses the configured vision model (`ai_vision_model`) and the same prompt and output contract as image extraction.
- **REQ-071-03 (Same contract)**: The result has the same shape every extractor returns (extracted text, document analysis, extraction quality, warnings, model used) plus ledger events.
- **REQ-071-04 (Ledger)**: A PDF fee agreement (`הסכם`) flows through the same ledger capture and client-resolution gate as images and DOCX. A PDF is always `הסכם` or unknown, never `בנק` (bugfix-028).
- **REQ-071-05 (Too large)**: A PDF beyond the model's document limits gets a friendly refusal asking for a smaller file; no model call is made and no fallback to per-page extraction exists.
- **REQ-071-06 (Scope)**: Applies to all PDFs (summaries for any shared PDF). No feature flag.

## Success criteria
- **SC-001**: A PDF costs one model call regardless of page count.
- **SC-002**: A fee-agreement PDF produces the same ledger outcome as the same agreement as an image or DOCX.

## Open points for planning
Real limits (pages / MB) and whether `ai_vision_model` accepts PDF input must be **confirmed with a real call** before the plan relies on them (CONSTITUTION: no unverified third-party assumptions) - a small billed check, with approval. Confirm the existing PDF E2E tests exercise the Backbone media path. Obsolete per-page unit tests tracked as 71-9.
