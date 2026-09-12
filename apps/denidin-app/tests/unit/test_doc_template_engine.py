"""
Unit tests for DocTemplateEngine (Feature 083).

Uses the REAL committed templates under config/fee_agreement_templates/ and
real python-docx calls - no mocking of internal code, per CONSTITUTION §I/§V.
"""

from pathlib import Path

import pytest

from src.managers.doc_template_engine import DocTemplateEngine

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "config" / "fee_agreement_templates"


@pytest.fixture
def engine(tmp_path):
    return DocTemplateEngine(templates_dir=TEMPLATES_DIR, tmp_dir=tmp_path / "fee_agreements")


class TestListVariants:
    def test_lists_all_five_variants(self, engine):
        variant_ids = {v.variant_id for v in engine.list_variants()}
        assert variant_ids == {
            "hourly_consultation",
            "retainer_agreement",
            "fixed_price_project",
            "multi_component_agreement",
            "alternative_tracks",
        }

    def test_multi_component_has_repeating_group(self, engine):
        variants = {v.variant_id: v for v in engine.list_variants()}
        rg = variants["multi_component_agreement"].repeating_group
        assert rg is not None
        assert rg.min_items == 2
        assert rg.row_placeholders == ["COMPONENT_LABEL", "COMPONENT_TERMS"]
        assert len(rg.example_terms) >= 1

    def test_single_fee_variant_has_no_repeating_group(self, engine):
        variants = {v.variant_id: v for v in engine.list_variants()}
        assert variants["hourly_consultation"].repeating_group is None


class TestGenerateSingleFeeVariant:
    def test_fills_all_placeholders(self, engine):
        values = {
            "FIRM_NAME": "אילה הוניגמן עריכת דין",
            "DATE": "12.9.2026",
            "CLIENT_NAME": "ישראל ישראלי",
            "SCOPE_OF_WORK": "בתביעה נגד מדינת ישראל",
            "HOURLY_RATE": "600",
            "FEE_AMOUNT": "15,000",
        }
        doc = engine.generate("hourly_consultation", values)

        assert doc.temp_path.exists()
        result = engine.verify(doc)
        assert result["remaining_placeholders"] == []
        assert result["missing_values"] == []
        assert result["clean"] is True
        for value in values.values():
            assert value in result["extracted_text"]

    def test_missing_placeholder_value_raises(self, engine):
        with pytest.raises(ValueError, match="missing"):
            engine.generate("hourly_consultation", {"FIRM_NAME": "X"})

    def test_extra_placeholder_value_raises(self, engine):
        values = {
            "FIRM_NAME": "X", "DATE": "1.1.2026", "CLIENT_NAME": "Y",
            "SCOPE_OF_WORK": "Z", "HOURLY_RATE": "1", "FEE_AMOUNT": "1",
            "UNEXPECTED": "nope",
        }
        with pytest.raises(ValueError, match="extra"):
            engine.generate("hourly_consultation", values)

    def test_empty_value_raises(self, engine):
        values = {
            "FIRM_NAME": "X", "DATE": "1.1.2026", "CLIENT_NAME": "Y",
            "SCOPE_OF_WORK": "Z", "HOURLY_RATE": "1", "FEE_AMOUNT": "   ",
        }
        with pytest.raises(ValueError, match="non-empty"):
            engine.generate("hourly_consultation", values)

    def test_unknown_variant_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown"):
            engine.generate("no_such_variant", {})

    def test_components_supplied_for_single_fee_variant_raises(self, engine):
        values = {
            "FIRM_NAME": "X", "DATE": "1.1.2026", "CLIENT_NAME": "Y",
            "SCOPE_OF_WORK": "Z", "HOURLY_RATE": "1", "FEE_AMOUNT": "1",
        }
        with pytest.raises(ValueError, match="no repeating_group"):
            engine.generate("hourly_consultation", values, components=[
                {"label": "a", "terms": "b"}, {"label": "c", "terms": "d"},
            ])


class TestGenerateMultiComponentAgreement:
    BASE_VALUES = {
        "FIRM_NAME": "משרד עורכי דין",
        "DATE": "12.9.2026",
        "CLIENT_NAME": "חברת דלתא בע\"מ",
        "SCOPE_OF_WORK": "בהסכם מסחרי",
        "TOTAL_FEE": "25,000",
    }

    def test_any_n_components_cloned(self, engine):
        components = [
            {"label": "שלב הכנה", "terms": "10,000 ₪ כולל מע\"מ."},
            {"label": "שלב דיון", "terms": "8,000 ₪ כולל מע\"מ."},
            {"label": "שלב פסק דין", "terms": "7,000 ₪ כולל מע\"מ, עד לתקרה של 10 שעות."},
        ]
        doc = engine.generate("multi_component_agreement", self.BASE_VALUES, components=components)
        result = engine.verify(doc)

        assert result["clean"] is True
        for entry in components:
            assert entry["label"] in result["extracted_text"]
            assert entry["terms"] in result["extracted_text"]

    def test_below_min_items_raises(self, engine):
        with pytest.raises(ValueError, match="at least 2"):
            engine.generate(
                "multi_component_agreement", self.BASE_VALUES,
                components=[{"label": "only one", "terms": "x"}],
            )

    def test_missing_components_raises(self, engine):
        with pytest.raises(ValueError, match="at least 2"):
            engine.generate("multi_component_agreement", self.BASE_VALUES, components=None)

    def test_malformed_component_entry_raises(self, engine):
        with pytest.raises(ValueError, match="exactly keys"):
            engine.generate(
                "multi_component_agreement", self.BASE_VALUES,
                components=[
                    {"label": "a", "terms": "b"},
                    {"label": "c", "fee": "d"},
                ],
            )


class TestGenerateAlternativeTracks:
    BASE_VALUES = {
        "FIRM_NAME": "משרד עורכי דין",
        "DATE": "12.9.2026",
        "CLIENT_NAME": "מר ישראלי",
        "SCOPE_OF_WORK": "בתביעה כספית",
        "SHARED_ADDON_TERMS": "אין תוספות החלות על שני המסלולים.",
    }

    def test_two_tracks_cloned(self, engine):
        tracks = [
            {"label": "מסלול א' - שכר טרחה קבוע", "terms": "18,000 ₪ כולל מע\"מ."},
            {"label": "מסלול ב' - הצלחה", "terms": "10,000 ₪ + 7% מהסכום שנפסק."},
        ]
        doc = engine.generate("alternative_tracks", self.BASE_VALUES, components=tracks)
        result = engine.verify(doc)

        assert result["clean"] is True
        for track in tracks:
            assert track["label"] in result["extracted_text"]
            assert track["terms"] in result["extracted_text"]
        assert self.BASE_VALUES["SHARED_ADDON_TERMS"] in result["extracted_text"]

    def test_three_tracks_supported(self, engine):
        tracks = [
            {"label": f"מסלול {i}", "terms": f"תנאי מסלול {i}"} for i in range(3)
        ]
        doc = engine.generate("alternative_tracks", self.BASE_VALUES, components=tracks)
        result = engine.verify(doc)
        assert result["clean"] is True

    def test_below_min_items_raises(self, engine):
        with pytest.raises(ValueError, match="at least 2"):
            engine.generate(
                "alternative_tracks", self.BASE_VALUES,
                components=[{"label": "only track", "terms": "x"}],
            )
