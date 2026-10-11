from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_liquidity_friction import (
    EXPECTED_NAMES,
    ORIGINAL_ZIP,
    PRICE_BLOB,
    PRICE_FILE,
    SOURCE_SHA,
    build_one_session_liquidity,
    load_official_oct9,
    validate_one_session_liquidity,
)


def _study() -> dict:
    p, z, receipts = load_official_oct9(Path("."))
    return build_one_session_liquidity(p, z, receipts)


def test_exact_original_five_equity_identity_and_turnover_recovery() -> None:
    report = _study()
    validate_one_session_liquidity(report)
    assert report["original_five_company_count"] == 5
    assert tuple(row["symbol"] for row in report["cases"]) == EXPECTED_NAMES
    assert report["source_provenance"]["market_context_git_blob_sha"] == PRICE_BLOB
    assert report["source_provenance"]["original_udiff_zip_sha256"] == SOURCE_SHA
    values = {row["symbol"]: row for row in report["cases"]}
    assert values["DEVX"]["single_session_traded_value_inr_crore"] == pytest.approx(
        0.612414613
    )
    assert values["INOXGREEN"]["single_session_traded_value_inr_crore"] == pytest.approx(
        943.188886141
    )
    assert values["ANANTRAJ"]["single_session_traded_value_inr_crore"] == pytest.approx(
        83.43717623
    )
    assert values["NPST"]["single_session_traded_value_inr_crore"] == pytest.approx(
        14.30554548
    )
    assert values["SAMBHV"]["single_session_traded_value_inr_crore"] == pytest.approx(
        41.546847722
    )
    assert all(row["verified_bid_ask_spread"] is False for row in values.values())


def test_devx_small_day_participation_quotient_never_claims_fill() -> None:
    devx = next(row for row in _study()["cases"] if row["symbol"] == "DEVX")
    by_pair = {
        (s["single_day_participation_percent"], s["illustrative_ticket_inr"]): s
        for s in devx["illustrative_participation_scenarios"]
    }
    one_lakh_at_one_percent = by_pair[(1, 100_000)]
    ten_lakh_at_one_percent = by_pair[(1, 1_000_000)]
    one_crore_at_five_percent = by_pair[(5, 10_000_000)]
    assert ten_lakh_at_one_percent["same_day_turnover_fraction_inr"] == pytest.approx(
        61_241.4613
    )
    assert ten_lakh_at_one_percent["ticket_divided_by_same_day_fraction"] == pytest.approx(
        1_000_000 / 61_241.4613
    )
    assert one_lakh_at_one_percent["predicted_elapsed_trading_days"] is None
    assert one_crore_at_five_percent["executable_order_capacity_verified"] is False
    assert one_crore_at_five_percent["predicted_elapsed_trading_days"] is None
    assert devx["multi_session_liquidity_distribution_measured"] is False


def test_all_scenarios_are_explicitly_not_execution_forecasts() -> None:
    report = _study()
    assert report["original_selection_changed"] is False
    assert report["spread_slippage_and_impact_modeled"] is False
    assert report["daily_volumes_assumed_stable"] is False
    assert report["expected_returns_calculated"] is False
    assert report["investment_recommendations_created"] is False
    assert report["portfolio_eligibility_allowed"] is False
    assert report["live_capital_allowed"] is False
    for row in report["cases"]:
        assert row["actual_ticket_execution_claimed"] is False
        assert row["verified_orderbook_depth"] is False
        assert len(row["illustrative_participation_scenarios"]) == 6
        for item in row["illustrative_participation_scenarios"]:
            assert item["executable_order_capacity_verified"] is False
            assert item["predicted_elapsed_trading_days"] is None
            assert item["ticket_divided_by_same_day_fraction"] > 0


def test_tampered_raw_original_and_price_context_are_refused(tmp_path: Path) -> None:
    for name in (PRICE_FILE, ORIGINAL_ZIP):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(name).read_bytes())
    load_official_oct9(tmp_path)
    original = tmp_path / ORIGINAL_ZIP
    original.write_bytes(original.read_bytes() + b"change")
    with pytest.raises(ValueError, match="original whole-market"):
        load_official_oct9(tmp_path)
    original.write_bytes(ORIGINAL_ZIP.read_bytes())
    old_price = tmp_path / PRICE_FILE
    old_price.write_bytes(old_price.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="frozen five-case market"):
        load_official_oct9(tmp_path)


def test_forged_original_eq_market_values_rejected() -> None:
    p, z, provenance = load_official_oct9(Path("."))
    copy = deepcopy(p)
    devx = next(row for row in copy["price_context_rows"] if row["symbol"] == "DEVX")
    devx["official_oct9_total_traded_value_inr"] += 1_000_000
    with pytest.raises(ValueError, match="original NSE"):
        build_one_session_liquidity(copy, z, provenance)


def test_packet_digest_and_capital_guard_are_fail_closed() -> None:
    report = _study()
    bad = deepcopy(report)
    bad["cases"][1]["single_session_traded_value_inr_crore"] = 999
    with pytest.raises(ValueError, match="modified"):
        validate_one_session_liquidity(bad)
    bad = deepcopy(report)
    bad["expected_returns_calculated"] = True
    with pytest.raises(ValueError, match="modified"):
        validate_one_session_liquidity(bad)


def test_cli_regenerates_exact_original_evidence(tmp_path: Path) -> None:
    out = tmp_path / "liquidity.json"
    command = [
        sys.executable,
        "scripts/build_hg007_liquidity_friction.py",
        "--out", str(out),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    info = json.loads(result.stdout)
    assert info["case_count"] == 5
    assert info["traded_value_crore"]["DEVX"] == pytest.approx(0.61241)
    assert json.loads(out.read_text(encoding="utf-8")) == _study()
    subprocess.run(
        command + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    out.write_text(out.read_text(encoding="utf-8") + "fake")
    failed = subprocess.run(
        command + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "packet was modified" in failed.stderr
