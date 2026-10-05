# Data Model: Feature 098

No persisted data is added. Everything is configuration, in-memory values, or Morning's
own existing client record.

## Morning-MCP configuration (`apps/morning-mcp-app/config/config.*.json`)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `allocation_threshold_nis` | number > 0 | `5000` | New. Pre-VAT, ₪. Added to `config.schema.json` and `MorningMCPConfig`. |
| `default_vat_rate` | number 0-1 | `0.18` (was `0.17`) | Existing, previously unused. Value fix approved by PM 2026-10-05 (D-2). |

## DeniDin configuration (`apps/denidin-app/config/config.*.json`)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `allocation_threshold_nis` | number > 0 | `5000` | New, top-level. A copy of Morning-MCP's value; change both together. Used only to fill the prompt placeholder. |

## `InvoicingRules` (Morning-MCP, in-memory)

Built once in `create_server` from config: `allocation_threshold_nis: float`,
`vat_rate: float`. Passed into the three document-creating tools by dependency injection
(no module globals).

## Morning client record (existing, unchanged)

`Client.tax_id: Optional[str]` - mapped from Morning's `taxId`.

**"Has a valid ID"** ⇔ `tax_id` is not `None` and, after stripping surrounding
whitespace, matches `^\d{9}$`. Anything else (missing, empty, 8 digits, contains dashes)
counts as missing.

## Allocation check (pure function, Morning-MCP)

Inputs: the built document payload, the client's `tax_id`, `InvoicingRules`.

1. Applies only if `payload.type ∈ {305, 320}`.
2. `gross = Σ income[i].price × income[i].quantity`.
3. `pre_vat = gross / (1 + vat_rate)` if `payload.vatType == 1`, else `gross`;
   rounded to 2 decimals.
4. Refuse ⇔ `pre_vat > allocation_threshold_nis` **and** the client has no valid ID.
