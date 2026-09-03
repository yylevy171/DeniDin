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
        analysis = {
            "event_subtype": "הפקדה",
            "amount": "9,440₪",
            "txn_date": "12/07/2026",
            "bank_number": "12",
            "bank_branch": "345",
            "bank_account": "678901",
            "client_name": "דנה לולו",
        }
        stash = build_ledger_stash_text(
            "אישור העברה בנקאית\nסכום: 9,440 ₪", analysis, "בנק", source_medium="image"
        )
        assert stash.startswith("📸 התקבלה תמונה של אסמכתת העברה/הפקדה בנקאית.")
        assert "סכום: 9,440₪" in stash
        assert "מספר סניף: 345" in stash
        assert "שם על האסמכתא: דנה לולו" in stash
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
