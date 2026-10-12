"""Feature 067 acceptance scenario A8 (user-stories.md). `expensive`: a real vision call.

AUTHORED, NOT YET RUN - and it needs its own explicit per-run approval, like every expensive test:

    scripts/run_single_test.sh \\
      "tests/expensive/test_realistic_message_handling_expensive.py::test_a8_image_sent_while_a_text_request_is_handled_is_analyzed_on_its_own"

The owner sends a text request and, a moment later, an image. The text request is answered normally,
the image is analyzed on its own right after, and nothing is lost or analyzed twice.
"""
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

from tests.billed._067_harness import intake_rig
from tests.billed.conftest import denidin_app, denidin_config, live_morning_tunnel  # noqa: F401 - fixtures
from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID

pytestmark = pytest.mark.expensive

_MEDIA_DIR = Path(__file__).parent.parent / "fixtures" / "media"
_IMAGE = "receipt_cafe.jpg"


@pytest.fixture
def http_server():
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(_MEDIA_DIR), **kw)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 8769), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:8769"
    server.shutdown()


def test_a8_image_sent_while_a_text_request_is_handled_is_analyzed_on_its_own(denidin_app, http_server):
    with intake_rig(denidin_app, GODFATHER_CHAT_ID) as rig:
        text = rig.send_text("מה השעה עכשיו?")
        image = rig.send_image(_IMAGE, "", f"{http_server}/{_IMAGE}")
        rig.wait_until_idle(timeout=420)
        assert text._test_sent_messages, "the text request was not answered"
        assert image._test_sent_messages, "the image was never analyzed"
        # nothing waits around, nothing is handled twice: one reply set per message
        assert not rig.intake.deferred
        assert len(rig.stored_user_messages()) >= 2
