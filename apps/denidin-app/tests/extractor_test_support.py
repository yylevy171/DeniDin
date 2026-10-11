"""Shared helper for media-extractor tests (REQ-063-08): extractors read
`context.ai_manager` - its `client`, `extraction_prompt_prefix()`,
`capture_ledger_events_from_text()` and `single_prompt_text()`. This gives a Mock
ai_manager whose `single_prompt_text` is the REAL AIManager implementation, running
over the mocked `client.responses.create` the tests script."""
import functools
from unittest.mock import Mock

from src.core.ai_manager import AIManager


def make_extractor_ai_manager(prefix: str = "") -> Mock:
    ai_manager = Mock()
    ai_manager.extraction_prompt_prefix = Mock(return_value=prefix)
    ai_manager.capture_ledger_events_from_text = Mock(return_value=[])
    ai_manager.call_model_with_retry = AIManager.call_model_with_retry
    ai_manager.single_prompt_text = functools.partial(AIManager.single_prompt_text, ai_manager)
    return ai_manager
