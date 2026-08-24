# Integration Contract: `query_ledger_events` Tool Schema

**Feature**: 044-ledger-event-querying · Per METHODOLOGY.md §VII format.

One new local `type: "function"` OpenAI Responses API tool, attached to a turn only when
the resolved role is GODFATHER or ADMIN (FR-004) — same conditional-attachment mechanism
`AIHandler._assemble_tools` already uses for Morning MCP tools and the reminder tools (a
new `LEDGER_QUERY_AUTHORIZED_ROLES` tuple, see `research.md` Decision 9). `strict: True` /
full `required` / `additionalProperties: False`, matching every other local tool in this
file.

---

### `query_ledger_events` (read-only, no approval gate)

```python
QUERY_LEDGER_EVENTS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "query_ledger_events",
    "description": (
        "Search previously captured ledger events (fee agreements AND bank-deposit records) "
        "to answer a question about past agreements, amounts, hours, or payments - without "
        "needing the user to paste the original message again. ONLY call this when the "
        "user's question gives you at least ONE identifying detail to search on (a client/"
        "payer name, a date or date range, an amount or amount range, or specific matter "
        "text) - if the question is too vague to form a real search (e.g. 'what did we "
        "agree on' with nothing else), ASK the user for the missing detail FIRST; never "
        "call this with every filter empty just to see what comes back. "
        "client_name is fuzzy-matched against BOTH client_name and payer_name on file - "
        "typos and partial names are fine, it does not need to be exact. date_from/date_to "
        "and amount_min/amount_max are plain ranges - YOU resolve any fuzziness yourself "
        "before calling (e.g. 'August' -> that month's first/last day; 'around 40,000, "
        "might include VAT' -> widen the amount range yourself, e.g. try 0.8x-1.2x). "
        "free_text is matched (typo-tolerant, NOT meaning-based) against the event's own "
        "description/component/condition text - it will find similar WORDING, not a "
        "differently-phrased description of the same matter. "
        "If client_name matches more than one distinct real client with no single clear "
        "winner, this returns candidates instead of events - relay them to the user and ask "
        "which one they meant. If they confirm more than one (or 'both'/'all'), call this "
        "again ONCE PER confirmed exact name and combine the results yourself. An empty "
        "result means no matching record was found - say so plainly, never fabricate an "
        "answer. For a question needing arithmetic (a sum, a balance owed, a total across "
        "clients/periods), use the returned events' own clean numeric fields yourself - this "
        "tool never computes totals for you. "
        "YOU MAY CALL THIS TOOL MULTIPLE TIMES IN THE SAME TURN - this is how to answer a "
        "request spanning more than one name, date range, or other criterion at once (e.g. "
        "'what was agreed with client A or client B', 'hours in August or September') - call "
        "once per distinct name/range/criterion and combine all the results yourself when "
        "you reply. This tool is read-only, so calling it several times is always safe. "
        "If a single call's matches are very numerous, don't just dump every event verbatim - "
        "use your own judgment about summarizing or asking the user to narrow further, the "
        "same way you would for any other long answer."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "client_name": {
                "type": ["string", "null"],
                "description": "Fuzzy-matched against stored client_name/payer_name - typos and partial names are fine.",
            },
            "date_from": {
                "type": ["string", "null"],
                "description": "ISO-8601 YYYY-MM-DD, inclusive lower bound. Matches if EITHER the event's own date or its transaction date falls in range - resolve relative/approximate phrases yourself first.",
            },
            "date_to": {
                "type": ["string", "null"],
                "description": "ISO-8601 YYYY-MM-DD, inclusive upper bound. Same matching as date_from.",
            },
            "amount_min": {
                "type": ["number", "null"],
                "description": "Inclusive lower bound on the event's amount. Widen this yourself if VAT ambiguity is plausible.",
            },
            "amount_max": {
                "type": ["number", "null"],
                "description": "Inclusive upper bound on the event's amount. Same reasoning as amount_min.",
            },
            "source_type": {
                "type": ["string", "null"],
                "description": "Exact category match against the event's own source_type - הסכם for fee-agreement events, בנק for bank-deposit events, חשבונית for accounting documents pulled from Morning, or any other value that may exist. NOT a fixed list - the ledger can grow new source types over time; pass whatever value the user's own question implies. Leave null to search across every type (needed for e.g. an owed-balance question spanning agreement + payments).",
            },
            "event_subtype": {
                "type": ["string", "null"],
                "description": "Exact category match against the event's own event_subtype. Almost never worth setting - leave null unless the user specifically distinguishes subtypes. NOT a fixed list, same reasoning as source_type.",
            },
            "free_text": {
                "type": ["string", "null"],
                "description": "Typo-tolerant (NOT meaning-based) match against the event's own free-text fields (description, component_label, trigger_condition, and any accounting-document text fields like document number/status/payment method).",
            },
        },
        "required": [
            "client_name", "date_from", "date_to", "amount_min", "amount_max",
            "source_type", "event_subtype", "free_text",
        ],
        "additionalProperties": False,
    },
}
```

