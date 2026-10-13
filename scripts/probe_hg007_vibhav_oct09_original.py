"""Acquire original INOXGREEN 9-Oct Vibhav subsidiary equity-conversion filing.

Strict NSE archive URL. This source-custody stage only verifies raw bytes,
issuer identity and disclosed equity conversion; WWIL BTA completion remains
a separate unresolved legal/business event.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader
from pypdf.errors import PdfReadError

SOURCE_ID = "HG007-P045-INOXGREEN-2026-10-09-VIBHAV-EQUITY-CONVERSION-SOURCE-v1"
OFFICIAL_URL = (
    "https://nsearchives.nseindia.com/corporate/"
    "IGESL_09102026233918_IGESL_SE_Vibhav_WOS_intimaiton_dsc.pdf"
)
MAX_SIZE = 8_000_000
OK = "OFFICIAL_NSE_OCT09_PDF_CAPTURED_UNREVIEWED"
BLOCKED = "OFFICIAL_NSE_PDF_BLOCKED"
NOT_PDF = "SOURCE_NONPDF_OR_SEMANTIC_IDENTITY_MISMATCH"
FAILED = "SOURCE_HTTP_OR_NETWORK_FAILURE"
NOT_FOUND = "SOURCE_NOT_FOUND"
REDIRECT = "SOURCE_UNFOLLOWED_REDIRECT"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pdf_pages(raw: bytes) -> list[str]:
    if (
        not isinstance(raw, bytes)
        or not 1000 <= len(raw) <= MAX_SIZE
        or not raw.startswith(b"%PDF-")
        or b"%%EOF" not in raw[-2048:]
    ):
        raise ValueError("official original PDF byte envelope missing or oversized")
    try:
        pdf = PdfReader(io.BytesIO(raw), strict=False)
        if len(pdf.pages) != 2:
            raise ValueError("official October 9 original has unexpected page count")
        pages = [page.extract_text() or "" for page in pdf.pages]
    except (PdfReadError, OSError, TypeError, KeyError, ValueError) as exc:
        raise ValueError("original PDF page tree/text unreadable") from exc
    if any(len(page.strip()) < 150 for page in pages):
        raise ValueError("original filing has unreadable page text")
    return pages


def verify_original_oct9(raw: bytes) -> dict[str, Any]:
    pages = _pdf_pages(raw)
    first = re.sub(r"\s+", " ", pages[0]).casefold()
    other = re.sub(r"\s+", " ", pages[1]).casefold()
    required_first = (
        "9th october, 2026",
        "inoxgreen",
        "vibhav energy",
        "rs. 150",
        "5 crore",
        "10 crore",
        "authum",
        "75%",
        "25%",
        "ceased to be",
    )
    for term in required_first:
        if term not in first:
            raise ValueError(f"issuer original October 9 page 1 missing {term}")
    if (
        "400.01" not in other
        or "fresh cash outflow" not in other
        or "completed" not in other
        or "50 crore" not in other
    ):
        raise ValueError("original October 9 Annexure A shareholder/terms missing")
    if 250.01 + 50 + 100 != 400.01:
        raise ValueError("original subsidiary share-capital conversion math changed")
    parent = 250.01 + 50
    outside = 100
    return {
        "page_count": 2,
        "page_text_sha256": [hashlib.sha256(page.encode()).hexdigest() for page in pages],
        "issuer": "Inox Green Energy Services Limited",
        "issuer_symbol": "INOXGREEN",
        "filing_date_ist": "2026-10-09",
        "vibhav_conversion_date_ist": "2026-10-09",
        "total_existing_icds_converted_inr_crore": 150,
        "inoxgreen_icd_converted_inr_crore": 50,
        "authum_icd_converted_inr_crore": 100,
        "inoxgreen_new_vibhav_equity_shares_crore": 5,
        "authum_new_vibhav_equity_shares_crore": 10,
        "subsidiary_paid_up_cap_after_conversion_inr_crore": 400.01,
        "reported_issuer_vibhav_ownership_pct": 75,
        "reported_authum_vibhav_ownership_pct": 25,
        "post_conversion_vibhav_wholly_owned": False,
        "parent_vibhav_subsidiary_status_preserved": True,
        "conversion_is_noncash": True,
        "illustrative_capital_fraction_from_par_equity": parent / (parent + outside),
        "original_wwil_bta_legal_transfer_verified_by_this_notice": False,
        "authum_and_parent_nonconvertible_loan_balances_currently_verified": False,
        "stock_expected_returns_calculated": False,
    }


def _receipt(state: str, http: int | None, raw: bytes | None, facts: dict | None, reason: str) -> dict:
    if (raw is None) != (state != OK):
        raise ValueError("original PDF receipt/source success state mismatch")
    return {
        "schema_version": 1,
        "source_id": SOURCE_ID,
        "original_nse_url": OFFICIAL_URL,
        "observed_at_utc": _now(),
        "source_http_status": http,
        "source_state": state,
        "original_pdf_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
        "original_pdf_size": len(raw) if raw is not None else None,
        "text_verified_disclosure_fields_not_investment_approval": facts,
        "source_error": reason,
        "original_page_visual_audit_complete": False,
        "source_first_public_timestamp_verified": False,
        "wwil_bta_conditions_satisfied": False,
        "wwil_undertaking_transfer_completed": False,
        "acquired_wwil_normalized_ebitda_verified": False,
        "company_equity_price_target_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def acquire_oct9(*, attempts: int = 2, sleep_seconds: float = 3) -> tuple[dict, bytes | None]:
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("attempts must be bounded between 1 and 3")
    if type(sleep_seconds) not in (int, float) or not 0 <= sleep_seconds <= 30:
        raise ValueError("retry spacing must be 0-30 seconds")
    last_http: int | None = None
    last_issue = "NO_RESPONSE"
    for attempt in range(attempts):
        try:
            response = requests.get(
                OFFICIAL_URL, timeout=30, allow_redirects=False,
                headers={"Accept": "application/pdf", "User-Agent": "marketlab-original-nse-source/1.0"},
            )
            last_http = response.status_code
            if getattr(response, "url", OFFICIAL_URL) != OFFICIAL_URL or 300 <= last_http < 400:
                return _receipt(REDIRECT, last_http, None, None, "NO_REDIRECT_FOLLOWING"), None
            if last_http == 200:
                body = response.content
                try:
                    details = verify_original_oct9(body)
                except ValueError as exc:
                    return _receipt(NOT_PDF, 200, None, None, str(exc)), None
                return _receipt(OK, 200, body, details, "EXACT_BYTES_SEALED_NOT_VISUALLY_REVIEWED"), body
            if last_http in (401, 403, 429):
                return _receipt(BLOCKED, last_http, None, None, "ACCESS_RESTRICTED_NO_BYPASS"), None
            if last_http == 404:
                return _receipt(NOT_FOUND, 404, None, None, "EXACT_PDF_MISSING"), None
            last_issue = f"HTTP_{last_http}"
            if last_http < 500:
                break
        except requests.RequestException as exc:
            last_issue = type(exc).__name__
        if attempt + 1 < attempts:
            time.sleep(sleep_seconds)
    return _receipt(FAILED, last_http, None, None, last_issue), None


def retain_source(output_dir: Path, receipt: dict, original: bytes | None) -> None:
    if receipt.get("source_id") != SOURCE_ID:
        raise ValueError("wrong original filing source identity")
    if original is not None:
        sha = hashlib.sha256(original).hexdigest()
        if (
            receipt.get("source_state") != OK
            or receipt.get("original_pdf_sha256") != sha
            or receipt.get("text_verified_disclosure_fields_not_investment_approval")
            != verify_original_oct9(original)
        ):
            raise ValueError("original PDF bytes/semantic checksum mismatch")
        dest = output_dir / "raw" / "sha256" / f"{sha}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.read_bytes() != original:
            raise ValueError("immutable original PDF cannot be overwritten")
        dest.write_bytes(original)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
            raise ValueError("original source retention hash failed")
    elif receipt.get("original_pdf_sha256") is not None:
        raise ValueError("missing PDF bytes cannot claim source identity")
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "source-receipt-v1.json"
    encoded = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if dest.exists() and dest.read_text(encoding="utf-8") != encoded:
        raise ValueError("source receipt overwrite refused")
    dest.write_text(encoded, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--attempts", default=2, type=int)
    args = parser.parse_args()
    receipt, body = acquire_oct9(attempts=args.attempts)
    retain_source(args.out_dir, receipt, body)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
