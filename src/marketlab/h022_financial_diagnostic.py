from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from typing import Any

import numpy as np

from marketlab.h022_composition_diagnostic import _canonical_hash, _group_metrics

DIAGNOSTIC_ID = "H022-D003"
HYPOTHESIS_ID = "H022"
PANEL_SHA256 = "907a88c1ed2bfddd650ec589799660f1d26aa8d4c678f787bb3b9d765a05b17a"
EXPECTED_RECORD_COUNT = 559
FINANCIAL_LABEL = "Financial Services"
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 22_025
MIN_RECOVERY_OBSERVATIONS = 100


class H022FinancialDiagnosticError(ValueError):
    """Raised when the H022 financial-composition diagnostic is invalid."""


def validate_panel(panel: dict[str, Any]) -> None:
    if panel.get("diagnostic_id") != "H022-D002" or panel.get("hypothesis_id") != HYPOTHESIS_ID:
        raise H022FinancialDiagnosticError("unexpected H022-D002 panel identity")
    if panel.get("panel_sha256") != PANEL_SHA256:
        raise H022FinancialDiagnosticError("H022-D002 panel digest changed")
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    if _canonical_hash(unsigned) != PANEL_SHA256:
        raise H022FinancialDiagnosticError("H022-D002 panel hash mismatch")
    rows = panel.get("records")
    if not isinstance(rows, list) or len(rows) != EXPECTED_RECORD_COUNT:
        raise H022FinancialDiagnosticError("H022-D002 panel row count changed")


def _zscore(values: np.ndarray) -> np.ndarray:
    std = float(np.std(values, ddof=0))
    if not math.isfinite(std) or std <= 0:
        raise H022FinancialDiagnosticError("financial diagnostic variable has zero dispersion")
    return (values - float(np.mean(values))) / std


def _additional_coefficients(rows: list[dict[str, Any]]) -> tuple[float, float, float]:
    signal = np.asarray([float(row["h022_signal"]) for row in rows], dtype=float)
    future = np.asarray([float(row["future_60d_excess_pp"]) for row in rows], dtype=float)
    financial = np.asarray(
        [1.0 if row["industry"] == FINANCIAL_LABEL else 0.0 for row in rows], dtype=float
    )
    if float(np.min(financial)) == float(np.max(financial)):
        raise H022FinancialDiagnosticError("additional sample must contain both financial cells")
    z_signal = _zscore(signal)
    design = np.column_stack(
        [np.ones(len(rows)), z_signal, financial, z_signal * financial]
    )
    coefficients, *_ = np.linalg.lstsq(design, future, rcond=None)
    nonfinancial_slope = float(coefficients[1])
    interaction = float(coefficients[3])
    financial_slope = nonfinancial_slope + interaction
    return nonfinancial_slope, financial_slope, interaction


def _bootstrap(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)
    symbols = sorted(by_symbol)
    rng = random.Random(BOOTSTRAP_SEED)
    nonfinancial: list[float] = []
    financial: list[float] = []
    interaction: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample: list[dict[str, Any]] = []
        for _symbol in symbols:
            sample.extend(by_symbol[rng.choice(symbols)])
        try:
            nonfin, fin, diff = _additional_coefficients(sample)
        except H022FinancialDiagnosticError:
            continue
        nonfinancial.append(nonfin)
        financial.append(fin)
        interaction.append(diff)
    if not nonfinancial:
        raise H022FinancialDiagnosticError("no valid financial bootstrap iterations")

    def ci(values: list[float]) -> list[float]:
        low, high = np.quantile(np.asarray(values, dtype=float), [0.025, 0.975])
        return [float(low), float(high)]

    return {
        "valid_iterations": len(nonfinancial),
        "additional_nonfinancial_slope_ci_95_pp": ci(nonfinancial),
        "additional_financial_slope_ci_95_pp": ci(financial),
        "financial_interaction_ci_95_pp": ci(interaction),
    }


def _recovery_classification(metrics: dict[str, Any]) -> str:
    if int(metrics["observation_count"]) < MIN_RECOVERY_OBSERVATIONS:
        return "INSUFFICIENT_ADDITIONAL_NONFINANCIAL_ROWS"
    spread = metrics["top_minus_bottom_mean_excess_pp"]
    median = metrics["top_quintile_median_excess_pp"]
    beat = metrics["top_quintile_benchmark_beat_rate"]
    if (
        spread is not None
        and median is not None
        and beat is not None
        and float(spread) >= 2.0
        and float(median) > 0
        and float(beat) >= 0.55
    ):
        return "RECOVERS_PROMISING_STYLE"
    return "DOES_NOT_RECOVER_PROMISING_STYLE"


def summarize_financial_composition(panel: dict[str, Any]) -> dict[str, Any]:
    validate_panel(panel)
    rows = panel["records"]
    labelled = [row for row in rows if row.get("industry")]
    current = [row for row in labelled if row["composition_group"] == "CURRENT_U001"]
    if any(row["industry"] == FINANCIAL_LABEL for row in current):
        raise H022FinancialDiagnosticError("frozen current U001 unexpectedly contains Financial Services")
    additional = [
        row
        for row in labelled
        if row["composition_group"] == "ADDITIONAL_HISTORICAL_NIFTY200"
    ]
    additional_financial = [row for row in additional if row["industry"] == FINANCIAL_LABEL]
    additional_nonfinancial = [row for row in additional if row["industry"] != FINANCIAL_LABEL]
    if not additional_financial or not additional_nonfinancial:
        raise H022FinancialDiagnosticError("additional historical sample is missing a financial cell")

    nonfin_slope, fin_slope, interaction = _additional_coefficients(additional)
    bootstrap = _bootstrap(additional)
    additional_nonfinancial_metrics = _group_metrics(additional_nonfinancial)
    summary: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "evidence_class": "POST_OUTCOME_FINANCIAL_COMPOSITION_DIAGNOSTIC",
        "input_panel_sha256": PANEL_SHA256,
        "labelled_observation_count": len(labelled),
        "excluded_null_industry_count": len(rows) - len(labelled),
        "cells": {
            "CURRENT_U001_NONFINANCIAL": _group_metrics(current),
            "ADDITIONAL_NONFINANCIAL": additional_nonfinancial_metrics,
            "ADDITIONAL_FINANCIAL": _group_metrics(additional_financial),
        },
        "additional_nonfinancial_recovery_classification": _recovery_classification(
            additional_nonfinancial_metrics
        ),
        "additional_group_regression": {
            "standardized_h022_slope_nonfinancial_pp": nonfin_slope,
            "standardized_h022_slope_financial_pp": fin_slope,
            "standardized_h022_x_financial_interaction_pp": interaction,
            "cluster_bootstrap": bootstrap,
        },
        "can_upgrade_h022_validation": False,
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = _canonical_hash(summary)
    return summary
