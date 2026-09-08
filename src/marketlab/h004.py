from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


PRIMARY_TRADED_VALUE_MIN = 20_000_000.0
DISCOVERY_TRADED_VALUE_MIN = 2_500_000.0


@dataclass(frozen=True)
class H004Evaluation:
    stage1_eligible: bool
    primary_universe: bool
    discovery_universe: bool
    pre_momentum_eligible: bool
    anchors: tuple[str, ...]
    quality_warnings: tuple[str, ...]
    hard_reject_reasons: tuple[str, ...]
    speculative_base_effect: bool
    expectation_gap: bool
    watch_points: int
    stage2_trigger: bool
    trigger_conditions: tuple[str, ...]
    not_executable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage1_eligible": self.stage1_eligible,
            "primary_universe": self.primary_universe,
            "discovery_universe": self.discovery_universe,
            "pre_momentum_eligible": self.pre_momentum_eligible,
            "anchors": list(self.anchors),
            "quality_warnings": list(self.quality_warnings),
            "hard_reject_reasons": list(self.hard_reject_reasons),
            "speculative_base_effect": self.speculative_base_effect,
            "expectation_gap": self.expectation_gap,
            "watch_points": self.watch_points,
            "stage2_trigger": self.stage2_trigger,
            "trigger_conditions": list(self.trigger_conditions),
            "not_executable": self.not_executable,
        }


