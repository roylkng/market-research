from __future__ import annotations

import copy
import math
import statistics
from collections import defaultdict, deque
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_history import historical_market_information_known_at
from marketlab.alpha_market import (
    DailyEquityObservation,
    eligible_history_for_ae001,
)

RG001_PANEL_ID = "AE001-RG001-v1"
REGIME_VARIABLES = (
    "nifty500_return_1",
    "nifty500_return_5",
    "nifty500_return_20",
    "nifty500_return_60",
    "nifty500_realized_vol_20",
    "nifty500_realized_vol_60",
    "nifty500_drawdown_from_60d_high",
    "breadth_advancer_fraction_1",
    "breadth_positive_momentum20_fraction",
    "breadth_median_return_1",
    "breadth_return_dispersion_1",
    "breadth_median_turnover_surprise20",
)


def _verify_market_panel(panel: dict[str, Any]) -> None:
    stored = str(panel.get("panel_sha256") or "")
    unsigned = copy.deepcopy(panel)
    unsigned.pop("panel_sha256", None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError("RG001 market panel hash mismatch")
    if panel.get("live_capital_allowed") is not False:
        raise AlphaContractError("RG001 market panel cannot allow live capital")


def _benchmark_close(session: dict[str, Any]) -> float:
    benchmark = session.get("benchmark")
    if not isinstance(benchmark, dict):
        raise AlphaContractError("RG001 market session lacks benchmark")
    value = float(benchmark.get("close_price"))
    if not math.isfinite(value) or value <= 0:
        raise AlphaContractError("RG001 benchmark close must be finite and positive")
    return value


def _equities(
    session: dict[str, Any],
) -> list[DailyEquityObservation]:
    raw_rows = session.get("equities")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise AlphaContractError("RG001 market session equities are required")
    rows = []
    for raw in raw_rows:
        try:
            row = (
                raw
                if isinstance(raw, DailyEquityObservation)
                else DailyEquityObservation(**raw)
            )
        except TypeError as exc:
            raise AlphaContractError("RG001 malformed equity observation") from exc
        rows.append(row)
    return rows


def _close_return(closes: list[float], lookback: int) -> float:
    if lookback < 1 or len(closes) < lookback + 1:
        raise AlphaContractError("RG001 close-return lookback is invalid")
    return closes[-1] / closes[-(lookback + 1)] - 1.0


def build_rg001_panel(
    market_panel: dict[str, Any],
) -> dict[str, Any]:
    """Build point-in-time market context from the official AE001 market panel."""

    _verify_market_panel(market_panel)
    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or len(sessions) < 61:
        raise AlphaContractError("RG001 requires at least 61 market sessions")
    dates = [str(row.get("session_date") or "") for row in sessions]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise AlphaContractError("RG001 market sessions must be unique and chronological")

    histories: dict[
        tuple[str, str], deque[DailyEquityObservation]
    ] = defaultdict(lambda: deque(maxlen=61))
    history_indices: dict[
        tuple[str, str], deque[int]
    ] = defaultdict(lambda: deque(maxlen=61))
    benchmark_closes: deque[float] = deque(maxlen=61)
    source_window: deque[dict[str, str]] = deque(maxlen=61)
    rows = []

    for session_index, session in enumerate(sessions):
        day = dates[session_index]
        udiff_sha = str(session.get("udiff_sha256") or "")
        benchmark_sha = str(session.get("benchmark_sha256") or "")
        if len(udiff_sha) != 64 or len(benchmark_sha) != 64:
            raise AlphaContractError(f"{day}: RG001 source SHA-256 missing")

        benchmark_closes.append(_benchmark_close(session))
        source_window.append(
            {
                "session_date": day,
                "udiff_sha256": udiff_sha,
                "benchmark_sha256": benchmark_sha,
            }
        )
        current_rows = _equities(session)
        seen: set[tuple[str, str]] = set()
        for observation in current_rows:
            if observation.session_date != day:
                raise AlphaContractError(f"{day}: RG001 equity session mismatch")
            identity = (observation.symbol, observation.isin)
            if identity in seen:
                raise AlphaContractError(f"{day}: RG001 duplicate equity identity")
            seen.add(identity)
            histories[identity].append(observation)
            history_indices[identity].append(session_index)

        if session_index < 60:
            continue
        if len(benchmark_closes) != 61 or len(source_window) != 61:
            raise AlphaContractError("RG001 benchmark/source history gap")

        eligible_histories = []
        expected_indices = list(range(session_index - 60, session_index + 1))
        for identity in sorted(seen):
            history = list(histories[identity])
            indices = list(history_indices[identity])
            if (
                len(history) == 61
                and indices == expected_indices
                and eligible_history_for_ae001(history)
            ):
                eligible_histories.append(history)

        if not eligible_histories:
            raise AlphaContractError(
                f"{day}: RG001 has no dynamically eligible equities"
            )

        benchmark = list(benchmark_closes)
        benchmark_returns = [
            benchmark[index] / benchmark[index - 1] - 1.0
            for index in range(1, len(benchmark))
        ]

        stock_returns_1 = [
            history[-1].close_price / history[-2].close_price - 1.0
            for history in eligible_histories
        ]
        stock_momentum_20 = [
            history[-1].close_price / history[-21].close_price - 1.0
            for history in eligible_histories
        ]
        turnover_surprises = [
            history[-1].turnover_inr
            / statistics.median(row.turnover_inr for row in history[-21:-1])
            for history in eligible_histories
        ]

        values = {
            "nifty500_return_1": _close_return(benchmark, 1),
            "nifty500_return_5": _close_return(benchmark, 5),
            "nifty500_return_20": _close_return(benchmark, 20),
            "nifty500_return_60": _close_return(benchmark, 60),
            "nifty500_realized_vol_20": statistics.pstdev(
                benchmark_returns[-20:]
            ),
            "nifty500_realized_vol_60": statistics.pstdev(
                benchmark_returns[-60:]
            ),
            "nifty500_drawdown_from_60d_high": (
                benchmark[-1] / max(benchmark[-60:]) - 1.0
            ),
            "breadth_advancer_fraction_1": (
                sum(value > 0.0 for value in stock_returns_1)
                / len(stock_returns_1)
            ),
            "breadth_positive_momentum20_fraction": (
                sum(value > 0.0 for value in stock_momentum_20)
                / len(stock_momentum_20)
            ),
            "breadth_median_return_1": statistics.median(stock_returns_1),
            "breadth_return_dispersion_1": statistics.pstdev(stock_returns_1),
            "breadth_median_turnover_surprise20": statistics.median(
                turnover_surprises
            ),
        }
        if set(values) != set(REGIME_VARIABLES):
            raise AlphaContractError("RG001 variable set changed unexpectedly")
        if not all(math.isfinite(float(value)) for value in values.values()):
            raise AlphaContractError("RG001 state contains nonfinite value")

        rows.append(
            {
                "session_date": day,
                "known_at": historical_market_information_known_at(day),
                "eligible_equity_count": len(eligible_histories),
                "source_window_sha256": digest(list(source_window)),
                "values": values,
            }
        )

    panel: dict[str, Any] = {
        "schema_version": 1,
        "panel_id": RG001_PANEL_ID,
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "market_panel_sha256": market_panel["panel_sha256"],
        "historical_archives_captured_prospectively": False,
        "variable_names": list(REGIME_VARIABLES),
        "variable_set_sha256": digest(list(REGIME_VARIABLES)),
        "state_count": len(rows),
        "rows": rows,
        "stock_level_alpha": False,
        "direct_cross_sectional_feature_use": False,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel
