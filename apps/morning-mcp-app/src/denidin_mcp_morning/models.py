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

from pydantic import BaseModel, EmailStr, Field, model_validator


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

        if "issue_date" not in mapped and "date" in data:
            mapped["issue_date"] = data["date"]
        if "due_date" not in mapped and "dueDate" in data:
            mapped["due_date"] = data["dueDate"]
        if "total_amount" not in mapped and "total" in data:
            mapped["total_amount"] = data["total"]
        if "vat_amount" not in mapped and "vatAmount" in data:
            mapped["vat_amount"] = data["vatAmount"]

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
