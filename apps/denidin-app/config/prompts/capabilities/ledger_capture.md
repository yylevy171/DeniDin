# Capability: Ledger Events — Capture (domain, godfather/admin only)

Capture is automatic — you do not need to do anything here. A separate,
already-proven post-turn recognition mechanism reads every godfather/admin
turn (this conversation's own persisted message, text or media-extracted
alike) after you reply, and captures any genuine new fee-agreement (הסכם) or
bank-deposit (בנק) event on its own, with no action from you.

This step exists only so Planning has an explicit, documented answer when a
turn looks like it might involve capturing a ledger event: there is nothing
to call and nothing to decide — simply continue with your reply as normal.
Do not attempt to capture, confirm, or mention "saving" the event yourself;
saying so would be redundant with (and could confuse the user about) the
automatic mechanism, which already handles it silently in the background.

Note: capture of a Morning-sourced accounting document (חשבונית) is the
accounting-reconciliation service's own job — always separate from both this
step and the post-turn mechanism above.
