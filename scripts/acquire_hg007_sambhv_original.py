"""Capture Sambhv's original 3-Aug-2026 Q1 FY27 investor presentation.

The 0.36-MMTPA ₹810cr steel coil project and the 25MW ₹125cr captive
plant appear as distinct roadmap investments. Their economic dependency
must be examined before assigning either CAPEX to a 50% equity-upside
scenario. Source-byte capture is not proof either asset is commissioned.
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

CASE_ID = "HG007-P016-SAMBHV-Q1FY27-ORIGINAL-PHASE1-CAPEX-v1"
ORIGINAL_URL = (
    "https://www.sambhv.com/uploads/pdf/investors/"
    "financial-performance/results/2026-2027/Investor-Presentation.pdf"
)
MIN_BYTES = 120_000
MAX_BYTES = 16_000_000
PAGE_COUNT = 43
ROADMAP_PAGE_ONE_BASED = 9
SOURCE_KIND = "ORIGINAL_ISSUER_HOSTED_Q1FY27_PDF"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pages(raw: bytes) -> list[str]:
    if (
        not isinstance(raw, bytes)
        or not MIN_BYTES <= len(raw) <= MAX_BYTES
        or not raw.startswith(b"%PDF-")
        or b"%%EOF" not in raw[-2048:]
    ):
        raise ValueError("original issuer investor PDF signature/size invalid")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if len(reader.pages) != PAGE_COUNT:
            raise ValueError("original Sambhv Q1FY27 PDF changed page count")
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, OSError, KeyError, ValueError, TypeError) as exc:
        raise ValueError("original Q1FY27 PDF page text extraction failed") from exc
    return pages


def verify_original_issuer_roadmap(raw: bytes) -> dict[str, Any]:
    pages = _pages(raw)
    if len(pages) != PAGE_COUNT:
        raise ValueError("source PDF page count mismatch")
    intro = re.sub(r"\s+", " ", " ".join(pages[:2]).casefold())
    roadmap = re.sub(r"\s+", " ", pages[ROADMAP_PAGE_ONE_BASED - 1].casefold())
    if "sambhv steel tubes" not in intro or "august 03, 2026" not in intro:
        raise ValueError("original Sambhv investor presentation issuer/date mismatch")
    required = (
        "future roadmap", "0.36", "8,100", "25 mw", "1,250",
        "q4fy27", "commissioning", "1.2",
    )
    for token in required:
        if token not in roadmap:
            raise ValueError(f"original Phase I roadmap page lacks exact CAPEX token: {token}")
    if not (roadmap.index("8,100") < roadmap.index("1,250")):
        raise ValueError("steel and separate 25MW roadmap line order changed")
    return {
        "page_count": PAGE_COUNT,
        "roadmap_page_number": ROADMAP_PAGE_ONE_BASED,
        "roadmap_text_sha256": hashlib.sha256(
            pages[ROADMAP_PAGE_ONE_BASED - 1].encode()
        ).hexdigest(),
        "original_all_page_text_sha256": [
            hashlib.sha256(page.encode()).hexdigest() for page in pages
        ],
        "source_declared_steel_capacity_mmtpa": 0.36,
        "source_declared_steel_capex_inr_crore": 810.0,
        "source_declared_power_capacity_mw": 25.0,
        "source_declared_power_capex_inr_crore": 125.0,
        "both_stated_target_commissioning": "Q4FY27",
        "power_plant_is_economically_required_for_steel_ebitda_verified": False,
        "both_capex_budgets_proven_fully_funded_or_spent": False,
    }


def _receipt(
    state: str, *,
    http_status: int | None,
    raw: bytes | None,
    original_terms: dict | None,
    issue: str,
) -> dict[str, Any]:
    successful = state == "ORIGINAL_ISSUER_PDF_BYTES_AND_ROADMAP_IDENTITY_VERIFIED"
    if successful != (raw is not None and original_terms is not None):
        raise ValueError("Sambhv original receipt and content state mismatch")
    return {
        "schema_version": 1,
        "case_id": CASE_ID,
        "source_kind": SOURCE_KIND,
        "symbol": "SAMBHV",
        "issuer": "Sambhv Steel Tubes Limited",
        "source_url": ORIGINAL_URL,
        "source_filing_date": "2026-08-03",
        "captured_at_utc": _now(),
        "http_status": http_status,
        "status": state,
        "raw_sha256": hashlib.sha256(raw).hexdigest() if successful else None,
        "raw_byte_count": len(raw) if successful else None,
        "document_identity_evidence": original_terms,
        "reason": issue,
        "original_page_layout_review_complete": False,
        "steel_power_budget_aggregation_authorized": False,
        "steel_phase_1_commissioning_verified": False,
        "power_phase_1_commissioning_verified": False,
        "company_fcf_or_ebitda_uplift_verified": False,
        "stock_target_or_expected_return_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def acquire_sambhv_original(
    *, attempts: int = 2, sleep_seconds: float = 3.0
) -> tuple[dict[str, Any], bytes | None]:
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("SAMBHV retry count outside 1–3")
    if type(sleep_seconds) not in (float, int) or not 0 <= sleep_seconds <= 30:
        raise ValueError("invalid bounded source retry delay")
    code: int | None = None
    state = "FETCH_FAILED"
    reason = "ORIGINAL_SOURCE_UNAVAILABLE"
    for index in range(attempts):
        try:
            response = requests.get(
                ORIGINAL_URL,
                headers={
                    "User-Agent": "marketlab-source-research/1.0",
                    "Accept": "application/pdf",
                },
                timeout=30,
                allow_redirects=False,
            )
            code = response.status_code
            if getattr(response, "url", ORIGINAL_URL) != ORIGINAL_URL:
                state, reason = "UNFOLLOWED_REDIRECT", "UNAPPROVED_RESPONSE_URL"
                break
            if code == 200:
                raw = response.content
                try:
                    result = verify_original_issuer_roadmap(raw)
                except ValueError as exc:
                    state, reason = "INVALID_SOURCE", str(exc)
                    break
                return _receipt(
                    "ORIGINAL_ISSUER_PDF_BYTES_AND_ROADMAP_IDENTITY_VERIFIED",
                    http_status=200, raw=raw, original_terms=result,
                    issue="ORIGINAL_PAGE_TERMS_SOURCE_VERIFIED_NOT_ECONOMIC_DEPENDENCY"
                ), raw
            if code in (401, 403, 429):
                state, reason = "ACCESS_BLOCKED", f"HTTP_{code}_NO_BYPASS"
                break
            if code == 404:
                state, reason = "SOURCE_NOT_AVAILABLE", "EXACT_ISSUER_PDF_NOT_FOUND"
                break
            if 300 <= code < 400:
                state, reason = "UNFOLLOWED_REDIRECT", f"HTTP_{code}_NO_FOLLOW"
                break
            reason = f"HTTP_{code}_OR_EMPTY_BODY"
            if code < 500:
                break
        except requests.RequestException as exc:
            reason = type(exc).__name__
        if index + 1 < attempts:
            time.sleep(sleep_seconds)
    return _receipt(
        state, http_status=code, raw=None, original_terms=None, issue=reason
    ), None


def save_original(root: Path, receipt: dict[str, Any], raw: bytes | None) -> None:
    if receipt.get("case_id") != CASE_ID:
        raise ValueError("wrong Sambhv original PDF source case")
    root.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        digest = hashlib.sha256(raw).hexdigest()
        if (
            receipt.get("status") != "ORIGINAL_ISSUER_PDF_BYTES_AND_ROADMAP_IDENTITY_VERIFIED"
            or receipt.get("raw_sha256") != digest
            or receipt.get("document_identity_evidence") != verify_original_issuer_roadmap(raw)
        ):
            raise ValueError("original Sambhv raw PDF/evidence disagree")
        pdf = root / "raw" / "sha256" / f"{digest}.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        if pdf.exists() and pdf.read_bytes() != raw:
            raise ValueError("immutable original Sambhv PDF source collision")
        pdf.write_bytes(raw)
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != digest:
            raise ValueError("original Sambhv PDF hash failed after writing")
    elif receipt.get("raw_sha256") is not None:
        raise ValueError("missing original PDF cannot have a SHA")
    encoded = json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False)+"\n"
    destination = root / "source-receipt-v1.json"
    if destination.exists() and destination.read_text(encoding="utf-8") != encoded:
        raise ValueError("immutable Sambhv original source receipt cannot be rewritten")
    destination.write_text(encoded, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=3)
    args = parser.parse_args()
    receipt, raw = acquire_sambhv_original(
        attempts=args.attempts, sleep_seconds=args.sleep_seconds
    )
    save_original(args.out_dir, receipt, raw)
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
