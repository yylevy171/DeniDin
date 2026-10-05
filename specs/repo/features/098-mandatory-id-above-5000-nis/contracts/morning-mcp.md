# Contracts: Feature 098

## C1 - New MCP tool `get_invoicing_rules` (Morning-MCP)

- **Arguments**: none.
- **Auth**: the server's existing bearer token (not exempt like `/health`).
- **Result** (JSON text, per the 2026-09-04 JSON-only contract):
  ```json
  {"allocation_threshold_nis": 5000}
  ```
- **Side effects**: none; no Morning API call.
- **Approval**: none (read-only; must NOT be added to `APPROVAL_REQUIRED_MCP_TOOLS`).

## C2 - Refusal from the document-creating tools (Morning-MCP)

Applies to `create_invoice` (305), `create_combo_document` (320),
`create_combo_document_as_reference` (320). Their signatures are **unchanged**.

When the allocation check (data-model.md) refuses:
- Nothing is sent to Morning (`POST /documents` is never called).
- Audit: `log_refusal(<tool>, "client_tax_id_required", client_name=…, pre_vat_amount=…, threshold=…)`.
- MCP result: `isError=True`, text (Hebrew, user-facing, returned verbatim by `errors.py`):
  ```
  ❌ לא ניתן להפיק את המסמך: ללקוח <name> אין ת.ז / ח.פ במערכת. מסמך מסוג חשבונית מס
  או חשבונית מס/קבלה מעל <threshold> ₪ לפני מע"מ דורש מספר הקצאה, ולשם כך חייב להיות
  מספר מזהה של הלקוח. יש לבקש את ת.ז / ח.פ (9 ספרות), לעדכן את הלקוח, ולנסות שוב.
  ```
- Every other outcome (below threshold, valid ID, out-of-scope type) is byte-for-byte
  today's behavior.

## C3 - New `MorningClient.get_client(client_id)` (Morning-MCP, internal)

`GET {base_url}/clients/{client_id}` → the client record (dict). Same `_request`/
`raise_for_status` pattern as `get_invoice`. **LIVE-VERIFY** (research R1).

## C4 - DeniDin startup fetch (DeniDin, internal)

- Discover URL via `MorningMcpLocator(config.mcp).current_server_url()`, auth via
  `config.mcp['morning_auth_token']`.
- MCP `call_tool("get_invoicing_rules", {})` with the `mcp` Python client.
- Poll every 2s for up to 60s, then every 5 minutes until success (CONSTITUTION §XVIII).
- On success: set `InvoicingRules.allocation_threshold_nis`, log INFO once. Each failed
  attempt: DEBUG; the transition to the 5-minute phase: WARNING.

## C5 - Prompt placeholder (DeniDin)

`{{ALLOCATION_THRESHOLD_NIS}}` in `runtime_constitution.md` (and, after Feature 063, in
the backbone prompt files). Substituted in `AIHandler._load_constitution`:
- known → `5,000` (thousands separator, no decimals when whole);
- unknown → `סף מספר ההקצאה` with no number.
A placeholder left unsubstituted in the final instructions is a bug (unit test).
