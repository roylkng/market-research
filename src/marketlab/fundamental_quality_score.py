from __future__ import annotations

from math import ceil
from typing import Any

from marketlab.alpha import AlphaContractError, digest

SCORE_ID = "FQ001-S001-v1"
EXPECTED_DIAGNOSTIC_ID = "FQ001-D001-P2-v1"
EXPECTED_PANEL_SHA256 = "0112a61cdb928c35ecf0c55a6f8a95ccb3ebc8a137ee3d8f31c1816c89134ee4"
EXPECTED_UNIVERSE_SHA256 = "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"


def _midpoint_percentile(values: list[float], value: float) -> float:
    if not values:
        raise AlphaContractError("FQ001 S001 percentile requires non-empty values")
    less = sum(candidate < value for candidate in values)
    equal = sum(candidate == value for candidate in values)
    return 100.0 * (less + 0.5 * equal) / len(values)


def _avg_capital_employed(record: dict[str, Any]) -> float | None:
    target = record["target_facts"]
    baseline = record["baseline_facts"]
    fields = ("total_assets", "current_liabilities")
    if any(target.get(field) is None or baseline.get(field) is None for field in fields):
        return None
    target_ce = target["total_assets"] - target["current_liabilities"]
    baseline_ce = baseline["total_assets"] - baseline["current_liabilities"]
    return (target_ce + baseline_ce) / 2.0


