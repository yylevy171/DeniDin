# Integration Contract: `query_ledger_events` Tool Schema

**Feature**: 044-ledger-event-querying · Per METHODOLOGY.md §VII format.

One new local `type: "function"` OpenAI Responses API tool, attached to a turn only when
the resolved role is GODFATHER or ADMIN (FR-004) — same conditional-attachment mechanism
`AIHandler._assemble_tools` already uses for Morning MCP tools and the reminder tools (a
new `LEDGER_QUERY_AUTHORIZED_ROLES` tuple, see `research.md` Decision 9). `strict: True` /
full `required` / `additionalProperties: False`, matching every other local tool in this
file.

> **2026-08-24 redesign**: the original schema below (8 separate structured filter
> parameters: `client_name`, `date_from`/`date_to`, `amount_min`/`amount_max`,
> `source_type`, `event_subtype`, `free_text`) was replaced wholesale after a real billed
> test (`test_payer_name_search`) showed the AND-combined structured filters let the model
> accidentally exclude a genuine match by over-constraining one call, and the design had no
> way to express OR/NOT/threshold reasoning at all. Replaced with a single `criteria` list
> of `{text, hint}` pairs and a "retrieve broadly, then score" engine — see `research.md`'s
> "2026-08-24 Redesign" section and `tasks.md`'s "Addendum, 2026-08-24" for the full
> decision trail. The schema below reflects the CURRENT (post-redesign) contract.

> **2026-08-25 hint-group review**: the `category` group conflated three unrelated axes
> (event classification, VAT treatment, document lifecycle status) under one misleading
> name; `due_date` was a dead, always-null reserved field with no populating code path;
> `component_label` was a non-searchable capture-time-only field wrongly included. Redesigned
> to 9 groups: `identity` (now also includes `split_partner`), `date` (now `event_datetime`/
> `txn_date` only - `due_date` and the removed `accounting_document_creation_date` dropped),
> `event_type` (`source_type`/`event_subtype` only), `vat` (new, `vat_status`), `amount`,
> `percentage`, `free_text` (renamed from `description`, `component_label` dropped),
> `document` (now also includes `accounting_document_status`/`accounting_document_status_label`),
> `banking`. The `split` group is gone (its one field, `split_partner`, moved into `identity`).
> The `accounting_document_creation_date` field itself was removed from the persisted schema
> entirely (2026-08-25, user directive) - it was a byte-for-byte duplicate of `event_datetime`
> for every record it ever appeared on; `event_datetime` is now the only creation-date field,
> for every source_type alike. See `data-model.md`'s field table and `research.md` for the
> full rationale. The schema below reflects the CURRENT (post-25-08-25-review) contract.

---

### `query_ledger_events` (read-only, no approval gate)

