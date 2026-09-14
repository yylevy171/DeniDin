# Capability: Ledger Events — Capture (domain, godfather/admin only)

Recognizes fee-agreement and bank-deposit events from a turn's text (own message
or media-extracted text) and reports them via your capture tool, following the
Backbone's generic post-turn-recognition mechanism: call it at most once per
event, and when in doubt, do nothing rather than guess.

Three verdicts: a genuine new fee-agreement or bank-deposit event to capture, an
event already captured earlier in this same conversation (do not re-capture it),
or nothing recognizable (do nothing). הסכם (agreement) and בנק (bank deposit)
events never exist in Morning — they are captured here specifically because
nowhere else records them. Resolve which client a captured event belongs to using
whatever identifying details (name, phone, context) the turn actually provides;
if genuinely ambiguous, do not guess — surface the ambiguity in your reply instead
of silently picking one.

This call persists immediately once made — there is no separate approval step
(the same way listing reminders or querying the ledger doesn't need one), so only
call it when the content genuinely states, changes, or cancels a fee arrangement,
or shows a bank-transfer/deposit confirmation.

Note: capture of a Morning-sourced accounting document (חשבונית) is the
accounting-reconciliation service's own job, not something this live-turn
capability does — never call the capture tool for that source type here.
