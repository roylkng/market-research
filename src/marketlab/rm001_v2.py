from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np

from marketlab.alpha import AlphaContractError, cross_sectional_percentile, digest
from marketlab.alpha_corporate_actions import (
    action_index,
    blocked_actions,
    validate_action_ledger,
)
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.rm001 import (
    ANNUALIZATION_SESSIONS,
    BETA_LOOKBACK_SESSIONS,
    FACTOR_COVARIANCE_WINDOW,
    IDIO_WINDOW,
    MIN_FACTOR_CROSS_SECTION,
    MIN_IDIO_OBSERVATIONS,
    _centered_percentile,
    _market_maps,
    _q,
    _verify_hash,
    trailing_beta60,
)
from marketlab.rm001_size_panel import size_rows_by_session

RM001_V2_MODEL_ID = "RM001-v2-DEVELOPMENT"
FACTOR_NAMES_V2 = (
    "MARKET_COMMON",
    "BETA60_RELATIVE",
    "MOMENTUM20",
    "VOLATILITY60",
    "LIQUIDITY",
    "SIZE",
)


@dataclass(frozen=True)
class RiskExposureV2:
    session_date: str
    symbol: str
    isin: str
    market_common: float
    beta60_relative: float
    momentum20: float
    volatility60: float
    liquidity: float
    size: float

    def vector(self) -> tuple[float, ...]:
        return (
            self.market_common,
            self.beta60_relative,
            self.momentum20,
            self.volatility60,
            self.liquidity,
            self.size,
        )


def _identity_key(identity: tuple[str, str]) -> str:
    return f"{identity[0]}|{identity[1]}"


