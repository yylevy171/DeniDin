"""Pydantic models for Morning API resources.

These validate MCP tool inputs/outputs and map onto the real Morning
`/documents` and `/clients` response shapes (nested `client{}`, `emails[]`,
`date`/`dueDate`, `total`/`vatAmount`). Persistence is not required; models
exist to validate, not to be stored. Any timestamp a model stamps itself is
UTC (CONSTITUTION.md §II).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# Morning's real /documents(/search) status codes, confirmed live against
# GET /documents/statuses (2026-07-08): 0 open, 1 closed, 2 manually closed,
# 3 cancelling document, 4 cancelled document. Mapped onto this app's
# canonical status vocabulary (paid/unpaid/cancelled) used throughout
# formatters.py and the tool contracts.
_MORNING_STATUS_CODES = {
    0: "unpaid",
    1: "paid",
    2: "paid",
    3: "cancelled",
    4: "cancelled",
}

# Morning's OWN literal status vocabulary, confirmed live against
# GET /documents/statuses (2026-08-23). Deliberately kept separate from the
# canonical paid/unpaid mapping above, which is an interpretation, not a
# translation: Morning's real axis is open/closed, so "מסמך סגור" -> "paid" is
# a simplification that can be wrong (for a חשבון עסקה/proforma, "closed"
# plausibly means "converted to an invoice", not "paid"). Feature 025 Phase 9
# records this literal label in the ledger alongside the derived one so the
# real value is never lost.
_MORNING_STATUS_LABELS = {
    0: "מסמך פתוח",
    1: "מסמך סגור",
    2: "מסמך סומן ידנית כסגור",
    3: "מסמך מבטל",
    4: "מסמך שבוטל",
}

# Morning's real document type codes, confirmed live against GET
# /documents/types (2026-07-21/22, bugfix-014) - display-only labels, not
# used for any filtering/business-logic decision (that stays on the
# canonical status vocabulary above). Only the types actually relevant to
# this app's real usage are included; GET /documents/types returns more
# (quotes, orders, delivery notes, deposits, etc.) that aren't needed here.
_DOCUMENT_TYPE_NAMES = {
    300: "חשבון עסקה",
    305: "חשבונית מס",
    320: "חשבונית מס / קבלה",
    330: "חשבונית זיכוי",
    400: "קבלה",
}

# Morning's real payment method codes, confirmed live against GET
# /payments/types (2026-07-22, bugfix-014) - display-only labels for a
# receipt's payment[].type field.
_PAYMENT_TYPE_NAMES = {
    0: "ניכוי במקור",
    1: "מזומן",
    2: "צ'ק",
    3: "כרטיס אשראי",
    4: "העברה בנקאית",
    5: "פייפאל",
    10: "אפליקציית תשלום",
    11: "אחר",
}


class Client(BaseModel):
    """A Morning client (customer) record."""

    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    created_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def _map_morning_client_shape(cls, data: Any) -> Any:
        """Map Morning's real client shape onto this model's fields: `emails`
        (list) -> `email` (single), `taxId` (camelCase) -> `tax_id`. This gap
        (this model was defined in Feature 005 but never actually exercised
        against a real Morning response until Feature 026's
        _resolve_client_by_name/list_clients started calling
        Client.model_validate() - confirmed live 2026-07-29: tax_id silently
        came back None despite Morning returning taxId)."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "email" not in data and "emails" in data:
            emails = data.get("emails") or []
            data["email"] = emails[0] if emails else None
        if "tax_id" not in data and "taxId" in data:
            data["tax_id"] = data["taxId"]
        return data


class Payment(BaseModel):
    """A single payment recorded against an invoice.

    Reworked 2026-08-23 (Feature 025 Phase 9) after finding this model was
    entirely unreachable: `Invoice.payments` had no mapping from the raw
    `payment` key, and `invoice_id` was required even though the raw payment
    object never carries one - so it would have failed validation even if the
    mapping had existed. Field shapes below come from real dev-sandbox
    payloads (a bank transfer and a cash payment), not from documentation.
    """

    id: Optional[str] = None
    # Optional (was required): the raw payment object has no invoice_id at all -
    # it is nested inside its document, so the parent is implicit.
    invoice_id: Optional[str] = None
    amount: float = Field(ge=0)
    currency: str = "ILS"
    payment_date: Optional[date] = None
    method: Optional[str] = None          # raw `name`, e.g. "העברה בנקאית" / "מזומן"
    payment_type: Optional[int] = None    # raw `type`, per GET /payments/types
    status: Optional[int] = None
    # Structured bank details - present ONLY on get_invoice_details' response;
    # /documents/search carries the same information merely concatenated into a
    # Hebrew string in the payment's own `description`.
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None
    bank_account: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _map_morning_payment_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        mapped: Dict[str, Any] = dict(data)
        mapped.setdefault("payment_date", data.get("date"))
        mapped.setdefault("method", data.get("name"))
        mapped.setdefault("payment_type", data.get("type"))
        mapped.setdefault("bank_name", data.get("bankName"))
        mapped.setdefault("bank_branch", data.get("bankBranch"))
        mapped.setdefault("bank_account", data.get("bankAccount"))
        return mapped


