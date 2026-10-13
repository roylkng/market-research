from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_oct13_28_snapshot import (
    AUDIT_ID,
    RAW_NSE_SHA256,
    RAW_PATH,
    SOURCES,
    _read_sources,
    build_oct13_market_snapshot,
    materialize_oct13_28,
    validate_oct13_market_snapshot,
)


def test_all_28_stocks_exact_official_oct13_observation_no_new_reselection() -> None:
    result = materialize_oct13_28(Path("."))
    assert result["audit_id"] == AUDIT_ID
    assert result["market_session_ist"] == "2026-10-13"
    assert result["total_original_cases"] == 28
    assert len(result["company_source_observations"]) == 28
    assert len({row["symbol"] for row in result["company_source_observations"]}) == 28
    assert result["independent_h021_same_source_EQ_rows_reconciled"] == 10
    assert (
        result["official_valid_EQ_company_count"]
        + result["non_EQ_series_company_count"]
        + result["absent_or_identity_blocked_company_count"]
    ) == 28
    assert result["live_capital_allowed"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["stock_total_returns_or_index_excess_calculated"] is False
    assert result["stock_selection_or_research_priority_changed"] is False
    validate_oct13_market_snapshot(result)


def test_five_investment_thesis_research_cases_remain_just_source_prices() -> None:
    result = materialize_oct13_28(Path("."))
    by_symbol = {x["symbol"]: x for x in result["company_source_observations"]}
    for name in ("ANANTRAJ", "INOXGREEN", "DEVX", "NPST", "SAMBHV"):
        item = by_symbol[name]
        assert item["reported_EQ_close_inr"] is not None
        assert item["reported_EQ_close_inr"] > 0
        assert item["reported_EQ_traded_value_inr_crore"] > 0
        assert item["source_series_state"] == "OFFICIAL_EQ_PRICE_VOLUME_OBSERVED_NOT_FILL"
        assert item["portfolio_position_created"] is False
        assert item["actual_trade_execution_confirmed"] is False
        assert item["equity_expected_return_computed"] is False
        assert item["corporate_action_and_dividend_adjustment_verified"] is False
    assert by_symbol["INOXGREEN"]["frozen_isin"] == "INE510W01014"
    assert by_symbol["INOXGREEN"]["historical_capital_basis_status"] == (
        "STALE_MARCH_FD_DENOMINATOR_AFTER_SEPTEMBER_QIP"
    )
    assert by_symbol["INOXGREEN"]["inoxgreen_latest_vepl_oct09_stage_retained"] is True
    assert by_symbol["DEVX"]["original_twenty_day_EQ_median_value_inr_crore_if_complete"] == pytest.approx(
        0.40847033
    )


def test_legacy_non_eq_issuers_do_not_inherit_fake_eq_observations() -> None:
    result = materialize_oct13_28(Path("."))
    by_symbol = {x["symbol"]: x for x in result["company_source_observations"]}
    for name in ("ORBTEXP", "RETAIL"):
        row = by_symbol[name]
        assert row["frozen_isin"] in ("INE231G01010", "INE03DD01011")
        assert row["historical_original_source_EQ_sessions"] < 20
        assert row["original_twenty_day_EQ_median_value_inr_crore_if_complete"] is None
        assert row["one_day_EQ_value_to_past_median_multiple_not_alpha"] is None
        if row["source_series_state"] == "NON_EQ_SERIES_OBSERVED_NOT_EQ_SOURCE":
            assert row["reported_EQ_close_inr"] is None
            assert row["reported_EQ_traded_value_inr_crore"] is None
            assert "BE" in row["source_other_series_if_not_equity"]
        elif row["source_series_state"] == "OFFICIAL_EQ_PRICE_VOLUME_OBSERVED_NOT_FILL":
            assert row["reported_EQ_close_inr"] > 0
        else:
            assert row["source_series_state"] in {
                "SOURCE_IDENTITY_CONFLICT_DO_NOT_FILL",
                "OFFICIAL_EQ_ROW_MISSING_NO_SUBSTITUTION",
                "NO_OFFICIAL_NSE_STOCK_ROW",
                "INVALID_NSE_EQ_PRICE_OR_TURNOVER",
            }
    assert result["one_day_turnover_multiple_is_return_alpha_or_order_capacity"] is False


def test_current_source_is_exactly_the_reconciled_h021_whole_market_zip() -> None:
    sources, raw, receipts = _read_sources(Path("."))
    assert hashlib.sha256(raw).hexdigest() == RAW_NSE_SHA256
    assert receipts["nse_original_udiff_zip"]["bytes"] == len(raw)
    assert receipts["current_day_p008"]["git_blob_sha"] == SOURCES["current_day_p008"][1]
    assert sources["current_day_p008"]["capture_state"] == "SOURCE_COMPLETE"
    assert sources["current_day_p008"]["stock_source"]["sha256"] == RAW_NSE_SHA256
    assert sources["latest_stage_p046"]["original_28_company_selection_changed"] is False


def test_frozen_stage_or_source_substitution_rejected_without_fills() -> None:
    sources, raw, receipts = _read_sources(Path("."))
    original = deepcopy(sources)
    build_oct13_market_snapshot(sources, original_nse_zip=raw, receipts=receipts)
    assert sources == original

    altered = deepcopy(sources)
    altered["latest_stage_p046"]["casework_with_current_vepl_milestone"][0]["symbol"] = (
        "UNLISTED"
    )
    with pytest.raises(ValueError, match="selected company identity mismatch"):
        build_oct13_market_snapshot(altered, original_nse_zip=raw, receipts=receipts)

    with pytest.raises(ValueError, match="UDiFF raw bytes"):
        build_oct13_market_snapshot(
            sources, original_nse_zip=raw + b"fabricated", receipts=receipts
        )


def test_any_packet_sha_edit_rejected_and_cannot_promote_cash() -> None:
    result = materialize_oct13_28(Path("."))
    result["company_source_observations"][0]["reported_EQ_close_inr"] = 99999.0
    with pytest.raises(ValueError, match="packet SHA changed"):
        validate_oct13_market_snapshot(result)

    result = materialize_oct13_28(Path("."))
    result["live_capital_allowed"] = True
    with pytest.raises(ValueError, match="packet SHA changed"):
        validate_oct13_market_snapshot(result)


def test_original_zip_or_source_packet_byte_mutation_cannot_pass(tmp_path: Path) -> None:
    for path, _sha in SOURCES.values():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(path).read_bytes())
    zipped = tmp_path / RAW_PATH
    zipped.parent.mkdir(parents=True, exist_ok=True)
    zipped.write_bytes(RAW_PATH.read_bytes())
    sources, raw, receipts = _read_sources(tmp_path)
    assert build_oct13_market_snapshot(
        sources, original_nse_zip=raw, receipts=receipts
    )["total_original_cases"] == 28
    zipped.write_bytes(zipped.read_bytes() + b"fake")
    with pytest.raises(ValueError, match="original ZIP SHA"):
        _read_sources(tmp_path)

    zipped.write_bytes(RAW_PATH.read_bytes())
    p = tmp_path / SOURCES["latest_stage_p046"][0]
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="original Git blob changed"):
        _read_sources(tmp_path)


def test_source_snap_cli_deterministic_and_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "market-snapshot.json"
    args = [sys.executable, "scripts/build_hg007_oct13_28_snapshot.py", "--out", str(path)]
    first = subprocess.run(args, check=True, capture_output=True, text=True)
    meta = json.loads(first.stdout)
    assert meta["frozen_symbol_count"] == 28
    assert meta["return_alpha_or_position_authorized"] is False
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report == materialize_oct13_28(Path("."))
    subprocess.run(
        [*args, "--verify-existing"], check=True, capture_output=True, text=True
    )
    path.write_text(path.read_text(encoding="utf-8") + "modified", encoding="utf-8")
    invalid = subprocess.run(
        [*args, "--verify-existing"], check=False, capture_output=True, text=True
    )
    assert invalid.returncode != 0
    assert "was modified" in invalid.stderr