**`AIHandler` MUST**: dispatch this immediately on a matching `function_call` (never gated by
`PendingLocalToolApproval`, since this is read-only). See `data-model.md` for the exact
filter-matching rules and the four possible `function_call_output` shapes (resolved matches /
ambiguous candidates / vague-query-guard error / individual-call parse failure).

**`AIHandler` MUST (multi-call dispatch — research.md Decision 10, data-model.md "Multi-call
dispatch")**: use `extract_all_function_calls` (NOT `extract_function_call`/
`extract_function_call_id` — those only return the first match, the pattern `list_reminders`
uses since it can only sensibly appear once per turn). A single turn may legitimately contain
several `query_ledger_events` calls; execute each independently, and report every one of them
back in ONE follow-up `responses.create` call as a list of `function_call_output` items (one
per `call_id`) — mirrors `_call_openai_ledger_followup_api`'s existing multi-item batching
exactly. This is the deliberate OPPOSITE of `capture_ledger_event`'s bugfix-018 rule (which
rejects the entire turn if it sees more than one call) — that rule exists because
`capture_ledger_event` WRITES data and an uncontrolled multi-call burst risked corrupting the
ledger with duplicates; `query_ledger_events` writes nothing, so multiple calls per turn are
always safe and are how "client A or B" / multi-range requests get answered (see
`research.md` Decision 10 for the full reasoning and the "candidates → user says both/all"
flow this same mechanism resolves).

**`AIHandler` MUST (per-call failure isolation)**: if one call's `arguments` fail to parse
(truncated mid-generation), only that call's own `function_call_output` gets the error shape
(data-model.md shape D) — every other well-formed call from the same turn still executes and
returns its own real result. Never reject the whole turn the way `capture_ledger_event` does
— there is no cross-call risk here to guard against.

**`AIHandler` MUST (vague-query guard, code-side backstop — research.md Decision 6)**: if
every one of the eight arguments the model actually supplied is `null`, do NOT execute a
whole-ledger scan — return the `{"error": "no_search_criteria", ...}` shape instead (see
`data-model.md` shape C), so the model's next turn asks the user rather than silently
answering from (or dumping) the entire ledger.

**`AIHandler` MUST (entity-ambiguity detection)**: when `client_name` is non-null, group the
index's distinct `client_name`/`payer_name` string values that fuzzy-match ≥
`_NAME_MATCH_THRESHOLD`; if 2+ distinct strings qualify, return shape B (candidates) instead
of executing the rest of the filter — never silently pick the top-scoring one.

**Key departures from every other tool in this file**:
- Unlike `capture_ledger_event`/reminder tools, this one **mutates nothing** — no
  `PendingApprovalManager`/`PendingLocalToolApproval` involvement at all, ever.
- Unlike the Morning MCP tools, this is a **local** function tool — no remote server, no
  ngrok tunnel, no bearer auth; the whole implementation lives in `apps/denidin-app`.
- Result multiplicity (many matching events) is normal and expected — see `research.md`
  Decision 4 for why this is explicitly NOT the same thing as the candidate-list ambiguity
  shape above.
