"""Acquire exact first-party DEVX FY26 PDF and independent Oct 8 credit review.

This source-only pipeline refuses altered URLs, access bypass, broken PDFs,
unrelated HTML and investment-grade promotions. It does not decide what
multiple, EBITDA or price target should apply to the prospective Winston.
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
from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError

SOURCE_ID = "HG007-P013-DEVX-FY26-LEASE-AND-OCT8-CREDIT-ORIGINALS-v1"
NSE_PDF_URL = "https://nsearchives.nseindia.com/corporate/DEVACCE_20052026134050_SE_Investors_Presentation.pdf"
ACUITE_URL = "https://connect.acuite.in/fcompany-details/DEV_ACCELERATOR_LIMITED/8th_Oct_26"
MAX_BYTES = {"nse_pdf": 15_000_000, "acuite_html": 2_000_000}
ALLOWED = ("nse_pdf", "acuite_html")
FAILURES = {"ACCESS_BLOCKED", "NOT_PUBLISHED", "UNFOLLOWED_REDIRECT", "INVALID_DOCUMENT", "FETCH_FAILED"}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pdf_pages(raw: bytes) -> list[str]:
    if (
        not isinstance(raw, bytes)
        or not 10_000 <= len(raw) <= MAX_BYTES["nse_pdf"]
        or not raw.startswith(b"%PDF-")
        or b"%%EOF" not in raw[-2048:]
    ):
        raise ValueError("NSE investor presentation PDF original byte envelope failed")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if len(reader.pages) != 34:
            raise ValueError("NSE official DEVX investor PDF is not 34 pages")
        pages = [p.extract_text() or "" for p in reader.pages]
    except (PdfReadError, KeyError, OSError, TypeError, ValueError) as exc:
        raise ValueError("original NSE DEVX investor PDF pages unavailable") from exc
    if any(len(p.strip()) < 15 for p in pages[:2]):
        raise ValueError("original PDF cover/title cannot be read")
    return pages


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def validate_original(kind: str, raw: bytes) -> dict[str, Any]:
    """Return source locator and hash *only*, never grant economic verification."""
    if kind not in ALLOWED:
        raise ValueError("unknown DEVX source family")
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES[kind]:
        raise ValueError("original source bytes absent or outside bounded limit")
    if kind == "nse_pdf":
        pages = _pdf_pages(raw)
        cover = _normal(" ".join(pages[:2]))
        source = _normal("\n".join(pages))
        for token in ("dev accelerator", "devx"):
            if token not in cover:
                raise ValueError(f"original NSE PDF cover issuer/date mismatch: {token}")
        if "20th may, 2026" not in cover and "may 20, 2026" not in cover:
            raise ValueError("original NSE PDF cover issuer/date mismatch: 20 May 2026")
        for token in (
            "standalone financial metrics",
            "cash ebit",
            "103.46",
            "36.55",
            "66.92",
            "450,000",
        ):
            if token not in source and not (token == "450,000" and "winston" in source):
                raise ValueError(f"original NSE DEVX PDF missing expected earnings/lease term: {token}")
        return {
            "page_count": len(pages),
            "page_text_sha256": [hashlib.sha256(p.encode()).hexdigest() for p in pages],
            "snapshot_fy": "2025-26",
            "issuer_symbol": "DEVX",
            "standalone_indas_ebitda_cr_source_number_text_present": True,
            "standalone_cash_ebit_cr_source_number_text_present": True,
            "lease_rent_outflow_cr_source_number_text_present": True,
            "winston_signed_not_recognized_as_current_cash_flow": True,
        }
    # The original Acuite site serves fragments and prefixed server markup
    # without a reliable DOCTYPE. Identity is established by fixed original
    # HTTPS endpoint plus full source content, not its first ten bytes.
    decoded = raw.decode("utf-8-sig", errors="strict")
    if "\x00" in decoded:
        raise ValueError("original Acuite HTML contains binary/null bytes")
    parsed = BeautifulSoup(decoded, "html.parser")
    if parsed.find(["html", "body", "table", "h1", "p", "div"]) is None:
        raise ValueError("credit rating response lacks HTML document elements")
    text = _normal(parsed.get_text(" ", strip=True))
    if len(text) < 3500:
        raise ValueError("credit rating page unusually short")
    for token in (
        "dev accelerator limited",
        "october 08, 2026",
        "acuite bbb",
        "stable",
        "3.11",
        "1.32",
        "lease liabilities",
        "non convertible debentures",
        "ahmedabad",
    ):
        if token not in text:
            raise ValueError(f"Acuite Oct 8 credit page identity/credit clause missing: {token}")
    return {
        "source_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source_text_chars": len(text),
        "issuer": "DEV ACCELERATOR LIMITED",
        "source_rating_date": "2026-10-08",
        "rating": "ACUITE BBB / Stable",
        "no_issuer_audit_or_equity_investment_approval": True,
    }


def acquire_source(
    kind: str, *, attempts: int = 2, sleep_seconds: float = 3
) -> tuple[dict[str, Any], bytes | None]:
    if kind not in ALLOWED:
        raise ValueError("unknown original DEVX source")
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("attempts must be 1-3")
    if type(sleep_seconds) not in (float, int) or not 0 <= sleep_seconds <= 30:
        raise ValueError("invalid source retry interval")
    url = NSE_PDF_URL if kind == "nse_pdf" else ACUITE_URL
    code: int | None = None
    reason = "NO_OFFICIAL_ORIGINAL_RESPONSE"
    state = "FETCH_FAILED"
    for attempt in range(attempts):
        try:
            response = requests.get(
                url, timeout=30, allow_redirects=False,
                headers={"User-Agent": "marketlab-devx-original-research/1.0",
                         "Accept": "application/pdf" if kind == "nse_pdf" else "text/html"},
            )
            code = response.status_code
            if getattr(response, "url", url) != url:
                state = "UNFOLLOWED_REDIRECT"
                reason = "ACTUAL_RESPONSE_URL_MISMATCH"
                break
            if code == 200:
                raw = response.content
                try:
                    evidence = validate_original(kind, raw)
                except (UnicodeDecodeError, ValueError) as exc:
                    state = "INVALID_DOCUMENT"
                    reason = str(exc)
                    break
                return {
                    "schema_version": 1,
                    "source_id": SOURCE_ID,
                    "source_kind": kind,
                    "url": url,
                    "http_status": 200,
                    "status": "SOURCE_CAPTURED_IDENTITY_CHECKED",
                    "captured_at_utc": _now(),
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "raw_byte_count": len(raw),
                    "structural_evidence": evidence,
                    "original_page_layout_semantic_approved": False,
                    "winston_operating_earnings_verified": False,
                    "post_ncd_company_net_debt_verified": False,
                    "target_price_or_expected_return_calculated": False,
                    "portfolio_eligibility_allowed": False,
                    "live_capital_allowed": False,
                }, raw
            if code in (401, 403, 429):
                state, reason = "ACCESS_BLOCKED", f"HTTP_{code}_NO_BYPASS"
                break
            if code == 404:
                state, reason = "NOT_PUBLISHED", "EXACT_ORIGINAL_URL_NOT_AVAILABLE"
                break
            if 300 <= code < 400:
                state, reason = "UNFOLLOWED_REDIRECT", f"HTTP_{code}_NO_FOLLOW"
                break
            reason = f"HTTP_{code}_OR_EMPTY"
            if code < 500:
                break
        except requests.RequestException as exc:
            reason = type(exc).__name__
        if attempt + 1 < attempts:
            time.sleep(sleep_seconds)
    else:
        state = "FETCH_FAILED"
    return {
        "schema_version": 1,
        "source_id": SOURCE_ID,
        "source_kind": kind,
        "url": url,
        "http_status": code,
        "status": state,
        "captured_at_utc": _now(),
        "raw_sha256": None,
        "raw_byte_count": None,
        "reason": reason,
        "structural_evidence": None,
        "original_page_layout_semantic_approved": False,
        "winston_operating_earnings_verified": False,
        "post_ncd_company_net_debt_verified": False,
        "target_price_or_expected_return_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }, None


def retain_sources(
    output_root: Path, results: dict[str, tuple[dict, bytes | None]]
) -> dict[str, Any]:
    if set(results) != set(ALLOWED):
        raise ValueError("exact NSE PDF + Acuite HTML results required")
    output_root.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for kind in ALLOWED:
        receipt, raw = results[kind]
        if receipt.get("source_kind") != kind or receipt.get("source_id") != SOURCE_ID:
            raise ValueError("original source receipt kind/identity changed")
        if raw is not None:
            validated = validate_original(kind, raw)
            digest = hashlib.sha256(raw).hexdigest()
            if (
                receipt.get("status") != "SOURCE_CAPTURED_IDENTITY_CHECKED"
                or receipt.get("raw_sha256") != digest
                or receipt.get("raw_byte_count") != len(raw)
                or receipt.get("structural_evidence") != validated
            ):
                raise ValueError("original source bytes differ from source receipt")
            dest = output_root / "raw" / "sha256" / f"{digest}{'.pdf' if kind == 'nse_pdf' else '.html'}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.read_bytes() != raw:
                raise ValueError("immutable original DEVX content-addressed source differs")
            dest.write_bytes(raw)
            if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
                raise ValueError("stored original DEVX source lost its SHA256")
        elif receipt.get("raw_sha256") is not None:
            raise ValueError("unavailable source falsely contains original sha256")
        receipts[kind] = receipt

    out = {
        "schema_version": 1,
        "source_bundle_id": SOURCE_ID,
        "source_statuses": {kind: receipts[kind]["status"] for kind in ALLOWED},
        "source_receipts": receipts,
        "both_independent_originals_available": all(
            receipts[kind]["status"] == "SOURCE_CAPTURED_IDENTITY_CHECKED"
            for kind in ALLOWED
        ),
        "total_return_outcomes_opened": False,
        "company_expected_returns_calculated": False,
        "stock_selection_changed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    packet_path = output_root / "bundle-attempt.json"
    packet_path.write_text(
        json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+"\n",
        encoding="utf-8",
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=3)
    args = parser.parse_args()
    results = {
        kind: acquire_source(kind, attempts=args.attempts, sleep_seconds=args.sleep_seconds)
        for kind in ALLOWED
    }
    report = retain_sources(args.out_dir, results)
    print(json.dumps(report, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
