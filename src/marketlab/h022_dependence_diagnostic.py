from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any, Callable

import numpy as np
from scipy import stats

DIAGNOSTIC_ID = "H022-D004"
HYPOTHESIS_ID = "H022"
EXECUTION_RULE_ID = "H022-X001"
OUTCOME_REPORT_SHA256 = "310d3709393047db4ec5e2eacb9d333fac2d81b83e86bc65140dc4bc60c6d22f"
EXPECTED_COMPLETE_ROWS = 559
PRIMARY_HORIZON = "60"
MIN_REDUCED_ROWS = 150
MIN_PUBLICATION_MONTHS = 8
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 22_026


class H022DependenceDiagnosticError(ValueError):
    """Raised when the frozen H022 dependence diagnostic cannot be reproduced."""


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
        raise H022DependenceDiagnosticError(
            "H022 dependence payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _validate_outcome_report(report: dict[str, Any]) -> None:
    if report.get("hypothesis_id") != HYPOTHESIS_ID:
        raise H022DependenceDiagnosticError("unexpected H022 hypothesis id")
    if report.get("execution_rule_id") != EXECUTION_RULE_ID:
        raise H022DependenceDiagnosticError("unexpected H022 execution rule")
    if report.get("report_sha256") != OUTCOME_REPORT_SHA256:
        raise H022DependenceDiagnosticError("expanded H022 outcome digest changed")
    unsigned = dict(report)
    unsigned.pop("report_sha256", None)
    if _canonical_hash(unsigned) != OUTCOME_REPORT_SHA256:
        raise H022DependenceDiagnosticError("expanded H022 outcome hash mismatch")


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise H022DependenceDiagnosticError("publication timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise H022DependenceDiagnosticError(
            f"invalid publication timestamp: {value}"
        ) from exc
    if parsed.tzinfo is None:
        raise H022DependenceDiagnosticError("publication timestamp must be timezone-aware")
    return parsed


def _session_date(payload: object, *, label: str) -> str:
    if not isinstance(payload, dict):
        raise H022DependenceDiagnosticError(f"{label} session is missing")
    raw = payload.get("session_date")
    if not isinstance(raw, str):
        raise H022DependenceDiagnosticError(f"{label} session date is missing")
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError as exc:
        raise H022DependenceDiagnosticError(
            f"invalid {label} session date: {raw}"
        ) from exc


def build_dependence_panel(report: dict[str, Any]) -> dict[str, Any]:
    _validate_outcome_report(report)
    outcome_records = report.get("records")
    if not isinstance(outcome_records, list):
        raise H022DependenceDiagnosticError("expanded H022 records must be a list")

    records: list[dict[str, Any]] = []
    for row in outcome_records:
        if not isinstance(row, dict):
            raise H022DependenceDiagnosticError("expanded H022 row must be an object")
        horizons = row.get("horizons")
        if not isinstance(horizons, dict):
            raise H022DependenceDiagnosticError("expanded H022 horizon map is missing")
        horizon = horizons.get(PRIMARY_HORIZON)
        if not isinstance(horizon, dict) or horizon.get("status") != "COMPLETE":
            continue
        publication = _parse_timestamp(row.get("exchange_published_at_utc"))
        source_id = str(row.get("source_id") or "").strip()
        symbol = str(row.get("symbol") or "").strip().upper()
        if not source_id or not symbol:
            raise H022DependenceDiagnosticError("complete row identity is missing")
        signal = float(row["primary_signal"])
        future = float(horizon["gross_excess_pp"])
        if not math.isfinite(signal) or not math.isfinite(future):
            raise H022DependenceDiagnosticError("complete row has non-finite values")
        entry_date = _session_date(row.get("entry_session"), label="entry")
        exit_date = _session_date(horizon.get("exit_session"), label="exit")
        if date.fromisoformat(exit_date) < date.fromisoformat(entry_date):
            raise H022DependenceDiagnosticError("60-session exit precedes entry")
        records.append(
            {
                "source_id": source_id,
                "symbol": symbol,
                "exchange_published_at_utc": publication.isoformat(),
                "publication_month": publication.date().isoformat()[:7],
                "entry_session_date": entry_date,
                "exit_session_date": exit_date,
                "h022_signal": signal,
                "future_60d_excess_pp": future,
            }
        )

    if len(records) != EXPECTED_COMPLETE_ROWS:
        raise H022DependenceDiagnosticError(
            f"expected {EXPECTED_COMPLETE_ROWS} complete rows, found {len(records)}"
        )
    records.sort(
        key=lambda row: (
            str(row["exchange_published_at_utc"]),
            str(row["symbol"]),
            str(row["source_id"]),
        )
    )
    source_ids = [str(row["source_id"]) for row in records]
    if len(source_ids) != len(set(source_ids)):
        raise H022DependenceDiagnosticError("duplicate complete source_id")

    panel: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "evidence_class": "POST_OUTCOME_DEPENDENCE_DIAGNOSTIC",
        "outcome_report_sha256": OUTCOME_REPORT_SHA256,
        "primary_horizon_sessions": 60,
        "record_count": len(records),
        "records": records,
    }
    panel["panel_sha256"] = _canonical_hash(panel)
    return panel


