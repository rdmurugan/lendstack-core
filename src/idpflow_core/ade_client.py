"""Thin wrapper over LandingAI Agentic Document Extraction (ADE).

ADE is a two-step pipeline (verified against docs.landing.ai):
  1. client.parse(document=...)  -> markdown + chunks[].grounding.{page, box{left,top,right,bottom}}
  2. client.extract(schema=..., markdown=...) -> extraction{values} + extraction_metadata{references}

We run both, then map each extracted field's `references` (chunk ids) back to the parse
chunks' grounding to attach page + bounding box provenance. ADE extract returns grounding
references rather than a numeric confidence, so groundedness is our primary audit signal:
ungrounded values are review-flagged.

If VISION_AGENT_API_KEY is unset, falls back to a deterministic STUB so the server runs
end-to-end in dev/CI without live API calls or cost.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import (
    BoundingBox,
    DocType,
    DocumentExtraction,
    ExtractedField,
    Provenance,
)
from .schemas import schema_for

REVIEW_THRESHOLD = float(os.getenv("CONFIDENCE_REVIEW_THRESHOLD", "0.85"))
PARSE_MODEL = os.getenv("ADE_PARSE_MODEL", "dpt-2-latest")
EXTRACT_MODEL = os.getenv("ADE_EXTRACT_MODEL", "extract-latest")


def _flag(fields: list[ExtractedField]) -> bool:
    """Set needs_review for ungrounded values or sub-threshold confidence."""
    for f in fields:
        low_conf = f.confidence is not None and f.confidence < REVIEW_THRESHOLD
        if not f.grounded or low_conf:
            f.needs_review = True
    return any(f.needs_review for f in fields)


class ADEClient:
    """Wraps the official `landingai-ade` library with graceful stub fallback.

    Auth: the library reads VISION_AGENT_API_KEY from the environment. We also accept
    LANDINGAI_API_KEY and mirror it into VISION_AGENT_API_KEY for convenience.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = (
            api_key or os.getenv("VISION_AGENT_API_KEY") or os.getenv("LANDINGAI_API_KEY")
        )
        self._client = None
        if self.api_key:
            os.environ.setdefault("VISION_AGENT_API_KEY", self.api_key)
            try:
                from landingai_ade import LandingAIADE  # type: ignore

                env = os.getenv("LANDINGAI_ENV")  # "eu" for EU endpoints
                self._client = LandingAIADE(environment=env) if env else LandingAIADE()
            except Exception:  # noqa: BLE001 - degrade to stub
                self._client = None

    @property
    def is_live(self) -> bool:
        return self._client is not None

    def extract(self, file_path: str, doc_type: DocType) -> DocumentExtraction:
        if self.is_live:
            return self._extract_live(file_path, doc_type)
        return self._extract_stub(file_path, doc_type)

    # --- live -------------------------------------------------------------
    def _extract_live(self, file_path: str, doc_type: DocType) -> DocumentExtraction:
        warnings: list[str] = []

        # Step 1: parse -> markdown + grounded chunks
        if file_path.startswith(("http://", "https://")):
            parsed = self._client.parse(document_url=file_path, model=PARSE_MODEL)  # type: ignore[union-attr]
        else:
            parsed = self._client.parse(document=Path(file_path), model=PARSE_MODEL)  # type: ignore[union-attr]

        # `parsed.grounding` is a dict keyed by BOTH chunk-UUIDs and table-cell ids
        # ("0-9", "0-5", ...). Extract `references` point at these ids, so we resolve
        # provenance + confidence through this map (NOT through `chunks`, which only
        # holds top-level chunk UUIDs). Pages are 0-indexed; we store 1-indexed.
        gmap: dict[str, tuple[Provenance, float | None]] = {}
        for gid, gobj in (getattr(parsed, "grounding", {}) or {}).items():
            box = getattr(gobj, "box", None)
            bbox = (
                BoundingBox(left=box.left, top=box.top, right=box.right, bottom=box.bottom)
                if box is not None
                else None
            )
            page0 = getattr(gobj, "page", 0)
            page = (page0 + 1) if isinstance(page0, int) else 1
            conf = getattr(gobj, "confidence", None)
            gmap[str(gid)] = (
                Provenance(page=page, bbox=bbox, source_doc_type=doc_type),
                float(conf) if conf is not None else None,
            )

        markdown = getattr(parsed, "markdown", None)
        meta = getattr(parsed, "metadata", None)
        page_count = int(getattr(meta, "page_count", 1) or 1) if meta else 1

        # Step 2: extract -> typed fields + references
        schema = json.dumps(schema_for(doc_type))
        extracted = self._client.extract(  # type: ignore[union-attr]
            schema=schema, markdown=markdown, model=EXTRACT_MODEL
        )

        values = getattr(extracted, "extraction", {}) or {}
        emeta = getattr(extracted, "extraction_metadata", {}) or {}
        emeta = emeta if isinstance(emeta, dict) else getattr(emeta, "__dict__", {})
        values = values if isinstance(values, dict) else getattr(values, "__dict__", {})

        ex_metadata = getattr(extracted, "metadata", None)
        if ex_metadata is not None:
            for w in getattr(ex_metadata, "warnings", []) or []:
                warnings.append(f"{getattr(w, 'code', 'warning')}: {getattr(w, 'msg', '')}")
            sve = getattr(ex_metadata, "schema_violation_error", None)
            if sve:
                warnings.append(f"schema_violation: {sve}")

        fields: list[ExtractedField] = []
        for name, value in values.items():
            field_meta = emeta.get(name) if isinstance(emeta, dict) else None
            refs = []
            if field_meta is not None:
                refs = (
                    field_meta.get("references", [])
                    if isinstance(field_meta, dict)
                    else getattr(field_meta, "references", [])
                ) or []
            refs = [str(r) for r in refs]
            resolved = next(((p, c) for r in refs if (m := gmap.get(r)) for (p, c) in [m]), None)
            prov, conf = resolved if resolved else (None, None)
            fields.append(
                ExtractedField(
                    name=name,
                    value=None if value is None else str(value),
                    grounded=prov is not None,
                    references=refs,
                    confidence=conf,
                    provenance=prov
                    or Provenance(page=1, bbox=None, source_doc_type=doc_type),
                )
            )

        review = _flag(fields)
        confs = [f.confidence for f in fields if f.confidence is not None]
        overall = (
            round(sum(confs) / len(confs), 4)
            if confs
            else (round(sum(f.grounded for f in fields) / len(fields), 4) if fields else 0.0)
        )
        return DocumentExtraction(
            doc_type=doc_type,
            page_count=page_count,
            overall_confidence=overall,
            fields=fields,
            raw_markdown=markdown,
            review_required=review,
            warnings=warnings,
        )

    # --- stub -------------------------------------------------------------
    def _extract_stub(self, file_path: str, doc_type: DocType) -> DocumentExtraction:
        # (name, value, grounded, confidence-proxy)
        samples: dict[DocType, list[tuple[str, str, bool]]] = {
            DocType.PAYSTUB: [
                ("borrower.gross_pay_period", "3,250.00", True),
                ("borrower.pay_frequency", "biweekly", True),
                ("borrower.ytd_gross", "42,250.00", True),
                ("employer.name", "Acme Logistics LLC", True),
            ],
            DocType.W2: [
                ("borrower.wages_box1", "78,000.00", True),
                ("employer.ein", "12-3456789", True),
                ("tax_year", "2025", True),
            ],
            DocType.URLA_1003: [
                ("borrower.declared_monthly_income", "6,500.00", True),
                ("loan.amount", "320,000.00", True),
                ("property.value", "400,000.00", True),
                ("loan.purpose", "purchase", True),
            ],
            DocType.BANK_STATEMENT: [
                ("account.ending_balance", "18,420.11", True),
                ("account.holder", "Jane Q Borrower", False),  # ungrounded -> review
            ],
        }
        rows = samples.get(doc_type, [("document.detected_type", doc_type.value, True)])
        fields = [
            ExtractedField(
                name=n,
                value=v,
                grounded=g,
                references=[f"stub-chunk-{i}"] if g else [],
                confidence=None,
                provenance=Provenance(page=1, bbox=None, source_doc_type=doc_type),
            )
            for i, (n, v, g) in enumerate(rows)
        ]
        review = _flag(fields)
        grounded_ratio = round(sum(1 for f in fields if f.grounded) / len(fields), 4)
        return DocumentExtraction(
            doc_type=doc_type,
            page_count=1,
            overall_confidence=grounded_ratio,
            fields=fields,
            raw_markdown=f"# (STUB) {doc_type.value}\nSet VISION_AGENT_API_KEY for live extraction.",
            review_required=review,
            warnings=["STUB MODE: no API key set; values are synthetic."],
        )
