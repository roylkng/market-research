from __future__ import annotations

import json
import math
import subprocess
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from marketlab.h021_signed_challenger import (
    FIRST_PROSPECTIVE_CAPTURE,
    MIN_PRIOR_ABS_EPS_INR,
    build_signed_challenger_intent,
    validate_challenger_intent,
)

CALENDAR_PATH = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json"
)
SOURCE_SHA = {
    key: "a" * 64 for key in (
        "comparison", "prior_gzip", "prior_manifest",
        "current_gzip", "current_manifest",
    )
}


def _sample(*, current_date: str = "2026-10-16", prior_date: str = "2026-09-18"):
    prior, current, members, revision = [], [], [], []
    for i in range(100):
        symbol = f"S{i:03d}"
        original_eps = 10.0
        current_eps = 10.0 + i / 100.0
        if i == 0:
            original_eps, current_eps = -2.0, -3.0  # Worsening loss: bad positive ratio
        if i == 1:
            original_eps, current_eps = -2.0, -1.0  # Improving loss: bad negative ratio
        if i == 2:
            original_eps, current_eps = 0.1, 0.15  # Original ratio +50, challenger +5
        analysts = 2 if i == 3 else 6
        members.append({"symbol": symbol, "isin": f"INE{i:09d}", "rank": i+1})
        base = {
            "symbol": symbol,
            "consensus_eps": original_eps,
            "fiscal_period": "FY2027",
            "period_ending": "2027-03-31",
            "eps_currency": "INR",
            "analyst_count": analysts,
        }
        prior.append(base)
        current.append({**base, "consensus_eps": current_eps})
        ratio = 100 * (current_eps / original_eps - 1)
        revision.append({
            "symbol": symbol,
            "prior_capture_date": prior_date,
            "current_capture_date": current_date,
            "analyst_count_prior": analysts,
            "analyst_count_current": analysts,
            "primary_signal_available": analysts >= 5,
            "primary_signal_reason": (
                "ELIGIBLE" if analysts >= 5 else "ANALYST_COVERAGE_LT_5"
            ),
            "eps_revision_pct": ratio,
            "period_compatible": True,
            "eps_currency_compatible": True,
            "source_compatible": True,
        })
    eligible = [r for r in revision if r["primary_signal_available"]]
    rank = sorted(eligible, key=lambda row: (-row["eps_revision_pct"], row["symbol"]))
    cutoff = rank[math.ceil(len(rank) * 0.10) - 1]["eps_revision_pct"]
    top = [row["symbol"] for row in rank if row["eps_revision_pct"] >= cutoff]
    comparison = {
        "hypothesis_id": "H021",
        "schema_version": 1,
        "prior_capture_date_ist": prior_date,
        "current_capture_date_ist": current_date,
        "capture_interval_days": (date.fromisoformat(current_date) -
                                  date.fromisoformat(prior_date)).days,
        "primary_signal": "28-35 day same-period consensus EPS revision",
        "primary_coverage_rule": "analyst_count >= 5 at both captures",
        "primary_signal_available_count": len(eligible),
        "primary_top_decile_count": len(top),
        "primary_top_decile_symbols": top,
        "source_version": "H021-public-stockanalysis-spgi-plus-trendlyne-secondary-v1",
        "universe_git_blob_sha": "8026e81faee3e913d2fba1dba72d60603b69fa07",
        "outcomes_opened": False,
        "live_capital_allowed": False,
        "revision_observations": revision,
    }
    current_capture = {
        "capture_date_ist": current_date,
        "captured_at_utc": f"{current_date}T10:30:00Z",
        "outcomes_opened": False, "live_capital_allowed": False,
        "source_version": comparison["source_version"],
        "observations": current,
    }
    prior_capture = {
        "capture_date_ist": prior_date,
        "captured_at_utc": f"{prior_date}T11:00:00Z",
        "outcomes_opened": False, "live_capital_allowed": False,
        "source_version": comparison["source_version"],
        "observations": prior,
    }
    manifest = {
        "schema_version": 2,
        "capture_date_ist": current_date,
        "logical_capture_id": f"{current_date}-full-u001-v1",
        "captured_at_utc": f"{current_date}T10:30:00Z",
        "source_version": comparison["source_version"],
        "universe_git_blob_sha": comparison["universe_git_blob_sha"],
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }
    universe = {"cohort_id": "FY27-Q2-2026-09-06", "members": members}
    calendar = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    return comparison, prior_capture, current_capture, manifest, universe, calendar


def _build(
    fixture=None, *,
    prepared: str = "2026-10-16T12:00:00Z",
):
    c, a, b, manifest, universe, calendar = fixture or _sample()
    return build_signed_challenger_intent(
        comparison=c, prior=a, current=b, manifest=manifest,
        universe=universe, calendar=calendar,
        prepared_at_utc=prepared, original_source_hashes=SOURCE_SHA,
    )


