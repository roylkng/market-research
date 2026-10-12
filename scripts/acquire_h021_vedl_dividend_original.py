"""Exact-source Oct 8 VEDL dividend filing acquisition for the frozen H021 cohort.

An original filing confirms a declared dividend and *record date*, not
paper trade execution, dividend entitlement, ex-date or total-return
comparability. The archived Oct 8 NSE announcement was already visible
before the prospective Oct 12 entry. New PDF bytes fetched after entry
must never be backdated or called a pre-entry PDF capture.
"""

from __future__ import annotations

import argparse
import gzip
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

from marketlab.h021_first_entry_intent import git_blob_sha

SOURCE_ID = "H021-P012-VEDL-2026-10-08-ORIGINAL-NSE-DIVIDEND-v1"
FROZEN_ANNOUNCEMENT_PATH = Path("research/prospective/ss002-p001/2026-10-08-v1.json")
FROZEN_ANNOUNCEMENT_BLOB = "123c858432d2f4af86d76792a85c727077ff7ec0"
FROZEN_CAPTURE_ID = "SS002-P001-2026-10-08-v1"
FROZEN_ANNOUNCEMENT_CAPTURE_SHA = (
    "cefe063a076ff9bfb6a88e06293fe435e5a7a62707b0e294d247640d10ca135d"
)
FROZEN_ANNOUNCEMENTS_RAW_SHA = (
    "aff6e8075d4f2b3067a2fa84349a484ed7ba225825397db6d1978ccea2718171"
)
ORIGINAL_ANNOUNCEMENT_ID = (
    "753e6a20e6f165677087990a6c35ec54971b034afa4bbb83ada5ab6c73135092"
)
ORIGINAL_PUBLICATION_UTC = "2026-10-08T07:41:56Z"
ORIGINAL_SOURCE_URL = (
    "https://nsearchives.nseindia.com/corporate/"
    "VEDL_08102026131108_SEIntimationOutcomeofBM1stInterimDividendsigned.pdf"
)
FIRST_ENTRY_INTENT_DATE = "2026-10-12T03:45:00Z"
PDF_MAX_BYTES = 5_000_000
STATES = frozenset({
    "OFFICIAL_PDF_BYTES_AND_ISSUER_TEXT_CAPTURED_NOT_ENTITLEMENT_AUDITED",
    "ACCESS_BLOCKED_NO_BYPASS",
    "ORIGINAL_FILE_NOT_FOUND",
    "UNFOLLOWED_REDIRECT",
    "INVALID_OR_UNREADABLE_OFFICIAL_PDF",
    "HTTP_OR_NETWORK_FAILURE",
})


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_hash(value: dict[str, Any]) -> str:
    return _sha(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    )


