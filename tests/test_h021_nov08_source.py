from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from marketlab.h021_nov08_source import (
    SOURCE_RELEASE_NOT_BEFORE,
    SUNDAY,
    build_h021_muhurat_source,
    validate_h021_muhurat_source,
)
from marketlab.marketdata import index_snapshot_url, udiff_url
from scripts import collect_h021_nov08_source as collection

CAPTURE = "2026-11-08T11:50:00Z"
RECORD = "2026-11-08T12:00:00Z"


def _udiff(universe: dict, *, missing: str | None = None) -> bytes:
    symbols = (
        "VEDL", "ETERNAL", "DMART", "IDEA", "ADANIENSOL",
        "JSWSTEEL", "COALINDIA", "INFY", "GAIL", "POWERGRID",
    )
    isin = {row["symbol"]: row["isin"] for row in universe["members"]}
    buf = io.StringIO()
    columns = (
        "TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb",
        "SctySrs", "OpnPric", "HghPric", "LwPric", "ClsPric",
    )
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    for offset, symbol in enumerate(symbols):
        if symbol == missing:
            continue
        price = 100 + offset
        writer.writerow({
            "TradDt": "2026-11-08", "Sgmt": "CM", "Src": "NSE",
            "FinInstrmTp": "STK", "ISIN": isin[symbol],
            "TckrSymb": symbol, "SctySrs": "EQ",
            "OpnPric": price, "HghPric": price + 3,
            "LwPric": price - 2, "ClsPric": price + 1,
        })
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr(
            "BhavCopy_NSE_CM_0_0_0_20261108_F_0000.csv", buf.getvalue()
        )
    return raw.getvalue()


def _index() -> bytes:
    return (
        b"Index Name,Index Date,Open Index Value,Closing Index Value\n"
        b"Nifty 500,08-11-2026,23000,23025\n"
    )


def _source(name: str, body: bytes | None) -> dict:
    url = udiff_url(SUNDAY) if name == "udiff" else index_snapshot_url(SUNDAY)
    return {
        "status": "OK" if body is not None else "NOT_PUBLISHED",
        "url": url,
        "captured_at_utc": CAPTURE,
        "http_status": 200 if body is not None else 404,
        "raw": body,
        "error": None if body is not None else "OFFICIAL_SUNDAY_SOURCE_NOT_PUBLISHED",
    }


def _build(
    *, missing: str | None = None, index: bytes | None = None,
    capture: str = CAPTURE, recorded: str = RECORD,
) -> dict:
    intent, universe, clock = collection.load_source_ancestry()
    udiff = _source("udiff", _udiff(universe, missing=missing))
    source_index = _source("index", _index() if index is None else index)
    udiff["captured_at_utc"] = capture
    source_index["captured_at_utc"] = capture
    return build_h021_muhurat_source(
        intent, universe, clock, udiff_source=udiff,
        index_source=source_index, recorded_at_utc=recorded,
    )


def test_p023_archived_immutable_source_ancestry() -> None:
    intent, universe, clock = collection.load_source_ancestry()
    assert intent["intent_id"] == "H021-P003-2026-10-09-FIRST-COHORT-v1"
    assert len(universe["members"]) == 100
    assert clock["H021_20_completed_sessions_calendar_exit_ist"] == (
        SUNDAY.isoformat()
    )
    assert SOURCE_RELEASE_NOT_BEFORE.isoformat() == "2026-11-08T10:45:00+00:00"


def test_original_sunday_ohlc_is_source_only_and_unadjusted() -> None:
    packet = _build()
    validate_h021_muhurat_source(packet)
    assert packet["special_session_date_ist"] == "2026-11-08"
    assert packet["capture_state"] == "SOURCE_COMPLETE_NOT_ECONOMIC_RETURN"
    assert packet["observed_issuer_stock_ohlc_count"] == 10
    assert len(packet["stocks"]) == 10
    assert packet["stocks"][0]["symbol"] == "VEDL"
    assert packet["stocks"][0]["original_unadjusted_ohlc_inr"]["open_inr"] == 100
    assert packet["benchmark"]["close"] == 23025
    assert packet["original_stock_and_index_row_coverage_complete"] is True
    assert packet["benchmark"]["basis"] == "ORIGINAL_NSE_PRICE_INDEX_NOT_TRI"
    for field in (
        "H021_H20_trading_return_or_index_excess_calculated",
        "actual_execution_and_fees_verified",
        "CAS_nonCAS_security_specific_close_basis_verified",
        "corporate_action_and_dividend_total_return_verified",
        "H021_60_official_2027_calendar_verified",
        "equity_expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert packet[field] is False


def test_unpublished_index_and_stock_row_dont_create_economic_prices() -> None:
    intent, universe, clock = collection.load_source_ancestry()
    packet = build_h021_muhurat_source(
        intent, universe, clock,
        udiff_source=_source("udiff", _udiff(universe, missing="IDEA")),
        index_source=_source("index", None),
        recorded_at_utc=RECORD,
    )
    assert packet["capture_state"] == "SOURCE_INCOMPLETE_NO_FABRICATED_PRICE"
    idea = next(x for x in packet["stocks"] if x["symbol"] == "IDEA")
    assert idea["state"] == "OFFICIAL_EQ_IDENTITY_ABSENT"
    assert idea["original_unadjusted_ohlc_inr"]["close_inr"] is None
    assert packet["benchmark"]["close"] is None
    assert packet["original_stock_and_index_row_coverage_complete"] is False


def test_source_fails_closed_before_nov08_special_trading_and_for_spoofed_url() -> None:
    intent, universe, clock = collection.load_source_ancestry()
    with pytest.raises(ValueError, match="before all exchange trading cutoffs"):
        _build(recorded="2026-11-08T10:30:00Z")
    with pytest.raises(ValueError, match="before official session close"):
        _build(capture="2026-11-08T10:30:00Z")
    u = _source("udiff", _udiff(universe))
    u["url"] = "https://example.invalid/forged-20261108.zip"
    with pytest.raises(ValueError, match="unexpected NSE source URL"):
        build_h021_muhurat_source(
            intent, universe, clock, udiff_source=u,
            index_source=_source("index", _index()), recorded_at_utc=RECORD,
        )


def test_source_packet_cannot_become_fake_market_returns() -> None:
    original = _build()
    before = deepcopy(original)
    forged = deepcopy(original)
    forged["stocks"][0]["original_unadjusted_ohlc_inr"]["close_inr"] = 999
    with pytest.raises(ValueError, match="packet hash changed"):
        validate_h021_muhurat_source(forged)
    for key in (
        "H021_H20_trading_return_or_index_excess_calculated",
        "CAS_nonCAS_security_specific_close_basis_verified",
        "live_capital_allowed",
    ):
        forged = deepcopy(original)
        forged[key] = True
        with pytest.raises(ValueError, match="packet hash changed"):
            validate_h021_muhurat_source(forged)
    assert original == before


def test_source_tries_only_exact_nse_date_and_respects_http_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Denied:
        status_code = 403
        content = b"Forbidden"
        url = udiff_url(SUNDAY)

    def fake_get(url: str, **kwargs: object) -> Denied:
        calls.append((url, kwargs))
        return Denied()

    monkeypatch.setattr(collection.requests, "get", fake_get)
    item = collection.fetch_exact_source(udiff_url(SUNDAY), attempts=3, sleep_seconds=0)
    assert item["status"] == "ACCESS_BLOCKED"
    assert item["raw"] is None
    assert len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False
    with pytest.raises(ValueError, match="only 8 Nov"):
        collection.fetch_exact_source(udiff_url(date(2026, 11, 9)))


def test_receipt_and_raw_source_sha_retained_without_trade(tmp_path: Path) -> None:
    intent, universe, clock = collection.load_source_ancestry()
    raw = _udiff(universe)
    index = _index()
    receipt = collection.persist_source_attempt(
        tmp_path, intent=intent, universe=universe, amendment=clock,
        udiff=_source("udiff", raw), index=_source("index", index),
        recorded_at_utc=RECORD,
    )
    assert receipt["captured_result"] == "SOURCE_COMPLETE_NOT_ECONOMIC_RETURN"
    assert receipt["benchmark_excess_returns_opened"] is False
    packet = json.loads(
        (tmp_path / "special-source-observation-v1.json").read_text(encoding="utf-8")
    )
    validate_h021_muhurat_source(packet)
    for retained in receipt["originals_retained"]:
        source_bytes = (tmp_path / retained["relative_path"]).read_bytes()
        assert hashlib.sha256(source_bytes).hexdigest() == retained["original_sha256"]
