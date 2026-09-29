from __future__ import annotations

import csv
import io
import math
import statistics
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, FeatureDefinition, digest
from marketlab.alpha_market import DailyEquityObservation
from marketlab.events import sha256_bytes
from marketlab.marketdata import MarketArtifactStore

SEC_BHAVDATA_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/products/content/"
    "sec_bhavdata_full_{ddmmyyyy}.csv"
)
DELIVERY_RECONCILIATION_TOLERANCE_PP = 0.05

DELIVERY_DEFINITIONS = [
    FeatureDefinition(
        "delivery_pct",
        "cash_flows",
        "v1",
        "Current deliverable quantity divided by traded quantity.",
        1,
    ),
    FeatureDefinition(
        "delivery_pct_change_1",
        "cash_flows",
        "v1",
        "Change in delivery fraction from the prior completed session.",
        1,
    ),
    FeatureDefinition(
        "delivery_pct_delta_median_20",
        "cash_flows",
        "v1",
        "Current delivery fraction minus the prior twenty-session median.",
        20,
    ),
    FeatureDefinition(
        "delivery_pct_zscore_20",
        "cash_flows",
        "v1",
        "Current delivery fraction standardized by prior twenty sessions.",
        20,
    ),
    FeatureDefinition(
        "delivery_pct_vol_20",
        "cash_flows",
        "v1",
        "Population standard deviation of prior twenty delivery fractions.",
        20,
    ),
    FeatureDefinition(
        "delivery_qty_surprise_20",
        "cash_flows",
        "v1",
        "Current deliverable quantity divided by prior twenty-session median.",
        20,
    ),
    FeatureDefinition(
        "delivery_value_surprise_20",
        "cash_flows",
        "v1",
        "Current delivered-value proxy divided by prior twenty-session median.",
        20,
    ),
    FeatureDefinition(
        "close_vs_vwap",
        "cash_flows",
        "v1",
        "Current close relative to NSE average traded price.",
        1,
    ),
    FeatureDefinition(
        "vwap_vs_open",
        "cash_flows",
        "v1",
        "NSE average traded price relative to current open.",
        1,
    ),
]


@dataclass(frozen=True)
class DeliveryObservation:
    session_date: str
    symbol: str
    avg_price: float
    traded_qty: float
    turnover_lacs: float
    trade_count: float
    delivery_qty: float | None
    delivery_pct: float | None


class DeliveryAcquisitionError(RuntimeError):
    """Raised when exact NSE delivery evidence cannot be acquired safely."""


def delivery_url(session_date: date) -> str:
    return SEC_BHAVDATA_URL_TEMPLATE.format(
        ddmmyyyy=session_date.strftime("%d%m%Y")
    )


def _number(
    value: object,
    field: str,
    *,
    positive: bool = False,
    allow_missing: bool = False,
) -> float | None:
    raw = str(value or "").strip()
    if allow_missing and raw in {"", "-"}:
        return None
    try:
        parsed = float(raw)
    except (TypeError, ValueError) as exc:
        raise AlphaContractError(f"invalid delivery {field}: {value}") from exc
    if not math.isfinite(parsed):
        raise AlphaContractError(f"delivery {field} must be finite")
    if positive and parsed <= 0:
        raise AlphaContractError(f"delivery {field} must be positive")
    if not positive and parsed < 0:
        raise AlphaContractError(f"delivery {field} cannot be negative")
    return parsed


