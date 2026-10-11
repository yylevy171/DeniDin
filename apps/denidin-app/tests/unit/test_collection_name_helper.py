"""Feature 070 - collection_name_for_chat (T007a).

Pins the exact production collection names and the no-raise property, so the
bugfix-035 H1 failure mode (raw @ in a group-chat collection name) cannot recur.
"""
import pytest

from src.managers.memory_collections import collection_name_for_chat


class TestCollectionNameForChat:
    def test_one_to_one_chat_matches_live_prod(self):
        assert collection_name_for_chat("972522968679@c.us") == "memory_972522968679"

    def test_group_chat_matches_live_prod(self):
        assert (
            collection_name_for_chat("120363210094632983@g.us")
            == "memory_120363210094632983_at_g.us"
        )

    def test_group_name_has_no_raw_at_sign(self):
        name = collection_name_for_chat("120363210094632983@g.us")
        assert "@" not in name
        assert ":" not in name

    @pytest.mark.parametrize(
        "chat",
        [
            "972522968679@c.us",
            "120363210094632983@g.us",
            "12345@lid",
            "weird:chat@thing.example",
            "no-suffix",
        ],
    )
    def test_never_raises_and_is_collection_safe(self, chat):
        name = collection_name_for_chat(chat)
        assert isinstance(name, str) and name
        assert "@" not in name and ":" not in name
        assert name.startswith("memory_")

    def test_deterministic(self):
        a = collection_name_for_chat("120363210094632983@g.us")
        b = collection_name_for_chat("120363210094632983@g.us")
        assert a == b
