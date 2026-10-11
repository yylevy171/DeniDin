"""Feature 070 — summarize_conversation (T021a).

contracts/summarizer.md: returns the model summary on success; on ANY exception
from the OpenAI call returns the raw transcript (fallback) and logs one WARNING,
never raises; no embedding / ChromaDB / marker side effects.
"""
from types import SimpleNamespace

import pytest

from src.handlers import summarizer
from src.handlers.summarizer import summarize_conversation

MESSAGES = [
    {"role": "user", "content": "מתי הפגישה?"},
    {"role": "assistant", "content": "מחר ב-10:00"},
]


class _FakeResponses:
    def __init__(self, *, output_text=None, raises=None):
        self._output_text = output_text
        self._raises = raises
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise self._raises
        return SimpleNamespace(output_text=self._output_text)


class _FakeClient:
    def __init__(self, responses):
        self.responses = responses


def test_returns_model_summary_on_success():
    client = _FakeClient(_FakeResponses(output_text="  • fact\n\nsummary body  "))
    out = summarize_conversation(client, "gpt-5.6-luna", MESSAGES)
    assert out == "• fact\n\nsummary body"
    assert client.responses.calls[0]["model"] == "gpt-5.6-luna"
    assert "user: מתי הפגישה?" in client.responses.calls[0]["input"]


def test_falls_back_to_raw_transcript_and_warns_once(caplog):
    client = _FakeClient(_FakeResponses(raises=RuntimeError("network down")))
    with caplog.at_level("WARNING"):
        out = summarize_conversation(client, "gpt-5.6-luna", MESSAGES)
    assert out == "user: מתי הפגישה?\nassistant: מחר ב-10:00"
    assert sum(1 for r in caplog.records if r.levelname == "WARNING") == 1


def test_empty_model_output_falls_back_to_transcript():
    client = _FakeClient(_FakeResponses(output_text=""))
    out = summarize_conversation(client, "gpt-5.6-luna", MESSAGES)
    assert out == "user: מתי הפגישה?\nassistant: מחר ב-10:00"


def test_never_touches_chromadb_or_markers(monkeypatch):
    # If summarize_conversation imported/used a MemoryManager or RollMarkerStore
    # it would be visible on the module; assert it doesn't.
    assert not hasattr(summarizer, "MemoryManager")
    assert not hasattr(summarizer, "RollMarkerStore")


def test_group_prefixed_content_passes_through_verbatim():
    client = _FakeClient(_FakeResponses(output_text="ok"))
    summarize_conversation(
        client, "m", [{"role": "user", "content": "[Dana] שלום"}]
    )
    assert "user: [Dana] שלום" in client.responses.calls[0]["input"]
