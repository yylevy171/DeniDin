#!/usr/bin/env python3
"""Deterministic fixture seeder for Feature 068's Playwright acceptance suite.

Writes real on-disk data (events / sessions / messages / media / password hash) into one or
more data roots under ``apps/webapp/e2e/.fixture/`` — no mocking, exactly the layout
``LedgerReader`` / ``ContextReader`` read in production. All dates are computed **relative to
the day the seeder runs** so the trailing-window and lookback assertions never go stale.

Usage:  python3 e2e/seed_fixture.py            # (re)build every fixture root
        python3 e2e/seed_fixture.py --print    # also dump the derived constants as JSON

The derived constants (event ids, expected counts, the password) are mirrored by hand in
``e2e/fixtures.ts`` — ``--print`` is the cross-check.
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE_ROOT = HERE / ".fixture"
PASSWORD = "e2e-pass"
PASSWORD_SALT = "denidin-pw"  # webapp_backend.auth.PASSWORD_SALT

# --- tiny real binary assets (1x1) --------------------------------------------------------
_JPEG_1PX = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA"
    "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
    "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
    "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
    "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/9oADAMB"
    "AAIRAxEAPwD3+iiigD//2Q=="
)
_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
_PDF_MIN = (
    b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 120 120]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
    b"0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n170\n%%EOF\n"
)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S+03:00")


def _ddmmyyyy(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y")


class Builder:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.events = root / "events"
        self.sessions = root / "sessions"
        self.media = root / "media"
        for d in (self.events, self.sessions, self.media):
            d.mkdir(parents=True, exist_ok=True)
        (root / "auth").mkdir(parents=True, exist_ok=True)
        import hashlib

        (root / "auth" / "password.hash").write_text(
            hashlib.sha256((PASSWORD_SALT + PASSWORD).encode()).hexdigest(), encoding="utf-8"
        )
        self.today = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)

    def day(self, back: int, hour: int = 12, minute: int = 0) -> datetime:
        return (self.today - timedelta(days=back)).replace(hour=hour, minute=minute)

    # -- events ---------------------------------------------------------------------------
    def event(self, event_id: str, **fields) -> None:
        base = {
            "event_id": event_id,
            "source_type": None,
            "event_subtype": None,
            "client_name": None,
            "amount": None,
            "description": None,
            "session_id": None,
            "message_id": None,
            "vat_status": None,
            "captured_at": _iso(self.today),
        }
        base.update(fields)
        (self.events / f"{event_id}.json").write_text(
            json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # -- sessions / messages ------------------------------------------------------------
    def session(self, sid: str, messages: list[dict], *, sub: str = "messages",
                stale_dir: str | None = None) -> None:
        sdir = self.sessions / sid if stale_dir is None else self.sessions / stale_dir / sid
        (sdir / sub).mkdir(parents=True, exist_ok=True)
        (sdir / "session.json").write_text(
            json.dumps({"session_id": sid}, ensure_ascii=False), encoding="utf-8"
        )
        for m in messages:
            (sdir / sub / f"{m['message_id']}.json").write_text(
                json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def media_file(self, name: str, kind: str = "jpg") -> str:
        data = {"jpg": _JPEG_1PX, "png": _PNG_1PX, "pdf": _PDF_MIN}[kind]
        (self.media / name).write_bytes(data)
        return f"media/{name}"


def _msg(mid: str, role: str, content: str, ts: datetime, *, sender: str | None = None,
         image_path: str | None = None) -> dict:
    return {
        "message_id": mid,
        "role": role,
        "content": content,
        "timestamp": _iso(ts),
        "sender": sender or ("someone" if role != "assistant" else None),
        "image_path": image_path,
    }


def build_full(root: Path) -> dict:
    b = Builder(root)

    # ---- E1: הסכם/יצירה, anchor with an image, bidirectional lookback window -----------
    s1_anchor = b.day(2, 14, 0)
    img1 = b.media_file("e1-anchor.jpg", "jpg")
    img1b = b.media_file("e1-second.png", "png")
    b.session("S1", [
        _msg("M0", "user", "בדיוק על הגבול", s1_anchor - timedelta(minutes=10), sender="דוד"),
        _msg("M1", "user", "הסכם עם ישראל ישראלי", s1_anchor - timedelta(minutes=9), sender="דוד"),
        _msg("M2", "user", "8000 שקל בשני תשלומים", s1_anchor - timedelta(minutes=3), sender="דוד",
             image_path=img1b),
        _msg("M3", "user", "הנה הצילום", s1_anchor, sender="דוד", image_path=img1),
        _msg("M4", "assistant", "נרשם. הסכם שכר טרחה נקלט.", s1_anchor + timedelta(minutes=2)),
        _msg("M5", "user", "מחוץ לחלון", s1_anchor + timedelta(minutes=20), sender="דוד"),
    ])
    b.event("E1", source_type="הסכם", event_subtype="יצירה", client_name="ישראל ישראלי",
            amount=5000, description="שכר טרחה עבור ישראל ישראלי",
            event_date=_ddmmyyyy(s1_anchor), event_time="14:00", txn_date=None,
            session_id="S1", message_id="M3", vat_status="לא צוין",
            component_label="שכר טרחה", percent=10, trigger_condition=None,
            hours=None, hourly_rate=None, reference=None, reference_hint=None,
            payer_name=None, split_partner=None, split_percent=None)

    # ---- E2: בנק/הפקדה, 8 days back (out of default 7, in 14) --------------------------
    d8 = b.day(8, 9, 30)
    b.session("S2", [
        _msg("M20", "user", "הפקדה של בר רפאלי", d8 - timedelta(minutes=4), sender="דוד"),
        _msg("M21", "assistant", "נקלט.", d8 + timedelta(minutes=1)),
        _msg("M2B", "user", "העברה בנקאית עבור שכר טרחה", d8 - timedelta(minutes=2), sender="דוד"),
        _msg("M2C", "assistant", "הפקדה נרשמה.", d8 + timedelta(minutes=2)),
    ])
    b.event("E2", source_type="בנק", event_subtype="הפקדה", client_name="דנה כהן",
            amount=1200, description="העברה בנקאית עבור שכר טרחה",
            event_date=_ddmmyyyy(d8), event_time="09:30", txn_date=_ddmmyyyy(d8),
            session_id="S2", message_id="M2B",
            bank_number="12", bank_branch="736", bank_account="654844",
            vat_status=None, payer_name="דנה כהן")

    # ---- E3: הסכם/עדכון exactly 7 days back (boundary — included) ----------------------
    d7 = b.day(7, 10, 0)
    b.session("S3", [
        _msg("M30", "user", "עדכון להסכם של משה לוי", d7 - timedelta(minutes=2), sender="דוד"),
        _msg("M31", "assistant", "ההסכם עודכן.", d7 + timedelta(minutes=1)),
    ])
    b.event("E3", source_type="הסכם", event_subtype="עדכון", client_name="משה לוי",
            amount=3000, description="עדכון שכר טרחה", event_date=_ddmmyyyy(d7),
            event_time="10:00", session_id="S3", message_id="M30",
            reference="REF-9", reference_hint=None, vat_status="כולל מע\"מ")

    # ---- E4: חשבונית / "חשבונית מס / קבלה" + bank transfer -> bank fields shown --------
    d3 = b.day(3, 16, 0)
    b.event("E4", source_type="חשבונית", event_subtype="חשבונית מס / קבלה",
            client_name="מרים אבן", amount=800, description="ייעוץ משפטי",
            event_datetime=f"{_ddmmyyyy(d3)} 16:00", txn_date=None,
            session_id="accounting-reconciliation", message_id=None,
            accounting_document_display_number="40429",
            accounting_document_status_label="מסמך פתוח",
            accounting_document_status="לא שולם", accounting_document_status_code=0,
            accounting_document_payment_method="העברה בנקאית",
            bank_number=None, bank_branch=None, bank_account=None,
            vat_status="לא צוין")

    # ---- E5 / E6: identical date (day 1) — tiebreaker: event_id descending ------------
    d1 = b.day(1, 11, 0)
    b.event("E5", source_type="חשבונית", event_subtype="חשבון עסקה", client_name="יוסי חן",
            amount=250, description="חשבון עסקה", event_datetime=f"{_ddmmyyyy(d1)} 11:00",
            session_id="accounting-reconciliation", message_id=None,
            accounting_document_display_number="40430",
            accounting_document_status_label="מסמך פתוח", vat_status="לא צוין")
    b.event("E6", source_type="חשבונית", event_subtype="חשבונית מס", client_name="טל ברק",
            amount=999, description="חשבונית מס", event_datetime=f"{_ddmmyyyy(d1)} 11:00",
            session_id="accounting-reconciliation", message_id=None,
            accounting_document_display_number="40431",
            accounting_document_status_label="שולם",
            accounting_document_payment_method="מזומן", vat_status="כולל מע\"מ")

    # ---- E7: בנק / מבוטל (subtype != הפקדה) -> bank fields IF-EXISTS (absent here) -----
    d0 = b.day(0, 8, 0)
    b.event("E7", source_type="בנק", event_subtype="מבוטל", client_name="רון גל",
            amount=400, description="הפקדה שבוטלה", event_date=_ddmmyyyy(d0),
            event_time="08:00", session_id=None, message_id=None,
            bank_number=None, bank_branch=None, bank_account=None, vat_status=None)

    # ---- E8: null amount (excluded from Σ) -------------------------------------------
    b.event("E8", source_type="הסכם", event_subtype="יצירה", client_name="נועה שקד",
            amount=None, description="הסכם ללא סכום", event_date=_ddmmyyyy(d0),
            event_time="08:05", session_id=None, message_id=None, vat_status="לא צוין")

    # ---- E9: חשבונית זיכוי, negative amount -----------------------------------------
    b.event("E9", source_type="חשבונית", event_subtype="חשבונית זיכוי", client_name="עדי מור",
            amount=-500, description="זיכוי", event_datetime=f"{_ddmmyyyy(d0)} 08:10",
            session_id="accounting-reconciliation", message_id=None,
            accounting_document_display_number="40432",
            accounting_document_status_label="מסמך פתוח",
            reference="", reference_hint="", vat_status="לא צוין")

    # ---- E10: unknown source_type -> unsupported detail panel -----------------------
    b.event("E10", source_type="מוזר", event_subtype=None, client_name="לא ידוע",
            amount=100, description="סוג לא מוכר", event_date=_ddmmyyyy(d0),
            event_time="08:15", session_id=None, message_id=None)

    # ---- E11: full-history event (day 400) — client prefix "ישראל" -----------------
    d400 = b.day(400, 12, 0)
    b.event("E11", source_type="הסכם", event_subtype="יצירה", client_name="ישראל כהן",
            amount=7000, description="הסכם ישן מאוד", event_date=_ddmmyyyy(d400),
            event_time="12:00", session_id=None, message_id=None, vat_status="לא צוין")

    # ---- E12: stale session_id, message lives in canonical S1 via message_id --------
    d2b = b.day(2, 15, 30)
    b.event("E12", source_type="הסכם", event_subtype="יצירה", client_name="בר רפאלי",
            amount=1500, description="בדיקת פתרון לפי מזהה הודעה",
            event_date=_ddmmyyyy(d2b), event_time="15:30",
            session_id="OLD-DEAD-SID-DOES-NOT-EXIST", message_id="M20",
            vat_status="לא צוין")

    # ---- E13: חשבונית / קבלה (400) + bank transfer + populated bank fields;
    #          its session carries a broken image + a PDF attachment ----------------
    d2c = b.day(2, 17, 0)
    pdf = b.media_file("e13-doc.pdf", "pdf")
    b.session("S13", [
        _msg("M130", "user", "קבלה עבור גיא עוז", d2c - timedelta(minutes=3), sender="דוד"),
        _msg("M131", "user", "מסמך מצורף", d2c - timedelta(minutes=1), sender="דוד",
             image_path=pdf),
        _msg("M132", "user", "והנה עוד תמונה", d2c, sender="דוד",
             image_path="media/does-not-exist.jpg"),
        _msg("M133", "assistant", "הקבלה נקלטה.", d2c + timedelta(minutes=2)),
    ])
    b.event("E13", source_type="חשבונית", event_subtype="קבלה", client_name="גיא עוז",
            amount=600, description="קבלה", event_datetime=f"{_ddmmyyyy(d2c)} 17:00",
            session_id="S13", message_id="M130",
            accounting_document_display_number="40433",
            accounting_document_status_label="שולם",
            accounting_document_payment_method="העברה בנקאית",
            bank_number="10", bank_branch="800", bank_account="123456",
            vat_status="כולל מע\"מ")

    # ---- E14: הסכם/יצירה with reference populated (IF-EXISTS shows even for יצירה) ----
    d4 = b.day(4, 13, 0)
    b.session("S14", [
        _msg("M140", "user", "הסכם עם אלון דר", d4 - timedelta(minutes=2), sender="דוד"),
        _msg("M141", "assistant", "נקלט.", d4 + timedelta(minutes=1)),
    ])
    b.event("E14", source_type="הסכם", event_subtype="יצירה", client_name="אלון דר",
            amount=2200, description="שכר טרחה לפי שעות", event_date=_ddmmyyyy(d4),
            event_time="13:00", session_id="S14", message_id="M140",
            reference="REF-14", reference_hint="לפי מייל", component_label="ריטיינר",
            hours=None, hourly_rate=None, percent=None, vat_status="לא צוין")

    # ---- E16: valid detail, but message_id resolves to nothing (session-resolves-
    #          -but-message-doesn't / unavailable-context graceful path) -------------
    b.event("E16", source_type="חשבונית", event_subtype="חשבונית מס", client_name="נוי שגב",
            amount=300, description="בדיקת כשל טעינת שיחה",
            event_datetime=f"{_ddmmyyyy(d0)} 08:25",
            session_id="S1", message_id="GHOST-MSG-NOT-ON-DISK",
            accounting_document_display_number="40435",
            accounting_document_status_label="מסמך פתוח", vat_status="לא צוין")

    # ---- E15: reconciliation event, no message_id -> no_conversation ---------------
    b.event("E15", source_type="חשבונית", event_subtype="חשבונית מס", client_name="פז אור",
            amount=1000, description="נקלט אוטומטית מ-Morning",
            event_datetime=f"{_ddmmyyyy(d0)} 08:20",
            session_id="accounting-reconciliation", message_id=None,
            accounting_document_display_number="40434",
            accounting_document_status_label="מסמך פתוח", vat_status="לא צוין")

    within7 = ["E1", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E12", "E13", "E14", "E15", "E16", "E3"]
    within14 = within7 + ["E2"]
    return {
        "password": PASSWORD,
        "root": str(root),
        "all_event_ids": sorted(p.stem for p in b.events.glob("*.json")),
        "within_7_days": within7,
        "within_14_days": within14,
        "boundary_included_id": "E3",       # exactly 7 days back
        "outside_7_within_14_id": "E2",     # 8 days back
        "same_date_pair": ["E5", "E6"],     # E6 sorts before E5 (event_id desc)
        "null_amount_id": "E8",
        "negative_amount_id": "E9",
        "unknown_type_id": "E10",
        "no_conversation_id": "E15",
        "unresolvable_context_id": "E16",
        "stale_session_id": "E12",
        "full_history_id": "E11",
        "client_prefix": {"query": "ישר", "expected": ["ישראל ישראלי", "ישראל כהן"]},
        "anchor_event": {
            "id": "E1", "lookback_10": ["M0", "M1", "M2", "M3", "M4"],
            "lookback_5": ["M2", "M3", "M4"],
        },
    }


def build_empty(root: Path) -> dict:
    """A data root whose only events are far outside any sane trailing window — used for the
    'zero events in window' empty-state cases."""
    b = Builder(root)
    old = b.day(500, 12, 0)
    b.event("Z1", source_type="הסכם", event_subtype="יצירה", client_name="ארכיון",
            amount=1, description="ישן מאוד", event_date=_ddmmyyyy(old), event_time="12:00")
    return {"password": PASSWORD, "root": str(root)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", dest="do_print")
    args = ap.parse_args()

    if FIXTURE_ROOT.exists():
        shutil.rmtree(FIXTURE_ROOT)
    FIXTURE_ROOT.mkdir(parents=True)

    full = build_full(FIXTURE_ROOT / "full")
    empty = build_empty(FIXTURE_ROOT / "empty")

    manifest = {"full": full, "empty": empty}
    (FIXTURE_ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # backend config files (one per root)
    for name in ("full", "empty"):
        cfg = {
            "environment": "test",
            "denidin_data_root": str(FIXTURE_ROOT / name),
            "denidin_src_path": "",
            "password_hash_file": str(FIXTURE_ROOT / name / "auth" / "password.hash"),
            "session_expiry_hours": 168,
            "http": {"host": "127.0.0.1",
                     "port": 8130 if name == "full" else 8131, "log_level": "WARNING"},
        }
        (FIXTURE_ROOT / f"config.{name}.json").write_text(
            json.dumps(cfg, indent=2), encoding="utf-8"
        )

    print(f"seeded {FIXTURE_ROOT}", file=sys.stderr)
    if args.do_print:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
