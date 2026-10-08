from __future__ import annotations

import math
from collections import Counter
from datetime import UTC, date, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest

AUDIT_ID = "SS001-D005-v1"
PRICE_SESSION = "2026-10-01"
PUBLICATION_CUTOFF_UTC = "2026-10-01T13:00:00Z"
EXPECTED_UNIVERSE_COUNT = 2319
EXPECTED_ELIGIBLE_SHARE_COUNT = 1965

EXPECTED_SOURCE = {
    "market": (
        "census_id",
        "SS001-D001-v1",
        "census_sha256",
        "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7",
    ),
    "shareholding": (
        "census_id",
        "SS001-D002-v1",
        "census_sha256",
        "214c1172491d58800dcded126303e7a2844967e75da57e0e6f666abc3b311293",
    ),
    "share_count": (
        "diagnostic_id",
        "SS001-D004-v1",
        "panel_sha256",
        "ab782411fef19afd80cdde3da1cba402eff70778ce0aaa0bd3e3afd571ee7428",
    ),
}

SHARE_ACTION_KEYS = (
    "bonus",
    "rights",
    "scheme_or_reorganisation",
    "split_or_consolidation",
)


def _source_index(payload: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    id_key, id_value, sha_key, sha_value = EXPECTED_SOURCE[label]
    if payload.get(id_key) != id_value or payload.get(sha_key) != sha_value:
        raise AlphaContractError(f"SS001 D005 {label} frozen source identity mismatch")
    for flag in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if payload.get(flag) is not False:
            raise AlphaContractError(f"SS001 D005 {label} requires {flag}=false")

    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_UNIVERSE_COUNT:
        raise AlphaContractError(f"SS001 D005 {label} requires 2319 source rows")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError(f"SS001 D005 {label} row must be an object")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in indexed:
            raise AlphaContractError(f"SS001 D005 {label} has invalid/duplicate symbols")
        indexed[symbol] = row
    return indexed


def _publication_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        return None
    return timestamp.astimezone(UTC)


def _report_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _positive_close(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _share_action_context(actions: object) -> str:
    if not isinstance(actions, dict):
        return "ACTION_CENSUS_UNAVAILABLE"
    values = []
    for key in SHARE_ACTION_KEYS:
        value = actions.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return "ACTION_CENSUS_UNAVAILABLE"
        values.append(value)
    if any(values):
        return "KNOWN_CORPORATE_ACTION_REVIEW_REQUIRED"
    return "NO_FLAG_IN_D001_STILL_UNVERIFIED"


def build_size_source_readiness(
    *,
    market_census: dict[str, Any],
    shareholding_census: dict[str, Any],
    share_count_panel: dict[str, Any],
) -> dict[str, Any]:
    market = _source_index(market_census, "market")
    holding = _source_index(shareholding_census, "shareholding")
    shares = _source_index(share_count_panel, "share_count")
    if set(market) != set(holding) or set(market) != set(shares):
        raise AlphaContractError("SS001 D005 cross-source symbol sets differ")

    if market_census.get("as_of_completed_session") != PRICE_SESSION:
        raise AlphaContractError("SS001 D005 price anchor is not 2026-10-01")
    if share_count_panel.get("capitalization_source_eligible_count") != (
        EXPECTED_ELIGIBLE_SHARE_COUNT
    ):
        raise AlphaContractError("SS001 D005 eligible share-count population mismatch")

    cutoff = _publication_timestamp(PUBLICATION_CUTOFF_UTC)
    assert cutoff is not None

    rows: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    review_counts: Counter[str] = Counter()
    eligible_population = 0
    ready_count = 0
    source_conflicts = 0

    for symbol in sorted(market):
        market_row = market[symbol]
        holding_row = holding[symbol]
        shares_row = shares[symbol]

        if market_row.get("series") != "EQ" or not market_row.get("isin"):
            state = "MARKET_SECURITY_IDENTITY_UNAVAILABLE"
        elif (
            shares_row.get("status") != "SHARE_COUNT_READY"
            or shares_row.get("capitalization_source_eligible") is not True
            or shares_row.get("partly_paid_flag") != "FALSE"
            or not isinstance(shares_row.get("reported_share_count"), int)
            or isinstance(shares_row.get("reported_share_count"), bool)
            or shares_row["reported_share_count"] <= 0
        ):
            state = "CAPITALIZATION_SHARE_SOURCE_NOT_READY"
        else:
            eligible_population += 1
            latest = holding_row.get("latest")
            if holding_row.get("source_state") != "READY" or not isinstance(latest, dict):
                state = "SHAREHOLDING_PUBLICATION_UNAVAILABLE"
            elif (
                shares_row.get("source_url") != latest.get("xbrl_url")
                or shares_row.get("report_date") != latest.get("report_date")
            ):
                state = "SOURCE_ID_CONFLICT"
                source_conflicts += 1
            else:
                published = _publication_timestamp(latest.get("broadcast_at_utc"))
                report_date = _report_date(latest.get("report_date"))
                if published is None or report_date is None:
                    state = "SHAREHOLDING_PUBLICATION_UNAVAILABLE"
                elif published > cutoff or report_date > date.fromisoformat(PRICE_SESSION):
                    state = "SHAREHOLDING_NOT_PUBLIC_AT_PRICE_CUTOFF"
                else:
                    price_context = market_row.get("market")
                    if (
                        not isinstance(price_context, dict)
                        or price_context.get("last_observed_session") != PRICE_SESSION
                        or not _positive_close(price_context.get("last_close"))
                    ):
                        state = "EXACT_PRICE_NOT_AVAILABLE"
                    else:
                        state = "TIME_AND_PRICE_READY"
                        ready_count += 1

        action_state = _share_action_context(
            market_row.get("corporate_actions_1y")
        )
        state_counts[state] += 1
        if state == "TIME_AND_PRICE_READY":
            review_counts[action_state] += 1

        latest = holding_row.get("latest")
        rows.append(
            {
                "symbol": symbol,
                "isin": market_row.get("isin"),
                "market_series": market_row.get("series"),
                "source_readiness_state": state,
                "d004_share_count_status": shares_row.get("status"),
                "d004_capitalization_source_eligible": (
                    shares_row.get("capitalization_source_eligible") is True
                ),
                "report_date": shares_row.get("report_date"),
                "exchange_published_at_utc": (
                    latest.get("broadcast_at_utc") if isinstance(latest, dict) else None
                ),
                "market_price_session": (
                    market_row.get("market", {}).get("last_observed_session")
                    if isinstance(market_row.get("market"), dict)
                    else None
                ),
                "share_action_clearance": action_state,
                "share_action_clearance_proven": False,
                "share_class_continuity_proven": False,
                "capitalization_calculation_allowed": False,
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    if eligible_population != EXPECTED_ELIGIBLE_SHARE_COUNT:
        raise AlphaContractError("SS001 D005 eligible accounting differs from D004")

    thresholds = {
        "complete_2319_identity_accounting": len(rows) == EXPECTED_UNIVERSE_COUNT,
        "exact_1965_eligible_share_count_accounting": (
            eligible_population == EXPECTED_ELIGIBLE_SHARE_COUNT
        ),
        "at_least_85pct_asof_price_readiness": (
            ready_count / eligible_population >= 0.85
        ),
        "zero_source_id_conflicts": source_conflicts == 0,
        "no_current_market_cap_outputs": True,
    }

    result = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "status": "COMPLETE_SOURCE_READINESS",
        "classification": "ASOF_SOURCE_JOIN_READINESS_NOT_MARKET_CAP",
        "price_session": PRICE_SESSION,
        "publication_cutoff_utc": PUBLICATION_CUTOFF_UTC,
        "source_sha256": {
            label: fields[3]
            for label, fields in sorted(EXPECTED_SOURCE.items())
        },
        "identity_count": len(rows),
        "d004_capitalization_source_eligible_count": eligible_population,
        "time_and_price_ready_count": ready_count,
        "time_and_price_ready_ratio": ready_count / eligible_population,
        "source_id_conflict_count": source_conflicts,
        "readiness_state_counts": dict(sorted(state_counts.items())),
        "share_action_clearance_state_counts_in_ready": dict(
            sorted(review_counts.items())
        ),
        "threshold_passes": thresholds,
        "feasibility_pass": all(thresholds.values()),
        "promotion_allowed_to_d006_share_change_review": all(thresholds.values()),
        "market_capitalization_calculated": False,
        "rows": rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["audit_sha256"] = digest(result)
    return result
