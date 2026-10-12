from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_eq_be_turnover import (
    MIXED_COMPANIES,
    P041_BLOB,
    P041_PATH,
    P042_BLOB,
    P042_PATH,
    _hash,
    build_mixed_series_context,
    load_frozen_sources,
    validate_mixed_series_context,
)


def _packet() -> dict:
    a, b, receipts = load_frozen_sources(Path("."))
    return build_mixed_series_context(a, b, provenance=receipts)


def test_all_twenty_exchange_days_and_twenty_eight_original_names() -> None:
    result = _packet()
    validate_mixed_series_context(result)
    assert result["original_company_selection_count"] == 28
    assert len(result["company_context"]) == 28
    assert result["original_eq_only_complete_company_count"] == 26
    assert result["original_mixed_eq_be_company_count"] == 2
    assert result["source_original_market_sessions"] == 20
    assert result["source_receipts"]["original_all_28"]["git_blob_sha"] == P041_BLOB
    assert result["source_receipts"]["original_eq_absence_review"]["git_blob_sha"] == P042_BLOB
    assert result["source_alpha_or_equity_returns_calculated"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False


def test_two_mixed_original_series_medians_and_identity_preserved() -> None:
    report = _packet()
    cases = {row["symbol"]: row for row in report["company_context"]}
    assert set(MIXED_COMPANIES).issubset(cases)
    orb = cases["ORBTEXP"]
    ret = cases["RETAIL"]
    assert (orb["source_eq_count"], orb["source_be_count"]) == (9, 11)
    assert (ret["source_eq_count"], ret["source_be_count"]) == (15, 5)
    assert orb["mixed_series_turnover_statistics"][
        "median_mixed_eq_be_daily_value_inr_crore"
    ] == pytest.approx(0.1227688325)
    assert ret["mixed_series_turnover_statistics"][
        "median_mixed_eq_be_daily_value_inr_crore"
    ] == pytest.approx(0.0113960010)
    for case in (orb, ret):
        assert case["original_eq_only_20day_statistics_still_blocked"] is True
        assert case["broker_be_eligibility_verified"] is False
        assert case["bid_ask_spread_market_depth_verified"] is False
        assert case["mixed_settlement_fill_simulation_authorized"] is False
        assert len(case["source_day_values"]) == 20
        assert all(row["paper_equity_execution_price_substituted"] is False
                   for row in case["source_day_values"])
        assert len({row["isin"] for row in case["source_day_values"]}) == 1
        assert case["mixed_series_turnover_statistics"][
            "mixed_series_median_is_executable_capacity"
        ] is False
    for symbol in report["original_company_order"]:
        if symbol not in MIXED_COMPANIES:
            case = cases[symbol]
            assert case["settlement_regime"] == "ONLY_EQ_ORIGINAL_20_DAY_SOURCE"
            assert case["company_original_eq_20day_statistics_unmodified"] is not None
            assert case["mixed_series_turnover_statistics"] is None


def test_changed_be_isin_and_mislabeled_alt_series_fail_closed() -> None:
    a, b, receipts = load_frozen_sources(Path("."))
    altered = deepcopy(b)
    target = next(row for row in altered["findings"] if row["symbol"] == "RETAIL")
    target["missing_eq_day_evidence"][0]["same_symbol_non_eq_rows"][0]["isin"] = (
        "INEFAKEFAKE00"
    )
    # Check even under a re-sealed compromised intermediate packet.
    from marketlab.hg007_eq_absence_review import _digest

    altered["packet_sha256"] = _digest({
        key: value for key, value in altered.items() if key != "packet_sha256"
    })
    with pytest.raises(ValueError, match="not a valid original BE"):
        build_mixed_series_context(a, altered, provenance=receipts)

    altered = deepcopy(b)
    target = next(row for row in altered["findings"] if row["symbol"] == "ORBTEXP")
    target["missing_eq_day_evidence"][0]["same_symbol_non_eq_rows"][0][
        "exchange_series"
    ] = "EQ"
    altered["packet_sha256"] = _digest({
        key: value for key, value in altered.items() if key != "packet_sha256"
    })
    with pytest.raises(ValueError, match="not a valid original BE"):
        build_mixed_series_context(a, altered, provenance=receipts)


def test_wrong_pinned_source_blob_fails_closed(tmp_path: Path) -> None:
    for path in (P041_PATH, P042_PATH):
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    load_frozen_sources(tmp_path)
    damaged = tmp_path / P042_PATH
    damaged.write_bytes(damaged.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Git blob no longer matches"):
        load_frozen_sources(tmp_path)


def test_rehashed_capital_and_source_promotion_rejected() -> None:
    for flag in (
        "source_alpha_or_equity_returns_calculated",
        "broker_netting_execution_slippage_verified",
        "future_trade_size_or_trade_probability_published",
        "investment_recommendations_created",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        changed = _packet()
        changed[flag] = True
        changed["packet_sha256"] = _hash({
            key: value for key, value in changed.items() if key != "packet_sha256"
        })
        with pytest.raises(ValueError, match="cannot enable"):
            validate_mixed_series_context(changed)


def test_offline_reproduction_and_changed_artifact_rejected(tmp_path: Path) -> None:
    out = tmp_path / "mix.json"
    args = [
        sys.executable, "scripts/build_hg007_eq_be_turnover.py",
        "--out", str(out),
    ]
    run = subprocess.run(args, check=True, capture_output=True, text=True)
    summary = json.loads(run.stdout)
    assert summary["original_companies"] == 28
    assert summary["mixed_eq_be_original_company_count"] == 2
    assert summary["broker_execution_proven"] is False
    assert json.loads(out.read_text(encoding="utf-8")) == _packet()
    subprocess.run(args + ["--verify-existing"], check=True, capture_output=True, text=True)
    out.write_text(out.read_text(encoding="utf-8") + "fake")
    failed = subprocess.run(
        args + ["--verify-existing"], check=False, capture_output=True, text=True,
    )
    assert failed.returncode != 0
    assert "mixed NSE settlement historical source changed" in failed.stderr
