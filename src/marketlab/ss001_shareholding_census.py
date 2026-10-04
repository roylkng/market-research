from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.h023_acquisition import discover_standard_quarter_sources
from marketlab.h023_ownership import previous_quarter_end

CENSUS_ID = "SS001-D002-v1"
EXPECTED_D001_ID = "SS001-D001-v1"
EXPECTED_D001_SHA = "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
EXPECTED_IDENTITY_COUNT = 2319


def _latest_for_date(
    sources: list[dict[str, Any]],
    report_date: str,
) -> dict[str, Any] | None:
    matches = [row for row in sources if row.get("report_date") == report_date]
    if not matches:
        return None
    matches.sort(
        key=lambda row: (
            str(row.get("broadcast_at_utc") or ""),
            str(row.get("record_id") or ""),
        ),
        reverse=True,
    )
    best_time = str(matches[0].get("broadcast_at_utc") or "")
    same_time = [
        row for row in matches if str(row.get("broadcast_at_utc") or "") == best_time
    ]
    source_ids = {str(row.get("source_id") or "") for row in same_time}
    if len(source_ids) != 1:
        raise AlphaContractError(
            f"SS001 D002 ambiguous latest revision for {report_date}"
        )
    return matches[0]


def summarize_shareholding_master(
    payload: object,
    *,
    symbol: str,
    raw_sha256: str,
) -> dict[str, Any]:
    sources = discover_standard_quarter_sources(payload, symbol=symbol)
    if not sources:
        return {
            "symbol": symbol,
            "source_state": "NO_STANDARD_QUARTER",
            "raw_master_sha256": raw_sha256,
            "latest": None,
            "prior": None,
            "has_adjacent_prior": False,
        }

    report_dates = sorted(
        {str(row["report_date"]) for row in sources},
        reverse=True,
    )
    latest_date = report_dates[0]
    latest = _latest_for_date(sources, latest_date)
    if latest is None:
        raise AlphaContractError("SS001 D002 latest source selection failed")
    prior_date = previous_quarter_end(latest_date)
    prior = _latest_for_date(sources, prior_date)

    def compact(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "source_id": row.get("source_id"),
            "record_id": row.get("record_id"),
            "report_date": row.get("report_date"),
            "broadcast_at_utc": row.get("broadcast_at_utc"),
            "xbrl_url": row.get("xbrl_url"),
            "master_row_sha256": row.get("master_row_sha256"),
            "revision_status": row.get("revision_status"),
            "revision_date": row.get("revision_date"),
        }

    return {
        "symbol": symbol,
        "source_state": "READY",
        "raw_master_sha256": raw_sha256,
        "latest": compact(latest),
        "prior": compact(prior),
        "has_adjacent_prior": prior is not None,
    }


def validate_d001_census(census: dict[str, Any]) -> list[dict[str, Any]]:
    if census.get("census_id") != EXPECTED_D001_ID:
        raise AlphaContractError("SS001 D002 requires frozen D001 census")
    if census.get("census_sha256") != EXPECTED_D001_SHA:
        raise AlphaContractError("SS001 D002 D001 census SHA mismatch")
    if census.get("eq_identity_count") != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("SS001 D002 identity count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if census.get(field) is not False:
            raise AlphaContractError(f"SS001 D002 requires D001 {field}=false")
    rows = census.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("SS001 D002 D001 rows unavailable")
    symbols = [str(row.get("symbol") or "").upper() for row in rows]
    if any(not symbol for symbol in symbols) or len(symbols) != len(set(symbols)):
        raise AlphaContractError("SS001 D002 D001 symbols are invalid")
    return rows


def build_shareholding_source_census(
    d001_census: dict[str, Any],
    acquired_rows: list[dict[str, Any]],
    *,
    captured_at_utc: str,
) -> dict[str, Any]:
    input_rows = validate_d001_census(d001_census)
    expected_symbols = {str(row["symbol"]).upper() for row in input_rows}

    by_symbol: dict[str, dict[str, Any]] = {}
    for row in acquired_rows:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol or symbol in by_symbol:
            raise AlphaContractError("SS001 D002 acquired rows require unique symbols")
        by_symbol[symbol] = row
    if set(by_symbol) != expected_symbols:
        missing = sorted(expected_symbols - set(by_symbol))
        extra = sorted(set(by_symbol) - expected_symbols)
        raise AlphaContractError(
            f"SS001 D002 source accounting mismatch: missing={missing[:10]} extra={extra[:10]}"
        )

    ready = sum(row.get("source_state") == "READY" for row in acquired_rows)
    adjacent = sum(
        row.get("source_state") == "READY"
        and row.get("has_adjacent_prior") is True
        for row in acquired_rows
    )
    state_counts = Counter(str(row.get("source_state") or "") for row in acquired_rows)

    ready_ratio = ready / EXPECTED_IDENTITY_COUNT
    adjacent_ratio = adjacent / EXPECTED_IDENTITY_COUNT
    threshold_passes = {
        "minimum_latest_standard_quarter_coverage": ready_ratio >= 0.85,
        "minimum_adjacent_quarter_coverage": adjacent_ratio >= 0.75,
        "complete_identity_accounting": len(acquired_rows) == EXPECTED_IDENTITY_COUNT,
    }

    output = {
        "schema_version": 1,
        "census_id": CENSUS_ID,
        "classification": "FULL_MARKET_SHAREHOLDING_SOURCE_CENSUS_NOT_ALPHA",
        "captured_at_utc": captured_at_utc,
        "source_endpoint": (
            "https://www.nseindia.com/api/corporate-share-holdings-master"
        ),
        "input_d001_census_sha256": EXPECTED_D001_SHA,
        "identity_count": EXPECTED_IDENTITY_COUNT,
        "ready_latest_source_count": ready,
        "ready_latest_source_ratio": ready_ratio,
        "adjacent_quarter_source_count": adjacent,
        "adjacent_quarter_source_ratio": adjacent_ratio,
        "source_state_counts": dict(sorted(state_counts.items())),
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_gf001_parser_design": all(threshold_passes.values()),
        "rows": sorted(acquired_rows, key=lambda row: str(row["symbol"])),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["census_sha256"] = digest(output)
    return output
