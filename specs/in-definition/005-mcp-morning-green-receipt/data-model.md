# data-model.md

Entities extracted from the feature spec and Phase‑0 research.

## Invoice
- id: string (Morning `documentId` / GUID)
- number: string (human-friendly document number)
- type: integer (document type id, e.g., 305 invoice, 200 receipt)
- status: string ("draft", "open", "closed", "paid", "cancelled")
- business_id: string
- client_id: string
- issue_date: date
- due_date: date
- amount: number (decimal, NIS)
- currency: string (3-letter, default: ILS)
- vat_included: boolean
- items: array of {description, quantity, unit_price, vatType}
- linked_document_ids: array[string]
- payments: array[Payment] (embedded summary)
- created_at: datetime (UTC)
- updated_at: datetime (UTC)

Validation rules:
- `amount` must be >= 0
- `currency` default to `ILS` when omitted
- `issue_date` must be <= `due_date` (if due_date present)

## Client
- id: string
- name: string (required)
- email: string (optional, email format)
- phone: string (optional)
- tax_id: string (optional)
- address: string (optional)
- balance: number (computed)
- created_at, updated_at: datetime (UTC)

Validation rules:
- `name` non-empty
- `email` when present must be valid email

## Payment
- id: string
- invoice_id: string
- amount: number
- currency: string
- payment_date: date
- method: string ("card","bank_transfer","cash",...)

## ExpenseDraft (file-upload driven)
- id: string
- uploaded_file_url: string
- status: string ("parsed","pending","declined")
- parsed_metadata: object (auto-extracted fields)
- created_at, updated_at: datetime (UTC)

Notes:
- Models are primarily Pydantic schemas to validate inputs and outputs for MCP tools.
- Persistence is optional; initial implementation will map 1:1 to Morning API responses and not store canonical copies unless explicitly required.