def build_rm001_v2_exposure_panel(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    size_panel: dict[str, Any],
) -> dict[str, Any]:
    validate_action_ledger(action_ledger)
    _verify_hash(
        market_panel,
        field="panel_sha256",
        name="RM001-v2 market panel",
    )
    _verify_hash(
        size_panel,
        field="panel_sha256",
        name="RM001-v2 size panel",
    )
    if size_panel.get("market_panel_sha256") != market_panel.get(
        "panel_sha256"
    ):
        raise AlphaContractError("RM001-v2 size/market panel binding mismatch")
    if feature_panel.get("corporate_action_ledger_sha256") != action_ledger.get(
        "ledger_sha256"
    ):
        raise AlphaContractError(
            "RM001-v2 feature panel is not bound to action ledger"
        )

    ranked = (
        feature_panel
        if feature_panel.get("transform")
        == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(feature_panel)
    )
    _verify_hash(
        ranked,
        field="panel_sha256",
        name="RM001-v2 ranked feature panel",
    )
    dates, stock_by_session, benchmark_by_session = _market_maps(market_panel)
    date_index = {value: index for index, value in enumerate(dates)}
    size_by_session = size_rows_by_session(size_panel)

    feature_rows_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ranked.get("rows", []):
        feature_rows_by_session[str(row["feature_session"])].append(row)

    exposures = []
    exclusions: dict[str, int] = defaultdict(int)

    for session in sorted(feature_rows_by_session):
        position = date_index.get(session)
        if position is None or position < BETA_LOOKBACK_SESSIONS:
            exclusions["BETA_HISTORY"] += len(feature_rows_by_session[session])
            continue
        sizes = size_by_session.get(session)
        if sizes is None:
            raise AlphaContractError(
                f"{session}: RM001-v2 size panel lacks market session"
            )
        candidates = []
        for row in feature_rows_by_session[session]:
            identity = (str(row["symbol"]), str(row["isin"]))
            market_cap = sizes.get(identity)
            if market_cap is None:
                exclusions["SIZE_EXACT_JOIN_MISSING"] += 1
                continue

            window_dates = dates[
                position - BETA_LOOKBACK_SESSIONS : position + 1
            ]
            stock_closes = []
            benchmark_closes = []
            complete = True
            for day in window_dates:
                stock = stock_by_session[day].get(identity)
                if stock is None:
                    complete = False
                    break
                stock_closes.append(stock.close_price)
                benchmark_closes.append(
                    benchmark_by_session[day].close_price
                )
            if not complete:
                exclusions["BETA_IDENTITY_GAP"] += 1
                continue
            try:
                beta = trailing_beta60(stock_closes, benchmark_closes)
            except AlphaContractError:
                exclusions["BETA_INVALID"] += 1
                continue

            values = row.get("values")
            if not isinstance(values, dict):
                raise AlphaContractError(
                    "RM001-v2 feature values must be an object"
                )
            try:
                candidate = {
                    "session_date": session,
                    "symbol": identity[0],
                    "isin": identity[1],
                    "market_cap_inr": float(market_cap),
                    "market_common": 1.0,
                    "beta60_relative": _q(beta - 1.0),
                    "momentum20": _q(
                        _centered_percentile(
                            values.get("momentum_20"),
                            "momentum20",
                        )
                    ),
                    "volatility60": _q(
                        _centered_percentile(
                            values.get("realized_vol_60"),
                            "volatility60",
                        )
                    ),
                    "liquidity": _q(
                        _centered_percentile(
                            values.get("turnover_inr"),
                            "liquidity",
                        )
                    ),
                }
            except AlphaContractError:
                exclusions["STYLE_EXPOSURE_INVALID"] += 1
                continue
            if not math.isfinite(candidate["market_cap_inr"]) or (
                candidate["market_cap_inr"] <= 0
            ):
                exclusions["SIZE_INVALID"] += 1
                continue
            candidates.append(candidate)

        size_percentiles = cross_sectional_percentile(
            {
                _identity_key((row["symbol"], row["isin"])): row[
                    "market_cap_inr"
                ]
                for row in candidates
            }
        )
        for candidate in candidates:
            key = _identity_key((candidate["symbol"], candidate["isin"]))
            percentile = size_percentiles[key]
            if percentile is None:
                exclusions["SIZE_PERCENTILE_INVALID"] += 1
                continue
            exposure = RiskExposureV2(
                session_date=session,
                symbol=candidate["symbol"],
                isin=candidate["isin"],
                market_common=candidate["market_common"],
                beta60_relative=candidate["beta60_relative"],
                momentum20=candidate["momentum20"],
                volatility60=candidate["volatility60"],
                liquidity=candidate["liquidity"],
                size=_q(2.0 * float(percentile) - 1.0),
            )
            if not all(math.isfinite(value) for value in exposure.vector()):
                exclusions["NONFINITE_EXPOSURE"] += 1
                continue
            exposures.append(
                {
                    "session_date": exposure.session_date,
                    "symbol": exposure.symbol,
                    "isin": exposure.isin,
                    "exposures": dict(
                        zip(
                            FACTOR_NAMES_V2,
                            exposure.vector(),
                            strict=True,
                        )
                    ),
                }
            )

    panel: dict[str, Any] = {
        "schema_version": 1,
        "model_id": RM001_V2_MODEL_ID,
        "factor_names": list(FACTOR_NAMES_V2),
        "input_feature_panel_sha256": feature_panel["panel_sha256"],
        "input_ranked_feature_panel_sha256": ranked["panel_sha256"],
        "input_market_panel_sha256": market_panel["panel_sha256"],
        "input_size_panel_sha256": size_panel["panel_sha256"],
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "exposure_count": len(exposures),
        "exclusions": dict(sorted(exclusions.items())),
        "rows": sorted(
            exposures,
            key=lambda item: (
                item["session_date"],
                item["symbol"],
                item["isin"],
            ),
        ),
        "size_contract": {
            "source": "NSE_CM_MII_SECURITY_FILE",
            "formula": "OFFICIAL_CLOSE * ISSD_CPTL",
            "transform": "CENTERED_WITHIN_SESSION_TIE_AWARE_PERCENTILE",
            "d007_result_sha256": size_panel["d007_result_sha256"],
            "prospective_source_timing_verified": False,
        },
        "deferred_factors": {
            "FREE_FLOAT_SIZE": "SOURCE_NOT_POPULATED",
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN",
        },
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _fit_factor_return_v2(
    exposures: list[dict[str, Any]],
    realized_returns: dict[tuple[str, str], float],
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    rows = [
        row
        for row in exposures
        if (row["symbol"], row["isin"]) in realized_returns
    ]
    if len(rows) < MIN_FACTOR_CROSS_SECTION:
        raise AlphaContractError("RM001-v2 factor cross-section is too small")
    matrix = np.asarray(
        [
            [
                float(row["exposures"][factor])
                for factor in FACTOR_NAMES_V2
            ]
            for row in rows
        ],
        dtype=float,
    )
    response = np.asarray(
        [
            realized_returns[(row["symbol"], row["isin"])]
            for row in rows
        ],
        dtype=float,
    )
    if not np.isfinite(matrix).all() or not np.isfinite(response).all():
        raise AlphaContractError(
            "RM001-v2 factor regression contains nonfinite values"
        )
    if np.linalg.matrix_rank(matrix) != len(FACTOR_NAMES_V2):
        raise AlphaContractError(
            "RM001-v2 factor design matrix is rank deficient"
        )
    coefficients, _, _, _ = np.linalg.lstsq(matrix, response, rcond=None)
    fitted = matrix @ coefficients
    residuals = response - fitted
    factor_returns = {
        factor: _q(coefficients[index])
        for index, factor in enumerate(FACTOR_NAMES_V2)
    }
    residual_rows = [
        {
            "symbol": row["symbol"],
            "isin": row["isin"],
            "residual_return": _q(residuals[index]),
        }
        for index, row in enumerate(rows)
    ]
    return factor_returns, residual_rows


def build_rm001_v2_factor_history(
    *,
    exposure_panel: dict[str, Any],
    market_panel: dict[str, Any],
    action_ledger: dict[str, Any],
) -> dict[str, Any]:
    _verify_hash(
        exposure_panel,
        field="panel_sha256",
        name="RM001-v2 exposure panel",
    )
    _verify_hash(
        market_panel,
        field="panel_sha256",
        name="RM001-v2 market panel",
    )
    validate_action_ledger(action_ledger)
    if exposure_panel.get("model_id") != RM001_V2_MODEL_ID:
        raise AlphaContractError("unexpected RM001-v2 exposure model ID")
    if exposure_panel.get("corporate_action_ledger_sha256") != (
        action_ledger.get("ledger_sha256")
    ):
        raise AlphaContractError(
            "RM001-v2 exposure/action ledger binding mismatch"
        )

    dates, stock_by_session, _ = _market_maps(market_panel)
    if (
        str(action_ledger.get("coverage_start_date") or "") > dates[0]
        or str(action_ledger.get("coverage_end_date") or "") < dates[-1]
    ):
        raise AlphaContractError(
            "RM001-v2 corporate-action coverage does not span market panel"
        )
    date_index = {value: index for index, value in enumerate(dates)}
    actions = action_index(action_ledger)
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in exposure_panel.get("rows", []):
        by_session[str(row["session_date"])].append(row)

    factor_returns = []
    residuals = []
    exclusions: dict[str, int] = defaultdict(int)

    for exposure_session in sorted(by_session):
        position = date_index.get(exposure_session)
        if position is None or position + 1 >= len(dates):
            exclusions["NO_NEXT_SESSION"] += 1
            continue
        realized_session = dates[position + 1]
        realized: dict[tuple[str, str], float] = {}

        for row in by_session[exposure_session]:
            identity = (str(row["symbol"]), str(row["isin"]))
            current = stock_by_session[exposure_session].get(identity)
            nxt = stock_by_session[realized_session].get(identity)
            if current is None or nxt is None:
                exclusions["MISSING_NEXT_IDENTITY"] += 1
                continue
            state = actions.get(identity[0].upper())
            if state is not None and state.get("status") != "READY":
                exclusions["ACTION_AUDIT_UNRESOLVED"] += 1
                continue
            if blocked_actions(
                actions,
                symbol=identity[0],
                start_exclusive=exposure_session,
                end_inclusive=realized_session,
            ):
                exclusions["CORPORATE_ACTION_BLOCKED"] += 1
                continue
            value = nxt.close_price / current.close_price - 1.0
            if not math.isfinite(value):
                exclusions["NONFINITE_RETURN"] += 1
                continue
            realized[identity] = value

        try:
            factors, residual_rows = _fit_factor_return_v2(
                by_session[exposure_session],
                realized,
            )
        except AlphaContractError as exc:
            if "cross-section is too small" in str(exc):
                exclusions["CROSS_SECTION_TOO_SMALL"] += 1
                continue
            raise
        factor_returns.append(
            {
                "exposure_session": exposure_session,
                "realized_session": realized_session,
                "factor_returns": factors,
                "observation_count": len(residual_rows),
            }
        )
        for row in residual_rows:
            residuals.append(
                {
                    "exposure_session": exposure_session,
                    "realized_session": realized_session,
                    **row,
                }
            )

    history: dict[str, Any] = {
        "schema_version": 1,
        "model_id": RM001_V2_MODEL_ID,
        "factor_names": list(FACTOR_NAMES_V2),
        "exposure_panel_sha256": exposure_panel["panel_sha256"],
        "market_panel_sha256": market_panel["panel_sha256"],
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "factor_return_count": len(factor_returns),
        "residual_count": len(residuals),
        "factor_returns": factor_returns,
        "residuals": residuals,
        "exclusions": dict(sorted(exclusions.items())),
        "live_capital_allowed": False,
    }
    history["history_sha256"] = digest(history)
    return history


def build_rm001_v2_risk_state(
    *,
    exposure_panel: dict[str, Any],
    factor_history: dict[str, Any],
    as_of_session: str,
    factor_window: int = FACTOR_COVARIANCE_WINDOW,
    idio_window: int = IDIO_WINDOW,
    min_idio_observations: int = MIN_IDIO_OBSERVATIONS,
) -> dict[str, Any]:
    _verify_hash(
        exposure_panel,
        field="panel_sha256",
        name="RM001-v2 exposure panel",
    )
    _verify_hash(
        factor_history,
        field="history_sha256",
        name="RM001-v2 factor history",
    )
    if factor_history.get("exposure_panel_sha256") != exposure_panel.get(
        "panel_sha256"
    ):
        raise AlphaContractError(
            "RM001-v2 factor history/exposure binding mismatch"
        )
    if factor_window < 2 or idio_window < 2 or min_idio_observations < 2:
        raise AlphaContractError("RM001-v2 risk windows are invalid")

    factor_rows = [
        row
        for row in factor_history["factor_returns"]
        if str(row["realized_session"]) <= as_of_session
    ]
    factor_rows.sort(key=lambda row: str(row["realized_session"]))
    if len(factor_rows) < factor_window:
        raise AlphaContractError(
            "RM001-v2 has insufficient factor-return history"
        )
    factor_rows = factor_rows[-factor_window:]
    matrix = np.asarray(
        [
            [
                float(row["factor_returns"][factor])
                for factor in FACTOR_NAMES_V2
            ]
            for row in factor_rows
        ],
        dtype=float,
    )
    covariance = np.cov(matrix, rowvar=False, ddof=1)
    if covariance.shape != (
        len(FACTOR_NAMES_V2),
        len(FACTOR_NAMES_V2),
    ):
        raise AlphaContractError("RM001-v2 covariance shape mismatch")
    if not np.isfinite(covariance).all():
        raise AlphaContractError(
            "RM001-v2 covariance contains nonfinite values"
        )

    current_rows = [
        row
        for row in exposure_panel["rows"]
        if str(row["session_date"]) == as_of_session
    ]
    if not current_rows:
        raise AlphaContractError(
            "RM001-v2 has no current exposures for as-of session"
        )
    current_identities = {
        (str(row["symbol"]), str(row["isin"])) for row in current_rows
    }

    residual_by_identity: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in factor_history["residuals"]:
        identity = (str(row["symbol"]), str(row["isin"]))
        if (
            identity in current_identities
            and str(row["realized_session"]) <= as_of_session
        ):
            residual_by_identity[identity].append(
                float(row["residual_return"])
            )

    observed_variances: dict[tuple[str, str], float] = {}
    for identity in sorted(current_identities):
        trailing = residual_by_identity.get(identity, [])[-idio_window:]
        if len(trailing) >= min_idio_observations:
            variance = float(np.var(np.asarray(trailing), ddof=1))
            if math.isfinite(variance) and variance >= 0:
                observed_variances[identity] = _q(variance)
    if not observed_variances:
        raise AlphaContractError(
            "RM001-v2 current universe has no usable idiosyncratic variances"
        )
    fallback = _q(
        np.percentile(
            np.asarray(list(observed_variances.values()), dtype=float),
            75,
        )
    )

    risk_rows = []
    for row in sorted(
        current_rows,
        key=lambda item: (item["symbol"], item["isin"]),
    ):
        identity = (str(row["symbol"]), str(row["isin"]))
        if identity in observed_variances:
            variance = observed_variances[identity]
            status = "OBSERVED"
        else:
            variance = fallback
            status = "CONSERVATIVE_IMPUTATION_P75"
        risk_rows.append(
            {
                "symbol": identity[0],
                "isin": identity[1],
                "exposures": {
                    factor: _q(row["exposures"][factor])
                    for factor in FACTOR_NAMES_V2
                },
                "idiosyncratic_variance_daily": _q(variance),
                "idiosyncratic_status": status,
            }
        )

    state: dict[str, Any] = {
        "schema_version": 1,
        "model_id": RM001_V2_MODEL_ID,
        "as_of_session": as_of_session,
        "factor_names": list(FACTOR_NAMES_V2),
        "factor_covariance_window": factor_window,
        "factor_covariance_first_realized_session": factor_rows[0][
            "realized_session"
        ],
        "factor_covariance_last_realized_session": factor_rows[-1][
            "realized_session"
        ],
        "factor_covariance_daily": [
            [_q(value) for value in row] for row in covariance.tolist()
        ],
        "idiosyncratic_window": idio_window,
        "minimum_idiosyncratic_observations": min_idio_observations,
        "idiosyncratic_fallback_p75": fallback,
        "exposure_panel_sha256": exposure_panel["panel_sha256"],
        "factor_history_sha256": factor_history["history_sha256"],
        "security_count": len(risk_rows),
        "rows": risk_rows,
        "size_contract": exposure_panel["size_contract"],
        "deferred_factors": exposure_panel["deferred_factors"],
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def portfolio_risk_v2(
    risk_state: dict[str, Any],
    *,
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    _verify_hash(
        risk_state,
        field="state_sha256",
        name="RM001-v2 risk state",
    )
    if risk_state.get("model_id") != RM001_V2_MODEL_ID:
        raise AlphaContractError("unexpected RM001-v2 risk state")
    if not positions:
        raise AlphaContractError("RM001-v2 positions cannot be empty")

    row_by_identity = {
        (str(row["symbol"]), str(row["isin"])): row
        for row in risk_state["rows"]
    }
    weights = []
    exposures = []
    idio = []
    for position in positions:
        weight = float(position["weight"])
        if not math.isfinite(weight) or weight < 0:
            raise AlphaContractError(
                "RM001-v2 weights must be finite and non-negative"
            )
        identity = (str(position["symbol"]), str(position["isin"]))
        row = row_by_identity.get(identity)
        if row is None:
            raise AlphaContractError(
                f"RM001-v2 position absent from risk state: {identity}"
            )
        weights.append(weight)
        exposures.append(
            [
                float(row["exposures"][factor])
                for factor in FACTOR_NAMES_V2
            ]
        )
        idio.append(float(row["idiosyncratic_variance_daily"]))

    weight_array = np.asarray(weights, dtype=float)
    if float(weight_array.sum()) > 1.0 + 1e-12:
        raise AlphaContractError(
            "RM001-v2 portfolio weights cannot exceed 1"
        )
    exposure_matrix = np.asarray(exposures, dtype=float)
    covariance = np.asarray(
        risk_state["factor_covariance_daily"],
        dtype=float,
    )
    factor_exposure = weight_array @ exposure_matrix
    factor_variance = float(
        factor_exposure @ covariance @ factor_exposure
    )
    idio_variance = float(
        np.sum((weight_array**2) * np.asarray(idio, dtype=float))
    )
    total_variance = max(0.0, factor_variance + idio_variance)
    covariance_times_exposure = covariance @ factor_exposure
    contributions = {
        factor: float(
            factor_exposure[index] * covariance_times_exposure[index]
        )
        for index, factor in enumerate(FACTOR_NAMES_V2)
    }
    return {
        "schema_version": 1,
        "model_id": RM001_V2_MODEL_ID,
        "as_of_session": risk_state["as_of_session"],
        "risk_state_sha256": risk_state["state_sha256"],
        "position_count": len(positions),
        "invested_weight": float(weight_array.sum()),
        "cash_weight": 1.0 - float(weight_array.sum()),
        "portfolio_factor_exposures": {
            factor: float(factor_exposure[index])
            for index, factor in enumerate(FACTOR_NAMES_V2)
        },
        "factor_variance_daily": factor_variance,
        "idiosyncratic_variance_daily": idio_variance,
        "total_variance_daily": total_variance,
        "annualized_volatility": math.sqrt(
            total_variance * ANNUALIZATION_SESSIONS
        ),
        "factor_variance_contributions_daily": contributions,
        "live_capital_allowed": False,
    }
