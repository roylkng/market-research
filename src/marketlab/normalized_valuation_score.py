from __future__ import annotations

import math
import statistics
from math import ceil
from typing import Any

from marketlab.alpha import AlphaContractError, digest

SCORE_ID = "NV001-S001-v1"
EXPECTED_DIAGNOSTIC_ID = "NV001-D001-P1-v1"
EXPECTED_PANEL_SHA256 = "3dbe5b914a532bb028ad38c6b6eec9762ef47f31ccc85289d1d1f9b69b251400"
EXPECTED_UNIVERSE_SHA256 = "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
EXPECTED_HISTORICAL_COUNT = 4


def _positive_finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _midpoint_percentile(values: list[float], value: float) -> float:
    if not values:
        raise AlphaContractError("NV001 S001 percentile requires non-empty values")
    less = sum(candidate < value for candidate in values)
    equal = sum(candidate == value for candidate in values)
    return 100.0 * (less + 0.5 * equal) / len(values)


def _validate_panel(panel: dict[str, Any]) -> None:
    if panel.get("diagnostic_id") != EXPECTED_DIAGNOSTIC_ID:
        raise AlphaContractError("NV001 S001 requires frozen P1 diagnostic")
    if panel.get("panel_sha256") != EXPECTED_PANEL_SHA256:
        raise AlphaContractError("NV001 S001 source panel SHA mismatch")
    if panel.get("universe_sha256") != EXPECTED_UNIVERSE_SHA256:
        raise AlphaContractError("NV001 S001 universe SHA mismatch")
    if panel.get("return_outcomes_opened") is not False:
        raise AlphaContractError("NV001 S001 refuses source panel with opened returns")
    if panel.get("model_fitted") is not False:
        raise AlphaContractError("NV001 S001 refuses fitted source model")
    if panel.get("portfolio_eligibility_allowed") is not False:
        raise AlphaContractError("NV001 S001 refuses portfolio-eligible source panel")
    if panel.get("live_capital_allowed") is not False:
        raise AlphaContractError("NV001 S001 refuses live-capital source panel")


def _history(record: dict[str, Any]) -> list[float]:
    observations = record.get("annual_observations")
    if not isinstance(observations, list):
        return []
    values: list[float] = []
    for row in observations:
        if not isinstance(row, dict):
            return []
        value = _positive_finite(row.get("trailing_pe"))
        if value is None:
            return []
        values.append(value)
    return values


def _eligible(record: dict[str, Any]) -> bool:
    history = _history(record)
    current = _positive_finite(record.get("current_trailing_pe"))
    return len(history) == EXPECTED_HISTORICAL_COUNT and current is not None


def build_normalized_valuation_score(panel: dict[str, Any]) -> dict[str, Any]:
    _validate_panel(panel)

    records = panel.get("records")
    failures = panel.get("failures")
    if not isinstance(records, list) or not isinstance(failures, list):
        raise AlphaContractError("NV001 S001 source panel rows unavailable")
    if len(records) + len(failures) != 100:
        raise AlphaContractError("NV001 S001 requires complete 100-name accounting")

    symbols = [str(row.get("symbol") or "") for row in records]
    if len(symbols) != len(set(symbols)):
        raise AlphaContractError("NV001 S001 duplicate source symbols")

    eligible = [row for row in records if _eligible(row)]
    if len(eligible) != 69:
        raise AlphaContractError(
            f"NV001 S001 expected 69 eligible rows, observed {len(eligible)}"
        )

    relative_values: dict[str, float] = {}
    context: dict[str, dict[str, float]] = {}
    for record in eligible:
        symbol = str(record["symbol"])
        history = _history(record)
        current = _positive_finite(record.get("current_trailing_pe"))
        assert current is not None
        median_pe = float(statistics.median(history))
        ratio = current / median_pe
        if not math.isfinite(ratio) or ratio <= 0:
            raise AlphaContractError(f"{symbol}: invalid current-to-history median")
        relative_values[symbol] = ratio
        context[symbol] = {
            "historical_min_pe": min(history),
            "historical_max_pe": max(history),
            "historical_median_pe": median_pe,
            "current_trailing_pe": current,
            "current_to_history_median": ratio,
            "discount_to_history_median_pct": 100.0 * (1.0 - ratio),
        }

    transformed = [-ratio for ratio in relative_values.values()]
    scored_rows = []
    for record in eligible:
        symbol = str(record["symbol"])
        ratio = relative_values[symbol]
        score = _midpoint_percentile(transformed, -ratio)
        scored_rows.append(
            {
                "symbol": symbol,
                "score_status": "SCORED",
                "normalized_valuation_score": score,
                **context[symbol],
                "accounting_basis": record.get("accounting_basis"),
                "source_record_sha256": record.get("record_sha256"),
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    scored_rows.sort(
        key=lambda row: (-row["normalized_valuation_score"], row["symbol"])
    )
    for rank, row in enumerate(scored_rows, start=1):
        row["valuation_rank"] = rank

    quartile_nominal_count = ceil(len(scored_rows) / 4.0)
    quartile_cutoff = scored_rows[quartile_nominal_count - 1][
        "normalized_valuation_score"
    ]
    for row in scored_rows:
        row["top_valuation_quartile"] = (
            row["normalized_valuation_score"] >= quartile_cutoff
        )

    source_unavailable = []
    unscored_partial = []
    for record in records:
        if _eligible(record):
            continue
        unscored_partial.append(
            {
                "symbol": record.get("symbol"),
                "score_status": "INSUFFICIENT_COMPLETE_HISTORY",
                "historical_pe_count": record.get("historical_pe_count"),
                "current_trailing_pe": record.get("current_trailing_pe"),
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )
    for failure in failures:
        source_unavailable.append(
            {
                "symbol": failure.get("symbol"),
                "score_status": "SOURCE_UNAVAILABLE",
                "reason_codes": [failure.get("stage"), failure.get("reason")],
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    output = {
        "schema_version": 1,
        "score_id": SCORE_ID,
        "classification": "POINT_IN_TIME_OWN_HISTORY_VALUATION_RESEARCH_SCORE_NOT_ALPHA",
        "source": {
            "diagnostic_id": EXPECTED_DIAGNOSTIC_ID,
            "source_panel_sha256": EXPECTED_PANEL_SHA256,
            "universe_sha256": EXPECTED_UNIVERSE_SHA256,
        },
        "scored_count": len(scored_rows),
        "insufficient_complete_history_count": len(unscored_partial),
        "source_unavailable_count": len(source_unavailable),
        "top_valuation_quartile_cutoff": quartile_cutoff,
        "top_valuation_quartile_count": sum(
            row["top_valuation_quartile"] for row in scored_rows
        ),
        "rows": scored_rows,
        "unscored_partial": sorted(
            unscored_partial, key=lambda row: str(row["symbol"])
        ),
        "source_unavailable": sorted(
            source_unavailable, key=lambda row: str(row["symbol"])
        ),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["score_sha256"] = digest(output)
    return output
