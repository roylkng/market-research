from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.alpha_model import (
    fit_ridge,
    project_examples,
    purge_training_examples,
)
from marketlab.alpha_multihorizon import build_action_safe_horizon_examples
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_t004_prospective import _score_model
from marketlab.po001 import (
    DEFAULT_MAX_INVESTED_WEIGHT,
    DEFAULT_MAX_NAME_WEIGHT,
    DEFAULT_MAX_TRADED_FRACTION,
    optimize_portfolio,
)
from marketlab.po001_i001 import (
    COST_REFERENCE_NOTIONAL_INR,
    RISK_AVERSION,
    TOP_DECILE_SHARE,
    _capped_proportional,
    _optimizer_summary,
    _portfolio_summary,
)
from marketlab.tc001 import TC001Config, observable_side_cost

STUDY_ID = "PO001-I002-v1"
DECISION_SESSION = "2026-08-31"
HORIZON_SESSIONS = 5
VALIDATION_START_SESSION = "2026-07-01"
RIDGE_L2 = 1.0
MIN_COMMON_IDENTITIES = 500


def _verify_hash(
    payload: dict[str, Any],
    *,
    hash_field: str,
    name: str,
) -> None:
    stored = str(payload.get(hash_field) or "")
    unsigned = dict(payload)
    unsigned.pop(hash_field, None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError(f"{name} hash mismatch")


def run_po001_i002(
    *,
    delivery_feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    risk_state: dict[str, Any],
) -> dict[str, Any]:
    _verify_hash(
        delivery_feature_panel,
        hash_field="panel_sha256",
        name="I002 delivery feature panel",
    )
    _verify_hash(
        market_panel,
        hash_field="panel_sha256",
        name="I002 market panel",
    )
    _verify_hash(
        action_ledger,
        hash_field="ledger_sha256",
        name="I002 corporate-action ledger",
    )
    _verify_hash(
        risk_state,
        hash_field="state_sha256",
        name="I002 RM001 risk state",
    )
    if str(risk_state.get("as_of_session") or "") != DECISION_SESSION:
        raise AlphaContractError(
            "I002 RM001 state does not match frozen decision session"
        )

    ranked = (
        delivery_feature_panel
        if delivery_feature_panel.get("transform")
        == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(delivery_feature_panel)
    )
    feature_names = [
        definition.name
        for definition in [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    ]
    definitions = ranked.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("I002 feature definitions are missing")
    if {str(row["name"]) for row in definitions} != set(feature_names):
        raise AlphaContractError(
            "I002 feature panel differs from frozen T003 27 features"
        )

    examples_by_horizon, exclusions = build_action_safe_horizon_examples(
        feature_panel=ranked,
        market_panel=market_panel,
        action_ledger=action_ledger,
        horizons=(HORIZON_SESSIONS,),
    )
    examples = project_examples(
        examples_by_horizon[HORIZON_SESSIONS],
        feature_names=feature_names,
    )
    training = purge_training_examples(
        examples,
        validation_start_session=VALIDATION_START_SESSION,
    )
    if len(training) < 100:
        raise AlphaContractError("I002 fold-2 training set is too small")
    if max(row.exit_session for row in training) >= VALIDATION_START_SESSION:
        raise AlphaContractError("I002 training contains validation-era label")
    model = fit_ridge(
        training,
        feature_names=feature_names,
        l2=RIDGE_L2,
        model_id="AE001-T003-H5-F2-AUGMENTED-RIDGE-I002",
    )

    decision_rows = [
        row
        for row in ranked.get("rows", [])
        if str(row.get("feature_session")) == DECISION_SESSION
    ]
    if not decision_rows:
        raise AlphaContractError(
            "I002 delivery panel lacks frozen decision session"
        )
    predictions = _score_model(asdict(model), decision_rows)
    alpha_all = {
        (str(row["symbol"]), str(row["isin"])): float(row["prediction"])
        for row in predictions
    }
    risk_identities = {
        (str(row["symbol"]), str(row["isin"]))
        for row in risk_state["rows"]
    }
    common = sorted(set(alpha_all) & risk_identities)
    if len(common) < MIN_COMMON_IDENTITIES:
        raise AlphaContractError(
            f"I002 common universe below minimum: {len(common)}"
        )
    alpha_by_identity = {
        identity: alpha_all[identity]
        for identity in common
    }

    ordered = sorted(
        common,
        key=lambda identity: (
            -alpha_by_identity[identity],
            identity[0],
            identity[1],
        ),
    )
    bucket_size = max(1, math.ceil(len(ordered) * TOP_DECILE_SHARE))
    top_decile = ordered[:bucket_size]
    equal_weights = {
        identity: 1.0 / len(top_decile)
        for identity in top_decile
    }
    if max(equal_weights.values()) > DEFAULT_MAX_NAME_WEIGHT + 1e-12:
        raise AlphaContractError(
            "I002 equal-weight top decile violates PO001 name cap"
        )
    proportional_weights = _capped_proportional(
        [
            (identity, alpha_by_identity[identity])
            for identity in top_decile
        ],
        cap=DEFAULT_MAX_NAME_WEIGHT,
    )

    buy = observable_side_cost(
        side="BUY",
        notional_inr=COST_REFERENCE_NOTIONAL_INR,
        config=TC001Config(),
    )
    sell = observable_side_cost(
        side="SELL",
        notional_inr=COST_REFERENCE_NOTIONAL_INR,
        config=TC001Config(),
    )
    buy_cost_bps = float(buy["total_bps"])
    sell_cost_bps = float(sell["total_bps"])

    baseline_equal = _portfolio_summary(
        name="EQUAL_WEIGHT_TOP_DECILE",
        weights=equal_weights,
        alpha_by_identity=alpha_by_identity,
        risk_state=risk_state,
        buy_cost_bps=buy_cost_bps,
        sell_cost_bps=sell_cost_bps,
        risk_aversion=RISK_AVERSION,
    )
    baseline_proportional = _portfolio_summary(
        name="POSITIVE_ALPHA_PROPORTIONAL_TOP_DECILE",
        weights=proportional_weights,
        alpha_by_identity=alpha_by_identity,
        risk_state=risk_state,
        buy_cost_bps=buy_cost_bps,
        sell_cost_bps=sell_cost_bps,
        risk_aversion=RISK_AVERSION,
    )

    def alpha_rows(*, with_cost: bool) -> list[dict[str, Any]]:
        return [
            {
                "symbol": identity[0],
                "isin": identity[1],
                "expected_excess_return": alpha_by_identity[identity],
                "current_weight": 0.0,
                "buy_cost_bps": buy_cost_bps if with_cost else 0.0,
                "sell_cost_bps": sell_cost_bps if with_cost else 0.0,
            }
            for identity in common
        ]

    risk_aware = optimize_portfolio(
        decision_session=DECISION_SESSION,
        horizon_sessions=HORIZON_SESSIONS,
        alpha_rows=alpha_rows(with_cost=False),
        risk_state=risk_state,
        risk_aversion=RISK_AVERSION,
        max_name_weight=DEFAULT_MAX_NAME_WEIGHT,
        max_invested_weight=DEFAULT_MAX_INVESTED_WEIGHT,
        max_traded_fraction_of_nav=DEFAULT_MAX_TRADED_FRACTION,
        factor_bounds={},
        terminal_liquidation=True,
    )
    full = optimize_portfolio(
        decision_session=DECISION_SESSION,
        horizon_sessions=HORIZON_SESSIONS,
        alpha_rows=alpha_rows(with_cost=True),
        risk_state=risk_state,
        risk_aversion=RISK_AVERSION,
        max_name_weight=DEFAULT_MAX_NAME_WEIGHT,
        max_invested_weight=DEFAULT_MAX_INVESTED_WEIGHT,
        max_traded_fraction_of_nav=DEFAULT_MAX_TRADED_FRACTION,
        factor_bounds={},
        terminal_liquidation=True,
    )

    alphas = [alpha_by_identity[identity] for identity in common]
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "evidence_class": "HISTORICAL_WALKFORWARD_OOS_INTEGRATION",
        "decision_session": DECISION_SESSION,
        "source_end_date": DECISION_SESSION,
        "horizon_sessions": HORIZON_SESSIONS,
        "realized_outcome_opened": False,
        "alpha_source": {
            "source_trial": "AE001-T003",
            "fold": 2,
            "validation_start_session": VALIDATION_START_SESSION,
            "training_example_count": len(training),
            "training_first_feature_session": min(
                row.feature_session for row in training
            ),
            "training_last_feature_session": max(
                row.feature_session for row in training
            ),
            "training_last_exit_session": max(
                row.exit_session for row in training
            ),
            "model_id": model.model_id,
            "model_sha256": model.model_sha256,
            "delivery_feature_panel_sha256": delivery_feature_panel[
                "panel_sha256"
            ],
            "ranked_delivery_feature_panel_sha256": ranked["panel_sha256"],
            "training_exclusions": exclusions,
        },
        "risk_source": {
            "model_id": risk_state["model_id"],
            "risk_state_sha256": risk_state["state_sha256"],
            "as_of_session": risk_state["as_of_session"],
            "deferred_factors": risk_state["deferred_factors"],
        },
        "cost_source": {
            "model_id": "TC001-v1-DEVELOPMENT",
            "surface": "OBSERVABLE_DELIVERY_EQUITY_COST_FLOOR",
            "reference_notional_inr": COST_REFERENCE_NOTIONAL_INR,
            "buy_cost_bps": buy_cost_bps,
            "sell_cost_bps": sell_cost_bps,
            "spread_included": False,
            "market_impact_included": False,
        },
        "frozen_parameters": {
            "risk_aversion": RISK_AVERSION,
            "max_name_weight": DEFAULT_MAX_NAME_WEIGHT,
            "max_invested_weight": DEFAULT_MAX_INVESTED_WEIGHT,
            "max_traded_fraction_of_nav": DEFAULT_MAX_TRADED_FRACTION,
            "terminal_liquidation": True,
            "factor_bounds": {},
        },
        "common_identity_count": len(common),
        "top_decile_count": len(top_decile),
        "alpha_distribution": {
            "min": min(alphas),
            "max": max(alphas),
            "positive_count": sum(value > 0.0 for value in alphas),
        },
        "portfolios": {
            "equal_weight_top_decile": baseline_equal,
            "positive_alpha_proportional_top_decile": baseline_proportional,
            "risk_aware_zero_cost": _optimizer_summary(
                name="RISK_AWARE_ZERO_COST",
                artifact=risk_aware,
            ),
            "full_po001_observable_cost_floor": _optimizer_summary(
                name="FULL_PO001_OBSERVABLE_COST_FLOOR",
                artifact=full,
            ),
        },
        "interpretation_limits": {
            "post_decision_market_sources_acquired": False,
            "no_realized_5d_outcome": True,
            "tc001_spread_included": False,
            "tc001_market_impact_included": False,
            "sector_factor_available": False,
            "size_factor_available": False,
            "prospective_alpha_claim": False,
        },
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact
