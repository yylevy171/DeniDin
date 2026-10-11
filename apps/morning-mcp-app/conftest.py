"""
Pytest configuration for the morning-mcp-app test suite.

Automatically configures logging for all tests (mirrors
apps/denidin-app/conftest.py exactly):
- Production: logs/morning-mcp.log
- Tests: logs/test_logs/{test_file_name}.log (automatic, per test file)
"""
import os
import sys
import logging
from pathlib import Path

import pytest

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from denidin_mcp_morning.utils.logger import LOCAL_LOG_DATEFMT, LocalTimeFormatter  # noqa: E402

# Track current test file for logging
_current_test_file = None


class _RateLimitSentinelHandler(logging.Handler):
    """Feature 059 item 3 (mirrors apps/denidin-app/conftest.py): detect a real
    OpenAI 429 rate-limit during a billed/expensive test.

    A billed/expensive test that fails only because OpenAI returned repeated
    `429 Too Many Requests` is exhibiting rate-limit pressure, not a code
    defect - but its result cannot be trusted either. This handler buffers,
    per test, whether a retries-exhausted rate-limit event was logged;
    `pytest_runtest_makereport` also inspects the test's own exception chain
    (these tests call OpenAI directly, so the SDK re-raises RateLimitError
    rather than anything logging it). Either way, billed/expensive results are
    forced to FAILED (never skip/xfail) with an unmistakable banner.
    """

    _MSG_SIGNATURES = (
        "rate limit exceeded",
        "error code: 429",
        "429 too many requests",
        "ratelimiterror",
    )

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.tripped = False
        self.detail = None

    def reset(self):
        self.tripped = False
        self.detail = None

    def emit(self, record):
        if self.tripped:
            return
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - never fail a test on logging
            message = str(getattr(record, "msg", ""))
        haystack = message.lower()
        hit = any(sig in haystack for sig in self._MSG_SIGNATURES)
        if not hit and record.exc_info and record.exc_info[0] is not None:
            hit = record.exc_info[0].__name__ == "RateLimitError"
        if hit:
            self.tripped = True
            self.detail = message


_rate_limit_sentinel = _RateLimitSentinelHandler()


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (hit the real Morning sandbox API)"
    )
    config.addinivalue_line(
        "markers",
        "billed: Tests that make real, text-only OpenAI API calls (cheap; skip by default)"
    )
    config.addinivalue_line(
        "markers",
        "expensive: Tests that make real vision/image/PDF/DOCX OpenAI API calls (costlier; skip by default)"
    )

    # Live per-test sound-off — ON BY DEFAULT (mirrors apps/denidin-app/conftest.py;
    # CLAUDE.md / METHODOLOGY.md §VI / CONSTITUTION.md §V). One
    # `>>> TEST [k/N] STATUS: <nodeid>` + `TEST-PROGRESS ...` line per test the
    # moment its result is determined. Controller process only. Opt out with
    # DENIDIN_TEST_SOUNDOFF=0; SANITY_PARALLEL_SOUNDOFF=1 forces it on.
    global _SOUNDOFF_ON
    _SOUNDOFF_ON = (
        os.environ.get("DENIDIN_TEST_SOUNDOFF", "1") != "0"
        or os.environ.get("SANITY_PARALLEL_SOUNDOFF") == "1"
    ) and not hasattr(config, "workerinput")


_SOUNDOFF_ON = False
_soundoff = {"done": 0, "total": 0}


def pytest_collection_finish(session):
    # morning-mcp-app tests run serially (no pytest-xdist dependency here), so
    # the core collection hook is enough for the k/N total.
    if _SOUNDOFF_ON and not _soundoff["total"]:
        _soundoff["total"] = len(getattr(session, "items", []) or [])


def pytest_runtest_logreport(report):
    if not _SOUNDOFF_ON:
        return
    if report.when == "call":
        status = report.outcome.upper()
    elif report.when == "setup" and report.outcome in ("failed", "skipped"):
        status = "ERROR" if report.outcome == "failed" else "SKIP"
    else:
        return
    _soundoff["done"] += 1
    n, total = _soundoff["done"], (_soundoff["total"] or "?")
    worker = getattr(report, "worker_id", "") or getattr(report, "node", "") or ""
    tag = f"  ({worker})" if worker else ""
    print(f"\n>>> TEST [{n}/{total}] {status}: {report.nodeid}{tag}", flush=True)
    print(f"TEST-PROGRESS done={n} total={total} status={status} node={report.nodeid}", flush=True)


