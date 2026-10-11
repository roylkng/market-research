from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_liquidity_readiness import (
    OVERLAY_ID,
    build_five_case_liquidity_overlay,
    load_verified_issuer_sources,
)


def _build() -> dict:
    original, p035, p036, src = load_verified_issuer_sources(Path("."))
    return build_five_case_liquidity_overlay(original, p035, p036, src)


def test_complete_five_source_cohort_and_nonexecutable_position_sizes() -> None:
    pkt = _build()
    assert pkt["overlay_id"] == OVERLAY_ID
    assert pkt["company_case_count"] == 5
    assert pkt["full_20_session_cash_market_source_verified"] is True
    assert pkt["original_five_case_names_and_order_unchanged"] is True
    assert [r["symbol"] for r in pkt["company_casework"]] == [
        "ANANTRAJ","DEVX","INOXGREEN","NPST","SAMBHV",
    ]
    assert pkt["orderbook_and_executable_liquidity_complete"] is False
    assert pkt["company_completion_probabilities_published"] == 0
    assert pkt["stock_recommendations_created"] is False
    assert pkt["live_capital_allowed"] is False
    by = {x["symbol"]:x["official_nse_historical_turnover_overlay"] for x in pkt["company_casework"]}
    assert by["DEVX"]["median_daily_traded_value_inr_crore"] == pytest.approx(.40847033)
    assert by["DEVX"]["p10_nearest_rank_daily_traded_value_inr_crore"] == pytest.approx(.083152182)
    assert by["INOXGREEN"]["median_daily_traded_value_inr_crore"] == pytest.approx(26.6312475355)
    assert by["INOXGREEN"]["oct9_to_trailing_20_median_source_turnover_ratio"] == pytest.approx(35.41662420747)
    assert by["NPST"]["highest_to_median_source_turnover_ratio"] > 40
    assert by["SAMBHV"]["highest_to_median_source_turnover_ratio"] > 19
    assert [sym for sym,row in by.items() if row["ticket_exceeds_one_pct_of_median_daily_turnover"]] == ["DEVX"]
    assert by["DEVX"]["ticket_divided_by_one_pct_of_median_source_turnover"] == pytest.approx(24.48158229754)
    assert all(
        x["quotient_is_a_trading_days_or_fill_prediction"] is False
        and x["reliable_executable_position_size_verified"] is False
        and x["multi_session_volume_assumed_representative_of_future"] is False
        for x in by.values()
    )


def test_original_payoff_cases_are_unchanged_and_no_stock_recommendation() -> None:
    old, p035, p036, src = load_verified_issuer_sources(Path("."))
    before = deepcopy((old, p035, p036))
    overlay = build_five_case_liquidity_overlay(old, p035, p036, src)
    assert before == (old, p035, p036)
    assert overlay["original_economic_underwriting_or_rank_modified"] is False
    for prior, current in zip(old["casework"], overlay["company_casework"], strict=True):
        assert current["original_hg005_hurdle_unmodified"] == prior[
            "original_hg005_hurdle_unmodified"
        ]
        assert current["necessary_original_document_and_underwriting_gates"] == prior[
            "necessary_original_document_and_underwriting_gates"
        ]
        assert current["probability_weighted_equity_expected_return"] is None
        assert current["live_capital_allowed"] is False


def test_tampered_twenty_day_turnover_and_preregistration_refused() -> None:
    old, p035, p036, src = load_verified_issuer_sources(Path("."))
    fake = deepcopy(p036)
    fake["company_distribution"][1]["twenty_session_traded_value_median_inr_crore"] = 5000
    with pytest.raises(ValueError, match="altered"):
        build_five_case_liquidity_overlay(old, p035, fake, src)
    fake = deepcopy(old)
    fake["casework"][1]["symbol"] = "UNREGISTERED"
    with pytest.raises(ValueError, match="company"):
        build_five_case_liquidity_overlay(fake, p035, p036, src)


def test_original_git_blob_and_20_day_market_bytes_remain_pinned(tmp_path: Path) -> None:
    from pathlib import Path as P

    from marketlab.hg007_liquidity_history import CALENDAR_PATH, ORIGINAL_ZIP, PRICE_FILE, ROOT
    from marketlab.hg007_liquidity_readiness import SOURCES

    for name,_sha in SOURCES.values():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(P(name).read_bytes())
    for item in (CALENDAR_PATH, ORIGINAL_ZIP, PRICE_FILE):
        p = tmp_path / item
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(item.read_bytes())
    orig = P(ROOT)
    dest = tmp_path / ROOT
    for data in orig.glob("raw/sha256/*.zip"):
        out = dest / "raw" / "sha256" / data.name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data.read_bytes())
    for receipt in orig.glob("receipts/*.json"):
        out = dest / "receipts" / receipt.name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(receipt.read_bytes())
    # Calendar original must be pinned, and P036 must independently replay
    # all original ZIPs through the 20-day parser.
    load_verified_issuer_sources(tmp_path)
    old_src=tmp_path / SOURCES["twenty_session_liquidity"][0]
    old_src.write_bytes(old_src.read_bytes()+b"x")
    with pytest.raises(ValueError, match="Git blob changed"):
        load_verified_issuer_sources(tmp_path)


def test_cli_reproduces_unchanged_original_and_rejects_edits(tmp_path: Path) -> None:
    path = tmp_path / "liquidity-overlay.json"
    cmd = [
        sys.executable, "scripts/build_hg007_liquidity_readiness.py",
        "--out", str(path),
    ]
    p = subprocess.run(cmd, check=True, capture_output=True, text=True)
    assert json.loads(p.stdout)["ticket_exceeds_one_pct_source_median"] == ["DEVX"]
    assert json.loads(path.read_text()) == _build()
    subprocess.run(cmd+["--verify-existing"], check=True, capture_output=True, text=True)
    path.write_text(path.read_text()+"altered")
    bad = subprocess.run(cmd+["--verify-existing"], check=False, capture_output=True, text=True)
    assert bad.returncode != 0
    assert "overlay has changed" in bad.stderr
