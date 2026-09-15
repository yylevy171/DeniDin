"""Real-sandbox integration test: Feature 072 Phase 1.a - MCP-Layer Latency
Proof (user-stories.md, "Revised and approved 2026-09-15, per operator
direction"). Proves the transparent cache actually eliminates the Morning
API round-trip at the MCP layer, in isolation - no OpenAI call needed, since
the thing being measured is purely `resolve_client_name`'s own execution
time.

No mocking (CONSTITUTION §V) - every call goes to the real Morning sandbox;
`TimestampingSearchClient` (_cache_test_helpers.py) is a thin pass-through
SPY, not a stand-in for a response.

Scenario (verbatim from user-stories.md):
  1. With the cache effectively OFF (no ClientCache passed - the exact
     byte-for-byte pre-feature code path, CONSTITUTION §VI), call
     resolve_client_name for the same known client 50 times, recording each
     call's wall-clock time.
  2. With the cache ON (a real ClientCache passed - cache warmed on the
     first call), repeat the same 50 calls.
  3. Compute and assert the average time for the flag-ON run is measurably
     lower than the flag-OFF run.

Proof required (per spec): print/log the exact average time saved per call.
If the average saved is negligible, that is a real finding to surface, not
a reason to weaken the assertion - so this test intentionally does NOT
hardcode a specific savings threshold beyond "measurably lower" (mean_on <
mean_off), and prints the full before/after numbers for a human to judge.

Per explicit operator instruction (2026-09-15): every one of the 50 MCP-
level resolve_client_name calls in each run, AND every real Morning HTTP
call made underneath, gets its own exact Israel-local wall-clock start/end
timestamp recorded (CONSTITUTION §II - now_local()/local_isoformat(), never
a bare datetime.now()) - not just an aggregate duration. The full per-call
log for both runs is written to a JSON file under logs/test_logs/ (this
app's existing test-log convention) so the raw timestamps are available for
inspection after the run, not just the printed summary.

NOTE: this test is deliberately NOT yet run (2026-09-15, explicit operator
instruction: "You can write the code for it, but dont start it yet") - it
makes 100 real Morning API calls (50 flag-off + 50 flag-on), which given
this session has already hit the sandbox's own POST /clients rate limit
more than once, needs a fresh, deliberate go-ahead before executing.
"""
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.client_cache import ClientCache
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import add_client, resolve_client_name
from denidin_mcp_morning.utils.time_utils import local_isoformat, now_local

from ._cache_test_helpers import TimestampingSearchClient

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"
LOG_DIR = APP_ROOT / "logs" / "test_logs"

_CALLS_PER_RUN = 50


@pytest.fixture
def morning_client():
    config = load_config(CONFIG_PATH)
    if not (config.api_key_id and config.api_key_secret):
        pytest.skip("No api_key_id/api_key_secret in config.test.json")
    return MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        auth_url=config.auth_url,
    )


def _timed_calls(spy, name: str, cache, count: int) -> list:
    """Call resolve_client_name `count` times against the real sandbox
    (through `spy`, so every underlying Morning call spy records is also
    timestamped), returning one dict per MCP-level call:
        {"call_index", "started_at", "ended_at", "duration_s"}
    Israel-local ISO timestamps throughout (CONSTITUTION §II)."""
    records = []
    for i in range(count):
        started = now_local()
        start_perf = time.perf_counter()
        resolve_client_name(spy, name, cache=cache)
        duration = time.perf_counter() - start_perf
        ended = now_local()
        records.append(
            {
                "call_index": i,
                "started_at": local_isoformat(started),
                "ended_at": local_isoformat(ended),
                "duration_s": duration,
            }
        )
    return records


