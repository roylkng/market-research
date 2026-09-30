from __future__ import annotations

import bisect
import copy
import math
import statistics
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from scipy.stats import rankdata

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_corporate_actions import (
    action_index,
    blocked_actions,
    validate_action_ledger,
)
from marketlab.alpha_fundamental import FEATURE_NAMES
from marketlab.alpha_model import (
    ModelExample,
    fit_ridge,
    predict_ridge,
)
from marketlab.alpha_trials import require_unopened_registered_trial
from marketlab.marketdata import IndexDailyPrice

T008_TRIAL_ID = "AE001-T008"
T008_REGISTRATION_STATUS = "FROZEN_BEFORE_RETURN_OUTCOMES"
D004_PANEL_SHA256 = (
    "35ba8ea6bb87c9c9e39f79b6f9479114d96535cfefecffed4f713b1a362cb5c5"
)
EXPECTED_UNIVERSE_SHA256 = (
    "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
)
PRIMARY_HORIZON = 20
SECONDARY_HORIZON = 5
RIDGE_L2 = 1.0
MIN_TRAINING_EXAMPLES = 120
MIN_OOS_PER_PERIOD = 60
MIN_COMBINED_PRIMARY_OOS = 120
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 8008
PRIMARY_MEAN_IC_MIN = 0.03
PRIMARY_MEAN_SPREAD_MIN = 0.005
IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")
SESSION_CLOSE_IST = time(15, 30)

FOLDS = (
    {
        "fold_id": "F1",
        "oos_period": "2026-03-31",
        "training_periods": ("2025-09-30", "2025-12-31"),
    },
    {
        "fold_id": "F2",
        "oos_period": "2026-06-30",
        "training_periods": (
            "2025-09-30",
            "2025-12-31",
            "2026-03-31",
        ),
    },
)


