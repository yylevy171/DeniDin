# Bugfix Spec: Morning document-creation confirmations omit the document link

## Bug ID
bugfix-050-morning-create-confirmations-omit-document-link

## Title
`create_invoice`, `create_combo_document`, `create_transaction_account`, `create_credit_note`,
and `create_receipt` all return a Hebrew confirmation string that does **not** contain a link to
the created document, even though Morning's own create response carries one. Morning returns a
`url: {he, origin}` object on every successful `POST /documents` (confirmed live for type 305 and
type 320), but every one of these tools builds its `Invoice` object with the direct
`Invoice(...)` constructor and never copies `response["url"]` into `Invoice.pdf_url` — so
`format_invoice_confirmation`'s `if invoice.pdf_url:` branch never fires and the `קישור:` line is
never emitted.

Downstream effect: `apps/denidin-app`'s `runtime_constitution.md` tells the model that a
create-document confirmation must always include a link, unprompted. With no link in the tool
output, the model's only way to satisfy that is to make a *separate* `download_invoice_pdf`
call and paste its result — which it does only sometimes. So the user gets a link on some runs
and not others, for the same action.

## Priority
**P2** — no wrong data is produced and the document is created correctly; the confirmation is
just missing a field it is supposed to carry, inconsistently. Annoying and constitution-violating,
not dangerous.

## Status
**Open — backlogged.** No fix designed. Per Bug-Driven Development (METHODOLOGY.md §VII), next
step is human approval of the root cause before test-gap analysis.

## Date Opened
2026-09-02

## Reported By
yaronlev171, during the Feature 059 billed-test stabilization sweep — `test_godfather_creates_
invoice_via_whatsapp` (rephrased that run to request a חשבונית מס/קבלה) failed its
`assert "http" in response` because `create_combo_document`'s confirmation carried no link, and
investigation showed `create_invoice` has the identical gap.

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` — `create_invoice` (~L773),
  `create_combo_document` (~L688), `create_transaction_account` (~L440), `create_credit_note`,
  `create_receipt`, and the reference variants (`create_combo_document_as_reference`) that reuse
  `format_invoice_confirmation`. Each constructs `Invoice(...)` directly and drops
  `response["url"]`.
- `apps/morning-mcp-app/src/denidin_mcp_morning/models.py` — `Invoice.from_api` (~L325) already
  maps `url.he`/`url.origin` → `pdf_url`; the create tools bypass it.
- `apps/morning-mcp-app/src/denidin_mcp_morning/formatters.py` — `format_invoice_confirmation`
  (~L92): the `if invoice.pdf_url:` branch that renders `קישור:`. Correct as written; it just
  never receives a populated `pdf_url` from the create path.
- `apps/denidin-app/config/runtime_constitution.md` — states the confirmation must include a
  link; currently only satisfiable via a separate `download_invoice_pdf` call.

## Description

### Observed
1. `create_combo_document` for a fresh חשבונית מס/קבלה (type 320): Morning `POST /documents`
   returns `status 201` with `url: {origin: "https://sandbox.d.greeninvoice.co.il/api/v1/
   documents/download?d=…", he: "…"}`. The MCP tool result is:
   `חשבונית #60463\nלקוח: "חוסיין שדה"\nסכום: ₪66.00\nסוג מסמך: חשבונית מס / קבלה\nמזהה פנימי
   (internal_morning_id): cce16652-…` — no link.
2. `create_invoice` (type 305): identical — Morning returns the same `url` object shape, the
   tool builds `Invoice(...)` without `pdf_url`, confirmation has no `קישור:` line.
3. `apps/denidin-app` billed test `test_godfather_creates_invoice_via_whatsapp` asserted
   `"http" in response` and passed only on runs where the model independently called
   `download_invoice_pdf`; it is a latent flake, not new to Feature 059.

### Expected
Every Morning create-document tool's confirmation string carries the document's own link
(`קישור: …`), sourced directly from the create response's `url` object, deterministically —
no separate `download_invoice_pdf` round-trip, no model-dependent behavior.

### Not in scope of this bug
- Changing `format_invoice_confirmation`'s output shape beyond the already-present `קישור:` line.
- `download_invoice_pdf` itself (works; builds the link from `url.he/origin/lang`).

## Test-gap analysis (to be done after root-cause approval)
Candidate: a `billed` (or sandbox-integration) test per create tool asserting the confirmation
string contains `קישור:` and an `https://…/documents/download` URL, with the model making no
`download_invoice_pdf` call. `apps/denidin-app`'s `test_godfather_creates_invoice_via_whatsapp`
would then legitimately re-add its link assertion.

## Related
- Feature 059 (`specs/low-priority/059-stabilize-tests-sanity-suite`) — surfaced this; that
  feature's fix is only to comment out the nondeterministic `"http"` assertion, deferring the
  real fix here.
- `download_invoice_pdf` (`formatters.py` ~L2629) — the current, indirect way a link is obtained.
