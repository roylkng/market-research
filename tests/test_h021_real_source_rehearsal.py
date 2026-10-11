from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from marketlab.h021_real_source_rehearsal import (
    FIRST_OPEN_UTC,
    ORIGINAL_TRADING_DAY,
    SOURCE_ZIP_PATH,
    SOURCE_ZIP_SHA256,
    SOURCE_ZIP_SIZE,
    rehearse_original_official_files,
    validate_pre_entry_rehearsal,
)
from marketlab.marketdata import index_snapshot_url
from scripts.acquire_h021_first_entry import load_and_verify_sources
from scripts.rehearse_h021_original_market_sources import acquire_prior_index

RECORDED = "2026-10-11T10:05:00Z"
CAPTURED = "2026-10-11T10:04:30Z"


def _index_csv() -> bytes:
    return (
        b"Index Name,Index Date,Open Index Value,Closing Index Value\n"
        b"Nifty 50,09-10-2026,25125,25232\n"
        b"Nifty 500,09-10-2026,23001.12,23102.19\n"
    )


def _source(
    raw: bytes | None = None,
    *,
    status: str = "OK",
    timestamp: str = CAPTURED,
) -> dict:
    return {
        "url": index_snapshot_url(ORIGINAL_TRADING_DAY),
        "status": status,
        "http_status": 200 if status == "OK" else 403,
        "raw": _index_csv() if raw is None and status == "OK" else raw,
        "error": None if status == "OK" else "HTTP_403_NO_BYPASS",
        "captured_at_utc": timestamp,
    }


def _inputs() -> tuple[dict, dict, bytes]:
    intent, universe = load_and_verify_sources()
    raw = Path(SOURCE_ZIP_PATH).read_bytes()
    assert len(raw) == SOURCE_ZIP_SIZE
    return intent, universe, raw


def test_real_original_oct9_nse_zip_parses_all_ten_unchanged_selections() -> None:
    intent, universe, raw = _inputs()
    original_intent = deepcopy(intent)
    packet = rehearse_original_official_files(
        intent, universe, original_oct9_zip=raw,
        index_source=_source(), rehearsal_at_utc=RECORDED,
    )
    validate_pre_entry_rehearsal(packet)
    assert packet["real_stock_row_valid_count"] == 10
    assert packet["selected_stock_identity_count"] == 10
    assert packet["rehearsal_state"] == "VALIDATED_REAL_OCT9_STOCK_AND_INDEX_SOURCE_FORMATS"
    assert packet["original_oct9_udiff_source_sha256"] == SOURCE_ZIP_SHA256
    assert packet["original_oct9_udiff_source_bytes"] == SOURCE_ZIP_SIZE
    assert [r["symbol"] for r in packet["stock_parser_receipts"]] == [
        "VEDL", "ETERNAL", "DMART", "IDEA", "ADANIENSOL",
        "JSWSTEEL", "COALINDIA", "INFY", "GAIL", "POWERGRID",
    ]
    assert all(
        r["status"] == "ORIGINAL_OCT9_EQ_OHLC_SCHEMA_VALIDATED_NO_PRICES_RELEASED"
        for r in packet["stock_parser_receipts"]
    )
    assert all(r["market_price_values_disclosed_in_rehearsal"] is False
               for r in packet["stock_parser_receipts"])
    assert packet["index_source_receipt"]["parser_identity_ready"] is True
    assert packet["index_source_receipt"]["raw_sha256"] is not None
    for flag in (
        "actual_oct12_price_rows_observed", "index_and_stock_return_observed",
        "entry_trade_filled", "selection_changed", "corporate_actions_verified",
        "dividends_adjusted", "portfolio_eligibility_allowed", "live_capital_allowed",
    ):
        assert packet[flag] is False
    assert intent == original_intent


def test_live_index_block_never_masquerades_as_completed_benchmark() -> None:
    intent, universe, raw = _inputs()
    packet = rehearse_original_official_files(
        intent, universe, original_oct9_zip=raw,
        index_source=_source(raw=None,status="ACCESS_BLOCKED"),
        rehearsal_at_utc=RECORDED,
    )
    assert packet["real_stock_row_valid_count"] == 10
    assert packet["rehearsal_state"] == "SOURCE_FORMAT_OR_ACCESS_BLOCKED_EXPLICITLY"
    assert packet["index_source_receipt"]["status"] == "ACCESS_BLOCKED"
    assert packet["index_source_receipt"]["raw_sha256"] is None
    assert packet["index_source_receipt"]["parser_identity_ready"] is False
    assert packet["live_capital_allowed"] is False
    validate_pre_entry_rehearsal(packet)


