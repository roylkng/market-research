"""Capture original September 2026 INOXGREEN NSE QIP filing, no bypass.

Only source provenance and limited deterministic issuer/date/share-capital
identity checks. The PDF is NOT a present-day FD shareholding report and
does not authorize any price targets or capital deployment.
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

CASE_ID = "HG007-P007-INOXGREEN-SEP29-QIP-EXCHANGE-ORIGINAL-v1"
ORIGINAL_URL = (
    "https://nsearchives.nseindia.com/corporate/"
    "IGESL_30092026005646_IGESL_SE_Allotment_30092026_S.pdf"
)
QIP_ALLOTTED_SHARES = 18_110_473
PRE_QIP_ISSUED_SHARES = 401_492_045
POST_QIP_ISSUED_SHARES = 419_602_518
ISSUE_PRICE_INR = 165.65
QIP_CONSIDERATION_INR = 2_999_999_852.45
PDF_MAX_BYTES = 8_000_000
ALLOWED_STATES = {
    "ORIGINAL_NSE_QIP_PDF_CAPTURED_TEXT_IDENTITY_PASSED",
    "ORIGINAL_NSE_QIP_ACCESS_BLOCKED",
    "ORIGINAL_NSE_QIP_NOT_FOUND",
    "ORIGINAL_NSE_QIP_UNFOLLOWED_REDIRECT",
    "ORIGINAL_NSE_QIP_INVALID_PDF_OR_IDENTITY",
    "ORIGINAL_NSE_QIP_HTTP_OR_NETWORK_FAILURE",
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pdf_envelope(raw: bytes) -> bool:
    return (
        isinstance(raw, bytes)
        and 1024 <= len(raw) <= PDF_MAX_BYTES
        and raw.startswith(b"%PDF-")
        and b"%%EOF" in raw[-2048:]
    )


def _extract_pdf_pages(raw: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if len(reader.pages) != 3:
            raise ValueError("original NSE QIP PDF expected exactly three pages")
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("original QIP PDF page structure/text unavailable") from exc
    if len(pages) != 3 or any(len(page.strip()) < 50 for page in pages):
        raise ValueError("original QIP PDF pages insufficiently readable")
    return pages


def verify_qip_original(raw: bytes) -> dict[str, Any]:
    """Prove source-text identity but do not promote an investment conclusion."""
    if not _pdf_envelope(raw):
        raise ValueError("original NSE source fails PDF byte envelope")
    pages = _extract_pdf_pages(raw)
    first = re.sub(r"\s+", " ", pages[0].casefold())
    all_text = re.sub(r"\s+", " ", " ".join(pages).casefold())
    expected_tokens = (
        "30th september, 2026",
        "inoxgreen",
        "qualified",
        "institutions placement",
        "29th september, 2026",
        "41,96,02,518",
        "1,81,10,473",
        "165.65",
        "401,49,20,450",
        "419,60,25,180",
    )
    if not all(term in all_text for term in expected_tokens):
        raise ValueError("original QIP document does not match original date/capital terms")
    if not "inoxgreen" in first or "allotment" not in first:
        raise ValueError("original QIP first page issuer identity missing")
    if POST_QIP_ISSUED_SHARES - PRE_QIP_ISSUED_SHARES != QIP_ALLOTTED_SHARES:
        raise ValueError("issuer-paid-up equity share reconciliation failed")
    if abs(QIP_ALLOTTED_SHARES * ISSUE_PRICE_INR - QIP_CONSIDERATION_INR) > 0.02:
        raise ValueError("issuer share issue price/size arithmetic failed")
    return {
        "page_count": len(pages),
        "page_text_sha256": [
            hashlib.sha256(page.encode("utf-8")).hexdigest() for page in pages
        ],
        "issuer_reported_date": "2026-09-30",
        "qip_allotment_date": "2026-09-29",
        "qip_allotted_shares": QIP_ALLOTTED_SHARES,
        "pre_qip_issued_shares": PRE_QIP_ISSUED_SHARES,
        "post_qip_issued_shares": POST_QIP_ISSUED_SHARES,
        "qip_issue_price_inr": ISSUE_PRICE_INR,
        "qip_total_consideration_inr": QIP_CONSIDERATION_INR,
        "current_esop_outstanding_verified": False,
        "current_fully_diluted_shares_verified": False,
    }


def _receipt(
    status: str,
    *,
    http_status: int | None,
    raw: bytes | None,
    detail: str,
    inspected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in ALLOWED_STATES:
        raise ValueError("unsupported original QIP capture state")
    success = status == "ORIGINAL_NSE_QIP_PDF_CAPTURED_TEXT_IDENTITY_PASSED"
    if success != (raw is not None and inspected is not None):
        raise ValueError("QIP source status/bytes and semantic envelope inconsistent")
    return {
        "schema_version": 1,
        "capture_id": CASE_ID,
        "symbol": "INOXGREEN",
        "isin": "INE510W01014",
        "source_url": ORIGINAL_URL,
        "source_access_date_utc": _now(),
        "http_status": http_status,
        "state": status,
        "source_original_pdf_sha256": (
            hashlib.sha256(raw).hexdigest() if success else None
        ),
        "source_original_pdf_bytes": len(raw) if success else None,
        "source_page_text_provenance": inspected,
        "block_reason": detail,
        "original_pdf_page_image_audit_complete": False,
        "qip_original_document_allotment_identity_confirmed": success,
        "current_fully_diluted_share_count_verified": False,
        "company_net_cash_debt_adjusted_for_qip_verified": False,
        "current_stock_target_price_calculated": False,
        "equity_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def probe_nse_original(*, attempts: int = 2, sleep_seconds: float = 2.0) -> tuple[dict, bytes | None]:
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("original-source attempts must be between 1 and 3")
    if type(sleep_seconds) not in (int, float) or not 0 <= sleep_seconds <= 30:
        raise ValueError("original-source retry spacing invalid")
    status = None
    reason = "NO_OFFICIAL_SOURCE_RESPONSE"
    for index in range(attempts):
        try:
            response = requests.get(
                ORIGINAL_URL,
                headers={
                    "User-Agent": "marketlab-independent-investment-research/1.0",
                    "Accept": "application/pdf",
                },
                allow_redirects=False,
                timeout=30,
            )
            status = response.status_code
            if getattr(response, "url", ORIGINAL_URL) != ORIGINAL_URL:
                return _receipt(
                    "ORIGINAL_NSE_QIP_UNFOLLOWED_REDIRECT", http_status=status,
                    raw=None, detail="SOURCE_URL_CHANGED_NO_BYPASS"
                ), None
            if status == 200:
                raw = response.content
                try:
                    extracted = verify_qip_original(raw)
                except ValueError as exc:
                    return _receipt(
                        "ORIGINAL_NSE_QIP_INVALID_PDF_OR_IDENTITY",
                        http_status=status, raw=None, detail=str(exc)
                    ), None
                return _receipt(
                    "ORIGINAL_NSE_QIP_PDF_CAPTURED_TEXT_IDENTITY_PASSED",
                    http_status=status, raw=raw, detail="ORIGINAL_PDF_BYTES_AND_LIMITED_TEXT_IDENTITY_RETAINED",
                    inspected=extracted,
                ), raw
            if status in (401, 403, 429):
                return _receipt(
                    "ORIGINAL_NSE_QIP_ACCESS_BLOCKED",
                    http_status=status, raw=None, detail=f"HTTP_{status}_NO_ACCESS_BYPASS"
                ), None
            if status == 404:
                return _receipt(
                    "ORIGINAL_NSE_QIP_NOT_FOUND",
                    http_status=404, raw=None, detail="EXACT_ORIGINAL_NSE_ATTACHMENT_NOT_FOUND"
                ), None
            if 300 <= status < 400:
                return _receipt(
                    "ORIGINAL_NSE_QIP_UNFOLLOWED_REDIRECT",
                    http_status=status, raw=None, detail="SOURCE_REDIRECT_NOT_FOLLOWED"
                ), None
            reason = f"HTTP_{status}_OR_EMPTY"
            if status < 500:
                break
        except requests.RequestException as exc:
            reason = type(exc).__name__
        if index + 1 < attempts:
            time.sleep(sleep_seconds)
    return _receipt(
        "ORIGINAL_NSE_QIP_HTTP_OR_NETWORK_FAILURE",
        http_status=status, raw=None, detail=reason
    ), None


def save_original(root: Path, receipt: dict[str, Any], raw: bytes | None) -> None:
    if not isinstance(receipt, dict) or receipt.get("capture_id") != CASE_ID:
        raise ValueError("original QIP receipt identity mismatch")
    root.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        expected = receipt.get("source_original_pdf_sha256")
        if (
            receipt.get("state") != "ORIGINAL_NSE_QIP_PDF_CAPTURED_TEXT_IDENTITY_PASSED"
            or hashlib.sha256(raw).hexdigest() != expected
        ):
            raise ValueError("source QIP PDF does not match original receipt")
        if verify_qip_original(raw) != receipt["source_page_text_provenance"]:
            raise ValueError("original PDF QIP page terms changed")
        original = root / "raw" / "sha256" / f"{expected}.pdf"
        original.parent.mkdir(parents=True, exist_ok=True)
        if original.exists() and original.read_bytes() != raw:
            raise ValueError("immutable QIP source PDF cannot be overwritten")
        original.write_bytes(raw)
        if hashlib.sha256(original.read_bytes()).hexdigest() != expected:
            raise ValueError("original QIP PDF SHA verification after retention failed")
    elif receipt.get("source_original_pdf_sha256") is not None:
        raise ValueError("blocked original QIP source cannot claim raw PDF")
    dest = root / "capture-receipt-v1.json"
    encoded = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if dest.exists() and dest.read_text(encoding="utf-8") != encoded:
        raise ValueError("original source receipt overwrite refused")
    dest.write_text(encoded, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=2)
    args = parser.parse_args()
    result, original = probe_nse_original(
        attempts=args.attempts, sleep_seconds=args.sleep_seconds
    )
    save_original(args.out_dir, result, original)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
