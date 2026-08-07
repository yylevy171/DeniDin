"""
Integration test for the player's LocalMediaServer (Feature 043, tasks.md T011a).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md SS VI).

Real HTTP round-trip against a real (loopback) socket - matches the pattern
tests/expensive/test_ledger_event_capture_e2e.py already uses for serving
fixture media files, factored out here as a small reusable context manager
(plan.md's LocalMediaServer) so both the player and tests can share it.
"""
import urllib.error
import urllib.request

import pytest

from player.media_server import LocalMediaServer


@pytest.mark.integration
class TestLocalMediaServer:
    def test_serves_a_file_from_the_media_dir(self, tmp_path):
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        (media_dir / "photo.jpg").write_bytes(b"fake jpeg bytes")

        with LocalMediaServer(media_dir) as base_url:
            with urllib.request.urlopen(f"{base_url}/photo.jpg") as response:
                content = response.read()

        assert content == b"fake jpeg bytes"

    def test_base_url_is_http_with_host_and_port(self, tmp_path):
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        with LocalMediaServer(media_dir) as base_url:
            assert base_url.startswith("http://")
            assert ":" in base_url.split("//", 1)[1]

    def test_missing_file_returns_404_not_a_crash(self, tmp_path):
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        with LocalMediaServer(media_dir) as base_url:
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(f"{base_url}/does_not_exist.jpg")
            assert exc_info.value.code == 404

    def test_server_stops_after_context_exit(self, tmp_path):
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        (media_dir / "photo.jpg").write_bytes(b"data")

        with LocalMediaServer(media_dir) as base_url:
            pass

        with pytest.raises(Exception):
            urllib.request.urlopen(f"{base_url}/photo.jpg", timeout=1)

    def test_two_servers_get_different_ports(self, tmp_path):
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        with LocalMediaServer(media_dir) as base_url_1:
            with LocalMediaServer(media_dir) as base_url_2:
                assert base_url_1 != base_url_2