def verify_archived_preentry_event(root: Path) -> dict[str, Any]:
    """The issuer-specific URL was already published before Oct 12 opening."""
    raw = (root / FROZEN_ANNOUNCEMENT_PATH).read_bytes()
    if git_blob_sha(raw) != FROZEN_ANNOUNCEMENT_BLOB:
        raise ValueError("original SS002 Oct 8 archived announcement blob was modified")
    saved = json.loads(raw)
    if not isinstance(saved, dict):
        raise TypeError("SS002 archived announcement must be an object")
    if (
        saved.get("capture_id") != FROZEN_CAPTURE_ID
        or saved.get("capture_sha256") != FROZEN_ANNOUNCEMENT_CAPTURE_SHA
        or saved.get("source_day_ist") != "2026-10-08"
        or saved.get("return_outcomes_opened") is not False
        or saved.get("portfolio_eligibility_allowed") is not False
        or saved.get("live_capital_allowed") is not False
    ):
        raise ValueError("original archived Oct 8 source publication contract changed")
    source = saved.get("sources", {}).get("announcement")
    if not isinstance(source, dict) or source.get("raw_sha256") != FROZEN_ANNOUNCEMENTS_RAW_SHA:
        raise ValueError("original Oct 8 raw NSE API bytes provenance changed")
    original_gzip_relpath = source.get("relative_path")
    if not isinstance(original_gzip_relpath, str) or not original_gzip_relpath.startswith(
        "research/prospective/ss002-p001/raw/announcements/"
    ):
        raise ValueError("original announcement raw NSE source path changed")
    original_gzip = (root / original_gzip_relpath).read_bytes()
    if _sha(original_gzip) != source.get("gzip_sha256"):
        raise ValueError("original Oct 8 gzip raw NSE source hash changed")
    raw_json = gzip.decompress(original_gzip)
    if _sha(raw_json) != FROZEN_ANNOUNCEMENTS_RAW_SHA:
        raise ValueError("uncompressed original NSE API source changed")
    if ORIGINAL_SOURCE_URL.encode("utf-8") not in raw_json:
        raise ValueError("original NSE event attachment absent from original raw API bytes")

    records = saved.get("announcements")
    if not isinstance(records, list):
        raise TypeError("Oct 8 source announcements absent")
    match = [
        entry for entry in records
        if isinstance(entry, dict)
        and entry.get("announcement_id") == ORIGINAL_ANNOUNCEMENT_ID
        and entry.get("symbol") == "VEDL"
    ]
    if len(match) != 1:
        raise ValueError("original NSE issuer event duplicated or missing")
    event = match[0]
    if (
        event.get("attchmntFile") != ORIGINAL_SOURCE_URL
        or event.get("exchange_published_at_utc") != ORIGINAL_PUBLICATION_UTC
        or event.get("desc") != "Dividend"
        or "Rs. 5 per equity share" not in str(event.get("attchmntText"))
    ):
        raise ValueError("original VEDL publication/amount/source URL changed")
    captured = datetime.fromisoformat(saved.get("acquired_at_utc"))
    published = datetime.fromisoformat(ORIGINAL_PUBLICATION_UTC)
    entry = datetime.fromisoformat(FIRST_ENTRY_INTENT_DATE)
    if (
        published.tzinfo is None or captured.tzinfo is None
        or not published < captured < entry
    ):
        raise ValueError("Vedanta archived NSE metadata not historically pre-entry")
    return {
        "ss002_capture_id": FROZEN_CAPTURE_ID,
        "ss002_capture_git_blob": FROZEN_ANNOUNCEMENT_BLOB,
        "ss002_capture_sha256": FROZEN_ANNOUNCEMENT_CAPTURE_SHA,
        "original_raw_nse_api_sha256": FROZEN_ANNOUNCEMENTS_RAW_SHA,
        "original_announcement_id": ORIGINAL_ANNOUNCEMENT_ID,
        "original_pdf_url_discovered_before_entry": ORIGINAL_SOURCE_URL,
        "source_public_broadcast_at_utc": ORIGINAL_PUBLICATION_UTC,
        "archived_source_acquired_at_utc": saved["acquired_at_utc"],
        "source_was_public_before_oct12_planned_entry": True,
    }


def verify_original_dividend_pdf(raw: bytes) -> dict[str, Any]:
    """One original NSE issuer page, no inferred ex-date from the board letter."""
    if (
        not isinstance(raw, bytes)
        or not 500 <= len(raw) <= PDF_MAX_BYTES
        or not raw.startswith(b"%PDF-")
        or b"%%EOF" not in raw[-2048:]
    ):
        raise ValueError("VEDL original attachment is not a valid PDF byte envelope")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if len(reader.pages) != 1:
            raise ValueError("expected exactly one NSE VEDL dividend board letter page")
        text = reader.pages[0].extract_text() or ""
    except (PdfReadError, KeyError, OSError, TypeError, ValueError) as exc:
        raise ValueError("original VEDL PDF structure/text unavailable") from exc
    # A source-page renderer may turn "1st" into "1 st" or insert spaces
    # around the FY27 dash/₹5/-. Match an exact *set of economic and
    # chronological facts* from the archived issuer PDF, not typography.
    normalized = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    anchors = (
        "vedanta limited",
        "october 08 2026",
        "vedl",
        "interim dividend",
        "2026 27",
        "5 per equity share",
        "october 14 2026",
        "record date",
        "01 00 pm ist",
    )
    for anchor in anchors:
        if anchor not in normalized:
            raise ValueError(f"original VEDL dividend PDF missing source anchor: {anchor}")
    # The source event independently declares the *first* interim dividend.
    # Reject a different sequential dividend even with matching other text.
    if re.search(
        r"\b(?:2\s*nd|second|3\s*rd|third)\s+interim\s+dividend\b",
        normalized,
    ):
        raise ValueError("original VEDL PDF is a different numbered dividend")
    if normalized.index("record date") > normalized.index("october 14 2026"):
        raise ValueError("original VEDL record date appears in wrong context")
    return {
        "original_pdf_sha256": _sha(raw),
        "original_pdf_page_count": 1,
        "original_pdf_page1_text_sha256": _sha(text.encode("utf-8")),
        "original_pdf_byte_count": len(raw),
        "issuer_reported_board_declaration_date": "2026-10-08",
        "issuer_reported_dividend_per_share_inr": 5.0,
        "issuer_reported_record_date_ist": "2026-10-14",
        "issuer_reported_board_approval_time_ist": "13:00",
        "ex_date_confirmed_by_this_pdf": False,
        "cash_dividend_payable_or_received_proven": False,
        "hypothetical_entry_holder_dividend_entitlement_proven": False,
    }