def _verify_hashed_payload(
    payload: dict[str, Any],
    *,
    hash_field: str,
    name: str,
) -> None:
    stored = str(payload.get(hash_field) or "")
    unsigned = copy.deepcopy(payload)
    unsigned.pop(hash_field, None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError(f"{name} hash mismatch")


def _parse_utc(value: object, field: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise AlphaContractError(f"{field} is missing")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise AlphaContractError(f"{field} is not ISO datetime") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _market_maps(
    market_panel: dict[str, Any],
) -> tuple[
    list[str],
    dict[str, list[dict[str, Any]]],
    dict[str, IndexDailyPrice],
]:
    _verify_hashed_payload(
        market_panel,
        hash_field="panel_sha256",
        name="T008 market panel",
    )
    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise AlphaContractError("T008 market panel sessions are missing")
    dates = [str(row["session_date"]) for row in sessions]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise AlphaContractError("T008 market sessions are not canonical")

    equities_by_session: dict[str, list[dict[str, Any]]] = {}
    benchmark_by_session: dict[str, IndexDailyPrice] = {}
    for session in sessions:
        day = str(session["session_date"])
        equities = session.get("equities")
        benchmark = session.get("benchmark")
        if not isinstance(equities, list) or not isinstance(benchmark, dict):
            raise AlphaContractError(f"{day}: malformed T008 market session")
        equities_by_session[day] = equities
        benchmark_by_session[day] = IndexDailyPrice(**benchmark)
    return dates, equities_by_session, benchmark_by_session


def _entry_identity(
    rows: list[dict[str, Any]],
    *,
    symbol: str,
) -> tuple[str, str, dict[str, Any]] | None:
    matches = [
        row
        for row in rows
        if str(row.get("symbol") or "").strip().upper() == symbol.upper()
    ]
    if not matches:
        return None
    identities = {
        (
            str(row.get("symbol") or "").strip().upper(),
            str(row.get("isin") or "").strip(),
        )
        for row in matches
    }
    if len(identities) != 1:
        raise AlphaContractError(
            f"{symbol}: T008 entry-session symbol maps to multiple ISINs"
        )
    row = matches[0]
    identity = next(iter(identities))
    return identity[0], identity[1], row


def _session_close_utc(session_date: str) -> datetime:
    day = datetime.fromisoformat(session_date).date()
    return datetime.combine(day, SESSION_CLOSE_IST, IST).astimezone(UTC)


def build_t008_event_labels(
    *,
    d004_panel: dict[str, Any],
    market_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    horizon_sessions: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    if horizon_sessions not in {PRIMARY_HORIZON, SECONDARY_HORIZON}:
        raise AlphaContractError("T008 horizon differs from frozen protocol")
    _verify_hashed_payload(
        d004_panel,
        hash_field="panel_sha256",
        name="T008 D004 panel",
    )
    if d004_panel.get("panel_sha256") != D004_PANEL_SHA256:
        raise AlphaContractError("T008 D004 panel differs from frozen source")
    if d004_panel.get("universe_sha256") != EXPECTED_UNIVERSE_SHA256:
        raise AlphaContractError("T008 D004 universe differs from frozen source")
    if d004_panel.get("return_outcomes_opened") is not False:
        raise AlphaContractError("T008 D004 panel already contains outcomes")
    validate_action_ledger(action_ledger)

    dates, equities_by_session, benchmark_by_session = _market_maps(
        market_panel
    )
    action_by_symbol = action_index(action_ledger)
    coverage_start = str(action_ledger.get("coverage_start_date") or "")
    coverage_end = str(action_ledger.get("coverage_end_date") or "")
    if (
        not coverage_start
        or not coverage_end
        or coverage_start > dates[0]
        or coverage_end < dates[-1]
    ):
        raise AlphaContractError(
            "T008 corporate-action coverage does not span market panel"
        )

    labels: dict[str, dict[str, Any]] = {}
    exclusions: dict[str, int] = defaultdict(int)

    for record in d004_panel.get("records", []):
        if record.get("all_six_features_complete") is not True:
            exclusions["INCOMPLETE_FEATURES"] += 1
            continue
        feature_values = record.get("features")
        if (
            not isinstance(feature_values, dict)
            or set(feature_values) != set(FEATURE_NAMES)
            or any(
                value is None or not math.isfinite(float(value))
                for value in feature_values.values()
            )
        ):
            exclusions["INVALID_FEATURES"] += 1
            continue

        record_sha = str(record.get("record_sha256") or "")
        unsigned = dict(record)
        unsigned.pop("record_sha256", None)
        if not record_sha or digest(unsigned) != record_sha:
            raise AlphaContractError("T008 D004 record hash mismatch")

        published = _parse_utc(
            record.get("target_exchange_published_at_utc"),
            "target_exchange_published_at_utc",
        )
        baseline_published = _parse_utc(
            record.get("baseline_exchange_published_at_utc"),
            "baseline_exchange_published_at_utc",
        )
        if baseline_published >= published:
            exclusions["BASELINE_NOT_PRIOR"] += 1
            continue

        publication_local_date = published.astimezone(IST).date().isoformat()
        entry_index = bisect.bisect_right(dates, publication_local_date)
        if entry_index >= len(dates):
            exclusions["NO_ENTRY_SESSION"] += 1
            continue
        exit_index = entry_index + horizon_sessions - 1
        if exit_index >= len(dates):
            exclusions["LABEL_NOT_MATURE"] += 1
            continue
        entry_session = dates[entry_index]
        exit_session = dates[exit_index]

        identity = _entry_identity(
            equities_by_session[entry_session],
            symbol=str(record["symbol"]),
        )
        if identity is None:
            exclusions["NO_ENTRY_EQ_IDENTITY"] += 1
            continue
        symbol, isin, entry_row = identity

        exit_matches = [
            row
            for row in equities_by_session[exit_session]
            if str(row.get("symbol") or "").strip().upper() == symbol
            and str(row.get("isin") or "").strip() == isin
        ]
        if len(exit_matches) != 1:
            exclusions["EXIT_IDENTITY_MISSING_OR_AMBIGUOUS"] += 1
            continue
        exit_row = exit_matches[0]

        state = action_by_symbol.get(symbol)
        if state is not None and state.get("status") != "READY":
            exclusions["ACTION_AUDIT_UNRESOLVED"] += 1
            continue
        if blocked_actions(
            action_by_symbol,
            symbol=symbol,
            start_exclusive=entry_session,
            end_inclusive=exit_session,
        ):
            exclusions["CORPORATE_ACTION_BLOCKED"] += 1
            continue

        entry_open = float(entry_row["open_price"])
        exit_close = float(exit_row["close_price"])
        benchmark_entry = benchmark_by_session[entry_session]
        benchmark_exit = benchmark_by_session[exit_session]
        if (
            entry_open <= 0
            or exit_close <= 0
            or benchmark_entry.open_price <= 0
            or benchmark_exit.close_price <= 0
        ):
            exclusions["INVALID_PRICE"] += 1
            continue

        stock_return = exit_close / entry_open - 1.0
        benchmark_return = (
            benchmark_exit.close_price / benchmark_entry.open_price - 1.0
        )
        excess = stock_return - benchmark_return
        if not all(
            math.isfinite(value)
            for value in (stock_return, benchmark_return, excess)
        ):
            exclusions["NONFINITE_RETURN"] += 1
            continue

        labels[record_sha] = {
            "record_sha256": record_sha,
            "symbol": symbol,
            "isin": isin,
            "target_period_end": str(record["target_period_end"]),
            "decision_timestamp_utc": published.isoformat(),
            "publication_local_date": publication_local_date,
            "entry_session": entry_session,
            "exit_session": exit_session,
            "exit_close_timestamp_utc": _session_close_utc(
                exit_session
            ).isoformat(),
            "horizon_sessions": horizon_sessions,
            "stock_return": stock_return,
            "benchmark_return": benchmark_return,
            "excess_return": excess,
        }

    return labels, dict(sorted(exclusions.items()))


def _fit_ecdf(
    records: list[dict[str, Any]],
) -> dict[str, tuple[float, ...]]:
    if not records:
        raise AlphaContractError("T008 ECDF training records are empty")
    result = {}
    for feature in FEATURE_NAMES:
        values = sorted(float(row["features"][feature]) for row in records)
        if not values or not all(math.isfinite(value) for value in values):
            raise AlphaContractError(f"T008 invalid ECDF values for {feature}")
        result[feature] = tuple(values)
    return result


def _cdf_transform(
    sorted_values: tuple[float, ...],
    value: float,
) -> float:
    n = len(sorted_values)
    if n == 0:
        raise AlphaContractError("T008 ECDF feature sample is empty")
    left = bisect.bisect_left(sorted_values, value)
    right = bisect.bisect_right(sorted_values, value)
    percentile = (left + 0.5 * (right - left)) / n
    return 2.0 * percentile - 1.0


def _transform_features(
    record: dict[str, Any],
    transform: dict[str, tuple[float, ...]],
) -> dict[str, float]:
    return {
        feature: _cdf_transform(
            transform[feature],
            float(record["features"][feature]),
        )
        for feature in FEATURE_NAMES
    }


def _examples_for_fold(
    *,
    d004_panel: dict[str, Any],
    labels: dict[str, dict[str, Any]],
    fold: dict[str, Any],
    horizon_sessions: int,
    restrict_oos_record_shas: set[str] | None = None,
) -> tuple[list[ModelExample], list[ModelExample], dict[str, Any], list[dict[str, Any]]]:
    records = d004_panel["records"]
    oos_records = [
        row
        for row in records
        if str(row["target_period_end"]) == fold["oos_period"]
        and str(row["record_sha256"]) in labels
        and (
            restrict_oos_record_shas is None
            or str(row["record_sha256"]) in restrict_oos_record_shas
        )
    ]
    if not oos_records:
        raise AlphaContractError(
            f"T008 {fold['fold_id']} has no valid OOS records"
        )
    earliest_oos_publication = min(
        _parse_utc(
            row["target_exchange_published_at_utc"],
            "target_exchange_published_at_utc",
        )
        for row in oos_records
    )

    training_records = []
    for row in records:
        if str(row["target_period_end"]) not in set(fold["training_periods"]):
            continue
        record_sha = str(row["record_sha256"])
        label = labels.get(record_sha)
        if label is None:
            continue
        exit_close = _parse_utc(
            label["exit_close_timestamp_utc"],
            "exit_close_timestamp_utc",
        )
        if exit_close >= earliest_oos_publication:
            continue
        training_records.append(row)

    if len(training_records) < MIN_TRAINING_EXAMPLES:
        raise AlphaContractError(
            f"T008 {fold['fold_id']} horizon {horizon_sessions} has only "
            f"{len(training_records)} mature training examples"
        )

    transform = _fit_ecdf(training_records)

    def make_example(row: dict[str, Any]) -> ModelExample:
        label = labels[str(row["record_sha256"])]
        return ModelExample(
            symbol=label["symbol"],
            isin=label["isin"],
            feature_session=label["publication_local_date"],
            entry_session=label["entry_session"],
            exit_session=label["exit_session"],
            horizon_sessions=horizon_sessions,
            features=_transform_features(row, transform),
            target_excess_return=float(label["excess_return"]),
        )

    training_examples = [make_example(row) for row in training_records]
    oos_examples = [make_example(row) for row in oos_records]
    metadata = {
        "fold_id": fold["fold_id"],
        "oos_period": fold["oos_period"],
        "training_periods": list(fold["training_periods"]),
        "earliest_oos_publication_utc": earliest_oos_publication.isoformat(),
        "training_example_count": len(training_examples),
        "oos_example_count": len(oos_examples),
        "transform_sha256": digest(
            {
                feature: list(values)
                for feature, values in sorted(transform.items())
            }
        ),
    }
    return training_examples, oos_examples, metadata, oos_records


def _period_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) < 4:
        raise AlphaContractError("T008 period metric requires at least four events")
    predictions = np.asarray(
        [float(row["prediction"]) for row in rows],
        dtype=float,
    )
    outcomes = np.asarray(
        [float(row["target_excess_return"]) for row in rows],
        dtype=float,
    )
    if not np.isfinite(predictions).all() or not np.isfinite(outcomes).all():
        raise AlphaContractError("T008 period metric contains nonfinite values")
    pred_rank = rankdata(predictions, method="average")
    outcome_rank = rankdata(outcomes, method="average")
    if np.std(pred_rank) == 0 or np.std(outcome_rank) == 0:
        raise AlphaContractError("T008 period rank is constant")
    rank_ic = float(np.corrcoef(pred_rank, outcome_rank)[0, 1])

    ordered = sorted(
        rows,
        key=lambda row: (
            -float(row["prediction"]),
            str(row["symbol"]),
            str(row["isin"]),
        ),
    )
    bucket = max(1, math.ceil(len(ordered) / 4))
    top = ordered[:bucket]
    bottom = ordered[-bucket:]
    top_mean = statistics.mean(
        float(row["target_excess_return"]) for row in top
    )
    bottom_mean = statistics.mean(
        float(row["target_excess_return"]) for row in bottom
    )
    return {
        "observation_count": len(rows),
        "rank_ic": rank_ic,
        "bucket_size": bucket,
        "top_quartile_mean_excess": top_mean,
        "bottom_quartile_mean_excess": bottom_mean,
        "top_minus_bottom_spread": top_mean - bottom_mean,
    }


def _aggregate_period_metrics(
    by_period: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    expected = {"2026-03-31", "2026-06-30"}
    if set(by_period) != expected:
        raise AlphaContractError(
            f"T008 OOS periods differ from frozen set: {sorted(by_period)}"
        )
    period_metrics = {
        period: _period_metrics(rows)
        for period, rows in sorted(by_period.items())
    }
    return {
        "per_period": period_metrics,
        "mean_rank_ic": statistics.mean(
            value["rank_ic"] for value in period_metrics.values()
        ),
        "mean_top_minus_bottom_spread": statistics.mean(
            value["top_minus_bottom_spread"]
            for value in period_metrics.values()
        ),
        "combined_prediction_count": sum(
            value["observation_count"] for value in period_metrics.values()
        ),
    }


def _symbol_cluster_bootstrap(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)
    symbols = sorted(by_symbol)
    if len(symbols) < 20:
        raise AlphaContractError("T008 bootstrap has too few unique symbols")

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    ic_values = []
    spread_values = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled_indices = rng.integers(0, len(symbols), size=len(symbols))
        replicated = []
        for instance, symbol_index in enumerate(sampled_indices):
            symbol = symbols[int(symbol_index)]
            for row in by_symbol[symbol]:
                replicated.append({**row, "_bootstrap_instance": instance})

        by_period: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in replicated:
            by_period[str(row["target_period_end"])].append(row)
        aggregate = _aggregate_period_metrics(by_period)
        ic_values.append(float(aggregate["mean_rank_ic"]))
        spread_values.append(
            float(aggregate["mean_top_minus_bottom_spread"])
        )

    return {
        "method": "SYMBOL_CLUSTER_PERCENTILE_BOOTSTRAP_V1",
        "seed": BOOTSTRAP_SEED,
        "replicates": BOOTSTRAP_REPLICATES,
        "unique_symbol_count": len(symbols),
        "mean_rank_ic_ci95": [
            float(np.percentile(ic_values, 2.5)),
            float(np.percentile(ic_values, 97.5)),
        ],
        "mean_spread_ci95": [
            float(np.percentile(spread_values, 2.5)),
            float(np.percentile(spread_values, 97.5)),
        ],
    }


def _run_horizon(
    *,
    d004_panel: dict[str, Any],
    labels: dict[str, dict[str, Any]],
    horizon_sessions: int,
    primary_valid_shas: set[str] | None = None,
) -> dict[str, Any]:
    ridge_rows = []
    composite_rows = []
    fold_reports = []
    valid_oos_shas: set[str] = set()

    for fold in FOLDS:
        train, oos, metadata, oos_records = _examples_for_fold(
            d004_panel=d004_panel,
            labels=labels,
            fold=fold,
            horizon_sessions=horizon_sessions,
            restrict_oos_record_shas=primary_valid_shas,
        )
        model = fit_ridge(
            train,
            feature_names=list(FEATURE_NAMES),
            l2=RIDGE_L2,
            model_id=(
                f"AE001-T008-H{horizon_sessions}-{fold['fold_id']}-RIDGE-v1"
            ),
        )
        predictions = predict_ridge(
            model,
            oos,
            prediction_role="OOS",
        )
        if len(predictions) != len(oos_records):
            raise AlphaContractError("T008 OOS prediction count mismatch")

        for prediction, source_record, example in zip(
            predictions,
            oos_records,
            oos,
            strict=True,
        ):
            record_sha = str(source_record["record_sha256"])
            valid_oos_shas.add(record_sha)
            ridge_rows.append(
                {
                    **prediction,
                    "record_sha256": record_sha,
                    "target_period_end": str(
                        source_record["target_period_end"]
                    ),
                }
            )
            composite_rows.append(
                {
                    "symbol": example.symbol,
                    "isin": example.isin,
                    "record_sha256": record_sha,
                    "target_period_end": str(
                        source_record["target_period_end"]
                    ),
                    "prediction": statistics.mean(
                        float(example.features[name])
                        for name in FEATURE_NAMES
                    ),
                    "target_excess_return": example.target_excess_return,
                }
            )

        fold_reports.append(
            {
                **metadata,
                "model_sha256": model.model_sha256,
                "training_last_exit_session": model.training_last_exit_session,
                "ridge_model": asdict(model),
            }
        )

    def group(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            result[str(row["target_period_end"])].append(row)
        return result

    ridge_metrics = _aggregate_period_metrics(group(ridge_rows))
    composite_metrics = _aggregate_period_metrics(group(composite_rows))
    bootstrap = _symbol_cluster_bootstrap(ridge_rows)

    return {
        "horizon_sessions": horizon_sessions,
        "folds": fold_reports,
        "ridge": ridge_metrics,
        "ridge_bootstrap": bootstrap,
        "equal_weight_composite_diagnostic": composite_metrics,
        "oos_predictions": ridge_rows,
        "valid_oos_record_shas": sorted(valid_oos_shas),
    }


def run_t008_trial(
    *,
    d004_panel: dict[str, Any],
    market_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    trial_ledger: dict[str, Any],
) -> dict[str, Any]:
    registration = require_unopened_registered_trial(
        trial_ledger,
        trial_id=T008_TRIAL_ID,
        required_status=T008_REGISTRATION_STATUS,
    )
    primary_labels, primary_exclusions = build_t008_event_labels(
        d004_panel=d004_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        horizon_sessions=PRIMARY_HORIZON,
    )
    secondary_labels, secondary_exclusions = build_t008_event_labels(
        d004_panel=d004_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        horizon_sessions=SECONDARY_HORIZON,
    )

    primary = _run_horizon(
        d004_panel=d004_panel,
        labels=primary_labels,
        horizon_sessions=PRIMARY_HORIZON,
    )
    primary_valid = set(primary["valid_oos_record_shas"])
    secondary = _run_horizon(
        d004_panel=d004_panel,
        labels=secondary_labels,
        horizon_sessions=SECONDARY_HORIZON,
        primary_valid_shas=primary_valid,
    )

    primary_counts = primary["ridge"]["per_period"]
    sample_gates = {
        "each_oos_period_at_least_60": all(
            value["observation_count"] >= MIN_OOS_PER_PERIOD
            for value in primary_counts.values()
        ),
        "combined_primary_oos_at_least_120": (
            primary["ridge"]["combined_prediction_count"]
            >= MIN_COMBINED_PRIMARY_OOS
        ),
        "each_training_fold_at_least_120": all(
            fold["training_example_count"] >= MIN_TRAINING_EXAMPLES
            for fold in primary["folds"]
        ),
    }
    ridge = primary["ridge"]
    bootstrap = primary["ridge_bootstrap"]
    period_values = list(ridge["per_period"].values())
    gates = {
        "fold_1_rank_ic_positive": period_values[0]["rank_ic"] > 0,
        "fold_2_rank_ic_positive": period_values[1]["rank_ic"] > 0,
        "mean_rank_ic_at_least_0_03": (
            ridge["mean_rank_ic"] >= PRIMARY_MEAN_IC_MIN
        ),
        "rank_ic_bootstrap_lower_positive": (
            bootstrap["mean_rank_ic_ci95"][0] > 0
        ),
        "fold_1_spread_positive": (
            period_values[0]["top_minus_bottom_spread"] > 0
        ),
        "fold_2_spread_positive": (
            period_values[1]["top_minus_bottom_spread"] > 0
        ),
        "mean_spread_at_least_50bps": (
            ridge["mean_top_minus_bottom_spread"]
            >= PRIMARY_MEAN_SPREAD_MIN
        ),
        "spread_bootstrap_lower_positive": (
            bootstrap["mean_spread_ci95"][0] > 0
        ),
        "minimum_sample_gates": all(sample_gates.values()),
    }
    primary_supported = all(gates.values())

    report: dict[str, Any] = {
        "schema_version": 1,
        "trial_id": T008_TRIAL_ID,
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "source_panel_sha256": d004_panel["panel_sha256"],
        "market_panel_sha256": market_panel["panel_sha256"],
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "trial_registration_event_sha256": registration["event_sha256"],
        "trial_ledger_sha256": trial_ledger["ledger_sha256"],
        "feature_names": list(FEATURE_NAMES),
        "feature_transform": "TRAINING_ONLY_EMPIRICAL_CDF_CENTERED_V1",
        "entry_rule": (
            "NEXT_NSE_SESSION_OPEN_STRICTLY_AFTER_PUBLICATION_LOCAL_DATE"
        ),
        "primary": {
            key: value
            for key, value in primary.items()
            if key != "valid_oos_record_shas"
        },
        "secondary": {
            key: value
            for key, value in secondary.items()
            if key != "valid_oos_record_shas"
        },
        "primary_label_exclusions": primary_exclusions,
        "secondary_label_exclusions": secondary_exclusions,
        "sample_gates": sample_gates,
        "primary_success_gates": gates,
        "primary_supported": primary_supported,
        "secondary_can_rescue_primary": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
