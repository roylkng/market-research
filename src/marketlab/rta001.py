from __future__ import annotations

import copy
import math
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest

RTA001_ID = "RTA001-v1"
ALPHA = 0.05
CATEGORIES = {
    "ALPHA_FEATURE_DISCOVERY",
    "ALPHA_COMBINATION_DIAGNOSTIC",
    "PORTFOLIO_CONTEXT",
    "PORTFOLIO_INTEGRATION",
    "RISK_MODEL",
    "SOURCE_FEASIBILITY",
    "SOLVER_STABILITY",
}


def validate_rta001_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("accounting_id") != RTA001_ID:
        raise AlphaContractError("RTA001 manifest identity mismatch")
    if manifest.get("live_capital_allowed") is not False:
        raise AlphaContractError("RTA001 cannot allow live capital")
    trials = manifest.get("trials")
    if not isinstance(trials, list) or not trials:
        raise AlphaContractError("RTA001 trial list is required")

    seen: set[str] = set()
    for trial in trials:
        if not isinstance(trial, dict):
            raise AlphaContractError("RTA001 trial entry must be an object")
        trial_id = str(trial.get("trial_id") or "").strip()
        if not trial_id or trial_id in seen:
            raise AlphaContractError(
                f"RTA001 trial IDs must be nonempty and unique: {trial_id}"
            )
        seen.add(trial_id)
        category = str(trial.get("category") or "")
        if category not in CATEGORIES:
            raise AlphaContractError(
                f"RTA001 unsupported category for {trial_id}: {category}"
            )
        p_value = trial.get("nominal_primary_p_value")
        accounting_p = trial.get("fdr_accounting_p_value")
        for label, value in (
            ("nominal_primary_p_value", p_value),
            ("fdr_accounting_p_value", accounting_p),
        ):
            if value is not None:
                parsed = float(value)
                if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
                    raise AlphaContractError(
                        f"RTA001 {trial_id} {label} must be in [0, 1]"
                    )

        family = trial.get("fdr_family")
        if family is not None and family not in manifest.get(
            "fdr_families", {}
        ):
            raise AlphaContractError(
                f"RTA001 {trial_id} references unknown FDR family {family}"
            )
        if (
            family is not None
            and trial.get("result_state") == "COMPLETE"
            and accounting_p is None
        ):
            raise AlphaContractError(
                f"RTA001 completed family trial lacks accounting p: {trial_id}"
            )

    source_results = manifest.get("source_feasibility_results", [])
    if not isinstance(source_results, list):
        raise AlphaContractError(
            "RTA001 source_feasibility_results must be a list"
        )
    if len(source_results) != len(set(source_results)):
        raise AlphaContractError(
            "RTA001 source feasibility result paths must be unique"
        )


def _sorted_p_values(
    rows: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    if not rows:
        raise AlphaContractError(
            "RTA001 multiplicity family has no completed p-values"
        )
    for trial_id, value in rows:
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise AlphaContractError(
                f"RTA001 invalid p-value for {trial_id}: {value}"
            )
    return sorted(rows, key=lambda item: (item[1], item[0]))


def benjamini_hochberg(
    rows: list[tuple[str, float]],
) -> dict[str, float]:
    ordered = _sorted_p_values(rows)
    count = len(ordered)
    raw = [
        min(1.0, value * count / rank)
        for rank, (_, value) in enumerate(ordered, start=1)
    ]
    adjusted = [1.0] * count
    running = 1.0
    for index in range(count - 1, -1, -1):
        running = min(running, raw[index])
        adjusted[index] = running
    return {
        ordered[index][0]: adjusted[index]
        for index in range(count)
    }


def benjamini_yekutieli(
    rows: list[tuple[str, float]],
) -> dict[str, float]:
    ordered = _sorted_p_values(rows)
    count = len(ordered)
    harmonic = sum(1.0 / index for index in range(1, count + 1))
    raw = [
        min(1.0, value * count * harmonic / rank)
        for rank, (_, value) in enumerate(ordered, start=1)
    ]
    adjusted = [1.0] * count
    running = 1.0
    for index in range(count - 1, -1, -1):
        running = min(running, raw[index])
        adjusted[index] = running
    return {
        ordered[index][0]: adjusted[index]
        for index in range(count)
    }


def holm(
    rows: list[tuple[str, float]],
) -> dict[str, float]:
    ordered = _sorted_p_values(rows)
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (trial_id, value) in enumerate(ordered, start=1):
        candidate = min(1.0, value * (count - rank + 1))
        running = max(running, candidate)
        adjusted[trial_id] = running
    return adjusted


def bonferroni(
    rows: list[tuple[str, float]],
) -> dict[str, float]:
    ordered = _sorted_p_values(rows)
    count = len(ordered)
    return {
        trial_id: min(1.0, value * count)
        for trial_id, value in ordered
    }


def _family_analysis(
    trials: list[dict[str, Any]],
    *,
    family_id: str,
    preregistered_only: bool,
) -> dict[str, Any]:
    family_trials = [
        trial
        for trial in trials
        if trial.get("fdr_family") == family_id
    ]
    completed = [
        trial
        for trial in family_trials
        if trial.get("result_state") == "COMPLETE"
        and trial.get("fdr_accounting_p_value") is not None
        and (
            not preregistered_only
            or trial.get("registration_mode")
            != "RETROSPECTIVE_ACCOUNTING_BACKFILL"
        )
    ]
    p_rows = [
        (
            str(trial["trial_id"]),
            float(trial["fdr_accounting_p_value"]),
        )
        for trial in completed
    ]
    bh = benjamini_hochberg(p_rows)
    by = benjamini_yekutieli(p_rows)
    holm_values = holm(p_rows)
    bonf = bonferroni(p_rows)

    records = []
    for trial in sorted(completed, key=lambda row: str(row["trial_id"])):
        trial_id = str(trial["trial_id"])
        nominal = trial.get("nominal_primary_p_value")
        reported = trial.get("reported_primary_supported")
        record = {
            "trial_id": trial_id,
            "reported_primary_supported": reported,
            "p_value_status": trial.get("p_value_status"),
            "nominal_primary_p_value": nominal,
            "fdr_accounting_p_value": float(
                trial["fdr_accounting_p_value"]
            ),
            "bh_q_value": bh[trial_id],
            "by_q_value": by[trial_id],
            "holm_adjusted_p_value": holm_values[trial_id],
            "bonferroni_adjusted_p_value": bonf[trial_id],
            "bh_significant_0_05": bh[trial_id] < ALPHA,
            "by_significant_0_05": by[trial_id] < ALPHA,
            "holm_significant_0_05": holm_values[trial_id] < ALPHA,
            "bonferroni_significant_0_05": bonf[trial_id] < ALPHA,
        }
        if reported is True:
            record["multiplicity_classification"] = (
                "NOMINALLY_AND_BH_SUPPORTED"
                if record["bh_significant_0_05"]
                else "NOMINALLY_SUPPORTED_NOT_BH_ROBUST"
            )
        elif reported is False:
            record["multiplicity_classification"] = (
                "PRIMARY_UNSUPPORTED"
            )
        else:
            record["multiplicity_classification"] = (
                "PRIMARY_SUPPORT_NOT_FORMALLY_CLASSIFIED"
            )
        records.append(record)

    return {
        "family_id": family_id,
        "preregistered_only": preregistered_only,
        "registered_trial_count": len(family_trials),
        "completed_adjusted_trial_count": len(completed),
        "pending_or_unadjusted_trial_count": (
            len(family_trials) - len(completed)
        ),
        "nominal_supported_count": sum(
            trial.get("reported_primary_supported") is True
            for trial in completed
        ),
        "bh_significant_count": sum(
            value < ALPHA for value in bh.values()
        ),
        "by_significant_count": sum(
            value < ALPHA for value in by.values()
        ),
        "holm_significant_count": sum(
            value < ALPHA for value in holm_values.values()
        ),
        "bonferroni_significant_count": sum(
            value < ALPHA for value in bonf.values()
        ),
        "records": records,
    }


def build_rta001_summary(
    manifest: dict[str, Any],
) -> dict[str, Any]:
    validate_rta001_manifest(manifest)
    trials = manifest["trials"]
    categories = Counter(str(trial["category"]) for trial in trials)
    result_states = Counter(
        str(trial.get("result_state") or "UNKNOWN")
        for trial in trials
    )

    family_summaries = {}
    for family_id in sorted(manifest.get("fdr_families", {})):
        family_summaries[family_id] = {
            "inclusive": _family_analysis(
                trials,
                family_id=family_id,
                preregistered_only=False,
            ),
            "preregistered_only_sensitivity": _family_analysis(
                trials,
                family_id=family_id,
                preregistered_only=True,
            ),
        }

    nominal_supported = [
        str(trial["trial_id"])
        for trial in trials
        if trial.get("reported_primary_supported") is True
    ]
    primary_failed = [
        str(trial["trial_id"])
        for trial in trials
        if trial.get("reported_primary_supported") is False
    ]

    summary: dict[str, Any] = {
        "schema_version": 1,
        "accounting_id": RTA001_ID,
        "as_of_date": manifest["as_of_date"],
        "explicit_trial_count": len(trials),
        "source_feasibility_result_artifact_count": len(
            manifest.get("source_feasibility_results", [])
        ),
        "total_accounted_research_objects": (
            len(trials)
            + len(manifest.get("source_feasibility_results", []))
        ),
        "category_counts": dict(sorted(categories.items())),
        "result_state_counts": dict(sorted(result_states.items())),
        "nominal_primary_supported_trials": sorted(nominal_supported),
        "primary_unsupported_trials": sorted(primary_failed),
        "fdr_families": family_summaries,
        "governance_conclusion": {
            "secondary_endpoints_can_rescue_failed_primary": False,
            "historical_nominal_support_is_not_automatically_multiplicity_robust": True,
            "prospective_confirmation_remains_preferred": True,
            "live_capital_allowed": False,
        },
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = digest(summary)
    return summary
