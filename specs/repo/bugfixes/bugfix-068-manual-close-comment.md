# Bugfix 068: Prevent "לסגור" Comment from Corrupting Agreement Totals

**Status**: In Progress — **absorbed into Feature 092** (2026-10-03)

The scope of this bugfix (stop `לסגור` from rewriting `manual_agreement_amount`/`invoices_net`;
close a row without changing its real numbers) is now delivered by
`specs/repo/features/092-undo-client-resolution/spec.md`, requirements R5, R6, R9 and R10, as an
explicit, persisted per-line status driven by UI buttons instead of a `force_closed` flag parsed
from the comment. This file stays as a pointer and closes out together with Feature 092.

## Original issue (for the record)

Typing "לסגור" in a Clients-tab comment makes `clients_reader._apply_status_directives` set
`manual_agreement_amount = invoices_net = max(agreed, paid)` so the row renders green. This
fakes the firm's financial data: a client who agreed to ₪10k and paid ₪2k shows as ₪10k/₪10k.
The required outcome: the row goes green while still showing the real ₪10k agreed / ₪2k paid.
