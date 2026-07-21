# Bugfix Spec: "All invoices from a customer" only returns one

## Bug ID
bugfix-014-list-invoices-only-returns-one-of-many

## Title
Asking for all invoices/payments from a named customer returns only a single result, even when more exist

## Status
Open — root cause investigated (read-only, 2026-07-21: code/config/docs review only, no code changed, nothing deployed, no tests run). Strong root-cause candidate found and confirmed at the documentation level for the `status="paid"` filter; pagination gap independently confirmed to exist in the code (real, but not confirmed as the cause of this specific report); `clientName` matching semantics still unconfirmed (would need a live API check, out of scope this pass). See "Investigation Findings" below.

## Date Opened
2026-07-20

## Reported By
yylevy171 (found via manual prod-environment testing, same live session as bugfix-012/013)

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` — `list_invoices()`
- The AI's tool-call argument construction (`AIHandler`/`runtime_constitution.md`'s invoice-management guidance) — the actual arguments passed into the tool are as much a suspect here as the tool's own filtering logic

## Description
User asked (real WhatsApp, prod, real Morning production account): "תבדוק כל התשלומים מלקוח בשם אריאן רגב" (check all payments from client Arian Regev), and again, more explicitly: "ביקשתי את *כל* התשלומים" (I asked for *all* the payments). Both times, `list_invoices` returned exactly one invoice (#112271, ₪7,213, paid 19/07/2026) — with no indication (`has_more`) that anything was omitted, and no way for the user to know whether that's genuinely the client's only invoice or whether the search under-matched.

## Evidence (from this session's real logs)

```
20:15:11 - MCP calls: [{'name': 'list_invoices', 'arguments':
  '{"status":"paid","from_date":"2026-01-01","to_date":"2026-07-20","client_name":"אריאן רגב"}',
  'output': 'חשבונית #112271 ...'}]

20:16:12 - MCP calls: [{'name': 'list_invoices', 'arguments':
  '{"status":"paid","from_date":"2026-01-01","to_date":"2026-07-20","client_name":"אריאן רגב"}',
  'output': 'חשבונית #112271 ...'}]  (identical call/result, after user explicitly said "ALL")
