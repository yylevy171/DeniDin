"""Shared helper for AIHandler tests (REQ-063-08): AIHandler takes the DeniDin object and
reads everything through it. Tests get the same real objects the app would
(denidin.build_denidin_objects), built off the test's own config."""
from src.handlers.ai_handler import AIHandler
from tests.denidin_test_support import make_app_denidin


def make_ai_handler(ai_client, config, **overrides) -> AIHandler:
    """An AIHandler on a DeniDin holding every real object built from `config`;
    `overrides` replace any of them (e.g. telemetry_manager=None). The DeniDin is
    `handler.denidin`."""
    app = make_app_denidin(ai_client, config, **overrides)
    app.ai_manager = AIHandler(app)
    return app.ai_manager
