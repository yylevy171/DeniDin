"""Agreements capabilities (Feature 089, US5): the WhatsApp tool dispatch onto a real
AgreementsManager - actor stamping, error strings, ambiguity, locking, and registration."""
import json
from types import SimpleNamespace

import pytest

from src.backbone.capability_tags import CapabilityTag
from src.capabilities.agreements.handler import dispatch_direct_tool_call
from src.capabilities.toolsets import WRITE_TOOL_NAMES, WRITE_TOOLS_BY_TAG, _local_tools_by_tag
from tests.denidin_test_support import make_agreements_manager

CLIENT = "ישראל ישראלי"


@pytest.fixture
def mgr(tmp_path):
    return make_agreements_manager(tmp_path)


@pytest.fixture
def backbone(mgr):
    return SimpleNamespace(agreements_manager=mgr, session_manager=None)


def _call(backbone, name, **args):
    return dispatch_direct_tool_call(backbone, name, args, {"chat_id": "c@c.us", "message_id": "m1"})


def _seed(mgr, title="ערעור"):
    agreement, _ = mgr.create_agreement(
        client_name=CLIENT, title=title, actor="webapp",
        components=[{"label": "ריטיינר", "amount": 5000}, {"label": "הצלחה", "percent": 10, "trigger_condition": "זכייה"}])
    return agreement


def _key(agreement, label):
    return next(c["component_key"] for c in agreement["components"] if c["label"] == label)


def test_find_agreements_lists_all_of_a_clients_agreements(backbone, mgr):
    _seed(mgr, "א")
    _seed(mgr, "ב")
    out = json.loads(_call(backbone, "find_agreements", client_name=CLIENT))
    assert len(out["agreements"]) == 2  # both returned: the model must ask, the tool never picks


def test_find_agreements_unknown_client_is_empty(backbone):
    assert json.loads(_call(backbone, "find_agreements", client_name="אין כזה"))["agreements"] == []


def test_update_component_is_stamped_whatsapp_and_reports_events(backbone, mgr):
    agreement = _seed(mgr)
    out = json.loads(_call(backbone, "update_component", agreement_id=agreement["agreement_id"],
                           component_key=_key(agreement, "ריטיינר"), amount=6000))
    assert out["ledger_event_ids"]
    assert mgr.revisions(agreement["agreement_id"])[-1]["actor"] == "whatsapp"


def test_set_component_status_and_locked_error_string(backbone, mgr):
    agreement = _seed(mgr)
    key = _key(agreement, "ריטיינר")
    _call(backbone, "set_component_status", agreement_id=agreement["agreement_id"], component_key=key, action="complete")
    out = _call(backbone, "update_component", agreement_id=agreement["agreement_id"], component_key=key, amount=1)
    assert out.startswith("error: locked:")


def test_complete_agreement_cascade_via_tool(backbone, mgr):
    agreement = _seed(mgr)
    out = json.loads(_call(backbone, "set_agreement_status", agreement_id=agreement["agreement_id"], action="complete"))
    statuses = {c["label"]: c["status"] for c in out["agreement"]["components"]}
    assert statuses == {"ריטיינר": "Completed", "הצלחה": "Cancelled"}


def test_add_component_and_duplicate_label_error(backbone, mgr):
    agreement = _seed(mgr)
    ok = json.loads(_call(backbone, "add_component", agreement_id=agreement["agreement_id"], label="בונוס", amount=900))
    assert "בונוס" in [c["label"] for c in ok["agreement"]["components"]]
    dup = _call(backbone, "add_component", agreement_id=agreement["agreement_id"], label="בונוס", amount=1)
    assert dup.startswith("error: validation:")


def test_unknown_agreement_and_missing_argument_and_unknown_tool(backbone):
    assert _call(backbone, "get_agreement", agreement_id="nope").startswith("error: not_found:")
    assert _call(backbone, "set_agreement_status", action="cancel").startswith("error: validation: missing")
    assert _call(backbone, "delete_component").startswith("error: unknown agreements tool")


def test_manager_absent_is_a_clean_error():
    assert _call(SimpleNamespace(agreements_manager=None), "find_agreements", client_name="x")


def test_registration_write_tools_are_gated_and_no_delete_tool():
    tools = _local_tools_by_tag()
    write_names = {t["name"] for t in tools[CapabilityTag.AGREEMENTS_WRITE]}
    read_names = {t["name"] for t in tools[CapabilityTag.AGREEMENTS_READ]}
    assert read_names == {"find_agreements", "get_agreement"}
    assert write_names == set(WRITE_TOOLS_BY_TAG[CapabilityTag.AGREEMENTS_WRITE]) <= WRITE_TOOL_NAMES
    assert not any("delete" in name for name in write_names)
