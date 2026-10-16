"""HG009 P016: strict original NSE Q1 FY27 financial HTML source replay.

Only verifies the exact historical original issuer/ISIN/standalone financial
table and the specific P015 amounts. It does not certify October 15 diluted
shares, equity fair value, cashflow, a price target or a trade.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from bs4 import BeautifulSoup

from marketlab.alpha import AlphaContractError, digest

SOURCE_BLOB = "eab274ece7d40e65cf1cb69db7632c1e92206f69"
SOURCE_PATH = Path("registry/hg009_p015_ace_acutaas_q1_sources.json")
ATTEMPT_DIR = Path("research/hg009/p016-originals/attempts")
ARCHIVE_DIR = Path("research/hg009/p016-originals/by-symbol")
Q1_ID = "HG009-P016-20261016-NSE-Q1-ROW-ATTESTATION-v1"
ALLOWED_HOST_PREFIX = "https://nsearchives.nseindia.com/corporate/ixbrl/"
MONEY_LABELS = {
    "paid_up_equity_capital": ("paid-up equity share capital",),
    "face_value_per_share_inr": ("face value of equity share capital",),
    "revenue": ("revenue from operations",),
    "other_income": ("other income",),
    "pbt": ("total profit before tax",),
    "pat": (
        "net profit loss for the period from continuing operations",
        "total profit (loss) for period",
    ),
}


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def original_q1_registry(root: Path) -> tuple[dict, str]:
    raw = (root / SOURCE_PATH).read_bytes()
    if _git_blob(raw) != SOURCE_BLOB:
        raise AlphaContractError("P016 frozen P015 Q1 issuer registry changed")
    record = json.loads(raw)
    if (
        record.get("registry_id")
        != "HG009-P015-ACE-ACUTAAS-Q1FY27-ORIGINAL-NSE-v1"
        or record.get("retained_original_HTML_bytes") is not False
        or len(record.get("issuer_rows", [])) != 2
        or {r["symbol"] for r in record["issuer_rows"]}
        != {"ACE", "ACUTAAS"}
    ):
        raise AlphaContractError("P016 pinned source scope not original")
    return record, hashlib.sha256(raw).hexdigest()


def _cells(table_row) -> list[str]:
    return [
        " ".join(td.get_text(" ", strip=True).split())
        for td in table_row.find_all(("td", "th"), recursive=False)
    ]


def _same_numeric(text: str, amount: object) -> bool:
    cleaned = text.strip().replace(",", "").replace("₹", "")
    if not cleaned or not re.fullmatch(r"\(?-?\d+(?:\.\d+)?\)?", cleaned):
        return False
    try:
        parsed = Decimal(cleaned.strip("()"))
        if cleaned.startswith("("):
            parsed = -parsed
        return parsed == Decimal(str(amount))
    except (InvalidOperation, ValueError):
        return False


def _matching_row(rows: list[list[str]], label: str, expected: object) -> bool:
    for cells in rows:
        labels = [
            idx for idx, cell in enumerate(cells)
            if label in cell.casefold()
        ]
        if not labels:
            continue
        for index in labels:
            if any(_same_numeric(value, expected) for value in cells[index + 1:]):
                return True
    return False


def _identity(rows: list[list[str]], key: str, expected: str) -> bool:
    for cells in rows:
        for pos, cell in enumerate(cells):
            if key == cell.casefold().strip():
                if any(
                    candidate.strip().upper() == expected.upper()
                    for candidate in cells[pos + 1:]
                ):
                    return True
    return False


def validate_q1_html(
    raw: bytes,
    issuer: dict[str, Any],
    *,
    recorded_at_utc: str,
) -> dict[str, Any]:
    if not 100 <= len(raw) <= 3_000_000:
        raise AlphaContractError("P016 source HTML empty or unreasonably large")
    url = issuer["original_url"]
    if (
        not isinstance(url, str)
        or not url.startswith(ALLOWED_HOST_PREFIX)
        or ".." in url
        or "?" in url
    ):
        raise AlphaContractError("P016 issuer original URL outside allowlist")
    try:
        stamp = datetime.fromisoformat(recorded_at_utc)
    except (ValueError, TypeError) as exc:
        raise AlphaContractError("P016 original UTC first-capture timestamp invalid") from exc
    if stamp.tzinfo is None:
        raise AlphaContractError("P016 source capture timestamp not aware")
    soup = BeautifulSoup(raw, "html.parser")
    rows = [_cells(r) for r in soup.find_all("tr")]
    source_text = soup.get_text(" ", strip=True)
    if (
        not rows
        or not _identity(rows, "nse symbol", issuer["symbol"])
        or not _identity(rows, "isin", issuer["isin"])
        or not _identity(rows, "nature of report standalone or consolidated",
                         "Standalone")
        or not _identity(rows, "whether results are audited or unaudited for the quarter ended",
                         "Unaudited")
        or issuer["period_end"] != "2026-06-30"
        or "30-06-2026" not in source_text
        or "Amount in (Lakhs)" not in source_text
    ):
        raise AlphaContractError(
            "P016 issuer/ISIN/quarter/unreviewed audited-status mismatch"
        )

    checks = {}
    for name, labels in MONEY_LABELS.items():
        value = issuer["amounts_in_lakh"][name]
        if type(value) not in (int, float):
            raise AlphaContractError(f"P016 original value not numeric: {name}")
        if not any(_matching_row(rows, label, value) for label in labels):
            raise AlphaContractError(
                f"P016 original NSE financial cell not matched: {name}"
            )
        checks[name] = {
            "expected_inr_lakh": value,
            "original_row_value_verified": True,
        }
    return {
        "attestation_id": Q1_ID,
        "symbol": issuer["symbol"],
        "isin": issuer["isin"],
        "filing_date": issuer["filing_date"],
        "period_end": issuer["period_end"],
        "reporting_basis": "STANDALONE_UNAUDITED_Q1FY27",
        "original_url": url,
        "captured_at_utc": stamp.astimezone(UTC).isoformat(),
        "original_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "original_raw_byte_count": len(raw),
        "verified_statement_fields": checks,
        "original_shares_are_june_basic_not_oct_diluted": True,
        "october_price_belongs_to_separate_original_daily_source": True,
        "normalized_owner_cashflow_established": False,
        "current_equity_value_established": False,
        "live_capital_allowed": False,
    }


def _blocked_record(issuer, captured: datetime, *, state: str,
                    status: int | None = None, failure: str | None = None,
                    raw: bytes | None = None) -> dict:
    return {
        "symbol": issuer["symbol"],
        "isin": issuer["isin"],
        "original_url": issuer["original_url"],
        "captured_at_utc": captured.astimezone(UTC).isoformat(),
        "state": state,
        "http_status": status,
        "reason": failure,
        "untrusted_raw_sha256": None if raw is None else hashlib.sha256(raw).hexdigest(),
        "archive_path": None,
        "source_verified": False,
        "live_capital_allowed": False,
    }


def capture_one_q1(
    issuer: dict,
    *,
    fetch: Callable[[str], tuple[int, bytes | None]],
    observe_now: Callable[[], datetime],
    root: Path,
) -> dict:
    try:
        status, raw = fetch(issuer["original_url"])
    except Exception as exc:
        return _blocked_record(
            issuer, observe_now(), state="ORIGINAL_NSE_HTTP_FAILED",
            failure=type(exc).__name__,
        )
    now = observe_now()
    if now.tzinfo is None:
        raise AlphaContractError("P016 source retrieval clock must have timezone")
    if status != 200 or raw is None:
        return _blocked_record(
            issuer, now, state="ORIGINAL_NSE_NOT_AVAILABLE", status=status
        )
    try:
        verified = validate_q1_html(
            raw, issuer, recorded_at_utc=now.isoformat()
        )
    except AlphaContractError as exc:
        return _blocked_record(
            issuer, now, state="ORIGINAL_NSE_ISSUER_OR_FINANCIAL_MISMATCH",
            status=200, failure=str(exc), raw=raw,
        )
    original = verified["original_raw_sha256"]
    path = root / ARCHIVE_DIR / issuer["symbol"] / f"{original}.html.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = gzip.compress(raw, compresslevel=9, mtime=0)
    if path.exists():
        if path.read_bytes() != blob:
            raise AlphaContractError("P016 original content-addressed byte collision")
    else:
        path.write_bytes(blob)
    record = {
        **verified,
        "state": "ORIGINAL_NSE_Q1_FULL_HTML_REPLAY_VERIFIED",
        "archive_path": str(path.relative_to(root)),
        "source_verified": True,
        "original_html_retained": True,
    }
    record["receipt_sha256"] = digest(record)
    return record


def verify_q1_receipt(receipt: dict, *, issuer: dict, root: Path) -> None:
    if receipt.get("state") != "ORIGINAL_NSE_Q1_FULL_HTML_REPLAY_VERIFIED":
        if receipt.get("source_verified") is not False:
            raise AlphaContractError("P016 failed issuer source was promoted")
        if receipt.get("archive_path") is not None:
            raise AlphaContractError("P016 failed issuer source has fake bytes")
        return
    unsigned = copy.deepcopy(receipt)
    sig = unsigned.pop("receipt_sha256", None)
    if sig != digest(unsigned):
        raise AlphaContractError("P016 issuer raw receipt signature altered")
    path = root / receipt["archive_path"]
    if not path.is_file():
        raise AlphaContractError("P016 original NSE archived HTML absent")
    try:
        raw = gzip.decompress(path.read_bytes())
    except OSError as exc:
        raise AlphaContractError("P016 invalid original HTML gzip bytes") from exc
    expected = validate_q1_html(
        raw, issuer, recorded_at_utc=receipt["captured_at_utc"]
    )
    for key in expected:
        if receipt.get(key) != expected[key]:
            raise AlphaContractError("P016 issuer original row/receipt mismatch")
