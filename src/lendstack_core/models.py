"""Pydantic models for lendstack-core.

Generic document-extraction + stacking models. EVERY extracted value carries grounding
(source references) and, where the parse step provides it, confidence + page/bbox — so
outputs are auditable. ADE's grounding is what makes this possible.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocType(str, Enum):
    """Document types recognized by the example schemas/profiles. Extend freely."""

    URLA_1003 = "urla_1003"
    W2 = "w2"
    PAYSTUB = "paystub"
    BANK_STATEMENT = "bank_statement"
    TAX_RETURN_1040 = "tax_return_1040"
    ID_DOCUMENT = "id_document"
    APPRAISAL = "appraisal"
    TITLE = "title"
    CLOSING_DISCLOSURE = "closing_disclosure"
    CREDIT_APPLICATION = "credit_application"
    CREDIT_REPORT = "credit_report"
    PROOF_OF_INSURANCE = "proof_of_insurance"
    PROOF_OF_RESIDENCE = "proof_of_residence"
    VEHICLE_DOC = "vehicle_doc"
    RETAIL_INSTALLMENT_CONTRACT = "retail_installment_contract"
    OTHER = "other"


class BoundingBox(BaseModel):
    """Normalized [0,1] coordinates of a value on its page (ADE visual grounding)."""

    left: float
    top: float
    right: float
    bottom: float


class Provenance(BaseModel):
    """Where a value came from — the audit trail."""

    page: int = Field(description="1-indexed page number the value was found on.")
    bbox: Optional[BoundingBox] = Field(default=None, description="Bounding box on the page.")
    source_doc_type: DocType = Field(description="Document type the value was extracted from.")


class ExtractedField(BaseModel):
    """A single extracted datum with grounding/provenance.

    ADE's extract step returns *references* (source chunk ids) per field rather than a numeric
    confidence; groundedness is the primary audit signal (an ungrounded value is review-flagged).
    `confidence` is populated when the grounding supplies one.
    """

    name: str
    value: Optional[str]
    grounded: bool = False
    references: list[str] = Field(default_factory=list)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    provenance: Optional[Provenance] = None
    needs_review: bool = False


class DocumentExtraction(BaseModel):
    doc_type: DocType
    page_count: int
    overall_confidence: float = Field(ge=0.0, le=1.0)
    fields: list[ExtractedField]
    raw_markdown: Optional[str] = None
    review_required: bool
    warnings: list[str] = Field(default_factory=list)


class MissingDoc(BaseModel):
    doc_type: DocType
    reason: str


class DocInput(BaseModel):
    """One document to process. doc_type is optional — if omitted, it is classified."""

    file_path: str
    doc_type: Optional[str] = None


class StackItem(BaseModel):
    position: int
    doc_type: DocType
    file_path: str
    in_profile: bool
    overall_confidence: Optional[float] = None
    review_required: bool = False


class StackResult(BaseModel):
    profile: str
    ordered_stack: list[StackItem]
    missing_docs: list[MissingDoc]
    is_complete: bool


class ClassifyResult(BaseModel):
    file_path: str
    doc_type: DocType
    method: str = Field(description="How the type was determined (hint | markdown | filename).")


class KeyField(BaseModel):
    name: str
    value: Optional[str]
    confidence: Optional[float]
    grounded: bool
    source_doc: DocType
    page: Optional[int]
    needs_review: bool


class DocumentPackage(BaseModel):
    """Documents stacked in order + extracted fields. Carries no decision."""

    package_id: str
    profile: str
    ordered_stack: list[StackItem]
    missing_docs: list[MissingDoc]
    is_complete: bool
    key_fields: list[KeyField]
    review_queue: list[KeyField] = Field(
        description="Ungrounded / low-confidence fields needing human verification."
    )
    summary: str


class RenderedPackage(BaseModel):
    """A rendered package: stacked PDF + JSON sidecar."""

    package_id: str
    pdf_path: str
    json_path: str
    page_count: int
    docs_embedded: int
    docs_not_embedded: list[str] = Field(default_factory=list)
    package: DocumentPackage
