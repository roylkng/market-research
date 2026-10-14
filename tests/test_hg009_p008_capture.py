"""No issuer/source swap can silently become P008 valuation evidence."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p008_capture import capture_issuer, validate_issuer_html
from marketlab.hg009_p008_underwriting import load_sources

ROOT = Path(__file__).resolve().parents[1]


def _acutaas_facts() -> dict:
    table = load_sources(ROOT)[0]["new_fy26"]["numeric_facts"]
    return next(f for f in table if f["symbol"] == "ACUTAAS")


def _html(*, symbol: str = "ACUTAAS", cfo: str = "29,217.36") -> bytes:
    return (
        "<html><body>"
        f"<p>NSE Symbol {symbol} ISIN INE00FF01025</p>"
        "<p>Consolidated Audited year ended 31-03-2026 INR Lakhs</p>"
        "<table>"
        "<tr><td>Profit before tax</td><td>48,272.57</td></tr>"
        f"<tr><td>Net cash flows from (used in)\n                        operating activities</td>"
        f"<td>{cfo}</td></tr>"
        "<tr><td>Purchase of property, plant and equipment</td>"
        "<td>32,797.88</td></tr>"
        "</table></body></html>"
    ).encode()


def test_source_bytes_confirm_exact_symbol_and_source_cash_rows():
    fact = _acutaas_facts()
    raw = _html()
    result = validate_issuer_html(
        raw, fact, observed_at_utc="2026-10-14T12:00:00+00:00"
    )
    assert result["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["raw_byte_count"] == len(raw)
    assert result["symbol"] == "ACUTAAS"
    assert result["isin"] == "INE00FF01025"
    assert result["live_capital_allowed"] is False
    assert result["financial_values_are_normalized_owner_fcf"] is False


def test_missing_cfo_or_wrong_issuer_cannot_satisfy_original():
    fact = _acutaas_facts()
    with pytest.raises(AlphaContractError, match="statement row unverified"):
        validate_issuer_html(
            _html(cfo="99,999.99"), fact,
            observed_at_utc="2026-10-14T12:00:00Z",
        )
    with pytest.raises(AlphaContractError, match="symbol/ISIN"):
        validate_issuer_html(
            _html(symbol="NOT_THE_ISSUER"), fact,
            observed_at_utc="2026-10-14T12:00:00Z",
        )


def test_synthetic_source_is_content_addressed_on_disk(tmp_path: Path):
    fact = _acutaas_facts()
    raw = _html()
    result = capture_issuer(
        fact,
        fetch=lambda url: (200, raw),
        now_utc=datetime(2026, 10, 14, 12, 0, tzinfo=UTC),
        root=tmp_path,
    )
    assert result["state"] == "ORIGINAL_RAW_ARCHIVED_WITH_VERIFIED_ROWS"
    path = tmp_path / result["original_raw_repo_path"]
    assert path.exists()
    assert gzip.decompress(path.read_bytes()) == raw
    assert result["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["receipt_sha256"]
    assert result["live_capital_allowed"] is False
    assert capture_issuer(
        fact,
        fetch=lambda url: (200, raw),
        now_utc=datetime(2026, 10, 14, 12, 1, tzinfo=UTC),
        root=tmp_path,
    )["raw_sha256"] == result["raw_sha256"]


def test_403_or_bad_html_creates_explicit_nonpromotable_source_receipt(tmp_path: Path):
    fact = _acutaas_facts()
    missing = capture_issuer(
        fact, fetch=lambda url: (403, None),
        now_utc=datetime(2026, 10, 14, 12, 0, tzinfo=UTC),
        root=tmp_path,
    )
    assert missing["state"] == "BLOCKED_ORIGINAL_NSE_HTTP"
    assert missing["raw_sha256"] is None
    assert missing["live_capital_allowed"] is False

    malformed = capture_issuer(
        fact, fetch=lambda url: (200, b"malformed NSE candidate"),
        now_utc=datetime(2026, 10, 14, 12, 0, tzinfo=UTC),
        root=tmp_path,
    )
    assert malformed["state"] == "BLOCKED_ORIGINAL_NSE_IDENTITY_OR_CASH_ROW"
    assert malformed["original_raw_repo_path"] is None
    assert malformed["financial_fields_cleared_for_valuation"] is False
    quarantined = tmp_path / malformed["quarantined_source_path_not_validated"]
    assert gzip.decompress(quarantined.read_bytes()) == b"malformed NSE candidate"
    assert "symbol/ISIN" in malformed["blocked_reason"]


def test_original_source_capture_script_not_network_run_by_unit_suite():
    from marketlab.hg009_p008_capture import EXPECTED_ROWS

    assert set(EXPECTED_ROWS) == {"pretax_profit", "operating_cfo", "ppe_purchase"}
    assert len(load_sources(ROOT)[0]["new_fy26"]["numeric_facts"]) == 3
    assert json.dumps(_acutaas_facts())  # statement metadata is JSON-serializable



def test_newline_inside_original_issuer_cashflow_row_is_not_false_rejection():
    # Archived NSE originals use a literal LF inside the text cell. A separate
    # space inserted between HTML nodes is not enough to normalize that LF.
    raw = _html()
    assert b"\n                        operating activities" in raw
    result = validate_issuer_html(
        raw, _acutaas_facts(), observed_at_utc="2026-10-14T19:00:00Z"
    )
    assert result["validation_state"] == (
        "ORIGINAL_NSE_FY26_CASHFLOW_SOURCE_BYTES_ROW_MATCHED"
    )
