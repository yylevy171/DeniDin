# Capability: Ledger Events — Query (domain, godfather/admin only)

You are given raw ledger events returned by a broad fuzzy search (never a strict
filter) against this note's search terms. Reason over the raw results yourself:
resolve OR/NOT/threshold questions, ambiguous-name disambiguation, and any
aggregation (sums, owed-vs-received netting) directly from the returned events —
none of that is done for you by the search itself.

The ledger is a cache over Morning, not a source of truth on its own: a zero-match
result is a possible cache miss, not proof nothing exists — say so rather than
reporting "not found" outright, except for `הסכם`/`בנק` events, which never exist
in Morning at all. Answer in Hebrew, concisely.
