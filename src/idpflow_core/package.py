"""Document-package orchestrator.

Pipeline:  ingest -> classify (if needed) -> extract (ADE) -> stack -> assemble.

Produces a DocumentPackage: documents stacked in the configured order, every extracted field
carried with confidence + page provenance, and a review queue of ungrounded/low-confidence
values. Document-source-agnostic: callers pass file paths from any source (upload portal,
watched SFTP/S3 folder, email intake, or an export). No vendor dependency.
"""

from __future__ import annotations

from .ade_client import ADEClient
from .classify import classify_document
from .models import DocInput, DocType, DocumentPackage, KeyField
from .stacking import stack_documents


def build_package(
    package_id: str,
    documents: list[DocInput],
    profile: str = "mortgage",
    custom_order: list[DocType] | None = None,
    client: ADEClient | None = None,
) -> DocumentPackage:
    client = client or ADEClient()

    typed: list[tuple[DocType, str]] = []
    key_fields: list[KeyField] = []
    extraction_quality: dict[str, float | None] = {}
    review_flags: dict[str, bool] = {}

    for doc in documents:
        cls = classify_document(doc.file_path, hint=doc.doc_type, client=client)
        dt = cls.doc_type
        typed.append((dt, doc.file_path))

        extraction = client.extract(doc.file_path, dt)
        extraction_quality[doc.file_path] = extraction.overall_confidence
        review_flags[doc.file_path] = extraction.review_required

        for f in extraction.fields:
            key_fields.append(
                KeyField(
                    name=f.name,
                    value=f.value,
                    confidence=f.confidence,
                    grounded=f.grounded,
                    source_doc=dt,
                    page=f.provenance.page if f.provenance else None,
                    needs_review=f.needs_review,
                )
            )

    stack = stack_documents(typed, profile=profile, custom_order=custom_order)
    for item in stack.ordered_stack:
        item.overall_confidence = extraction_quality.get(item.file_path)
        item.review_required = review_flags.get(item.file_path, False)

    review_queue = [k for k in key_fields if k.needs_review]
    summary = (
        f"Package {package_id} ({profile}): {len(stack.ordered_stack)} docs stacked, "
        f"{len(stack.missing_docs)} expected doc(s) missing, "
        f"{len(key_fields)} fields extracted, {len(review_queue)} flagged for review. "
        f"{'COMPLETE' if stack.is_complete else 'INCOMPLETE'}."
    )

    return DocumentPackage(
        package_id=package_id,
        profile=profile,
        ordered_stack=stack.ordered_stack,
        missing_docs=stack.missing_docs,
        is_complete=stack.is_complete,
        key_fields=key_fields,
        review_queue=review_queue,
        summary=summary,
    )
