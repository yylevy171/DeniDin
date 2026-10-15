"""Shared helper for tests that need an AI manager on a real DeniDin (REQ-063-08). The legacy
AIHandler is gone (Feature 067 no-turn redesign); the one implementation is the Backbone."""
from src.backbone.backbone import Backbone
from tests.denidin_test_support import make_app_denidin


def make_ai_handler(ai_client, config, **overrides) -> Backbone:
    """A Backbone on a DeniDin holding every real object built from `config`; `overrides` replace any
    of them. The DeniDin is `handler.denidin`."""
    app = make_app_denidin(ai_client, config, **overrides)
    app.ai_manager = Backbone(app)
    return app.ai_manager
