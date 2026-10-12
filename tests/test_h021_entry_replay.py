"""Synthetic exchange-file regression tests, NO invented real Oct12 prices."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_entry_observation import (
    EXPECTED_SELECTION,
    _canonical_hash,
    build_entry_observation,
)
from marketlab.h021_entry_replay import (
    replay_first_h021_entry,
    validate_first_h021_replay,
)
from marketlab.marketdata import index_snapshot_url, udiff_url
from scripts.acquire_h021_first_entry import load_and_verify_sources
from scripts.replay_h021_first_official_entry import reproduce_entry

DAY = "2026-10-12"
CAPTURE = "2026-10-12T13:30:00Z"
RECORDED = "2026-10-12T13:45:00Z"


def _raw_stock(universe: dict) -> bytes:
    by_symbol = {x["symbol"]: x["isin"] for x in universe["members"]}
    csvdata = io.StringIO()
    fields = [
        "TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb",
        "SctySrs", "OpnPric", "HghPric", "LwPric", "ClsPric",
    ]
    writer = csv.DictWriter(csvdata, fieldnames=fields)
    writer.writeheader()
    for i, symbol in enumerate(EXPECTED_SELECTION):
        price = 100.5 + i
        writer.writerow({
            "TradDt": DAY,
            "Sgmt": "CM",
            "Src": "NSE",
            "FinInstrmTp": "STK",
            "ISIN": by_symbol[symbol],
            "TckrSymb": symbol,
            "SctySrs": "EQ",
            "OpnPric": price,
            "HghPric": price + 2,
            "LwPric": price - 1,
            "ClsPric": price + 1,
        })
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as output:
        output.writestr(
            "BhavCopy_NSE_CM_0_0_0_20261012_F_0000.csv",
            csvdata.getvalue(),
        )
    return buffer.getvalue()


def _raw_index() -> bytes:
    return (
        b"Index Name,Index Date,Open Index Value,Closing Index Value\n"
        b"Nifty 500,12-10-2026,23200.50,23301.75\n"
        b"Nifty 50,12-10-2026,25100,25200\n"
    )


def _receipt(url: str, raw: bytes) -> dict:
    return {
        "url": url,
        "captured_at_utc": CAPTURE,
        "status": "OK",
        "http_status": 200,
        "raw": raw,
        "error": None,
    }


def _synthetic() -> tuple[dict, dict, dict, bytes, bytes]:
    intent, universe = load_and_verify_sources()
    stock, index = _raw_stock(universe), _raw_index()
    from datetime import date

    day = date(2026, 10, 12)
    packet = build_entry_observation(
        intent,
        universe,
        udiff_source=_receipt(udiff_url(day), stock),
        index_source=_receipt(index_snapshot_url(day), index),
        recorded_at_utc=RECORDED,
    )
    assert packet["source_observation_status"] == "FULL_OFFICIAL_OHLC_SOURCE_OBSERVED"
    return intent, universe, packet, stock, index


def _replay(intent: dict, universe: dict, packet: dict, stock: bytes, index: bytes) -> dict:
    return replay_first_h021_entry(
        original_packet=packet,
        frozen_intent=intent,
        frozen_universe=universe,
        stock_udiff_zip=stock,
        nifty500_index_csv=index,
    )


def _materialize(tmp_path: Path, packet: dict, stock: bytes, index: bytes) -> Path:
    root = tmp_path / "official"
    raw_dir = root / "raw" / "sha256"
    raw_dir.mkdir(parents=True)
    (raw_dir / f"{hashlib.sha256(stock).hexdigest()}.zip").write_bytes(stock)
    (raw_dir / f"{hashlib.sha256(index).hexdigest()}.csv").write_bytes(index)
    (root / "2026-10-12-first-entry-v1.json").write_text(
        json.dumps(packet, sort_keys=True),
        encoding="utf-8",
    )
    return root


def test_replay_exact_ten_exchange_opens_and_index_without_fills() -> None:
    intent, universe, packet, stock, index = _synthetic()
    original_inputs = deepcopy((intent, universe, packet))
    replayed = _replay(intent, universe, packet, stock, index)
    validate_first_h021_replay(replayed)
    assert replayed["selected_stock_source_count"] == 10
    assert [row["symbol"] for row in replayed["selected_stock_bars"]] == list(
        EXPECTED_SELECTION
    )
    assert replayed["selected_stock_bars"][0]["open_price_inr"] == 100.5
    assert replayed["benchmark_price_index_bar"]["open"] == 23200.50
    assert replayed["benchmark_price_index_bar"]["price_index_not_tri"] is True
    assert replayed["source_entry_record_sha256"] == packet["packet_sha256"]
    for blocked in (
        "proves_first_open_was_executable_fill",
        "current_market_depth_and_slippage_verified",
        "vedl_pre_entry_dividend_entitlement_verified",
        "all_ten_dividend_and_corporate_actions_verified",
        "benchmark_and_equity_dividend_total_return_bases_reconciled",
        "twenty_session_holding_outcome_opened",
        "sixty_session_holding_outcome_opened",
        "expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert replayed[blocked] is False
    assert (intent, universe, packet) == original_inputs


def test_rehashed_fabricated_stock_price_still_fails_original_raw_replay() -> None:
    intent, universe, packet, stock, index = _synthetic()
    packet["stock_observations"][0]["open_price_inr"] += 1.0
    packet["packet_sha256"] = _canonical_hash(
        {key: value for key, value in packet.items() if key != "packet_sha256"}
    )
    with pytest.raises(ValueError, match="VEDL:open_price_inr differs"):
        _replay(intent, universe, packet, stock, index)


def test_rehashed_fabricated_index_price_still_fails_original_raw_replay() -> None:
    intent, universe, packet, stock, index = _synthetic()
    packet["benchmark_observation"]["open_index_value"] += 200.0
    packet["packet_sha256"] = _canonical_hash(
        {key: value for key, value in packet.items() if key != "packet_sha256"}
    )
    with pytest.raises(ValueError, match="NIFTY500:open differs"):
        _replay(intent, universe, packet, stock, index)


def test_wrong_raw_or_mismatched_source_isin_cannot_be_relabelled() -> None:
    intent, universe, packet, stock, index = _synthetic()
    with pytest.raises(ValueError, match="raw bytes/URL/receipt identity mismatch"):
        _replay(intent, universe, packet, stock + b"x", index)
    with pytest.raises(ValueError, match="raw bytes/URL/receipt identity mismatch"):
        _replay(intent, universe, packet, stock, index + b"x")

    forged = deepcopy(packet)
    forged["stock_observations"][0]["isin"] = "INEBADBADBAD"
    forged["packet_sha256"] = _canonical_hash(
        {key: value for key, value in forged.items() if key != "packet_sha256"}
    )
    with pytest.raises(ValueError, match="original EQ/ISIN"):
        _replay(intent, universe, forged, stock, index)


def test_partial_or_missing_market_source_never_yields_full_replay() -> None:
    intent, universe, packet, stock, index = _synthetic()
    packet["observed_official_stock_open_count"] = 9
    packet["packet_sha256"] = _canonical_hash(
        {key: value for key, value in packet.items() if key != "packet_sha256"}
    )
    with pytest.raises(ValueError, match="incomplete or replaced"):
        _replay(intent, universe, packet, stock, index)


def test_source_files_independent_bytes_and_cli_are_reproducible(tmp_path: Path) -> None:
    intent, universe, packet, stock, index = _synthetic()
    root = _materialize(tmp_path, packet, stock, index)
    source_replayed = reproduce_entry(root)
    assert source_replayed == _replay(intent, universe, packet, stock, index)
    outfile = tmp_path / "independent.json"
    cmd = [
        sys.executable,
        "scripts/replay_h021_first_official_entry.py",
        "--original-dir", str(root),
        "--out", str(outfile),
    ]
    r = subprocess.run(cmd, check=True, text=True, capture_output=True)
    assert json.loads(r.stdout)["verified_actual_trade_fill"] is False
    assert json.loads(outfile.read_text(encoding="utf-8")) == source_replayed
    subprocess.run(cmd + ["--verify-existing"], check=True, text=True, capture_output=True)

    source_path = root / "raw" / "sha256" / f"{hashlib.sha256(stock).hexdigest()}.zip"
    source_path.write_bytes(source_path.read_bytes() + b"altered")
    with pytest.raises(ValueError, match="source bytes changed"):
        reproduce_entry(root)


def test_replay_packet_tamper_detection_cannot_enable_return_label() -> None:
    intent, universe, packet, stock, index = _synthetic()
    report = _replay(intent, universe, packet, stock, index)
    report["twenty_session_holding_outcome_opened"] = True
    with pytest.raises(ValueError, match="packet SHA is invalid"):
        validate_first_h021_replay(report)
