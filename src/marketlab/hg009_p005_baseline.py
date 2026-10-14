"""HG009 P005: source-only confounder audit for all 300 frozen research arms.

Use the same immutable Oct 5 HG001 source that defined selected100 and both
control100 arms. The experiment is not randomized, matched on industry/size,
or an alpha evaluation. Prior known earnings differences are disclosed before
any October 15 onward price labels are opened.
"""

from __future__ import annotations

import copy
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_controls import (
    load_hg009_inputs,
    verify_hg009_controls,
)
from marketlab.hg009_p003_accounting import _flags

REPORT_ID = "HG009-P005-2026-10-14-PREENTRY-300-SOURCE-BASELINE-v1"
FROZEN_SOURCE_DATE = "2026-10-05"
REVIEW_DATE = "2026-10-14"
SELECTED_SHA = (
    "e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5"
)
CONTROL_SHA = (
    "8c8d9781adf7900addd28a1a60f1cfb33bed9a1e4985e6c410a010d2c819eef8"
)
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
METRICS = (
    "revenue_yoy_pct",
    "basic_eps_yoy_pct",
    "pat_yoy_pct",
    "pbt_margin_delta_pp",
    "current_pbt_margin_pct",
    "finance_cost_yoy_pct",
)
SOURCE_CONTROL = Path(
    "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
)


def _numerical(value: Any, *, label: str) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise AlphaContractError(f"HG009 P005 nonfinite source number: {label}")
    return float(value)


def _summary(values: list[float | None]) -> dict[str, Any]:
    valid = sorted(x for x in values if x is not None)
    missing = len(values) - len(valid)
    if len(values) != 100 or missing < 0:
        raise AlphaContractError("HG009 P005 fixed cohort denominator must be 100")
    result = {
        "source_population_count": 100,
        "observed_count": len(valid),
        "missing_count": missing,
        "median_if_observed": (
            round(statistics.median(valid), 4) if valid else None
        ),
        "mean_if_observed": (
            round(statistics.fmean(valid), 4) if valid else None
        ),
        "minimum_if_observed": round(valid[0], 4) if valid else None,
        "maximum_if_observed": round(valid[-1], 4) if valid else None,
    }
    return result


