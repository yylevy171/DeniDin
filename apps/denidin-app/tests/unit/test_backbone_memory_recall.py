"""Unit tests (Feature 063, 2026-09-15 gap fix): Backbone._recall_memory
- long-term ChromaDB daily_summary recall was never wired into this backbone at
all; every flag-on turn's RECALLED MEMORIES block was silently empty, forever."""
from unittest.mock import MagicMock

import pytest

from tests.backbone_test_support import make_backbone, make_session_manager
from src.models.config import AppConfiguration


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    return base


def _backbone(prompts_root, **kwargs):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return make_backbone(MagicMock(), config, session_manager=make_session_manager(), **kwargs)


def test_recall_memory_returns_empty_string_without_memory_manager(prompts_root):
    backbone = _backbone(prompts_root)
    assert backbone._recall_memory("שאלה", "chat1", None, None) == ""


def test_recall_memory_returns_empty_string_without_chat_id(prompts_root):
    backbone = _backbone(prompts_root, memory_manager=MagicMock())
    assert backbone._recall_memory("שאלה", None, None, None) == ""


def test_recall_memory_uses_plain_recall_without_user_manager(prompts_root):
    memory_manager = MagicMock()
    memory_manager.recall.return_value = [{"content": "עמיר שילם 5000", "similarity": 0.81}]
    backbone = _backbone(prompts_root, memory_manager=memory_manager)

    result = backbone._recall_memory("כמה שילם עמיר", "972501@c.us", None, None)

    memory_manager.recall.assert_called_once()
    assert "עמיר שילם 5000" in result
    assert "0.81" in result
    assert result.startswith("RECALLED MEMORIES")


def test_recall_memory_uses_rbac_filtered_recall_with_user_manager(prompts_root):
    memory_manager = MagicMock()
    memory_manager.recall_with_rbac_filter.return_value = [{"content": "x", "similarity": 0.9}]
    user_manager = MagicMock()
    fake_user = MagicMock(allowed_memory_scopes=["own"], can_see_all_memories=False)
    user_manager.get_user.return_value = fake_user
    backbone = _backbone(prompts_root, memory_manager=memory_manager, user_manager=user_manager)

    backbone._recall_memory("שאלה", "chat1", "972501234567", None)

    memory_manager.recall.assert_not_called()
    call_kwargs = memory_manager.recall_with_rbac_filter.call_args.kwargs
    assert call_kwargs["user_phone"] == "972501234567"
    assert call_kwargs["allowed_scopes"] == ["own"]
    assert call_kwargs["can_see_all_memories"] is False


def test_recall_memory_returns_empty_string_when_nothing_found(prompts_root):
    memory_manager = MagicMock()
    memory_manager.recall.return_value = []
    backbone = _backbone(prompts_root, memory_manager=memory_manager)
    assert backbone._recall_memory("שאלה", "chat1", None, None) == ""


def test_recall_memory_never_raises_on_failure(prompts_root):
    memory_manager = MagicMock()
    memory_manager.recall.side_effect = RuntimeError("chromadb down")
    backbone = _backbone(prompts_root, memory_manager=memory_manager)
    assert backbone._recall_memory("שאלה", "chat1", None, None) == ""
