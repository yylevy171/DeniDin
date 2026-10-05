# Contracts: Feature 098

## C1 - (removed 2026-10-05)

The `get_invoicing_rules` MCP tool was dropped when DeniDin moved to its own config copy.

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

## C4 - DeniDin config field

`allocation_threshold_nis` (number > 0, default 5000), top-level in
`apps/denidin-app/config/config.*.json`, loaded into `AppConfiguration`. Must equal
Morning-MCP's `allocation_threshold_nis`.

## C5 - Prompt placeholder (DeniDin)

`{{ALLOCATION_THRESHOLD_NIS}}` in `runtime_constitution.md` (and, after Feature 063, in
the backbone prompt files). Substituted in `AIHandler._load_constitution` from `config.allocation_threshold_nis`,
formatted with a thousands separator and no decimals when whole (`5,000`).
A placeholder left unsubstituted in the final instructions is a bug (unit test).
