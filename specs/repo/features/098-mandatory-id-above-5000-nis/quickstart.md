# Quickstart: Feature 098

## Change the threshold
1. Edit `allocation_threshold_nis` in **both**
   `apps/morning-mcp-app/config/config.<env>.json` and
   `apps/denidin-app/config/config.<env>.json` - same value. Nothing checks they match.
2. Restart the environment (`scripts/stop_all.sh <env>` then `scripts/run_all.sh <env>` -
   needs explicit approval, like every start). Both config files are mounted, so no
   rebuild is needed.
3. **Prod** runs on the Windows box with its own config files - edit them there. Both
   apps default to 5000 (and morning-mcp-app's VAT rate to 0.18) if the field is absent.

## See it working (dev)
- In WhatsApp, as godfather/admin, ask for a 320 of 12,000 ₪ for a client with no ID
  → DeniDin asks for ת.ז / ח.פ (UAT 1.1).
- Morning-MCP log on a backstop refusal: `refusal ... client_tax_id_required`.

## Tests
- Unit / integration: `scripts/run_unit_integration_tests.sh` in each app.
- Acceptance (billed): `scripts/run_single_test.sh <node_id>` /
  `scripts/run_multiple_billed_tests.sh <node_id> ...` - needs dev Morning-MCP running
  with the new image.
