# Bugfix 075: DOCX Creation Fails to Send the Document to WhatsApp

**Status:** Open - root cause not yet investigated

## Problem Description
When a document (DOCX) is created (e.g. a fee agreement from a template), the document itself is
not delivered to the user over WhatsApp. The creation step runs, but the file never arrives in the
chat.

## Not Yet Known
- Which flow(s) are affected (all DOCX creation, or only some templates / only one path - legacy
  `AIHandler` vs. Capability Backbone `send_document`).
- Whether the failure is at file generation, at the Green API upload/send call, or in what the
  app reports back to the user afterwards (e.g. claiming success).
- Environment(s) where it reproduces (dev, prod, or both), and when it started.
- What the user sees in the chat when it fails.

## Next Steps (Bug-Driven Development, METHODOLOGY.md §VII)
1. Reproduce and trace the failing turn from real logs (no assumptions about Green API behavior
   without a real call - CONSTITUTION "No Unverified Third-Party Assumptions").
2. Root cause -> human approval.
3. Test-gap analysis -> failing test -> human approval.
4. Minimal fix -> verify.
