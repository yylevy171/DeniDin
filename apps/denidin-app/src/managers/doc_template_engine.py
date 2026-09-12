"""
DocTemplateEngine - Fee Agreement Document Generation (Feature 083).

Fills a .docx template variant's placeholders with AI-supplied values and
writes a temporary output file, without ever inventing a value the AI did not
explicitly provide (REQ-083-02). See
specs/repo/features/083-fee-agreement-docs/contracts/doc-template-engine.md
for the full contract this class implements.

Uses python-docx for both loading/replacing (generation direction) and
read-back (verification direction) - the same library DOCXExtractor already
depends on for the reverse (extraction) direction, per research.md #6.
"""

import copy
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from docx import Document

from src.models.fee_agreement import FeeAgreementVariant, GeneratedDocument
from src.utils.logger import get_logger
from src.utils.time_utils import now_local

logger = get_logger(__name__)

PLACEHOLDER_PATTERN = re.compile(r"\{\{[A-Z_]+\}\}")


class DocTemplateEngine:
    """Loads fee agreement template variants and fills them with AI-supplied
    values. Never guesses/defaults a missing value - every validation failure
    is raised as a ValueError so the caller (ai_handler.py's tool dispatch)
    can surface it back to the model as a tool-call error, per contract."""

    def __init__(self, templates_dir: Path, tmp_dir: Path) -> None:
        self.templates_dir = Path(templates_dir)
        self.tmp_dir = Path(tmp_dir)
        self._variants: Optional[Dict[str, FeeAgreementVariant]] = None

    def list_variants(self) -> List[FeeAgreementVariant]:
        """Loads/returns manifest.json's variants. Read-only; no side effects."""
        return list(self._load_variants().values())

    def _load_variants(self) -> Dict[str, FeeAgreementVariant]:
        if self._variants is None:
            manifest_path = self.templates_dir / "manifest.json"
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            self._variants = {
                v["variant_id"]: FeeAgreementVariant.from_dict(v)
                for v in manifest["variants"]
            }
        return self._variants

    def _get_variant(self, variant_id: str) -> FeeAgreementVariant:
        variants = self._load_variants()
        if variant_id not in variants:
            raise ValueError(
                f"Unknown fee agreement variant_id: {variant_id!r}. "
                f"Known variants: {sorted(variants.keys())}"
            )
        return variants[variant_id]

    def generate(
        self,
        variant_id: str,
        values: Dict[str, str],
        components: Optional[List[Dict[str, str]]] = None,
    ) -> GeneratedDocument:
        variant = self._get_variant(variant_id)
        self._validate_values(variant, values)
        self._validate_components(variant, components)

        doc = Document(str(self.templates_dir / variant.template_filename))
        self._replace_scalar_placeholders(doc, values)
        if variant.repeating_group is not None:
            self._clone_repeating_group(doc, variant.repeating_group, components or [])

        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        document_id = str(uuid.uuid4())
        temp_path = self.tmp_dir / f"{document_id}.docx"
        doc.save(str(temp_path))

        return GeneratedDocument(
            document_id=document_id,
            variant_id=variant_id,
            values=dict(values),
            temp_path=temp_path,
            created_at=now_local(),
            components=list(components) if components else None,
            verified=False,
            sent=False,
        )

    def verify(self, generated: GeneratedDocument) -> Dict[str, Any]:
        """Reads the generated document back and reports whether it's clean.
        Returns the raw facts (extracted text, leftover placeholder tokens,
        which expected values were/weren't found verbatim) - the ACTUAL
        accept/reject judgment is the model's, per REQ-083-04. This method
        never itself decides pass/fail."""
        doc = Document(str(generated.temp_path))
        full_text = self._extract_full_text(doc)

        remaining_placeholders = sorted(set(PLACEHOLDER_PATTERN.findall(full_text)))

        expected_values = list(generated.values.values())
        if generated.components:
            for entry in generated.components:
                expected_values.extend(entry.values())

        missing_values = [v for v in expected_values if v.strip() and v not in full_text]

        return {
            "document_id": generated.document_id,
            "extracted_text": full_text,
            "remaining_placeholders": remaining_placeholders,
            "missing_values": missing_values,
            "clean": not remaining_placeholders and not missing_values,
        }

    # -- validation -----------------------------------------------------

    @staticmethod
    def _validate_values(variant: FeeAgreementVariant, values: Dict[str, str]) -> None:
        expected = set(variant.placeholders)
        got = set(values.keys())
        if got != expected:
            missing = expected - got
            extra = got - expected
            raise ValueError(
                f"values keys mismatch for variant {variant.variant_id!r}: "
                f"missing={sorted(missing)} extra={sorted(extra)}"
            )
        for key, value in values.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"values[{key!r}] must be a non-empty string for variant "
                    f"{variant.variant_id!r} (REQ-083-02: empty is not a legitimate answer)"
                )

    @staticmethod
    def _validate_components(
        variant: FeeAgreementVariant, components: Optional[List[Dict[str, str]]]
    ) -> None:
        rg = variant.repeating_group
        if rg is None:
            if components is not None:
                raise ValueError(
                    f"variant {variant.variant_id!r} has no repeating_group - "
                    f"`components` must not be supplied"
                )
            return

        if not components or len(components) < rg.min_items:
            raise ValueError(
                f"variant {variant.variant_id!r} requires a `components` list of at "
                f"least {rg.min_items} entries; got "
                f"{0 if not components else len(components)}"
            )
        expected_keys = set(rg.row_placeholders)
        # components entries use lowercase tool-schema keys (label/terms) mapped
        # 1:1 in order onto row_placeholders (e.g. COMPONENT_LABEL/COMPONENT_TERMS,
        # TRACK_LABEL/TRACK_TERMS) - the tool schema always uses {label, terms}.
        for entry in components:
            if set(entry.keys()) != {"label", "terms"}:
                raise ValueError(
                    f"each components entry for variant {variant.variant_id!r} must have "
                    f"exactly keys 'label' and 'terms'; got {sorted(entry.keys())}"
                )
            for key in ("label", "terms"):
                if not isinstance(entry[key], str) or not entry[key].strip():
                    raise ValueError(
                        f"components entry {key!r} must be a non-empty string "
                        f"(REQ-083-02: empty is not a legitimate answer)"
                    )
        del expected_keys  # documents the row_placeholders <-> label/terms mapping above

    # -- replacement ------------------------------------------------------

    @staticmethod
    def _iter_all_paragraphs(doc: Document):
        for p in doc.paragraphs:
            yield p
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        yield p

    def _replace_scalar_placeholders(self, doc: Document, values: Dict[str, str]) -> None:
        for paragraph in self._iter_all_paragraphs(doc):
            for run in paragraph.runs:
                for key, value in values.items():
                    token = "{{" + key + "}}"
                    if token in run.text:
                        run.text = run.text.replace(token, value)

    def _clone_repeating_group(self, doc: Document, rg, components: List[Dict[str, str]]) -> None:
        label_token = "{{" + rg.row_placeholders[0] + "}}"
        terms_token = "{{" + rg.row_placeholders[1] + "}}"

        table_row = self._find_template_table_row(doc, label_token)
        if table_row is not None:
            self._clone_table_row(table_row, label_token, terms_token, components)
            return

        para_pair = self._find_template_paragraph_pair(doc, label_token, terms_token)
        if para_pair is not None:
            self._clone_paragraph_pair(para_pair, label_token, terms_token, components)
            return

        raise ValueError(
            f"template for a repeating_group variant does not contain a template "
            f"row/block with placeholders {label_token}/{terms_token}"
        )

    @staticmethod
    def _find_template_table_row(doc: Document, label_token: str):
        for table in doc.tables:
            for row in table.rows:
                row_text = "".join(cell.text for cell in row.cells)
                if label_token in row_text:
                    return row
        return None

    @staticmethod
    def _clone_table_row(template_row, label_token: str, terms_token: str, components):
        template_tr = template_row._tr
        for entry in components:
            new_tr = copy.deepcopy(template_tr)
            DocTemplateEngine._replace_in_xml_element(new_tr, label_token, entry["label"])
            DocTemplateEngine._replace_in_xml_element(new_tr, terms_token, entry["terms"])
            template_tr.addprevious(new_tr)
        template_tr.getparent().remove(template_tr)

    @staticmethod
    def _find_template_paragraph_pair(doc: Document, label_token: str, terms_token: str):
        paragraphs = doc.paragraphs
        for i, p in enumerate(paragraphs):
            if label_token in p.text and i + 1 < len(paragraphs) and terms_token in paragraphs[i + 1].text:
                return paragraphs[i], paragraphs[i + 1]
        return None

    @staticmethod
    def _clone_paragraph_pair(pair, label_token: str, terms_token: str, components):
        label_p, terms_p = pair
        label_el, terms_el = label_p._p, terms_p._p
        for entry in components:
            new_label_el = copy.deepcopy(label_el)
            new_terms_el = copy.deepcopy(terms_el)
            DocTemplateEngine._replace_in_xml_element(new_label_el, label_token, entry["label"])
            DocTemplateEngine._replace_in_xml_element(new_terms_el, terms_token, entry["terms"])
            label_el.addprevious(new_label_el)
            label_el.addprevious(new_terms_el)
        label_el.getparent().remove(label_el)
        terms_el.getparent().remove(terms_el)

    @staticmethod
    def _replace_in_xml_element(element, token: str, value: str) -> None:
        # Text runs live at w:r/w:t under the (possibly deepcopy'd) w:tr/w:p element.
        from docx.oxml.ns import qn

        for t in element.iter(qn("w:t")):
            if t.text and token in t.text:
                t.text = t.text.replace(token, value)

    @staticmethod
    def _extract_full_text(doc: Document) -> str:
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    parts.append(cell.text)
        return "\n".join(parts)
