from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from typing import Any

import numpy as np
from scipy import stats

DIAGNOSTIC_ID = "H022-D002"
HYPOTHESIS_ID = "H022"
OUTCOME_REPORT_SHA256 = "310d3709393047db4ec5e2eacb9d333fac2d81b83e86bc65140dc4bc60c6d22f"
RECONSTRUCTION_SHA256 = "dee26ffc683781202da21e789cc45f480d625772e8510f3beb1f65aa4a6ba144"
U001_COHORT_ID = "FY27-Q2-2026-09-06"
U001_CAPTURED_AT_UTC = "2026-09-06T12:21:06.431463Z"
U001_MEMBER_COUNT = 100
EXPECTED_COMPLETE_PRIMARY = 559
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 22_024
MIN_INDUSTRY_COVERAGE_SHARE = 0.90
MIN_INDUSTRY_ELIGIBLE = 200
MIN_INDUSTRY_DETAIL_COUNT = 15


class H022CompositionDiagnosticError(ValueError):
    """Raised when H022 composition attribution cannot be reproduced safely."""


def _canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise H022CompositionDiagnosticError(
            "H022 composition diagnostic payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _validate_hashed_document(
    payload: dict[str, Any], *, field: str, expected: str, label: str
) -> None:
    if payload.get(field) != expected:
        raise H022CompositionDiagnosticError(f"{label} digest changed")
    unsigned = dict(payload)
    unsigned.pop(field, None)
    if _canonical_hash(unsigned) != expected:
        raise H022CompositionDiagnosticError(f"{label} hash mismatch")


def validate_inputs(
    outcome_report: dict[str, Any],
    reconstruction: dict[str, Any],
    current_u001: dict[str, Any],
) -> None:
    if outcome_report.get("hypothesis_id") != HYPOTHESIS_ID:
        raise H022CompositionDiagnosticError("unexpected expanded H022 hypothesis id")
    if outcome_report.get("execution_rule_id") != "H022-X001":
        raise H022CompositionDiagnosticError("unexpected expanded H022 execution rule")
    _validate_hashed_document(
        outcome_report,
        field="report_sha256",
        expected=OUTCOME_REPORT_SHA256,
        label="expanded H022 outcome report",
    )

    if reconstruction.get("hypothesis_id") != HYPOTHESIS_ID:
        raise H022CompositionDiagnosticError("unexpected historical-universe hypothesis id")
    _validate_hashed_document(
        reconstruction,
        field="reconstruction_sha256",
        expected=RECONSTRUCTION_SHA256,
        label="historical Nifty 200 reconstruction",
    )
    members = reconstruction.get("expanded_union_members")
    if not isinstance(members, list) or len(members) != 211:
        raise H022CompositionDiagnosticError("historical union membership changed")

    if current_u001.get("cohort_id") != U001_COHORT_ID:
        raise H022CompositionDiagnosticError("current U001 cohort id changed")
    if current_u001.get("captured_at_utc") != U001_CAPTURED_AT_UTC:
        raise H022CompositionDiagnosticError("current U001 capture timestamp changed")
    u001_members = current_u001.get("members")
    if not isinstance(u001_members, list) or len(u001_members) != U001_MEMBER_COUNT:
        raise H022CompositionDiagnosticError("current U001 membership count changed")


