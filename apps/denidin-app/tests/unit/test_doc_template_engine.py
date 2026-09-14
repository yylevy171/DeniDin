"""
Unit tests for DocTemplateEngine (Feature 083).

Uses the REAL committed templates under config/fee_agreement_templates/ and
real python-docx calls - no mocking of internal code, per CONSTITUTION §I/§V.
"""

from pathlib import Path

import pytest
from docx import Document as DocxDocument
from docx.oxml.ns import qn

from src.managers.doc_template_engine import DocTemplateEngine

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "config" / "fee_agreement_templates"


@pytest.fixture
def engine(tmp_path):
    return DocTemplateEngine(templates_dir=TEMPLATES_DIR, tmp_dir=tmp_path / "fee_agreements")


class TestListVariants:
    def test_lists_all_three_variants(self, engine):
        # 2026-09-14: fixed_price_project folded into multi_component_agreement
        # (a single flat fee is now just one component); retainer_agreement
        # removed entirely (no real example ever existed for it in the actual
        # fee-agreement corpus) - see config/fee_agreement_templates/examples/README.md.
        variant_ids = {v.variant_id for v in engine.list_variants()}
        assert variant_ids == {
            "hourly_consultation",
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
            "DATE": "12.9.2026",
            "CLIENT_NAME": "ישראל ישראלי",
            "SCOPE_OF_WORK": "בתביעה נגד מדינת ישראל",
            "HOURLY_RATE": "600 ₪ כולל מע\"מ",
            "FEE_AMOUNT": "15,000 ₪ כולל מע\"מ",
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
            engine.generate("hourly_consultation", {"DATE": "1.1.2026"})

    def test_extra_placeholder_value_raises(self, engine):
        values = {
            "DATE": "1.1.2026", "CLIENT_NAME": "Y",
            "SCOPE_OF_WORK": "Z", "HOURLY_RATE": "1", "FEE_AMOUNT": "1",
            # FIRM_NAME is a fixed template constant, never an AI-supplied
            # value (2026-09-13) - supplying it is now itself an "extra" case.
            "FIRM_NAME": "nope",
        }
        with pytest.raises(ValueError, match="extra"):
            engine.generate("hourly_consultation", values)

    def test_empty_value_raises(self, engine):
        values = {
            "DATE": "1.1.2026", "CLIENT_NAME": "Y",
            "SCOPE_OF_WORK": "Z", "HOURLY_RATE": "1", "FEE_AMOUNT": "   ",
        }
        with pytest.raises(ValueError, match="non-empty"):
            engine.generate("hourly_consultation", values)

    def test_unknown_variant_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown"):
            engine.generate("no_such_variant", {})

    def test_components_supplied_for_single_fee_variant_raises(self, engine):
        values = {
            "DATE": "1.1.2026", "CLIENT_NAME": "Y",
            "SCOPE_OF_WORK": "Z", "HOURLY_RATE": "1", "FEE_AMOUNT": "1",
        }
        with pytest.raises(ValueError, match="no repeating_group"):
            engine.generate("hourly_consultation", values, components=[
                {"label": "a", "terms": "b"}, {"label": "c", "terms": "d"},
            ])


class TestGenerateMultiComponentAgreement:
    BASE_VALUES = {
        "DATE": "12.9.2026",
        "CLIENT_NAME": "חברת דלתא בע\"מ",
        "SCOPE_OF_WORK": "בהסכם מסחרי",
        "TOTAL_FEE": "25,000 ₪ כולל מע\"מ",
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


class TestGetReferenceMaterials:
    """2026-09-14 follow-up: get_fee_agreement_template now returns curated
    real-world examples + a directive alongside the template skeleton, not
    just the bare reference body - see doc_template_engine.py's own
    docstring for why one example alone is too thin a basis for the AI to
    reliably infer professional-grade phrasing from."""

    def test_variant_with_curated_examples_returns_them(self, engine):
        materials = engine.get_reference_materials("multi_component_agreement")
        assert materials["template_body"]
        assert len(materials["examples"]) >= 5
        assert materials["directive"]
        # Real examples, not the template's own placeholder skeleton.
        for example in materials["examples"]:
            assert "{{" not in example

    def test_alternative_tracks_has_curated_examples(self, engine):
        materials = engine.get_reference_materials("alternative_tracks")
        assert len(materials["examples"]) >= 1
        assert materials["directive"]

    def test_hourly_consultation_has_curated_examples(self, engine):
        materials = engine.get_reference_materials("hourly_consultation")
        assert len(materials["examples"]) >= 1
        assert materials["directive"]

    def test_unknown_variant_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown"):
            engine.get_reference_materials("no_such_variant")


class TestRenderFreeTextDocxFormatEssentials:
    """2026-09-14: these same shell/RTL/format checks previously existed ONLY
    in the billed acceptance tests (tests/billed/test_fee_agreement_generation_flow.py),
    which need a real OpenAI call to even reach - meaning nothing free/fast
    ever verified the actual .docx structure render_free_text() produces.
    render_free_text() takes body_text directly, so these checks belong here
    too, against fixed hardcoded input, with no AI involved at all.

    Deliberately duplicates (doesn't import) the billed file's assertion
    logic - unit tests should stand alone, and the fixed-input version here
    is simpler than the billed file's mock-capture plumbing."""

    # 2026-09-14: body_text is now ONLY the substantive content - the
    # title/date/identity header and the signature footer are code-owned
    # (render_free_text injects them; see its own docstring) and are checked
    # separately below, never expected to appear inside body_text itself.
    CLIENT_NAME = "ישראל ישראלי"
    SAMPLE_BODY = (
        "## היקף השירות\n"
        "עבור ביצוע השירותים, ישלם הלקוח לעוה\"ד **שכר טרחה בסך 15,000 ₪ "
        "כולל מע\"מ**."
    )

    @pytest.mark.parametrize(
        "variant_id", ["hourly_consultation", "multi_component_agreement", "alternative_tracks"]
    )
    def test_logo_present_in_header(self, engine, variant_id):
        doc = engine.render_free_text(variant_id, self.CLIENT_NAME, self.SAMPLE_BODY)
        docx_obj = DocxDocument(str(doc.temp_path))
        header_part = docx_obj.sections[0].header.part
        assert any(rel.reltype.endswith("/image") for rel in header_part.rels.values()), (
            f"header logo image missing for variant {variant_id!r} - the branded "
            f"shell was not preserved by render_free_text()"
        )

    @pytest.mark.parametrize(
        "variant_id", ["hourly_consultation", "multi_component_agreement", "alternative_tracks"]
    )
    def test_footer_contact_line_present(self, engine, variant_id):
        doc = engine.render_free_text(variant_id, self.CLIENT_NAME, self.SAMPLE_BODY)
        docx_obj = DocxDocument(str(doc.temp_path))
        footer_text = "\n".join(p.text for p in docx_obj.sections[0].footer.paragraphs)
        assert "honigman-law.com" in footer_text, (
            f"footer contact line missing/altered for variant {variant_id!r}: {footer_text!r}"
        )

    @pytest.mark.parametrize(
        "variant_id", ["hourly_consultation", "multi_component_agreement", "alternative_tracks"]
    )
    def test_every_body_paragraph_is_rtl_and_never_regresses_paragraph_level_bidi(
        self, engine, variant_id
    ):
        """The exact recipe confirmed (2026-09-13, by diffing a real
        human-verified-working .docx) to actually render right-to-left in
        real Word: <w:rtl/> on the paragraph mark AND on the run. jc itself
        may be "right" (the default), "center" (the title/"לבין" line), or
        "both" (justified body paragraphs, 2026-09-14 visual-fidelity fix,
        matched against the real reference corpus) - all are RTL-safe
        alignments, and NO OTHER value (e.g. "left") may ever appear.

        Paragraph-level <w:bidi/> is scoped exactly to jc="both" paragraphs,
        never any other alignment (2026-09-14, two related but opposite
        findings from two separate real-rendering checks): jc="right"/
        "center" WITH <w:bidi/> was proven, by diffing a real
        human-verified-working .docx, to break real Word's rendering - so it
        must never appear there. jc="both" WITHOUT <w:bidi/> was separately
        proven, via a real rendered screenshot, to render a short/single-line
        justified paragraph flush LEFT instead of right (a real visual bug,
        not a cosmetic nit) - so <w:bidi/> is REQUIRED there. Both directions
        of this rule must hold, every time."""
        doc = engine.render_free_text(variant_id, self.CLIENT_NAME, self.SAMPLE_BODY)
        docx_obj = DocxDocument(str(doc.temp_path))
        body_paragraphs = [p for p in docx_obj.paragraphs if p.text.strip()]
        assert body_paragraphs, "expected at least one non-empty body paragraph"
        for para in body_paragraphs:
            pPr = para._p.find(qn('w:pPr'))
            assert pPr is not None, f"paragraph has no pPr: {para.text!r}"
            jc = pPr.find(qn('w:jc'))
            jc_val = jc.get(qn('w:val')) if jc is not None else None
            assert jc_val in ('right', 'center', 'both'), (
                f"paragraph alignment is not right/center/both (RTL-safe): "
                f"{jc_val!r} for {para.text!r}"
            )
            mark_rPr = pPr.find(qn('w:rPr'))
            assert mark_rPr is not None and mark_rPr.find(qn('w:rtl')) is not None, (
                f"paragraph mark is not RTL: {para.text!r}"
            )
            for run in para.runs:
                if not run.text.strip():
                    continue
                run_rPr = run._r.find(qn('w:rPr'))
                assert run_rPr is not None and run_rPr.find(qn('w:rtl')) is not None, (
                    f"run text is not RTL: {run.text!r}"
                )
            has_bidi = pPr.find(qn('w:bidi')) is not None
            if jc_val == 'both':
                assert has_bidi, (
                    f"justified (jc=both) paragraph is missing <w:bidi/> - "
                    f"real rendering shows this as flush-LEFT, not right: {para.text!r}"
                )
            else:
                assert not has_bidi, (
                    f"paragraph-level <w:bidi/> present on a non-justified "
                    f"({jc_val!r}) paragraph - the confirmed real-Word "
                    f"RTL-rendering bug this feature fixed, must never regress: "
                    f"{para.text!r}"
                )

    @pytest.mark.parametrize(
        "variant_id", ["hourly_consultation", "multi_component_agreement", "alternative_tracks"]
    )
    def test_every_body_paragraph_uses_one_point_five_line_spacing(
        self, engine, variant_id
    ):
        """2026-09-14, explicit human instruction: single ("tight") line
        spacing made a real rendered document look visibly crowded. Every
        paragraph must use 1.5 line spacing (w:line="360" at
        lineRule="auto", where 240 is single) - checked directly on the
        rendered .docx, not just eyeballed off a screenshot."""
        doc = engine.render_free_text(variant_id, self.CLIENT_NAME, self.SAMPLE_BODY)
        docx_obj = DocxDocument(str(doc.temp_path))
        body_paragraphs = [p for p in docx_obj.paragraphs if p.text.strip()]
        assert body_paragraphs, "expected at least one non-empty body paragraph"
        for para in body_paragraphs:
            pPr = para._p.find(qn('w:pPr'))
            spacing = pPr.find(qn('w:spacing')) if pPr is not None else None
            assert spacing is not None, f"paragraph has no w:spacing: {para.text!r}"
            assert spacing.get(qn('w:line')) == '360', (
                f"paragraph is not 1.5-line-spaced (w:line={spacing.get(qn('w:line'))!r}, "
                f"expected '360'): {para.text!r}"
            )
            assert spacing.get(qn('w:lineRule')) == 'auto', (
                f"paragraph lineRule is not 'auto': {para.text!r}"
            )

    @pytest.mark.parametrize(
        "variant_id", ["hourly_consultation", "multi_component_agreement", "alternative_tracks"]
    )
    def test_header_block_alignment(self, engine, variant_id):
        """2026-09-14 fix: the "לבין" line (between the client and the firm
        in the code-injected header) was previously centered, inconsistent
        with the party/firm lines around it and with the rest of the
        document. The ONLY centered paragraph in the whole document must be
        the title itself - "לבין" and every other header line render
        right-aligned like the rest of the document."""
        doc = engine.render_free_text(variant_id, self.CLIENT_NAME, self.SAMPLE_BODY)
        docx_obj = DocxDocument(str(doc.temp_path))
        lavein_paragraphs = [p for p in docx_obj.paragraphs if p.text.strip() == "לבין"]
        assert lavein_paragraphs, "expected a \"לבין\" header line"
        for para in lavein_paragraphs:
            pPr = para._p.find(qn('w:pPr'))
            jc = pPr.find(qn('w:jc')) if pPr is not None else None
            assert jc is not None and jc.get(qn('w:val')) == 'right', (
                f"\"לבין\" line is not right-aligned (jc="
                f"{jc.get(qn('w:val')) if jc is not None else None!r})"
            )

        title_paragraphs = [p for p in docx_obj.paragraphs if p.text.strip() == engine._TITLE_TEXT]
        assert title_paragraphs, "expected the document title"
        centered = [
            p for p in docx_obj.paragraphs if p.text.strip()
            and (p._p.find(qn('w:pPr')) is not None)
            and (p._p.find(qn('w:pPr')).find(qn('w:jc')) is not None)
            and p._p.find(qn('w:pPr')).find(qn('w:jc')).get(qn('w:val')) == 'center'
        ]
        assert [p.text.strip() for p in centered] == [engine._TITLE_TEXT], (
            f"expected ONLY the title to be centered, got: "
            f"{[p.text.strip() for p in centered]!r}"
        )

    def test_body_text_lines_appear_verbatim_and_in_order(self, engine):
        """The AI's own substantive lines must appear, verbatim and in
        order, somewhere inside the full paragraph list - sandwiched between
        the code-owned header (title/date/identity) and footer (signature),
        which this test checks separately, not as an exact whole-document
        match (2026-09-14: body_text is no longer the entire document)."""
        doc = engine.render_free_text("hourly_consultation", self.CLIENT_NAME, self.SAMPLE_BODY)
        docx_obj = DocxDocument(str(doc.temp_path))
        actual_lines = [p.text for p in docx_obj.paragraphs]
        # "## " markup is stripped by render_free_text (it becomes a bold
        # heading, not literal text); "**" markers are stripped too (they
        # become bold runs, not literal asterisks) - compare against what
        # should actually appear on the page.
        expected_lines = [
            "היקף השירות",
            'עבור ביצוע השירותים, ישלם הלקוח לעוה"ד שכר טרחה בסך 15,000 ₪ כולל מע"מ.',
        ]
        # a contiguous subsequence, not necessarily the whole document
        joined_actual = "\n".join(actual_lines)
        joined_expected = "\n".join(expected_lines)
        assert joined_expected in joined_actual, (
            f"expected body lines to appear verbatim, in order, as a contiguous "
            f"block:\nexpected={joined_expected!r}\nactual document={actual_lines!r}"
        )

    def test_constant_boilerplate_is_code_injected_never_left_to_the_ai(self, engine):
        """2026-09-14 (explicit human instruction: "firm identity is "
        "CONSTANT! IT NEVER CHANGES!!") - the title, date, firm identity, and
        signature block must ALL be present regardless of what body_text
        says (this test's body_text never mentions any of them), because
        render_free_text() injects them itself. This is the regression the
        fix targets: a real billed run once had the AI write "המשרד" (the
        firm's own name is a fact only code/human can guarantee, never the
        model's memory)."""
        doc = engine.render_free_text(
            "hourly_consultation", self.CLIENT_NAME, self.SAMPLE_BODY
        )
        docx_obj = DocxDocument(str(doc.temp_path))
        text = "\n".join(p.text for p in docx_obj.paragraphs)
        assert "הסכם שכר טרחה" in text, f"code-owned title missing: {text!r}"
        assert self.CLIENT_NAME in text, f"client name missing: {text!r}"
        assert 'עו"ד אילה הוניגמן' in text, (
            f"code-owned firm identity missing - this must NEVER depend on "
            f"the AI remembering to write it: {text!r}"
        )
        assert "תאריך:" in text, f"code-owned date line missing: {text!r}"
        assert "חתימה:" in text, f"code-owned signature block missing: {text!r}"

    def test_bold_markup_produces_real_bold_runs(self, engine):
        """"## " headings and "**...**" spans (the AI's only formatting
        vocabulary - see render_free_text's docstring) must produce real
        <w:b/> runs, not literal "##"/"**" characters in the output."""
        doc = engine.render_free_text(
            "hourly_consultation", self.CLIENT_NAME, self.SAMPLE_BODY
        )
        docx_obj = DocxDocument(str(doc.temp_path))
        text = "\n".join(p.text for p in docx_obj.paragraphs)
        assert "##" not in text, f"literal '##' markup leaked into the text: {text!r}"
        assert "**" not in text, f"literal '**' markup leaked into the text: {text!r}"

        heading_para = next(p for p in docx_obj.paragraphs if p.text == "היקף השירות")
        assert any(run.bold for run in heading_para.runs), (
            "'## ' heading did not produce a bold run"
        )

        amount_para = next(p for p in docx_obj.paragraphs if "שכר טרחה בסך" in p.text)
        bold_runs = [r for r in amount_para.runs if r.bold and "15,000" in r.text]
        assert bold_runs, (
            f"'**...**' span around the amount did not produce a bold run: "
            f"{[(r.text, r.bold) for r in amount_para.runs]!r}"
        )
