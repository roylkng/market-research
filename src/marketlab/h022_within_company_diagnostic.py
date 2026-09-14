from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Any

import numpy as np
from scipy import stats

from marketlab.h022_dependence_diagnostic import nonoverlapping_event_rows

DIAGNOSTIC_ID = "H022-D005"
HYPOTHESIS_ID = "H022"
INPUT_DIAGNOSTIC_ID = "H022-D004"
INPUT_PANEL_SHA256 = "e776474d6406cc40aedf0c3ce10d7caf87c2b0e86bc6af99d5df717d5980fcab"
EXPECTED_ROWS = 559
MIN_FULL_SYMBOLS = 100
MIN_FULL_ROWS = 300
MIN_NONOVERLAP_SYMBOLS = 70
MIN_NONOVERLAP_ROWS = 180
MIN_PAIRS = 100
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 22_027


class H022WithinCompanyDiagnosticError(ValueError):
    """Raised when H022-D005 cannot be reproduced under its frozen contract."""


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
        raise H022WithinCompanyDiagnosticError(
            "H022-D005 payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def validate_input_panel(panel: dict[str, Any]) -> list[dict[str, Any]]:
    if panel.get("diagnostic_id") != INPUT_DIAGNOSTIC_ID:
        raise H022WithinCompanyDiagnosticError("unexpected D004 diagnostic id")
    if panel.get("panel_sha256") != INPUT_PANEL_SHA256:
        raise H022WithinCompanyDiagnosticError("D004 panel digest changed")
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    if _canonical_hash(unsigned) != INPUT_PANEL_SHA256:
        raise H022WithinCompanyDiagnosticError("D004 panel hash mismatch")
    records = panel.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_ROWS:
        raise H022WithinCompanyDiagnosticError("D004 panel row count changed")
    if not all(isinstance(row, dict) for row in records):
        raise H022WithinCompanyDiagnosticError("D004 panel record must be an object")
    return [dict(row) for row in records]


def _standardize_signal(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float, float]:
    signal = np.asarray([float(row["h022_signal"]) for row in rows], dtype=float)
    mean = float(np.mean(signal))
    std = float(np.std(signal, ddof=0))
    if not math.isfinite(mean) or not math.isfinite(std) or std <= 0:
        raise H022WithinCompanyDiagnosticError("H022 signal dispersion is invalid")
    result: list[dict[str, Any]] = []
    for row in rows:
        tagged = dict(row)
        tagged["z_h022"] = (float(row["h022_signal"]) - mean) / std
        result.append(tagged)
    return result, mean, std


def _eligible_multi_event_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(row["symbol"]) for row in rows)
    return [dict(row) for row in rows if counts[str(row["symbol"])] >= 2]


def _within_values(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    if not rows:
        raise H022WithinCompanyDiagnosticError("within-company estimator has no rows")
    group_key = "_bootstrap_cluster_id" if "_bootstrap_cluster_id" in rows[0] else "symbol"
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_group[str(row[group_key])].append(row)

    centered_signal: list[float] = []
    centered_future: list[float] = []
    for group_rows in by_group.values():
        if len(group_rows) < 2:
            continue
        signal_mean = statistics.fmean(float(row["z_h022"]) for row in group_rows)
        future_mean = statistics.fmean(
            float(row["future_60d_excess_pp"]) for row in group_rows
        )
        for row in group_rows:
            centered_signal.append(float(row["z_h022"]) - signal_mean)
            centered_future.append(float(row["future_60d_excess_pp"]) - future_mean)

    if len(centered_signal) < 3:
        raise H022WithinCompanyDiagnosticError("within-company estimator has too few rows")
    x = np.asarray(centered_signal, dtype=float)
    y = np.asarray(centered_future, dtype=float)
    if float(np.dot(x, x)) <= 0:
        raise H022WithinCompanyDiagnosticError("within-company signal has zero dispersion")
    return x, y


def _within_slope(rows: list[dict[str, Any]]) -> float:
    x, y = _within_values(rows)
    return float(np.dot(x, y) / np.dot(x, x))


def _within_spearman(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    x, y = _within_values(rows)
    if float(np.std(x, ddof=0)) <= 0 or float(np.std(y, ddof=0)) <= 0:
        return {"rho": None, "p_value": None}
    rho, p_value = stats.spearmanr(x, y)
    return {"rho": float(rho), "p_value": float(p_value)}


Estimator = Callable[[list[dict[str, Any]]], float]


def _cluster_bootstrap_ci(
    rows: list[dict[str, Any]], *, estimator: Estimator, seed_offset: int
) -> dict[str, Any]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)
    symbols = sorted(by_symbol)
    if len(symbols) < 2:
        raise H022WithinCompanyDiagnosticError("bootstrap requires multiple companies")
    rng = random.Random(BOOTSTRAP_SEED + seed_offset)
    estimates: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample: list[dict[str, Any]] = []
        for draw_index, _symbol in enumerate(symbols):
            chosen = rng.choice(symbols)
            for original in by_symbol[chosen]:
                copied = dict(original)
                copied["_bootstrap_cluster_id"] = f"{draw_index}:{chosen}"
                sample.append(copied)
        try:
            estimate = estimator(sample)
        except H022WithinCompanyDiagnosticError:
            continue
        if math.isfinite(estimate):
            estimates.append(estimate)
    if not estimates:
        raise H022WithinCompanyDiagnosticError("no valid within-company bootstrap iterations")
    low, high = np.quantile(np.asarray(estimates, dtype=float), [0.025, 0.975])
    return {
        "valid_iterations": len(estimates),
        "ci_95_low_pp": float(low),
        "ci_95_high_pp": float(high),
    }


def highest_lowest_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)

    pairs: list[dict[str, Any]] = []
    for symbol in sorted(by_symbol):
        group = by_symbol[symbol]
        if len(group) < 2:
            continue
        low = min(group, key=lambda row: (float(row["h022_signal"]), str(row["source_id"])))
        high = min(group, key=lambda row: (-float(row["h022_signal"]), str(row["source_id"])))
        low_signal = float(low["h022_signal"])
        high_signal = float(high["h022_signal"])
        if high_signal <= low_signal:
            continue
        difference = float(high["future_60d_excess_pp"]) - float(low["future_60d_excess_pp"])
        pairs.append(
            {
                "symbol": symbol,
                "low_source_id": str(low["source_id"]),
                "high_source_id": str(high["source_id"]),
                "low_h022_signal": low_signal,
                "high_h022_signal": high_signal,
                "low_future_60d_excess_pp": float(low["future_60d_excess_pp"]),
                "high_future_60d_excess_pp": float(high["future_60d_excess_pp"]),
                "high_minus_low_future_excess_pp": difference,
            }
        )
    return pairs


