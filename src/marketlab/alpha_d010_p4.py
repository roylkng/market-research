from __future__ import annotations

import math
import statistics
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any

from marketlab.alpha import AlphaContractError, FeatureDefinition, digest
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS

D010_P4_ID = "AE001-D010-P4-v1"
SHORT_P3B_REPORT_SHA256 = (
    "0cc1f518d8c91d4648851d55861cee66cca722c0e1858204cbdd6635f7c98528"
)
SLB_P3_REPORT_SHA256 = (
    "e41e749a9d0514ffc4a01af6dd923d6c838e898320bf0e4f0e699bafc9d8dd27"
)
MIN_FEATURE_SESSIONS = 200
MIN_FEATURE_ROWS = 100_000

D010_DEFINITIONS = [
    FeatureDefinition(
        "short_volume_share_lag1",
        "cash_flows",
        "v1",
        "Reported D-1 short-selling quantity divided by D-1 cash traded volume.",
        1,
        1,
    ),
    FeatureDefinition(
        "short_volume_share_change_1",
        "cash_flows",
        "v1",
        "Change in lagged short-selling volume share from the prior publication session.",
        20,
        1,
    ),
    FeatureDefinition(
        "short_volume_share_zscore_20",
        "cash_flows",
        "v1",
        "Lagged short-selling volume share standardized against prior 20 source-valid sessions.",
        20,
        1,
    ),
    FeatureDefinition(
        "slb_outstanding_days_volume20",
        "cash_flows",
        "v1",
        "Current total SLB outstanding quantity divided by prior-20-session median cash volume.",
        20,
        0,
    ),
    FeatureDefinition(
        "slb_outstanding_change_days_volume20",
        "cash_flows",
        "v1",
        "Change in total SLB outstanding quantity divided by prior-20-session median cash volume.",
        20,
        0,
    ),
    FeatureDefinition(
        "slb_outstanding_zscore_20",
        "cash_flows",
        "v1",
        "Current total SLB outstanding quantity standardized against prior 20 source-valid sessions.",
        20,
        0,
    ),
    FeatureDefinition(
        "slb_active_series_count",
        "cash_flows",
        "v1",
        "Count of distinct SLB contract series with outstanding positions for the identity.",
        1,
        0,
    ),
]


@dataclass(frozen=True)
class D010Observation:
    session_date: str
    symbol: str
    isin: str
    short_volume_share_lag1: float
    slb_outstanding_quantity: float
    slb_active_series_count: int
    cash_volume: float


def _verify_panel(
    panel: dict[str, Any],
    *,
    expected_id: str | None,
    name: str,
) -> None:
    stored = str(panel.get("panel_sha256") or "")
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError(f"{name} panel hash mismatch")
    if expected_id is not None and panel.get("panel_id") != expected_id:
        raise AlphaContractError(f"unexpected {name} panel id")


def _market_maps(
    market_panel: dict[str, Any],
) -> tuple[
    list[str],
    dict[str, dict[str, DailyEquityObservation]],
    dict[str, dict[str, DailyEquityObservation]],
]:
    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise AlphaContractError("D010 P4 market sessions are required")
    dates = [str(row["session_date"]) for row in sessions]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise AlphaContractError(
            "D010 P4 market sessions must be unique and chronological"
        )
    by_symbol: dict[str, dict[str, DailyEquityObservation]] = {}
    by_isin: dict[str, dict[str, DailyEquityObservation]] = {}
    for session in sessions:
        day = str(session["session_date"])
        symbol_map: dict[str, DailyEquityObservation] = {}
        isin_map: dict[str, DailyEquityObservation] = {}
        for raw in session.get("equities", []):
            row = (
                raw
                if isinstance(raw, DailyEquityObservation)
                else DailyEquityObservation(**raw)
            )
            if row.symbol in symbol_map or row.isin in isin_map:
                raise AlphaContractError(
                    f"{day}: duplicate symbol or ISIN in D010 P4 market panel"
                )
            symbol_map[row.symbol] = row
            isin_map[row.isin] = row
        by_symbol[day] = symbol_map
        by_isin[day] = isin_map
    return dates, by_symbol, by_isin


