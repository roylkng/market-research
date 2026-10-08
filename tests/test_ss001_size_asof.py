from __future__ import annotations

import copy

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_size_asof import build_size_source_readiness


def _sources() -> tuple[dict, dict, dict]:
    market_rows = []
    holding_rows = []
    share_rows = []
    for i in range(2319):
        symbol = f"S{i:04d}"
        eligible = i < 1965
        url = f"https://nsearchives.nseindia.com/xbrl/{i}.xml"
        market_rows.append(
            {
                "symbol": symbol,
                "isin": f"INE{i:09d}",
                "series": "EQ",
                "market": {
                    "last_observed_session": "2026-10-01",
                    "last_close": 80.0,
                },
                "corporate_actions_1y": {
                    "bonus": 0,
                    "rights": 0,
                    "scheme_or_reorganisation": 0,
                    "split_or_consolidation": 0,
                },
            }
        )
        holding_rows.append(
            {
                "symbol": symbol,
                "source_state": "READY" if eligible else "NO_STANDARD_QUARTER",
                "latest": (
                    {
                        "report_date": "2026-06-30",
                        "xbrl_url": url,
                        "broadcast_at_utc": "2026-07-19T12:00:00Z",
                    }
                    if eligible
                    else None
                ),
            }
        )
        share_rows.append(
            {
                "symbol": symbol,
                "status": "SHARE_COUNT_READY" if eligible else "SOURCE_UNAVAILABLE",
                "capitalization_source_eligible": eligible,
                "reported_share_count": 2_000_000 if eligible else None,
                "partly_paid_flag": "FALSE" if eligible else None,
                "report_date": "2026-06-30" if eligible else None,
                "source_url": url if eligible else None,
            }
        )

    market = {
        "census_id": "SS001-D001-v1",
        "census_sha256": (
            "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
        ),
        "as_of_completed_session": "2026-10-01",
        "rows": market_rows,
    }
    holding = {
        "census_id": "SS001-D002-v1",
        "census_sha256": (
            "214c1172491d58800dcded126303e7a2844967e75da57e0e6f666abc3b311293"
        ),
        "rows": holding_rows,
    }
    shares = {
        "diagnostic_id": "SS001-D004-v1",
        "panel_sha256": (
            "ab782411fef19afd80cdde3da1cba402eff70778ce0aaa0bd3e3afd571ee7428"
        ),
        "capitalization_source_eligible_count": 1965,
        "rows": share_rows,
    }
    for payload in (market, holding, shares):
        payload.update(
            {
                "return_outcomes_opened": False,
                "model_fitted": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )
    return market, holding, shares


def _run(market: dict, holding: dict, shares: dict) -> dict:
    return build_size_source_readiness(
        market_census=market,
        shareholding_census=holding,
        share_count_panel=shares,
    )


def test_complete_point_in_time_readiness_is_not_market_cap() -> None:
    market, holding, shares = _sources()
    output = _run(market, holding, shares)
    assert output["identity_count"] == 2319
    assert output["d004_capitalization_source_eligible_count"] == 1965
    assert output["time_and_price_ready_count"] == 1965
    assert output["feasibility_pass"] is True
    assert output["market_capitalization_calculated"] is False
    assert output["portfolio_eligibility_allowed"] is False
    row = output["rows"][0]
    assert row["capitalization_calculation_allowed"] is False
    assert row["share_action_clearance"] == "NO_FLAG_IN_D001_STILL_UNVERIFIED"
    assert not any(key.startswith("market_cap") for key in row)


def test_future_published_filing_cannot_qualify() -> None:
    market, holding, shares = _sources()
    holding["rows"][0]["latest"]["broadcast_at_utc"] = "2026-10-02T10:00:00Z"
    output = _run(market, holding, shares)
    assert output["time_and_price_ready_count"] == 1964
    assert output["rows"][0]["source_readiness_state"] == (
        "SHAREHOLDING_NOT_PUBLIC_AT_PRICE_CUTOFF"
    )


def test_conflicting_source_url_fails_frozen_gate() -> None:
    market, holding, shares = _sources()
    shares["rows"][0]["source_url"] = "https://nsearchives.nseindia.com/other.xml"
    output = _run(market, holding, shares)
    assert output["source_id_conflict_count"] == 1
    assert output["feasibility_pass"] is False
    assert output["rows"][0]["source_readiness_state"] == "SOURCE_ID_CONFLICT"


def test_known_action_is_review_only_not_clearance() -> None:
    market, holding, shares = _sources()
    market["rows"][0]["corporate_actions_1y"]["bonus"] = 1
    output = _run(market, holding, shares)
    row = output["rows"][0]
    assert row["source_readiness_state"] == "TIME_AND_PRICE_READY"
    assert row["share_action_clearance"] == "KNOWN_CORPORATE_ACTION_REVIEW_REQUIRED"
    assert row["share_action_clearance_proven"] is False


def test_forged_source_hash_rejected() -> None:
    market, holding, shares = _sources()
    modified = copy.deepcopy(shares)
    modified["panel_sha256"] = "x" * 64
    with pytest.raises(AlphaContractError, match="frozen source identity mismatch"):
        _run(market, holding, modified)


def test_no_future_return_or_portfolio_eligibility() -> None:
    market, holding, shares = _sources()
    market["return_outcomes_opened"] = True
    with pytest.raises(AlphaContractError, match="return_outcomes_opened=false"):
        _run(market, holding, shares)
