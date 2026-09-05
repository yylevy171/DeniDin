"""T023a (Feature 069, Phase 9): `build_ledger_stash_text` renders a media
extractor's ledger analysis + the verbatim extracted text into one structured
Hebrew stash block that a synthetic conversational turn carries as its
text_content.

Pure function, no OpenAI, no I/O - unit tier, no approval needed.
"""
import pytest

from src.handlers.ai_handler import build_ledger_stash_text, _STASH_MISSING


class TestBuildLedgerStashText:
    def test_bank_image_stash_has_header_fields_and_verbatim_frame(self):
        # Real shape from capture_ledger_events_from_text: amount / txn_date are
        # nested on the single component, not top-level.
        analysis = {
            "event_subtype": "הפקדה",
            "bank_number": "12",
            "bank_branch": "345",
            "bank_account": "678901",
            "client_name": "דנה לולו",
            "component_count": 1,
            "components": [
                {"amount": "9,440₪", "txn_date": "12/07/2026", "vat_status": "לא צוין"}
            ],
        }
        stash = build_ledger_stash_text(
            "אישור העברה בנקאית\nסכום: 9,440 ₪", analysis, "בנק", source_medium="image"
        )
        assert stash.startswith("📸 התקבלה תמונה של אסמכתת העברה/הפקדה בנקאית.")
        assert "פעולה: הפקדה" in stash
        assert "סכום: 9,440₪" in stash
        assert "תאריך הפקדה: 12/07/2026" in stash
        assert "מספר סניף: 345" in stash
        assert "לקוח משלם: דנה לולו" in stash
        # dropped fields must not reappear
        assert "מטבע:" not in stash
        assert "מספר אסמכתא:" not in stash
        assert "תת-סוג:" not in stash
        assert "--- טקסט שחולץ מהתמונה (מילה במילה) ---" in stash
        assert "אישור העברה בנקאית" in stash

    def test_agreement_docx_stash_uses_document_header_and_frame(self):
        stash = build_ledger_stash_text(
            "הסכם שכר טרחה בין הצדדים...", None, "הסכם", source_medium="document"
        )
        assert stash.startswith("📄 התקבל קובץ מסמך (DOCX) של הסכם שכר טרחה.")
        assert "--- טקסט שחולץ מהמסמך (מילה במילה) ---" in stash
        assert "הסכם שכר טרחה בין הצדדים" in stash

    def test_agreement_image_renders_percent_and_fixed_components(self):
        analysis = {
            "client_name": "רון לוי",
            "components": [
                {"percent": "15%", "percent_base": "סכום הזכייה"},
                {"amount": "1,500", "currency": "שקל", "description": "מקדמה"},
            ],
        }
        stash = build_ledger_stash_text("...", analysis, "הסכם", source_medium="image")
        assert stash.startswith("📸 התקבלה תמונה של הסכם שכר טרחה.")
        assert "אחוז: 15% — סכום הזכייה" in stash
        assert "סכום קבוע: 1,500 שקל — מקדמה" in stash

    def test_missing_fields_render_as_placeholder(self):
        stash = build_ledger_stash_text(None, {}, "בנק")
        assert f"סכום: {_STASH_MISSING}" in stash
        # verbatim frame still present, body is the placeholder
        assert stash.rstrip().endswith(_STASH_MISSING)