def test_new_challenger_first_cohort_oct16_does_not_rewrite_h021_v1() -> None:
    assert FIRST_PROSPECTIVE_CAPTURE == date(2026, 10, 16)
    assert MIN_PRIOR_ABS_EPS_INR == 1
    sources = _sample()
    originals = deepcopy(sources)
    record = _build(sources)
    validate_challenger_intent(record)
    assert sources == originals
    assert record["planned_entry_session_ist"] == "2026-10-19"
    assert record["planned_entry_open_utc"] == "2026-10-19T03:45:00Z"
    assert record["eligible_h021_comparator_count"] == 99
    assert record["challenger_selected_count"] == 10
    assert record["incumbent_h021_frozen_symbols_unchanged"] == sources[0][
        "primary_top_decile_symbols"
    ]
    original = set(record["incumbent_h021_frozen_symbols_unchanged"])
    challenger = {row["symbol"] for row in record["challenger_selected"]}
    assert "S000" in original and "S000" not in challenger
    assert "S001" not in original and "S001" in challenger
    assert "S002" in original and "S002" not in challenger
    assert record["paired_h021_and_challenger_overlap_count"] == len(original & challenger)
    assert all(row["entry_price_inr"] is None for row in record["challenger_selected"])
    assert all(row["capital_weight"] is None for row in record["challenger_selected"])
    assert record["future_return_prices_observed"] is False
    assert record["portfolio_eligibility_allowed"] is False
    assert record["live_capital_allowed"] is False


def test_negative_prior_eps_direction_and_near_zero_floor() -> None:
    a, prior, cur, manifest, univ, calendar = _sample()
    record = _build((a, prior, cur, manifest, univ, calendar))
    score = {row["symbol"]: row["signed_eps_floor_revision_pct"]
             for row in record["challenger_selected"]}
    assert score["S001"] == pytest.approx(50.0)
    assert record["covered_negative_prior_eps_count"] == 2
    assert record["covered_eps_floor_applied_count"] == 1
    assert "S002" not in score  # its 50% nominal ratio is floor-reduced to +5%


def test_cannot_backdate_first_oct09_cohort_or_prepare_after_open() -> None:
    sources = _sample(current_date="2026-10-09", prior_date="2026-09-11")
    with pytest.raises(ValueError, match="cannot backdate"):
        _build(sources, prepared="2026-10-09T12:00:00Z")
    with pytest.raises(ValueError, match="before next open"):
        _build(prepared="2026-10-19T03:45:00Z")
    with pytest.raises(ValueError, match="before next open"):
        _build(prepared="2026-10-19T10:00:00Z")


def test_refuse_unresolved_november_8_special_next_open() -> None:
    sources = _sample(current_date="2026-11-06", prior_date="2026-10-09")
    with pytest.raises(ValueError, match="unresolved Muhurat"):
        _build(sources, prepared="2026-11-06T12:00:00Z")


def test_bad_analyst_coverage_and_ineligible_cherry_pick_rejected() -> None:
    sources = list(_sample())
    sources[0]["revision_observations"][3]["primary_signal_available"] = True
    with pytest.raises(ValueError, match="contributor coverage"):
        _build(tuple(sources))
    sources = list(_sample())
    sources[0]["primary_top_decile_symbols"].append("S003")
    sources[0]["primary_top_decile_count"] += 1
    with pytest.raises(ValueError, match="coverage-ineligible"):
        _build(tuple(sources))


def test_source_eps_immutability_and_original_champion_rank() -> None:
    sources = list(_sample())
    sources[2]["observations"][0]["consensus_eps"] = -1
    with pytest.raises(ValueError, match="does not match source EPS"):
        _build(tuple(sources))
    sources = list(_sample())
    sources[0]["primary_top_decile_symbols"][0] = "S004"
    with pytest.raises(ValueError, match="selected cohort is inconsistent"):
        _build(tuple(sources))


def test_currency_switch_and_modified_fiscal_period_rejected() -> None:
    sources = list(_sample())
    sources[2]["observations"][1]["eps_currency"] = "USD"
    with pytest.raises(ValueError, match="incompatible periods/currencies"):
        _build(tuple(sources))
    sources = list(_sample())
    sources[1]["observations"][1]["period_ending"] = "2025-03-31"
    with pytest.raises(ValueError, match="incompatible periods/currencies"):
        _build(tuple(sources))


def test_missing_immutable_inputs_and_modified_output_digest_rejected() -> None:
    fixture = _sample()
    kwargs = dict(
        comparison=fixture[0], prior=fixture[1], current=fixture[2],
        manifest=fixture[3], universe=fixture[4], calendar=fixture[5],
        prepared_at_utc="2026-10-16T12:00:00Z",
    )
    with pytest.raises(ValueError, match="original H021 SHA-256"):
        build_signed_challenger_intent(
            **kwargs,
            original_source_hashes={**SOURCE_SHA, "current_gzip": "bad"},
        )
    record = _build()
    record["challenger_selected"][0]["symbol"] = "FICTITIOUS"
    with pytest.raises(ValueError, match="immutable intent was modified"):
        validate_challenger_intent(record)


def test_real_premature_oct09_capture_never_yields_new_trial_intent() -> None:
    from scripts.freeze_h021_signed_challenger import prepare_signed_challenger

    with pytest.raises(ValueError, match="cannot backdate"):
        prepare_signed_challenger(
            Path("."),
            Path(
                "research/prospective/h021/comparisons/"
                "2026-10-09-primary-revision-v1.json"
            ),
            "2026-10-10T12:00:00Z",
        )


def test_cli_forbids_early_or_late_renamed_output(tmp_path: Path) -> None:
    target = tmp_path / "retrospective.json"
    result = subprocess.run(
        [
            sys.executable, "scripts/freeze_h021_signed_challenger.py",
            "--comparison",
            "research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json",
            "--out", str(target),
        ],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "output path/date mismatch" in result.stderr
