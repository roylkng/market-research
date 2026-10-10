"""Acquire *exact* BSE original Oct7 WWIL press-release PDF by its filing ID.

Do not treat a successful byte download as financial statement verification,
realized EBITDA or legal BTA closing. Do not evade HTTP access restrictions.
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

DOCUMENT_ID = "HG007-P011-WWIL-2026-10-07-ORIGINAL-BSE-PRESS-v1"
ORIGINAL_BSE_PDF = (
    "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
    "e588eec4-0a4f-46f7-9cac-be11142c492a.pdf"
)
PRESS_BSE_SOURCE = (
    "https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?"
    "Pname=e588eec4-0a4f-46f7-9cac-be11142c492a.pdf"
)
MAX_PDF_BYTES = 8_000_000
STATUSES = frozenset({
    "BSE_ORIGINAL_PRESS_PDF_CAPTURED_UNREVIEWED",
    "BSE_OFFICIAL_DOCUMENT_ACCESS_BLOCKED",
    "BSE_OFFICIAL_DOCUMENT_NOT_FOUND",
    "BSE_UNFOLLOWED_REDIRECT",
    "BSE_NONPDF_SOURCE_BYTES",
    "BSE_NETWORK_OR_SERVER_ERROR",
})


def _stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pdf_envelope(raw: object) -> bool:
    return (
        isinstance(raw, bytes)
        and 512 <= len(raw) <= MAX_PDF_BYTES
        and raw.startswith(b"%PDF-")
        and b"%%EOF" in raw[-2048:]
    )


def _receipt(
    status: str,
    *,
    http_status: int | None,
    original_raw: bytes | None,
    reason: str,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError("unexpected WWIL BSE press source state")
    success = status == "BSE_ORIGINAL_PRESS_PDF_CAPTURED_UNREVIEWED"
    if success != (isinstance(original_raw, bytes) and _pdf_envelope(original_raw)):
        raise ValueError("original PDF source state mismatches byte envelope")
    return {
        "schema_version": 1,
        "document_id": DOCUMENT_ID,
        "document_type": "ORIGINAL_ISSUER_REG30_PRESS_RELEASE_PDF_UNREVIEWED",
        "issuer_symbol": "INOXGREEN",
        "reported_press_release_date": "2026-10-07",
        "official_original_source_url": ORIGINAL_BSE_PDF,
        "official_bse_annpdfopen_reference": PRESS_BSE_SOURCE,
        "retrieved_at_utc": _stamp(),
        "source_status": status,
        "http_status": http_status,
        "source_original_pdf_sha256": (
            hashlib.sha256(original_raw).hexdigest() if success else None
        ),
        "source_original_pdf_byte_count": (
            len(original_raw) if success else None
        ),
        "source_fetch_reason": reason,
        "all_pdf_pages_read_and_text_hash_verified": False,
        "management_2x_post_synergy_ebitda_multiple_semantically_approved": False,
        "wwil_historical_ebitda_source_verified": False,
        "deal_consideration_is_equivalent_to_enterprise_value_verified": False,
        "wwil_legal_transfer_completed_verified": False,
        "minority_equity_rights_and_dilution_verified": False,
        "stock_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def acquire_original_press(
    *, attempts: int = 2, delay_seconds: float = 3.0
) -> tuple[dict[str, Any], bytes | None]:
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("BSE source attempts must be in range 1..3")
    if type(delay_seconds) not in (int, float) or not 0 <= delay_seconds <= 30:
        raise ValueError("bounded BSE retry delay invalid")
    status: int | None = None
    reason = "NO_VERIFIED_BSE_RESPONSE"
    for attempt in range(attempts):
        try:
            response = requests.get(
                ORIGINAL_BSE_PDF,
                timeout=30,
                allow_redirects=False,
                headers={
                    "User-Agent": "marketlab-hg007-official-original/1.0",
                    "Accept": "application/pdf",
                },
            )
            status = response.status_code
            if getattr(response, "url", ORIGINAL_BSE_PDF) != ORIGINAL_BSE_PDF:
                return _receipt(
                    "BSE_UNFOLLOWED_REDIRECT", http_status=status,
                    original_raw=None, reason="UNEXPECTED_FINAL_RESPONSE_URL"
                ), None
            if status == 200:
                raw = response.content
                if not _pdf_envelope(raw):
                    return _receipt(
                        "BSE_NONPDF_SOURCE_BYTES", http_status=status,
                        original_raw=None, reason="PDF_HEADER_TRAILER_OR_SIZE_INVALID",
                    ), None
                return _receipt(
                    "BSE_ORIGINAL_PRESS_PDF_CAPTURED_UNREVIEWED",
                    http_status=status, original_raw=raw,
                    reason="EXACT_ORIGINAL_BYTES_RETAINED_TEXT_PAGE_AUDIT_PENDING",
                ), raw
            if status in (401, 403, 429):
                return _receipt(
                    "BSE_OFFICIAL_DOCUMENT_ACCESS_BLOCKED",
                    http_status=status, original_raw=None,
                    reason=f"HTTP_{status}_NO_ACCESS_BYPASS",
                ), None
            if status == 404:
                return _receipt(
                    "BSE_OFFICIAL_DOCUMENT_NOT_FOUND",
                    http_status=status, original_raw=None,
                    reason="EXACT_BSE_ORIGINAL_ID_NOT_AVAILABLE",
                ), None
            if 300 <= status < 400:
                return _receipt(
                    "BSE_UNFOLLOWED_REDIRECT", http_status=status,
                    original_raw=None, reason="NO_UNVERIFIED_REDIRECT",
                ), None
            reason = f"HTTP_{status}"
            if status < 500:
                break
        except requests.RequestException as exc:
            reason = type(exc).__name__
        if attempt+1 < attempts:
            time.sleep(delay_seconds)
    return _receipt(
        "BSE_NETWORK_OR_SERVER_ERROR", http_status=status,
        original_raw=None, reason=reason,
    ), None


def write_source(
    path: Path,
    *,
    receipt: dict[str, Any],
    original: bytes | None,
) -> None:
    if receipt.get("document_id") != DOCUMENT_ID:
        raise ValueError("source document ID changed")
    if original is not None:
        sha = hashlib.sha256(original).hexdigest()
        if (
            not _pdf_envelope(original)
            or receipt.get("source_original_pdf_sha256") != sha
            or receipt.get("source_original_pdf_byte_count") != len(original)
            or receipt.get("source_status") != "BSE_ORIGINAL_PRESS_PDF_CAPTURED_UNREVIEWED"
        ):
            raise ValueError("original PDF byte or SHA evidence inconsistent")
        filename = path / "raw" / "sha256" / f"{sha}.pdf"
        filename.parent.mkdir(parents=True, exist_ok=True)
        if filename.exists() and filename.read_bytes() != original:
            raise ValueError("original BSE press release hash collision")
        filename.write_bytes(original)
        if hashlib.sha256(filename.read_bytes()).hexdigest() != sha:
            raise ValueError("original PDF retention digest mismatch")
    else:
        if receipt.get("source_original_pdf_sha256") is not None:
            raise ValueError("unavailable original cannot have an original PDF SHA")
    path.mkdir(parents=True, exist_ok=True)
    (path / "source-receipt-v1.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    receipt, raw = acquire_original_press()
    write_source(args.out_dir, receipt=receipt, original=raw)
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
