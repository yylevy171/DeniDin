"""Feature 067: every expensive test starts every chat from a clean conversation (see
tests/billed/conftest.py's _fresh_conversation_for_every_test for why)."""
import pytest


@pytest.fixture(autouse=True)
def _fresh_conversation_for_every_test():
    from tests.e2e_helpers import start_every_chat_fresh
    start_every_chat_fresh()
    yield
