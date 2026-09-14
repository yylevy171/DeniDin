"""
Integration test (T023): denidin.py::initialize_app constructs the legacy
AIHandler when feature_flags.enable_capability_backbone is off (byte-identical to
today) and the new BackboneOrchestrator when it's on.

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
from src.backbone.orchestrator import BackboneOrchestrator
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
        "memory": {},
        "constitution_config": {},
        "backbone_config": {},
        "user_roles": {},
    }


@pytest.mark.integration
def test_flag_off_constructs_legacy_ai_handler_only(tmp_path):
    denidin = denidin_module.initialize_app(_config_dict(tmp_path, enable_backbone=False))
    try:
        assert isinstance(denidin.ai_handler, AIHandler)
        assert denidin.backbone_orchestrator is None
    finally:
        denidin.shutdown() if hasattr(denidin, "shutdown") else None


@pytest.mark.integration
def test_flag_on_constructs_backbone_orchestrator_alongside_legacy_handler(tmp_path):
    denidin = denidin_module.initialize_app(_config_dict(tmp_path, enable_backbone=True))
    try:
        # REQ-063-07: ai_handler is STILL constructed, unmodified, even when the
        # flag is on - only which one denidin.py's dispatch layer prefers changes.
        assert isinstance(denidin.ai_handler, AIHandler)
        assert isinstance(denidin.backbone_orchestrator, BackboneOrchestrator)
        # The new orchestrator reuses ai_handler's own manager instances
        # (REQ-063-03), never constructs duplicates.
        assert denidin.backbone_orchestrator.reminder_manager is denidin.ai_handler.reminder_manager
        assert denidin.backbone_orchestrator.ledger_event_manager is denidin.ai_handler.ledger_event_manager
    finally:
        denidin.shutdown() if hasattr(denidin, "shutdown") else None
