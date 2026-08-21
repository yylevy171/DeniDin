"""
Accounting document reconciliation service (Feature 025).

The single shared background mechanism that polls Morning for documents
created directly there (with no matching DeniDin conversation) and captures
them as LedgerEvents (source_type="חשבונית") - structurally mirrors
services/reminder_delivery_service.py's shape (Feature 054): one shared
worker function, called both periodically (APScheduler BackgroundScheduler +
CronTrigger) and once at startup for catch-up. See
specs/in-progress/025-morning-sourced-ledger-events/contracts/
accounting-reconciliation-service.md for the full contract this file
implements.

Unlike reminder delivery, this sweep never sends anything user-facing (no
WhatsApp message) - it is a silent background reconciliation whose only
output is persisted LedgerEvent files, discoverable the same way any other
ledger event already is.

Exactly one shared sweep mechanism for the whole process - not one job per
poll target (same guardrail as reminder_delivery_service.py).
"""
import re
from datetime import timedelta
from typing import Any, List, Optional

# type: ignore[import-untyped] on both - no stub package exists for apscheduler
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]

from src.handlers.ai_handler import LEDGER_EVENT_TOOL
from src.models.user import Role
from src.utils.logger import get_logger
from src.utils.time_utils import now_local

logger = get_logger(__name__)

# Revised 2026-08-21 (round 3): no more startup/periodic lookback split - that
# only mattered for a per-tick disk-rescan design this feature no longer has
# (the watermark is now derived from LedgerEventManager's in-memory cache,
# built once via a lazy one-time scan - see ledger_event_manager.py). One
# fallback lookback, used only when the cache is empty (no חשבונית event
# ever captured this process/environment yet).
FALLBACK_LOOKBACK = timedelta(days=1)

# Safety cap (spec.md Clarifications, round 3, user directive: "I don't want
# this to become a backfill mechanism"): if the gap since the derived
# watermark exceeds EITHER bound, the sweep skips/discards the ENTIRE tick
# (captures nothing, does not advance anything) rather than attempting a
# partial catch-up. The 5-day half is a genuine pre-check (pure local
# computation, no call needed). The 100-document half is a POST-check
# (round 4, spec.md's Clarifications) - no direct, non-AI MCP-client
# mechanism exists in this app to check it before calling OpenAI, so the
# service instead inspects the real list_invoices mcp_call's own output text
# (never the AI's summary/prose) AFTER the one OpenAI+MCP call completes,
# and discards that turn's captures entirely if breached. Logged at ERROR
# only on breach; no persisted tracker, no WhatsApp alert (this sweep stays
# a silent, log-discoverable-only mechanism throughout).
MAX_CATCHUP_LOOKBACK = timedelta(days=5)
MAX_CATCHUP_DOCUMENT_COUNT = 100

RECONCILIATION_SWEEP_JOB_ID = "accounting_document_reconciliation_sweep"

# morning-mcp-app's formatters.py always states the TRUE total count of
# matching documents, in one of these fixed Hebrew phrasings (format_invoice_list/
# format_too_many_invoices_message) - parsed here so the safety cap's
# 100-document check reads the tool's own real structured-ish output, never
# the AI's own summary. Order matters: the "too many" phrase is checked
# before the plain "found" phrase since both start with "נמצאו".
_TOO_MANY_RE = re.compile(r"נמצאו (\d+) חשבוניות התואמות את החיפוש - יותר מדי")
_TRUNCATED_RE = re.compile(r"מוצגות \d+ מתוך (\d+) חשבוניות שנמצאו")
_FOUND_RE = re.compile(r"נמצאו (\d+) חשבוניות:")
_NONE_FOUND_TEXT = "לא נמצאו חשבוניות"