def _source_maps(
    *,
    short_panel: dict[str, Any],
    slb_panel: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    _verify_panel(
        short_panel,
        expected_id="AE001-D010-P3B-SHORT-PANEL-v1",
        name="D010 short",
    )
    _verify_panel(
        slb_panel,
        expected_id="AE001-D010-P3-SOURCE-PANEL-v1",
        name="D010 SLB",
    )
    if short_panel.get("report_sha256") != SHORT_P3B_REPORT_SHA256:
        raise AlphaContractError("D010 P4 short source is not bound to P3B")
    if slb_panel.get("report_sha256") != SLB_P3_REPORT_SHA256:
        raise AlphaContractError("D010 P4 SLB source is not bound to P3")

    short_sessions = short_panel.get("sessions")
    slb_sessions = slb_panel.get("sessions")
    if not isinstance(short_sessions, list) or not isinstance(slb_sessions, list):
        raise AlphaContractError("D010 P4 source sessions must be lists")

    short_by_day = {
        str(row["publication_session"]): row
        for row in short_sessions
    }
    slb_by_day = {
        str(row["session_date"]): row
        for row in slb_sessions
    }
    if len(short_by_day) != len(short_sessions):
        raise AlphaContractError("duplicate D010 short publication session")
    if len(slb_by_day) != len(slb_sessions):
        raise AlphaContractError("duplicate D010 SLB session")
    return short_by_day, slb_by_day


def _zscore(current: float, prior: list[float]) -> float | None:
    if len(prior) != 20:
        raise AlphaContractError("D010 z-score requires 20 prior observations")
    std = statistics.pstdev(prior)
    if std == 0.0:
        return None
    return (current - statistics.mean(prior)) / std


def d010_features(history: list[D010Observation]) -> dict[str, float | None]:
    if len(history) != 21:
        raise AlphaContractError(
            "D010 feature history requires current plus 20 prior sessions"
        )
    current = history[-1]
    prior = history[:-1]
    prior_short = [row.short_volume_share_lag1 for row in prior]
    prior_slb = [row.slb_outstanding_quantity for row in prior]
    prior_volume = [row.cash_volume for row in prior]
    median_volume = statistics.median(prior_volume)
    if median_volume <= 0:
        raise AlphaContractError("D010 prior-20 median cash volume must be positive")

    return {
        "short_volume_share_lag1": current.short_volume_share_lag1,
        "short_volume_share_change_1": (
            current.short_volume_share_lag1
            - prior[-1].short_volume_share_lag1
        ),
        "short_volume_share_zscore_20": _zscore(
            current.short_volume_share_lag1,
            prior_short,
        ),
        "slb_outstanding_days_volume20": (
            current.slb_outstanding_quantity / median_volume
        ),
        "slb_outstanding_change_days_volume20": (
            current.slb_outstanding_quantity
            - prior[-1].slb_outstanding_quantity
        )
        / median_volume,
        "slb_outstanding_zscore_20": _zscore(
            current.slb_outstanding_quantity,
            prior_slb,
        ),
        "slb_active_series_count": float(current.slb_active_series_count),
    }


def _normalized_source_observations(
    *,
    market_panel: dict[str, Any],
    short_panel: dict[str, Any],
    slb_panel: dict[str, Any],
) -> tuple[
    list[str],
    dict[str, dict[tuple[str, str], D010Observation]],
    dict[str, dict[str, Any]],
]:
    dates, _, market_by_isin = _market_maps(market_panel)
    date_index = {value: index for index, value in enumerate(dates)}
    short_by_day, slb_by_day = _source_maps(
        short_panel=short_panel,
        slb_panel=slb_panel,
    )

    observations: dict[
        str, dict[tuple[str, str], D010Observation]
    ] = {}
    session_meta: dict[str, dict[str, Any]] = {}

    for day in dates:
        short_session = short_by_day.get(day)
        slb_session = slb_by_day.get(day)
        if short_session is None or slb_session is None:
            continue
        slb_source = slb_session.get("slb_open_positions")
        if not isinstance(slb_source, dict):
            raise AlphaContractError(f"{day}: missing SLB source object")
        short_ready = short_session.get("source_status") == "READY"
        slb_ready = slb_source.get("source_status") == "READY"
        if not (short_ready and slb_ready):
            session_meta[day] = {
                "source_ready": False,
                "short_status": short_session.get("source_status"),
                "slb_status": slb_source.get("source_status"),
            }
            continue

        position = date_index[day]
        if position < 1:
            raise AlphaContractError(
                f"{day}: D010 publication session has no previous market session"
            )
        trade_day = dates[position - 1]
        if str(short_session.get("trade_session")) != trade_day:
            raise AlphaContractError(
                f"{day}: D010 short trade session is not previous completed session"
            )

        short_qty_by_isin: dict[str, float] = {}
        for row in short_session.get("rows", []):
            if (
                row.get("trade_date_identity_status") != "MAPPED_EQ"
                or row.get("publication_continuity_status") != "SAME_ISIN_PRESENT"
            ):
                continue
            isin = str(row.get("trade_date_mapped_isin") or "")
            if not isin:
                raise AlphaContractError(f"{day}: mapped short row lacks ISIN")
            if isin in short_qty_by_isin:
                raise AlphaContractError(
                    f"{day}: duplicate mapped short-selling ISIN {isin}"
                )
            short_qty_by_isin[isin] = float(row["quantity"])

        slb_qty_by_isin: dict[str, float] = defaultdict(float)
        slb_series_by_isin: dict[str, set[str]] = defaultdict(set)
        seen_slb: set[tuple[str, str]] = set()
        for row in slb_source.get("rows", []):
            if row.get("identity_status") != "MAPPED_EQ":
                continue
            isin = str(row.get("mapped_isin") or "")
            series = str(row.get("series") or "")
            if not isin or not series:
                raise AlphaContractError(f"{day}: mapped SLB row lacks identity/series")
            key = (isin, series)
            if key in seen_slb:
                raise AlphaContractError(
                    f"{day}: duplicate SLB ISIN+series {key}"
                )
            seen_slb.add(key)
            slb_qty_by_isin[isin] += float(row["outstanding_quantity"])
            slb_series_by_isin[isin].add(series)

        current_by_isin = market_by_isin[day]
        trade_by_isin = market_by_isin[trade_day]
        session_rows: dict[tuple[str, str], D010Observation] = {}
        for isin, current in current_by_isin.items():
            previous = trade_by_isin.get(isin)
            if previous is None or previous.volume <= 0 or current.volume <= 0:
                continue
            short_qty = short_qty_by_isin.get(isin, 0.0)
            if short_qty < 0:
                raise AlphaContractError("negative D010 short quantity")
            slb_qty = slb_qty_by_isin.get(isin, 0.0)
            active_series = len(slb_series_by_isin.get(isin, set()))
            observation = D010Observation(
                session_date=day,
                symbol=current.symbol,
                isin=isin,
                short_volume_share_lag1=short_qty / previous.volume,
                slb_outstanding_quantity=slb_qty,
                slb_active_series_count=active_series,
                cash_volume=current.volume,
            )
            session_rows[(current.symbol, isin)] = observation

        observations[day] = session_rows
        session_meta[day] = {
            "source_ready": True,
            "short_raw_sha256": short_session.get("raw_sha256"),
            "slb_raw_sha256": slb_source.get("raw_sha256"),
            "short_trade_session": trade_day,
            "short_nonzero_identity_count": sum(
                row.short_volume_share_lag1 > 0
                for row in session_rows.values()
            ),
            "slb_nonzero_identity_count": sum(
                row.slb_outstanding_quantity > 0
                for row in session_rows.values()
            ),
        }
    return dates, observations, session_meta


def augment_feature_panel_with_d010(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    short_panel: dict[str, Any],
    slb_panel: dict[str, Any],
) -> dict[str, Any]:
    _verify_panel(feature_panel, expected_id=None, name="D010 base feature")
    _verify_panel(market_panel, expected_id=None, name="D010 market")
    if feature_panel.get("outcomes_attached") is not False:
        raise AlphaContractError("D010 P4 requires an outcome-free base feature panel")

    base_definitions = feature_panel.get("feature_definitions")
    if not isinstance(base_definitions, list):
        raise AlphaContractError("D010 P4 base feature definitions are missing")
    base_names = {str(row["name"]) for row in base_definitions}
    frozen_base = {definition.name for definition in PRICE_VOLUME_DEFINITIONS}
    if base_names != frozen_base:
        raise AlphaContractError(
            "D010 P4 requires the frozen 18-feature price/liquidity base panel"
        )

    definitions = list(base_definitions) + [
        asdict(definition) for definition in D010_DEFINITIONS
    ]
    definitions.sort(key=lambda row: row["name"])
    names = [str(row["name"]) for row in definitions]
    if len(names) != 25 or len(names) != len(set(names)):
        raise AlphaContractError("D010 P4 feature set must contain exactly 25 features")
    feature_set_sha256 = digest(definitions)

    dates, source_observations, source_meta = _normalized_source_observations(
        market_panel=market_panel,
        short_panel=short_panel,
        slb_panel=slb_panel,
    )
    date_index = {value: index for index, value in enumerate(dates)}

    base_rows_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feature_panel.get("rows", []):
        base_rows_by_session[str(row["feature_session"])].append(row)

    histories: dict[tuple[str, str], deque[D010Observation]] = defaultdict(
        lambda: deque(maxlen=21)
    )
    history_indices: dict[tuple[str, str], deque[int]] = defaultdict(
        lambda: deque(maxlen=21)
    )

    result_rows = []
    session_summaries = []
    excluded_source_gap_rows = 0
    excluded_identity_history_rows = 0
    null_counts = {definition.name: 0 for definition in D010_DEFINITIONS}

    for day in dates:
        position = date_index[day]
        current_source_rows = source_observations.get(day)
        if current_source_rows is not None:
            for identity, observation in current_source_rows.items():
                histories[identity].append(observation)
                history_indices[identity].append(position)

        kept = []
        for base_row in sorted(
            base_rows_by_session.get(day, []),
            key=lambda row: (str(row["symbol"]), str(row["isin"])),
        ):
            identity = (str(base_row["symbol"]), str(base_row["isin"]))
            history = list(histories.get(identity, ()))
            indices = list(history_indices.get(identity, ()))
            if current_source_rows is None:
                excluded_source_gap_rows += 1
                continue
            expected = list(range(position - 20, position + 1))
            if len(history) != 21 or indices != expected:
                excluded_identity_history_rows += 1
                continue
            if history[-1].symbol != identity[0] or history[-1].isin != identity[1]:
                excluded_identity_history_rows += 1
                continue

            new_values = d010_features(history)
            for name, value in new_values.items():
                if value is None:
                    null_counts[name] += 1
                elif not math.isfinite(float(value)):
                    raise AlphaContractError(
                        f"{day}/{identity}: nonfinite D010 feature {name}"
                    )
            source_window = [
                {
                    "session_date": observation.session_date,
                    "short_volume_share_lag1": observation.short_volume_share_lag1,
                    "slb_outstanding_quantity": observation.slb_outstanding_quantity,
                    "slb_active_series_count": observation.slb_active_series_count,
                }
                for observation in history
            ]
            kept.append(
                {
                    **base_row,
                    "feature_set_sha256": feature_set_sha256,
                    "values": {
                        **base_row["values"],
                        **new_values,
                    },
                    "d010_source_window_sha256": digest(source_window),
                }
            )

        if kept:
            universe_sha = digest(
                [
                    {"symbol": row["symbol"], "isin": row["isin"]}
                    for row in kept
                ]
            )
            for row in kept:
                row["universe_sha256"] = universe_sha
                result_rows.append(row)
            meta = source_meta.get(day, {})
            session_summaries.append(
                {
                    "session_date": day,
                    "eligible_count": len(kept),
                    "universe_sha256": universe_sha,
                    "short_raw_sha256": meta.get("short_raw_sha256"),
                    "slb_raw_sha256": meta.get("slb_raw_sha256"),
                    "short_trade_session": meta.get("short_trade_session"),
                    "short_nonzero_identity_count": meta.get(
                        "short_nonzero_identity_count"
                    ),
                    "slb_nonzero_identity_count": meta.get(
                        "slb_nonzero_identity_count"
                    ),
                }
            )

    panel: dict[str, Any] = {
        **{
            key: value
            for key, value in feature_panel.items()
            if key not in {
                "panel_sha256",
                "feature_definitions",
                "feature_set_sha256",
                "rows",
                "sessions",
                "feature_row_count",
                "session_count",
            }
        },
        "panel_id": "AE001-D010-P4-AUGMENTED-FEATURE-PANEL-v1",
        "evidence_class": (
            "HISTORICAL_RECONSTRUCTION_DEVELOPMENT_"
            "SOURCE_TIMING_UNVERIFIED"
        ),
        "base_feature_panel_sha256": feature_panel["panel_sha256"],
        "market_panel_sha256": market_panel["panel_sha256"],
        "short_source_panel_sha256": short_panel["panel_sha256"],
        "slb_source_panel_sha256": slb_panel["panel_sha256"],
        "short_p3b_report_sha256": SHORT_P3B_REPORT_SHA256,
        "slb_p3_report_sha256": SLB_P3_REPORT_SHA256,
        "feature_definitions": definitions,
        "feature_set_sha256": feature_set_sha256,
        "feature_semantics_id": D010_P4_ID,
        "history_sessions": 21,
        "source_gap_policy": "BREAK_WINDOW_NO_IMPUTATION",
        "session_count": len(session_summaries),
        "feature_row_count": len(result_rows),
        "excluded_source_gap_row_count": excluded_source_gap_rows,
        "excluded_identity_history_row_count": excluded_identity_history_rows,
        "d010_null_counts": null_counts,
        "sessions": session_summaries,
        "rows": result_rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def summarize_p4(panel: dict[str, Any]) -> dict[str, Any]:
    _verify_panel(
        panel,
        expected_id="AE001-D010-P4-AUGMENTED-FEATURE-PANEL-v1",
        name="D010 P4 augmented",
    )
    definitions = panel.get("feature_definitions")
    rows = panel.get("rows")
    sessions = panel.get("sessions")
    if not isinstance(definitions, list) or not isinstance(rows, list):
        raise AlphaContractError("D010 P4 panel is malformed")
    if not isinstance(sessions, list):
        raise AlphaContractError("D010 P4 session summaries are malformed")

    d010_names = [definition.name for definition in D010_DEFINITIONS]
    values_by_feature: dict[str, list[float]] = {
        name: [] for name in d010_names
    }
    for row in rows:
        values = row.get("values")
        if not isinstance(values, dict):
            raise AlphaContractError("D010 P4 row values are malformed")
        for name in d010_names:
            value = values.get(name)
            if value is None:
                continue
            parsed = float(value)
            if not math.isfinite(parsed):
                raise AlphaContractError("D010 P4 summary found nonfinite feature")
            values_by_feature[name].append(parsed)

    feature_stats = {}
    for name, values in values_by_feature.items():
        feature_stats[name] = {
            "non_null_count": len(values),
            "null_count": len(rows) - len(values),
            "nonzero_count": sum(value != 0.0 for value in values),
            "nonzero_fraction_of_non_null": (
                sum(value != 0.0 for value in values) / len(values)
                if values
                else None
            ),
            "min": min(values) if values else None,
            "median": statistics.median(values) if values else None,
            "max": max(values) if values else None,
        }

    passes = (
        len(definitions) == 25
        and len(sessions) >= MIN_FEATURE_SESSIONS
        and len(rows) >= MIN_FEATURE_ROWS
        and panel.get("outcomes_attached") is False
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D010_P4_ID,
        "evidence_class": panel["evidence_class"],
        "status": (
            "PROMOTE_INCREMENTAL_ALPHA_TRIAL"
            if passes
            else "P4_FEATURE_MATERIALIZATION_FAILED"
        ),
        "feature_count": len(definitions),
        "feature_session_count": len(sessions),
        "feature_row_count": len(rows),
        "feature_stats": feature_stats,
        "excluded_source_gap_row_count": panel[
            "excluded_source_gap_row_count"
        ],
        "excluded_identity_history_row_count": panel[
            "excluded_identity_history_row_count"
        ],
        "panel_sha256": panel["panel_sha256"],
        "short_source_panel_sha256": panel["short_source_panel_sha256"],
        "slb_source_panel_sha256": panel["slb_source_panel_sha256"],
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
