"""Source-bound POLYCAB 9 October 2026 NCLAT stay original PDF custody.

The SS002 lexical family INSOLVENCY_RESOLUTION is NOT a statement
that CIRP remains active. This only captures the original exchange
document and its explicitly dated issuer/court wording. No signal,
forecast, issuer insolvency probability, or trade is authorized.
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

ORIGINAL_URL = (
    "https://nsearchives.nseindia.com/corporate/"
    "POLYCAB_09102026194506_StockexchangeCIRP09102026.pdf"
)
CAPTURE_FILE = Path("research/prospective/ss002-p001/2026-10-09-v1.json")
CAPTURE_GIT_BLOB_SHA = "4eb8390b76a48957e19c1d49689ad9009be9c65a"
CAPTURE_PAYLOAD_SHA = "53158b6d5076bf3ede83cd2c4fc0c0678d6862ab4534cae24a64884729a424e0"
CANDIDATE_ANNOUNCEMENT_SEQ = "106813081"
CANDIDATE_SYMBOL = "POLYCAB"
CUSTODY_ID = "SS002-P015-2026-10-09-POLYCAB-NCLAT-STAY-ORIGINAL-v1"
MAX_PDF_BYTES = 9_000_000


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _blob_sha(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def original_announcement_identity(repo_root: Path) -> dict[str, Any]:
    raw = (repo_root / CAPTURE_FILE).read_bytes()
    if _blob_sha(raw) != CAPTURE_GIT_BLOB_SHA:
        raise ValueError("original 9 Oct NSE source capture Git blob drifted")
    capture = json.loads(raw)
    if (
        capture.get("capture_sha256") != CAPTURE_PAYLOAD_SHA
        or capture.get("source_day_ist") != "2026-10-09"
        or capture.get("announcement_count") != 579
        or capture.get("candidate_event_count") != 21
        or capture.get("return_outcomes_opened") is not False
        or capture.get("live_capital_allowed") is not False
    ):
        raise ValueError("original SS002 P001 source/candidate identity changed")
    candidates = [
        x for x in capture["candidate_events"]
        if str(x.get("seq_id")) == CANDIDATE_ANNOUNCEMENT_SEQ
    ]
    if len(candidates) != 1:
        raise ValueError("exact original NSE event 106813081 was not unique")
    candidate = candidates[0]
    if (
        candidate.get("symbol") != CANDIDATE_SYMBOL
        or candidate.get("approved_attachment_url") != ORIGINAL_URL
        or candidate.get("category_hints_only") != ["INSOLVENCY_RESOLUTION"]
        or candidate.get("economic_relevance_verified") is not False
        or candidate.get("portfolio_eligibility_allowed") is not False
        or candidate.get("current_eq_isin_at_capture") != "INE455K01017"
        or candidate.get("mapping_state") != "SYMBOL_IN_EQ_MASTER_AT_CAPTURE"
    ):
        raise ValueError("P015 attempted to replace original Polycab source event")
    return {
        "source_capture_path": str(CAPTURE_FILE),
        "source_capture_git_blob_sha": CAPTURE_GIT_BLOB_SHA,
        "source_capture_payload_sha256": CAPTURE_PAYLOAD_SHA,
        "source_event_seq": CANDIDATE_ANNOUNCEMENT_SEQ,
        "source_event_id": candidate["announcement_id"],
        "source_event_category": "INSOLVENCY_RESOLUTION",
        "original_nse_announcement_timestamp": candidate["exchange_published_at_utc"],
    }


def _pdf_identity(raw: bytes) -> dict[str, Any]:
    if (
        not isinstance(raw, bytes)
        or not 1400 <= len(raw) <= MAX_PDF_BYTES
        or not raw.startswith(b"%PDF-")
        or b"%%EOF" not in raw[-2048:]
    ):
        raise ValueError("NSE original Polycab court-document PDF envelope invalid")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, KeyError, OSError, TypeError, ValueError) as exc:
        raise ValueError("NSE Polycab original PDF cannot be parsed") from exc
    if len(pages) != 4 or any(len(page.strip()) < 70 for page in pages):
        raise ValueError("original NCLAT stay document must contain four readable pages")
    first = re.sub(r"\s+", " ", pages[0].casefold())
    all_pages = re.sub(r"\s+", " ", " ".join(pages).casefold())
    if (
        "polycab india limited" not in first
        or "october 09, 2026" not in first
        or "nclat" not in first
        or "2.79 crore" not in all_pages
        or "admission" not in all_pages
        or "corporate insolvency" not in all_pages
        or "stayed" not in all_pages
        or "abeyance" not in all_pages
        or "26.10.2026" not in all_pages
    ):
        raise ValueError("issuer/court stay and exact-date text identity not established")
    return {
        "page_count": 4,
        "original_pdf_page_text_sha256": [hashlib.sha256(x.encode()).hexdigest() for x in pages],
        "source_statement_filing_date_ist": "2026-10-09",
        "nclt_prior_admission_order_date_ist": "2026-10-07",
        "nclat_stay_order_date_ist": "2026-10-09",
        "disputed_claim_approx_inr_crore": 2.79,
        "next_hearing_reported_date_ist": "2026-10-26",
        "issuer_or_court_exact_text_reflects_stay": True,
        "post_9oct_further_court_status_verified": False,
        "legal_inference": "ADMISSION_ORDER_STAYED_PENDING_FURTHER_COURT_PROCESS_AS_OF_OCT09",
    }


def probe_official(
    repo_root: Path, *, attempts: int = 2, pause_seconds: float = 2.0
) -> tuple[dict[str, Any], bytes | None]:
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("official source retry count must be 1-3")
    if type(pause_seconds) not in (float, int) or not 0 <= pause_seconds <= 30:
        raise ValueError("official source retry pause outside bounds")
    original = original_announcement_identity(repo_root)
    status = "ORIGINAL_ATTACHMENT_UNAVAILABLE"
    detail = "NO_COMPLETED_SOURCE_REQUEST"
    http_status: int | None = None
    proof = None
    raw_verified = None
    for index in range(attempts):
        try:
            response = requests.get(
                ORIGINAL_URL, timeout=30, allow_redirects=False,
                headers={"User-Agent": "marketlab-ss002-original-document/1.0",
                         "Accept": "application/pdf"},
            )
            http_status = response.status_code
            if getattr(response, "url", ORIGINAL_URL) != ORIGINAL_URL:
                status, detail = "REDIRECT_BLOCKED", "NSE_ATTACHMENT_REQUEST_CHANGED_URL"
                break
            if http_status == 200:
                try:
                    proof = _pdf_identity(response.content)
                except ValueError as exc:
                    status, detail = "ORIGINAL_PDF_INVALID_OR_WRONG_EVENT", str(exc)
                    break
                status, detail = "ORIGINAL_NSE_PDF_TEXT_IDENTITY_VALIDATED", (
                    "ORIGINAL_PDF_CAPTURED_AND_ISSUER_NCLAT_STAY_KEYWORDS_BOUND"
                )
                raw_verified = response.content
                break
            if http_status in (401, 403, 429):
                status, detail = "SOURCE_ACCESS_BLOCKED", f"HTTP_{http_status}_NO_BYPASS"
                break
            if http_status == 404:
                status, detail = "SOURCE_NOT_PUBLISHED_OR_REMOVED", "EXACT_OFFICIAL_URL_HTTP404"
                break
            if 300 <= http_status < 400:
                status, detail = "REDIRECT_BLOCKED", "UNFOLLOWED_OFFICIAL_SOURCE_REDIRECT"
                break
            status, detail = "OFFICIAL_ENDPOINT_FAILURE", f"HTTP_{http_status}"
            if http_status < 500:
                break
        except requests.RequestException as exc:
            status, detail = "OFFICIAL_ENDPOINT_FAILURE", type(exc).__name__
        if index + 1 < attempts:
            time.sleep(pause_seconds)

    report = {
        "schema_version": 1,
        "custody_id": CUSTODY_ID,
        "symbol": CANDIDATE_SYMBOL,
        "original_nse_url": ORIGINAL_URL,
        "observed_at_utc": _utc(),
        "http_status": http_status,
        "original_9oct_candidate": original,
        "source_capture_state": status,
        "source_failure_or_context": detail,
        "original_document_sha256": _sha(raw_verified) if raw_verified else None,
        "original_document_bytes": len(raw_verified) if raw_verified else None,
        "original_pdf_text_identity": proof,
        "source_original_pdf_visual_semantic_audit_complete": False,
        "court_order_post_oct9_updates_checked": False,
        "issuer_currently_in_unstayed_cirp_proven": False,
        "issuer_insolvency_probability_calculated": False,
        "stock_price_or_market_cap_updated": False,
        "market_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return report, raw_verified


def retain_original(out_dir: Path, report: dict[str, Any], raw: bytes | None) -> None:
    if report.get("custody_id") != CUSTODY_ID:
        raise ValueError("source Polycab custody record mismatch")
    if (raw is None) != (report.get("original_document_sha256") is None):
        raise ValueError("original PDF raw/receipt state inconsistent")
    out_dir.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        sha = _sha(raw)
        if (
            report.get("source_capture_state") != "ORIGINAL_NSE_PDF_TEXT_IDENTITY_VALIDATED"
            or sha != report["original_document_sha256"]
            or _pdf_identity(raw) != report.get("original_pdf_text_identity")
        ):
            raise ValueError("Polycab original PDF source failed evidence revalidation")
        destination = out_dir / "raw" / "sha256" / f"{sha}.pdf"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError("immutable original Polycab PDF cannot be overwritten")
        destination.write_bytes(raw)
        if _sha(destination.read_bytes()) != sha:
            raise ValueError("Polycab source PDF SHA custody verification failed")
    dest = out_dir / "source-receipt-v1.json"
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if dest.exists() and dest.read_text(encoding="utf-8") != encoded:
        raise ValueError("immutable original source receipt cannot be rewritten")
    dest.write_text(encoded, encoding="utf-8")


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--repo-root", type=Path, default=Path("."))
    cli.add_argument("--out-dir", type=Path, required=True)
    cli.add_argument("--attempts", type=int, default=2)
    cli.add_argument("--pause-seconds", type=float, default=2)
    args = cli.parse_args()
    report, raw = probe_official(
        args.repo_root, attempts=args.attempts, pause_seconds=args.pause_seconds
    )
    retain_original(args.out_dir, report, raw)
    print(json.dumps(report, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
