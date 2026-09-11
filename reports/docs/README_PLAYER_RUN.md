# Rapaport's Operational Guide: Replaying WhatsApp Chats via the Player

**Author:** Rapaport (Senior Business & Operations Analyst)  
**Date:** September 11, 2026  
**Purpose:** Standard Operating Procedure (SOP) for replaying WhatsApp chat exports through DeniDin's AI event extraction pipeline (`player/run_player.py`) to backfill missing fee agreements and payments without data duplication or ledger corruption.

---

## 1. Executive Summary & Why We Need This
In our historical audit, we discovered that **prior to July 1, 2026, agreement events were completely omitted from the structured event ledger (`events/A*.json`)**. Over 110 agreements from Jan–Jun 2026 (and ~215 from 2025) remain trapped in raw WhatsApp text messages.

To close this operational gap cleanly, we use the DeniDin Player (Feature 043). The player simulates live WhatsApp webhook deliveries through DeniDin's LLM parser, generating legitimate, structured ledger event JSON files (`A*.json` and `B*.json`).

---

## 2. Architecture & Key Files
* **Entry Point:** `apps/denidin-app/player/run_player.py`
* **Parser Logic:** `apps/denidin-app/player/export_parser.py`
* **Player Configuration:** `apps/denidin-app/player/player_run_ahledger_prod.json` (or custom config)
* **Application Config:** `apps/denidin-app/config/config.player_prod.json`
* **Raw Chat Source:** `reports/19.8.26 whatsapp export/WhatsApp Chat with $$ גבייה אילה $$.txt` (or zip file `/Users/yaron/Projects/AHLedger/גבייה 19.8.26.zip`)
* **Production Event Target:** `~/denidin-winprod-data/events/` (or staging `player_data/events/`)

---

## 3. Pre-Flight Checklist (Critical Safety Rules)

> [!WARNING]
> **Production Safety Gate:** If `data_root` in your config resolves to `data` or points to live production data, you **MUST** explicitly pass `--confirm-production-data-root` on the command line.

1. **Always use an isolated `data_root` first:**
   Never replay directly into `~/denidin-winprod-data/events` on the first try. Output to `reports/player/output_staging/events` or `player_data`, verify the generated `A*.json` files, and reconcile before copying to production.
2. **Always use `--sound-off`:**
   This prints real-time status `[message i/total, line=N, sender, events_created]` to stdout so you can monitor progress and grab the exact resume line number if stopped.
3. **Use the Dedicated Virtual Environment:**
   Run with the Python interpreter at `/Users/yaron/Projects/DeniDin/apps/denidin-app/venv/bin/python` with `PYTHONPATH=/Users/yaron/Projects/DeniDin/apps/denidin-app`.

---

## 4. Player Configuration Template

Create or verify `reports/player/player_config_gap_backfill.json`:

```json
{
  "export_zip": "/Users/yaron/Projects/AHLedger/גבייה 19.8.26.zip",
  "chat_id": "120363210094632983@g.us",
  "sender_map": {
    "אילה 🐣": "972506205541@c.us",
    "Yaron Levy": "972522968679@c.us",
    "רון של נגה של אילה": "972587088887@c.us"
  },
  "data_root": "reports/player/staging_data",
  "denidin_config": "config/config.player_prod.json",
  "whatsapp_own_number": "972552468948"
}
```

---

## 5. Execution Commands

### A. Dry Run / Test on a Single Day (e.g., May 12, 2026)
```bash
cd /Users/yaron/Projects/DeniDin/apps/denidin-app
PYTHONPATH=. ./venv/bin/python player/run_player.py \
    ../../teammate5/reports/player/player_config_gap_backfill.json \
    --start 2026-05-12 \
    --end 2026-05-12 \
    --sound-off
```

### B. Full Missing Period Backfill (Jan 1, 2026 – June 30, 2026)
```bash
cd /Users/yaron/Projects/DeniDin/apps/denidin-app
PYTHONPATH=. ./venv/bin/python player/run_player.py \
    ../../teammate5/reports/player/player_config_gap_backfill.json \
    --start 2026-01-01 \
    --end 2026-06-30 \
    --sound-off
```

### C. Resuming an Interrupted Run (Avoid Duplication!)
If a run stops or crashes, check the last line printed (e.g. `line=1621`). Resume strictly from that line using `--start-at-line`:
```bash
cd /Users/yaron/Projects/DeniDin/apps/denidin-app
PYTHONPATH=. ./venv/bin/python player/run_player.py \
    ../../teammate5/reports/player/player_config_gap_backfill.json \
    --start 2026-01-01 \
    --end 2026-06-30 \
    --start-at-line 1621 \
    --sound-off
```

---

## 6. Post-Run Verification & Ingestion
1. Inspect the summary output in `staging_data/events/_runs/<run_id>/summary.json`.
2. Inspect the created `A*.json` files.
3. Check for any events flagged for review in `needs_clarification.jsonl`.
4. Run our reconciliation script to merge newly discovered agreements into the master ledger and update `generate_client_status.py`.
