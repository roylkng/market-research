"""Capture exact NSE Aug-11 NPST board outcome, quarterly review, and monitoring.

A source-only original PDF acquisition. Previous separate March monitoring
attachment was NOT June funding evidence; the official board outcome names
June monitoring and Q1 consolidated/standalone limited financial review.
Never relabel page captures as approved audit/cash/earnings/share valuation.
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

CAPTURE_ID = "HG007-P023-NPST-2026-JUNE-BOARD-OUTCOME-NSE-SOURCE-v1"
SOURCE_URL = (
    "https://nsearchives.nseindia.com/corporate/"
    "NPST_11082026193857_BM_Outcome-11082026_signed.pdf"
)
SOURCE_ROOT = Path("research/hg007/npst-aug2026-originals/2026-08-11-board-outcome-nse")
MIN_SOURCE_BYTES = 1_000
MAX_SOURCE_BYTES = 30_000_000
MAX_PAGES = 160
MAX_PAGE_CHARS = 160_000
MIN_TEXT_PAGE_COUNT = 3
REPORT_DATE = "2026-06-30"
ISSUER_ISIN = "INE0FFK01017"
VALID_STATUS = {
    "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_CAPTURED_TEXT_IDENTITIES_PASSED",
    "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_HTTP_BLOCKED",
    "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_NOT_FOUND",
    "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_UNFOLLOWED_REDIRECT",
    "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_BAD_PDF_OR_IDENTITY",
    "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_HTTP_OR_NETWORK_FAILURE",
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pdf_envelope(raw: object) -> bool:
    return (
        isinstance(raw, bytes)
        and MIN_SOURCE_BYTES <= len(raw) <= MAX_SOURCE_BYTES
        and raw.startswith(b"%PDF-")
        and b"%%EOF" in raw[-2048:]
    )


def original_page_evidence(raw: bytes) -> dict[str, Any]:
    """Conservative issuer/date/period identity, not a financial statement audit."""
    if not _pdf_envelope(raw):
        raise ValueError("board outcome failed exact PDF byte envelope")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        pages = len(reader.pages)
        if not 3 <= pages <= MAX_PAGES:
            raise ValueError("unexpected board outcome PDF page count")
        text_pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise ValueError("original board PDF page-tree/text reading failed") from exc
    if any(len(page) > MAX_PAGE_CHARS for page in text_pages):
        raise ValueError("original board source page text exceeds bounded size")
    nonempty = sum(len(page.strip()) >= 20 for page in text_pages)
    if nonempty < MIN_TEXT_PAGE_COUNT:
        raise ValueError("original board PDF lacks sufficient source text")
    normalized = " ".join(" ".join(text_pages).casefold().split())
    first = " ".join(text_pages[0].casefold().split())
    anchors = {
        "issuer": (
            ("network people services" in normalized or "npst" in normalized)
            and (ISSUER_ISIN.casefold() in normalized)
        ),
        "aug11_board_outcome": (
            "august 11, 2026" in normalized or "11.08.2026" in normalized
        ) and "board" in normalized,
        "june_2026_report": any(
            v in normalized
            for v in ("june 30, 2026", "30 june 2026", "30.06.2026", "30th june 2026")
        ),
        "financials_standalone_consolidated": (
            "standalone" in normalized and "consolidated" in normalized
        ),
        "financial_results_limited_review": (
            "limited review" in normalized
        ),
        "june_monitoring": any(
            "monitoring agency" in " ".join(page.casefold().split())
            and "june 30, 2026" in " ".join(page.casefold().split())
            for page in text_pages
        ),
        "original_cover_npst": (
            ISSUER_ISIN.casefold() in first
            and ("npst" in first or "network people services" in first)
        ),
    }
    if not all(anchors.values()):
        missing = sorted(k for k, val in anchors.items() if not val)
        raise ValueError(f"original NSE board outcome identity unproven: {missing}")
    page_ref_keywords = (
        "monitoring agency", "limited review", "consolidated",
        "other income", "other expenses", "cash and cash equivalents",
        "deviation", "utilisation", "utilization", "300.0041",
        "264.36", "35.6409", "careratings", "care ratings",
    )
    return {
        "issuer": "Network People Services Technologies Limited",
        "isin": ISSUER_ISIN,
        "reporting_quarter": REPORT_DATE,
        "filing_date": "2026-08-11",
        "original_document_page_count": pages,
        "source_text_pages_minimum20_chars": nonempty,
        "page_text_sha256": [
            hashlib.sha256(text.encode("utf-8")).hexdigest() for text in text_pages
        ],
        "identity_gates": anchors,
        "source_review_routing_pages": {
            term: [i + 1 for i, page in enumerate(text_pages) if term in page.casefold()]
            for term in page_ref_keywords
        },
        "independent_monetary_fact_semantic_audit_completed": False,
        "monitoring_agency_june_quarter_scope_original_text_identified": True,
        "reg32_unutilized_amount_is_verified_bank_cash": False,
        "consolidated_income_quality_audited": False,
        "separate_march_monitoring_source_relabelled_as_june": False,
    }


def _receipt(
    *,
    status: str,
    http: int | None,
    original_bytes: bytes | None,
    evidence: dict[str, Any] | None,
    reason: str,
) -> dict[str, Any]:
    if status not in VALID_STATUS:
        raise ValueError("invalid official board source status")
    ok = status == "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_CAPTURED_TEXT_IDENTITIES_PASSED"
    if ok != (original_bytes is not None and evidence is not None):
        raise ValueError("original board source status and bytes disagree")
    return {
        "schema_version": 1,
        "source_id": CAPTURE_ID,
        "issuer": "Network People Services Technologies Limited",
        "symbol": "NPST",
        "isin": ISSUER_ISIN,
        "quarter_end": REPORT_DATE,
        "filing_date": "2026-08-11",
        "source_url": SOURCE_URL,
        "captured_at_utc": _now(),
        "status": status,
        "http_status": http,
        "original_pdf_sha256": (
            hashlib.sha256(original_bytes).hexdigest() if ok else None
        ),
        "original_pdf_byte_count": len(original_bytes) if ok else None,
        "original_page_identity_evidence": evidence,
        "reason": reason,
        "original_pdf_visual_page_review_complete": False,
        "independent_june_quarter_monitoring_cash_verification_complete": False,
        "financial_statement_limited_review_semantic_analysis_complete": False,
        "reported_reg32_unused_proceeds_are_bank_cash_verified": False,
        "current_fully_diluted_share_count_verified": False,
        "updated_company_expected_return_calculated": False,
        "investment_recommendation_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def acquire_original_board_outcome(
    *, attempts: int = 2, sleep_seconds: float = 3.0
) -> tuple[dict[str, Any], bytes | None]:
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("NSE source requests bounded to 1-3")
    if type(sleep_seconds) not in (int, float) or not 0 <= sleep_seconds <= 30:
        raise ValueError("source retry delay must be 0-30 sec")
    last_http: int | None = None
    last_error = "OFFICIAL_NSE_ATTACHMENT_NO_RESPONSE"
    for attempt in range(attempts):
        try:
            response = requests.get(
                SOURCE_URL,
                timeout=45,
                headers={"User-Agent": "marketlab-independent-equity-research/1.0", "Accept": "application/pdf"},
                allow_redirects=False,
                stream=True,
            )
            last_http = response.status_code
            try:
                if getattr(response, "url", SOURCE_URL) != SOURCE_URL:
                    return _receipt(
                        status="ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_UNFOLLOWED_REDIRECT",
                        http=last_http, original_bytes=None, evidence=None,
                        reason="ORIGINAL_SOURCE_URL_CHANGED_NO_REDIRECT_BYPASS",
                    ), None
                if last_http == 200:
                    chunks = []
                    total = 0
                    for chunk in response.iter_content(chunk_size=128 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > MAX_SOURCE_BYTES:
                            return _receipt(
                                status="ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_BAD_PDF_OR_IDENTITY",
                                http=200, original_bytes=None, evidence=None,
                                reason="ORIGINAL_PDF_EXCEEDS_BOUNDED_MAX_BYTES",
                            ), None
                        chunks.append(chunk)
                    raw = b"".join(chunks)
                    try:
                        checked = original_page_evidence(raw)
                    except ValueError as exc:
                        return _receipt(
                            status="ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_BAD_PDF_OR_IDENTITY",
                            http=200, original_bytes=None, evidence=None,
                            reason=f"UNVERIFIED_PDF_IDENTITY_{type(exc).__name__}: {exc}",
                        ), None
                    return _receipt(
                        status="ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_CAPTURED_TEXT_IDENTITIES_PASSED",
                        http=200, original_bytes=raw, evidence=checked,
                        reason="ORIGINAL_SOURCE_TEXT_IDENTITY_ONLY_NO_ECONOMIC_AUDIT",
                    ), raw
                if last_http in (401, 403, 429):
                    return _receipt(
                        status="ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_HTTP_BLOCKED",
                        http=last_http, original_bytes=None, evidence=None,
                        reason=f"HTTP_{last_http}_NO_SOURCE_ACCESS_BYPASS",
                    ), None
                if last_http == 404:
                    return _receipt(
                        status="ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_NOT_FOUND",
                        http=404, original_bytes=None, evidence=None,
                        reason="EXACT_ORIGINAL_NSE_ATTACHMENT_NOT_FOUND",
                    ), None
                if last_http in (301, 302, 303, 307, 308):
                    return _receipt(
                        status="ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_UNFOLLOWED_REDIRECT",
                        http=last_http, original_bytes=None, evidence=None,
                        reason="HTTP_REDIRECT_NOT_FOLLOWED",
                    ), None
                last_error = f"HTTP_{last_http}_UNEXPECTED"
                if last_http < 500:
                    break
            finally:
                response.close()
        except requests.RequestException as exc:
            last_error = type(exc).__name__
        if attempt + 1 < attempts:
            time.sleep(sleep_seconds)
    return _receipt(
        status="ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_HTTP_OR_NETWORK_FAILURE",
        http=last_http, original_bytes=None, evidence=None, reason=last_error,
    ), None


def retain_source(root: Path, receipt: dict[str, Any], original: bytes | None) -> None:
    if not isinstance(receipt, dict) or receipt.get("source_id") != CAPTURE_ID:
        raise ValueError("board source receipt identity mismatch")
    root.mkdir(parents=True, exist_ok=True)
    if original is not None:
        if (
            receipt.get("status")
            != "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_CAPTURED_TEXT_IDENTITIES_PASSED"
            or receipt.get("original_pdf_sha256")
            != hashlib.sha256(original).hexdigest()
            or receipt.get("original_page_identity_evidence")
            != original_page_evidence(original)
        ):
            raise ValueError("original board outcome source PDF mismatches receipt")
        original_path = root / "raw" / "sha256" / f"{receipt['original_pdf_sha256']}.pdf"
        original_path.parent.mkdir(parents=True, exist_ok=True)
        if original_path.exists() and original_path.read_bytes() != original:
            raise ValueError("original NSE PDF SHA collision, refuse overwrite")
        original_path.write_bytes(original)
        if hashlib.sha256(original_path.read_bytes()).hexdigest() != receipt["original_pdf_sha256"]:
            raise ValueError("original NSE retained PDF SHA mismatch")
    elif receipt.get("original_pdf_sha256") is not None:
        raise ValueError("blocked official PDF must not provide a digest")
    receipt_path = root / "source-receipt-v1.json"
    encoded = json.dumps(
        receipt, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if receipt_path.exists() and receipt_path.read_text(encoding="utf-8") != encoded:
        raise ValueError("original source receipt is immutable")
    receipt_path.write_text(encoded, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=3.0)
    args = parser.parse_args()
    receipt, original = acquire_original_board_outcome(
        attempts=args.attempts, sleep_seconds=args.sleep_seconds
    )
    retain_source(args.out_dir, receipt, original)
    print(json.dumps({
        "source_id": receipt["source_id"],
        "status": receipt["status"],
        "http_status": receipt["http_status"],
        "original_sha256": receipt["original_pdf_sha256"],
        "pdf_byte_count": receipt["original_pdf_byte_count"],
        "page_count": (receipt["original_page_identity_evidence"] or {}).get(
            "original_document_page_count"
        ),
        "monitoring_agency_report_independently_reviewed": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
