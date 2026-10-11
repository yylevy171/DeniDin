"""
Feature 084 (WhatsApp reactions) - the expensive (vision/document) reaction-judgment
scenario pool. Plain data, NOT test functions - see tests/billed/reaction_judgment_pool.py's
own docstring for the full shape/field explanation; this file mirrors it for scenarios that
require a real document/image and a real vision call.

`document_path` names a fixture file under tests/expensive/data/ (or None for a scenario
that only needs a plain image placeholder - see the harness's own fixture-resolution logic).
These scenarios are NOT run automatically by anything - per CLAUDE.md's expensive-test
rules, each needs its own fresh, explicit human approval, every single run, one at a time.
"""
from typing import Any, Dict, List

EXPENSIVE_REACTION_SCENARIOS: List[Dict[str, Any]] = [
    {
        "name": "document_clean_agreement_full_resolution",
        "description": "Clean fee-agreement upload -> full resolution to a terminal reaction",
        "role": "godfather",
        "chat_id": "972500000201@c.us",
        "is_group": False,
        "document_type": "pdf",
        "document_path": "fee_agreement_clean.pdf",
        "followup_message": None,
        "hard_assertions": {},
    },
    {
        "name": "document_unreadable_garbled",
        "description": "Unreadable/garbled document -> resolution to a failure/attention reaction",
        "role": "godfather",
        "chat_id": "972500000202@c.us",
        "is_group": False,
        "document_type": "image",
        "document_path": "garbled_scan.jpg",
        "followup_message": None,
        "hard_assertions": {},
    },
    {
        "name": "document_requires_multi_turn_clarification",
        "description": "Document requiring multi-turn clarification before resolving",
        "role": "godfather",
        "chat_id": "972500000203@c.us",
        "is_group": False,
        "document_type": "pdf",
        "document_path": "fee_agreement_missing_client.pdf",
        "followup_message": "הלקוח הוא דוד לוי",
        "hard_assertions": {},
    },
    {
        "name": "document_workflow_abandoned",
        "description": "Document workflow explicitly abandoned by the user mid-flow",
        "role": "godfather",
        "chat_id": "972500000204@c.us",
        "is_group": False,
        "document_type": "pdf",
        "document_path": "fee_agreement_missing_client.pdf",
        "followup_message": "בעצם תשכח מזה, לא רלוונטי",
        "hard_assertions": {},
    },
    {
        "name": "document_in_group_chat_addressed",
        "description": "Document uploaded inside a group chat (addressed to DeniDin)",
        "role": "godfather",
        "chat_id": "120363000000000003@g.us",
        "is_group": True,
        "document_type": "pdf",
        "document_path": "fee_agreement_clean.pdf",
        "followup_message": None,
        "hard_assertions": {},
    },
    {
        "name": "document_second_type_receipt_photo",
        "description": "A second document type (a receipt/photo, not a PDF) - avoids "
                        "over-fitting judgment to one document shape",
        "role": "godfather",
        "chat_id": "972500000205@c.us",
        "is_group": False,
        "document_type": "image",
        "document_path": "receipt_photo.jpg",
        "followup_message": None,
        "hard_assertions": {},
    },
]
