"""Unit tests for BackboneOrchestrator's prompt loading/caching (T020,
contracts/prompt-assembly.md). No real OpenAI calls."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.backbone.capability_tags import CapabilityTag
from src.backbone.orchestrator import BackboneOrchestrator
from src.models.config import AppConfiguration


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE CONTENT", encoding="utf-8")
    (base / "prompts" / "capabilities" / "reminders_read.md").write_text(
        "REMINDERS_READ CONTENT", encoding="utf-8"
    )
    return base


def _make_config(base_dir: Path) -> AppConfiguration:
    return AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(base_dir)},
    )


def test_load_backbone_reads_file(prompts_root):
    orchestrator = BackboneOrchestrator(MagicMock(), _make_config(prompts_root))
    assert orchestrator.load_backbone() == "BACKBONE CONTENT"


def test_load_backbone_caches_until_mtime_changes(prompts_root):
    orchestrator = BackboneOrchestrator(MagicMock(), _make_config(prompts_root))
    assert orchestrator.load_backbone() == "BACKBONE CONTENT"

    backbone_path = prompts_root / "prompts" / "backbone.md"
    backbone_path.write_text("UPDATED CONTENT", encoding="utf-8")
    # bump mtime explicitly - fast successive writes can share a timestamp on
    # some filesystems
    import os
    os.utime(backbone_path, (backbone_path.stat().st_mtime + 5, backbone_path.stat().st_mtime + 5))

    assert orchestrator.load_backbone() == "UPDATED CONTENT"


def test_load_capability_prompt_reads_file(prompts_root):
    orchestrator = BackboneOrchestrator(MagicMock(), _make_config(prompts_root))
    content = orchestrator.load_capability_prompt(CapabilityTag.REMINDERS_READ)
    assert content == "REMINDERS_READ CONTENT"


def test_load_capability_prompt_missing_file_returns_empty_and_warns(prompts_root, caplog):
    orchestrator = BackboneOrchestrator(MagicMock(), _make_config(prompts_root))
    content = orchestrator.load_capability_prompt(CapabilityTag.LEDGER_QUERY)
    assert content == ""


def test_load_capability_prompt_independent_cache_per_tag(prompts_root):
    (prompts_root / "prompts" / "capabilities" / "ledger_query.md").write_text(
        "LEDGER_QUERY CONTENT", encoding="utf-8"
    )
    orchestrator = BackboneOrchestrator(MagicMock(), _make_config(prompts_root))
    assert orchestrator.load_capability_prompt(CapabilityTag.REMINDERS_READ) == "REMINDERS_READ CONTENT"
    assert orchestrator.load_capability_prompt(CapabilityTag.LEDGER_QUERY) == "LEDGER_QUERY CONTENT"
