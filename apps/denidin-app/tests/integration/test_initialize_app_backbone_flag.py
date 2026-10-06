"""
Integration test (T023): denidin.py::initialize_app constructs the legacy
AIHandler when feature_flags.enable_capability_backbone is off (byte-identical to
today) and the new Backbone when it's on.

No real Green API/OpenAI network calls happen during initialize_app itself (the
OpenAI client and Morning MCP locator are both lazy - they only reach the network
on an actual request). Uses a synthetic config dict rather than config.test.json,
so this test needs no real credentials and constructs its own isolated DeniDin
instance rather than touching the module-level singleton other integration tests
share.
"""
from pathlib import Path

import pytest

import denidin as denidin_module
from src.backbone.backbone import Backbone
from src.handlers.ai_handler import AIHandler


def _config_dict(tmp_path, enable_backbone: bool) -> dict:
    return {
        "green_api_instance_id": "1234567890",
        "green_api_token": "test-token",
        "ai_api_key": "sk-test-not-a-real-key",
        "ai_model": "gpt-5.6-luna",
        "ai_vision_model": "gpt-5.6-luna",
        "ai_embedding_model": "text-embedding-3-large",
        "ai_reply_max_tokens": 1000,
        "log_level": "INFO",
        "data_root": str(tmp_path / "data"),
        "feature_flags": {"enable_capability_backbone": enable_backbone},
        # longterm storage_dir does not follow data_root - keep ChromaDB in tmp too
        "memory": {"longterm": {"storage_dir": str(tmp_path / "data" / "memory")}},
        "constitution_config": {},
        "backbone_config": {},
        "user_roles": {},
    }


@pytest.mark.integration
def test_flag_off_constructs_legacy_ai_handler_only(tmp_path):
    denidin = denidin_module.initialize_app(_config_dict(tmp_path, enable_backbone=False))
    assert isinstance(denidin.ai_manager, AIHandler)
    assert not denidin.backbone_enabled


@pytest.mark.integration
def test_flag_on_constructs_the_backbone_and_never_the_legacy_handler(tmp_path, monkeypatch):
    """REQ-063-08: with the flag on, AIHandler is never constructed - nor any of its
    own state (its pending-approval managers live only on it)."""
    import src.handlers.ai_handler as ai_handler_module

    def _must_not_construct(*_args, **_kwargs):
        raise AssertionError("AIHandler constructed with the backbone flag on")
    monkeypatch.setattr(ai_handler_module.AIHandler, "__init__", _must_not_construct)

    denidin = denidin_module.initialize_app(_config_dict(tmp_path, enable_backbone=True))
    assert isinstance(denidin.ai_manager, Backbone)
    assert denidin.backbone_enabled
    assert not hasattr(denidin, "ai_handler") and not hasattr(denidin, "backbone")


@pytest.mark.integration
@pytest.mark.parametrize("enable_backbone", [False, True])
def test_denidin_owns_the_data_and_shares_it_with_the_ai_manager(tmp_path, enable_backbone):
    """REQ-063-08: DeniDin owns its data objects; the AI implementation uses the very
    same instances, never duplicates."""
    denidin = denidin_module.initialize_app(_config_dict(tmp_path, enable_backbone=enable_backbone))
    for name in ("session_manager", "user_manager", "ledger_event_manager", "reminder_manager",
                 "memory_manager", "morning_mcp_locator", "roll_marker_store",
                 "doc_template_engine", "fee_agreement_tools"):
        assert getattr(denidin.ai_manager, name) is getattr(denidin, name), name
    assert denidin.ai_manager.telemetry_manager is denidin.telemetry_manager
    assert denidin.ledger_event_recognizer.session_manager is denidin.session_manager
