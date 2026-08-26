"""
Regression test for method_a.py's real transform logic (locks in the manual verification done
during implementation — a raw-shape mismatch was caught and fixed this way before this test
existed: Payment's raw `method` field is actually spelled `name` in Morning's real payload).

No live network call — Invoice.model_validate/format_invoice_json/_expand_accounting_document_json
are all pure, local, deterministic code.
"""
import method_a


def _real_shaped_raw_document(**overrides):
    """A raw document in MorningClient.get_invoice()'s real shape (research.md R1/R6)."""
    doc = {
        "id": "real-shape-test-001",
        "number": 50002,
        "type": 305,  # חשבונית מס
        "client": {"id": "c1", "name": "Test Client Ltd."},
        "status": 2,
        "amount": 100.0,
        "total": 117.0,
        "vat": 17.0,
        "documentDate": "2025-01-15",
        "creationDate": 1737000000,
        "income": [
            {"description": "Consulting", "quantity": 1, "price": 100.0, "amountTotal": 100.0}
        ],
        "payment": [{"name": "מזומן", "type": 1, "date": "2025-01-16", "amount": 117.0}],
    }
    doc.update(overrides)
    return doc


def test_transform_produces_a_fully_expanded_ledger_event():
    event = method_a.transform(_real_shaped_raw_document())

    assert event["source_type"] == "חשבונית"
    assert event["accounting_document_display_number"] == "50002"
    assert event["event_subtype"] == "חשבונית מס"  # translate_document_type(305)
    assert event["client_name"] == "Test Client Ltd."
    assert event["description"] == "Consulting"
    assert event["amount"] == "117.0"
    assert event["accounting_document_payment_method"] == "מזומן"


def test_transform_derives_creation_date_from_creationDate_epoch():
    event = method_a.transform(_real_shaped_raw_document())
    # 1737000000 is a real Unix epoch second, mapped Israel-local (research.md R1/R6).
    assert event["accounting_document_creation_date"].startswith("2025-01-16")


def test_transform_multi_line_item_uses_only_the_first():
    """User decision, Feature 025 (2026-08-23): only the first line item is ever captured."""
    doc = _real_shaped_raw_document(income=[
        {"description": "First item", "quantity": 1, "price": 50.0, "amountTotal": 50.0},
        {"description": "Second item", "quantity": 1, "price": 50.0, "amountTotal": 50.0},
    ])
    event = method_a.transform(doc)
    assert event["description"] == "First item"