def _float(row: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(row: Mapping[str, Any], key: str) -> bool:
    value = row.get(key, False)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def evaluate_h004_row(row: Mapping[str, Any]) -> H004Evaluation:
    """Evaluate one point-in-time H004 candidate row.

    This function intentionally does not inspect future returns. Stock-level
    price/volume information is prohibited from the Stage-1 anchor and is used
    only for the Stage-2 execution trigger.
    """

    traded_value = _float(row, "median_20d_traded_value_inr")
    discovery_universe = traded_value >= DISCOVERY_TRADED_VALUE_MIN
    primary_universe = traded_value >= PRIMARY_TRADED_VALUE_MIN

    pre_momentum_eligible = (
        _float(row, "prior_5d_return_pct") < 10.0
        and _float(row, "prior_20d_return_pct") < 20.0
        and _float(row, "prior_1d_return_pct") < 8.0
    )

    catalyst_grade = int(_float(row, "catalyst_grade"))

    earnings_tests = 0
    earnings_tests += _float(row, "revenue_yoy_pct") >= 20.0
    earnings_tests += _float(row, "operating_profit_yoy_pct") >= 30.0
    earnings_tests += _float(row, "pat_yoy_pct") >= 40.0
    margin_test = _float(row, "margin_change_pp") >= 1.0 or _bool(row, "loss_to_profit")
    earnings_tests += margin_test

    earnings_invalidated = any(
        (
            _bool(row, "tax_reversal_primary_driver"),
            _bool(row, "asset_sale_primary_driver"),
            _bool(row, "deconsolidation_gain_primary_driver"),
            _bool(row, "management_says_non_recurring"),
        )
    )

    absolute_pat = _float(row, "quarterly_pat_inr_crore")
    speculative_base_effect = absolute_pat < 2.0

    earnings_anchor = (
        not earnings_invalidated
        and not speculative_base_effect
        and (
            earnings_tests == 4
            or (earnings_tests >= 3 and catalyst_grade >= 3)
        )
    )

    prior_loss_or_low_margin = _bool(row, "prior_comparable_loss") or _float(
        row, "prior_operating_margin_pct", 100.0
    ) <= 3.0
    turnaround_anchor = (
        prior_loss_or_low_margin
        and (
            _float(row, "loss_narrowing_pct") >= 50.0
            or _float(row, "margin_change_pp") >= 2.0
        )
        and _float(row, "revenue_yoy_pct") >= 5.0
        and not _bool(row, "material_liquidity_deterioration")
    )

    catalyst_anchor = catalyst_grade >= 3

    anchors: list[str] = []
    if earnings_anchor:
        anchors.append("EARNINGS_INFLECTION")
    if turnaround_anchor:
        anchors.append("TURNAROUND")
    if catalyst_anchor:
        anchors.append("CORPORATE_CATALYST")

    hard_reject_reasons: list[str] = []
    if _bool(row, "rising_promoter_pledge"):
        hard_reject_reasons.append("RISING_PROMOTER_PLEDGE")
    if _bool(row, "qualified_audit_or_auditor_resignation"):
        hard_reject_reasons.append("AUDIT_GOVERNANCE_RISK")

    quality_warnings: list[str] = []
    if _float(row, "other_income_or_exceptional_pct_pbt") >= 30.0:
        quality_warnings.append("HIGH_NON_OPERATING_PBT_SHARE")
    if speculative_base_effect:
        quality_warnings.append("SPECULATIVE_BASE_EFFECT")
    if earnings_invalidated:
        quality_warnings.append("EARNINGS_ANCHOR_INVALIDATED_BY_ONE_OFF")
    if _bool(row, "negative_ocf_inconsistent_with_inflection"):
        quality_warnings.append("CASH_CONVERSION_MISMATCH")

    event_age_sessions = int(_float(row, "event_age_sessions"))
    expectation_gap = (
        event_age_sessions >= 3
        and _float(row, "event_to_decision_return_pct") <= 7.0
        and pre_momentum_eligible
        and (earnings_anchor or turnaround_anchor)
    )

    # Ranking points are secondary to the anchor rules and are frozen before
    # broad replay. They do not contain stock-level momentum.
    watch_points = 0
    watch_points += earnings_tests
    watch_points += min(max(catalyst_grade, 0), 4)
    watch_points += 2 if turnaround_anchor else 0
    watch_points += 1 if expectation_gap else 0
    watch_points += 1 if _bool(row, "sector_context_positive") else 0
    watch_points += 1 if _bool(row, "valuation_asymmetry_positive") else 0
    watch_points += 1 if _bool(row, "balance_sheet_capacity_positive") else 0
    watch_points -= len(quality_warnings)

    stage1_eligible = (
        discovery_universe
        and pre_momentum_eligible
        and bool(anchors)
        and not hard_reject_reasons
    )

    trigger_conditions: list[str] = []
    one_day_return = _float(row, "trigger_1d_return_pct")
    if 2.0 <= one_day_return <= 8.0:
        trigger_conditions.append("EARLY_PRICE_RECOGNITION")
    if _float(row, "trigger_volume_vs_20d_median") >= 2.0:
        trigger_conditions.append("ABNORMAL_VOLUME")
    if _float(row, "trigger_delivery_vs_20d_median") >= 1.5:
        trigger_conditions.append("ABNORMAL_DELIVERY")
    if _float(row, "trigger_sector_relative_return_pp") >= 2.0:
        trigger_conditions.append("SECTOR_RELATIVE_STRENGTH")
    if _bool(row, "trigger_close_within_5pct_60d_high"):
        trigger_conditions.append("NEAR_60D_HIGH")

    not_executable = _bool(row, "one_sided_no_offer") or _bool(
        row, "first_trigger_is_upper_circuit"
    )
    stage2_trigger = (
        stage1_eligible
        and len(trigger_conditions) >= 2
        and _float(row, "trigger_prior_5d_return_pct") < 15.0
        and not not_executable
    )

    return H004Evaluation(
        stage1_eligible=stage1_eligible,
        primary_universe=primary_universe,
        discovery_universe=discovery_universe,
        pre_momentum_eligible=pre_momentum_eligible,
        anchors=tuple(anchors),
        quality_warnings=tuple(quality_warnings),
        hard_reject_reasons=tuple(hard_reject_reasons),
        speculative_base_effect=speculative_base_effect,
        expectation_gap=expectation_gap,
        watch_points=watch_points,
        stage2_trigger=stage2_trigger,
        trigger_conditions=tuple(trigger_conditions),
        not_executable=not_executable,
    )
