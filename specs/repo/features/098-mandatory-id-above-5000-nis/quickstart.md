# Quickstart: Feature 098

## Change the threshold
1. Edit `allocation_threshold_nis` in `apps/morning-mcp-app/config/config.<env>.json`.
2. Restart the environment (`scripts/stop_all.sh <env>` then `scripts/run_all.sh <env>` -
   needs explicit approval, like every start). DeniDin re-fetches the value at startup.
   Restarting only morning-mcp-app updates the hard refusal immediately, but DeniDin's
   prompts keep the old number until DeniDin restarts too.

## See it working (dev)
- In WhatsApp, as godfather/admin, ask for a 320 of 12,000 ₪ for a client with no ID
  → DeniDin asks for ת.ז / ח.פ (UAT 1.1).
- DeniDin log at startup: one INFO line with the fetched threshold.
- Morning-MCP log on a backstop refusal: `refusal ... client_tax_id_required`.

## Tests
- Unit / integration: `scripts/run_unit_integration_tests.sh` in each app.
- Acceptance (billed): `scripts/run_single_test.sh <node_id>` /
  `scripts/run_multiple_billed_tests.sh <node_id> ...` - needs dev Morning-MCP running
  with the new image.
