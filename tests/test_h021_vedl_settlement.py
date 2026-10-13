from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_vedl_settlement import (
    SOURCE_REFS,
    build_pre_ex_date_settlement_review,
    load_exact_source_records,
    validate_pre_ex_date_settlement_review,
)


def _source() -> tuple[dict, dict]:
    return load_exact_source_records(Path("."))


def test_oct14_nse_dividend_exdate_original_t1_scenario_preentry() -> None:
    originals, receipts = _source()
    baseline = deepcopy(originals)
    result = build_pre_ex_date_settlement_review(
        originals, receipts, repo_root=Path(".")
    )
    validate_pre_ex_date_settlement_review(result)

    assert result["security"] == {
        "symbol": "VEDL", "isin": "INE205A01025", "equity_series": "EQ",
    }
    assert result["original_issuer_dividend_per_share_inr"] == 5
    assert result["planned_research_entry_proxy_date_ist"] == "2026-10-12"
    assert result["ordinary_t1_candidate_settlement_session_ist"] == "2026-10-13"
    assert result["last_cum_dividend_regular_market_session_ist"] == "2026-10-13"
    assert result["official_nse_exchange_ex_date_ist"] == "2026-10-14"
    assert result["official_nse_exchange_record_date_ist"] == "2026-10-14"
    assert result["issuer_original_notice_public_before_oct12_selection_entry"]
    assert result["undisputed_source_measurement_states"][
        "oct12_official_next_open_observed_not_tradable_fill"
    ]
    assert result["undisputed_source_measurement_states"][
        "oct13_official_eq_day_observed_not_trade"
    ]
    assert result["conditional_hypothetical_position_scenario"][
        "paper_scenario_classification"
    ].startswith("POTENTIAL_DIVIDEND_ENTITLEMENT_IF")
    for field in (
        "actual_buy_execution_and_slippage_verified",
        "cash_entitlement_independently_verified",
        "payable_cash_settlement_or_dividend_credit_verified",
        "realized_h021_returns_computed",
        "future_h021_20_or_60_session_outcomes_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert result[field] is False
    assert result["conditional_hypothetical_position_scenario"][
        "actual_record_date_demat_holder_confirmed"
    ] is False
    assert originals == baseline


def test_attempted_source_relabel_as_earlier_or_different_dividend_rejected() -> None:
    originals, receipts = _source()
    mutated = deepcopy(originals)
    mutated["nse_original_vedl_exdate"]["official_matching_row"][
        "exchange_ex_date"
    ] = "2026-10-13"
    with pytest.raises(ValueError, match="ex-date/issuer"):
        build_pre_ex_date_settlement_review(
            mutated, receipts, repo_root=Path(".")
        )

    mutated = deepcopy(originals)
    mutated["original_vedl_issuer_dividend"][
        "issuer_reported_dividend_terms"
    ]["issuer_reported_dividend_per_share_inr"] = 10
    with pytest.raises(ValueError, match="ex-date/issuer"):
        build_pre_ex_date_settlement_review(
            mutated, receipts, repo_root=Path(".")
        )


def test_vedl_entry_and_oct13_source_identity_cannot_be_substituted() -> None:
    originals, receipts = _source()
    mutated = deepcopy(originals)
    next_day = mutated["daily_original_oct13"]
    selected = next(row for row in next_day["stock_rows"] if row["symbol"] == "VEDL")
    selected["series"] = "BE"
    with pytest.raises(ValueError, match="modified after sealing"):
        build_pre_ex_date_settlement_review(
            mutated, receipts, repo_root=Path(".")
        )

    mutated = deepcopy(originals)
    mutated["frozen_intent"]["selected_observations"][0]["symbol"] = "OTHER"
    with pytest.raises(ValueError, match="first intent no longer derived"):
        build_pre_ex_date_settlement_review(
            mutated, receipts, repo_root=Path(".")
        )


def test_source_git_blob_drift_is_a_hard_failure(tmp_path: Path) -> None:
    for filename, _sha in SOURCE_REFS.values():
        target = tmp_path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(filename).read_bytes())
    originals, receipts = load_exact_source_records(tmp_path)
    assert len(receipts) == 6
    assert "frozen_intent" in originals
    source = tmp_path / SOURCE_REFS["nse_original_vedl_exdate"][0]
    source.write_bytes(source.read_bytes() + b" ")
    with pytest.raises(ValueError, match="original nse_original_vedl_exdate Git blob"):
        load_exact_source_records(tmp_path)


def test_mutated_review_cannot_claim_realized_returns_or_settlement() -> None:
    originals, receipts = _source()
    result = build_pre_ex_date_settlement_review(
        originals, receipts, repo_root=Path(".")
    )
    result["cash_entitlement_independently_verified"] = True
    with pytest.raises(ValueError, match="record changed"):
        validate_pre_ex_date_settlement_review(result)


def test_cli_packet_idempotent_and_return_blind(tmp_path: Path) -> None:
    out = tmp_path / "t1-dividend-risk.json"
    command = [
        sys.executable, "scripts/reconcile_h021_vedl_exdate_settlement.py",
        "--out", str(out),
    ]
    result = subprocess.run(
        command, check=True, capture_output=True, text=True
    )
    summary = json.loads(result.stdout)
    packet = json.loads(out.read_text(encoding="utf-8"))
    assert summary["cash_entitlement_verified"] is False
    assert summary["return_outcomes_opened"] is False
    assert summary["official_ex_date"] == "2026-10-14"
    assert packet["live_capital_allowed"] is False
    subprocess.run(
        command + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    out.write_text(
        out.read_text(encoding="utf-8") + "FALSIFIED", encoding="utf-8"
    )
    failure = subprocess.run(
        command + ["--verify-existing"], check=False,
        capture_output=True, text=True,
    )
    assert failure.returncode != 0
    assert "risk packet was changed" in failure.stderr
