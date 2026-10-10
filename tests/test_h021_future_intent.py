from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_future_intent import build_future_h021_intent

COMPARISON = Path(
    "research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json"
)
MANIFEST = Path(
    "research/prospective/h021/captures/2026-10-09-full-u001-v1.manifest.json"
)
CALENDAR = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json"
)
UNIVERSE = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")


def _base() -> tuple[dict, dict, dict, dict]:
    return tuple(
        json.loads(path.read_text(encoding="utf-8"))
        for path in (COMPARISON, MANIFEST, CALENDAR, UNIVERSE)
    )


def _build(
    comparison: dict,
    manifest: dict,
    calendar: dict,
    universe: dict,
    when: str = "2026-10-10T00:00:00Z",
) -> dict:
    return build_future_h021_intent(
        comparison, manifest, calendar, universe,
        prepared_at_utc=when,
        comparison_raw_sha256="a" * 64,
        manifest_raw_sha256="b" * 64,
    )


def test_first_valid_sealed_h021_reproduces_original_ten_without_returns() -> None:
    comp, manifest, calendar, universe = _base()
    original_comp = deepcopy(comp)
    result = _build(comp, manifest, calendar, universe)
    original_intent = json.loads(Path(
        "research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json"
    ).read_text(encoding="utf-8"))

    assert [x["symbol"] for x in result["selected_observations"]] == [
        x["symbol"] for x in original_intent["selected_observations"]
    ]
    assert result["planned_entry"]["session_date_ist"] == "2026-10-12"
    assert result["planned_entry"]["open_timestamp_utc"] == "2026-10-12T03:45:00Z"
    assert result["eligible_count"] == 97
    assert result["selected_count"] == 10
    assert result["packet_sha256"] and len(result["packet_sha256"]) == 64
    assert all(x["entry_price"] is None and x["capital_weight"] is None
               for x in result["selected_observations"])
    for field in (
        "return_outcomes_opened", "trades_executed",
        "stock_corporate_actions_audited", "benchmark_total_return_basis_audited",
        "portfolio_eligibility_allowed", "live_capital_allowed",
    ):
        assert result[field] is False
    assert comp == original_comp


def _oct16_fixture() -> tuple[dict, dict, dict, dict]:
    comparison, manifest, calendar, universe = _base()
    comparison["prior_capture_date_ist"] = "2026-09-18"
    comparison["current_capture_date_ist"] = "2026-10-16"
    for row in comparison["revision_observations"]:
        row["prior_capture_date"] = "2026-09-18"
        row["current_capture_date"] = "2026-10-16"
    manifest["capture_date_ist"] = "2026-10-16"
    manifest["logical_capture_id"] = "2026-10-16-full-u001-v1"
    manifest["captured_at_utc"] = "2026-10-16T13:00:00Z"
    return comparison, manifest, calendar, universe


def test_next_week_future_cohort_uses_its_own_next_verified_open() -> None:
    comparison, manifest, calendar, universe = _oct16_fixture()
    result = _build(
        comparison, manifest, calendar, universe,
        when="2026-10-17T01:00:00Z",
    )
    assert result["intent_id"] == "H021-P005-2026-10-16-PRIMARY-ENTRY-v1"
    assert result["planned_entry"]["session_date_ist"] == "2026-10-19"
    assert result["selected_count"] == 10


@pytest.mark.parametrize("value", [
    "2026-10-16T09:50:00Z",
    "2026-10-19T04:00:00Z",
])
def test_rejects_before_capture_and_after_next_market_open(value: str) -> None:
    comp, manifest, calendar, universe = _oct16_fixture()
    with pytest.raises(ValueError, match="after next open or before source close"):
        _build(comp, manifest, calendar, universe, when=value)


def test_rejects_late_capture_even_when_planning_time_precedes_next_open() -> None:
    comp, manifest, calendar, universe = _oct16_fixture()
    manifest["captured_at_utc"] = "2026-10-19T03:46:00Z"
    with pytest.raises(ValueError, match="after next open"):
        _build(comp, manifest, calendar, universe, when="2026-10-19T03:44:00Z")


def test_rejects_relabelled_cohort_or_removed_analyst_coverage() -> None:
    comp, manifest, calendar, universe = _base()
    comp["primary_top_decile_symbols"][0] = "TRENT"
    with pytest.raises(ValueError, match="top-decile"):
        _build(comp, manifest, calendar, universe)

    comp, manifest, calendar, universe = _base()
    symbol = comp["primary_top_decile_symbols"][0]
    row = next(row for row in comp["revision_observations"] if row["symbol"] == symbol)
    row["analyst_count_current"] = 1
    with pytest.raises(ValueError, match="analyst primary threshold"):
        _build(comp, manifest, calendar, universe)


def test_rejects_frozen_source_or_horizon_changes() -> None:
    comp, manifest, calendar, universe = _base()
    comp["outcomes_opened"] = True
    with pytest.raises(ValueError, match="return outcomes"):
        _build(comp, manifest, calendar, universe)

    comp, manifest, calendar, universe = _base()
    comp["universe_git_blob_sha"] = "0" * 40
    with pytest.raises(ValueError, match="universe"):
        _build(comp, manifest, calendar, universe)

    comp, manifest, calendar, universe = _base()
    calendar["sessions"] = [
        row for row in calendar["sessions"]
        if row["session_date"] <= "2026-10-09"
    ]
    with pytest.raises(ValueError, match="no verified next NSE session"):
        _build(comp, manifest, calendar, universe)


def test_rejects_duplicate_and_missing_company_universe() -> None:
    comp, manifest, calendar, universe = _base()
    comp["revision_observations"][0]["symbol"] = comp[
        "revision_observations"
    ][1]["symbol"]
    with pytest.raises(ValueError, match="duplicate"):
        _build(comp, manifest, calendar, universe)

    comp, manifest, calendar, universe = _base()
    universe["members"][0]["symbol"] = "NONEXISTENT"
    with pytest.raises(ValueError, match="symbol set"):
        _build(comp, manifest, calendar, universe)