def _symbol_set(rows: list[object], *, label: str) -> set[str]:
    symbols: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise H022CompositionDiagnosticError(f"{label} member must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in symbols:
            raise H022CompositionDiagnosticError(f"invalid/duplicate {label} symbol: {symbol}")
        symbols.add(symbol)
    return symbols


def build_diagnostic_panel(
    outcome_report: dict[str, Any],
    reconstruction: dict[str, Any],
    current_u001: dict[str, Any],
) -> dict[str, Any]:
    validate_inputs(outcome_report, reconstruction, current_u001)
    union_rows = reconstruction["expanded_union_members"]
    union_symbols = _symbol_set(union_rows, label="historical union")
    u001_symbols = _symbol_set(current_u001["members"], label="current U001")
    if not u001_symbols.issubset(union_symbols):
        raise H022CompositionDiagnosticError("current U001 is not contained in historical union")

    industry_by_symbol: dict[str, str | None] = {}
    for row in union_rows:
        symbol = str(row["symbol"]).strip().upper()
        raw_industry = row.get("industry")
        industry = str(raw_industry).strip() if raw_industry is not None else None
        industry_by_symbol[symbol] = industry or None

    records: list[dict[str, Any]] = []
    outcome_records = outcome_report.get("records")
    if not isinstance(outcome_records, list):
        raise H022CompositionDiagnosticError("expanded H022 outcome records must be a list")
    for row in outcome_records:
        if not isinstance(row, dict):
            raise H022CompositionDiagnosticError("expanded H022 outcome row must be an object")
        horizon = row.get("horizons", {}).get("60")
        if not isinstance(horizon, dict) or horizon.get("status") != "COMPLETE":
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol not in union_symbols:
            raise H022CompositionDiagnosticError(
                f"complete H022 symbol missing from historical union: {symbol}"
            )
        records.append(
            {
                "source_id": str(row["source_id"]),
                "symbol": symbol,
                "h022_signal": float(row["primary_signal"]),
                "future_60d_excess_pp": float(horizon["gross_excess_pp"]),
                "composition_group": (
                    "CURRENT_U001"
                    if symbol in u001_symbols
                    else "ADDITIONAL_HISTORICAL_NIFTY200"
                ),
                "industry": industry_by_symbol[symbol],
            }
        )

    if len(records) != EXPECTED_COMPLETE_PRIMARY:
        raise H022CompositionDiagnosticError(
            f"expected {EXPECTED_COMPLETE_PRIMARY} complete 60-session rows, found {len(records)}"
        )
    panel: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "evidence_class": "POST_OUTCOME_COMPOSITION_DIAGNOSTIC",
        "outcome_report_sha256": OUTCOME_REPORT_SHA256,
        "reconstruction_sha256": RECONSTRUCTION_SHA256,
        "current_u001_cohort_id": U001_COHORT_ID,
        "record_count": len(records),
        "records": records,
    }
    panel["panel_sha256"] = _canonical_hash(panel)
    return panel


def _zscore(values: np.ndarray) -> np.ndarray:
    std = float(np.std(values, ddof=0))
    if not math.isfinite(std) or std <= 0:
        raise H022CompositionDiagnosticError("diagnostic variable has zero/non-finite dispersion")
    return (values - float(np.mean(values))) / std


