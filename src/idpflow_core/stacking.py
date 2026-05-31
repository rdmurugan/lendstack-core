"""Document-stacking engine.

Stacks a set of documents into the order a reviewer wants. Order is configurable via named
profiles; the defaults below are examples for mortgage and auto document sets.

It cares only about a list of (doc_type, file_path) -- it does NOT care whether the documents
arrived via an upload portal, an SFTP/S3 drop, an email, or an export. Connectors are thin
adapters that produce this list.
"""

from __future__ import annotations

from .models import DocType, MissingDoc, StackItem, StackResult

# Full display/stacking order per profile (assembly order of the credit file).
STACK_PROFILES: dict[str, list[DocType]] = {
    # Mortgage: typical investor/agency stacking order.
    "mortgage": [
        DocType.URLA_1003,
        DocType.CREDIT_REPORT,
        DocType.PAYSTUB,
        DocType.W2,
        DocType.TAX_RETURN_1040,
        DocType.BANK_STATEMENT,
        DocType.ID_DOCUMENT,
        DocType.APPRAISAL,
        DocType.TITLE,
        DocType.CLOSING_DISCLOSURE,
    ],
    # Indirect auto: credit app + decision, then stips, then contract.
    "auto_indirect": [
        DocType.CREDIT_APPLICATION,
        DocType.CREDIT_REPORT,
        DocType.ID_DOCUMENT,
        DocType.PAYSTUB,
        DocType.PROOF_OF_INSURANCE,
        DocType.PROOF_OF_RESIDENCE,
        DocType.VEHICLE_DOC,
        DocType.RETAIL_INSTALLMENT_CONTRACT,
    ],
    # Direct auto/consumer: member-supplied stips into the LOS.
    "auto_direct": [
        DocType.CREDIT_APPLICATION,
        DocType.ID_DOCUMENT,
        DocType.PAYSTUB,
        DocType.BANK_STATEMENT,
        DocType.PROOF_OF_INSURANCE,
        DocType.PROOF_OF_RESIDENCE,
        DocType.VEHICLE_DOC,
    ],
}

# Subset of each profile that MUST be present for a complete file.
REQUIRED_BY_PROFILE: dict[str, set[DocType]] = {
    "mortgage": {
        DocType.URLA_1003,
        DocType.PAYSTUB,
        DocType.W2,
        DocType.BANK_STATEMENT,
        DocType.ID_DOCUMENT,
    },
    "auto_indirect": {
        DocType.CREDIT_APPLICATION,
        DocType.ID_DOCUMENT,
        DocType.PAYSTUB,
        DocType.PROOF_OF_INSURANCE,
    },
    "auto_direct": {
        DocType.CREDIT_APPLICATION,
        DocType.ID_DOCUMENT,
        DocType.PAYSTUB,
    },
}


def profiles() -> list[str]:
    return list(STACK_PROFILES.keys())


def stack_documents(
    present: list[tuple[DocType, str]],
    profile: str = "mortgage",
    custom_order: list[DocType] | None = None,
) -> StackResult:
    """Order documents by stack profile (or a caller-supplied custom order).

    Args:
        present: list of (doc_type, file_path) already collected.
        profile: a named profile in STACK_PROFILES.
        custom_order: optional explicit ordering that overrides the profile's order.

    Docs whose type isn't in the order are appended at the end (in_profile=False).
    Missing required docs are reported separately.
    """
    order = custom_order or STACK_PROFILES.get(profile, STACK_PROFILES["mortgage"])
    order_index = {dt: i for i, dt in enumerate(order)}

    items: list[StackItem] = []
    pos = 1
    used: list[int] = []

    # Place docs that are in the profile order, in order (stable for duplicates).
    for dt in order:
        for idx, (d, fp) in enumerate(present):
            if idx in used:
                continue
            if d == dt:
                items.append(
                    StackItem(position=pos, doc_type=d, file_path=fp, in_profile=True)
                )
                pos += 1
                used.append(idx)

    # Append any extras not in the profile.
    for idx, (d, fp) in enumerate(present):
        if idx not in used:
            items.append(StackItem(position=pos, doc_type=d, file_path=fp, in_profile=False))
            pos += 1

    present_types = {d for d, _ in present}
    required = REQUIRED_BY_PROFILE.get(profile, set())
    missing = [
        MissingDoc(doc_type=d, reason=f"Required for the '{profile}' stack.")
        for d in order
        if d in required and d not in present_types
    ]
    return StackResult(
        profile=profile,
        ordered_stack=items,
        missing_docs=missing,
        is_complete=len(missing) == 0,
    )
