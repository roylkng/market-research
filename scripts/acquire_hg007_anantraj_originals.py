"""Acquire exact official July 2026 ANANTRAJ demerger/ACPL original PDFs.

This is immutable source custody, not an NCLT-approved effective scheme,
post-demerger cap table, estimated stock return or investment authorization.
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

SOURCE_ID = "HG007-P021-ANANTRAJ-ORIGINAL-JULY2026-SCHEME-SOURCES-v1"
PDF_SOURCES: dict[str, dict[str, Any]] = {
    "july20_subsidiary_rights_proposal": {
        "url": "https://nsearchives.nseindia.com/corporate/ANANTRAJ_20072026150454_Intimation_20072026.pdf",
        "date": "2026-07-20",
        "pages": 3,
        "tokens": (
            "37,43,22,553",
            "37,45,72,553",
            "2,50,000",
            "74,86,45,106",
            "ashok cloud",
        ),
    },
    "july21_completed_subscription": {
        "url": "https://nsearchives.nseindia.com/corporate/ANANTRAJ_21072026120301_Intimation_ACPL_Updates.pdf",
        "date": "2026-07-21",
        "pages": 1,
        "tokens": (
            "37,43,22,553",
            "74,86,45,106",
            "completed",
            "ashok cloud",
        ),
    },
    "july21_conditional_demerger_press": {
        "url": "https://nsearchives.nseindia.com/corporate/ANANTRAJ_21072026190031_Intimation_Press_Release_21072026.pdf",
        "date": "2026-07-21",
        "pages": 4,
        "tokens": (
            "one fully paid-up",
            "scheme will not result in the cancellation",
            "continue to remain a subsidiary",
            "ashok cloud",
            "approvals",
        ),
    },
}
MAX_PDF_BYTES = 6_000_000
STATES = frozenset({
    "OFFICIAL_PDF_SOURCE_PAGES_VERIFIED_NOT_TRANSACTION_CLOSE",
    "OFFICIAL_SOURCE_ACCESS_BLOCKED",
    "OFFICIAL_SOURCE_NOT_FOUND",
    "OFFICIAL_SOURCE_UNFOLLOWED_REDIRECT",
    "OFFICIAL_SOURCE_INVALID_PDF_OR_TEXT",
    "OFFICIAL_SOURCE_HTTP_OR_TRANSPORT_FAILURE",
})


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pdf_pages(raw: bytes, *, expected_count: int) -> list[str]:
    if (
        not isinstance(raw, bytes)
        or not 550 <= len(raw) <= MAX_PDF_BYTES
        or not raw.startswith(b"%PDF-")
        or b"%%EOF" not in raw[-2048:]
    ):
        raise ValueError("exact original PDF bytes fail trusted envelope")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        pages = list(reader.pages)
        if len(pages) != expected_count:
            raise ValueError("original filing PDF unexpected page count")
        texts = [page.extract_text() or "" for page in pages]
    except (PdfReadError, OSError, ValueError, TypeError, KeyError) as exc:
        raise ValueError("official original PDF parser unavailable") from exc
    if len(texts) != expected_count or any(len(x.strip()) < 35 for x in texts):
        raise ValueError("original filing PDF page text incomplete")
    return texts


def verify_source_bytes(key: str, raw: bytes) -> dict[str, Any]:
    if key not in PDF_SOURCES:
        raise ValueError("original issuer source ID not preregistered")
    contract = PDF_SOURCES[key]
    pages = _pdf_pages(raw, expected_count=contract["pages"])
    document = re.sub(r"\s+", " ", " ".join(pages)).casefold()
    absent = [value for value in contract["tokens"] if value.casefold() not in document]
    if absent:
        raise ValueError(f"original {key} issuer/transaction identity mismatch: {absent}")
    return {
        "official_source_url": contract["url"],
        "issuer_filing_date": contract["date"],
        "original_pdf_sha256": hashlib.sha256(raw).hexdigest(),
        "original_pdf_bytes": len(raw),
        "original_pdf_page_count": len(pages),
        "page_text_sha256": [
            hashlib.sha256(page.encode("utf-8")).hexdigest() for page in pages
        ],
        "issuer_terms_original_text_located": True,
        "full_scheme_pdf_and_transferred_net_liabilities_verified": False,
        "shareholder_or_nclt_approval_verified": False,
        "scheme_effective_date_verified": False,
    }


def _receipt(
    key: str,
    state: str,
    *,
    http_status: int | None,
    reason: str,
    verified: dict[str, Any] | None,
) -> dict[str, Any]:
    if key not in PDF_SOURCES or state not in STATES:
        raise ValueError("invalid source custody identity/state")
    success = state == "OFFICIAL_PDF_SOURCE_PAGES_VERIFIED_NOT_TRANSACTION_CLOSE"
    if success != (verified is not None):
        raise ValueError("source success must have verified original pages")
    return {
        "schema_version": 1,
        "source_batch_id": SOURCE_ID,
        "source_role": key,
        "official_url": PDF_SOURCES[key]["url"],
        "issuer_filing_date": PDF_SOURCES[key]["date"],
        "retrieved_at_utc": _utcnow(),
        "state": state,
        "http_status": http_status,
        "verified_original": verified,
        "reason": reason,
        "official_nclt_effective_demerger_order_verified": False,
        "post_scheme_cap_table_verified": False,
        "transferred_net_liabilities_verified": False,
        "future_anantraj_shareholder_record_date_verified": False,
        "full_shareholder_return_computed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def acquire_one(key: str, *, attempts: int, sleep_seconds: float) -> tuple[dict, bytes | None]:
    if key not in PDF_SOURCES:
        raise ValueError("original issuer source unknown")
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("bounded NSE source attempts must be 1-3")
    if type(sleep_seconds) not in (int, float) or not 0 <= sleep_seconds <= 20:
        raise ValueError("bounded source retry delay invalid")
    url = PDF_SOURCES[key]["url"]
    last_status: int | None = None
    last_reason = "NO_OFFICIAL_RESPONSE"
    for index in range(attempts):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "marketlab-anant-original-source/1.0",
                         "Accept": "application/pdf"},
                timeout=25,
                allow_redirects=False,
            )
            last_status = response.status_code
            if getattr(response, "url", url) != url:
                return _receipt(
                    key, "OFFICIAL_SOURCE_UNFOLLOWED_REDIRECT",
                    http_status=last_status, reason="URL_CHANGED_NO_BYPASS", verified=None
                ), None
            if last_status == 200:
                raw = response.content
                try:
                    verified = verify_source_bytes(key, raw)
                except ValueError as exc:
                    return _receipt(
                        key, "OFFICIAL_SOURCE_INVALID_PDF_OR_TEXT",
                        http_status=200, reason=str(exc), verified=None
                    ), None
                return _receipt(
                    key, "OFFICIAL_PDF_SOURCE_PAGES_VERIFIED_NOT_TRANSACTION_CLOSE",
                    http_status=200, reason="ORIGINAL_NSE_PDF_TEXT_IDENTITY_CONFIRMED",
                    verified=verified,
                ), raw
            if last_status in (401, 403, 429):
                return _receipt(
                    key, "OFFICIAL_SOURCE_ACCESS_BLOCKED", http_status=last_status,
                    reason=f"HTTP_{last_status}_NO_ACCESS_BYPASS", verified=None
                ), None
            if last_status == 404:
                return _receipt(
                    key, "OFFICIAL_SOURCE_NOT_FOUND", http_status=404,
                    reason="ORIGINAL_ATTACHMENT_NOT_FOUND", verified=None
                ), None
            if 300 <= last_status < 400:
                return _receipt(
                    key, "OFFICIAL_SOURCE_UNFOLLOWED_REDIRECT", http_status=last_status,
                    reason="ORIGINAL_HOST_REDIRECT_NOT_FOLLOWED", verified=None
                ), None
            last_reason = f"HTTP_{last_status}"
            if last_status < 500:
                break
        except requests.RequestException as exc:
            last_reason = type(exc).__name__
        if index + 1 < attempts:
            time.sleep(sleep_seconds)
    return _receipt(
        key, "OFFICIAL_SOURCE_HTTP_OR_TRANSPORT_FAILURE",
        http_status=last_status, reason=last_reason, verified=None
    ), None


def retain_attempt(output: Path, sources: dict[str, tuple[dict, bytes | None]]) -> dict:
    if set(sources) != set(PDF_SOURCES):
        raise ValueError("all three original issuer sources must be accounted for")
    output.mkdir(parents=True, exist_ok=True)
    receipts = []
    for key in PDF_SOURCES:
        receipt, original = sources[key]
        if receipt.get("source_role") != key or receipt.get("source_batch_id") != SOURCE_ID:
            raise ValueError("wrong original PDF role/issuer batch receipt")
        if original is not None:
            verified = verify_source_bytes(key, original)
            if receipt["verified_original"] != verified:
                raise ValueError("original NSE source receipt changed")
            target = output / "raw" / "sha256" / f"{verified['original_pdf_sha256']}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != original:
                raise ValueError("original filing bytes immutable SHA conflict")
            target.write_bytes(original)
            if hashlib.sha256(target.read_bytes()).hexdigest() != verified["original_pdf_sha256"]:
                raise ValueError("persisted original PDF hash failed")
        elif receipt.get("verified_original") is not None:
            raise ValueError("no original bytes for claimed verified PDF")
        receipts.append(receipt)
    complete = all(
        row["state"] == "OFFICIAL_PDF_SOURCE_PAGES_VERIFIED_NOT_TRANSACTION_CLOSE"
        for row in receipts
    )
    result = {
        "schema_version": 1,
        "source_batch_id": SOURCE_ID,
        "source_completion_state": (
            "THREE_ORIGINAL_ISSUER_FILINGS_VERIFIED"
            if complete else "INCOMPLETE_OR_BLOCKED_ORIGINAL_SOURCES"
        ),
        "source_receipts": receipts,
        "original_source_count": 3,
        "original_verified_count": sum(
            row["state"] == "OFFICIAL_PDF_SOURCE_PAGES_VERIFIED_NOT_TRANSACTION_CLOSE"
            for row in receipts
        ),
        "original_scheme_transaction_effective_verified": False,
        "pro_forma_newco_ownership_completed_verified": False,
        "equity_expected_return_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    (output / "source-receipts-v1.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=2)
    args = parser.parse_args()
    evidence = {
        key: acquire_one(key, attempts=args.attempts, sleep_seconds=args.sleep_seconds)
        for key in PDF_SOURCES
    }
    result = retain_attempt(args.out_dir, evidence)
    print(json.dumps({
        "source_batch_id": SOURCE_ID,
        "original_verified_count": result["original_verified_count"],
        "source_completion_state": result["source_completion_state"],
        "source_receipts": [
            {"source_role": v["source_role"], "state": v["state"],
             "original_sha256": (v["verified_original"] or {}).get("original_pdf_sha256")}
            for v in result["source_receipts"]
        ],
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
