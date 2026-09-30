from __future__ import annotations

import copy
import math
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from scipy import stats

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_diagnostics import _project_examples
from marketlab.alpha_fundamental import FEATURE_NAMES as FUNDAMENTAL_FEATURE_NAMES
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.alpha_model import (
    ModelExample,
    fit_ridge,
    predict_ridge,
)
from marketlab.alpha_multihorizon import build_action_safe_horizon_examples
from marketlab.alpha_trials import require_unopened_registered_trial

TRIAL_ID = "AE001-T008"
TRIAL_STATUS = "FROZEN_BEFORE_OUTCOME_MATERIALIZATION"
TRIAL_MODEL_ID = "AE001-T008-v1"

D004_PANEL_SHA256 = (
    "35ba8ea6bb87c9c9e39f79b6f9479114d96535cfefecffed4f713b1a362cb5c5"
)
UNIVERSE_SHA256 = (
    "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
)
BASE_FEATURE_COUNT = 27
AUGMENTED_FEATURE_COUNT = 33
RIDGE_L2 = 1.0
PRIMARY_HORIZON = 20
SECONDARY_HORIZON = 5
MIN_TRAINING_EVENTS = 100
MIN_VALIDATION_EVENTS = 60
QUINTILE_SHARE = 0.20
BOOTSTRAP_REPETITIONS = 10_000
BOOTSTRAP_SEED = 20260930
MIN_VALID_BOOTSTRAPS = 9_500
IST = ZoneInfo("Asia/Kolkata")
DECISION_CUTOFF = time(18, 30)

FOLDS = (
    {
        "fold": 1,
        "validation_target_period": "2026-03-31",
        "training_target_periods": ("2025-09-30", "2025-12-31"),
    },
    {
        "fold": 2,
        "validation_target_period": "2026-06-30",
        "training_target_periods": (
            "2025-09-30",
            "2025-12-31",
            "2026-03-31",
        ),
    },
)


@dataclass(frozen=True)
class EventMeta:
    target_period_end: str
    target_exchange_published_at_utc: str
    accounting_basis: str
    source_record_sha256: str