def build_hg009_source_baseline(
    *,
    source: dict[str, Any],
    selected: dict[str, Any],
    controls: dict[str, Any],
) -> dict[str, Any]:
    verify_hg009_controls(controls, source=source, selected=selected)
    if (
        selected.get("cohort_sha256") != SELECTED_SHA
        or controls.get("manifest_sha256") != CONTROL_SHA
    ):
        raise AlphaContractError("HG009 P005 frozen 300 company original SHA drift")
    source_rows = {
        (item["symbol"], item["isin"]): item for item in source["rows"]
    }
    if len(source_rows) != 2319:
        raise AlphaContractError("HG009 P005 original source rows not unique")
    arms = {
        "SELECTED": selected["selected"],
        "ONE_LANE": controls["controls"]["ONE_LANE"],
        "ZERO_LANE": controls["controls"]["ZERO_LANE"],
    }
    output_arms: dict[str, dict[str, Any]] = {}
    exposure_rows: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for arm in ARMS:
        rows = arms[arm]
        if len(rows) != 100:
            raise AlphaContractError("HG009 P005 source arm size changed")
        metrics = {key: [] for key in METRICS}
        turnover = []
        promoter = []
        lanes = Counter()
        flags = Counter()
        band_counts = Counter()
        earnings_states = Counter()
        for identity in rows:
            key = (identity["symbol"], identity["isin"])
            if key in identities:
                raise AlphaContractError("HG009 P005 duplicate symbol+ISIN identity")
            identities.add(key)
            original = source_rows.get(key)
            if original is None:
                raise AlphaContractError("HG009 P005 source identity disappeared")
            source_hash = digest(original)
            if source_hash != identity.get(
                "full_frozen_router_row_sha256",
                identity.get("original_hg001_row_sha256"),
            ):
                raise AlphaContractError("HG009 P005 source row hash discrepancy")
            if original.get("liquidity_band") != identity.get(
                "source_liquidity_band"
            ):
                raise AlphaContractError("HG009 P005 frozen liquidity band drift")
            if original.get("in_existing_u001") is not False:
                raise AlphaContractError("HG009 P005 controls include U001 member")
            for name in METRICS:
                amount = _numerical(
                    original["earnings_metrics"].get(name),
                    label=f"{identity['symbol']} {name}",
                )
                metrics[name].append(amount)
            turnover.append(
                _numerical(
                    original["median_daily_turnover_inr"],
                    label=f"{identity['symbol']} turnover",
                )
            )
            promoter.append(
                _numerical(
                    original.get("promoter_percentage"),
                    label=f"{identity['symbol']} promoter",
                )
            )
            band_counts[original["liquidity_band"]] += 1
            earnings_states[original["earnings_inflection_state"]] += 1
            lanes[original["active_opportunity_lane_count"]] += 1
            observed_flags = _flags(original)
            flags.update(observed_flags)
            exposure_rows.append({
                "arm": arm,
                "symbol": original["symbol"],
                "isin": original["isin"],
                "original_hg001_row_sha256": source_hash,
                "original_opportunity_lane_count": original[
                    "active_opportunity_lane_count"
                ],
                "original_liquidity_band": original["liquidity_band"],
                "original_earnings_metrics": copy.deepcopy(
                    original["earnings_metrics"]
                ),
                "original_earnings_review_flags": observed_flags,
                "original_promotion_or_index_membership": False,
                "price_return_opened": False,
                "trading_capacity_verified": False,
            })
        if len(turnover) != 100 or any(x is None for x in turnover):
            raise AlphaContractError("HG009 P005 original turnover missing")
        output_arms[arm] = {
            "original_source_count": 100,
            "liquidity_band_counts": dict(sorted(band_counts.items())),
            "opportunity_lane_count_distribution": {
                str(k): v for k, v in sorted(lanes.items())
            },
            "earnings_inflection_state_counts": dict(
                sorted(earnings_states.items())
            ),
            "earnings_document_flag_counts_overlapping": dict(
                sorted(flags.items())
            ),
            "frozen_turnover_inr": _summary(turnover),
            "promoter_percentage": _summary(promoter),
            "earnings_metrics": {
                name: _summary(metrics[name]) for name in METRICS
            },
        }
    if len(identities) != 300 or len(exposure_rows) != 300:
        raise AlphaContractError("HG009 P005 must preserve 300 original identities")
    base_bands = output_arms["SELECTED"]["liquidity_band_counts"]
    if any(output_arms[arm]["liquidity_band_counts"] != base_bands for arm in ARMS):
        raise AlphaContractError("HG009 P005 source bands not matched")
    exposure_rows.sort(key=lambda r: (r["arm"], r["symbol"], r["isin"]))
    result: dict[str, Any] = {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "classification": "PREENTRY_OBSERVATIONAL_CONFOUNDER_BASELINE_NOT_ALPHA",
        "method_review_date": REVIEW_DATE,
        "data_source_snapshot_date": FROZEN_SOURCE_DATE,
        "selected_manifest_sha256": SELECTED_SHA,
        "controls_manifest_sha256": CONTROL_SHA,
        "source_population_size": 2319,
        "unique_frozen_identity_count": 300,
        "arms": output_arms,
        "source_identity_metric_rows": exposure_rows,
        "liquidity_band_only_matching": True,
        "industry_matching_complete": False,
        "financial_vs_industrial_comparable_normalization_complete": False,
        "size_enterprise_value_matching_complete": False,
        "source_diagnostics_are_not_return_predictors": True,
        "arbitrary_review_flags_not_statistically_calibrated": True,
        "first_entry_after_freeze": "2026-10-15",
        "future_market_returns_observed": False,
        "causal_alpha_demonstrated": False,
        "investment_recommendations_generated": False,
        "live_capital_allowed": False,
    }
    result["packet_sha256"] = digest(result)
    return result


def materialize_hg009_source_baseline(root: Path) -> dict[str, Any]:
    source, selected = load_hg009_inputs(root)
    controls = json.loads((root / SOURCE_CONTROL).read_text(encoding="utf-8"))
    return build_hg009_source_baseline(
        source=source, selected=selected, controls=controls
    )


def validate_hg009_source_baseline(
    result: dict[str, Any],
    *,
    source: dict[str, Any],
    selected: dict[str, Any],
    controls: dict[str, Any],
) -> None:
    unsigned = copy.deepcopy(result)
    recorded = unsigned.pop("packet_sha256", None)
    if recorded != digest(unsigned):
        raise AlphaContractError("HG009 P005 tampered source baseline packet")
    expected = build_hg009_source_baseline(
        source=source, selected=selected, controls=controls
    )
    if expected != result:
        raise AlphaContractError("HG009 P005 original source baseline unreproducible")