@pytest.fixture(scope="session", autouse=True)
def setup_test_logging():
    """
    Configure logging for test session.
    Creates logs/test_logs directory for all test logs.
    """
    test_logs_dir = project_root / "logs" / "test_logs"
    test_logs_dir.mkdir(parents=True, exist_ok=True)
    yield
    # Cleanup happens automatically via .gitignore


def pytest_runtest_setup(item):
    """
    Pytest hook: Configure logging before each test runs.
    Automatically sets up per-test-file logging.
    Clears all existing loggers to ensure test logs go to test_logs directory.
    """
    global _current_test_file

    # Get the test file name (e.g., 'test_config.py' -> 'test_config')
    test_file = Path(item.fspath).stem
    _current_test_file = test_file

    # Configure logging for this test file
    log_filename = f'test_logs/{test_file}.log'
    log_path = project_root / "logs" / log_filename

    # Ensure the directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Clear ALL existing loggers and their handlers (including module-level loggers)
    # This ensures that any loggers created during module import are reconfigured
    loggers_to_clear = [logging.getLogger()] + [
        logging.getLogger(name) for name in logging.root.manager.loggerDict
    ]

    for logger_obj in loggers_to_clear:
        if isinstance(logger_obj, logging.Logger):
            for handler in logger_obj.handlers[:]:
                handler.close()
                logger_obj.removeHandler(handler)

    # Set up root logger with file handler for this test file
    root_logger = logging.getLogger()

    # bugfix-037: test logs use the same Israel-local, offset-bearing timestamps
    # as the apps' own logs, so a test log can be read against a prod log directly.
    formatter = LocalTimeFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt=LOCAL_LOG_DATEFMT
    )

    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)

    # Feature 059 item 3: re-attach the per-test rate-limit sentinel (the loop
    # above just stripped every root handler) and clear its buffer.
    _rate_limit_sentinel.reset()
    root_logger.addHandler(_rate_limit_sentinel)

    # Ensure all child loggers inherit from root
    for name in logging.root.manager.loggerDict:
        logger_obj = logging.getLogger(name)
        if isinstance(logger_obj, logging.Logger):
            logger_obj.propagate = True  # Ensure propagation to root logger


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Feature 059 item 3 (mirrors apps/denidin-app/conftest.py): for
    billed/expensive tests only, if a real OpenAI 429 rate-limit occurred
    during the `call` phase, force the result to FAILED (never skip/xfail)
    with an unmistakable banner. The test stays FAILED on every re-run until
    the OpenAI rate-limit window resets - the intended signal: fix nothing,
    wait, re-run.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    marker_names = {m.name for m in item.iter_markers()}
    if not marker_names & {"billed", "expensive"}:
        return

    detail = _rate_limit_sentinel.detail
    rate_limited = _rate_limit_sentinel.tripped
    if not rate_limited and call.excinfo is not None:
        chain = []
        exc = call.excinfo.value
        while exc is not None and exc not in chain:
            chain.append(exc)
            exc = exc.__cause__ or exc.__context__
        for exc in chain:
            text = f"{type(exc).__name__}: {exc}".lower()
            if type(exc).__name__ == "RateLimitError" or "error code: 429" in text or "429 too many requests" in text:
                rate_limited = True
                detail = f"{type(exc).__name__}: {exc}"
                break
    if not rate_limited:
        return

    banner = (
        "\n"
        "============== OPENAI RATE LIMIT (429) DETECTED - Feature 059 item 3 ==============\n"
        "OpenAI returned repeated 429s during this test. That is real rate-limit pressure,\n"
        "NOT necessarily a code defect.\n"
        "\n"
        "This run is marked FAILED (never skipped) on purpose: a rate-limited run is not a\n"
        "trustworthy pass or fail.\n"
        "\n"
        "DO NOT investigate this as a bug yet. Wait for the OpenAI rate-limit window to\n"
        "reset, then re-run this test unchanged.\n"
        f"\nDetail: {detail}\n"
        "================================================================================="
    )
    report.outcome = "failed"
    if report.longrepr is None:
        report.longrepr = banner
    else:
        report.sections.append(("OpenAI rate limit (Feature 059 item 3)", banner))
