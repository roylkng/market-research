from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, FeatureDefinition, digest
from marketlab.alpha_futures import fo_udiff_url
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_options_source import OptionContractObservation
from marketlab.alpha_options_source_d006 import (
    parse_fo_udiff_stock_options_d006,
)
from marketlab.events import sha256_bytes
from marketlab.marketdata import MarketArtifactStore

T009_NEAR_ATM_ABS_MONEYNESS = 0.05
T009_MAX_NEAREST_ABS_MONEYNESS = 0.10
T009_MIN_PAIRED_STRIKES = 3

OPTIONS_DEFINITIONS = [
    FeatureDefinition(
        "opt_front_log1p_days_to_expiry",
        "derivatives_flows",
        "v1",
        "Log one plus calendar days to front stock-option expiry.",
        1,
    ),
    FeatureDefinition(
        "opt_nearest_abs_moneyness",
        "derivatives_flows",
        "v1",
        "Absolute moneyness of nearest front-expiry paired strike.",
        1,
    ),
    FeatureDefinition(
        "opt_atm_straddle_fraction",
        "derivatives_flows",
        "v1",
        "Nearest paired call plus put settlement divided by cash close.",
        1,
    ),
    FeatureDefinition(
        "opt_atm_put_call_premium_imbalance",
        "derivatives_flows",
        "v1",
        "Nearest paired put-minus-call premium over their premium sum.",
        1,
    ),
    FeatureDefinition(
        "opt_paired_put_call_oi_imbalance",
        "derivatives_flows",
        "v1",
        "Paired front-expiry put-minus-call OI over paired total OI.",
        1,
    ),
    FeatureDefinition(
        "opt_paired_put_call_volume_imbalance",
        "derivatives_flows",
        "v1",
        "Paired front-expiry put-minus-call contracts over paired volume.",
        1,
    ),
    FeatureDefinition(
        "opt_paired_put_call_change_oi_imbalance",
        "derivatives_flows",
        "v1",
        "Put-minus-call aggregate OI change over sum absolute OI changes.",
        1,
    ),
    FeatureDefinition(
        "opt_paired_total_oi_change_fraction",
        "derivatives_flows",
        "v1",
        "Aggregate paired current OI change divided by reconstructed prior OI.",
        1,
    ),
    FeatureDefinition(
        "opt_near_atm_oi_share",
        "derivatives_flows",
        "v1",
        "Paired CE+PE OI within five percent moneyness over paired total OI.",
        1,
    ),
    FeatureDefinition(
        "opt_near_atm_volume_share",
        "derivatives_flows",
        "v1",
        "Paired CE+PE contracts within five percent moneyness over paired volume.",
        1,
    ),
]


class OptionsAcquisitionError(RuntimeError):
    """Raised when T009 historical options evidence cannot be acquired safely."""


