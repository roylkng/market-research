"""Acquire *independently discovered* NSE original Anant Raj QIP monitoring PDF.

NSE published the same 8-Aug-2026/30-Jun-2026 original filing, distinct
from the unavailable BSE AttachLive URL. This is a new verifiable official
source URL, not an access-control workaround or replacement of BSE evidence.
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

from scripts.probe_hg007_anantraj_june_qip_monitor import _inspect_original_pdf

NSE_ORIGINAL_URL = (
    "https://nsearchives.nseindia.com/corporate/"
    "ANANTRAJ_08082026182321_Intimation_Monitoring_Agency_08082026.pdf"
)
SOURCE_ID = "HG007-P028-ANANTRAJ-NSE-JUNE-QIP-MONITOR-ORIGINAL-v1"
CAPTURED = "NSE_ORIGINAL_21PAGE_PDF_CAPTURED_NOT_CLOUD_ASSET_AUDIT"
STATES = {
    CAPTURED, "NSE_ACCESS_BLOCKED", "NSE_SOURCE_NOT_FOUND",
    "NSE_UNFOLLOWED_REDIRECT", "NSE_DOCUMENT_REJECTED",
    "NSE_HTTP_OR_NETWORK_FAILURE",
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _receipt(
    status: str, *, http_code: int | None, original: bytes | None,
    identity: dict[str, Any] | None, error: str,
) -> dict[str, Any]:
    if status not in STATES:
        raise ValueError("unrecognized original NSE source status")
    good = status == CAPTURED
    if good != (original is not None and identity is not None):
        raise ValueError("source receipt claims inconsistent original bytes")
    return {
        "schema_version": 1, "source_id": SOURCE_ID,
        "source_type": "EXACT_ORIGINAL_NSE_ARCHIVE_PDF",
        "original_source_url": NSE_ORIGINAL_URL,
        "symbol": "ANANTRAJ", "report_quarter_end": "2026-06-30",
        "document_publication_date": "2026-08-08",
        "captured_at_utc": _now(), "http_status": http_code,
        "state": status, "reason": error,
        "source_sha256": hashlib.sha256(original).hexdigest() if good else None,
        "source_byte_count": len(original) if good else None,
        "pdf_text_identity": identity,
        "all_object_values_page_visually_checked": False,
        "monitoring_report_is_independent_financial_audit": False,
        "cloud_capex_deployment_confirmed_from_balances": False,
        "cash_transferred_to_ashok_cloud_ascertained": False,
        "liabilities_transferred_to_ashok_cloud_ascertained": False,
        "company_completion_probability_published": False,
        "equity_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def acquire_nse_original(*, attempts: int = 2, sleep_seconds: float = 3.0
                         ) -> tuple[dict[str, Any], bytes | None]:
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("source attempts must be 1, 2, or 3")
    if type(sleep_seconds) not in (int, float) or not 0 <= sleep_seconds <= 30:
        raise ValueError("source retry delay out of range")
    last_status: int | None = None
    issue = "NO_VALID_HTTP_RESPONSE"
    for attempt in range(attempts):
        try:
            res = requests.get(
                NSE_ORIGINAL_URL,
                headers={"User-Agent": "marketlab-official-exchange-file-research/1.0",
                         "Accept": "application/pdf"},
                timeout=40,
                allow_redirects=False,
            )
            last_status = res.status_code
            if getattr(res, "url", NSE_ORIGINAL_URL) != NSE_ORIGINAL_URL:
                return _receipt(
                    "NSE_UNFOLLOWED_REDIRECT", http_code=last_status, original=None,
                    identity=None, error="UNEXPECTED_EXCHANGE_HOST_OR_URL"
                ), None
            if last_status == 200:
                raw = res.content
                try:
                    identity = _inspect_original_pdf(raw)
                    if identity.get("page_count") != 21:
                        raise ValueError("NSE original expected 21 pages")
                except ValueError as exc:
                    return _receipt(
                        "NSE_DOCUMENT_REJECTED", http_code=200,
                        original=None, identity=None, error=str(exc)
                    ), None
                return _receipt(
                    CAPTURED, http_code=200, original=raw,
                    identity=identity, error="ORIGINAL_21_PAGES_RETAINED_UNREVIEWED"
                ), raw
            if last_status in (401, 403, 429):
                return _receipt(
                    "NSE_ACCESS_BLOCKED", http_code=last_status, original=None,
                    identity=None, error=f"HTTP_{last_status}_NO_BYPASS"
                ), None
            if last_status == 404:
                return _receipt(
                    "NSE_SOURCE_NOT_FOUND", http_code=404, original=None,
                    identity=None, error="EXACT_NSE_ARCHIVE_PDF_NOT_FOUND"
                ), None
            if 300 <= last_status < 400:
                return _receipt(
                    "NSE_UNFOLLOWED_REDIRECT", http_code=last_status,
                    original=None, identity=None, error="REDIRECT_NOT_FOLLOWED"
                ), None
            issue = f"HTTP_{last_status}"
            if last_status < 500:
                break
        except requests.RequestException as exc:
            issue = type(exc).__name__
        if attempt + 1 < attempts:
            time.sleep(sleep_seconds)
    return _receipt(
        "NSE_HTTP_OR_NETWORK_FAILURE", http_code=last_status,
        original=None, identity=None, error=issue
    ), None


def save_original(out_dir: Path, receipt: dict, data: bytes | None) -> None:
    if receipt.get("source_id") != SOURCE_ID:
        raise ValueError("unrecognized NSE original report receipt")
    out_dir.mkdir(parents=True, exist_ok=True)
    if data is not None:
        if receipt.get("state") != CAPTURED:
            raise ValueError("cannot anchor PDF bytes under blocked source")
        sha = hashlib.sha256(data).hexdigest()
        if sha != receipt.get("source_sha256"):
            raise ValueError("original NSE source sha mismatch")
        parsed = _inspect_original_pdf(data)
        if parsed != receipt.get("pdf_text_identity") or parsed.get("page_count") != 21:
            raise ValueError("NSE source page identity changed between fetch and retention")
        dest = out_dir / "raw" / "sha256" / f"{sha}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.read_bytes() != data:
            raise ValueError("SHA-addressed original NSE report cannot change")
        dest.write_bytes(data)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
            raise ValueError("original NSE report corrupted during retention")
    elif receipt.get("source_sha256") is not None:
        raise ValueError("blocked NSE original cannot assert PDF hash")
    dest = out_dir / "attempt.json"
    encoded = json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if dest.exists() and dest.read_text(encoding="utf-8") != encoded:
        raise ValueError("original NSE report receipt already anchored")
    dest.write_text(encoded, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=3)
    args = parser.parse_args()
    receipt, raw = acquire_nse_original(
        attempts=args.attempts, sleep_seconds=args.sleep_seconds
    )
    save_original(args.out_dir, receipt, raw)
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
