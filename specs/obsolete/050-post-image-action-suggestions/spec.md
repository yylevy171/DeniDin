# Feature Specification: Common Actions Offered After Image Processing

**Feature Branch**: `feature/050-post-image-action-suggestions`
**Created**: 2026-08-13
**Status**: Placeholder — not yet clarified/specced. Captured from a 2026-08-13 backlog
conversation; run `speckit.specify` + `speckit.clarify` before starting implementation.

## Input

User description: "offer common actions post image process" — after `MediaHandler`/
`ImageExtractor` finishes analyzing an incoming image, proactively suggest relevant follow-up
actions to the user rather than just returning the extracted text/analysis.

## Notes captured so far

- Candidate actions (to confirm during clarify, not assumed): create an invoice/receipt from a
  photographed document via Morning MCP (godfather/admin only, per existing RBAC gating), save
  extracted info to memory, log a ledger event (Feature 033) if the image looks like a fee
  agreement or bank deposit slip.
- Needs to fit the existing extractor contract (`extracted_text`, `document_analysis`, etc.)
  without changing behavior for roles that don't get suggestions (e.g. plain clients with no
  Morning MCP tool attached).
- Media messages currently bypass `AIHandler.get_response` entirely (`WhatsAppHandler.
  handle_media_message()` never routes through it — see the "Message flow" note in CLAUDE.md).
  This feature needs to decide whether suggestions come from a lightweight rule/model step
  inside `MediaHandler` itself, or whether image results start routing through the
  conversational pipeline in some way — a meaningful architectural fork to resolve in planning,
  not here.
