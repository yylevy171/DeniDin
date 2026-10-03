"""
Accounting document reconciliation service (Feature 025).

The single shared background mechanism that polls Morning for documents
created directly there (with no matching DeniDin conversation) and captures
them as LedgerEvents (source_type="חשבונית") - structurally mirrors
services/reminder_delivery_service.py's shape (Feature 054): one shared
worker function, called both periodically (APScheduler BackgroundScheduler +
IntervalTrigger - NOT CronTrigger, unlike reminder_delivery_service.py; see
start_accounting_reconciliation_scheduler's own docstring for why) and once
at startup for catch-up. See
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
import json
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional

# apscheduler ships no type stubs - hence the import-untyped ignore on its imports.
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from src.core.ai_manager import MORNING_READ_MCP_TOOLS, MORNING_WRITE_MCP_TOOLS
from src.managers.ledger_event_recognizer import LEDGER_EVENT_TOOL
from src.utils.function_calls import extract_all_function_calls
from src.utils.wire_log import audit_wire, debug_wire
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
# Widened 1->2 days (2026-08-22, explicit user decision, live dev testing):
# a 1-day window genuinely missed real sandbox documents once real wall-clock
# time passed between test runs on different days.
FALLBACK_LOOKBACK = timedelta(days=2)

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

# bugfix-047: the reconciliation sweep's OpenAI+MCP call is far heavier than a
# conversational turn - in a single turn OpenAI fetches the Morning MCP tool
# list over the tunnel, runs list_invoices(include_full_details=true) (a
# server-side per-document detail fan-out), then has a reasoning model emit one
# verbose capture_ledger_event call per document. That legitimately takes
# 30-60s+ and grows with document volume. The shared OpenAI client is built
# with timeout=30.0 (denidin.py) for conversational turns; inheriting it here
# made ~every dev sweep fail with APITimeoutError (2x30s with the client's
# max_retries=1) once the sandbox held ~13+ in-window documents. This call
# gets its own generous ceiling instead, applied via .with_options() at the
# call site (same mechanism _call_openai_approval_api already uses for its own
# max_retries override). max_retries=0 too: a retry re-runs the entire sweep
# from scratch (list_invoices included) and the hourly scheduler tick is
# already the real retry. The scheduler runs at most one sweep at a time
# (max_instances=1), so a long-running call is harmless.
RECONCILIATION_CALL_TIMEOUT_SECONDS = 300.0

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

        # Phase 9: the sweep asks for output_format="json", whose payload
        # states total_matched explicitly - far more reliable than the prose
        # phrase-matching below, which is retained only as a fallback for a
        # tool that answered in text anyway.
        try:
            payload = json.loads(output_text)
            if isinstance(payload, dict) and "total_matched" in payload:
                totals.append(int(payload["total_matched"]))
                continue
        except (ValueError, TypeError):
            pass

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
        "Automated accounting reconciliation task. Make tool calls only - never write a "
        "text reply, no human will read one.\n\n"
        f"STEP 1: Call list_invoices with from_date={since_str}, output_format=\"json\" "
        "and include_full_details=true. "
        "It returns {\"total_matched\": N, \"documents\": [ ... ]} - every document, "
        "already complete. You do NOT need get_invoice_details: each entry already "
        "includes its payment and linked-document details.\n\n"
        "STEP 2: For EVERY object in that \"documents\" array, call capture_ledger_event "
        "exactly once - one call per document, never merged, never skipped - with:\n"
        "- source_type: \"חשבונית\"\n"
        "- event_subtype: \"הפקה\" (a placeholder - code overwrites it with the "
        "document's real Morning type)\n"
        "- accounting_document_json: that document's ENTIRE JSON object, copied verbatim "
        "as a single string, exactly as it appeared. Do not summarise it, reorder it, "
        "translate it, drop fields, or fill anything in yourself - every value is read "
        "out of it by code.\n"
        "- every other argument: null.\n\n"
        "If \"documents\" is empty, make no capture_ledger_event calls at all and stop."
    )


class AccountingReconciler:
    """The accounting-document reconciliation sweep (Feature 025), its own class
    (REQ-063-08). Uses DeniDin's ledger and, from the AI implementation in use, only
    the OpenAI client and the Morning MCP connection - so it runs the same whichever
    implementation the backbone flag selects."""

    def __init__(self, ai_manager: Any, ledger_event_manager: Any):
        self.ai_manager = ai_manager
        self.ledger_event_manager = ledger_event_manager

    def _morning_tools(self) -> List[Dict[str, Any]]:
        """The Morning MCP tools entry for the sweep - a headless background job with no
        real user, so it runs as an admin. Reads are never gated; writes would need
        approval (the sweep only ever reads)."""
        connection = self.ai_manager.morning_mcp_connection("accounting-reconciliation-sweep", Role.ADMIN)
        if connection is None:
            return []
        return [self.ai_manager.morning_mcp_entry(
            connection,
            server_label=connection[2].get('morning_server_label', 'morning-invoices'),
            require_approval={
                "always": {"tool_names": list(MORNING_WRITE_MCP_TOOLS)},
                "never": {"tool_names": list(MORNING_READ_MCP_TOOLS)},
            },
        )]

    def sweep(self, log_prefix: str = "") -> None:
        """Shared worker: derive the poll watermark from LedgerEventManager's
        in-memory accounting-document cache, safety-cap-check the gap (5-day half
        pre-hoc, 100-document half post-hoc - see MAX_CATCHUP_LOOKBACK/
        MAX_CATCHUP_DOCUMENT_COUNT above), then - if within bounds - ask OpenAI
        (with Morning MCP + LEDGER_EVENT_TOOL attached) to list/detail every
        not-yet-known Morning document since that watermark and capture each as
        a LedgerEvent via capture().
        Shared by both the periodic APScheduler job and
        run_startup_accounting_reconciliation_sweep's boot-time catch-up call.
        See contracts/accounting-reconciliation-service.md for the full
        step-by-step this implements.
        """
        ai_manager = self.ai_manager
        ledger_event_manager = self.ledger_event_manager

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

        morning_tools = self._morning_tools()
        if not morning_tools:
            logger.error(
                f"{log_prefix}[025] Accounting reconciliation sweep: Morning MCP tools "
                "unavailable this tick - skipping, next tick will retry"
            )
            return
        tools = morning_tools + [LEDGER_EVENT_TOOL]

        prompt = _build_reconciliation_prompt(since)

        reconciliation_kwargs = {
            "model": ai_manager.config.ai_model,
            "input": [{"role": "user", "content": prompt}],
            "tools": tools,
            # Real bug (2026-08-22): this call originally set no output cap at
            # all - the only OpenAI call in this app that didn't - leaving it
            # on whatever the API's own default is. A full sweep legitimately
            # emits one capture_ledger_event call per document (~185 output
            # tokens each; ~3.3k for 18 documents, and this feature's own
            # safety cap allows up to 100), so an unstated default is a real
            # truncation risk. Uses the same config value every conversational
            # call already uses.
            "max_output_tokens": ai_manager.config.ai_reply_max_tokens,
        }
        try:
            audit_wire("openai", "out", f"{log_prefix}accounting_reconciliation_sweep", reconciliation_kwargs)
            debug_wire("openai", "out", f"{log_prefix}accounting_reconciliation_sweep", reconciliation_kwargs)
            # bugfix-047: override the shared client's conversational-turn timeout
            # (30s) and retry (1) - see RECONCILIATION_CALL_TIMEOUT_SECONDS above.
            response = ai_manager.client.with_options(
                timeout=RECONCILIATION_CALL_TIMEOUT_SECONDS, max_retries=0
            ).responses.create(**reconciliation_kwargs)
            audit_wire("openai", "in", f"{log_prefix}accounting_reconciliation_sweep", response)
            debug_wire("openai", "in", f"{log_prefix}accounting_reconciliation_sweep", response)
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
            event_ids = self.capture(response)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                f"{log_prefix}[025] Accounting reconciliation sweep failed (persist step): {e}",
                exc_info=True,
            )
            return

        ledger_event_manager.prune_accounting_document_cache()
        logger.info(f"{log_prefix}[025] Accounting reconciliation sweep captured {len(event_ids)} event(s)")

    def capture(self, response) -> List[str]:
        """Feature 025 (Morning-Sourced Ledger Events): thin adapter for the
        accounting-document reconciliation sweep's headless OpenAI+MCP call
        (services/accounting_reconciliation_service.py) - parses every
        capture_ledger_event call in `response` and passes each straight
        through to LedgerEventManager.add_ledger_events_from_call,
        unconditionally.

        Structurally separate from the conversational post-turn recognition
        call (`recognize_ledger_event`, Feature 069):
        - NO same-turn-mcp_call suppression - list_invoices/
          get_invoice_details mcp_calls co-occurring with capture_ledger_event
          in the same turn is the normal, expected shape here.
        - NO one-call-per-turn limit - calling once per new document, several
          times in the same sweep tick, is the normal case.
        - NO dedup/anomaly decision of its own (round 3 of spec.md's
          Clarifications: "it's clearly a ledger requirement regardless of
          ai") - LedgerEventManager.add_ledger_event owns that entirely via
          its own in-memory cache; this handler trusts it completely, same
          as every other capture path.
        - NO follow-up OpenAI round-trip, no confirmation reply - this is not
          a conversational turn, nothing user-facing is ever produced here.

        Returns the list of newly-persisted event_ids (empty if nothing was
        captured, or everything was a true duplicate/malformed).
        """
        calls = extract_all_function_calls(response, LEDGER_EVENT_TOOL["name"])
        event_ids: List[str] = []
        for call in calls:
            if call["arguments"] is None:
                logger.error(
                    "[025] Reconciliation sweep: capture_ledger_event call had "
                    f"unparseable arguments (call_id={call['call_id']!r}) - rejected, "
                    "not silently dropped"
                )
                continue
            # message_timestamp=None: this sweep has no real source message, and
            # LedgerEventManager.add_ledger_event already derives the correct
            # event_datetime itself for source_type=חשבונית directly from the
            # Morning document's own creation timestamp (carried inside
            # accounting_document_json, expanded internally) - it only falls
            # back to message_timestamp/now_local() when that's unavailable.
            # A prior separate ai_handler-side timestamp derivation here
            # (removed 2026-08-25) was redundant with that and, since it read
            # the raw un-expanded call arguments, never actually fired.
            try:
                new_event_ids = self.ledger_event_manager.add_ledger_events_from_call(
                    session_id="accounting-reconciliation",
                    call_arguments=call["arguments"],
                    message_id=None,
                    message_timestamp=None,
                )
                event_ids.extend(new_event_ids)
            except Exception as e:  # pylint: disable=broad-except
                logger.error(
                    f"[025] Failed to persist accounting-document ledger event(s): {e}",
                    exc_info=True
                )
        return event_ids


def _sweep_accounting_documents(global_context: Any, log_prefix: str = "") -> None:
    """One sweep, for the scheduler and the startup catch-up: DeniDin's ledger, the AI
    implementation in use."""
    AccountingReconciler(global_context.ai_manager, global_context.ledger_event_manager).sweep(log_prefix)


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
    callers must never pass it (leaving it None yields the real
    IntervalTrigger below).

    Uses IntervalTrigger, NOT reminder_delivery_service.py's
    CronTrigger(minute=f"*/{n}") pattern (real bug, found live in dev
    2026-08-21): a cron minute field only accepts steps within 0-59 -
    CronTrigger(minute="*/60") raises ValueError at scheduler-start time
    ("the step value (60) is higher than the total range of the
    expression"), which crashed the real running app (an unhandled exception
    at module scope in denidin.py's __main__, with no auto-restart, per
    watchdog.py's own by-design no-retry behavior). reminder_delivery_service.py's
    own CronTrigger use is safe only because it's always configured with a
    small value (5 minutes) - this field is user-configurable to any
    positive integer, so it needs a trigger that's valid for any of them.
    IntervalTrigger trades away wall-clock alignment (which correctness here
    never depended on, unlike the reminder sweep) for correctness at every
    valid input."""
    if update_freq_minutes <= 0:
        logger.info(
            "[025] accounting_ledger_update_freq=0 (or unset) - accounting reconciliation "
            "sweep is inactive, no scheduler started"
        )
        return None

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: _sweep_accounting_documents(global_context),
        trigger=trigger or IntervalTrigger(minutes=update_freq_minutes),
        id=RECONCILIATION_SWEEP_JOB_ID,
        max_instances=1,  # a slow tick must not overlap the next one
    )
    scheduler.start()
    logger.info(f"[025] Accounting reconciliation scheduler started (every {update_freq_minutes} min)")
    return scheduler
