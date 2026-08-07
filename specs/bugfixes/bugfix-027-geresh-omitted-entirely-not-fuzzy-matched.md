# Bugfix Spec: Client search doesn't find a geresh-containing name when the geresh is typed omitted entirely

## Bug ID
bugfix-027-geresh-omitted-entirely-not-fuzzy-matched

## Title
A client-name search/reference that omits the Hebrew geresh consonant-modifier entirely (e.g.
"גקי", "צוצו") does not resolve to the real, geresh-containing stored client name ("ג׳קי",
"צ'וצ'ו") - unlike a search that uses the *wrong* punctuation variant (apostrophe instead of
geresh), which bugfix (implemented directly under Feature 027, 2026-08-07, see below) already
fixed.

## Priority
P2 - a real, user-facing false-negative ("client not found" for a client that exists), but
narrower than the sibling issue this was split from: it only affects the subset of client names
that use a geresh-marked consonant (ג׳/צ׳/ח׳/ז׳-type sounds) AND where the reference typed/said
omits the geresh character rather than merely using the wrong punctuation mark for it.

## Status
Open - deferred by explicit user decision (2026-08-07) at the same time the sibling
apostrophe/geresh **punctuation-variant** bug was fixed directly under Feature 027 (see
"Related Work" below), because this is a distinct and meaningfully more complex problem, not a
one-line extension of that fix. No fix has been designed or implemented. Per Bug-Driven
Development (METHODOLOGY.md §VII), next step is human approval of the root cause/complexity
assessment below before any test-gap analysis or fix design begins.

## Date Opened
2026-08-07

## Reported By
yaronlev171, while reviewing the sibling apostrophe/geresh punctuation-variant bug found during
Feature 027 (mandatory-client-reference-invoicing) verification. Explicitly asked for the
missing-geresh case ("search for גקי should find ג׳קי") to be assessed and either fixed
alongside the punctuation-variant bug or split into its own bugfix if too complex - it was
judged too complex to bundle, hence this spec.

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` - `_resolve_client_by_name` (and every
  caller: `get_client_details`, `update_client`, `_resolve_client_for_document_creation`,
  `list_clients`'s `name` filter) - all delegate directly to
  `MorningClient.search_clients({"name": ...})`, a real, remote Morning API call whose matching
  semantics this app does not control.

## Description
Two related but distinct client-name matching gaps exist for Hebrew names that use a geresh
(׳) to mark a non-native consonant sound (e.g. ג׳ for "j", צ׳ for "ch", ח׳/ז׳ for other
non-native sounds - roughly 11% of the shared Hebrew family-name test pool,
`apps/denidin-app/tests/billed/data/hebrew_family_names.txt`, contains one):

1. **Wrong punctuation variant** (FIXED under Feature 027, 2026-08-07): the model/user types an
   ASCII apostrophe (`'`) or typographic apostrophe (`'`) where the stored record - or a later
   reference to the same name - uses the correct Hebrew geresh (`׳`), or vice versa. Confirmed
   live: a full-name Morning search for `"פיליפ סידורוביץ׳"` (geresh) returned **zero** matches
   against a client actually stored as `"פיליפ סידורוביץ'"` (apostrophe), even though a shorter,
   punctuation-free query (`"פיליפ"`) found it fine. Fixed by normalizing every client name to
   the single correct geresh form at every write/lookup boundary
   (`tools._normalize_hebrew_geresh`, 12 new unit tests in
   `tests/unit/test_tools_client_management.py`) - this makes the exact punctuation character
   typed irrelevant, since both the stored record and every query are canonicalized before
   comparison.

2. **Geresh omitted entirely** (THIS bugfix, NOT fixed): a reference that drops the
   geresh-marked consonant's modifier character altogether - not substituting a different
   punctuation mark for it, but typing the name as if the modifier weren't there at all (e.g.
   "גקי" instead of "ג׳קי" for "Jackie", or "צוצו" instead of "צ'וצ'ו"/"צ׳וצ׳ו"). Normalization
   (case 1's fix) cannot help here: there is no apostrophe/geresh character present in the query
   to normalize - the query and the stored name literally differ by a whole character being
   present vs. absent, not by which punctuation mark represents it.

## Why this is more complex than case 1 (root cause / complexity assessment, pending approval)

- Morning's real client search is a **remote, server-side token-prefix match** (confirmed live,
  `research.md` Decision 12, Feature 026) - this app does not control or reimplement its
  matching algorithm. A query for "גקי" and a stored token "ג׳קי" are different strings to that
  index; there is no normalization this app can apply to the query alone that makes Morning's
  own search engine treat them as the same token.
- Supporting this would require *not* trusting Morning's search as the sole source of
  candidates: e.g. fetching a broader candidate set (or all clients - real accounts can hold
  hundreds, `list_clients`'s own docstring cites 278 in this app's sandbox) and doing local
  fuzzy comparison by stripping geresh characters from both the query and every candidate name
  before comparing.
- That approach has real costs case 1 did not: extra Morning API calls / latency (potentially
  multiple pages for a large account), and new ambiguity risk (a short, punctuation-stripped
  query could now coincidentally match an unrelated client that never had a geresh at all, or
  fail to disambiguate between two clients that only differ by geresh placement).
- It is a genuine change in matching **semantics** (a new fuzzy-search capability), not a
  boundary-normalization fix - it deserves its own scoped design, disambiguation rules, and test
  coverage rather than folding into case 1's fix.

## Related Work
- Feature 027 (`specs/in-progress/027-mandatory-client-reference-invoicing/`) - the feature
  whose real-sandbox verification surfaced case 1, fixed directly on that branch (see
  `_normalize_hebrew_geresh` in `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`).
- Feature 031 (`specs/done/031-fuzzy-client-lookup-by-name/`) - already-shipped, general
  substring/prefix fuzzy matching (the `is_exact_match`/disclosure mechanism). Does not mention
  or address geresh/apostrophe handling at all - confirmed via a text search of its spec - so
  this bugfix is a genuinely new gap, not a regression of that feature.

## Next Step
Per BDD, awaiting human approval of the complexity assessment above (and a priority/scheduling
decision - this may be better suited to a small dedicated feature spec than a bugfix, given it's
a new capability rather than a regression) before any test-gap analysis or fix design begins.
