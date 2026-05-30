"""Per-document-type JSON extraction schemas passed to ADE `client.extract`.

ADE extracts structured fields by matching the document's markdown against a JSON schema.
Keep field names canonical (dot-namespaced) so downstream consumers see stable field names
regardless of how a given lender's form is laid out.
"""

from __future__ import annotations

from .models import DocType


def _obj(props: dict[str, str]) -> dict:
    return {
        "type": "object",
        "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
    }


EXTRACTION_SCHEMAS: dict[DocType, dict] = {
    DocType.PAYSTUB: _obj(
        {
            "borrower.gross_pay_period": "Gross pay for this pay period",
            "borrower.pay_frequency": "weekly | biweekly | semimonthly | monthly",
            "borrower.ytd_gross": "Year-to-date gross pay",
            "employer.name": "Employer / company name",
            "pay_date": "Pay date on the stub",
        }
    ),
    DocType.W2: _obj(
        {
            "borrower.wages_box1": "Box 1 wages, tips, other compensation",
            "employer.ein": "Employer EIN (Box b)",
            "employer.name": "Employer name (Box c)",
            "tax_year": "Tax year of the W-2",
        }
    ),
    DocType.URLA_1003: _obj(
        {
            "borrower.declared_monthly_income": "Borrower total monthly income",
            "loan.amount": "Requested loan amount",
            "loan.purpose": "purchase | refinance | cash-out",
            "property.value": "Property value or purchase price",
            "property.address": "Subject property address",
        }
    ),
    DocType.BANK_STATEMENT: _obj(
        {
            "account.holder": "Account holder name",
            "account.ending_balance": "Statement ending balance",
            "account.institution": "Bank / institution name",
            "statement.period": "Statement period",
        }
    ),
    DocType.TAX_RETURN_1040: _obj(
        {
            "borrower.agi": "Adjusted gross income (1040 line 11)",
            "borrower.total_income": "Total income (1040 line 9)",
            "tax_year": "Tax year",
        }
    ),
    DocType.CLOSING_DISCLOSURE: _obj(
        {
            "loan.amount": "Loan amount",
            "loan.interest_rate": "Interest rate",
            "loan.monthly_pi": "Monthly principal & interest",
            "cash_to_close": "Cash to close",
        }
    ),
}


def schema_for(doc_type: DocType) -> dict:
    """Return the extraction schema for a doc type, defaulting to a type-detection schema."""
    return EXTRACTION_SCHEMAS.get(
        doc_type,
        _obj({"document.detected_type": "Best guess of the document type"}),
    )