def _parse_list_invoices_total(response: Any) -> Optional[int]:
    """Extracts the TRUE total candidate-document count from every
    list_invoices mcp_call in `response.output`, taking the max across calls
    if the model queried more than once. Returns None if no list_invoices
    call was made at all (a normal case - e.g. zero candidates, or the model
    never needed to call it) - callers must treat None as "nothing to check
    against the cap", not as an error. Logs a WARNING (but still returns
    None) if a list_invoices call WAS made but its output didn't match any
    known phrasing - a residual gap flagged for future tightening, not
    silently pretended to be a hard guarantee.
    """
    totals: List[int] = []
    found_any_call = False
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "mcp_call" or getattr(item, "name", None) != "list_invoices":
            continue
        found_any_call = True
        output_text = getattr(item, "output", None) or ""
        if _NONE_FOUND_TEXT in output_text:
            totals.append(0)
            continue
        match = _TOO_MANY_RE.search(output_text) or _TRUNCATED_RE.search(output_text) or _FOUND_RE.search(output_text)
        if match:
            totals.append(int(match.group(1)))
        else:
            logger.warning(
                "[025] list_invoices mcp_call output didn't match any known total-count "
                f"phrasing - cannot verify the safety cap for this call: {output_text!r}"
            )

    if not totals:
        if found_any_call:
            return None  # a call happened but nothing was parseable - see WARNING above
        return None  # no list_invoices call at all - nothing to check
    return max(totals)


def _build_reconciliation_prompt(since) -> str:
    """The dedicated, non-conversational prompt for the reconciliation sweep
    (contracts/accounting-reconciliation-service.md) - NOT
    runtime_constitution.md, NOT AIHandler._build_instructions' normal
    assembly. `since` is an aware datetime (Israel local)."""
    since_str = since.strftime("%Y-%m-%d")
    return (
        f"List every Morning document created on or after {since_str} (use list_invoices "
        f"with from_date={since_str}, paginate/re-query as needed to see all of them). For "
        "each one, call get_invoice_details to get its full fields (including its exact "
        "creation date+time), then call capture_ledger_event with source_type=\"חשבונית\" "
        "populated directly from that document's real fields - accounting_document_display_number "
        "from its user-facing display number (never Morning's internal id), "
        "accounting_document_creation_date as an ISO-8601 date+time built from the exact "
        "date+time get_invoice_details states (e.g. \"נוצר ב: 20/08/2026 18:52\" -> "
        "\"2026-08-20T18:52:00\") - never inferred, never guessed, never left as just a date. "
        "Call capture_ledger_event once per document - do not skip any, do not merge multiple "
        "documents into one call. Do not produce any other reply text - this is not a "
        "conversation, no one will read a text reply."
    )


