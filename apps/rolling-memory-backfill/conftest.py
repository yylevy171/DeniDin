"""Pytest bootstrap for the rolling-memory-backfill suite (Feature 070, US4).

Sys.path insertion of both this app's own root (so ``import _denidin_loader`` and
``import backfill_daily_summaries`` resolve) and ``apps/denidin-app`` root (so the
real Feature 070 modules import), mirroring ``apps/prod-ledger-backfill/conftest.py``.
Neither sibling app is pip-installable.
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent
REPO_ROOT = PROJECT_ROOT.parent.parent
DENIDIN_APP_ROOT = REPO_ROOT / "apps" / "denidin-app"

for path in (PROJECT_ROOT, DENIDIN_APP_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "billed: real, text-only OpenAI calls (see pytest.ini)",
    )


@pytest.fixture
def fake_openai_client():
    """OpenAI network boundary only — responses echo the transcript so a token in
    a seeded message reaches both the summary and the embedding call."""
    from types import SimpleNamespace

    calls = {"responses": [], "embeddings": []}

    def responses_create(**kwargs):
        calls["responses"].append(kwargs)
        return SimpleNamespace(output_text="SUMMARY: " + kwargs.get("input", ""))

    def embeddings_create(model, input):  # noqa: A002 - OpenAI's own kwarg name
        calls["embeddings"].append(input)
        vec = [float((sum(bytearray(input.encode())) % 97) + i) for i in range(16)]
        return SimpleNamespace(data=[SimpleNamespace(embedding=vec)])

    client = SimpleNamespace(
        responses=SimpleNamespace(create=responses_create),
        embeddings=SimpleNamespace(create=embeddings_create),
        with_options=lambda **_k: SimpleNamespace(
            responses=SimpleNamespace(create=responses_create)
        ),
    )
    client._calls = calls
    return client
