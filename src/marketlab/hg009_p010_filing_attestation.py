"""HG009 P010: replay archived issuer original rows with date/unit attribution.

Never infer normalized earnings or valuation from a matching number token.
Different original NSE HTML byte versions are independently checked. POKARNA
remains blocked because its large PDF has not been durably source-archived.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import io
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from pypdf import PdfReader

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p009_originals import (
    ARCHIVE_ROOT,
    source_specifications,
    validate_original_receipt,
)

PROGRAM_ID = "HG009-P010-NSE-ISSUER-ORIGINAL-ROW-RECONCILIATION-v1"
REVIEW_DATE = "2026-10-15"

# Original statement quantities remain under the proper source unit.
# 2025 PIX is INR ACTUALS, not INR lakhs like the later 2026 filing.
PROOF_ROWS = {
    "MAYURUNIQ-FY26_AUDITED_CONSOLIDATED": {
        "issuer_name": "MAYURUNIQ",
        "reporting_basis": "CONSOLIDATED_AUDITED",
        "source_unit": "INR_LAKH",
        "period_end": "31-03-2026",
        "kind": "html",
        "rows": {
            "pbt_lakh": ("total profit before tax", "25,898.23"),
            "cfo_lakh": (
                "net cash flows from (used in) operating activities",
                "13,315.27",
            ),
            "ppe_purchase_lakh": (
                "purchase of property, plant and equipment",
                "2,420.71",
            ),
        },
        "summary_crore": {
            "reported_pbt_cr": 258.9823,
            "reported_cfo_cr": 133.1527,
            "reported_ppe_cash_cr": 24.2071,
        },
    },
    "PIXTRANS-Q1FY27_STANDALONE": {
        "issuer_name": "PIXTRANS",
        "reporting_basis": "STANDALONE_UNAUDITED",
        "source_unit": "INR_LAKH",
        "period_end": "30-06-2026",
        "kind": "html",
        "rows": {
            "reported_pbt_lakh": ("total profit before tax", "6,081.68"),
            "other_income_lakh": ("other income", "2,731.12"),
        },
        "required_note": (
            "fvtpl adjustment on investments amounting to rs. 2,529.49 lakhs"
        ),
        "summary_crore": {
            "reported_pbt_cr": 60.8168,
            "one_item_investment_fvtpl_cr": 25.2949,
            "pbt_less_single_fvtpl_item_cr": 35.5219,
        },
    },
    "PIXTRANS-Q1FY26_STANDALONE": {
        "issuer_name": "PIXTRANS",
        "reporting_basis": "STANDALONE_UNAUDITED",
        "source_unit": "INR_ACTUAL_RUPEES",
        "period_end": "30-Jun-2025",
        "kind": "html",
        "rows": {
            "reported_pbt_actual_inr": (
                "total profit before tax", "309666000"
            ),
        },
        "summary_crore": {
            "reported_prior_year_pbt_cr": 30.9666,
        },
    },
    "DATAMATICS-FY26_AUDITED_CONSOLIDATED": {
        "issuer_name": "DATAMATICS",
        "reporting_basis": "CONSOLIDATED_AUDITED",
        "source_unit": "INR_CRORE",
        "period_end": "31-Mar-26",
        "kind": "pdf",
        "pdf_zero_based_page": 7,
        "pdf_required_text": (
            "Cash Flow Statement", "Consolidated",
            "Net cash flow from operating activities",
            "323.99", "Purchase of fixed assets", "39.57",
        ),
        "summary_crore": {
            "reported_cfo_cr": 323.99,
            "reported_fixed_asset_cash_spend_cr": 39.57,
            "preliminary_cfo_minus_selected_capex_proxy_cr": 284.42,
        },
    },
}
UNARCHIVED_DOCUMENTS = {
    "POKARNA-FY26_ORIGINAL_RESULT_PACKET": (
        "PENDING_EXTERNAL_CONTENT_ADDRESSED_20MB_PDF_ARCHIVE"
    ),
}


def _squash(text: str) -> str:
    return " ".join(text.casefold().replace("\xa0", " ").split())


def _numeric_in_line(line: str, token: str) -> bool:
    """Accept source-native numeric grouping, never any arbitrary substring."""
    exact = re.escape(token)
    # For legacy full-rupee source with ungrouped amounts allow grouped form
    # only when the value is identical after commas are removed.
    forms = [exact]
    if token.isdigit():
        forms.append(re.escape(f"{int(token):,}"))
    return any(
        re.search(rf"(?<![0-9.,]){form}(?![0-9.,])", line)
        for form in forms
    )


def _check_html(raw: bytes, spec: dict, rule: dict) -> dict:
    content = BeautifulSoup(raw, "html.parser")
    full = _squash(content.get_text(" ", strip=True))
    if (
        _squash("NSE Symbol") not in full
        or spec["symbol"].casefold() not in full
        or spec["isin"].casefold() not in full
        or "standalone" not in full if "STANDALONE" in rule["reporting_basis"]
        else "consolidated" not in full
    ):
        raise AlphaContractError("P010 issuer symbol/ISIN/basis not source verified")
    if _squash(rule["period_end"]) not in full:
        raise AlphaContractError("P010 accounting period missing from original HTML")
    if rule["source_unit"] == "INR_LAKH":
        if "lakhs" not in full:
            raise AlphaContractError("P010 declared lakh accounting units absent")
    elif (
        rule["source_unit"] == "INR_ACTUAL_RUPEES"
        and "in actuals" not in full
    ):
        raise AlphaContractError("P010 PIX prior period is not confirmed INR actuals")
    if "AUDITED" in rule["reporting_basis"] and "audited" not in full:
        raise AlphaContractError("P010 annual audited status unproven")
    if "UNAUDITED" in rule["reporting_basis"] and "unaudited" not in full:
        raise AlphaContractError("P010 quarterly unaudited status unproven")
    lines = [
        _squash(tr.get_text(" ", strip=True))
        for tr in content.find_all("tr")
        if tr.find("tr") is None
    ]
    evidence = []
    for key, (label, numeric) in rule["rows"].items():
        matches = [
            line for line in lines
            if _squash(label) in line and _numeric_in_line(line, numeric)
        ]
        if not matches:
            raise AlphaContractError(
                f"P010 original issuer statement row mismatch: {key}"
            )
        evidence.append({
            "row_id": key,
            "expected_source_unit": rule["source_unit"],
            "exact_source_numeric_token": numeric,
            "source_leaf_row_label": label,
            "original_matching_leaf_row_count": len(matches),
        })
    note = rule.get("required_note")
    if note and _squash(note) not in full:
        raise AlphaContractError("P010 original PIX investment FVTPL note missing")
    return {
        "row_evidence": evidence,
        "textual_issuer_identity_verified": True,
        "textual_period_and_accounting_unit_verified": True,
        "same_row_number_label_checked": True,
        "nonoperating_note_checked": bool(note),
        "pdf_page_column_order_independently_verified": None,
    }


def _check_pdf(raw: bytes, rule: dict) -> dict:
    pdf = PdfReader(io.BytesIO(raw))
    page_num = rule["pdf_zero_based_page"]
    if len(pdf.pages) <= page_num:
        raise AlphaContractError("P010 source Datamatics cashflow page absent")
    page = pdf.pages[page_num]
    extracted = page.extract_text(extraction_mode="layout")
    normalized = _squash(extracted)
    matches = {
        term: _squash(term) in normalized
        for term in rule["pdf_required_text"]
    }
    if not all(matches.values()):
        missing = [key for key, result in matches.items() if not result]
        raise AlphaContractError(
            f"P010 original cashflow page text incomplete: {missing}"
        )
    return {
        "pdf_page_zero_based": page_num,
        "pdf_native_text_sha256": hashlib.sha256(
            extracted.encode("utf-8")
        ).hexdigest(),
        "pdf_required_tokens": matches,
        "pdf_page_column_order_independently_verified": False,
        "cashflow_column_attribution_requires_manual_visible_page_check": True,
        "same_row_number_label_checked": False,
        "textual_issuer_identity_verified": True,
        "textual_period_and_accounting_unit_verified": True,
        "row_evidence": [],
    }


def build_p010_evidence(root: Path) -> dict[str, Any]:
    originals = {
        spec["document_id"]: spec for spec in source_specifications(root)
    }
    if set(originals) != set(PROOF_ROWS) | set(UNARCHIVED_DOCUMENTS):
        raise AlphaContractError("P010 original five source slots drifted")
    all_receipts = list(sorted(
        (root / ARCHIVE_ROOT / "attempts").glob("*.json")
    ))
    evidence_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in all_receipts:
        receipt = __import__("json").loads(path.read_text(encoding="utf-8"))
        validate_original_receipt(receipt, root=root)
        name = receipt["document_id"]
        if name not in originals:
            raise AlphaContractError("P010 unregistered original evidence")
        for key, val in originals[name].items():
            if receipt.get(key) != val:
                raise AlphaContractError("P010 source spec differs from registered original")
        evidence_by_doc[name].append(receipt)

    outputs = []
    for name, spec in originals.items():
        rules = PROOF_ROWS.get(name)
        receipts = evidence_by_doc[name]
        archive_versions = {}
        for receipt in receipts:
            src_sha = receipt.get("raw_sha256")
            if not receipt.get("raw_repo_path") or not src_sha:
                continue
            archive_versions.setdefault(src_sha, receipt)
        audit_versions = []
        for source_sha, receipt in sorted(archive_versions.items()):
            path = root / receipt["raw_repo_path"]
            raw = gzip.decompress(path.read_bytes())
            if hashlib.sha256(raw).hexdigest() != source_sha:
                raise AlphaContractError("P010 original NSE bytes hash changed")
            try:
                proof = (
                    _check_html(raw, spec, rules)
                    if rules["kind"] == "html"
                    else _check_pdf(raw, rules)
                )
            except (AlphaContractError, ValueError, OSError) as exc:
                audit_versions.append({
                    "source_sha256": source_sha,
                    "source_receipt_sha256": receipt["receipt_sha256"],
                    "source_completion_utc": receipt["actual_retrieved_at_utc"],
                    "status": "BLOCKED_FILING_ROW_OR_IDENTITY_MISMATCH",
                    "block_reason": str(exc)[:512],
                    "verified_rows": None,
                })
            else:
                audit_versions.append({
                    "source_sha256": source_sha,
                    "source_receipt_sha256": receipt["receipt_sha256"],
                    "source_completion_utc": receipt["actual_retrieved_at_utc"],
                    "status": "DOCUMENT_TEXT_TOKENS_VERIFIED_NOT_OWNER_CASH",
                    "block_reason": None,
                    "verified_rows": proof,
                })
        if not rules:
            state = UNARCHIVED_DOCUMENTS[name]
        elif not archive_versions:
            state = "MISSING_ORIGINAL_RETAINED_BYTES"
        elif any(
            ver["status"] == "BLOCKED_FILING_ROW_OR_IDENTITY_MISMATCH"
            for ver in audit_versions
        ):
            state = "BLOCKED_SOURCE_VERSION_DISAGREEMENT_OR_FORMAT"
        else:
            state = "ORIGINAL_SOURCE_TEXT_MATCHED_NOT_INVESTMENT_READY"
        outputs.append({
            "document_id": name,
            "symbol": spec["symbol"],
            "isin": spec["isin"],
            "source_url": spec["source_url"],
            "source_document_declared_date": spec[
                "original_issuer_publication_date"
            ],
            "accounting_basis": None if not rules else rule_basis(rules),
            "source_units": None if not rules else rules["source_unit"],
            "archived_byte_version_count": len(archive_versions),
            "original_issuer_source_version_proofs": audit_versions,
            "state": state,
            "conditionally_verified_reported_facts_cr": (
                rules["summary_crore"] if state ==
                "ORIGINAL_SOURCE_TEXT_MATCHED_NOT_INVESTMENT_READY"
                else None
            ),
            "company_equity_value_verified": False,
            "retained_source_is_same_as_issuer_owner_cash": False,
        })
    result = {
        "schema_version": 1,
        "audit_id": PROGRAM_ID,
        "audit_date": REVIEW_DATE,
        "original_document_count": 5,
        "archive_verified_document_count": sum(
            row["archived_byte_version_count"] > 0 for row in outputs
        ),
        "all_versions_textually_verified_count": sum(
            row["state"] == "ORIGINAL_SOURCE_TEXT_MATCHED_NOT_INVESTMENT_READY"
            for row in outputs
        ),
        "price_or_current_diluted_share_count_verified": False,
        "normalized_owner_cashflow_verified": False,
        "any_price_target_or_return_estimated": False,
        "current_real_money_trades_authorized": False,
        "live_capital_allowed": False,
        "source_documents": outputs,
    }
    result["packet_sha256"] = digest(result)
    return result


def rule_basis(rule: dict) -> str:
    return rule["reporting_basis"]


def validate_p010_evidence(
    packet: dict[str, Any], *,
    root: Path,
) -> None:
    data = copy.deepcopy(packet)
    recorded = data.pop("packet_sha256", None)
    if recorded != digest(data):
        raise AlphaContractError("P010 original financial report digest changed")
    if packet != build_p010_evidence(root):
        raise AlphaContractError("P010 original financial source replay mismatch")