def _pair_bootstrap_ci(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    if len(pairs) < 2:
        raise H022WithinCompanyDiagnosticError("paired bootstrap requires multiple companies")
    values = [float(row["high_minus_low_future_excess_pp"]) for row in pairs]
    rng = random.Random(BOOTSTRAP_SEED + 2)
    means: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample = [rng.choice(values) for _value in values]
        means.append(statistics.fmean(sample))
    low, high = np.quantile(np.asarray(means, dtype=float), [0.025, 0.975])
    return {
        "valid_iterations": len(means),
        "ci_95_low_pp": float(low),
        "ci_95_high_pp": float(high),
    }


def _within_block(rows: list[dict[str, Any]], *, seed_offset: int) -> dict[str, Any]:
    slope = _within_slope(rows)
    return {
        "observation_count": len(rows),
        "symbol_count": len({str(row["symbol"]) for row in rows}),
        "standardized_h022_within_slope_pp": slope,
        "within_spearman": _within_spearman(rows),
        "bootstrap": _cluster_bootstrap_ci(
            rows,
            estimator=_within_slope,
            seed_offset=seed_offset,
        ),
    }


def summarize_within_company(panel: dict[str, Any]) -> dict[str, Any]:
    raw_rows = validate_input_panel(panel)
    standardized, signal_mean, signal_std = _standardize_signal(raw_rows)

    full_rows = _eligible_multi_event_rows(standardized)
    nonoverlap_all = nonoverlapping_event_rows(standardized)
    nonoverlap_rows = _eligible_multi_event_rows(nonoverlap_all)
    pairs = highest_lowest_pairs(standardized)

    full = _within_block(full_rows, seed_offset=0)
    nonoverlap = _within_block(nonoverlap_rows, seed_offset=1)

    pair_values = [float(row["high_minus_low_future_excess_pp"]) for row in pairs]
    pair_mean = statistics.fmean(pair_values) if pair_values else None
    pair_median = statistics.median(pair_values) if pair_values else None
    pair_positive_share = (
        sum(value > 0 for value in pair_values) / len(pair_values) if pair_values else None
    )
    paired = {
        "pair_count": len(pairs),
        "mean_high_minus_low_excess_pp": pair_mean,
        "median_high_minus_low_excess_pp": pair_median,
        "positive_pair_share": pair_positive_share,
        "bootstrap": _pair_bootstrap_ci(pairs),
    }

    insufficient = (
        int(full["symbol_count"]) < MIN_FULL_SYMBOLS
        or int(full["observation_count"]) < MIN_FULL_ROWS
        or int(nonoverlap["symbol_count"]) < MIN_NONOVERLAP_SYMBOLS
        or int(nonoverlap["observation_count"]) < MIN_NONOVERLAP_ROWS
        or len(pairs) < MIN_PAIRS
    )
    full_slope = float(full["standardized_h022_within_slope_pp"])
    nonoverlap_slope = float(nonoverlap["standardized_h022_within_slope_pp"])
    if pair_mean is None:
        raise H022WithinCompanyDiagnosticError("paired comparison is empty")

    if insufficient:
        sign_classification = "DATA_INSUFFICIENT"
    elif full_slope > 0 and nonoverlap_slope > 0 and pair_mean > 0:
        sign_classification = "WITHIN_POSITIVE"
    else:
        sign_classification = "WITHIN_SIGN_UNSTABLE"

    ci_lows = [
        float(full["bootstrap"]["ci_95_low_pp"]),
        float(nonoverlap["bootstrap"]["ci_95_low_pp"]),
        float(paired["bootstrap"]["ci_95_low_pp"]),
    ]
    bootstrap_support = (
        "ALL_INTERVALS_POSITIVE"
        if all(value > 0 for value in ci_lows)
        else "MIXED_OR_UNCERTAIN"
    )

    summary: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "evidence_class": "POST_OUTCOME_WITHIN_COMPANY_DIAGNOSTIC",
        "input_panel_sha256": INPUT_PANEL_SHA256,
        "record_count": len(standardized),
        "all_symbol_count": len({str(row["symbol"]) for row in standardized}),
        "signal_standardization": {
            "mean": signal_mean,
            "population_std": signal_std,
        },
        "company_fixed_effect": full,
        "nonoverlap_company_fixed_effect": {
            **nonoverlap,
            "nonoverlap_all_observation_count": len(nonoverlap_all),
        },
        "highest_vs_lowest_signal_pair": paired,
        "sign_classification": sign_classification,
        "bootstrap_support": bootstrap_support,
        "can_upgrade_h022_validation": False,
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = _canonical_hash(summary)
    return summary