def _global_standardization(rows: list[dict[str, Any]]) -> tuple[float, float]:
    values = np.asarray([float(row["h022_signal"]) for row in rows], dtype=float)
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=0))
    if not math.isfinite(mean) or not math.isfinite(std) or std <= 0:
        raise H022DependenceDiagnosticError("H022 signal has zero/non-finite dispersion")
    return mean, std


def _with_zsignal(
    rows: list[dict[str, Any]], *, mean: float, std: float
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        tagged = dict(row)
        tagged["z_h022"] = (float(row["h022_signal"]) - mean) / std
        result.append(tagged)
    return result


def _ols_slope(rows: list[dict[str, Any]]) -> float:
    if len(rows) < 3:
        raise H022DependenceDiagnosticError("OLS requires at least three rows")
    z_signal = np.asarray([float(row["z_h022"]) for row in rows], dtype=float)
    future = np.asarray([float(row["future_60d_excess_pp"]) for row in rows], dtype=float)
    if float(np.std(z_signal, ddof=0)) <= 0:
        raise H022DependenceDiagnosticError("OLS signal has zero dispersion")
    design = np.column_stack([np.ones(len(rows)), z_signal])
    coefficients, *_ = np.linalg.lstsq(design, future, rcond=None)
    return float(coefficients[1])


def _company_balanced_slope(rows: list[dict[str, Any]]) -> float:
    if len(rows) < 3:
        raise H022DependenceDiagnosticError("company-balanced OLS requires rows")
    cluster_key = "_bootstrap_cluster_id" if "_bootstrap_cluster_id" in rows[0] else "symbol"
    counts = Counter(str(row[cluster_key]) for row in rows)
    weights = np.asarray(
        [1.0 / counts[str(row[cluster_key])] for row in rows], dtype=float
    )
    z_signal = np.asarray([float(row["z_h022"]) for row in rows], dtype=float)
    future = np.asarray([float(row["future_60d_excess_pp"]) for row in rows], dtype=float)
    design = np.column_stack([np.ones(len(rows)), z_signal])
    root_weights = np.sqrt(weights)
    weighted_design = design * root_weights[:, None]
    weighted_future = future * root_weights
    coefficients, *_ = np.linalg.lstsq(weighted_design, weighted_future, rcond=None)
    return float(coefficients[1])


def _month_fixed_effect_slope(rows: list[dict[str, Any]]) -> float:
    if len(rows) < 3:
        raise H022DependenceDiagnosticError("month fixed-effect OLS requires rows")
    months = sorted({str(row["publication_month"]) for row in rows})
    z_signal = np.asarray([float(row["z_h022"]) for row in rows], dtype=float)
    future = np.asarray([float(row["future_60d_excess_pp"]) for row in rows], dtype=float)
    columns: list[np.ndarray] = [np.ones(len(rows)), z_signal]
    for month in months[1:]:
        columns.append(
            np.asarray(
                [1.0 if str(row["publication_month"]) == month else 0.0 for row in rows],
                dtype=float,
            )
        )
    design = np.column_stack(columns)
    coefficients, *_ = np.linalg.lstsq(design, future, rcond=None)
    return float(coefficients[1])


def first_complete_event_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    first: dict[str, dict[str, Any]] = {}
    for row in sorted(
        rows,
        key=lambda item: (
            str(item["exchange_published_at_utc"]),
            str(item["source_id"]),
        ),
    ):
        first.setdefault(str(row["symbol"]), row)
    return sorted(
        (dict(row) for row in first.values()),
        key=lambda row: (str(row["exchange_published_at_utc"]), str(row["source_id"])),
    )


def nonoverlapping_event_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)

    kept: list[dict[str, Any]] = []
    for symbol in sorted(by_symbol):
        ordered = sorted(
            by_symbol[symbol],
            key=lambda row: (str(row["entry_session_date"]), str(row["source_id"])),
        )
        last_exit: date | None = None
        for row in ordered:
            entry = date.fromisoformat(str(row["entry_session_date"]))
            exit_day = date.fromisoformat(str(row["exit_session_date"]))
            if last_exit is None or entry > last_exit:
                kept.append(dict(row))
                last_exit = exit_day
    kept.sort(
        key=lambda row: (str(row["entry_session_date"]), str(row["symbol"]), str(row["source_id"]))
    )
    return kept


