"""Acquire issuer's exact Oct-2026 Sambhv sales/warrant PDFs, without bypass.

Two short exchange-facing issuer-hosted PDFs: Q2FY27 sales volumes (2 Oct)
and preferential-warrant monitoring-agency appointment (6 Oct). This
source evidence neither establishes warrant exercise, cash balance,
new 0.36MMTPA commissioning nor an investable return forecast.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader
from pypdf.errors import PdfReadError

SOURCE_ID = "HG007-P031-SAMBHV-OCT2026-VOLUME-WARRANT-PRIMARY-SOURCE-v1"
PDFS = {
    "q2_sales": {
        "url": (
            "https://www.sambhv.com/uploads/pdf/investors/investor-information/"
            "announcement/Sales-Volume-Update-Q2-FY-2026-27.pdf"
        ),
        "pages": 2,
        "reported_date": "2026-10-02",
    },
    "warrant_monitor": {
        "url": (
            "https://www.sambhv.com/uploads/pdf/investors/investor-information/"
            "announcement/Monitoring-Agency-Appointment-for-Preferential-Issue-of-Warrants.pdf"
        ),
        "pages": 1,
        "reported_date": "2026-10-06",
    },
}
QUARTERS = {
    "q2_fy27": {
        "structural_tonnes": 67020,
        "gp_tonnes": 32126,
        "stainless_tonnes": 14445,
        "value_added_total_tonnes": 113591,
        "intermediates_tonnes": 9071,
        "all_product_sales_tonnes": 122662,
    },
    "q1_fy27": {
        "structural_tonnes": 56617,
        "gp_tonnes": 29814,
        "stainless_tonnes": 14760,
        "value_added_total_tonnes": 101191,
        "intermediates_tonnes": 6580,
        "all_product_sales_tonnes": 107771,
    },
    "q2_fy26": {
        "structural_tonnes": 57788,
        "gp_tonnes": 20207,
        "stainless_tonnes": 11567,
        "value_added_total_tonnes": 89562,
        "intermediates_tonnes": 9206,
        "all_product_sales_tonnes": 98768,
    },
}
WARRANT_ISSUE_PROCEEDS_INR = 999_971_000
WARRANT_ISSUE_PROCEEDS_CR = WARRANT_ISSUE_PROCEEDS_INR / 10_000_000
MAX_PDF_BYTES = 12_000_000
STATES = {
    "ORIGINAL_ISSUER_PDF_CAPTURED_FACTS_VERIFIED",
    "ORIGINAL_ISSUER_SOURCE_ACCESS_BLOCKED",
    "ORIGINAL_ISSUER_SOURCE_NOT_FOUND",
    "ORIGINAL_ISSUER_REDIRECT_NOT_FOLLOWED",
    "ORIGINAL_ISSUER_INVALID_PDF_OR_FACTS",
    "ORIGINAL_ISSUER_HTTP_OR_NETWORK_FAILURE",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pdf_bytes_plausible(raw: bytes) -> bool:
    return (
        isinstance(raw, bytes)
        and 300 <= len(raw) <= MAX_PDF_BYTES
        and raw.startswith(b"%PDF-")
        and b"%%EOF" in raw[-2048:]
    )


def _text_pages(raw: bytes, *, expected_count: int) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if len(reader.pages) != expected_count:
            raise ValueError("original PDF page count does not match issuer document")
        texts = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("original issuer PDF cannot yield intact text pages") from exc
    if len(texts) != expected_count or any(len(page.strip()) < 80 for page in texts):
        raise ValueError("original issuer PDF contains missing text pages")
    return texts


def _text_identity(kind: str, pages: list[str]) -> dict[str, Any]:
    if kind not in PDFS or len(pages) != PDFS[kind]["pages"]:
        raise ValueError("wrong issuer document type or page count")
    text = re.sub(r"\s+", " ", " ".join(pages).lower()).replace(",", "")
    if "sambhv steel tubes limited" not in text or "sambhv" not in text:
        raise ValueError("PDF text does not prove SAMBHV issuer identity")
    if kind == "q2_sales":
        required = (
            "october 02 2026",
            "sales volume update",
            "structural pipes",
            "pre-galvanised",
            "stainless steel coils",
            "intermediate products",
            "q2 fy27",
            "q1 fy27",
            "q2 fy26",
        )
        # Each original table value is required to appear at least once.
        # Table/column arithmetic is then independently cross-checked.
        numeric = tuple(
            str(value)
            for quarter in QUARTERS.values()
            for value in quarter.values()
        )
        if any(term not in text for term in required + numeric):
            raise ValueError("original Q2 sales table source fact missing")
        for quarter_name, series in QUARTERS.items():
            if sum(series[col] for col in (
                "structural_tonnes", "gp_tonnes", "stainless_tonnes"
            )) != series["value_added_total_tonnes"]:
                raise ValueError(f"{quarter_name}: value-added component sum invalid")
            if series["value_added_total_tonnes"] + series["intermediates_tonnes"] != (
                series["all_product_sales_tonnes"]
            ):
                raise ValueError(f"{quarter_name}: original gross sales row invalid")
        return {
            "period_end_date": "2026-09-30",
            "report_date": "2026-10-02",
            "reported_quarter_values_tonnes": QUARTERS,
            "quarterly_price_or_ebitda_disclosed": False,
        }
    required = (
        "october 06 2026",
        "monitoring agency",
        "care ratings",
        "preferential issue of warrants",
        "august 10 2026",
        "999971000",
    )
    if any(term not in text for term in required):
        raise ValueError("issuer warrant monitoring disclosure terms absent")
    return {
        "report_date": "2026-10-06",
        "monitoring_agency_name": "CARE Ratings Limited",
        "shareholder_approval_date_stated": "2026-08-10",
        "issue_proceeds_stated_inr": WARRANT_ISSUE_PROCEEDS_INR,
        "issue_proceeds_stated_inr_crore": WARRANT_ISSUE_PROCEEDS_CR,
        "actual_warrant_exercise_and_cash_receipt_verified": False,
    }


def verify_original_pdf(kind: str, raw: bytes) -> dict[str, Any]:
    if kind not in PDFS or not _pdf_bytes_plausible(raw):
        raise ValueError("original issuer source URL/PDF envelope invalid")
    pages = _text_pages(raw, expected_count=PDFS[kind]["pages"])
    facts = _text_identity(kind, pages)
    return {
        "page_count": len(pages),
        "per_page_extracted_text_sha256": [
            hashlib.sha256(text.encode("utf-8")).hexdigest() for text in pages
        ],
        "issuer_filing_fact_checks": facts,
        "exact_pdf_sha256": hashlib.sha256(raw).hexdigest(),
        "full_pdf_visual_semantic_audit_completed": False,
        "shareholders_receipt_or_return_from_issue_proved": False,
    }


def _receipt(
    kind: str,
    state: str,
    *,
    status: int | None,
    raw: bytes | None,
    facts: dict[str, Any] | None,
    error: str,
) -> dict[str, Any]:
    success = state == "ORIGINAL_ISSUER_PDF_CAPTURED_FACTS_VERIFIED"
    if kind not in PDFS or state not in STATES:
        raise ValueError("invalid official issuer source receipt")
    if success != (raw is not None and facts is not None):
        raise ValueError("original source bytes/state must agree")
    return {
        "schema_version": 1,
        "capture_id": SOURCE_ID,
        "document_family": kind,
        "symbol": "SAMBHV",
        "source_url": PDFS[kind]["url"],
        "original_filing_date": PDFS[kind]["reported_date"],
        "captured_at_utc": _utc_now(),
        "state": state,
        "http_status": status,
        "original_pdf_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
        "original_pdf_byte_count": len(raw) if raw else None,
        "independently_reproducible_text": facts,
        "error_or_readiness_reason": error,
        "issuer_post_june_operating_profitability_verified": False,
        "new_steel_phase1_commissioned_verified": False,
        "current_fully_diluted_warrant_count_verified": False,
        "warrant_funds_received_into_bank_verified": False,
        "original_filing_visual_audit_completed": False,
        "shareholder_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def acquire_issuer_pdf(
    kind: str, *, attempts: int = 2, retry_seconds: float = 3.0
) -> tuple[dict[str, Any], bytes | None]:
    if kind not in PDFS:
        raise ValueError("unrecognized original issuer filing")
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("original source attempts must be 1 to 3")
    if type(retry_seconds) not in (float, int) or not 0 <= retry_seconds <= 30:
        raise ValueError("invalid retry seconds")
    url = PDFS[kind]["url"]
    last_status: int | None = None
    reason = "NO_ISSUER_SOURCE_RESPONSE"
    for index in range(attempts):
        try:
            response = requests.get(
                url, timeout=30, allow_redirects=False,
                headers={
                    "User-Agent": "marketlab-original-issuer-sambhv-evidence/1.0",
                    "Accept": "application/pdf",
                },
            )
            last_status = response.status_code
            if getattr(response, "url", url) != url:
                return _receipt(
                    kind, "ORIGINAL_ISSUER_REDIRECT_NOT_FOLLOWED",
                    status=last_status, raw=None, facts=None,
                    error="UNEXPECTED_ORIGIN_OR_REDIRECT",
                ), None
            if last_status == 200:
                raw = response.content
                try:
                    facts = verify_original_pdf(kind, raw)
                except ValueError as exc:
                    return _receipt(
                        kind, "ORIGINAL_ISSUER_INVALID_PDF_OR_FACTS",
                        status=200, raw=None, facts=None, error=str(exc)
                    ), None
                return _receipt(
                    kind, "ORIGINAL_ISSUER_PDF_CAPTURED_FACTS_VERIFIED",
                    status=200, raw=raw, facts=facts,
                    error="FACT_TABLE_IDENTIFIED_SOURCE_DOCUMENT_REVIEWED_NOT_ALLOCATION",
                ), raw
            if last_status in (401, 403, 429):
                return _receipt(
                    kind, "ORIGINAL_ISSUER_SOURCE_ACCESS_BLOCKED",
                    status=last_status, raw=None, facts=None,
                    error=f"HTTP_{last_status}_NO_BYPASS",
                ), None
            if last_status == 404:
                return _receipt(
                    kind, "ORIGINAL_ISSUER_SOURCE_NOT_FOUND",
                    status=404, raw=None, facts=None, error="EXACT_ISSUER_SOURCE_MISSING"
                ), None
            if 300 <= last_status < 400:
                return _receipt(
                    kind, "ORIGINAL_ISSUER_REDIRECT_NOT_FOLLOWED",
                    status=last_status, raw=None, facts=None, error="HTTP_REDIRECT",
                ), None
            reason = f"HTTP_{last_status}_OR_EMPTY"
            if last_status < 500:
                break
        except requests.RequestException as exc:
            reason = type(exc).__name__
        if index + 1 < attempts:
            time.sleep(retry_seconds)
    return _receipt(
        kind, "ORIGINAL_ISSUER_HTTP_OR_NETWORK_FAILURE",
        status=last_status, raw=None, facts=None, error=reason
    ), None


def _growth(current: int, prior: int) -> float:
    if current < 0 or prior <= 0:
        raise ValueError("invalid source volumes for growth calculation")
    return 100 * (current / prior - 1)


def build_sambhv_q2_case(
    records: dict[str, dict[str, Any]],
    raw_by_kind: dict[str, bytes | None],
) -> dict[str, Any]:
    if set(records) != set(PDFS) or set(raw_by_kind) != set(PDFS):
        raise ValueError("exact two October Sambhv originals required")
    sources: dict[str, Any] = {}
    for kind in PDFS:
        entry = records[kind]
        raw = raw_by_kind[kind]
        if (
            entry.get("capture_id") != SOURCE_ID
            or entry.get("document_family") != kind
            or entry.get("source_url") != PDFS[kind]["url"]
            or entry.get("state") != "ORIGINAL_ISSUER_PDF_CAPTURED_FACTS_VERIFIED"
            or entry.get("http_status") != 200
            or not isinstance(raw, bytes)
            or entry.get("original_pdf_sha256") != hashlib.sha256(raw).hexdigest()
        ):
            raise ValueError(f"{kind}: no verified original issuer PDF")
        inspected = verify_original_pdf(kind, raw)
        if entry.get("independently_reproducible_text") != inspected:
            raise ValueError(f"{kind}: original table facts changed after capture")
        sources[kind] = {
            "original_pdf_sha256": entry["original_pdf_sha256"],
            "source_url": entry["source_url"],
            "captured_at_utc": entry["captured_at_utc"],
            "original_pdf_byte_count": entry["original_pdf_byte_count"],
            "page_count": inspected["page_count"],
            "page_text_sha256": inspected["per_page_extracted_text_sha256"],
            "source_year_month": "2026-10",
        }
    q2 = QUARTERS["q2_fy27"]
    q1 = QUARTERS["q1_fy27"]
    year = QUARTERS["q2_fy26"]
    summary = {
        name: {
            "q2_fy27_tonnes": q2[name],
            "q1_fy27_tonnes": q1[name],
            "q2_fy26_tonnes": year[name],
            "yoy_pct": _growth(q2[name], year[name]),
            "qoq_pct": _growth(q2[name], q1[name]),
        }
        for name in q2
    }
    if not math.isclose(
        summary["all_product_sales_tonnes"]["yoy_pct"], 24.192046006803825,
        abs_tol=1e-9,
    ):
        raise ValueError("original sales figures failed independent reconciliation")
    return {
        "schema_version": 1,
        "readout_id": SOURCE_ID,
        "classification": "REPORTED_OCTOBER_VOLUME_AND_WARRANT_AGENCY_FACTS_NOT_EARNINGS",
        "symbol": "SAMBHV",
        "official_source_receipts": sources,
        "q2_2026_27_volume_report_date": "2026-10-02",
        "q2_vs_q1_vs_prior_year_sales_tonnes": summary,
        "sales_volume_issuer_reported_not_audited_revenue": True,
        "warrant_monitoring_appointment_date": "2026-10-06",
        "warrant_proceeds_issuer_disclosed_inr_crore": WARRANT_ISSUE_PROCEEDS_CR,
        "monitoring_agency": "CARE Ratings Limited",
        "shareholder_prior_approval_date": "2026-08-10",
        "warrant_proceeds_are_verified_current_cash": False,
        "warrant_exercise_and_dilution_verified": False,
        "steel_phase1_0_36mmtpa_plant_operating_verified": False,
        "steel_810cr_and_power_125cr_remaining_capex_reconciled_to_proceeds": False,
        "sales_yoy_growth_proves_incremental_ebitda": False,
        "new_business_cash_free_flow_verified": False,
        "current_fully_diluted_share_count_verified": False,
        "investment_expected_returns_computed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def save_attempt(
    out_dir: Path,
    records: dict[str, dict[str, Any]],
    raw_by_kind: dict[str, bytes | None],
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for kind, entry in records.items():
        body = raw_by_kind[kind]
        if body is not None:
            sha = hashlib.sha256(body).hexdigest()
            if sha != entry.get("original_pdf_sha256"):
                raise ValueError("original issuer byte custody SHA mismatch")
            location = out_dir / "raw" / "sha256" / f"{sha}.pdf"
            location.parent.mkdir(parents=True, exist_ok=True)
            if location.exists() and location.read_bytes() != body:
                raise ValueError("immutable original issuer document differs")
            location.write_bytes(body)
        (out_dir / f"{kind}-source-receipt.json").write_text(
            json.dumps(entry, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    ready = all(
        records[kind]["state"] == "ORIGINAL_ISSUER_PDF_CAPTURED_FACTS_VERIFIED"
        for kind in PDFS
    )
    full = build_sambhv_q2_case(records, raw_by_kind) if ready else None
    if full is not None:
        (out_dir / "sambhv-october-case.json").write_text(
            json.dumps(full, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    return {
        "attempt_id": SOURCE_ID,
        "ready_both_original_issuer_pdfs": ready,
        "states": {kind: records[kind]["state"] for kind in PDFS},
        "forward_valuation_allowed": False,
        "live_capital_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--retry-seconds", type=float, default=3.0)
    args = parser.parse_args()
    receipts: dict[str, dict[str, Any]] = {}
    originals: dict[str, bytes | None] = {}
    for kind in PDFS:
        receipt, original = acquire_issuer_pdf(
            kind, attempts=args.attempts, retry_seconds=args.retry_seconds
        )
        receipts[kind] = receipt
        originals[kind] = original
    print(json.dumps(save_attempt(args.out_dir, receipts, originals), sort_keys=True))


if __name__ == "__main__":
    main()
