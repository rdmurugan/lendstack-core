"""Lightweight document classifier.

Determines a DocType for a file when the caller doesn't supply one. Order of precedence:
  1. explicit hint (caller-provided doc_type)
  2. live ADE parse -> keyword match on the layout-aware markdown
  3. filename heuristic (works offline / in stub mode)

Keyword matching is intentionally simple and auditable; a future version can use an ADE
schema-extract classification call. No ML magic that an examiner can't follow.
"""

from __future__ import annotations

from pathlib import Path

from .ade_client import ADEClient
from .models import ClassifyResult, DocType

# Ordered (DocType, keywords) — first match wins. Keep specific types before generic.
_KEYWORDS: list[tuple[DocType, tuple[str, ...]]] = [
    (DocType.W2, ("w-2", "wage and tax statement", "form w2")),
    (DocType.TAX_RETURN_1040, ("form 1040", "1040", "u.s. individual income tax return")),
    (DocType.PAYSTUB, ("earnings statement", "pay stub", "paystub", "ytd gross", "net pay")),
    (DocType.CLOSING_DISCLOSURE, ("closing disclosure",)),
    (DocType.URLA_1003, ("uniform residential loan application", "form 1003", "urla")),
    (DocType.CREDIT_APPLICATION, ("credit application", "application for credit")),
    (DocType.CREDIT_REPORT, ("credit report", "fico", "experian", "equifax", "transunion")),
    (DocType.PROOF_OF_INSURANCE, ("declarations page", "proof of insurance", "policy number")),
    (DocType.BANK_STATEMENT, ("statement period", "beginning balance", "ending balance")),
    (DocType.PROOF_OF_RESIDENCE, ("utility bill", "lease agreement", "proof of residence")),
    (DocType.RETAIL_INSTALLMENT_CONTRACT, ("retail installment", "amount financed", "annual percentage rate")),
    (DocType.VEHICLE_DOC, ("vehicle identification number", "vin", "odometer", "bill of sale")),
    (DocType.ID_DOCUMENT, ("driver license", "driver's license", "passport", "identification card")),
]

_FILENAME_HINTS: list[tuple[DocType, tuple[str, ...]]] = [
    (DocType.W2, ("w2", "w-2")),
    (DocType.PAYSTUB, ("paystub", "pay_stub", "earnings")),
    (DocType.TAX_RETURN_1040, ("1040", "tax_return", "taxreturn")),
    (DocType.URLA_1003, ("1003", "urla", "loan_application")),
    (DocType.BANK_STATEMENT, ("bank", "statement")),
    (DocType.CLOSING_DISCLOSURE, ("closing_disclosure", "cd_")),
    (DocType.CREDIT_APPLICATION, ("credit_app", "creditapp", "application")),
    (DocType.PROOF_OF_INSURANCE, ("insurance", "poi")),
    (DocType.ID_DOCUMENT, ("license", "passport", "id_", "_id")),
    (DocType.VEHICLE_DOC, ("vehicle", "vin", "title")),
]


def _match(text: str, table: list[tuple[DocType, tuple[str, ...]]]) -> DocType | None:
    low = text.lower()
    for dt, kws in table:
        if any(k in low for k in kws):
            return dt
    return None


def classify_document(
    file_path: str, hint: str | None = None, client: ADEClient | None = None
) -> ClassifyResult:
    if hint:
        return ClassifyResult(file_path=file_path, doc_type=DocType(hint), method="hint")

    client = client or ADEClient()
    if client.is_live and not file_path.startswith(("http://", "https://")):
        try:
            # Reuse extract() which parses; cheaper: do a parse-only here.
            from landingai_ade import LandingAIADE  # type: ignore

            raw = LandingAIADE()
            parsed = raw.parse(document=Path(file_path), model="dpt-2-latest")
            md = getattr(parsed, "markdown", "") or ""
            dt = _match(md, _KEYWORDS)
            if dt:
                return ClassifyResult(file_path=file_path, doc_type=dt, method="markdown")
        except Exception:  # noqa: BLE001 - fall through to filename heuristic
            pass

    dt = _match(Path(file_path).name, _FILENAME_HINTS)
    return ClassifyResult(
        file_path=file_path, doc_type=dt or DocType.OTHER, method="filename"
    )
