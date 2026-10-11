"""Re-export of the Feature 070 US3 balance invariant.

The implementation now lives at ``src/managers/message_integrity.py`` so the
standalone ``apps/rolling-memory-backfill`` pipeline can reuse it. This shim
keeps the historical ``tests.helpers.message_integrity`` import path working.
"""
from src.managers.message_integrity import assert_message_integrity

__all__ = ["assert_message_integrity"]
