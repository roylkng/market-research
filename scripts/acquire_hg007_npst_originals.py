"""Retain exact BSE NPST Q1 FY27 financial/capital-deployment originals.

Three issuer-specific filings are intentionally *different* evidence
families: 11-Aug Q1 investor presentation, June-quarter Reg32 proceeds
statement and a historical March-quarter monitoring report filed in
August. Do not label March monitoring a June monitoring audit.

HTTP block, HTML 200, unreviewed text and missing PDFs are explicit.
No bypass, redirect substitution, predicted returns or live capital.
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

CASE_ID = "HG007-P018-NPST-ORIGINAL-Q1FY27-FILING-SOURCE-BUNDLE-v1"
FILINGS = {
    "2026-08-11-investor-presentation": {
        "url": (
            "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
            "5fab053f-1334-4b70-8ba7-4325e7f07b2e.pdf"
        ),
        "dated_filing": "2026-08-11",
        "declared_reporting_period": "2026-06-30",
        "family": "INVESTOR_PRESENTATION_Q1FY27",
    },
    "2026-08-11-june-reg32-use-of-funds": {
        "url": (
            "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
            "0f52b8e1-9062-4b5a-be7c-ef0206f32489.pdf"
        ),
        "dated_filing": "2026-08-11",
        "declared_reporting_period": "2026-06-30",
        "family": "REG32_JUNE_2026_VARIATION_AND_USE_OF_PROCEEDS",
    },
    "2026-08-11-march-monitoring-agency": {
        "url": (
            "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
            "32b88b70-da2a-4109-8187-d3a51bb7b860.pdf"
        ),
        "dated_filing": "2026-08-11",
        "declared_reporting_period": "2026-03-31",
        "family": "MONITORING_AGENCY_PRIOR_MARCH_QUARTER",
    },
}
MIN_BYTES = 700
MAX_BYTES = 32_000_000
MAX_PAGES = 180


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pdf_envelope(raw: object) -> bool:
    return (
        isinstance(raw, bytes)
        and MIN_BYTES <= len(raw) <= MAX_BYTES
        and raw.startswith(b"%PDF-")
        and b"%%EOF" in raw[-2048:]
    )


def _pdf_page_evidence(raw: bytes) -> dict[str, Any]:
    if not _pdf_envelope(raw):
        raise ValueError("original BSE attachment is not a bounded PDF byte envelope")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        count = len(reader.pages)
        if not 1 <= count <= MAX_PAGES:
            raise ValueError("unexpected NPST original page count")
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
    except (PdfReadError, OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("original BSE NPST PDF page-tree/text extraction failed") from exc
    normalized = " ".join(" ".join(pages).casefold().split())
    issuer_text_match = (
        "network people services" in normalized
        or "npst" in normalized
    )
    period_june_text_present = (
        "30 june 2026" in normalized
        or "30th june 2026" in normalized
        or "30.06.2026" in normalized
        or "30-06-2026" in normalized
        or "june 30, 2026" in normalized
        or "q1 fy27" in normalized
        or "q1fy27" in normalized
    )
    period_march_text_present = (
        "march 31, 2026" in normalized
        or "31 march 2026" in normalized
        or "31st march 2026" in normalized
        or "31-03-2026" in normalized
        or "31.03.2026" in normalized
    )
    return {
        "page_count": count,
        "page_text_sha256": [
            hashlib.sha256(text.encode("utf-8")).hexdigest() for text in pages
        ],
        "page_text_nonempty_count": sum(bool(text.strip()) for text in pages),
        "issuer_name_mentioned_in_extracted_text": issuer_text_match,
        "june_2026_reporting_date_text_found": period_june_text_present,
        "march_2026_reporting_date_text_found": period_march_text_present,
        "original_document_full_economic_review_complete": False,
    }


def acquire_original(
    filing_id: str, *, attempts: int = 2, sleep_seconds: float = 2
) -> tuple[dict[str, Any], bytes | None]:
    if filing_id not in FILINGS:
        raise ValueError("only three predeclared original NPST BSE sources allowed")
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("original source attempts must be 1-3")
    if type(sleep_seconds) not in (int, float) or not 0 <= sleep_seconds <= 30:
        raise ValueError("bounded retry delay must be 0-30 sec")
    source = FILINGS[filing_id]
    last_http = None
    reason = "OFFICIAL_SOURCE_UNAVAILABLE"
    inspection = None
    raw = None
    state = "ORIGINAL_SOURCE_HTTP_OR_NETWORK_FAILED"
    for attempt in range(attempts):
        try:
            response = requests.get(
                source["url"],
                timeout=35,
                headers={
                    "User-Agent": "marketlab-source-research/1.0",
                    "Accept": "application/pdf",
                },
                allow_redirects=False,
            )
            last_http = response.status_code
            if getattr(response, "url", source["url"]) != source["url"]:
                state, reason = "ORIGINAL_SOURCE_REDIRECT_UNFOLLOWED", "SOURCE_URL_CHANGED"
                break
            if last_http == 200:
                try:
                    inspection = _pdf_page_evidence(response.content)
                except ValueError as exc:
                    state, reason = "ORIGINAL_PDF_NOT_VERIFIABLE", str(exc)
                    break
                raw = response.content
                state = "ORIGINAL_PDF_BYTE_AND_PAGE_STRUCTURE_CAPTURED"
                reason = "EXACT_SOURCE_BYTES_CAPTURED_NO_ECONOMIC_FACT_APPROVAL"
                break
            if last_http in (401, 403, 429):
                state, reason = "ORIGINAL_SOURCE_ACCESS_BLOCKED", f"HTTP_{last_http}_NO_BYPASS"
                break
            if last_http == 404:
                state, reason = "ORIGINAL_SOURCE_NOT_FOUND", "EXACT_SOURCE_HTTP_404"
                break
            if 300 <= last_http < 400:
                state, reason = "ORIGINAL_SOURCE_REDIRECT_UNFOLLOWED", "REDIRECT_NOT_FOLLOWED"
                break
            reason = f"HTTP_{last_http}_OR_EMPTY_BODY"
            if last_http < 500:
                break
        except requests.RequestException as exc:
            reason = type(exc).__name__
        if attempt + 1 < attempts:
            time.sleep(sleep_seconds)
    success = raw is not None and inspection is not None
    if success != (state == "ORIGINAL_PDF_BYTE_AND_PAGE_STRUCTURE_CAPTURED"):
        raise ValueError("captured raw NPST bytes/source state inconsistency")
    receipt = {
        "schema_version": 1,
        "case_id": CASE_ID,
        "symbol": "NPST",
        "isin": "INE0FFK01017",
        "source_kind": filing_id,
        "filing_family": source["family"],
        "original_bse_url": source["url"],
        "source_declared_filing_date": source["dated_filing"],
        "source_declared_reporting_period": source["declared_reporting_period"],
        "captured_at_utc": _now(),
        "status": state,
        "http_status": last_http,
        "original_raw_sha256": hashlib.sha256(raw).hexdigest() if success else None,
        "original_raw_byte_count": len(raw) if success else None,
        "original_pdf_page_evidence": inspection,
        "failure_or_review_reason": reason,
        "source_issuer_text_reconciled": (
            inspection["issuer_name_mentioned_in_extracted_text"] if success else False
        ),
        "source_reporting_period_text_reconciled": (
            inspection[
                "june_2026_reporting_date_text_found"
                if source["declared_reporting_period"] == "2026-06-30"
                else "march_2026_reporting_date_text_found"
            ]
            if success else False
        ),
        "original_pdf_text_economic_facts_approved": False,
        "monitoring_march_is_not_q1_june_evidence": (
            source["family"] == "MONITORING_AGENCY_PRIOR_MARCH_QUARTER"
        ),
        "unutilized_proceeds_reported_value_verified": False,
        "original_q1fy27_ebitda_verified": False,
        "incremental_ebitda_attributable_to_unspent_capital_verified": False,
        "current_fd_equity_and_share_price_verified": False,
        "company_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return receipt, raw


def save_original(root: Path, receipt: dict[str, Any], raw: bytes | None) -> None:
    filing_id = receipt.get("source_kind")
    if receipt.get("case_id") != CASE_ID or filing_id not in FILINGS:
        raise ValueError("unrecognized original NPST filing/source ID")
    if receipt.get("original_bse_url") != FILINGS[filing_id]["url"]:
        raise ValueError("original BSE filing URL was substituted")
    root.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        digest = hashlib.sha256(raw).hexdigest()
        if (
            receipt.get("status") != "ORIGINAL_PDF_BYTE_AND_PAGE_STRUCTURE_CAPTURED"
            or receipt.get("original_raw_sha256") != digest
            or receipt.get("original_pdf_page_evidence") != _pdf_page_evidence(raw)
        ):
            raise ValueError("NPST original PDF/receipt source content mismatch")
        target = root / "raw" / "sha256" / f"{digest}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != raw:
            raise ValueError("immutable NPST PDF source already differs")
        target.write_bytes(raw)
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("original NPST PDF SHA changed on disk")
    elif receipt.get("original_raw_sha256") is not None:
        raise ValueError("blocked original source cannot claim hash")
    receipt_path = root / "original-receipt-v1.json"
    encoded = json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if receipt_path.exists() and receipt_path.read_text(encoding="utf-8") != encoded:
        raise ValueError("immutable NPST original source receipt cannot be overwritten")
    receipt_path.write_text(encoded, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True, choices=sorted(FILINGS))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=2)
    args = parser.parse_args()
    receipt, raw = acquire_original(
        args.source_id, attempts=args.attempts, sleep_seconds=args.sleep_seconds
    )
    save_original(args.out_dir, receipt, raw)
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