def _eligibility_reasons(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if record.get("all_core_metrics_complete") is not True:
        reasons.append("CORE_METRICS_INCOMPLETE")
    target = record.get("target_facts")
    if not isinstance(target, dict):
        return reasons + ["TARGET_FACTS_UNAVAILABLE"]

    pat = target.get("profit_after_tax")
    equity = target.get("total_equity")
    revenue = target.get("revenue")
    avg_ce = _avg_capital_employed(record)

    if not isinstance(pat, (int, float)) or isinstance(pat, bool) or pat <= 0:
        reasons.append("PAT_NONPOSITIVE")
    if not isinstance(equity, (int, float)) or isinstance(equity, bool) or equity <= 0:
        reasons.append("EQUITY_NONPOSITIVE")
    if not isinstance(avg_ce, (int, float)) or isinstance(avg_ce, bool) or avg_ce <= 0:
        reasons.append("AVG_CAPITAL_EMPLOYED_NONPOSITIVE")
    if not isinstance(revenue, (int, float)) or isinstance(revenue, bool) or revenue <= 0:
        reasons.append("REVENUE_NONPOSITIVE")
    return reasons


def _validate_panel(panel: dict[str, Any]) -> None:
    if panel.get("diagnostic_id") != EXPECTED_DIAGNOSTIC_ID:
        raise AlphaContractError("FQ001 S001 requires frozen P2 diagnostic")
    if panel.get("panel_sha256") != EXPECTED_PANEL_SHA256:
        raise AlphaContractError("FQ001 S001 source panel SHA mismatch")
    if panel.get("universe_sha256") != EXPECTED_UNIVERSE_SHA256:
        raise AlphaContractError("FQ001 S001 universe SHA mismatch")
    if panel.get("return_outcomes_opened") is not False:
        raise AlphaContractError("FQ001 S001 refuses source panel with opened returns")
    if panel.get("model_fitted") is not False:
        raise AlphaContractError("FQ001 S001 refuses fitted source model")
    if panel.get("portfolio_eligibility_allowed") is not False:
        raise AlphaContractError("FQ001 S001 refuses portfolio-eligible source panel")
    if panel.get("live_capital_allowed") is not False:
        raise AlphaContractError("FQ001 S001 refuses live-capital source panel")


def build_quality_score(panel: dict[str, Any]) -> dict[str, Any]:
    _validate_panel(panel)

    records = panel.get("records")
    failures = panel.get("failures")
    if not isinstance(records, list) or not isinstance(failures, list):
        raise AlphaContractError("FQ001 S001 source panel rows unavailable")
    if len(records) != 88 or len(failures) != 12:
        raise AlphaContractError("FQ001 S001 requires frozen P2 88/12 source accounting")
    if len(records) + len(failures) != 100:
        raise AlphaContractError("FQ001 S001 requires complete 100-name accounting")

    record_by_symbol = {record["symbol"]: record for record in records}
    failure_by_symbol = {failure["symbol"]: failure for failure in failures}
    if len(record_by_symbol) != len(records) or len(failure_by_symbol) != len(failures):
        raise AlphaContractError("FQ001 S001 duplicate source symbols")

    eligible_records = [
        record for record in records if not _eligibility_reasons(record)
    ]
    if not eligible_records:
        raise AlphaContractError("FQ001 S001 has no score-eligible rows")

    metric_values = {
        "roce_proxy": [float(record["metrics"]["roce_proxy"]) for record in eligible_records],
        "cfo_to_pat": [float(record["metrics"]["cfo_to_pat"]) for record in eligible_records],
        "negative_accruals": [
            -float(record["metrics"]["accruals_to_avg_assets"])
            for record in eligible_records
        ],
        "cfo_minus_ppe_to_pat": [
            float(record["metrics"]["cfo_minus_ppe_to_pat"])
            for record in eligible_records
        ],
        "negative_net_borrowings_to_equity": [
            -float(record["metrics"]["net_borrowings_to_equity"])
            for record in eligible_records
        ],
    }

    scored_rows = []
    excluded_rows = []
    for record in records:
        reasons = _eligibility_reasons(record)
        if reasons:
            excluded_rows.append(
                {
                    "symbol": record["symbol"],
                    "score_status": "QUALITY_PREREQUISITE_FAILED",
                    "reason_codes": reasons,
                    "source_record_sha256": record["record_sha256"],
                    "portfolio_eligibility_allowed": False,
                    "live_capital_allowed": False,
                }
            )
            continue

        metrics = record["metrics"]
        capital_efficiency = _midpoint_percentile(
            metric_values["roce_proxy"], float(metrics["roce_proxy"])
        )
        cfo_percentile = _midpoint_percentile(
            metric_values["cfo_to_pat"], float(metrics["cfo_to_pat"])
        )
        accrual_percentile = _midpoint_percentile(
            metric_values["negative_accruals"],
            -float(metrics["accruals_to_avg_assets"]),
        )
        cash_conversion = (cfo_percentile + accrual_percentile) / 2.0
        self_funded_reinvestment = _midpoint_percentile(
            metric_values["cfo_minus_ppe_to_pat"],
            float(metrics["cfo_minus_ppe_to_pat"]),
        )
        balance_sheet = _midpoint_percentile(
            metric_values["negative_net_borrowings_to_equity"],
            -float(metrics["net_borrowings_to_equity"]),
        )
        quality_score = (
            capital_efficiency
            + cash_conversion
            + self_funded_reinvestment
            + balance_sheet
        ) / 4.0

        scored_rows.append(
            {
                "symbol": record["symbol"],
                "score_status": "SCORED",
                "quality_score": quality_score,
                "pillars": {
                    "capital_efficiency": capital_efficiency,
                    "cash_conversion": cash_conversion,
                    "self_funded_reinvestment": self_funded_reinvestment,
                    "balance_sheet": balance_sheet,
                },
                "cash_conversion_subsignals": {
                    "cfo_to_pat_percentile": cfo_percentile,
                    "negative_accruals_percentile": accrual_percentile,
                },
                "raw_metrics": dict(metrics),
                "ppe_capex_to_revenue_context": metrics["ppe_capex_to_revenue"],
                "issuer_identity_continuity": record["issuer_identity_continuity"],
                "source_record_sha256": record["record_sha256"],
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    scored_rows.sort(key=lambda row: (-row["quality_score"], row["symbol"]))
    for rank, row in enumerate(scored_rows, start=1):
        row["quality_rank"] = rank

    quartile_nominal_count = ceil(len(scored_rows) / 4.0)
    quartile_cutoff = scored_rows[quartile_nominal_count - 1]["quality_score"]
    for row in scored_rows:
        row["top_quality_quartile"] = row["quality_score"] >= quartile_cutoff

    unavailable_rows = [
        {
            "symbol": failure["symbol"],
            "score_status": "SOURCE_UNAVAILABLE",
            "reason_codes": [failure["stage"], failure["reason"]],
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        }
        for failure in failures
    ]
    unavailable_rows.sort(key=lambda row: row["symbol"])
    excluded_rows.sort(key=lambda row: row["symbol"])

    output = {
        "schema_version": 1,
        "score_id": SCORE_ID,
        "classification": "POINT_IN_TIME_ACCOUNTING_QUALITY_RESEARCH_SCORE_NOT_ALPHA",
        "source_diagnostic_id": panel["diagnostic_id"],
        "source_panel_sha256": panel["panel_sha256"],
        "universe_sha256": panel["universe_sha256"],
        "source_complete_count": len(records),
        "scored_count": len(scored_rows),
        "quality_prerequisite_failed_count": len(excluded_rows),
        "source_unavailable_count": len(unavailable_rows),
        "score_rule": {
            "pillar_weights": {
                "capital_efficiency": 0.25,
                "cash_conversion": 0.25,
                "self_funded_reinvestment": 0.25,
                "balance_sheet": 0.25,
            },
            "cash_conversion_subweights": {
                "cfo_to_pat": 0.5,
                "negative_accruals_to_avg_assets": 0.5,
            },
            "percentile_method": "MIDPOINT_EMPIRICAL_CDF_WITHIN_SCORE_ELIGIBLE_SET",
            "ppe_capex_to_revenue_role": "CONTEXT_ONLY_NOT_SCORED",
            "sector_adjustment": "NONE",
        },
        "top_quality_quartile_cutoff": quartile_cutoff,
        "top_quality_quartile_count": sum(
            int(row["top_quality_quartile"]) for row in scored_rows
        ),
        "scored": scored_rows,
        "quality_prerequisite_failed": excluded_rows,
        "source_unavailable": unavailable_rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["score_sha256"] = digest(output)
    return output