```python
QUERY_LEDGER_EVENTS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "query_ledger_events",
    "description": (
        "Search previously captured ledger events (fee agreements, bank-deposit records, "
        "and accounting documents pulled from Morning) to answer a question about past "
        "agreements, amounts, hours, percentages, or payments - without needing the user "
        "to paste the original message again. ONLY call this when the user's question gives "
        "you at least ONE identifying detail to search on - if the question is too vague to "
        "form a real search (e.g. 'what did we agree on' with nothing else), ASK the user "
        "for the missing detail FIRST; never call this with an empty criteria list just to "
        "see what comes back. "
        "criteria is a list of {text, hint} pairs, one per distinct fact you're searching "
        "for. EVERY criterion searches EVERY field on every event (name, date, amount, "
        "percent, description, document number, bank details, everything) - there is no "
        "way to restrict a criterion to only one field. A NUMBER given as text (e.g. "
        "'100', '40000') is compared numerically against the event's numeric fields only "
        "(amount, hourly_rate, percent, percent_base, split_percent, bank_number, "
        "bank_branch, bank_account, accounting_document_display_number) - exact value, not "
        "fuzzy string similarity, so pass the literal number, not a description of it. Any "
        "other text is fuzzy/typo-tolerant matched (NOT meaning-based - it finds similar "
        "WORDING, not a differently-phrased version of the same idea) against every text "
        "field. Resolve relative/approximate phrasing yourself before calling (e.g. "
        "'August' -> pass a date like '2026-08', 'around 40,000, might include VAT' -> "
        "consider searching both the round number and a VAT-adjusted figure as separate "
        "criteria if genuinely ambiguous). "
        "hint is optional and is a SOFT signal only, never a hard filter - see the hint "
        "parameter's own description below for the full list of groups and what each means. "
        "If the question is scoped to a time period (this month, this week, since Monday, "
        "etc.) always add a separate criterion with hint='date' carrying that period - this "
        "tool applies no date filtering on its own, so without a date-hinted criterion a "
        "time-scoped question can match events from ANY month, not just the intended one. "
        "Multiple criteria in ONE call are ANDed - only events matching ALL of them "
        "(individually, above a real-match confidence floor) come back. Each returned event "
        "also carries a 'confidence' score - higher means a stronger match across the given "
        "criteria; use your judgment about how much confidence to trust for borderline "
        "matches. "
        "If an 'identity'-hinted criterion matches more than one distinct real client/payer "
        "with no single clear winner, this returns candidates instead of events - relay them "
        "to the user and ask which one they meant. If they confirm more than one (or 'both'/"
        "'all'), call this again ONCE PER confirmed exact name and combine the results "
        "yourself. An empty result means no matching record was found - say so plainly, "
        "never fabricate an answer. "
        "For OR-type questions (spanning more than one name, date range, or other criterion "
        "where ANY may match - e.g. 'client A or client B', 'hours in August or September'), "
        "issue ONE SEPARATE CALL PER alternative and combine all the results yourself when "
        "you reply - this tool is read-only, so calling it several times in the same turn is "
        "always safe. For NOT/exclusion or numeric-threshold questions (e.g. 'everyone except "
        "X', 'who owes more than 100'), call this with a broad criteria set that retrieves "
        "every plausibly-relevant event (do NOT try to encode the exclusion/threshold into "
        "criteria - there is no such filter), then apply the exclusion or threshold yourself "
        "by reasoning over the returned events' own fields before replying. For a question "
        "needing arithmetic (a sum, a balance owed, a total across clients/periods), use the "
        "returned events' own clean numeric fields yourself - this tool never computes totals "
        "for you. If a single call's matches are very numerous, don't just dump every event "
        "verbatim - use your own judgment about summarizing or asking the user to narrow "
        "further, the same way you would for any other long answer."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "criteria": {
                "type": "array",
                "description": (
                    "One entry per distinct fact being searched for within this call "
                    "(ANDed together). Use multiple calls, not multiple array entries, for "
                    "OR-type questions - see the tool description."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": (
                                "The literal value to search for - a name, a date, a plain "
                                "number, or free text. Searched against every field on every "
                                "event; see the tool description for how numbers vs. text are "
                                "compared."
                            ),
                        },
                        "hint": {
                            "type": ["string", "null"],
                            "enum": [
                                "identity", "date", "event_type", "vat", "amount",
                                "percentage", "free_text", "document", "banking", None,
                            ],
                            "description": (
                                "Optional soft weighting signal - which closed field group "
                                "this text is most likely describing. Never a hard filter: "
                                "every field is always checked regardless, this only nudges "
                                "scoring if the text's best match lands in the hinted group. "
                                "Leave null if unsure. Groups: "
                                "'identity' = client name, payer name, or split-partner name. "
                                "'date' = the event's own date/time or a transaction date - "
                                "use this whenever the question is scoped to a period (this "
                                "month, this week, since Monday, etc.); pass the "
                                "period/date as the criterion's text. "
                                "'event_type' = source type (הסכם/בנק/חשבונית) or event "
                                "subtype (e.g. חשבונית מס, קבלה). "
                                "'vat' = VAT status/treatment. "
                                "'amount' = amount or hourly rate. "
                                "'percentage' = percent, percent base, or split percent. "
                                "'free_text' = the free-text description, a trigger "
                                "condition, or a reference hint - prose, not a specific field. "
                                "'document' = the accounting document's display number, "
                                "payment method, or its status/status label (open/paid/"
                                "cancelled etc. - a document lifecycle fact, not the event's "
                                "own date). "
                                "'banking' = bank number, branch, or account."
                            ),
                        },
                    },
                    "required": ["text", "hint"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["criteria"],
        "additionalProperties": False,
    },
}
```

