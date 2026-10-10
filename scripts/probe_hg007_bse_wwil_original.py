"""Bounded original BSE attachment acquisition for provisional HG007 WWIL research.

A PDF byte capture is not original-page semantic approval, transfer
completion, normalized WWIL EBITDA, nor permission to value INOXGREEN.
Never evade BSE HTTP 403, follow unapproved redirects, or invent source bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

CASE_ID = "HG007-P003-INOXGREEN-WWIL-ORIGINAL-BSE-SOURCE-v1"
ORIGINAL_BSE_URL = (
    "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
    "d3241df5-32e2-4476-8075-bb5ed130e697.pdf"
)
MAX_BYTES = 15_000_000
MAX_ATTEMPTS = 3
SOURCE_STATES = {
    "PDF_SOURCE_BYTES_CAPTURED_NOT_SEMANTICALLY_AUDITED",
    "ORIGINAL_ATTACHMENT_ACCESS_BLOCKED",
    "OFFICIAL_ATTACHMENT_UNAVAILABLE",
    "UNFOLLOWED_REDIRECT",
    "HTTP_OR_CONTENT_FAILURE",
    "NOT_A_VERIFIABLE_PDF_BYTE_ENVELOPE",
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pdf_byte_envelope(raw: bytes) -> bool:
    """Minimal safety envelope, NOT full document authenticity or PDF parsing."""
    if not isinstance(raw, bytes) or not 512 <= len(raw) <= MAX_BYTES:
        return False
    if not raw.startswith(b"%PDF-"):
        return False
    return b"%%EOF" in raw[-2048:]


def _attempt_result(
    *,
    status: str,
    http_status: int | None,
    source_sha256: str | None,
    byte_count: int | None,
    reason: str,
    captured_at_utc: str,
) -> dict[str, Any]:
    if status not in SOURCE_STATES:
        raise ValueError("unsupported WWIL original-source status")
    return {
        "schema_version": 1,
        "case_id": CASE_ID,
        "issuer": "Inox Green Energy Services Limited",
        "listed_symbol": "INOXGREEN",
        "reported_disclosure_date": "2026-10-07",
        "original_source_url": ORIGINAL_BSE_URL,
        "captured_at_utc": captured_at_utc,
        "state": status,
        "http_status": http_status,
        "original_pdf_sha256": source_sha256,
        "original_pdf_byte_count": byte_count,
        "source_byte_envelope_checked": source_sha256 is not None,
        "source_pdf_full_structure_validated": False,
        "original_page_semantic_audit_approved": False,
        "wwil_transfer_conditions_precedent_verified_satisfied": False,
        "vibhav_actual_conversion_classes_and_prices_verified": False,
        "wwil_normalized_ebitda_verified": False,
        "completion_probability_calculated": False,
        "expected_return_calculated": False,
        "stock_price_target_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "reason": reason,
    }


def acquire_original_bse_pdf(
    *,
    attempts: int = 2,
    sleep_seconds: float = 3.0,
) -> tuple[dict[str, Any], bytes | None]:
    if type(attempts) is not int or attempts < 1 or attempts > MAX_ATTEMPTS:
        raise ValueError("BSE attempts must be an integer between 1 and 3")
    if type(sleep_seconds) not in (float, int) or not 0 <= sleep_seconds <= 30:
        raise ValueError("BSE retry pause outside allowed range")
    last_http: int | None = None
    last_reason = "NO_COMPLETE_OFFICIAL_RESPONSE"
    for attempt in range(attempts):
        try:
            response = requests.get(
                ORIGINAL_BSE_URL,
                timeout=30,
                headers={"User-Agent": "marketlab-hg007-source-probe/1.0", "Accept": "application/pdf"},
                allow_redirects=False,
            )
            last_http = response.status_code
            if getattr(response, "url", ORIGINAL_BSE_URL) != ORIGINAL_BSE_URL:
                return (
                    _attempt_result(
                        status="UNFOLLOWED_REDIRECT",
                        http_status=last_http, source_sha256=None,
                        byte_count=None, reason="REQUEST_URL_CHANGED_OR_UNEXPECTED_HOST",
                        captured_at_utc=_now(),
                    ),
                    None,
                )
            if response.status_code == 200:
                raw = response.content
                if not _pdf_byte_envelope(raw):
                    return (
                        _attempt_result(
                            status="NOT_A_VERIFIABLE_PDF_BYTE_ENVELOPE",
                            http_status=200, source_sha256=None,
                            byte_count=None, reason="PDF_SIGNATURE_OR_TRAILER_OR_SIZE_INVALID",
                            captured_at_utc=_now(),
                        ),
                        None,
                    )
                sha = hashlib.sha256(raw).hexdigest()
                return (
                    _attempt_result(
                        status="PDF_SOURCE_BYTES_CAPTURED_NOT_SEMANTICALLY_AUDITED",
                        http_status=200, source_sha256=sha,
                        byte_count=len(raw),
                        reason="ORIGINAL_BYTES_RETAINED_ORIGINAL_PAGES_NOT_YET_REVIEWED",
                        captured_at_utc=_now(),
                    ),
                    raw,
                )
            if response.status_code in (401, 403, 429):
                return (
                    _attempt_result(
                        status="ORIGINAL_ATTACHMENT_ACCESS_BLOCKED",
                        http_status=last_http, source_sha256=None,
                        byte_count=None, reason=f"HTTP_{last_http}_NO_ACCESS_BYPASS",
                        captured_at_utc=_now(),
                    ),
                    None,
                )
            if response.status_code == 404:
                return (
                    _attempt_result(
                        status="OFFICIAL_ATTACHMENT_UNAVAILABLE",
                        http_status=404, source_sha256=None,
                        byte_count=None, reason="EXACT_ORIGINAL_ATTACHMENT_HTTP_404",
                        captured_at_utc=_now(),
                    ),
                    None,
                )
            if 300 <= response.status_code < 400:
                return (
                    _attempt_result(
                        status="UNFOLLOWED_REDIRECT",
                        http_status=last_http, source_sha256=None,
                        byte_count=None, reason="BSE_REDIRECT_NOT_FOLLOWED",
                        captured_at_utc=_now(),
                    ),
                    None,
                )
            last_reason = f"HTTP_{last_http}"
            if last_http < 500:
                break
        except requests.RequestException as exc:
            last_reason = type(exc).__name__
        if attempt + 1 < attempts:
            time.sleep(sleep_seconds)
    return (
        _attempt_result(
            status="HTTP_OR_CONTENT_FAILURE",
            http_status=last_http, source_sha256=None,
            byte_count=None, reason=last_reason, captured_at_utc=_now(),
        ),
        None,
    )


def retain_original_source(root: Path, receipt: dict[str, Any], raw: bytes | None) -> None:
    """Materialize only exact successful originals plus an honest receipt."""
    if not isinstance(receipt, dict) or receipt.get("case_id") != CASE_ID:
        raise ValueError("unrecognized source receipt")
    root.mkdir(parents=True, exist_ok=True)
    if raw is None:
        if receipt.get("original_pdf_sha256") is not None:
            raise ValueError("blocked original source cannot have PDF digest")
    else:
        if receipt.get("state") != "PDF_SOURCE_BYTES_CAPTURED_NOT_SEMANTICALLY_AUDITED":
            raise ValueError("only recognized original PDF bytes may be retained")
        digest = hashlib.sha256(raw).hexdigest()
        if not _pdf_byte_envelope(raw) or digest != receipt.get("original_pdf_sha256"):
            raise ValueError("original PDF envelope/bytes disagree with source receipt")
        exact = root / "original-raw" / "sha256" / f"{digest}.pdf"
        exact.parent.mkdir(parents=True, exist_ok=True)
        if exact.exists() and exact.read_bytes() != raw:
            raise ValueError("immutable original PDF raw digest collision")
        exact.write_bytes(raw)
        if hashlib.sha256(exact.read_bytes()).hexdigest() != digest:
            raise ValueError("original PDF retention hash check failed")
    (root / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=3)
    args = parser.parse_args()
    receipt, raw = acquire_original_bse_pdf(
        attempts=args.attempts, sleep_seconds=args.sleep_seconds
    )
    retain_original_source(args.out_dir, receipt, raw)
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
