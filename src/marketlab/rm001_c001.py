from __future__ import annotations

import hashlib
import math
import statistics
from collections import defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_corporate_actions import (
    action_index,
    blocked_actions,
    validate_action_ledger,
)
from marketlab.alpha_diagnostics import newey_west_mean_inference
from marketlab.rm001 import (
    _market_maps,
    build_rm001_exposure_panel,
    build_rm001_factor_history,
    build_rm001_risk_state,
    portfolio_risk,
)
from marketlab.rm001_v2 import (
    build_rm001_v2_exposure_panel,
    build_rm001_v2_factor_history,
    build_rm001_v2_risk_state,
    portfolio_risk_v2,
)
from marketlab.rm001_v3 import (
    build_rm001_v3_risk_state,
    portfolio_risk_v3,
)

STUDY_ID = "RM001-C001-v1"
CANDIDATE_START = "2026-04-01"
CANDIDATE_END = "2026-09-24"
PROBE_SIZE = 30
HASH_PROBE_COUNT = 8
MIN_COMMON_IDENTITIES = 500
MIN_VALID_PROBES_PER_DATE = 12
MIN_EVALUATED_DATES = 40
NEWEY_WEST_LAG = 5
LOG_RATIO_EPSILON = 1e-12
TAIL_FACTORS = (
    "BETA60_RELATIVE",
    "MOMENTUM20",
    "VOLATILITY60",
    "LIQUIDITY",
    "SIZE",
)

_NOT_READY_MESSAGES = (
    "RM001 has insufficient factor-return history",
    "RM001-v2 has insufficient factor-return history",
    "RM001-v3 has insufficient realized factor-return history",
    "RM001-v3 complete residual-history universe is too small",
)


def _is_not_ready(exc: AlphaContractError) -> bool:
    message = str(exc)
    return any(token in message for token in _NOT_READY_MESSAGES)


def qlike_loss(predicted_variance: float, realized_squared_return: float) -> float:
    predicted = float(predicted_variance)
    realized = float(realized_squared_return)
    if not math.isfinite(predicted) or predicted <= 0:
        raise AlphaContractError(
            "C001 predicted variance must be finite and strictly positive"
        )
    if not math.isfinite(realized) or realized < 0:
        raise AlphaContractError(
            "C001 realized squared return must be finite and non-negative"
        )
    return math.log(predicted) + realized / predicted


def _identity(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row["symbol"]), str(row["isin"]))