**`AIHandler` MUST**: dispatch this immediately on a matching `function_call` (never gated by
`PendingLocalToolApproval`, since this is read-only). See `data-model.md` for the exact
scoring rules and the three possible `function_call_output` shapes (scored matches /
ambiguous candidates / vague-query-guard error), plus the isolated per-call parse-failure
shape below.

**`AIHandler` MUST (multi-call dispatch — research.md Decision 10, data-model.md "Multi-call
dispatch")**: use `extract_all_function_calls` (NOT `extract_function_call`/
`extract_function_call_id` — those only return the first match, the pattern `list_reminders`
uses since it can only sensibly appear once per turn). A single turn may legitimately contain
several `query_ledger_events` calls (this is now how OR-type questions are answered — see the
tool description); execute each independently, and report every one of them back in ONE
follow-up `responses.create` call as a list of `function_call_output` items (one per
`call_id`) — mirrors `_call_openai_ledger_followup_api`'s existing multi-item batching
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
`criteria` is empty or `null` (or every entry's `text` is empty), do NOT execute a
whole-ledger scan — return the `{"error": "no_search_criteria", ...}` shape instead (see
`data-model.md` shape C), so the model's next turn asks the user rather than silently
answering from (or dumping) the entire ledger.

**`AIHandler` MUST (entity-ambiguity detection)**: for any criterion whose `hint` is
`"identity"`, group the index's distinct `client_name`/`payer_name` string values that
fuzzy-match the criterion's `text` ≥ `_NAME_MATCH_THRESHOLD`; if 2+ distinct strings qualify,
return shape B (candidates) instead of executing the rest of the search — never silently pick
the top-scoring one.

**`LedgerEventManager` MUST (per-criterion scoring, `_score_criterion` — 2026-08-24
redesign)**: score every event against every criterion across ALL `_SEARCHABLE_FIELDS`
(never restricted to the hinted group), then add a bonus if the winning field belongs to the
stated hint's group. An event only counts as a match if EVERY criterion individually clears
`_CRITERION_MATCH_FLOOR` — not just the average across criteria (confirmed necessary
empirically: a mean-of-scores gate lets one perfect match on one criterion "carry" a
near-irrelevant score on another past the floor). A criterion whose `text` parses as a clean
number is compared ONLY against `_NUMERIC_FIELDS`, via real numeric equality — never fuzzy
string matching (confirmed empirically that fuzzy string matching between a number and a
digit-heavy non-numeric field, e.g. a date, spuriously scores high). A field whose own
STORED VALUE is short (< `_SHORT_VALUE_LENGTH_THRESHOLD`, 8 chars) can only win a criterion
if its score clears the near-exact `_SHORT_VALUE_MATCH_THRESHOLD` (85) — confirmed
empirically that short, near-universal filler/categorical values (`event_subtype="יצירה"`,
`component_label="בסיס"`) can spuriously score well above the general floor against a
completely unrelated, longer query, under either scorer. An identity field
(`client_name`/`payer_name`) can additionally only ever become a criterion's winning field
if its raw (pre-bonus) score clears the separately-proven `_NAME_MATCH_THRESHOLD` (70) —
never just the general floor plus the hint bonus (confirmed empirically: two genuinely
unrelated real Hebrew names can score ~40 raw, which clears the general floor once the
identity hint bonus is added, without this extra gate).

**Key departures from every other tool in this file**:
- Unlike `capture_ledger_event`/reminder tools, this one **mutates nothing** — no
  `PendingApprovalManager`/`PendingLocalToolApproval` involvement at all, ever.
- Unlike the Morning MCP tools, this is a **local** function tool — no remote server, no
  ngrok tunnel, no bearer auth; the whole implementation lives in `apps/denidin-app`.
- Result multiplicity (many matching events) is normal and expected — see `research.md`
  Decision 4 for why this is explicitly NOT the same thing as the candidate-list ambiguity
  shape above.
