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

Note: full write-side wiring for this capability (the actual capture-tool
dispatch) is tracked as follow-up work (tasks.md's Deferred section) — this
prompt file is authored now so the capability's boundaries are already defined
when that wiring lands.
