"""
Fee agreement document generation models (Feature 083).

FeeAgreementVariant is config, not persisted state - loaded from
config/fee_agreement_templates/manifest.json (see data-model.md). GeneratedDocument
is an in-memory, single-turn value scoped to one generate -> verify -> send
tool-call chain - never persisted to disk as a record (only the .docx file
itself briefly exists on disk, under {data_root}/tmp/fee_agreements/).
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class RepeatingGroup:
    """Declares that a variant's template has exactly one repeatable block
    (a table row for multi_component_agreement; a heading+paragraph block for
    alternative_tracks), cloned once per entry in a tool call's `components`
    list. See data-model.md's "Variable-length component rows" / "Alternative
    fee tracks" sections."""

    min_items: int
    row_placeholders: List[str]
    example_terms: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict) -> "RepeatingGroup":
        return cls(
            min_items=int(data["min_items"]),
            row_placeholders=list(data["row_placeholders"]),
            example_terms=list(data.get("example_terms", [])),
        )


@dataclass
class FeeAgreementVariant:
    """One entry from manifest.json. Read-only config, not persisted state."""

    variant_id: str
    template_filename: str
    placeholders: List[str]
    selection_cues: List[str] = field(default_factory=list)
    repeating_group: Optional[RepeatingGroup] = None
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> "FeeAgreementVariant":
        rg = data.get("repeating_group")
        return cls(
            variant_id=data["variant_id"],
            template_filename=data["template_filename"],
            placeholders=list(data.get("placeholders", [])),
            selection_cues=list(data.get("selection_cues", [])),
            repeating_group=RepeatingGroup.from_dict(rg) if rg else None,
            notes=data.get("notes", ""),
        )


@dataclass
class GeneratedDocument:
    """Represents one fee agreement generation attempt within a single turn's
    tool-call chain. Not a database row, not persisted to disk as a record -
    scoped to one turn's in-memory tool-call chain (see data-model.md)."""

    document_id: str
    variant_id: str
    values: Dict[str, str]
    temp_path: Path
    created_at: datetime
    components: Optional[List[Dict[str, str]]] = None
    verified: bool = False
    sent: bool = False