def _verify_d004_panel(panel: dict[str, Any]) -> None:
    stored = str(panel.get("panel_sha256") or "")
    unsigned = copy.deepcopy(panel)
    unsigned.pop("panel_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("T008 D004 panel hash mismatch")
    if stored != D004_PANEL_SHA256:
        raise AlphaContractError("T008 D004 panel differs from frozen source")
    if panel.get("diagnostic_id") != "AE001-T008-D004-v1":
        raise AlphaContractError("T008 unexpected source diagnostic")
    if panel.get("universe_sha256") != UNIVERSE_SHA256:
        raise AlphaContractError("T008 D004 universe SHA mismatch")
    if panel.get("return_outcomes_opened") is not False:
        raise AlphaContractError("T008 D004 source contains returns")
    if panel.get("model_fitted") is not False:
        raise AlphaContractError("T008 D004 source contains model fit")
    records = panel.get("records")
    if not isinstance(records, list) or len(records) != 369:
        raise AlphaContractError("T008 D004 frozen record count mismatch")


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise AlphaContractError(
            f"T008 invalid publication timestamp: {value}"
        ) from exc
    if parsed.tzinfo is None:
        raise AlphaContractError("T008 publication timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _decision_cutoff_utc(session_date: str) -> datetime:
    day = date.fromisoformat(session_date)
    return datetime.combine(day, DECISION_CUTOFF, IST).astimezone(UTC)


def map_publication_to_decision_session(
    publication_utc: str,
    session_dates: list[str],
) -> str:
    published = _parse_utc(publication_utc)
    for session in session_dates:
        if _decision_cutoff_utc(session) >= published:
            return session
    raise AlphaContractError(
        "T008 filing publication has no decision session in market support window"
    )


def build_t008_event_feature_panel(
    *,
    d004_panel: dict[str, Any],
    delivery_feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    universe_identity_by_symbol: dict[str, str],
    corporate_action_ledger_sha256: str,
) -> tuple[dict[str, Any], dict[tuple[str, str, str], EventMeta], dict[str, int]]:
    _verify_d004_panel(d004_panel)
    if len(universe_identity_by_symbol) != 100:
        raise AlphaContractError("T008 requires exact frozen 100-member universe map")

    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise AlphaContractError("T008 market sessions are missing")
    session_dates = [str(row["session_date"]) for row in sessions]
    if session_dates != sorted(session_dates):
        raise AlphaContractError("T008 market sessions are not chronological")

    ranked = (
        delivery_feature_panel
        if delivery_feature_panel.get("transform")
        == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(delivery_feature_panel)
    )
    definitions = ranked.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("T008 CORE27 definitions are missing")
    base_names = [str(row["name"]) for row in definitions]
    if len(base_names) != BASE_FEATURE_COUNT or len(set(base_names)) != BASE_FEATURE_COUNT:
        raise AlphaContractError("T008 CORE27 feature count mismatch")
    if set(base_names) & set(FUNDAMENTAL_FEATURE_NAMES):
        raise AlphaContractError("T008 fundamental/base feature-name collision")

    base_lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in ranked.get("rows", []):
        key = (
            str(row["feature_session"]),
            str(row["symbol"]).upper(),
            str(row["isin"]),
        )
        if key in base_lookup:
            raise AlphaContractError(f"T008 duplicate CORE27 row: {key}")
        base_lookup[key] = row

    rows = []
    metadata: dict[tuple[str, str, str], EventMeta] = {}
    exclusions: Counter[str] = Counter()
    seen_source_keys: set[tuple[str, str]] = set()

    for record in d004_panel["records"]:
        symbol = str(record["symbol"]).upper()
        target_period = str(record["target_period_end"])
        source_key = (target_period, symbol)
        if source_key in seen_source_keys:
            raise AlphaContractError(f"T008 duplicate D004 event: {source_key}")
        seen_source_keys.add(source_key)

        isin = universe_identity_by_symbol.get(symbol)
        if not isin:
            exclusions["NO_FROZEN_UNIVERSE_IDENTITY"] += 1
            continue
        decision_session = map_publication_to_decision_session(
            str(record["target_exchange_published_at_utc"]),
            session_dates,
        )
        base = base_lookup.get((decision_session, symbol, isin))
        if base is None:
            exclusions["NO_CORE27_DECISION_ROW"] += 1
            continue

        raw_fund = record.get("features")
        if not isinstance(raw_fund, dict) or set(raw_fund) != set(
            FUNDAMENTAL_FEATURE_NAMES
        ):
            raise AlphaContractError("T008 D004 fundamental feature set mismatch")
        if any(raw_fund[name] is None for name in FUNDAMENTAL_FEATURE_NAMES):
            raise AlphaContractError("T008 D004 complete row has missing fundamental")
        fundamental_values = {
            name: float(raw_fund[name]) for name in FUNDAMENTAL_FEATURE_NAMES
        }
        if not all(math.isfinite(value) for value in fundamental_values.values()):
            raise AlphaContractError("T008 fundamental value is nonfinite")

        base_values = base.get("values")
        if not isinstance(base_values, dict) or set(base_values) != set(base_names):
            raise AlphaContractError("T008 CORE27 event row feature set mismatch")
        values = {
            **{
                name: (
                    None
                    if base_values[name] is None
                    else float(base_values[name])
                )
                for name in base_names
            },
            **fundamental_values,
        }
        key = (decision_session, symbol, isin)
        if key in metadata:
            raise AlphaContractError(
                "T008 two filing events map to the same decision identity"
            )
        metadata[key] = EventMeta(
            target_period_end=target_period,
            target_exchange_published_at_utc=str(
                record["target_exchange_published_at_utc"]
            ),
            accounting_basis=str(record["accounting_basis"]),
            source_record_sha256=str(record["record_sha256"]),
        )
        rows.append(
            {
                "feature_session": decision_session,
                "symbol": symbol,
                "isin": isin,
                "values": values,
                "target_period_end": target_period,
                "target_exchange_published_at_utc": str(
                    record["target_exchange_published_at_utc"]
                ),
                "source_record_sha256": str(record["record_sha256"]),
            }
        )

    panel: dict[str, Any] = {
        "schema_version": 1,
        "panel_id": "AE001-T008-EVENT-FEATURES-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "source_d004_panel_sha256": d004_panel["panel_sha256"],
        "source_core27_panel_sha256": delivery_feature_panel["panel_sha256"],
        "ranked_core27_panel_sha256": ranked["panel_sha256"],
        "corporate_action_ledger_sha256": corporate_action_ledger_sha256,
        "base_feature_names": base_names,
        "fundamental_feature_names": list(FUNDAMENTAL_FEATURE_NAMES),
        "feature_count": len(base_names) + len(FUNDAMENTAL_FEATURE_NAMES),
        "row_count": len(rows),
        "rows": sorted(
            rows,
            key=lambda row: (
                row["target_period_end"],
                row["feature_session"],
                row["symbol"],
                row["isin"],
            ),
        ),
        "exclusions": dict(sorted(exclusions.items())),
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    if panel["feature_count"] != AUGMENTED_FEATURE_COUNT:
        raise AlphaContractError("T008 augmented feature count mismatch")
    panel["panel_sha256"] = digest(panel)
    return panel, metadata, dict(sorted(exclusions.items()))


def _empirical_percentile(value: float, sorted_training: list[float]) -> float:
    if not sorted_training:
        raise AlphaContractError("T008 empirical transform has empty training data")
    left = bisect_left(sorted_training, value)
    right = bisect_right(sorted_training, value)
    return (left + 0.5 * (right - left)) / len(sorted_training)


def _transform_fundamentals(
    training: list[ModelExample],
    validation: list[ModelExample],
    *,
    base_feature_names: list[str],
) -> tuple[list[ModelExample], list[ModelExample], dict[str, Any]]:
    distributions: dict[str, list[float]] = {}
    diagnostics = {}
    for feature in FUNDAMENTAL_FEATURE_NAMES:
        values = sorted(float(row.features[feature]) for row in training)
        if not values or not all(math.isfinite(value) for value in values):
            raise AlphaContractError(
                f"T008 invalid training distribution for {feature}"
            )
        distributions[feature] = values
        diagnostics[feature] = {
            "training_count": len(values),
            "training_min": values[0],
            "training_median": float(np.median(np.asarray(values))),
            "training_max": values[-1],
        }

    def transform(rows: list[ModelExample]) -> list[ModelExample]:
        result = []
        for row in rows:
            features = {
                name: (
                    None
                    if row.features[name] is None
                    else float(row.features[name])
                )
                for name in base_feature_names
            }
            for feature in FUNDAMENTAL_FEATURE_NAMES:
                value = float(row.features[feature])
                features[feature] = _empirical_percentile(
                    value,
                    distributions[feature],
                )
            result.append(
                ModelExample(
                    symbol=row.symbol,
                    isin=row.isin,
                    feature_session=row.feature_session,
                    entry_session=row.entry_session,
                    exit_session=row.exit_session,
                    horizon_sessions=row.horizon_sessions,
                    features=features,
                    target_excess_return=row.target_excess_return,
                )
            )
        return result

    return transform(training), transform(validation), diagnostics


def _spearman(predictions: list[float], targets: list[float]) -> float | None:
    if len(predictions) != len(targets) or len(predictions) < 3:
        return None
    observed = stats.spearmanr(predictions, targets)
    value = float(observed.statistic)
    if not math.isfinite(value):
        return None
    return value


def _event_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) < 5:
        raise AlphaContractError("T008 event metric requires at least five rows")
    predictions = [float(row["prediction"]) for row in rows]
    targets = [float(row["target_excess_return"]) for row in rows]
    rank_ic = _spearman(predictions, targets)
    if rank_ic is None:
        raise AlphaContractError("T008 event rank IC is undefined")
    ordered = sorted(
        rows,
        key=lambda row: (
            -float(row["prediction"]),
            str(row["symbol"]),
            str(row["isin"]),
        ),
    )
    bucket = max(1, math.ceil(len(ordered) * QUINTILE_SHARE))
    top = ordered[:bucket]
    bottom = ordered[-bucket:]
    top_mean = float(np.mean([float(row["target_excess_return"]) for row in top]))
    bottom_mean = float(
        np.mean([float(row["target_excess_return"]) for row in bottom])
    )
    return {
        "event_count": len(rows),
        "rank_ic": rank_ic,
        "quintile_count": bucket,
        "top_quintile_mean_excess": top_mean,
        "bottom_quintile_mean_excess": bottom_mean,
        "top_minus_bottom_quintile_spread": top_mean - bottom_mean,
        "mean_prediction": float(np.mean(predictions)),
    }


def _decision_week(session_date: str) -> str:
    day = date.fromisoformat(session_date)
    monday = day.fromordinal(day.toordinal() - day.weekday())
    return monday.isoformat()


def _paired_rows(
    base: list[dict[str, Any]],
    augmented: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    def index(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
        result = {}
        for row in rows:
            key = (
                str(row["feature_session"]),
                str(row["symbol"]),
                str(row["isin"]),
            )
            if key in result:
                raise AlphaContractError("T008 duplicate prediction identity")
            result[key] = row
        return result

    left = index(base)
    right = index(augmented)
    if left.keys() != right.keys():
        raise AlphaContractError("T008 base/augmented OOS identities differ")
    paired = []
    for key in sorted(left):
        base_row = left[key]
        aug_row = right[key]
        if float(base_row["target_excess_return"]) != float(
            aug_row["target_excess_return"]
        ):
            raise AlphaContractError("T008 paired prediction targets differ")
        paired.append(
            {
                "feature_session": key[0],
                "decision_week": _decision_week(key[0]),
                "symbol": key[1],
                "isin": key[2],
                "target_excess_return": float(base_row["target_excess_return"]),
                "base_prediction": float(base_row["prediction"]),
                "augmented_prediction": float(aug_row["prediction"]),
            }
        )
    return paired


def _metrics_from_paired(
    rows: list[dict[str, Any]],
    *,
    prediction_field: str,
) -> dict[str, Any]:
    projected = [
        {
            "feature_session": row["feature_session"],
            "symbol": row["symbol"],
            "isin": row["isin"],
            "prediction": row[prediction_field],
            "target_excess_return": row["target_excess_return"],
        }
        for row in rows
    ]
    return _event_metrics(projected)


def _fold_delta(rows: list[dict[str, Any]]) -> dict[str, Any]:
    base = _metrics_from_paired(rows, prediction_field="base_prediction")
    augmented = _metrics_from_paired(
        rows,
        prediction_field="augmented_prediction",
    )
    return {
        "event_count": len(rows),
        "base": base,
        "augmented": augmented,
        "delta_rank_ic": augmented["rank_ic"] - base["rank_ic"],
        "delta_quintile_spread": (
            augmented["top_minus_bottom_quintile_spread"]
            - base["top_minus_bottom_quintile_spread"]
        ),
        "mean_augmented_minus_base_prediction": float(
            np.mean(
                [
                    row["augmented_prediction"] - row["base_prediction"]
                    for row in rows
                ]
            )
        ),
        "decision_week_count": len({row["decision_week"] for row in rows}),
    }


def _weighted_delta(
    fold_deltas: list[dict[str, Any]],
    field: str,
) -> float:
    total = sum(int(row["event_count"]) for row in fold_deltas)
    if total <= 0:
        raise AlphaContractError("T008 pooled event count is zero")
    return sum(
        int(row["event_count"]) * float(row[field])
        for row in fold_deltas
    ) / total


def _cluster_bootstrap(
    fold_rows: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rank_deltas = []
    spread_deltas = []

    grouped_folds = []
    for rows in fold_rows:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[row["decision_week"]].append(row)
        cluster_names = sorted(groups)
        if len(cluster_names) < 3:
            raise AlphaContractError(
                "T008 bootstrap requires at least three decision-week clusters per fold"
            )
        grouped_folds.append((cluster_names, groups))

    for _ in range(BOOTSTRAP_REPETITIONS):
        sampled_fold_deltas = []
        valid = True
        for cluster_names, groups in grouped_folds:
            sampled_names = rng.choice(
                cluster_names,
                size=len(cluster_names),
                replace=True,
            )
            sampled_rows = []
            for name in sampled_names.tolist():
                sampled_rows.extend(groups[str(name)])
            try:
                sampled_fold_deltas.append(_fold_delta(sampled_rows))
            except AlphaContractError:
                valid = False
                break
        if not valid:
            continue
        rank_deltas.append(
            _weighted_delta(sampled_fold_deltas, "delta_rank_ic")
        )
        spread_deltas.append(
            _weighted_delta(sampled_fold_deltas, "delta_quintile_spread")
        )

    valid_count = len(rank_deltas)
    if valid_count != len(spread_deltas):
        raise AlphaContractError("T008 bootstrap metric count mismatch")
    if valid_count < MIN_VALID_BOOTSTRAPS:
        raise AlphaContractError(
            f"T008 valid bootstrap repetitions below frozen minimum: {valid_count}"
        )

    rank = np.asarray(rank_deltas, dtype=float)
    spread = np.asarray(spread_deltas, dtype=float)
    return {
        "seed": BOOTSTRAP_SEED,
        "requested_repetitions": BOOTSTRAP_REPETITIONS,
        "valid_repetitions": valid_count,
        "cluster": "DECISION_ISO_WEEK",
        "rank_ic_delta": {
            "mean": float(rank.mean()),
            "ci95_low": float(np.quantile(rank, 0.025)),
            "ci95_high": float(np.quantile(rank, 0.975)),
        },
        "quintile_spread_delta": {
            "mean": float(spread.mean()),
            "ci95_low": float(np.quantile(spread, 0.025)),
            "ci95_high": float(np.quantile(spread, 0.975)),
        },
    }


def _run_horizon(
    *,
    horizon: int,
    examples: list[ModelExample],
    metadata: dict[tuple[str, str, str], EventMeta],
    base_feature_names: list[str],
) -> dict[str, Any]:
    fold_reports = []
    fold_paired_rows = []

    for spec in FOLDS:
        validation_period = str(spec["validation_target_period"])
        training_periods = set(spec["training_target_periods"])

        validation = [
            row
            for row in examples
            if metadata[
                (row.feature_session, row.symbol, row.isin)
            ].target_period_end
            == validation_period
        ]
        if len(validation) < MIN_VALIDATION_EVENTS:
            raise AlphaContractError(
                f"T008 H{horizon} fold {spec['fold']} has fewer than "
                f"{MIN_VALIDATION_EVENTS} validation events"
            )
        earliest_validation_session = min(
            row.feature_session for row in validation
        )
        training = [
            row
            for row in examples
            if metadata[
                (row.feature_session, row.symbol, row.isin)
            ].target_period_end
            in training_periods
            and row.exit_session < earliest_validation_session
        ]
        if len(training) < MIN_TRAINING_EVENTS:
            raise AlphaContractError(
                f"T008 H{horizon} fold {spec['fold']} has fewer than "
                f"{MIN_TRAINING_EVENTS} purged training events"
            )

        transformed_train, transformed_validation, transform_diag = (
            _transform_fundamentals(
                training,
                validation,
                base_feature_names=base_feature_names,
            )
        )
        base_train = _project_examples(
            transformed_train,
            base_feature_names,
        )
        base_validation = _project_examples(
            transformed_validation,
            base_feature_names,
        )
        augmented_names = [
            *base_feature_names,
            *FUNDAMENTAL_FEATURE_NAMES,
        ]
        base_model = fit_ridge(
            base_train,
            feature_names=base_feature_names,
            l2=RIDGE_L2,
            model_id=(
                f"AE001-T008-H{horizon}-F{spec['fold']:02d}-CORE27"
            ),
        )
        augmented_model = fit_ridge(
            transformed_train,
            feature_names=augmented_names,
            l2=RIDGE_L2,
            model_id=(
                f"AE001-T008-H{horizon}-F{spec['fold']:02d}-CORE33F"
            ),
        )
        base_predictions = predict_ridge(
            base_model,
            base_validation,
            prediction_role="OOS",
        )
        augmented_predictions = predict_ridge(
            augmented_model,
            transformed_validation,
            prediction_role="OOS",
        )
        paired = _paired_rows(base_predictions, augmented_predictions)
        fold_delta = _fold_delta(paired)
        fold_paired_rows.append(paired)

        fold_reports.append(
            {
                "fold": spec["fold"],
                "validation_target_period": validation_period,
                "training_target_periods": sorted(training_periods),
                "earliest_validation_decision_session": (
                    earliest_validation_session
                ),
                "training_event_count": len(training),
                "validation_event_count": len(validation),
                "training_last_exit_session": max(
                    row.exit_session for row in training
                ),
                "base_model_sha256": base_model.model_sha256,
                "augmented_model_sha256": augmented_model.model_sha256,
                "base_coefficients": dict(
                    zip(
                        base_model.feature_names,
                        base_model.coefficients,
                        strict=True,
                    )
                ),
                "augmented_coefficients": dict(
                    zip(
                        augmented_model.feature_names,
                        augmented_model.coefficients,
                        strict=True,
                    )
                ),
                "fundamental_transform": transform_diag,
                **fold_delta,
            }
        )

    pooled_rank = _weighted_delta(fold_reports, "delta_rank_ic")
    pooled_spread = _weighted_delta(
        fold_reports,
        "delta_quintile_spread",
    )
    bootstrap = _cluster_bootstrap(fold_paired_rows)
    supported = (
        all(float(row["delta_rank_ic"]) > 0.0 for row in fold_reports)
        and all(
            float(row["delta_quintile_spread"]) > 0.0
            for row in fold_reports
        )
        and pooled_rank > 0.0
        and bootstrap["rank_ic_delta"]["ci95_low"] > 0.0
        and pooled_spread > 0.0
        and bootstrap["quintile_spread_delta"]["ci95_low"] > 0.0
    )
    return {
        "horizon_sessions": horizon,
        "folds": fold_reports,
        "pooled_weighted_delta_rank_ic": pooled_rank,
        "pooled_weighted_delta_quintile_spread": pooled_spread,
        "cluster_bootstrap": bootstrap,
        "endpoint_supported": supported,
    }


def run_t008_trial(
    *,
    d004_panel: dict[str, Any],
    delivery_feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    universe_identity_by_symbol: dict[str, str],
    trial_ledger: dict[str, Any],
) -> dict[str, Any]:
    registration = require_unopened_registered_trial(
        trial_ledger,
        trial_id=TRIAL_ID,
        required_status=TRIAL_STATUS,
    )
    payload = registration["payload"]
    if payload["source_panel"]["panel_sha256"] != D004_PANEL_SHA256:
        raise AlphaContractError("T008 trial registration source SHA mismatch")
    if payload["primary"]["horizon_sessions"] != PRIMARY_HORIZON:
        raise AlphaContractError("T008 primary horizon differs from registration")
    if payload["secondary"]["horizon_sessions"] != SECONDARY_HORIZON:
        raise AlphaContractError("T008 secondary horizon differs from registration")
    if float(payload["model"]["l2"]) != RIDGE_L2:
        raise AlphaContractError("T008 ridge l2 differs from registration")

    event_panel, metadata, join_exclusions = build_t008_event_feature_panel(
        d004_panel=d004_panel,
        delivery_feature_panel=delivery_feature_panel,
        market_panel=market_panel,
        universe_identity_by_symbol=universe_identity_by_symbol,
        corporate_action_ledger_sha256=action_ledger["ledger_sha256"],
    )
    examples_by_horizon, label_exclusions = build_action_safe_horizon_examples(
        feature_panel=event_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        horizons=(SECONDARY_HORIZON, PRIMARY_HORIZON),
    )
    base_feature_names = list(event_panel["base_feature_names"])

    primary = _run_horizon(
        horizon=PRIMARY_HORIZON,
        examples=examples_by_horizon[PRIMARY_HORIZON],
        metadata=metadata,
        base_feature_names=base_feature_names,
    )
    secondary = _run_horizon(
        horizon=SECONDARY_HORIZON,
        examples=examples_by_horizon[SECONDARY_HORIZON],
        metadata=metadata,
        base_feature_names=base_feature_names,
    )

    period_counts = Counter(
        meta.target_period_end for meta in metadata.values()
    )
    basis_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for meta in metadata.values():
        basis_counts[meta.target_period_end][meta.accounting_basis] += 1

    report: dict[str, Any] = {
        "schema_version": 1,
        "trial_id": TRIAL_ID,
        "model_id": TRIAL_MODEL_ID,
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "trial_registration_event_sha256": registration["event_sha256"],
        "trial_ledger_sha256": trial_ledger["ledger_sha256"],
        "source": {
            "d004_panel_sha256": d004_panel["panel_sha256"],
            "core27_delivery_panel_sha256": delivery_feature_panel[
                "panel_sha256"
            ],
            "market_panel_sha256": market_panel["panel_sha256"],
            "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
            "event_feature_panel_sha256": event_panel["panel_sha256"],
            "joined_event_count": event_panel["row_count"],
            "join_exclusions": join_exclusions,
            "label_exclusions": label_exclusions,
            "joined_period_counts": dict(sorted(period_counts.items())),
            "joined_basis_counts": {
                period: dict(sorted(counts.items()))
                for period, counts in sorted(basis_counts.items())
            },
        },
        "feature_contract": {
            "base": "CORE27",
            "augmented": "CORE33_FUND",
            "base_feature_names": base_feature_names,
            "fundamental_feature_names": list(FUNDAMENTAL_FEATURE_NAMES),
            "fundamental_transform": (
                "PURGED_TRAINING_EMPIRICAL_PERCENTILE"
            ),
        },
        "primary_20d": primary,
        "secondary_5d": secondary,
        "interpretation": (
            "PRIMARY_20D_SUPPORTED"
            if primary["endpoint_supported"]
            else "PRIMARY_20D_NOT_SUPPORTED"
        ),
        "secondary_may_rescue_primary": False,
        "prospective_claim_allowed": False,
        "historical_delivery_publication_timing_verified": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
