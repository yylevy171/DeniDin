# Bugfix 075: DOCX Creation Fails to Send the Document to WhatsApp

**Status:** Obsolete - resolved by configuration, no code change (2026-10-15)

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

## Resolution (2026-10-15)
Root cause found from prod logs: every `sendFileByUpload` went to `https://media.green-api.com`
(connection refused / timeout). Feature 101 moved the API host to the instance host
(`green_api_host_mode: "instance"` -> `7107.api.greenapi.com`) but left `green_api_media_host`
at `null`, i.e. the library default, which is the dead generic media host.

Fix is config only - `green_api_media_host` already exists in `denidin-app` v0.8.2 and is passed to
the library's `media=`, which `sendFileByUpload` uses. Values (from the Green API console):
- prod: `https://7107.api.greenapi.com`
- dev: `https://7105.media.greenapi.com`

Confirmed working in both environments by the operator. No code change; a proposed explicit
`green_api_api_url` setting was discarded as unnecessary (`instance` mode already derives the
console's apiUrl in both environments).