def parse_sec_bhavdata_full(
    raw_csv: bytes,
    *,
    session_date: date,
) -> list[DeliveryObservation]:
    """Parse NSE full bhavdata delivery fields for EQ securities."""

    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AlphaContractError("delivery CSV must be UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise AlphaContractError("delivery CSV has no header")
    normalized_header = {str(name).strip() for name in reader.fieldnames}
    required = {
        "SYMBOL",
        "SERIES",
        "DATE1",
        "AVG_PRICE",
        "TTL_TRD_QNTY",
        "TURNOVER_LACS",
        "NO_OF_TRADES",
        "DELIV_QTY",
        "DELIV_PER",
    }
    if not required.issubset(normalized_header):
        raise AlphaContractError(
            f"delivery CSV header changed: {sorted(normalized_header)}"
        )

    expected_date = session_date.strftime("%d-%b-%Y").casefold()
    rows = []
    seen: set[str] = set()
    for raw_row in reader:
        row = {
            str(key).strip(): str(value or "").strip()
            for key, value in raw_row.items()
            if key is not None
        }
        if row.get("SERIES", "").upper() != "EQ":
            continue
        symbol = row.get("SYMBOL", "").upper()
        if not symbol:
            raise AlphaContractError("delivery EQ row is missing symbol")
        if symbol in seen:
            raise AlphaContractError(
                f"duplicate delivery EQ symbol on {session_date}: {symbol}"
            )
        seen.add(symbol)
        if row.get("DATE1", "").casefold() != expected_date:
            raise AlphaContractError(
                f"{symbol}: delivery row date does not match {session_date}"
            )
        avg_price = _number(row.get("AVG_PRICE"), "AVG_PRICE", positive=True)
        traded_qty = _number(row.get("TTL_TRD_QNTY"), "TTL_TRD_QNTY")
        turnover_lacs = _number(row.get("TURNOVER_LACS"), "TURNOVER_LACS")
        trade_count = _number(row.get("NO_OF_TRADES"), "NO_OF_TRADES")
        delivery_qty = _number(
            row.get("DELIV_QTY"),
            "DELIV_QTY",
            allow_missing=True,
        )
        delivery_pct = _number(
            row.get("DELIV_PER"),
            "DELIV_PER",
            allow_missing=True,
        )
        assert avg_price is not None
        assert traded_qty is not None
        assert turnover_lacs is not None
        assert trade_count is not None
        if delivery_pct is not None and not 0.0 <= delivery_pct <= 100.0:
            raise AlphaContractError(
                f"{symbol}: delivery percentage outside [0, 100]"
            )
        if delivery_qty is not None and delivery_qty > traded_qty + 1e-9:
            raise AlphaContractError(
                f"{symbol}: delivery quantity exceeds traded quantity"
            )
        rows.append(
            DeliveryObservation(
                session_date=session_date.isoformat(),
                symbol=symbol,
                avg_price=float(avg_price),
                traded_qty=float(traded_qty),
                turnover_lacs=float(turnover_lacs),
                trade_count=float(trade_count),
                delivery_qty=(
                    None if delivery_qty is None else float(delivery_qty)
                ),
                delivery_pct=(
                    None if delivery_pct is None else float(delivery_pct) / 100.0
                ),
            )
        )
    if not rows:
        raise AlphaContractError(f"no delivery EQ rows for {session_date}")
    return sorted(rows, key=lambda row: row.symbol)


def delivery_session_quality(
    rows: list[DeliveryObservation],
) -> dict[str, Any]:
    """Audit whether NSE delivery quantity and percentage are internally coherent.

    The two fields are retained exactly as published. A session with any complete
    EQ row differing by more than the frozen tolerance is excluded wholesale
    rather than selecting one conflicting field as authoritative.
    """

    diffs = []
    for row in rows:
        if (
            row.delivery_qty is None
            or row.delivery_pct is None
            or row.traded_qty <= 0
        ):
            continue
        implied_pct = 100.0 * row.delivery_qty / row.traded_qty
        reported_pct = 100.0 * row.delivery_pct
        diffs.append(abs(implied_pct - reported_pct))
    if not diffs:
        return {
            "status": "EXCLUDE_SESSION_NO_COMPLETE_RECONCILIATION_ROWS",
            "complete_row_count": 0,
            "violating_row_count": 0,
            "max_abs_diff_pp": None,
            "tolerance_pp": DELIVERY_RECONCILIATION_TOLERANCE_PP,
        }
    violating = sum(
        diff > DELIVERY_RECONCILIATION_TOLERANCE_PP for diff in diffs
    )
    return {
        "status": (
            "READY"
            if violating == 0
            else "EXCLUDE_SESSION_INTERNAL_FIELD_INCONSISTENCY"
        ),
        "complete_row_count": len(diffs),
        "violating_row_count": violating,
        "max_abs_diff_pp": max(diffs),
        "tolerance_pp": DELIVERY_RECONCILIATION_TOLERANCE_PP,
    }


def acquire_historical_delivery_panel(
    *,
    session_dates: list[str],
    fetcher,
    store_root: str | Path | None = None,
    captured_at_utc: datetime | None = None,
) -> dict[str, Any]:
    if not session_dates:
        raise DeliveryAcquisitionError("delivery session list cannot be empty")
    if session_dates != sorted(session_dates) or len(session_dates) != len(
        set(session_dates)
    ):
        raise DeliveryAcquisitionError(
            "delivery sessions must be unique and chronological"
        )
    captured = captured_at_utc or datetime.now(UTC)
    if captured.tzinfo is None:
        raise DeliveryAcquisitionError(
            "delivery captured_at_utc must be timezone-aware"
        )
    store = MarketArtifactStore(store_root) if store_root is not None else None
    sessions = []
    for raw_day in session_dates:
        day = date.fromisoformat(raw_day)
        url = delivery_url(day)
        raw = fetcher(url)
        if raw is None:
            raise DeliveryAcquisitionError(
                f"{day}: NSE delivery report is unavailable"
            )
        raw_sha = sha256_bytes(raw)
        if store is not None:
            store.retain(
                raw,
                source_url=url,
                captured_at=captured,
                suffix=".csv",
            )
        try:
            rows = parse_sec_bhavdata_full(raw, session_date=day)
        except AlphaContractError as exc:
            raise DeliveryAcquisitionError(
                f"{day}: NSE delivery report failed parser contract"
            ) from exc
        quality = delivery_session_quality(rows)
        sessions.append(
            {
                "session_date": day.isoformat(),
                "source_url": url,
                "raw_sha256": raw_sha,
                "source_quality": quality,
                "rows": [asdict(row) for row in rows],
            }
        )
    panel: dict[str, Any] = {
        "schema_version": 1,
        "panel_id": "AE001-HISTORICAL-DELIVERY-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "historical_archives_captured_prospectively": False,
        "session_count": len(sessions),
        "source_quality_policy": (
            "EXCLUDE_WHOLE_SESSION_IF_ANY_COMPLETE_EQ_ROW_HAS_"
            "ABS_DELIV_PER_VS_QTY_RATIO_DIFF_GT_0_05_PERCENTAGE_POINTS"
        ),
        "excluded_source_quality_session_count": sum(
            session["source_quality"]["status"] != "READY"
            for session in sessions
        ),
        "excluded_source_quality_sessions": [
            session["session_date"]
            for session in sessions
            if session["source_quality"]["status"] != "READY"
        ],
        "sessions": sessions,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def delivery_features(
    history: list[DeliveryObservation],
    *,
    market_current: DailyEquityObservation,
) -> dict[str, float | None]:
    if len(history) != 21:
        raise AlphaContractError(
            "delivery feature history must contain current plus twenty prior sessions"
        )
    if history[-1].session_date != market_current.session_date:
        raise AlphaContractError("delivery and market current session mismatch")
    current = history[-1]
    prior = history[:-1]
    if current.delivery_pct is None or current.delivery_qty is None:
        raise AlphaContractError("current delivery observation is incomplete")
    if any(
        row.delivery_pct is None or row.delivery_qty is None
        for row in prior
    ):
        raise AlphaContractError("prior delivery history is incomplete")

    prior_pct = [float(row.delivery_pct) for row in prior]
    current_pct = float(current.delivery_pct)
    pct_mean = statistics.mean(prior_pct)
    pct_std = statistics.pstdev(prior_pct)
    prior_qty = [float(row.delivery_qty) for row in prior]
    prior_values = [
        float(row.delivery_qty) * row.avg_price
        for row in prior
    ]
    current_value = float(current.delivery_qty) * current.avg_price
    return {
        "delivery_pct": current_pct,
        "delivery_pct_change_1": (
            current_pct - float(prior[-1].delivery_pct)
        ),
        "delivery_pct_delta_median_20": (
            current_pct - statistics.median(prior_pct)
        ),
        "delivery_pct_zscore_20": (
            None if pct_std == 0.0 else (current_pct - pct_mean) / pct_std
        ),
        "delivery_pct_vol_20": pct_std,
        "delivery_qty_surprise_20": _safe_ratio(
            float(current.delivery_qty),
            statistics.median(prior_qty),
        ),
        "delivery_value_surprise_20": _safe_ratio(
            current_value,
            statistics.median(prior_values),
        ),
        "close_vs_vwap": (
            market_current.close_price / current.avg_price - 1.0
        ),
        "vwap_vs_open": (
            current.avg_price / market_current.open_price - 1.0
        ),
    }


def augment_feature_panel_with_delivery(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    delivery_panel: dict[str, Any],
) -> dict[str, Any]:
    """Augment an action-safe feature panel using delivery-complete common rows."""

    def verify_panel(panel: dict[str, Any], *, name: str) -> None:
        stored = str(panel.get("panel_sha256") or "")
        unsigned = dict(panel)
        unsigned.pop("panel_sha256", None)
        if len(stored) != 64 or digest(unsigned) != stored:
            raise AlphaContractError(f"{name} panel hash mismatch")

    verify_panel(feature_panel, name="feature")
    verify_panel(market_panel, name="market")
    verify_panel(delivery_panel, name="delivery")
    if feature_panel.get("outcomes_attached") is not False:
        raise AlphaContractError("delivery augmentation requires outcome-free features")

    market_sessions = market_panel.get("sessions")
    delivery_sessions = delivery_panel.get("sessions")
    if not isinstance(market_sessions, list) or not isinstance(
        delivery_sessions, list
    ):
        raise AlphaContractError("market/delivery sessions must be lists")
    market_dates = [str(row["session_date"]) for row in market_sessions]
    delivery_dates = [str(row["session_date"]) for row in delivery_sessions]
    if market_dates != delivery_dates:
        raise AlphaContractError(
            "delivery panel session set must exactly match market panel"
        )

    base_definitions = feature_panel.get("feature_definitions")
    if not isinstance(base_definitions, list):
        raise AlphaContractError("base feature definitions are missing")
    definitions = list(base_definitions) + [
        asdict(definition) for definition in DELIVERY_DEFINITIONS
    ]
    names = [str(row["name"]) for row in definitions]
    if len(names) != len(set(names)):
        raise AlphaContractError("delivery features collide with base features")
    definitions.sort(key=lambda row: row["name"])
    feature_set_sha256 = digest(definitions)

    base_rows_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feature_panel.get("rows", []):
        base_rows_by_session[str(row["feature_session"])].append(row)

    histories: dict[
        tuple[str, str], deque[DeliveryObservation]
    ] = defaultdict(lambda: deque(maxlen=21))
    history_indices: dict[tuple[str, str], deque[int]] = defaultdict(
        lambda: deque(maxlen=21)
    )
    result_rows = []
    session_summary = []
    excluded_missing_delivery = 0
    excluded_noncontiguous_delivery = 0
    excluded_source_quality_sessions = [
        str(session["session_date"])
        for session in delivery_sessions
        if not (
            isinstance(session.get("source_quality"), dict)
            and session["source_quality"].get("status") == "READY"
        )
    ]
    source_sha_by_session: dict[str, str] = {}

    for session_index, (market_session, delivery_session) in enumerate(
        zip(market_sessions, delivery_sessions, strict=True)
    ):
        session_date = str(market_session["session_date"])
        source_sha_by_session[session_date] = str(
            delivery_session["raw_sha256"]
        )
        market_by_symbol: dict[str, DailyEquityObservation] = {}
        for raw in market_session.get("equities", []):
            market_row = (
                raw
                if isinstance(raw, DailyEquityObservation)
                else DailyEquityObservation(**raw)
            )
            if market_row.symbol in market_by_symbol:
                raise AlphaContractError(
                    f"{session_date}: duplicate market EQ symbol"
                )
            market_by_symbol[market_row.symbol] = market_row

        delivery_by_symbol = {}
        source_quality = delivery_session.get("source_quality")
        source_ready = (
            isinstance(source_quality, dict)
            and source_quality.get("status") == "READY"
        )
        delivery_rows = (
            delivery_session.get("rows", []) if source_ready else []
        )
        for raw in delivery_rows:
            delivery_row = (
                raw
                if isinstance(raw, DeliveryObservation)
                else DeliveryObservation(**raw)
            )
            if delivery_row.symbol in delivery_by_symbol:
                raise AlphaContractError(
                    f"{session_date}: duplicate delivery symbol"
                )
            delivery_by_symbol[delivery_row.symbol] = delivery_row

        for symbol, market_row in market_by_symbol.items():
            delivery_row = delivery_by_symbol.get(symbol)
            if delivery_row is None:
                continue
            identity = (symbol, market_row.isin)
            histories[identity].append(delivery_row)
            history_indices[identity].append(session_index)

        kept = []
        for base_row in sorted(
            base_rows_by_session.get(session_date, []),
            key=lambda row: (str(row["symbol"]), str(row["isin"])),
        ):
            identity = (str(base_row["symbol"]), str(base_row["isin"]))
            history = list(histories.get(identity, ()))
            indices = list(history_indices.get(identity, ()))
            if len(history) != 21:
                excluded_missing_delivery += 1
                continue
            expected = list(range(session_index - 20, session_index + 1))
            if indices != expected:
                excluded_noncontiguous_delivery += 1
                continue
            market_current = market_by_symbol.get(identity[0])
            if market_current is None or market_current.isin != identity[1]:
                excluded_missing_delivery += 1
                continue
            try:
                new_values = delivery_features(
                    history,
                    market_current=market_current,
                )
            except AlphaContractError:
                excluded_missing_delivery += 1
                continue
            source_window = [
                {
                    "session_date": row.session_date,
                    "delivery_raw_sha256": source_sha_by_session[
                        row.session_date
                    ],
                }
                for row in history
            ]
            updated = {
                **base_row,
                "feature_set_sha256": feature_set_sha256,
                "values": {**base_row["values"], **new_values},
                "delivery_source_window_sha256": digest(source_window),
            }
            kept.append(updated)

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
            session_summary.append(
                {
                    "session_date": session_date,
                    "eligible_count": len(kept),
                    "universe_sha256": universe_sha,
                }
            )

    panel = {
        **{
            key: value
            for key, value in feature_panel.items()
            if key
            not in {
                "panel_sha256",
                "feature_definitions",
                "feature_set_sha256",
                "rows",
                "sessions",
                "feature_row_count",
                "session_count",
            }
        },
        "panel_id": "AE001-HISTORICAL-DELIVERY-AUGMENTED-ACTION-SAFE-v1",
        "base_feature_panel_sha256": feature_panel["panel_sha256"],
        "delivery_panel_sha256": delivery_panel["panel_sha256"],
        "feature_definitions": definitions,
        "feature_set_sha256": feature_set_sha256,
        "delivery_join_contract": (
            "DELIVERY_SYMBOL_EQ_REBOUND_TO_SAME_SESSION_UDIFF_SYMBOL_PLUS_ISIN"
        ),
        "delivery_history_sessions": 21,
        "delivery_source_quality_policy": delivery_panel[
            "source_quality_policy"
        ],
        "delivery_excluded_source_quality_sessions": (
            excluded_source_quality_sessions
        ),
        "delivery_missing_excluded_row_count": excluded_missing_delivery,
        "delivery_noncontiguous_excluded_row_count": (
            excluded_noncontiguous_delivery
        ),
        "session_count": len(session_summary),
        "feature_row_count": len(result_rows),
        "sessions": session_summary,
        "rows": result_rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel
