# Quickstart: 102 - Calendar Reminders as WhatsApp Events (.ics)

## Try the builder (no environment needed)
```bash
cd apps/denidin-app
venv/bin/python3 - <<'PY'
from src.utils.reminder_ics import CalendarEntry, build_ics
print(build_ics([CalendarEntry("rem-1", "לשלם לספק", "2026-10-20T11:00:00+03:00", None, 0)]).decode())
PY
```

## Run the tests (always through the wrapper - never bare pytest)
```bash
cd apps/denidin-app
scripts/run_unit_integration_tests.sh tests/unit/test_reminder_ics.py tests/unit/test_reminder_manager_ics.py \
  tests/unit/test_whatsapp_handler_calendar_file.py tests/unit/test_denidin_send_calendar_file.py \
  tests/unit/test_capability_reminders_calendar_file.py tests/unit/test_backbone_reminder_calendar_flush.py \
  tests/unit/test_reminders_calendar_prompts.py tests/integration/test_reminder_calendar_file_102.py
```

## Acceptance (billed, needs the user's go-ahead before the first run; dev environment running)
`tests/billed/test_reminder_calendar_file_102.py` - one test per approved UAT (1.1-5.4). UAT 3.1 is manual:
tap the received file on Android and confirm the calendar sheet opens.

## Operational notes
- No new config. The temp folder is `{data_root}/tmp/reminder_ics/` and is emptied after every send.
- Deploying needs a new release (prompts under `config/prompts/` are baked into the image) - a human decision.
- The new `reminder_ics_sequences` table is created automatically at startup (`IF NOT EXISTS`); existing reminders start at SEQUENCE 0.

## Manual device checks (not automatable)
1. **UAT 3.1** - on Android, tap a received `.ics` in WhatsApp: the calendar sheet opens with the title and time, no alert.
2. **Unchanged re-send** - ask DeniDin for the calendar file of a reminder that is already on the calendar; tap it.
   Record: updated in place (expected) / duplicated / ignored. (Not yet verified, spec section 2.)