def _row_map(state: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = state.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("C001 risk state rows are missing")
    result = {_identity(row): row for row in rows}
    if len(result) != len(rows):
        raise AlphaContractError("C001 risk state contains duplicate identities")
    return result


def _hash_probe(
    identities: list[tuple[str, str]],
    *,
    index: int,
) -> tuple[str, list[tuple[str, str]]]:
    name = f"HASH{index:02d}"
    ranked = sorted(
        identities,
        key=lambda identity: (
            hashlib.sha256(
                (
                    f"RM001-C001|{name}|"
                    f"{identity[0]}|{identity[1]}"
                ).encode()
            ).hexdigest(),
            identity[0],
            identity[1],
        ),
    )
    if len(ranked) < PROBE_SIZE:
        raise AlphaContractError("C001 hash probe universe is too small")
    return name, ranked[:PROBE_SIZE]


def build_probe_library(
    *,
    v1_state: dict[str, Any],
    v2_state: dict[str, Any],
    v3_state: dict[str, Any],
) -> dict[str, list[tuple[str, str]]]:
    v1 = _row_map(v1_state)
    v2 = _row_map(v2_state)
    v3 = _row_map(v3_state)
    common = sorted(set(v1) & set(v2) & set(v3))
    if len(common) < MIN_COMMON_IDENTITIES:
        raise AlphaContractError(
            f"C001 common risk universe below minimum: {len(common)}"
        )

    probes: dict[str, list[tuple[str, str]]] = {}
    for index in range(HASH_PROBE_COUNT):
        name, members = _hash_probe(common, index=index)
        probes[name] = members

    for factor in TAIL_FACTORS:
        values = []
        for identity in common:
            exposures = v2[identity].get("exposures")
            if not isinstance(exposures, dict) or factor not in exposures:
                raise AlphaContractError(
                    f"C001 v2 state lacks probe factor {factor}"
                )
            value = float(exposures[factor])
            if not math.isfinite(value):
                raise AlphaContractError(
                    f"C001 nonfinite probe exposure for {factor}"
                )
            values.append((identity, value))

        low = sorted(
            values,
            key=lambda item: (
                item[1],
                item[0][0],
                item[0][1],
            ),
        )[:PROBE_SIZE]
        high = sorted(
            values,
            key=lambda item: (
                -item[1],
                item[0][0],
                item[0][1],
            ),
        )[:PROBE_SIZE]
        if len(low) != PROBE_SIZE or len(high) != PROBE_SIZE:
            raise AlphaContractError(
                f"C001 factor-tail probe is too small for {factor}"
            )
        probes[f"{factor}_LOW"] = [identity for identity, _ in low]
        probes[f"{factor}_HIGH"] = [identity for identity, _ in high]

    expected = HASH_PROBE_COUNT + 2 * len(TAIL_FACTORS)
    if len(probes) != expected:
        raise AlphaContractError("C001 probe-count invariant failed")
    for name, identities in probes.items():
        if len(identities) != PROBE_SIZE or len(set(identities)) != PROBE_SIZE:
            raise AlphaContractError(
                f"C001 probe membership invariant failed: {name}"
            )
    return dict(sorted(probes.items()))


def _positions(
    identities: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    weight = 1.0 / len(identities)
    return [
        {
            "symbol": identity[0],
            "isin": identity[1],
            "weight": weight,
        }
        for identity in identities
    ]


def _realized_probe_return(
    *,
    identities: list[tuple[str, str]],
    decision_session: str,
    realized_session: str,
    stock_by_session: dict[
        str, dict[tuple[str, str], Any]
    ],
    actions: dict[str, dict[str, Any]],
) -> tuple[float | None, str | None]:
    weight = 1.0 / len(identities)
    realized = 0.0
    for identity in identities:
        current = stock_by_session[decision_session].get(identity)
        nxt = stock_by_session[realized_session].get(identity)
        if current is None or nxt is None:
            return None, "MISSING_NEXT_IDENTITY"
        state = actions.get(identity[0].upper())
        if state is not None and state.get("status") != "READY":
            return None, "ACTION_AUDIT_UNRESOLVED"
        if blocked_actions(
            actions,
            symbol=identity[0],
            start_exclusive=decision_session,
            end_inclusive=realized_session,
        ):
            return None, "CORPORATE_ACTION_BLOCKED"
        stock_return = nxt.close_price / current.close_price - 1.0
        if not math.isfinite(stock_return):
            return None, "NONFINITE_RETURN"
        realized += weight * stock_return
    return realized, None


def _model_summary(
    rows: list[dict[str, Any]],
    *,
    model_key: str,
) -> dict[str, Any]:
    if not rows:
        return {
            "score_count": 0,
            "mean_qlike": None,
            "mean_predicted_variance": None,
            "mean_realized_squared_return": None,
            "aggregate_calibration_ratio": None,
            "mean_absolute_log_variance_ratio": None,
            "underprediction_fraction": None,
            "mean_qlike_by_probe": {},
        }

    predicted = [float(row[f"{model_key}_variance"]) for row in rows]
    realized = [float(row["realized_squared_return"]) for row in rows]
    losses = [float(row[f"{model_key}_qlike"]) for row in rows]
    ratios = [
        abs(
            math.log(
                (realized_value + LOG_RATIO_EPSILON)
                / (predicted_value + LOG_RATIO_EPSILON)
            )
        )
        for predicted_value, realized_value in zip(
            predicted,
            realized,
            strict=True,
        )
    ]
    by_probe: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_probe[str(row["probe_name"])].append(
            float(row[f"{model_key}_qlike"])
        )
    return {
        "score_count": len(rows),
        "mean_qlike": statistics.mean(losses),
        "mean_predicted_variance": statistics.mean(predicted),
        "mean_realized_squared_return": statistics.mean(realized),
        "aggregate_calibration_ratio": (
            sum(realized) / sum(predicted)
        ),
        "mean_absolute_log_variance_ratio": statistics.mean(ratios),
        "underprediction_fraction": (
            sum(
                realized_value > predicted_value
                for predicted_value, realized_value in zip(
                    predicted,
                    realized,
                    strict=True,
                )
            )
            / len(rows)
        ),
        "mean_qlike_by_probe": {
            name: statistics.mean(values)
            for name, values in sorted(by_probe.items())
        },
    }


def _classification(
    *,
    included_date_count: int,
    v3_minus_v1: dict[str, Any],
    v3_minus_v2: dict[str, Any],
) -> str:
    if included_date_count < MIN_EVALUATED_DATES:
        return "INSUFFICIENT_CALIBRATION_SAMPLE"

    def significant_better(inference: dict[str, Any]) -> bool:
        mean = inference.get("mean")
        high = inference.get("ci95_high")
        return (
            mean is not None
            and high is not None
            and float(mean) < 0.0
            and float(high) < 0.0
        )

    v31 = significant_better(v3_minus_v1)
    v32 = significant_better(v3_minus_v2)
    if v31 and v32:
        return "V3_SUPERIOR_OOS_RISK_FORECAST"

    means_negative = (
        v3_minus_v1.get("mean") is not None
        and v3_minus_v2.get("mean") is not None
        and float(v3_minus_v1["mean"]) < 0.0
        and float(v3_minus_v2["mean"]) < 0.0
    )
    if v31 or v32 or means_negative:
        return "V3_MIXED_OOS_RISK_FORECAST"
    return "NO_V3_OOS_RISK_SUPERIORITY"


def run_rm001_c001(
    *,
    market_panel: dict[str, Any],
    feature_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    size_panel: dict[str, Any],
) -> dict[str, Any]:
    validate_action_ledger(action_ledger)
    dates, stock_by_session, _ = _market_maps(market_panel)
    date_index = {value: index for index, value in enumerate(dates)}
    actions = action_index(action_ledger)

    v1_exposures = build_rm001_exposure_panel(
        feature_panel=feature_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
    )
    v1_history = build_rm001_factor_history(
        exposure_panel=v1_exposures,
        market_panel=market_panel,
        action_ledger=action_ledger,
    )
    v2_exposures = build_rm001_v2_exposure_panel(
        feature_panel=feature_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        size_panel=size_panel,
    )
    v2_history = build_rm001_v2_factor_history(
        exposure_panel=v2_exposures,
        market_panel=market_panel,
        action_ledger=action_ledger,
    )

    candidate_dates = [
        value
        for value in dates
        if CANDIDATE_START <= value <= CANDIDATE_END
        and date_index[value] + 1 < len(dates)
    ]

    probe_rows: list[dict[str, Any]] = []
    date_rows: list[dict[str, Any]] = []
    skipped_dates: list[dict[str, str]] = []

    for decision_session in candidate_dates:
        realized_session = dates[date_index[decision_session] + 1]
        try:
            v1_state = build_rm001_risk_state(
                exposure_panel=v1_exposures,
                factor_history=v1_history,
                as_of_session=decision_session,
            )
            v2_state = build_rm001_v2_risk_state(
                exposure_panel=v2_exposures,
                factor_history=v2_history,
                as_of_session=decision_session,
            )
            v3_state = build_rm001_v3_risk_state(
                v2_risk_state=v2_state,
                v2_factor_history=v2_history,
            )
        except AlphaContractError as exc:
            if _is_not_ready(exc):
                skipped_dates.append(
                    {
                        "decision_session": decision_session,
                        "reason": str(exc),
                    }
                )
                continue
            raise

        probes = build_probe_library(
            v1_state=v1_state,
            v2_state=v2_state,
            v3_state=v3_state,
        )

        valid_losses = {
            "v1": [],
            "v2": [],
            "v3": [],
        }
        valid_probe_count = 0

        for probe_name, identities in probes.items():
            realized_return, unavailable_reason = _realized_probe_return(
                identities=identities,
                decision_session=decision_session,
                realized_session=realized_session,
                stock_by_session=stock_by_session,
                actions=actions,
            )
            if unavailable_reason is not None:
                probe_rows.append(
                    {
                        "decision_session": decision_session,
                        "realized_session": realized_session,
                        "probe_name": probe_name,
                        "status": "UNAVAILABLE",
                        "reason": unavailable_reason,
                    }
                )
                continue

            assert realized_return is not None
            positions = _positions(identities)
            v1_forecast = portfolio_risk(
                v1_state,
                positions=positions,
            )
            v2_forecast = portfolio_risk_v2(
                v2_state,
                positions=positions,
            )
            v3_forecast = portfolio_risk_v3(
                v3_state,
                positions=positions,
            )
            realized_squared = realized_return * realized_return
            variances = {
                "v1": float(v1_forecast["total_variance_daily"]),
                "v2": float(v2_forecast["total_variance_daily"]),
                "v3": float(v3_forecast["total_variance_daily"]),
            }
            losses = {
                key: qlike_loss(value, realized_squared)
                for key, value in variances.items()
            }
            valid_probe_count += 1
            for key in valid_losses:
                valid_losses[key].append(losses[key])

            probe_rows.append(
                {
                    "decision_session": decision_session,
                    "realized_session": realized_session,
                    "probe_name": probe_name,
                    "status": "SCORED",
                    "member_count": len(identities),
                    "members_sha256": digest(
                        [
                            {
                                "symbol": identity[0],
                                "isin": identity[1],
                            }
                            for identity in identities
                        ]
                    ),
                    "realized_return": realized_return,
                    "realized_squared_return": realized_squared,
                    "v1_variance": variances["v1"],
                    "v2_variance": variances["v2"],
                    "v3_variance": variances["v3"],
                    "v1_qlike": losses["v1"],
                    "v2_qlike": losses["v2"],
                    "v3_qlike": losses["v3"],
                }
            )

        if valid_probe_count >= MIN_VALID_PROBES_PER_DATE:
            means = {
                key: statistics.mean(values)
                for key, values in valid_losses.items()
            }
            date_rows.append(
                {
                    "decision_session": decision_session,
                    "realized_session": realized_session,
                    "valid_probe_count": valid_probe_count,
                    "v1_mean_qlike": means["v1"],
                    "v2_mean_qlike": means["v2"],
                    "v3_mean_qlike": means["v3"],
                    "v3_minus_v1": means["v3"] - means["v1"],
                    "v3_minus_v2": means["v3"] - means["v2"],
                    "v2_minus_v1": means["v2"] - means["v1"],
                    "v1_state_sha256": v1_state["state_sha256"],
                    "v2_state_sha256": v2_state["state_sha256"],
                    "v3_state_sha256": v3_state["state_sha256"],
                }
            )
        else:
            skipped_dates.append(
                {
                    "decision_session": decision_session,
                    "reason": (
                        "VALID_PROBE_COUNT_BELOW_MINIMUM:"
                        f"{valid_probe_count}"
                    ),
                }
            )

    scored_rows = [
        row for row in probe_rows if row["status"] == "SCORED"
    ]
    inferences = {
        "v3_minus_v1": newey_west_mean_inference(
            [float(row["v3_minus_v1"]) for row in date_rows],
            max_lag=NEWEY_WEST_LAG,
        ),
        "v3_minus_v2": newey_west_mean_inference(
            [float(row["v3_minus_v2"]) for row in date_rows],
            max_lag=NEWEY_WEST_LAG,
        ),
        "v2_minus_v1": newey_west_mean_inference(
            [float(row["v2_minus_v1"]) for row in date_rows],
            max_lag=NEWEY_WEST_LAG,
        ),
    }
    classification = _classification(
        included_date_count=len(date_rows),
        v3_minus_v1=inferences["v3_minus_v1"],
        v3_minus_v2=inferences["v3_minus_v2"],
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "status": classification,
        "evidence_class": (
            "HISTORICAL_RECONSTRUCTION_OOS_RISK_CALIBRATION"
        ),
        "candidate_window": {
            "start": CANDIDATE_START,
            "end": CANDIDATE_END,
        },
        "candidate_date_count": len(candidate_dates),
        "evaluated_date_count": len(date_rows),
        "minimum_evaluated_date_count": MIN_EVALUATED_DATES,
        "minimum_valid_probes_per_date": MIN_VALID_PROBES_PER_DATE,
        "probe_count_per_ready_date": (
            HASH_PROBE_COUNT + 2 * len(TAIL_FACTORS)
        ),
        "probe_size": PROBE_SIZE,
        "primary_loss": "QLIKE",
        "models": {
            "v1": _model_summary(scored_rows, model_key="v1"),
            "v2": _model_summary(scored_rows, model_key="v2"),
            "v3": _model_summary(scored_rows, model_key="v3"),
        },
        "paired_date_level_inference": inferences,
        "date_metrics": date_rows,
        "probe_metrics": probe_rows,
        "skipped_dates": skipped_dates,
        "source": {
            "market_panel_sha256": market_panel["panel_sha256"],
            "feature_panel_sha256": feature_panel["panel_sha256"],
            "action_ledger_sha256": action_ledger["ledger_sha256"],
            "size_panel_sha256": size_panel["panel_sha256"],
            "v1_exposure_panel_sha256": v1_exposures["panel_sha256"],
            "v1_factor_history_sha256": v1_history["history_sha256"],
            "v2_exposure_panel_sha256": v2_exposures["panel_sha256"],
            "v2_factor_history_sha256": v2_history["history_sha256"],
        },
        "interpretation_limits": {
            "historical_reconstruction": True,
            "prospective_calibration_claim_allowed": False,
            "alpha_claim_allowed": False,
            "realized_investment_return_claim_allowed": False,
            "live_capital_allowed": False,
        },
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