def _spearman(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    if len(rows) < 3:
        return {"rho": None, "p_value": None}
    signal = np.asarray([float(row["h022_signal"]) for row in rows], dtype=float)
    future = np.asarray([float(row["future_60d_excess_pp"]) for row in rows], dtype=float)
    if float(np.std(signal, ddof=0)) <= 0 or float(np.std(future, ddof=0)) <= 0:
        return {"rho": None, "p_value": None}
    rho, p_value = stats.spearmanr(signal, future)
    return {"rho": float(rho), "p_value": float(p_value)}


def _quintile_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) < 10:
        raise H022DependenceDiagnosticError("quintile diagnostic requires at least 10 rows")
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
        "top_quintile_count": len(top_values),
        "bottom_quintile_count": len(bottom_values),
        "top_quintile_mean_excess_pp": top_mean,
        "bottom_quintile_mean_excess_pp": bottom_mean,
        "top_minus_bottom_mean_excess_pp": top_mean - bottom_mean,
        "top_quintile_median_excess_pp": statistics.median(top_values),
        "top_quintile_benchmark_beat_rate": (
            sum(value > 0 for value in top_values) / len(top_values)
        ),
    }


def _reduced_sample_metrics(rows: list[dict[str, Any]], slope: float) -> dict[str, Any]:
    rank = _spearman(rows)
    result: dict[str, Any] = {
        "observation_count": len(rows),
        "symbol_count": len({str(row["symbol"]) for row in rows}),
        "standardized_h022_slope_pp": slope,
        "spearman_signal_vs_future_excess": rank["rho"],
        "spearman_p_value": rank["p_value"],
    }
    result.update(_quintile_metrics(rows))
    return result


Estimator = Callable[[list[dict[str, Any]]], float]


def _cluster_bootstrap_ci(
    rows: list[dict[str, Any]],
    *,
    estimator: Estimator,
    seed_offset: int,
    company_balanced: bool = False,
) -> dict[str, Any]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)
    symbols = sorted(by_symbol)
    if len(symbols) < 2:
        raise H022DependenceDiagnosticError("bootstrap requires at least two symbols")
    rng = random.Random(BOOTSTRAP_SEED + seed_offset)
    estimates: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample: list[dict[str, Any]] = []
        for draw_index, _symbol in enumerate(symbols):
            chosen = rng.choice(symbols)
            for original in by_symbol[chosen]:
                copied = dict(original)
                if company_balanced:
                    copied["_bootstrap_cluster_id"] = f"{draw_index}:{chosen}"
                sample.append(copied)
        try:
            estimate = estimator(sample)
        except (H022DependenceDiagnosticError, np.linalg.LinAlgError):
            continue
        if math.isfinite(estimate):
            estimates.append(estimate)
    if not estimates:
        raise H022DependenceDiagnosticError("no valid bootstrap iterations")
    low, high = np.quantile(np.asarray(estimates, dtype=float), [0.025, 0.975])
    return {
        "valid_iterations": len(estimates),
        "ci_95_low_pp": float(low),
        "ci_95_high_pp": float(high),
    }


def _validate_panel(panel: dict[str, Any]) -> list[dict[str, Any]]:
    if panel.get("diagnostic_id") != DIAGNOSTIC_ID:
        raise H022DependenceDiagnosticError("unexpected dependence diagnostic id")
    if panel.get("outcome_report_sha256") != OUTCOME_REPORT_SHA256:
        raise H022DependenceDiagnosticError("dependence panel input digest changed")
    stored = panel.get("panel_sha256")
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    if stored != _canonical_hash(unsigned):
        raise H022DependenceDiagnosticError("dependence panel hash mismatch")
    records = panel.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_COMPLETE_ROWS:
        raise H022DependenceDiagnosticError("dependence panel row count changed")
    if not all(isinstance(row, dict) for row in records):
        raise H022DependenceDiagnosticError("dependence panel record must be an object")
    return records


