"""Shared helpers for Backbone tests.

make_backbone (REQ-063-08): the Backbone takes the DeniDin object and reads everything
through it - so tests build a DeniDin with the same real objects initialize_app builds
(denidin.build_denidin_objects), on a throwaway data root, and replace whichever ones
the test cares about. Long-term memory is off unless the test passes its own
memory_manager.
"""
import tempfile
from pathlib import Path
from typing import Any

from src.backbone.backbone import Backbone
from src.models.config import AppConfiguration
from tests.denidin_test_support import make_app_denidin, make_session_manager, with_storage

__all__ = ["make_backbone", "make_session_manager"]


def make_backbone(ai_client: Any, config: AppConfiguration, *, backbone_class: type = Backbone,
                  **overrides: Any) -> Backbone:
    """A Backbone (or `backbone_class`, a Backbone subclass) on a DeniDin holding real
    objects built on a throwaway data root; `overrides` replace any of them (e.g.
    session_manager=..., telemetry_manager=...). The DeniDin is `backbone.denidin`."""
    data_root = Path(tempfile.mkdtemp(prefix="backbone_data_"))
    app = make_app_denidin(ai_client, with_storage(config, data_root, longterm_enabled=False), **overrides)
    app.ai_manager = backbone_class(app)
    return app.ai_manager
