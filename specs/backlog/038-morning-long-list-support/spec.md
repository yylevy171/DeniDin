# Feature Spec: Morning Long List Support

**Feature ID**: 038-morning-long-list-support
**Priority**: TBD
**Status**: Draft
**Created**: August 4, 2026

---

## Origin

Observed live in prod (2026-08-04): a query for July invoices returned 46 of
62 actual documents, silently dropping the rest — the user caught the
discrepancy manually by cross-checking against the Green Invoice website.

## Problem Statement

`list_invoices` (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`,
line 411) fetches only a single page from Morning's `/documents/search` and
hard-caps results to `_LIST_INVOICES_MAX_ITEMS = 10` client-side (line 44),
silently truncating anything beyond that — only a `has_more` flag hints that
more results exist. There is no loop to fetch additional Morning pages.

`search_clients` (same file, ~line 909) already solves the equivalent
problem correctly for `/clients/search`: it loops through Morning's pages
(`page`/`total`/`total_pages`) until the full result set is retrieved.
`list_invoices` does not apply this pattern.

## Requirement (confirmed direction)

Apply the same real-pagination approach `search_clients` already uses to
`list_invoices` — loop Morning's `/documents/search` pages and return the
complete matching set (or a substantially higher cap than 10), instead of
truncating after one page.

## Open Questions (for `speckit.clarify`)

- Is a sane upper bound still needed to avoid a single WhatsApp
  reply/token budget blowing up on a very wide query (e.g. "all invoices
  ever")?
- Does the conversational layer need its own pagination/summarization on
  top of a fully-fetched result set, or is "fetch everything, let the model
  summarize" sufficient?

---

*No `speckit.plan`/`user-stories.md`/`tasks.md` has been run yet — this is a
definition-only draft, not a fully specified feature.*