class LinkedDocument(BaseModel):
    """A Morning document linked to another (e.g. a receipt linked to the
    invoice it pays, or a credit invoice linked to the invoice it cancels).

    Real shape confirmed live (2026-07-21/22, bugfix-014): this field
    (`linkedDocuments`) only appears on the single-document GET
    (`MorningClient.get_invoice` / `GET /documents/{id}`) response - it is
    completely absent from `/documents/search` (what `list_invoices` uses).
    It is structured and bidirectional (appears on both the original
    document and the thing linked to it), unlike the free-text `remarks`/
    `description` fields these documents also carry, which are user-editable
    and not trusted as a linkage mechanism.
    """

    id: str
    type: Optional[int] = None
    number: Optional[str] = None
    document_date: Optional[date] = None
    amount: float = Field(ge=0)
    currency: str = "ILS"

    @field_validator("number", mode="before")
    @classmethod
    def _coerce_number_to_str(cls, value: Any) -> Optional[str]:
        return str(value) if value is not None else None

    @model_validator(mode="before")
    @classmethod
    def _map_document_date(cls, data: Any) -> Any:
        if isinstance(data, dict) and "document_date" not in data and "documentDate" in data:
            data = dict(data)
            data["document_date"] = data["documentDate"]
        return data


class Invoice(BaseModel):
    """A Morning document (invoice/receipt), mapped from the real API response."""

    id: str
    number: Optional[str] = None
    type: Optional[int] = None
    client_id: Optional[str] = None
    client_name: str
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    currency: str = "ILS"
    amount: float = Field(ge=0)
    total_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    # Feature 025 Phase 9: exposed so denidin-app can DERIVE vat_status in code
    # rather than asking the model. Not persisted to the ledger themselves
    # (user decision, 2026-08-23) - read from the payload, then discarded.
    amount_excl_vat: Optional[float] = None
    vat_rate: Optional[float] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    # denidin-app's Feature 025 (Morning-Sourced Ledger Events): the real
    # creationDate field is a genuine Unix epoch integer with full
    # second-level precision (live-confirmed 2026-08-21 against the real dev
    # sandbox: e.g. 1787241168 -> 2026-08-20 18:52:48 Israel local) -
    # completely separate from issue_date/documentDate (date-only).
    creation_timestamp: Optional[datetime] = None
    # denidin-app's Feature 025: Morning's own top-level document description
    # (e.g. "תחזוקה") - live-confirmed present on real /documents(/search)
    # responses, but never mapped here until 2026-08-22, so no MCP tool could
    # surface it at all. Distinct from income[].description (per-line-item).
    description: Optional[str] = None
    status: Optional[str] = None
    # Feature 025 Phase 9: Morning's raw status int and its OWN literal label,
    # kept alongside `status`'s canonical paid/unpaid interpretation - see
    # _MORNING_STATUS_LABELS for why the two are not the same thing.
    status_code: Optional[int] = None
    status_label: Optional[str] = None
    payments: List[Payment] = Field(default_factory=list)
    # Raw Morning line items (`income`), passed through as-is: denidin-app's
    # ledger takes only the first and warns if there are more (user decision,
    # 2026-08-23), which requires seeing the whole array.
    income: List[Dict[str, Any]] = Field(default_factory=list)
    linked_documents: List[LinkedDocument] = Field(default_factory=list)
    pdf_url: Optional[str] = None

    @field_validator("number", mode="before")
    @classmethod
    def _coerce_number_to_str(cls, value: Any) -> Optional[str]:
        """Morning's real `/documents` response returns `number` as an int (e.g. 50002)."""
        return str(value) if value is not None else None

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: Any) -> Optional[str]:
        """Map Morning's numeric document-status codes onto our canonical vocabulary.

        Morning's /documents(/search) responses return `status` as an int
        (confirmed live against GET /documents/statuses); string statuses
        (e.g. already-canonical values used internally) pass through unchanged.
        """
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, int):
            return _MORNING_STATUS_CODES.get(value, str(value))
        return str(value)

    @model_validator(mode="before")
    @classmethod
    def _map_morning_document_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        mapped: Dict[str, Any] = dict(data)
        client = data.get("client") or {}
        if isinstance(client, dict):
            mapped.setdefault("client_id", client.get("id"))
            mapped.setdefault("client_name", client.get("name"))
            mapped.setdefault("client_phone", client.get("phone"))
            emails = client.get("emails") or []
            mapped.setdefault("client_email", emails[0] if emails else None)

        # Real /documents(/search) responses use `documentDate` (confirmed
        # live); some earlier fixtures/callers use a plain `date` key - prefer
        # documentDate when both are present, but keep the `date` fallback so
        # existing callers/tests using that shape keep working.
        if "issue_date" not in mapped and ("documentDate" in data or "date" in data):
            mapped["issue_date"] = data.get("documentDate") or data.get("date")
        # Feature 025 Phase 9: raw payment array -> payments. The raw key is
        # `payment` (singular); without this the field was silently always []
        # for every caller (a real, long-standing bug - see Payment's docstring).
        if "payments" not in mapped and isinstance(data.get("payment"), list):
            mapped["payments"] = data["payment"]

        # Morning's raw status int + its own literal label, preserved alongside
        # the canonical paid/unpaid interpretation `status` carries.
        raw_status = data.get("status")
        if isinstance(raw_status, int):
            mapped.setdefault("status_code", raw_status)
            mapped.setdefault("status_label", _MORNING_STATUS_LABELS.get(raw_status))

        if "creation_timestamp" not in mapped and "creationDate" in data and data["creationDate"] is not None:
            # Real API sends a Unix epoch int (confirmed live 2026-08-21) - Pydantic
            # parses an int/float datetime field as seconds-since-epoch automatically.
            mapped["creation_timestamp"] = data["creationDate"]
        if "due_date" not in mapped and "dueDate" in data:
            mapped["due_date"] = data["dueDate"]
        if "total_amount" not in mapped and "total" in data:
            mapped["total_amount"] = data["total"]
        # Real /documents(/search) responses spell this `vat`, not `vatAmount`
        # (live-confirmed 2026-08-23) - the vatAmount-only mapping meant
        # vat_amount was silently None for every real document. Prefer the real
        # key, keep vatAmount as a fallback for existing fixtures/callers.
        if "vat_amount" not in mapped and ("vat" in data or "vatAmount" in data):
            mapped["vat_amount"] = data.get("vat", data.get("vatAmount"))
        if "amount_excl_vat" not in mapped and "amountExcludeVat" in data:
            mapped["amount_excl_vat"] = data["amountExcludeVat"]
        if "vat_rate" not in mapped and "vatRate" in data:
            mapped["vat_rate"] = data["vatRate"]

        # Real GET /documents/{id} responses include a `linkedDocuments` array
        # (confirmed live, bugfix-014) - completely absent from
        # /documents/search. Map it here so any Invoice built from a
        # single-document GET (get_invoice_details) surfaces it.
        if "linked_documents" not in mapped and "linkedDocuments" in data:
            mapped["linked_documents"] = data["linkedDocuments"]

        # Real /documents(/search) responses include a `url: {he, origin}`
        # object with ready-to-use, pre-signed PDF download links (confirmed
        # live - same shape download_invoice_pdf reads from the single-GET
        # response). Map it here too so any tool returning an Invoice (list,
        # details, create) can surface the link, not just download_invoice_pdf.
        if "pdf_url" not in mapped:
            urls = data.get("url") or {}
            if isinstance(urls, dict):
                pdf_url = urls.get("he") or urls.get("origin")
                if pdf_url:
                    mapped["pdf_url"] = pdf_url

        return mapped


class FinancialSummary(BaseModel):
    """Aggregated totals/counts for a reporting period."""

    period_start: date
    period_end: date
    total_invoiced: float
    total_paid: float
    total_unpaid: float
    invoice_count: int
    paid_invoice_count: int
    unpaid_invoice_count: int
    average_invoice_amount: float