def _sweep_accounting_documents(global_context: Any, log_prefix: str = "") -> None:
    """Shared worker: derive the poll watermark from LedgerEventManager's
    in-memory accounting-document cache, safety-cap-check the gap (5-day half
    pre-hoc, 100-document half post-hoc - see MAX_CATCHUP_LOOKBACK/
    MAX_CATCHUP_DOCUMENT_COUNT above), then - if within bounds - ask OpenAI
    (with Morning MCP + LEDGER_EVENT_TOOL attached) to list/detail every
    not-yet-known Morning document since that watermark and capture each as
    a LedgerEvent via AIHandler._handle_accounting_reconciliation_capture.
    Shared by both the periodic APScheduler job and
    run_startup_accounting_reconciliation_sweep's boot-time catch-up call.
    See contracts/accounting-reconciliation-service.md for the full
    step-by-step this implements.
    """
    ai_handler = global_context.ai_handler
    ledger_event_manager = ai_handler.ledger_event_manager

    now = now_local()
    since = ledger_event_manager.get_accounting_document_watermark()
    if since is None:
        since = now - FALLBACK_LOOKBACK

    if now - since > MAX_CATCHUP_LOOKBACK:
        logger.error(
            f"{log_prefix}[025] Accounting reconciliation sweep: gap since watermark "
            f"({since.isoformat()}) exceeds {MAX_CATCHUP_LOOKBACK} - skipping this tick "
            "entirely (this is not a backfill mechanism) - needs admin intervention"
        )
        return

    # Synthetic authorized "user" for _build_morning_mcp_tools' RBAC check -
    # there is no real per-turn user_obj for a headless background job.
    synthetic_user = type("SyntheticAdmin", (), {"role": Role.ADMIN})()
    morning_tools = ai_handler._build_morning_mcp_tools(  # pylint: disable=protected-access
        synthetic_user, "accounting-reconciliation-sweep"
    )
    if not morning_tools:
        logger.error(
            f"{log_prefix}[025] Accounting reconciliation sweep: Morning MCP tools "
            "unavailable this tick - skipping, next tick will retry"
        )
        return
    tools = morning_tools + [LEDGER_EVENT_TOOL]

    prompt = _build_reconciliation_prompt(since)

    try:
        response = ai_handler.client.responses.create(
            model=ai_handler.config.ai_model,
            input=[{"role": "user", "content": prompt}],
            tools=tools,
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            f"{log_prefix}[025] Accounting reconciliation sweep failed (OpenAI/MCP call): {e}",
            exc_info=True,
        )
        return

    total = _parse_list_invoices_total(response)
    if total is not None and total > MAX_CATCHUP_DOCUMENT_COUNT:
        logger.error(
            f"{log_prefix}[025] Accounting reconciliation sweep: list_invoices reported "
            f"{total} candidate document(s) (> {MAX_CATCHUP_DOCUMENT_COUNT}) - discarding this "
            "entire turn's captures (this is not a backfill mechanism) - needs admin intervention"
        )
        return

    try:
        event_ids = ai_handler._handle_accounting_reconciliation_capture(response)  # pylint: disable=protected-access
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            f"{log_prefix}[025] Accounting reconciliation sweep failed (persist step): {e}",
            exc_info=True,
        )
        return

    ledger_event_manager.prune_accounting_document_cache()
    logger.info(f"{log_prefix}[025] Accounting reconciliation sweep captured {len(event_ids)} event(s)")


def run_startup_accounting_reconciliation_sweep(global_context: Any) -> None:
    """Runs synchronously on the main thread before the periodic scheduler
    starts - catches anything created in Morning while the process wasn't
    running, mirroring run_startup_reminder_sweep's precedent."""
    logger.info("[025] Running startup accounting reconciliation sweep (catch-up for any missed window)")
    _sweep_accounting_documents(global_context, log_prefix="[STARTUP] ")


def start_accounting_reconciliation_scheduler(
    global_context: Any, update_freq_minutes: int, trigger: Any = None
) -> Optional[BackgroundScheduler]:
    """Creates, starts, and returns the single shared APScheduler instance for
    the accounting document reconciliation sweep - exactly ONE job for the
    whole process. `update_freq_minutes` is config.accounting_ledger_update_freq
    - 0 means the feature is inactive: no job is registered, no scheduler is
    started, and this returns None (caller, denidin.py, must handle that).
    `trigger` is a testability seam only, same convention as
    reminder_delivery_service.py's start_reminder_scheduler - production
    callers must never pass it (leaving it None yields the real wall-clock-
    aligned CronTrigger below)."""
    if update_freq_minutes <= 0:
        logger.info(
            "[025] accounting_ledger_update_freq=0 (or unset) - accounting reconciliation "
            "sweep is inactive, no scheduler started"
        )
        return None

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: _sweep_accounting_documents(global_context),
        trigger=trigger or CronTrigger(minute=f"*/{update_freq_minutes}"),
        id=RECONCILIATION_SWEEP_JOB_ID,
        max_instances=1,  # a slow tick must not overlap the next one
    )
    scheduler.start()
    logger.info(
        f"[025] Accounting reconciliation scheduler started (every {update_freq_minutes} min, "
        "wall-clock-aligned)"
    )
    return scheduler