def _receipt(state: str, *, http_status: int | None, raw: bytes | None,
             original_text: dict[str, Any] | None, archive: dict,
             error: str) -> dict[str, Any]:
    if state not in STATES:
        raise ValueError("unrecognized official source acquisition state")
    success = state == "OFFICIAL_PDF_BYTES_AND_ISSUER_TEXT_CAPTURED_NOT_ENTITLEMENT_AUDITED"
    if success != (raw is not None and original_text is not None):
        raise ValueError("official PDF success must have source text + original bytes")
    result: dict[str, Any] = {
        "schema_version": 1,
        "source_id": SOURCE_ID,
        "classification": "ORIGINAL_DIVIDEND_DECLARATION_NOT_PORTFOLIO_RETURN_CLEARANCE",
        "symbol": "VEDL",
        "isin": "INE205A01025",
        "source_url": ORIGINAL_SOURCE_URL,
        "first_original_announcement_provenance": archive,
        "original_pdf_fetched_at_utc": _now(),
        "state": state,
        "http_status": http_status,
        "original_pdf_sha256": _sha(raw) if success else None,
        "original_pdf_size": len(raw) if success else None,
        "issuer_reported_dividend_terms": original_text,
        "error_or_note": error,
        "actual_ex_date_verified_by_board_letter": False,
        "complete_h021_corporate_action_census_verified": False,
        "h021_return_basis_total_return_certified": False,
        "dividend_cash_payment_proven": False,
        "actual_h021_trade_and_entitlement_proven": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["packet_sha256"] = _canonical_hash(result)
    return result


def download_original(*, archive: dict[str, Any], attempts: int = 2,
                      retry_delay: float = 2.0) -> tuple[dict, bytes | None]:
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("official dividend source attempts must be between 1 and 3")
    if type(retry_delay) not in (int, float) or not 0 <= retry_delay <= 30:
        raise ValueError("invalid official dividend source retry delay")
    last_status: int | None = None
    last_error = "NO_ORIGINAL_SOURCE_RESPONSE"
    for i in range(attempts):
        try:
            res = requests.get(
                ORIGINAL_SOURCE_URL,
                headers={
                    "User-Agent": "marketlab-h021-original-dividend-evidence/1.0",
                    "Accept": "application/pdf",
                },
                timeout=30,
                allow_redirects=False,
            )
            last_status = res.status_code
            if getattr(res, "url", ORIGINAL_SOURCE_URL) != ORIGINAL_SOURCE_URL:
                return _receipt("UNFOLLOWED_REDIRECT", http_status=last_status,
                                raw=None, original_text=None, archive=archive,
                                error="SOURCE_URL_CHANGED_NO_BYPASS"), None
            if last_status == 200:
                data = res.content
                try:
                    terms = verify_original_dividend_pdf(data)
                except ValueError as exc:
                    return _receipt("INVALID_OR_UNREADABLE_OFFICIAL_PDF",
                                    http_status=last_status, raw=None,
                                    original_text=None, archive=archive,
                                    error=str(exc)), None
                return _receipt(
                    "OFFICIAL_PDF_BYTES_AND_ISSUER_TEXT_CAPTURED_NOT_ENTITLEMENT_AUDITED",
                    http_status=200, raw=data, original_text=terms,
                    archive=archive, error="ORIGINAL_DECLARATION_TEXT_VERIFIED_ENTITLEMENT_OPEN",
                ), data
            if last_status in (401, 403, 429):
                return _receipt("ACCESS_BLOCKED_NO_BYPASS",
                                http_status=last_status, raw=None, original_text=None,
                                archive=archive, error=f"HTTP_{last_status}"), None
            if last_status == 404:
                return _receipt("ORIGINAL_FILE_NOT_FOUND",
                                http_status=404, raw=None, original_text=None,
                                archive=archive, error="EXACT_NSE_ATTACHMENT_MISSING"), None
            if 300 <= last_status < 400:
                return _receipt("UNFOLLOWED_REDIRECT",
                                http_status=last_status, raw=None, original_text=None,
                                archive=archive, error="NO_FOLLOW_OTHER_HOST"), None
            last_error = f"HTTP_{last_status}_OR_UNEXPECTED_EMPTY"
            if last_status < 500:
                break
        except requests.RequestException as exc:
            last_error = type(exc).__name__
        if i + 1 < attempts:
            time.sleep(retry_delay)
    return _receipt("HTTP_OR_NETWORK_FAILURE", http_status=last_status,
                    raw=None, original_text=None, archive=archive,
                    error=last_error), None


def verify_receipt(receipt: dict[str, Any], original: bytes | None) -> None:
    if receipt.get("source_id") != SOURCE_ID or receipt.get("source_url") != ORIGINAL_SOURCE_URL:
        raise ValueError("original Vedanta NSE capture record identity changed")
    digest = receipt.get("packet_sha256")
    if not isinstance(digest, str) or _canonical_hash(
        {k: v for k, v in receipt.items() if k != "packet_sha256"}
    ) != digest:
        raise ValueError("VEDL original filing receipt is not authentic")
    if any(receipt.get(flag) is not False for flag in (
        "actual_ex_date_verified_by_board_letter",
        "h021_return_basis_total_return_certified",
        "dividend_cash_payment_proven",
        "actual_h021_trade_and_entitlement_proven",
        "return_outcomes_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    )):
        raise ValueError("original VEDL PDF may not authorize future returns or capital")
    success = receipt.get("state") == (
        "OFFICIAL_PDF_BYTES_AND_ISSUER_TEXT_CAPTURED_NOT_ENTITLEMENT_AUDITED"
    )
    if success:
        if not isinstance(original, bytes) or _sha(original) != receipt.get("original_pdf_sha256"):
            raise ValueError("original PDF bytes do not match source receipt SHA")
        if receipt.get("issuer_reported_dividend_terms") != verify_original_dividend_pdf(original):
            raise ValueError("verified VEDL PDF page terms do not reproduce from raw")
    elif original is not None or receipt.get("original_pdf_sha256") is not None:
        raise ValueError("missing/blocked original cannot advertise source PDF bytes")


def retain_capture(root: Path, receipt: dict[str, Any], raw: bytes | None) -> None:
    verify_receipt(receipt, raw)
    root.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        digest = _sha(raw)
        dest = root / "original" / "sha256" / f"{digest}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.read_bytes() != raw:
            raise ValueError("immutable official VEDL PDF source conflict")
        dest.write_bytes(raw)
        if _sha(dest.read_bytes()) != digest:
            raise ValueError("original Vedanta PDF failed retention SHA verification")
    dest = root / "source-receipt-v1.json"
    encoded = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if dest.exists() and dest.read_text(encoding="utf-8") != encoded:
        raise ValueError("existing dated original source receipt cannot be overwritten")
    dest.write_text(encoded, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--retry-delay", type=float, default=2)
    args = parser.parse_args()
    previous = verify_archived_preentry_event(args.repo_root)
    receipt, raw = download_original(
        archive=previous, attempts=args.attempts, retry_delay=args.retry_delay
    )
    retain_capture(args.out_dir, receipt, raw)
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