def test_syntactically_valid_but_wrong_index_date_fails_closed() -> None:
    intent, universe, raw = _inputs()
    bad_index = _index_csv().replace(b"09-10-2026", b"08-10-2026")
    packet = rehearse_original_official_files(
        intent, universe, original_oct9_zip=raw,
        index_source=_source(bad_index),
        rehearsal_at_utc=RECORDED,
    )
    assert packet["real_stock_row_valid_count"] == 10
    assert packet["index_source_receipt"]["parser_identity_ready"] is False
    assert packet["rehearsal_state"] == "SOURCE_FORMAT_OR_ACCESS_BLOCKED_EXPLICITLY"


def test_refuse_oct12_open_or_pre_oct9_close_rehearsal() -> None:
    intent, universe, raw = _inputs()
    assert FIRST_OPEN_UTC.isoformat() == "2026-10-12T03:45:00+00:00"
    for time in ("2026-10-09T09:00:00Z", "2026-10-12T03:45:00Z"):
        with pytest.raises(ValueError, match="after Oct9 close and before Oct12 open"):
            rehearse_original_official_files(
                intent, universe, original_oct9_zip=raw,
                index_source=_source(), rehearsal_at_utc=time,
            )


def test_original_stock_zip_and_frozen_intent_cannot_be_replaced() -> None:
    intent, universe, raw = _inputs()
    with pytest.raises(ValueError, match="original source bytes changed"):
        rehearse_original_official_files(
            intent, universe, original_oct9_zip=raw + b"aftermarket",
            index_source=_source(), rehearsal_at_utc=RECORDED,
        )
    modified = deepcopy(intent)
    modified["selected_observations"][0]["symbol"] = "TRENT"
    with pytest.raises(ValueError, match="selection"):
        rehearse_original_official_files(
            modified, universe, original_oct9_zip=raw,
            index_source=_source(), rehearsal_at_utc=RECORDED,
        )


def test_no_spoofed_index_url_future_capture_or_receipt_drift() -> None:
    intent, universe, raw = _inputs()
    wrong = _source()
    wrong["url"] = "https://archives.nseindia.com.evil.invalid/index.csv"
    with pytest.raises(ValueError, match="index source URL"):
        rehearse_original_official_files(
            intent, universe, original_oct9_zip=raw,
            index_source=wrong, rehearsal_at_utc=RECORDED,
        )

    with pytest.raises(ValueError, match="capture outside pre-entry"):
        rehearse_original_official_files(
            intent, universe, original_oct9_zip=raw,
            index_source=_source(timestamp="2026-10-12T10:01:00Z"),
            rehearsal_at_utc=RECORDED,
        )
    packet = rehearse_original_official_files(
        intent, universe, original_oct9_zip=raw,
        index_source=_source(), rehearsal_at_utc=RECORDED,
    )
    packet["stock_parser_receipts"][0]["status"] = "FAKE_PROFIT"
    with pytest.raises(ValueError, match="modified"):
        validate_pre_entry_rehearsal(packet)


def test_index_download_http403_does_not_retry_or_follow_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.rehearse_h021_original_market_sources as module

    calls = []

    class FakeResponse:
        status_code = 403
        content = b"<html>blocked</html>"

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(module.requests, "get", fake_get)
    receipt = acquire_prior_index()
    assert receipt["status"] == "ACCESS_BLOCKED"
    assert receipt["http_status"] == 403
    assert receipt["raw"] is None
    assert len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][0] == index_snapshot_url(date(2026, 10, 9))


def test_index_source_is_excluded_from_rehearsal_selection() -> None:
    intent, universe, raw = _inputs()
    observed = rehearse_original_official_files(
        intent, universe, original_oct9_zip=raw,
        index_source=_source(), rehearsal_at_utc=RECORDED,
    )
    assert observed["pre_future_entry_intent_unchanged"] is True
    assert observed["source_session"] == "2026-10-09"
    assert observed["planned_future_entry_session"] == "2026-10-12"
    assert "selected" not in json.dumps(observed).lower() or (
        observed["selected_stock_identity_count"] == 10
    )
