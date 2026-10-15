"""bugfix-077 addendum: a Morning document that was created or cancelled successfully is final.

A failed reaction once led the model to redo a flow that had already created a tax document. Duplicate tax
documents carry legal consequences, so the backbone, the write capability and every flow that creates or
cancels a document must say that a completed write is never repeated because of anything that follows.
"""
from pathlib import Path

import pytest

PROMPTS = Path(__file__).resolve().parents[2] / "config" / "prompts"
WRITING_FLOWS = [
    "flow_cancel_document_with_credit_note", "flow_cancel_transaction_account",
    "flow_issue_invoice_for_payment_due", "flow_issue_invoice_receipt_combo",
    "flow_issue_payment_received_with_reference_doc", "flow_issue_receipt_without_invoice",
    "flow_issue_transaction_account", "flow_morning_document_write",
]
MARKER = "cannot be undone"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_backbone_says_a_completed_write_is_never_repeated():
    assert MARKER in _read(PROMPTS / "backbone.md")


def test_the_write_capability_says_a_completed_write_is_never_repeated():
    assert MARKER in _read(PROMPTS / "capabilities" / "cap_invoicing_write.md")


@pytest.mark.parametrize("flow", WRITING_FLOWS)
def test_every_document_writing_flow_says_a_completed_write_is_never_repeated(flow):
    top = "\n".join(_read(PROMPTS / "flows" / f"{flow}.md").splitlines()[:16])
    assert MARKER in top