def options_features(
    contracts: list[OptionContractObservation],
    *,
    market_current: DailyEquityObservation,
) -> dict[str, float]:
    if not contracts:
        raise AlphaContractError("T009 stock-option contracts are missing")
    if any(
        row.session_date != market_current.session_date
        or row.symbol != market_current.symbol
        for row in contracts
    ):
        raise AlphaContractError(
            "T009 options/cash session or symbol identity mismatch"
        )

    day = date.fromisoformat(market_current.session_date)
    valid = [
        row
        for row in contracts
        if date.fromisoformat(row.expiry_date) > day
    ]
    if not valid:
        raise AlphaContractError("T009 has no strictly future option expiry")
    front_expiry = min(row.expiry_date for row in valid)
    front = [row for row in valid if row.expiry_date == front_expiry]

    calls: dict[float, OptionContractObservation] = {}
    puts: dict[float, OptionContractObservation] = {}
    for row in front:
        target = calls if row.option_type == "CE" else puts
        if row.strike_price in target:
            raise AlphaContractError(
                "T009 duplicate logical contract survived D006 parser"
            )
        target[row.strike_price] = row

    paired = sorted(set(calls) & set(puts))
    if len(paired) < T009_MIN_PAIRED_STRIKES:
        raise AlphaContractError(
            "T009 requires at least three paired front-expiry strikes"
        )

    cash_close = float(market_current.close_price)
    if not math.isfinite(cash_close) or cash_close <= 0:
        raise AlphaContractError("T009 cash close must be positive")
    nearest = min(
        paired,
        key=lambda strike: (
            abs(strike / cash_close - 1.0),
            strike,
        ),
    )
    nearest_abs_moneyness = abs(nearest / cash_close - 1.0)
    if nearest_abs_moneyness > T009_MAX_NEAREST_ABS_MONEYNESS:
        raise AlphaContractError(
            "T009 nearest paired strike exceeds frozen moneyness limit"
        )

    days_to_expiry = (date.fromisoformat(front_expiry) - day).days
    if days_to_expiry <= 0:
        raise AlphaContractError("T009 front expiry is not strictly future")

    nearest_call = calls[nearest]
    nearest_put = puts[nearest]
    atm_premium_sum = (
        nearest_call.settlement_price + nearest_put.settlement_price
    )
    if atm_premium_sum <= 0:
        raise AlphaContractError("T009 ATM premium sum is non-positive")

    call_oi = sum(calls[strike].open_interest for strike in paired)
    put_oi = sum(puts[strike].open_interest for strike in paired)
    total_oi = call_oi + put_oi
    if total_oi <= 0:
        raise AlphaContractError("T009 paired total OI is non-positive")

    call_volume = sum(calls[strike].traded_contracts for strike in paired)
    put_volume = sum(puts[strike].traded_contracts for strike in paired)
    total_volume = call_volume + put_volume

    call_change_oi = sum(
        calls[strike].change_in_open_interest for strike in paired
    )
    put_change_oi = sum(
        puts[strike].change_in_open_interest for strike in paired
    )
    change_abs_denominator = abs(call_change_oi) + abs(put_change_oi)

    total_change_oi = call_change_oi + put_change_oi
    prior_total_oi = total_oi - total_change_oi
    if prior_total_oi <= 0:
        raise AlphaContractError(
            "T009 reconstructed paired prior OI is non-positive"
        )

    near_atm = [
        strike
        for strike in paired
        if abs(strike / cash_close - 1.0)
        <= T009_NEAR_ATM_ABS_MONEYNESS
    ]
    near_atm_oi = sum(
        calls[strike].open_interest + puts[strike].open_interest
        for strike in near_atm
    )
    near_atm_volume = sum(
        calls[strike].traded_contracts + puts[strike].traded_contracts
        for strike in near_atm
    )

    result = {
        "opt_front_log1p_days_to_expiry": math.log1p(days_to_expiry),
        "opt_nearest_abs_moneyness": nearest_abs_moneyness,
        "opt_atm_straddle_fraction": atm_premium_sum / cash_close,
        "opt_atm_put_call_premium_imbalance": (
            nearest_put.settlement_price
            - nearest_call.settlement_price
        )
        / atm_premium_sum,
        "opt_paired_put_call_oi_imbalance": (
            put_oi - call_oi
        )
        / total_oi,
        "opt_paired_put_call_volume_imbalance": (
            0.0
            if total_volume == 0
            else (put_volume - call_volume) / total_volume
        ),
        "opt_paired_put_call_change_oi_imbalance": (
            0.0
            if change_abs_denominator == 0
            else (put_change_oi - call_change_oi)
            / change_abs_denominator
        ),
        "opt_paired_total_oi_change_fraction": (
            total_change_oi / prior_total_oi
        ),
        "opt_near_atm_oi_share": near_atm_oi / total_oi,
        "opt_near_atm_volume_share": (
            0.0
            if total_volume == 0
            else near_atm_volume / total_volume
        ),
    }
    if any(not math.isfinite(float(value)) for value in result.values()):
        raise AlphaContractError("T009 derived option feature is nonfinite")
    return result


