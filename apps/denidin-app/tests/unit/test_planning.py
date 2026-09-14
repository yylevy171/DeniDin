"""Unit tests for Plan parsing/validation, RBAC filtering, and fail-open behavior
(T021, data-model.md's Plan/RBAC sections)."""
from unittest.mock import MagicMock

import pytest

from src.backbone.capability_tags import CapabilityTag
from src.backbone.planning import (
    Plan,
    PlanStep,
    build_plan,
    fail_open_plan,
    parse_plan,
    role_allowed_capabilities,
)
from src.models.user import Role


def test_role_allowed_capabilities_client_gets_only_media_analysis():
    allowed = role_allowed_capabilities(Role.CLIENT)
    assert allowed == [CapabilityTag.MEDIA_ANALYSIS]


def test_role_allowed_capabilities_godfather_gets_full_domain_set():
    allowed = role_allowed_capabilities(Role.GODFATHER)
    assert CapabilityTag.MEDIA_ANALYSIS in allowed
    assert CapabilityTag.REMINDERS_WRITE in allowed
    assert CapabilityTag.LEDGER_QUERY in allowed
    assert CapabilityTag.INVOICING_READ in allowed


def test_parse_plan_empty_steps_is_valid():
    plan = parse_plan({"steps": []}, [CapabilityTag.MEDIA_ANALYSIS])
    assert plan.is_empty
    assert plan.steps == []


def test_parse_plan_drops_unrecognized_capability():
    plan = parse_plan(
        {"steps": [{"capability": "not_a_real_tag", "note": "x"}]},
        [CapabilityTag.MEDIA_ANALYSIS],
    )
    assert plan.is_empty


def test_parse_plan_drops_meta_capability_named_as_a_step():
    plan = parse_plan(
        {"steps": [{"capability": "planning", "note": "x"}]},
        [CapabilityTag.MEDIA_ANALYSIS],
    )
    assert plan.is_empty


def test_parse_plan_drops_capability_role_not_allowed():
    plan = parse_plan(
        {"steps": [{"capability": "reminders_write", "note": "x"}]},
        [CapabilityTag.MEDIA_ANALYSIS],  # role not allowed reminders_write
    )
    assert plan.is_empty


def test_parse_plan_keeps_allowed_valid_steps_in_order():
    plan = parse_plan(
        {"steps": [
            {"capability": "media_analysis", "note": "extract"},
            {"capability": "ledger_capture", "note": "recognize"},
        ]},
        [CapabilityTag.MEDIA_ANALYSIS, CapabilityTag.LEDGER_CAPTURE],
    )
    assert plan.steps == [
        PlanStep(CapabilityTag.MEDIA_ANALYSIS, "extract"),
        PlanStep(CapabilityTag.LEDGER_CAPTURE, "recognize"),
    ]


def test_parse_plan_raises_on_missing_steps_key():
    with pytest.raises(ValueError):
        parse_plan({}, [CapabilityTag.MEDIA_ANALYSIS])


def test_parse_plan_raises_on_non_dict_input():
    with pytest.raises(ValueError):
        parse_plan(None, [CapabilityTag.MEDIA_ANALYSIS])


def test_fail_open_plan_includes_every_allowed_domain_capability_in_canonical_order():
    allowed = [CapabilityTag.LEDGER_QUERY, CapabilityTag.MEDIA_ANALYSIS, CapabilityTag.REMINDERS_READ]
    plan = fail_open_plan(allowed)
    tags = [step.capability for step in plan.steps]
    # canonical order per capability_tags.CAPABILITY_INFO
    assert tags == [CapabilityTag.LEDGER_QUERY, CapabilityTag.REMINDERS_READ, CapabilityTag.MEDIA_ANALYSIS]


def test_build_plan_falls_open_on_malformed_json():
    orchestrator = MagicMock()
    orchestrator.call_capability_step.return_value = "not valid json"
    request = MagicMock()

    plan = build_plan(orchestrator, request, "some intent", [CapabilityTag.MEDIA_ANALYSIS])
    assert plan.steps == [PlanStep(CapabilityTag.MEDIA_ANALYSIS, "fail-open")]


def test_build_plan_falls_open_on_call_exception():
    orchestrator = MagicMock()
    orchestrator.call_capability_step.side_effect = RuntimeError("boom")
    request = MagicMock()

    plan = build_plan(orchestrator, request, "some intent", [CapabilityTag.LEDGER_QUERY])
    assert plan.steps == [PlanStep(CapabilityTag.LEDGER_QUERY, "fail-open")]


def test_build_plan_parses_valid_response():
    orchestrator = MagicMock()
    orchestrator.call_capability_step.return_value = '{"steps": [{"capability": "media_analysis", "note": "x"}]}'
    request = MagicMock()

    plan = build_plan(orchestrator, request, "some intent", [CapabilityTag.MEDIA_ANALYSIS])
    assert plan.steps == [PlanStep(CapabilityTag.MEDIA_ANALYSIS, "x")]
