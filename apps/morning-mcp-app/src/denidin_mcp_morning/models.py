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
        """Map Morning's `emails: [str]` list onto the single `email` field."""
        if isinstance(data, dict) and "email" not in data and "emails" in data:
            emails = data.get("emails") or []
            data = dict(data)
            data["email"] = emails[0] if emails else None
        return data


class Payment(BaseModel):
    """A single payment recorded against an invoice."""

    id: Optional[str] = None
    invoice_id: str
    amount: float = Field(ge=0)
    currency: str = "ILS"
    payment_date: date
    method: Optional[str] = None


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
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    payments: List[Payment] = Field(default_factory=list)
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
        if "due_date" not in mapped and "dueDate" in data:
            mapped["due_date"] = data["dueDate"]
        if "total_amount" not in mapped and "total" in data:
            mapped["total_amount"] = data["total"]
        if "vat_amount" not in mapped and "vatAmount" in data:
            mapped["vat_amount"] = data["vatAmount"]

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