def acquire_historical_options_panel(
    *,
    session_dates: list[str],
    fetcher,
    store_root: str | Path | None = None,
    captured_at_utc: datetime | None = None,
) -> dict[str, Any]:
    if not session_dates:
        raise OptionsAcquisitionError(
            "T009 options session list cannot be empty"
        )
    if (
        session_dates != sorted(session_dates)
        or len(session_dates) != len(set(session_dates))
    ):
        raise OptionsAcquisitionError(
            "T009 options sessions must be unique and chronological"
        )
    captured = captured_at_utc or datetime.now(UTC)
    if captured.tzinfo is None:
        raise OptionsAcquisitionError(
            "T009 captured_at_utc must be timezone-aware"
        )
    store = MarketArtifactStore(store_root) if store_root is not None else None

    sessions = []
    source_hashes = []
    for session_text in session_dates:
        day = date.fromisoformat(session_text)
        url = fo_udiff_url(day)
        raw = fetcher(url)
        if raw is None:
            sessions.append(
                {
                    "session_date": session_text,
                    "status": "UNAVAILABLE",
                    "source_url": url,
                    "raw_sha256": None,
                    "diagnostics": None,
                    "rows": [],
                }
            )
            continue

        raw_sha = sha256_bytes(raw)
        source_hashes.append(
            {"session_date": session_text, "raw_sha256": raw_sha}
        )
        if store is not None:
            store.retain(
                raw,
                source_url=url,
                captured_at=captured,
                suffix=".zip",
            )
        try:
            rows, diagnostics = parse_fo_udiff_stock_options_d006(
                raw,
                session_date=day,
            )
        except AlphaContractError as exc:
            sessions.append(
                {
                    "session_date": session_text,
                    "status": "PARSER_REJECTED",
                    "source_url": url,
                    "raw_sha256": raw_sha,
                    "diagnostics": {"error": str(exc)},
                    "rows": [],
                }
            )
            continue

        sessions.append(
            {
                "session_date": session_text,
                "status": "READY",
                "source_url": url,
                "raw_sha256": raw_sha,
                "diagnostics": {
                    **asdict(diagnostics),
                },
                "rows": [asdict(row) for row in rows],
            }
        )

    panel: dict[str, Any] = {
        "schema_version": 1,
        "panel_id": "AE001-HISTORICAL-STOCK-OPTIONS-D006-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "source_contract": "AE001-D006-v1",
        "historical_archive_publication_timestamps_verified": False,
        "session_count": len(sessions),
        "ready_session_count": sum(
            row["status"] == "READY" for row in sessions
        ),
        "unavailable_session_count": sum(
            row["status"] == "UNAVAILABLE" for row in sessions
        ),
        "parser_rejected_session_count": sum(
            row["status"] == "PARSER_REJECTED" for row in sessions
        ),
        "source_hashes_sha256": digest(source_hashes),
        "sessions": sessions,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def augment_feature_panel_with_options(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    options_panel: dict[str, Any],
) -> dict[str, Any]:
    def verify(panel: dict[str, Any], *, name: str) -> None:
        stored = str(panel.get("panel_sha256") or "")
        unsigned = dict(panel)
        unsigned.pop("panel_sha256", None)
        if len(stored) != 64 or digest(unsigned) != stored:
            raise AlphaContractError(f"{name} panel hash mismatch")

    verify(feature_panel, name="T009 base feature")
    verify(market_panel, name="T009 market")
    verify(options_panel, name="T009 options")
    if feature_panel.get("outcomes_attached") is not False:
        raise AlphaContractError(
            "T009 options augmentation requires outcome-free features"
        )

    market_sessions = market_panel.get("sessions")
    options_sessions = options_panel.get("sessions")
    if not isinstance(market_sessions, list) or not isinstance(
        options_sessions, list
    ):
        raise AlphaContractError("T009 market/options sessions are required")
    market_dates = [str(row["session_date"]) for row in market_sessions]
    options_dates = [str(row["session_date"]) for row in options_sessions]
    if market_dates != options_dates:
        raise AlphaContractError(
            "T009 options panel session set must exactly match market panel"
        )

    base_definitions = feature_panel.get("feature_definitions")
    if not isinstance(base_definitions, list):
        raise AlphaContractError("T009 base feature definitions are missing")
    definitions = list(base_definitions) + [
        asdict(definition) for definition in OPTIONS_DEFINITIONS
    ]
    names = [str(row["name"]) for row in definitions]
    if len(names) != len(set(names)):
        raise AlphaContractError("T009 options features collide with base")
    definitions.sort(key=lambda row: row["name"])
    feature_set_sha256 = digest(definitions)

    base_rows_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feature_panel.get("rows", []):
        base_rows_by_session[str(row["feature_session"])].append(row)

    result_rows = []
    session_summary = []
    excluded: dict[str, int] = defaultdict(int)

    for market_session, options_session in zip(
        market_sessions,
        options_sessions,
        strict=True,
    ):
        session_text = str(market_session["session_date"])
        base_rows = base_rows_by_session.get(session_text, [])
        if options_session["status"] != "READY":
            excluded[f"SESSION_{options_session['status']}"] += len(base_rows)
            continue

        market_by_symbol: dict[str, DailyEquityObservation] = {}
        for raw in market_session.get("equities", []):
            row = (
                raw
                if isinstance(raw, DailyEquityObservation)
                else DailyEquityObservation(**raw)
            )
            if row.symbol in market_by_symbol:
                raise AlphaContractError(
                    f"{session_text}: duplicate T009 cash symbol"
                )
            market_by_symbol[row.symbol] = row

        contracts_by_symbol: dict[
            str, list[OptionContractObservation]
        ] = defaultdict(list)
        for raw in options_session.get("rows", []):
            row = (
                raw
                if isinstance(raw, OptionContractObservation)
                else OptionContractObservation(**raw)
            )
            contracts_by_symbol[row.symbol].append(row)

        kept = []
        for base_row in sorted(
            base_rows,
            key=lambda row: (
                str(row["symbol"]),
                str(row["isin"]),
            ),
        ):
            symbol = str(base_row["symbol"])
            isin = str(base_row["isin"])
            market_current = market_by_symbol.get(symbol)
            if market_current is None or market_current.isin != isin:
                excluded["CASH_IDENTITY_MISMATCH"] += 1
                continue
            contracts = contracts_by_symbol.get(symbol)
            if not contracts:
                excluded["NO_STOCK_OPTIONS"] += 1
                continue
            try:
                new_values = options_features(
                    contracts,
                    market_current=market_current,
                )
            except AlphaContractError as exc:
                reason = str(exc)
                if "strictly future" in reason:
                    excluded["NO_STRICTLY_FUTURE_EXPIRY"] += 1
                elif "three paired" in reason:
                    excluded["INSUFFICIENT_PAIRED_STRIKES"] += 1
                elif "moneyness" in reason:
                    excluded["NO_NEAR_ATM_PAIRED_STRIKE"] += 1
                elif "prior OI" in reason:
                    excluded["NONPOSITIVE_PAIRED_PRIOR_OI"] += 1
                elif "total OI" in reason:
                    excluded["NONPOSITIVE_PAIRED_TOTAL_OI"] += 1
                else:
                    excluded["INVALID_OPTION_STRUCTURE"] += 1
                continue

            updated = {
                **base_row,
                "feature_set_sha256": feature_set_sha256,
                "values": {
                    **base_row["values"],
                    **new_values,
                },
                "options_source_sha256": options_session["raw_sha256"],
            }
            kept.append(updated)

        if kept:
            universe_sha = digest(
                [
                    {
                        "symbol": row["symbol"],
                        "isin": row["isin"],
                    }
                    for row in kept
                ]
            )
            for row in kept:
                row["universe_sha256"] = universe_sha
                result_rows.append(row)
            session_summary.append(
                {
                    "session_date": session_text,
                    "eligible_count": len(kept),
                    "universe_sha256": universe_sha,
                    "options_raw_sha256": options_session["raw_sha256"],
                }
            )

    panel: dict[str, Any] = {
        **{
            key: value
            for key, value in feature_panel.items()
            if key
            not in {
                "panel_sha256",
                "panel_id",
                "feature_definitions",
                "feature_set_sha256",
                "rows",
                "sessions",
                "feature_row_count",
                "session_count",
            }
        },
        "panel_id": "AE001-HISTORICAL-OPTIONS-AUGMENTED-v1",
        "base_feature_panel_sha256": feature_panel["panel_sha256"],
        "options_panel_sha256": options_panel["panel_sha256"],
        "options_source_hashes_sha256": options_panel[
            "source_hashes_sha256"
        ],
        "feature_definitions": definitions,
        "feature_set_sha256": feature_set_sha256,
        "options_join_contract": (
            "SAME_SESSION_FO_STO_SYMBOL_TO_CM_EQ_SYMBOL_PLUS_ISIN"
        ),
        "options_contract_selection": (
            "D006_VALID_ROWS_STRICTLY_FUTURE_FRONT_EXPIRY_PAIRED_STRIKES"
        ),
        "exclusion_counts": dict(sorted(excluded.items())),
        "session_count": len(session_summary),
        "feature_row_count": len(result_rows),
        "sessions": session_summary,
        "rows": result_rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel
