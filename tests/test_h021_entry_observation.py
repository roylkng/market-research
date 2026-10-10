from __future__ import annotations

import csv
import io
import json
import zipfile
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from marketlab.h021_entry_observation import (
    ENTRY_DAY,
    EXPECTED_SELECTION,
    build_entry_observation,
    validate_entry_observation,
)
from marketlab.marketdata import index_snapshot_url, udiff_url
from scripts.acquire_h021_first_entry import (
    download_official_source,
    load_and_verify_sources,
    write_acquisition,
)

CAPTURE_UTC = "2026-10-12T13:30:00Z"
RECORD_UTC = "2026-10-12T13:45:00Z"


def _udiff(universe: dict, *, omit: str | None = None, wrong_isin: str | None = None) -> bytes:
    by_symbol = {item["symbol"]: item["isin"] for item in universe["members"]}
    stream = io.StringIO()
    fields = [
        "TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb",
        "SctySrs", "OpnPric", "HghPric", "LwPric", "ClsPric",
    ]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for i, symbol in enumerate(EXPECTED_SELECTION):
        if symbol == omit:
            continue
        price = 100 + i
        writer.writerow({
            "TradDt": ENTRY_DAY,
            "Sgmt": "CM",
            "Src": "NSE",
            "FinInstrmTp": "STK",
            "ISIN": "INVALIDISIN0" if symbol == wrong_isin else by_symbol[symbol],
            "TckrSymb": symbol,
            "SctySrs": "EQ",
            "OpnPric": f"{price:.2f}",
            "HghPric": f"{price + 1:.2f}",
            "LwPric": f"{price - 1:.2f}",
            "ClsPric": f"{price + 0.5:.2f}",
        })
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("BhavCopy_NSE_CM_0_0_0_20261012_F_0000.csv", stream.getvalue())
    return buffer.getvalue()


def _index() -> bytes:
    return (
        b"Index Name,Index Date,Open Index Value,Closing Index Value\n"
        b"Nifty 50,12-10-2026,25000,25200\n"
        b"Nifty 500,12-10-2026,23200.50,23301.75\n"
    )


def _source(name: str, raw: bytes | None, status: str = "OK") -> dict:
    return {
        "url": (
            udiff_url(date(2026, 10, 12))
            if name == "udiff"
            else index_snapshot_url(date(2026, 10, 12))
        ),
        "captured_at_utc": CAPTURE_UTC,
        "status": status,
        "http_status": 200 if status == "OK" else 404,
        "raw": raw,
        "error": None if status == "OK" else "OFFICIAL_NOT_PUBLISHED",
    }


def test_immutable_source_identity_before_market_data() -> None:
    intent, universe = load_and_verify_sources()
    assert intent["primary_top_decile_count"] == 10
    assert universe["cohort_id"] == "FY27-Q2-2026-09-06"
    assert [r["symbol"] for r in intent["selected_observations"]] == list(
        EXPECTED_SELECTION
    )


def test_all_ten_stock_opens_and_nifty500_index_observed_without_trade() -> None:
    intent, universe = load_and_verify_sources()
    original_intent = deepcopy(intent)
    original_universe = deepcopy(universe)
    packet = build_entry_observation(
        intent,
        universe,
        udiff_source=_source("udiff", _udiff(universe)),
        index_source=_source("index", _index()),
        recorded_at_utc=RECORD_UTC,
    )
    validate_entry_observation(packet)
    assert packet["source_observation_status"] == "FULL_OFFICIAL_OHLC_SOURCE_OBSERVED"
    assert packet["observed_official_stock_open_count"] == 10
    assert [r["symbol"] for r in packet["stock_observations"]] == list(
        EXPECTED_SELECTION
    )
    assert packet["stock_observations"][0]["open_price_inr"] == 100.0
    assert packet["benchmark_observation"]["open_index_value"] == 23200.5
    assert packet["benchmark_observation"]["basis"] == "PRICE_INDEX_NOT_TRI"
    assert all(r["actual_trade_fill_confirmed"] is False for r in packet["stock_observations"])
    for flag in (
        "return_outcomes_opened", "expected_returns_calculated",
        "entry_trades_executed", "live_capital_allowed",
        "portfolio_eligibility_allowed", "execution_and_liquidity_verified",
        "corporate_action_adjustments_verified", "dividends_and_total_return_basis_verified",
    ):
        assert packet[flag] is False
    assert intent == original_intent
    assert universe == original_universe


def test_missing_stock_and_identity_mismatch_never_get_prices() -> None:
    intent, universe = load_and_verify_sources()
    packet = build_entry_observation(
        intent, universe,
        udiff_source=_source("udiff", _udiff(universe, omit="VEDL", wrong_isin="GAIL")),
        index_source=_source("index", _index()),
        recorded_at_utc=RECORD_UTC,
    )
    by_symbol = {row["symbol"]: row for row in packet["stock_observations"]}
    assert by_symbol["VEDL"]["status"] == "NO_OFFICIAL_EQ_ROW"
    assert by_symbol["VEDL"]["open_price_inr"] is None
    assert by_symbol["GAIL"]["status"] == "PARSER_OR_IDENTITY_ERROR"
    assert by_symbol["GAIL"]["open_price_inr"] is None
    assert packet["observed_official_stock_open_count"] == 8
    assert packet["source_observation_status"] == "PARTIAL_OR_BLOCKED_SOURCE_OBSERVATION"


def test_unavailable_or_invalid_official_source_is_recorded_without_fills() -> None:
    intent, universe = load_and_verify_sources()
    blocked = _source("udiff", None, status="NOT_PUBLISHED")
    packet = build_entry_observation(
        intent, universe,
        udiff_source=blocked,
        index_source=_source("index", _index()),
        recorded_at_utc=RECORD_UTC,
    )
    assert packet["observed_official_stock_open_count"] == 0
    assert all(row["open_price_inr"] is None for row in packet["stock_observations"])
    assert packet["source_receipts"]["udiff"]["status"] == "NOT_PUBLISHED"

    corrupted = _source("udiff", b"not-a-real-zip")
    packet = build_entry_observation(
        intent, universe,
        udiff_source=corrupted,
        index_source=_source("index", b"invalid CSV"),
        recorded_at_utc=RECORD_UTC,
    )
    assert all(row["status"] == "PARSER_OR_IDENTITY_ERROR" for row in packet["stock_observations"])
    assert packet["benchmark_observation"]["status"] == "PARSER_OR_BENCHMARK_ERROR"
    assert packet["source_observation_status"] == "PARTIAL_OR_BLOCKED_SOURCE_OBSERVATION"


def test_rejects_future_or_before_close_capture_and_spoofed_sources() -> None:
    intent, universe = load_and_verify_sources()
    udiff = _source("udiff", _udiff(universe))
    index = _source("index", _index())
    with pytest.raises(ValueError, match="before exchange session closes"):
        build_entry_observation(
            intent, universe, udiff_source=udiff, index_source=index,
            recorded_at_utc="2026-10-12T09:00:00Z",
        )
    udiff["captured_at_utc"] = "2026-10-12T09:00:00Z"
    with pytest.raises(ValueError, match="before completed session close"):
        build_entry_observation(
            intent, universe, udiff_source=udiff, index_source=index,
            recorded_at_utc=RECORD_UTC,
        )
    udiff = _source("udiff", _udiff(universe))
    udiff["url"] = "https://example.com/fake-file.zip"
    with pytest.raises(ValueError, match="wrong official NSE source URL"):
        build_entry_observation(
            intent, universe, udiff_source=udiff, index_source=index,
            recorded_at_utc=RECORD_UTC,
        )


def test_rejects_intent_override_and_tampered_packet_digest() -> None:
    intent, universe = load_and_verify_sources()
    intent["selected_observations"][0]["symbol"] = "TRENT"
    with pytest.raises(ValueError, match="selection"):
        build_entry_observation(
            intent, universe, udiff_source=_source("udiff", _udiff(universe)),
            index_source=_source("index", _index()),
            recorded_at_utc=RECORD_UTC,
        )
    intent, universe = load_and_verify_sources()
    packet = build_entry_observation(
        intent, universe, udiff_source=_source("udiff", _udiff(universe)),
        index_source=_source("index", _index()), recorded_at_utc=RECORD_UTC,
    )
    packet["stock_observations"][0]["open_price_inr"] = 999.0
    with pytest.raises(ValueError, match="content hash mismatch"):
        validate_entry_observation(packet)


def test_source_retention_provenance(tmp_path: Path) -> None:
    intent, universe = load_and_verify_sources()
    raw = _udiff(universe)
    attempt = write_acquisition(
        tmp_path, intent=intent, universe=universe,
        udiff=_source("udiff", raw), index=_source("index", _index()),
        recorded_at_utc=RECORD_UTC,
    )
    path = tmp_path / "entry-observation-v1.json"
    packet = json.loads(path.read_text(encoding="utf-8"))
    validate_entry_observation(packet)
    assert attempt["packet_sha256"] == packet["packet_sha256"]
    assert {x["kind"] for x in attempt["raw_sources_retained"]} == {"udiff", "index"}
    for item in attempt["raw_sources_retained"]:
        retained = tmp_path / item["path"]
        assert retained.is_file()
        assert len(retained.read_bytes()) > 0


def test_access_denial_never_triggers_redirect_or_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.acquire_h021_first_entry as module

    calls = []

    class FakeResponse:
        status_code = 403
        content = b"blocked"

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(module.requests, "get", fake_get)
    result = download_official_source(
        udiff_url(date.fromisoformat(ENTRY_DAY)), attempts=3, sleep_seconds=0
    )
    assert result["status"] == "ACCESS_BLOCKED"
    assert result["raw"] is None
    assert len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False
