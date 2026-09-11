"""
Pytest configuration for DeniDin test suite.

Automatically configures logging for all tests:
- Production: logs/denidin.log
- Tests: logs/test_logs/{test_file_name}.log (automatic, per test file)
"""
import os
import sys
import pytest
import logging
import warnings
from pathlib import Path

# Suppress SWIG deprecation warnings from ChromaDB before any imports
warnings.filterwarnings("ignore", message=".*builtin type.*has no __module__ attribute")

# Add src directory to Python path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from src.utils.logger import LOCAL_LOG_DATEFMT, LocalTimeFormatter  # noqa: E402

# Track current test file for logging
_current_test_file = None


class _RateLimitSentinelHandler(logging.Handler):
    """Feature 059 item 3: detect a real OpenAI 429 rate-limit during a
    billed/expensive test.

    A billed/expensive test that fails because OpenAI returned repeated
    `429 Too Many Requests` - so the app exhausted its retries and returned
    its `"I'm currently at capacity"` fallback (`ai_handler.py`) - is exhibiting
    CORRECT behavior under real rate-limit pressure, not a code defect. But it
    is also not a trustworthy pass or fail: the test's real assertions ran
    against a degraded response. Historically this was indistinguishable from an
    actual regression without reading the raw HTTP log by hand (Feature 054
    finish-up, 2026-08-19).

    This handler buffers, per test, whether the app logged a
    retries-exhausted rate-limit event. `pytest_runtest_makereport` reads it and,
    for `billed`/`expensive` tests only, forces the result to FAILED (never
    skip/xfail) with an unmistakable banner telling the reader to re-run once
    the OpenAI rate-limit window resets before investigating as a bug.
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
        except Exception:  # pragma: no cover - defensive, never fail a test on logging
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
    """Register custom markers and filter warnings."""
    config.addinivalue_line(
        "markers",
        "billed: Tests that make real, text-only OpenAI API calls (cheap; skip by default)"
    )
    config.addinivalue_line(
        "markers",
        "expensive: Tests that make real vision/image/PDF/DOCX OpenAI API calls (costlier; skip by default)"
    )
    
    # Suppress harmless SWIG deprecation warnings from ChromaDB
    warnings.filterwarnings(
        "ignore",
        message=".*builtin type.*has no __module__ attribute",
        category=DeprecationWarning
    )

    # Live per-test sound-off — ON BY DEFAULT for every pytest invocation
    # (CLAUDE.md / METHODOLOGY.md §VI / CONSTITUTION.md §V: an individual
    # PASS/FAIL/ERROR/SKIP line MUST be emitted the moment each test's result is
    # determined — serial or parallel, sanity or not, one test or a thousand).
    # Prints one `>>> TEST [k/N] STATUS: <nodeid>` line plus a grep-friendly
    # `TEST-PROGRESS ...` line per test as it finishes. pytest-xdist otherwise
    # streams almost nothing while workers churn, which is exactly the case this
    # guards against. Controller process only (xdist workers stay quiet so the
    # controller is the single voice). Opt OUT only with DENIDIN_TEST_SOUNDOFF=0.
    # SANITY_PARALLEL_SOUNDOFF=1 is still honoured as a forcing alias.
    global _SOUNDOFF_ON
    _SOUNDOFF_ON = (
        os.environ.get("DENIDIN_TEST_SOUNDOFF", "1") != "0"
        or os.environ.get("SANITY_PARALLEL_SOUNDOFF") == "1"
    ) and not hasattr(config, "workerinput")


_SOUNDOFF_ON = False
_soundoff = {"done": 0, "total": 0, "ids": set()}


def pytest_xdist_node_collection_finished(node, ids):
    """xdist: each worker reports its collected ids - union gives the real total."""
    if _SOUNDOFF_ON:
        _soundoff["ids"].update(ids)
        _soundoff["total"] = len(_soundoff["ids"])


def pytest_collection_finish(session):
    """Non-xdist fallback (e.g. a subset run with -n 0/1 on the controller)."""
    if _SOUNDOFF_ON and not _soundoff["total"]:
        _soundoff["total"] = len(getattr(session, "items", []) or [])


def pytest_runtest_logreport(report):
    if not _SOUNDOFF_ON:
        return
    # One line per test: its `call` result, or a setup that errored/skipped.
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
    
    # Get the test file name (e.g., 'test_ai_handler.py' -> 'test_ai_handler')
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

    # Feature 059 item 3: the loop above just stripped every root handler, so
    # re-attach the per-test rate-limit sentinel and clear its buffer for this
    # test. Applies to every test cheaply; only billed/expensive results act on
    # it (see pytest_runtest_makereport).
    _rate_limit_sentinel.reset()
    root_logger.addHandler(_rate_limit_sentinel)
    
    # Ensure all child loggers inherit from root
    for name in logging.root.manager.loggerDict:
        logger_obj = logging.getLogger(name)
        if isinstance(logger_obj, logging.Logger):
            logger_obj.propagate = True  # Ensure propagation to root logger
            # Reset each logger's OWN level too, not just propagate: modules
            # like ai_handler.py create their logger via get_logger(__name__)
            # at import time with an explicit level (default INFO), and a
            # logger's own explicit level short-circuits isEnabledFor() before
            # propagation is even considered - setting propagate=True alone
            # does NOT make logger.debug() calls appear just because the root
            # logger is DEBUG. NOTSET makes it defer to the root's level.
            logger_obj.setLevel(logging.NOTSET)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Feature 059 item 3: for billed/expensive tests only, if the app logged a
    retries-exhausted OpenAI 429 during the test's `call` phase, force the
    result to FAILED (never skip/xfail) with an unmistakable banner.

    A rate-limited run is not a trustworthy pass or fail - the assertions ran
    against the app's `"I'm currently at capacity"` fallback. The test stays
    FAILED on every re-run until the OpenAI rate-limit window resets, which is
    the intended signal: fix nothing, wait, re-run.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    marker_names = {m.name for m in item.iter_markers()}
    if not marker_names & {"billed", "expensive"}:
        return

    # Two ways a real 429 shows up: (a) the app caught RateLimitError, logged it,
    # and returned its capacity fallback - the log sentinel catches that;
    # (b) a test called OpenAI directly and the SDK re-raised RateLimitError
    # after its own retries - that surfaces as the test's own exception.
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
        "The app exhausted its OpenAI retries during this test and returned its\n"
        "\"I'm currently at capacity\" fallback. That is the app's CORRECT behavior under\n"
        "real rate-limit pressure - it is NOT necessarily a code defect.\n"
        "\n"
        "This run is marked FAILED (never skipped) on purpose: the assertions ran against\n"
        "a degraded response, so neither a pass nor a fail here can be trusted.\n"
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


@pytest.fixture(scope="module")
def test_logger_config(request):
    """
    Provide logger configuration for each test module.
    
    NOTE: This fixture is now optional - logging is automatically configured
    via pytest_runtest_setup hook. Keep for backward compatibility.
    """
    module_name = Path(request.module.__file__).stem
    
    return {
        'logs_dir': 'logs',
        'log_filename': f'test_logs/{module_name}.log',
        'log_level': 'DEBUG'
    }