def summarize_dependence(panel: dict[str, Any]) -> dict[str, Any]:
    raw_records = _validate_panel(panel)
    records = [dict(row) for row in raw_records]
    signal_mean, signal_std = _global_standardization(records)
    standardized = _with_zsignal(records, mean=signal_mean, std=signal_std)

    first_rows = first_complete_event_rows(standardized)
    nonoverlap_rows = nonoverlapping_event_rows(standardized)
    month_count = len({str(row["publication_month"]) for row in standardized})
    symbol_count = len({str(row["symbol"]) for row in standardized})
    event_counts = Counter(str(row["symbol"]) for row in standardized)

    event_slope = _ols_slope(standardized)
    company_slope = _company_balanced_slope(standardized)
    first_slope = _ols_slope(first_rows)
    nonoverlap_slope = _ols_slope(nonoverlap_rows)
    month_slope = _month_fixed_effect_slope(standardized)

    insufficient = (
        len(first_rows) < MIN_REDUCED_ROWS
        or len(nonoverlap_rows) < MIN_REDUCED_ROWS
        or month_count < MIN_PUBLICATION_MONTHS
    )
    control_slopes = {
        "company_balanced": company_slope,
        "first_event_per_symbol": first_slope,
        "nonoverlapping_events": nonoverlap_slope,
        "publication_month_fixed_effects": month_slope,
    }
    sensitivity_flags: list[str] = []
    if company_slope <= 0 or first_slope <= 0:
        sensitivity_flags.append("REPEATED_COMPANY")
    if nonoverlap_slope <= 0:
        sensitivity_flags.append("OVERLAP")
    if month_slope <= 0:
        sensitivity_flags.append("CALENDAR_MONTH")

    if insufficient:
        sign_classification = "DATA_INSUFFICIENT"
    elif sensitivity_flags:
        sign_classification = "SIGN_UNSTABLE"
    else:
        sign_classification = "BROAD_POSITIVE"

    bootstraps = {
        "company_balanced": _cluster_bootstrap_ci(
            standardized,
            estimator=_company_balanced_slope,
            seed_offset=0,
            company_balanced=True,
        ),
        "first_event_per_symbol": _cluster_bootstrap_ci(
            first_rows,
            estimator=_ols_slope,
            seed_offset=1,
        ),
        "nonoverlapping_events": _cluster_bootstrap_ci(
            nonoverlap_rows,
            estimator=_ols_slope,
            seed_offset=2,
        ),
        "publication_month_fixed_effects": _cluster_bootstrap_ci(
            standardized,
            estimator=_month_fixed_effect_slope,
            seed_offset=3,
        ),
    }
    all_intervals_positive = all(
        float(result["ci_95_low_pp"]) > 0 for result in bootstraps.values()
    )
    bootstrap_support = (
        "ALL_INTERVALS_POSITIVE" if all_intervals_positive else "MIXED_OR_UNCERTAIN"
    )

    summary: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "evidence_class": "POST_OUTCOME_DEPENDENCE_DIAGNOSTIC",
        "panel_sha256": panel["panel_sha256"],
        "record_count": len(standardized),
        "symbol_count": symbol_count,
        "publication_month_count": month_count,
        "signal_standardization": {
            "mean": signal_mean,
            "population_std": signal_std,
        },
        "repetition": {
            "mean_complete_events_per_symbol": len(standardized) / symbol_count,
            "median_complete_events_per_symbol": statistics.median(event_counts.values()),
            "max_complete_events_per_symbol": max(event_counts.values()),
        },
        "event_level_baseline": {
            "standardized_h022_slope_pp": event_slope,
            "spearman": _spearman(standardized),
        },
        "company_balanced": {
            "standardized_h022_slope_pp": company_slope,
            "bootstrap": bootstraps["company_balanced"],
        },
        "first_event_per_symbol": {
            **_reduced_sample_metrics(first_rows, first_slope),
            "bootstrap": bootstraps["first_event_per_symbol"],
        },
        "nonoverlapping_events": {
            **_reduced_sample_metrics(nonoverlap_rows, nonoverlap_slope),
            "removed_overlap_row_count": len(standardized) - len(nonoverlap_rows),
            "bootstrap": bootstraps["nonoverlapping_events"],
        },
        "publication_month_fixed_effects": {
            "distinct_month_count": month_count,
            "standardized_h022_slope_pp": month_slope,
            "bootstrap": bootstraps["publication_month_fixed_effects"],
        },
        "control_slopes_pp": control_slopes,
        "sign_classification": sign_classification,
        "bootstrap_support": bootstrap_support,
        "sensitivity_flags": sensitivity_flags,
        "can_upgrade_h022_validation": False,
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = _canonical_hash(summary)
    return summary