def test_cache_on_is_measurably_faster_than_cache_off_for_repeated_resolution(
    morning_client, tmp_path: Path
):
    unique_marker = f"DENIDIN_LATENCY_PROOF_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    # Sandbox-unique tokens (not ordinary English words - see
    # test_client_cache_miss_then_hit.py's comment on why) so this doesn't
    # collide with leftover sandbox test data and risk an ambiguous match,
    # which would make the flag-off run's own timing meaningless.
    name = f"ZL{unique_marker} ZM{unique_marker}"

    # add_client's own write-through is irrelevant here - only cache=None is
    # ever passed to it, so this creation never touches any cache regardless
    # of which run below uses it.
    add_client(
        morning_client, name=name, email=f"{unique_marker}@example.com",
        phone="050-1234567", cache=None,
    )

    # Flag OFF: no ClientCache object even constructed on this path - the
    # exact byte-for-byte pre-feature code path (CONSTITUTION §VI). Every
    # one of these 50 calls is expected to make its own real search_clients
    # call underneath - the spy timestamps each one.
    off_spy = TimestampingSearchClient(morning_client)
    off_mcp_calls = _timed_calls(off_spy, name, cache=None, count=_CALLS_PER_RUN)

    # Flag ON: a real ClientCache, warmed by the very first of these 50 calls
    # (a live miss -> write-through), every subsequent call a hit - the spy
    # is expected to record exactly ONE underlying search_clients call
    # across all 50 MCP-level calls.
    cache = ClientCache(tmp_path / "client_cache.db")
    on_spy = TimestampingSearchClient(morning_client)
    on_mcp_calls = _timed_calls(on_spy, name, cache=cache, count=_CALLS_PER_RUN)

    off_durations = [r["duration_s"] for r in off_mcp_calls]
    on_durations = [r["duration_s"] for r in on_mcp_calls]
    mean_off = statistics.mean(off_durations)
    mean_on = statistics.mean(on_durations)
    saved = mean_off - mean_on

    log_payload = {
        "test": "test_cache_on_is_measurably_faster_than_cache_off_for_repeated_resolution",
        "calls_per_run": _CALLS_PER_RUN,
        "client_name": name,
        "flag_off": {
            "mcp_calls": off_mcp_calls,  # 50 entries, each with its own started_at/ended_at
            "morning_calls": off_spy.calls,  # every real search_clients call, timestamped
            "mean_duration_s": mean_off,
            "median_duration_s": statistics.median(off_durations),
        },
        "flag_on": {
            "mcp_calls": on_mcp_calls,  # 50 entries, each with its own started_at/ended_at
            "morning_calls": on_spy.calls,  # every real search_clients call, timestamped
            "mean_duration_s": mean_on,
            "median_duration_s": statistics.median(on_durations),
        },
        "mean_time_saved_per_call_s": saved,
    }

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"client_cache_latency_proof_{int(datetime.now(timezone.utc).timestamp())}.json"
    log_path.write_text(json.dumps(log_payload, ensure_ascii=False, indent=2))

    print(
        f"\n[Feature 072 Phase 1.a] resolve_client_name, {_CALLS_PER_RUN} calls each:\n"
        f"  flag OFF: mean={mean_off:.4f}s  median={statistics.median(off_durations):.4f}s  "
        f"real Morning search_clients calls={len(off_spy.calls)}\n"
        f"  flag ON:  mean={mean_on:.4f}s  median={statistics.median(on_durations):.4f}s  "
        f"real Morning search_clients calls={len(on_spy.calls)}\n"
        f"  mean time saved per call: {saved:.4f}s "
        f"({(saved / mean_off * 100) if mean_off else 0:.1f}% of the flag-off mean)\n"
        f"  full per-call timestamp log: {log_path}\n"
    )

    # Per spec: assert "measurably lower", not any specific magnitude - a
    # negligible saving is a real finding to surface, not something to hide
    # behind a weakened assertion.
    assert mean_on < mean_off, (
        f"cache-on mean ({mean_on:.4f}s) was not lower than cache-off mean "
        f"({mean_off:.4f}s) - the cache-hit fast path did not measurably help"
    )
