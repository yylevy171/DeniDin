# Tasks: Feature 099
Order in bundle: 4th.
- T099-A1 Unit tests (morning-mcp-app): cancelling-receipt payload (type 400, link to 320, negative price, first payment's method/details, description, today's date); refusal when 330 or negative 400 already linked; refusal when not linked to client; `amount` given -> ValueError; 305 and standalone behaviour unchanged.
- T099-A2 Integration tests (real sandbox): 320 -> 330 -> cancelling receipt; second attempt refused; 305 flow unaffected.
- T099-B1 Extend `create_receipt` + helper `_build_cancelling_receipt_payload`; formatter confirmation; docs in `server.py` tool description.
- T099-B2 Prompts: `flow_cancel_document_with_credit_note.md` (320 path, two approvals, already-credited refusal, declined/failed 400), `cap_invoicing_write.md`.
- T099-B3 Rebuild note: dev `morning-mcp-app` container must be rebuilt before any billed run (human approval to start/stop).
- T099-C Acceptance: `billed` 99-1 (sanity; add to `run_sanity.sh`), 99-2, 99-3, 99-4 - written last.