```

## Suspected Root Cause (unconfirmed — needs investigation before a fix is proposed)

The strongest lead from the evidence above: **the tool call includes `status="paid"` in both attempts, even after the user explicitly said "all payments."** `list_invoices()` (`tools.py:201`) applies this as a hard client-side filter (`_matches_status`, `tools.py:174`) — any invoice for this same client that is unpaid, overdue, or cancelled would be silently excluded from the result, with no signal to the user that filtering happened. This is the same *shape* of issue as bugfix-013 (unrequested/undisclosed narrowing of a search when the user asked for something broader) — here specifically a `status` filter instead of a date filter.

Other candidates that have NOT been ruled out and would need real testing to confirm/exclude:
- **Pagination**: `_extract_items()` (`tools.py:165`) takes only `response.get("items")`/`.get("data")` from a single API response with no loop over further pages. If Morning's `/documents/search` paginates and this client's invoices span more than one page, only the first page's items would ever reach the client-side filters — silently dropping the rest with no `has_more` signal (unlike the deliberate 10-item display cap in `list_invoices`, which IS tracked via `has_more`).
- **`clientName` server-side matching semantics**: `_map_list_invoices_filters()` sends `clientName` directly to Morning's search endpoint (`tools.py:144`) — if Morning does an exact/strict match rather than a fuzzy/contains match, invoices under a slightly different real client-name variant (e.g. a company suffix, alternate spelling) would never be returned at all, independent of the status/pagination issues above.
- **Whether the customer genuinely only has one invoice** has not been independently verified against the Morning dashboard the way bugfix-012's underlying data was (user manually confirmed that one). This should be checked first, the same way, before assuming the tool is wrong.

## Steps to Reproduce
1. As a confirmed GODFATHER/ADMIN, ask for "all invoices" or "all payments" from a real named client known (via the Morning dashboard) to have more than one invoice, at least one of which is not `status=paid`.
2. Observe whether `list_invoices` returns all of them, or only a subset — and whether `status="paid"` (or any other unrequested filter) appears in the tool call's arguments.

## Investigation Findings (read-only, 2026-07-21)

**Scope of this pass**: code/config/log/documentation review only. No code was changed, no tests were run, no deployment was touched, per explicit instruction. Findings below are root-cause analysis for approval, not fixes.

### Root cause found for the `status="paid"` filter: an existing constitution rule over-generalizes from a payment-related word to a hard status filter

`apps/denidin-app/data/constitution/runtime_constitution.md` (line 200):

> "Status/action words: 'שילם' / 'לשלם' / 'שולם' → `status="paid"`; ..."

The user's request was "תבדוק כל **התשלומים** מלקוח בשם אריאן רגב" ("check all the **payments** from client Arian Regev"). "תשלומים" (payments, plural noun) shares the same ש-ל-ם root as the literal trigger words the rule lists ("שילם"=paid, "לשלם"=to pay, "שולם"=was paid), but is a different part of speech with a different, broader meaning: "give me the payment/transaction history" (a request for scope) rather than "show me only the ones marked as paid" (a request for a status filter). The rule as written doesn't clearly distinguish these, and the model's tool call (`status="paid"` in both attempts, including after the user said "ALL" explicitly) is consistent with it having over-generalized the rule to the noun form.

This is corroborated by `bugfix-013`'s own logs from the same session: the Zehavit message ("כמה **שילמה** ומתי" — "how much did she **pay** and when") also triggered `status="paid"`, and there the trigger word is even more literally "שילמה" (paid, verb form) — yet the user was clearly asking for full payment *history* ("תן לי הכל" / "give me everything" in the very same sentence), not a paid-only filter. Both incidents fit the same pattern: any mention of paying/payment vocabulary is being read as an explicit request to filter to `status="paid"`, even when the surrounding sentence asks for a broader view.

This also violates the constitution's own transparency rule (lines 202-207: "Be transparent about anything you filled in yourself... If your confidence in a filled-in value is low... ask instead of guessing silently") — neither reply disclosed that a status filter had been applied, so the user had no way to know their "all payments" request had been silently narrowed.

**Recommended fix direction** (not yet approved): narrow the constitution's rule so it only triggers `status="paid"`/`status="unpaid"`/`status="cancelled"` when the word is used to qualify a specific status *of* an invoice/action (e.g. "mark it paid", "the invoice she paid", "cancel it") — not when the user is asking broadly for "all payments"/"payment history" as a scope of what to retrieve. Also worth adding an explicit example contrasting the two ("תשלומים" as scope vs. "ששולם"/"שילמה" as a status qualifier) since the literal-word-matching approach is exactly what over-generalized here.

### Pagination gap: confirmed present in code, not confirmed as this report's cause

`MorningClient.list_invoices` (`morning_client.py:63-69`) sends whatever `params` dict it's given straight to `POST /documents/search` with **no `page`/`pageSize` keys ever added**, and does **not loop over subsequent pages**. The cached Green Invoice Postman collection (`specs/in-definition/005-mcp-morning-green-receipt/Green Invoice Public API.postman_collection.json`) confirms `/documents/search` is genuinely paginated — its own example request sets `"page": 1, "pageSize": 20`, and its example response has the shape `{"pageSize":20,"page":1,"total":0,"from":1,"to":0,"pages":0,"items":[],"aggregations":{...}}`. `_extract_items()` (`tools.py:170-176`) only ever reads `response.get("items")` from whatever single response comes back — if `page`/`pageSize` are omitted, Morning's own defaults apply (not documented in the cached collection; unconfirmed what they are), and if a client has more documents than fit on the first page, everything past page 1 is silently invisible to this tool, with no `has_more`-style signal for this specific failure mode (`list_invoices`'s own `has_more` flag only reflects its own 10-item display cap over whatever page 1 already returned — it can't detect truncation Morning itself performed upstream).

This is a real, confirmed gap independent of the `status` filter issue above — but it is **not confirmed to be what caused the Arian Regev report specifically** (that would require knowing Arian Regev's actual total document count and Morning's actual default page size/count, neither of which is available from static review). It's flagged here as a separate, real latent risk worth its own fix regardless of what caused this particular incident.

### `clientName` matching semantics: still unconfirmed, needs a live check

`_map_list_invoices_filters()` (`tools.py:149-167`) sends `clientName` directly to Morning's search endpoint. Whether Morning does exact, prefix, or fuzzy/contains matching is not stated in the cached Postman collection's description text, and confirming it would require an actual live search call — out of scope for this read-only pass. Not ruled in or out as a contributing cause.

### Recommendation

Three independent candidates, not mutually exclusive:
1. **`status="paid"` over-triggering** — root cause found and documented above; fix is a constitution wording change, same category/risk as bugfix-011's precedent. Strongest, best-evidenced candidate for what actually happened in the reported session (the identical `status="paid"` appears in both attempts, including after the user said "ALL").
2. **Pagination** — confirmed as a real gap in the code, independent of what caused this specific report; worth its own fix regardless, but needs a decision on scope (separate bugfix vs. bundled with this one).
3. **`clientName` matching** — genuinely unconfirmed; would need a live, low-risk read-only API check (e.g. searching a real client with a known alternate-name variant) before any conclusion, which was out of scope this pass.

## Expected Behavior
"All invoices"/"all payments" (no status qualifier from the user) should not silently apply a `status="paid"` filter — either omit the status filter entirely (matching `list_invoices`' own `status: Optional[str] = None` default, which already means "no filter" per `_matches_status`'s `if not status or status == "all": return True`), or explicitly ask the user whether they mean paid-only. Separately, pagination and clientName-matching behavior need to be confirmed correct against real multi-invoice, multi-status client data.

## Acceptance Criteria (blocked on root-cause approval, then live confirmation + fix approval)
- [ ] Reproduce against a real client with multiple invoices of mixed status (verify ground truth via Morning dashboard first, as bugfix-012 was) — not done this pass (read-only, no live calls)
- [x] Strongest root-cause candidate identified and documented at the code/prompt level (`status="paid"` over-triggered by the constitution's payment-word rule matching "תשלומים") — see Investigation Findings
- [x] Pagination gap independently confirmed to exist in the code (real, but not confirmed as this specific report's cause)
- [ ] `clientName` matching semantics confirmed (still needs a live check)
- [ ] Root cause explanation(s) approved by human (BDD gate)
- [ ] Failing test written (BDD, per METHODOLOGY §VII) before any fix
- [ ] Fix approved and applied
- [ ] Test passes; no regression in the existing Morning tools test suite
- [ ] Re-verified live against real production data

## References
- `specs/bugfixes/bugfix-012-financial-summary-drops-nonallowlisted-invoice-types.md` (if written — see note below) and `bugfix-013` (Zehavit name/date-narrowing) — same live testing session, related "unrequested narrowing" pattern
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)

## Note
`bugfix-012` (get_financial_summary type-filter bug) was subsequently written up, fixed, and merged (`specs/done/bugfixes/bugfix-012-financial-summary-drops-nonallowlisted-invoice-types.md`, PR #111). `bugfix-013` (Zehavit client-name garbling / unrequested date narrowing) was also subsequently written up and has now had its root cause investigated (see that spec's own Investigation Findings section, added 2026-07-21 in the same pass as this file's).