def _spearman(rows: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    if len(rows) < 3:
        return None, None
    signal = np.asarray([float(row["h022_signal"]) for row in rows], dtype=float)
    future = np.asarray([float(row["future_60d_excess_pp"]) for row in rows], dtype=float)
    if float(np.std(signal)) <= 0 or float(np.std(future)) <= 0:
        return None, None
    rho, p_value = stats.spearmanr(signal, future)
    return float(rho), float(p_value)


def _quintile_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) < 10:
        return {
            "top_quintile_count": 0,
            "bottom_quintile_count": 0,
            "top_quintile_mean_excess_pp": None,
            "bottom_quintile_mean_excess_pp": None,
            "top_minus_bottom_mean_excess_pp": None,
            "top_quintile_median_excess_pp": None,
            "top_quintile_benchmark_beat_rate": None,
        }
    ordered = sorted(
        rows,
        key=lambda row: (float(row["h022_signal"]), str(row["source_id"])),
    )
    tagged = [
        (min(4, index * 5 // len(ordered)), row)
        for index, row in enumerate(ordered)
    ]
    bottom = [row for quintile, row in tagged if quintile == 0]
    top = [row for quintile, row in tagged if quintile == 4]
    top_values = [float(row["future_60d_excess_pp"]) for row in top]
    bottom_values = [float(row["future_60d_excess_pp"]) for row in bottom]
    top_mean = statistics.fmean(top_values)
    bottom_mean = statistics.fmean(bottom_values)
    return {
        "top_quintile_count": len(top),
        "bottom_quintile_count": len(bottom),
        "top_quintile_mean_excess_pp": top_mean,
        "bottom_quintile_mean_excess_pp": bottom_mean,
        "top_minus_bottom_mean_excess_pp": top_mean - bottom_mean,
        "top_quintile_median_excess_pp": statistics.median(top_values),
        "top_quintile_benchmark_beat_rate": (
            sum(value > 0 for value in top_values) / len(top_values)
        ),
    }


def _group_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rho, p_value = _spearman(rows)
    result = {
        "observation_count": len(rows),
        "symbol_count": len({str(row["symbol"]) for row in rows}),
        "spearman_signal_vs_future_excess": rho,
        "spearman_p_value": p_value,
    }
    result.update(_quintile_metrics(rows))
    return result


def _composition_coefficients(rows: list[dict[str, Any]]) -> tuple[float, float, float]:
    signal = np.asarray([float(row["h022_signal"]) for row in rows], dtype=float)
    future = np.asarray([float(row["future_60d_excess_pp"]) for row in rows], dtype=float)
    current = np.asarray(
        [1.0 if row["composition_group"] == "CURRENT_U001" else 0.0 for row in rows],
        dtype=float,
    )
    if float(np.min(current)) == float(np.max(current)):
        raise H022CompositionDiagnosticError("composition regression requires both groups")
    z_signal = _zscore(signal)
    design = np.column_stack(
        [np.ones(len(rows)), z_signal, current, z_signal * current]
    )
    coefficients, *_ = np.linalg.lstsq(design, future, rcond=None)
    additional_slope = float(coefficients[1])
    interaction = float(coefficients[3])
    current_slope = additional_slope + interaction
    return additional_slope, current_slope, interaction


def _industry_fixed_effect_coefficient(rows: list[dict[str, Any]]) -> float:
    industries = sorted({str(row["industry"]) for row in rows})
    if len(industries) < 2:
        raise H022CompositionDiagnosticError("industry regression requires at least two industries")
    signal = np.asarray([float(row["h022_signal"]) for row in rows], dtype=float)
    future = np.asarray([float(row["future_60d_excess_pp"]) for row in rows], dtype=float)
    z_signal = _zscore(signal)
    columns: list[np.ndarray] = [np.ones(len(rows)), z_signal]
    for industry in industries[1:]:
        columns.append(
            np.asarray([1.0 if row["industry"] == industry else 0.0 for row in rows])
        )
    design = np.column_stack(columns)
    coefficients, *_ = np.linalg.lstsq(design, future, rcond=None)
    return float(coefficients[1])


def _cluster_bootstrap_composition(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)
    symbols = sorted(by_symbol)
    rng = random.Random(BOOTSTRAP_SEED)
    additional: list[float] = []
    current: list[float] = []
    interaction: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample: list[dict[str, Any]] = []
        for _symbol in symbols:
            sample.extend(by_symbol[rng.choice(symbols)])
        try:
            add_slope, cur_slope, interaction_slope = _composition_coefficients(sample)
        except H022CompositionDiagnosticError:
            continue
        additional.append(add_slope)
        current.append(cur_slope)
        interaction.append(interaction_slope)
    if not additional:
        raise H022CompositionDiagnosticError("no valid composition bootstrap iterations")

    def interval(values: list[float]) -> list[float]:
        low, high = np.quantile(np.asarray(values, dtype=float), [0.025, 0.975])
        return [float(low), float(high)]

    return {
        "valid_iterations": len(additional),
        "additional_slope_ci_95_pp": interval(additional),
        "current_u001_slope_ci_95_pp": interval(current),
        "interaction_ci_95_pp": interval(interaction),
    }


def _cluster_bootstrap_industry(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)
    symbols = sorted(by_symbol)
    rng = random.Random(BOOTSTRAP_SEED)
    coefficients: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample: list[dict[str, Any]] = []
        for _symbol in symbols:
            sample.extend(by_symbol[rng.choice(symbols)])
        try:
            coefficients.append(_industry_fixed_effect_coefficient(sample))
        except H022CompositionDiagnosticError:
            continue
    if not coefficients:
        raise H022CompositionDiagnosticError("no valid industry bootstrap iterations")
    low, high = np.quantile(np.asarray(coefficients, dtype=float), [0.025, 0.975])
    return {
        "valid_iterations": len(coefficients),
        "coefficient_ci_95_low_pp": float(low),
        "coefficient_ci_95_high_pp": float(high),
    }


def _composition_classification(additional_slope: float, current_slope: float) -> str:
    if additional_slope > 0 and current_slope > 0:
        return "BROAD_POSITIVE"
    if additional_slope <= 0 < current_slope:
        return "CURRENT_U001_CONCENTRATED"
    if current_slope <= 0 < additional_slope:
        return "ADDITIONAL_CONCENTRATED"
    return "BROAD_NONPOSITIVE"


def _industry_classification(
    *,
    coverage_share: float,
    eligible_count: int,
    coefficient: float | None,
    ci_low: float | None,
    leave_one_out_min: float | None,
) -> str:
    if coverage_share < MIN_INDUSTRY_COVERAGE_SHARE or eligible_count < MIN_INDUSTRY_ELIGIBLE:
        return "DATA_INSUFFICIENT"
    if coefficient is None or coefficient <= 0:
        return "NOT_ESTABLISHED"
    if ci_low is not None and ci_low > 0 and leave_one_out_min is not None and leave_one_out_min > 0:
        return "SUPPORTIVE_BREADTH"
    if leave_one_out_min is not None and leave_one_out_min > 0:
        return "PARTIAL_BREADTH"
    return "SECTOR_SENSITIVE"


def summarize_diagnostic(panel: dict[str, Any]) -> dict[str, Any]:
    stored = panel.get("panel_sha256")
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    if stored != _canonical_hash(unsigned):
        raise H022CompositionDiagnosticError("composition diagnostic panel hash mismatch")
    records = panel.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_COMPLETE_PRIMARY:
        raise H022CompositionDiagnosticError("composition diagnostic panel row count changed")

    current_rows = [row for row in records if row["composition_group"] == "CURRENT_U001"]
    additional_rows = [
        row for row in records if row["composition_group"] == "ADDITIONAL_HISTORICAL_NIFTY200"
    ]
    additional_slope, current_slope, interaction = _composition_coefficients(records)
    composition_bootstrap = _cluster_bootstrap_composition(records)
    composition = {
        "classification": _composition_classification(additional_slope, current_slope),
        "groups": {
            "CURRENT_U001": _group_metrics(current_rows),
            "ADDITIONAL_HISTORICAL_NIFTY200": _group_metrics(additional_rows),
        },
        "standardized_h022_slope_additional_pp": additional_slope,
        "standardized_h022_slope_current_u001_pp": current_slope,
        "standardized_h022_x_current_u001_interaction_pp": interaction,
        "cluster_bootstrap": composition_bootstrap,
    }

    industry_rows = [row for row in records if row.get("industry")]
    industry_coverage = len(industry_rows) / len(records)
    industry_coefficient: float | None = None
    industry_bootstrap: dict[str, Any] | None = None
    leave_one_out: dict[str, float] = {}
    details: dict[str, Any] = {}
    if (
        industry_coverage >= MIN_INDUSTRY_COVERAGE_SHARE
        and len(industry_rows) >= MIN_INDUSTRY_ELIGIBLE
    ):
        industry_coefficient = _industry_fixed_effect_coefficient(industry_rows)
        industry_bootstrap = _cluster_bootstrap_industry(industry_rows)
        industries = sorted({str(row["industry"]) for row in industry_rows})
        for industry in industries:
            remaining = [row for row in industry_rows if row["industry"] != industry]
            leave_one_out[industry] = _industry_fixed_effect_coefficient(remaining)
            group = [row for row in industry_rows if row["industry"] == industry]
            if len(group) >= MIN_INDUSTRY_DETAIL_COUNT:
                details[industry] = _group_metrics(group)
    loo_values = list(leave_one_out.values())
    leave_one_out_min = min(loo_values) if loo_values else None
    leave_one_out_max = max(loo_values) if loo_values else None
    industry_ci_low = (
        float(industry_bootstrap["coefficient_ci_95_low_pp"])
        if industry_bootstrap is not None
        else None
    )
    industry = {
        "classification": _industry_classification(
            coverage_share=industry_coverage,
            eligible_count=len(industry_rows),
            coefficient=industry_coefficient,
            ci_low=industry_ci_low,
            leave_one_out_min=leave_one_out_min,
        ),
        "eligible_observation_count": len(industry_rows),
        "missing_industry_observation_count": len(records) - len(industry_rows),
        "industry_coverage_share": industry_coverage,
        "industry_count": len({str(row["industry"]) for row in industry_rows}),
        "standardized_h022_industry_fixed_effect_coefficient_pp": industry_coefficient,
        "cluster_bootstrap": industry_bootstrap,
        "leave_one_industry_out_coefficient_min_pp": leave_one_out_min,
        "leave_one_industry_out_coefficient_max_pp": leave_one_out_max,
        "leave_one_industry_out_coefficients_pp": leave_one_out,
        "industries_with_at_least_15_observations": details,
    }

    summary: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "evidence_class": "POST_OUTCOME_COMPOSITION_DIAGNOSTIC",
        "panel_sha256": panel["panel_sha256"],
        "record_count": len(records),
        "composition": composition,
        "industry": industry,
        "can_upgrade_h022_validation": False,
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = _canonical_hash(summary)
    return summary
