"""Exact BSE source probe for Anant Raj's Q1FY27 QIP monitoring report.

The unsigned/unaudited monitoring report is source evidence only.
Never equate unspent QIP cash with demerger-transferred cash, nor
consider monitoring-agency 'no deviation' an audit of cloud balances.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader
from pypdf.errors import PdfReadError

CASE_ID = "HG007-P027-ANANTRAJ-JUNE2026-QIP-AGENCY-ORIGINAL-v1"
SOURCE_URL = (
    "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
    "8d34184b-45a6-4317-b98d-02b4d60e7b25.pdf"
)
MAX_BYTES = 16_000_000
CAPTURE_OK = "ORIGINAL_BSE_MONITOR_PDF_BYTES_CAPTURED_NOT_FINANCIAL_AUDIT"
RESULT_STATES = {
    CAPTURE_OK, "BSE_ACCESS_BLOCKED", "BSE_404_NOT_PUBLISHED",
    "BSE_REDIRECT_NOT_FOLLOWED", "BSE_INVALID_PDF_OR_ISSUER",
    "BSE_HTTP_OR_NETWORK_FAILURE",
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _inspect_original_pdf(raw: bytes) -> dict[str, Any]:
    if (
        not isinstance(raw, bytes)
        or not 2048 <= len(raw) <= MAX_BYTES
        or not raw.startswith(b"%PDF-")
        or b"%%EOF" not in raw[-2048:]
    ):
        raise ValueError("original BSE monitoring report PDF byte envelope invalid")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        count = len(reader.pages)
        if not 4 <= count <= 80:
            raise ValueError("original monitoring agency report pages outside expected range")
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, KeyError, TypeError, OSError, ValueError) as exc:
        raise ValueError("source monitoring report has unreadable PDF pages") from exc
    first = " ".join(pages[:3]).casefold()
    whole = " ".join(pages).casefold()
    if (
        "anant raj" not in first
        or "monitoring agency" not in first
        or "june 30, 2026" not in whole
        or "qualified" not in whole
        or "infomerics" not in whole
    ):
        raise ValueError("monitor report original issuer, period or auditor mismatch")
    return {
        "original_issuer": "Anant Raj Limited",
        "monitoring_agency_named_in_original": "Infomerics Valuation and Rating Limited",
        "reported_quarter_end": "2026-06-30",
        "original_issuer_document_date": "2026-08-08",
        "page_count": count,
        "page_text_sha256": [
            hashlib.sha256(page.encode("utf-8")).hexdigest() for page in pages
        ],
        "all_pages_semantically_or_visually_approved": False,
        "reported_qip_objects_amounts_issuer_independently_reconciled": False,
        "actual_cash_transferred_to_ashok_cloud_verified": False,
    }


def _receipt(state: str, http_status: int | None, *,
             raw: bytes | None, details: dict | None, reason: str) -> dict[str, Any]:
    if state not in RESULT_STATES:
        raise ValueError("invalid official BSE monitoring report source state")
    ok = state == CAPTURE_OK
    if ok != (raw is not None and details is not None):
        raise ValueError("source state and original bytes are contradictory")
    return {
        "schema_version": 1, "capture_id": CASE_ID, "listed_symbol": "ANANTRAJ",
        "issuer": "Anant Raj Limited", "report_quarter_end": "2026-06-30",
        "source_url": SOURCE_URL, "captured_at_utc": _now(),
        "http_status": http_status, "state": state, "reason": reason,
        "original_pdf_sha256": hashlib.sha256(raw).hexdigest() if ok else None,
        "original_pdf_byte_count": len(raw) if ok else None,
        "source_pdf_text_identity": details,
        "full_qip_utilization_table_audited": False,
        "cloud_scheme_cash_transfer_amount_audited": False,
        "cloud_scheme_loan_transfer_amount_audited": False,
        "anant_raj_debt_free_business_confirmed": False,
        "report_is_a_financial_statement_audit": False,
        "equity_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def acquire_bse_original(*, attempts: int = 2, sleep_seconds: float = 3.0
                         ) -> tuple[dict[str, Any], bytes | None]:
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("source attempts must be between 1 and 3")
    if type(sleep_seconds) not in (float, int) or not 0 <= sleep_seconds <= 30:
        raise ValueError("source retry delay outside allowed bound")
    last_http: int | None = None
    issue = "NO_VALID_HTTP_RESPONSE"
    for i in range(attempts):
        try:
            response = requests.get(
                SOURCE_URL, timeout=35, allow_redirects=False,
                headers={"User-Agent": "marketlab-research-source-audit/1.0",
                         "Accept": "application/pdf"},
            )
            status = response.status_code
            last_http = status
            if getattr(response, "url", SOURCE_URL) != SOURCE_URL:
                return _receipt("BSE_REDIRECT_NOT_FOLLOWED", status, raw=None,
                                details=None, reason="EXACT_ORIGINAL_URL_CHANGED"), None
            if status == 200:
                original = response.content
                try:
                    details = _inspect_original_pdf(original)
                except ValueError as exc:
                    return _receipt("BSE_INVALID_PDF_OR_ISSUER", status, raw=None,
                                    details=None, reason=str(exc)), None
                return _receipt(
                    CAPTURE_OK, status, raw=original, details=details,
                    reason="ORIGINAL_BYTES_RETAINED_AUDIT_STILL_PENDING",
                ), original
            if status in (401, 403, 429):
                return _receipt("BSE_ACCESS_BLOCKED", status, raw=None, details=None,
                                reason=f"HTTP_{status}_NO_ACCESS_BYPASS"), None
            if status == 404:
                return _receipt("BSE_404_NOT_PUBLISHED", status, raw=None,
                                details=None, reason="ORIGINAL_ATTACHMENT_MISSING"), None
            if 300 <= status < 400:
                return _receipt("BSE_REDIRECT_NOT_FOLLOWED", status, raw=None,
                                details=None, reason="REDIRECT_NOT_FOLLOWED"), None
            issue = f"HTTP_{status}"
            if status < 500:
                break
        except requests.RequestException as exc:
            issue = type(exc).__name__
        if i + 1 < attempts:
            time.sleep(sleep_seconds)
    return _receipt("BSE_HTTP_OR_NETWORK_FAILURE", last_http, raw=None,
                    details=None, reason=issue), None


def retain_original(out_dir: Path, receipt: dict[str, Any], original: bytes | None) -> None:
    if receipt.get("capture_id") != CASE_ID:
        raise ValueError("unexpected original QIP report receipt identity")
    out_dir.mkdir(parents=True, exist_ok=True)
    if original is not None:
        if receipt.get("state") != CAPTURE_OK:
            raise ValueError("cannot retain BSE PDF from unverified source")
        parsed = _inspect_original_pdf(original)
        sha = hashlib.sha256(original).hexdigest()
        if sha != receipt.get("original_pdf_sha256") or (
            parsed != receipt.get("source_pdf_text_identity")
        ):
            raise ValueError("original PDF content or page text disagrees with receipt")
        location = out_dir / "raw" / "sha256" / f"{sha}.pdf"
        location.parent.mkdir(parents=True, exist_ok=True)
        if location.exists() and location.read_bytes() != original:
            raise ValueError("original source hash collision")
        location.write_bytes(original)
    elif receipt.get("original_pdf_sha256") is not None:
        raise ValueError("cannot assert original PDF SHA without original bytes")
    target = out_dir / "attempt.json"
    encoded = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") != encoded:
        raise ValueError("original source receipt may not be overwritten")
    target.write_text(encoded, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=3)
    args = parser.parse_args()
    receipt, original = acquire_bse_original(
        attempts=args.attempts, sleep_seconds=args.sleep_seconds
    )
    retain_original(args.out_dir, receipt, original)
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
