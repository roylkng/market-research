from __future__ import annotations

import csv
import io
import math
import statistics
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from marketlab.alpha import AlphaContractError

DEFAULT_MEDIAN_PRIOR_20D_TRADED_VALUE_INR = 20_000_000.0


@dataclass(frozen=True)
class DailyEquityObservation:
    session_date: str
    symbol: str
    isin: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    previous_close: float
    volume: float
    turnover_inr: float
    trade_count: float


_REQUIRED_UDIFF_FIELDS = {
    "TradDt",
    "Sgmt",
    "Src",
    "FinInstrmTp",
    "ISIN",
    "TckrSymb",
    "SctySrs",
    "OpnPric",
    "HghPric",
    "LwPric",
    "ClsPric",
    "PrvsClsgPric",
    "TtlTradgVol",
    "TtlTrfVal",
    "TtlNbOfTxsExctd",
}


def _finite(value: object, field: str, *, positive: bool = False) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise AlphaContractError(f"invalid {field}: {value}") from exc
    if not math.isfinite(parsed):
        raise AlphaContractError(f"{field} must be finite")
    if positive and parsed <= 0:
        raise AlphaContractError(f"{field} must be positive")
    if not positive and parsed < 0:
        raise AlphaContractError(f"{field} cannot be negative")
    return parsed


def parse_udiff_eq_panel(raw_zip: bytes, *, session_date: date) -> list[DailyEquityObservation]:
    """Parse all NSE main-board EQ stock rows from one official UDiFF bhavcopy."""

    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = archive.namelist()
            if len(names) != 1 or not names[0].lower().endswith(".csv"):
                raise AlphaContractError("UDiFF archive must contain exactly one CSV")
            raw_csv = archive.read(names[0])
    except (zipfile.BadZipFile, KeyError) as exc:
        raise AlphaContractError(f"invalid UDiFF archive: {exc}") from exc

    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AlphaContractError("UDiFF CSV must be UTF-8") from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not _REQUIRED_UDIFF_FIELDS.issubset(reader.fieldnames):
        raise AlphaContractError("UDiFF header does not satisfy AE001 market feature contract")

    wanted_day = session_date.isoformat()
    rows: list[DailyEquityObservation] = []
    seen: set[tuple[str, str]] = set()
    for row in reader:
        if (
            str(row.get("TradDt") or "").strip() != wanted_day
            or str(row.get("Sgmt") or "").strip().upper() != "CM"
            or str(row.get("Src") or "").strip().upper() != "NSE"
            or str(row.get("FinInstrmTp") or "").strip().upper() != "STK"
            or str(row.get("SctySrs") or "").strip().upper() != "EQ"
        ):
            continue
        symbol = str(row.get("TckrSymb") or "").strip().upper()
        isin = str(row.get("ISIN") or "").strip()
        if not symbol or not isin:
            raise AlphaContractError("UDiFF EQ row requires symbol and ISIN")
        identity = (symbol, isin)
        if identity in seen:
            raise AlphaContractError(f"duplicate UDiFF EQ identity: {symbol}/{isin}")
        seen.add(identity)
        observation = DailyEquityObservation(
            session_date=wanted_day,
            symbol=symbol,
            isin=isin,
            open_price=_finite(row.get("OpnPric"), "open_price", positive=True),
            high_price=_finite(row.get("HghPric"), "high_price", positive=True),
            low_price=_finite(row.get("LwPric"), "low_price", positive=True),
            close_price=_finite(row.get("ClsPric"), "close_price", positive=True),
            previous_close=_finite(
                row.get("PrvsClsgPric"), "previous_close", positive=True
            ),
            volume=_finite(row.get("TtlTradgVol"), "volume"),
            turnover_inr=_finite(row.get("TtlTrfVal"), "turnover_inr"),
            trade_count=_finite(row.get("TtlNbOfTxsExctd"), "trade_count"),
        )
        if not (
            observation.low_price
            <= observation.open_price
            <= observation.high_price
            and observation.low_price
            <= observation.close_price
            <= observation.high_price
        ):
            raise AlphaContractError(f"{symbol}: invalid OHLC ordering")
        rows.append(observation)
    if not rows:
        raise AlphaContractError(f"no NSE EQ rows found for {wanted_day}")
    return sorted(rows, key=lambda row: (row.symbol, row.isin))


def _identity_history(
    observations: Iterable[DailyEquityObservation],
    *,
    symbol: str,
    isin: str,
) -> list[DailyEquityObservation]:
    rows = sorted(
        (
            row
            for row in observations
            if row.symbol == symbol.upper() and row.isin == isin
        ),
        key=lambda row: row.session_date,
    )
    if len({row.session_date for row in rows}) != len(rows):
        raise AlphaContractError(f"duplicate history session for {symbol}/{isin}")
    return rows


def eligible_history_for_ae001(
    history: list[DailyEquityObservation],
    *,
    median_prior_20d_traded_value_inr_min: float = (
        DEFAULT_MEDIAN_PRIOR_20D_TRADED_VALUE_INR
    ),
) -> bool:
    """Check AE001 eligibility from one identity's history ending at the current row."""

    if len(history) < 61:
        return False
    prior = history[:-1]
    median_turnover = statistics.median(row.turnover_inr for row in prior[-20:])
    return median_turnover >= median_prior_20d_traded_value_inr_min


def eligible_for_ae001(
    observations: Iterable[DailyEquityObservation],
    *,
    symbol: str,
    isin: str,
    current_session: str,
    median_prior_20d_traded_value_inr_min: float = (
        DEFAULT_MEDIAN_PRIOR_20D_TRADED_VALUE_INR
    ),
) -> bool:
    history = _identity_history(observations, symbol=symbol, isin=isin)
    current_index = next(
        (index for index, row in enumerate(history) if row.session_date == current_session),
        None,
    )
    if current_index is None:
        return False
    return eligible_history_for_ae001(
        history[: current_index + 1],
        median_prior_20d_traded_value_inr_min=(
            median_prior_20d_traded_value_inr_min
        ),
    )


def build_dynamic_universe(
    observations: Iterable[DailyEquityObservation],
    *,
    current_session: str,
    median_prior_20d_traded_value_inr_min: float = (
        DEFAULT_MEDIAN_PRIOR_20D_TRADED_VALUE_INR
    ),
) -> list[tuple[str, str]]:
    rows = list(observations)
    current = [row for row in rows if row.session_date == current_session]
    eligible = [
        (row.symbol, row.isin)
        for row in current
        if eligible_for_ae001(
            rows,
            symbol=row.symbol,
            isin=row.isin,
            current_session=current_session,
            median_prior_20d_traded_value_inr_min=(
                median_prior_20d_traded_value_inr_min
            ),
        )
    ]
    return sorted(eligible)


def _returns(history: list[DailyEquityObservation]) -> list[float]:
    return [
        history[index].close_price / history[index - 1].close_price - 1.0
        for index in range(1, len(history))
    ]


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def build_price_volume_features_from_history(
    history: list[DailyEquityObservation],
) -> dict[str, float | None]:
    """Build AE001 EOD features from one identity history ending at current session."""

    if len(history) < 61:
        identity = (
            f"{history[-1].symbol}/{history[-1].isin}"
            if history
            else "unknown identity"
        )
        raise AlphaContractError(f"{identity}: fewer than 60 prior sessions")

    current = history[-1]
    prior = history[:-1]
    returns = _returns(history)

    def momentum(sessions: int) -> float:
        return current.close_price / history[-(sessions + 1)].close_price - 1.0

    def realized_vol(sessions: int) -> float:
        return statistics.pstdev(returns[-sessions:])

    def distance_from_high(sessions: int) -> float:
        trailing_high = max(row.high_price for row in history[-sessions:])
        return current.close_price / trailing_high - 1.0

    prior20 = prior[-20:]
    turnover_median_20 = statistics.median(row.turnover_inr for row in prior20)
    volume_median_20 = statistics.median(row.volume for row in prior20)
    trades_median_20 = statistics.median(row.trade_count for row in prior20)

    amihud_terms = []
    for row, daily_return in zip(history[-20:], returns[-20:], strict=True):
        if row.turnover_inr > 0:
            amihud_terms.append(abs(daily_return) / row.turnover_inr)
    amihud_20_scaled = (
        statistics.mean(amihud_terms) * 1_000_000_000.0 if amihud_terms else None
    )

    return {
        "momentum_1": momentum(1),
        "momentum_3": momentum(3),
        "momentum_5": momentum(5),
        "momentum_10": momentum(10),
        "momentum_20": momentum(20),
        "momentum_60": momentum(60),
        "realized_vol_20": realized_vol(20),
        "realized_vol_60": realized_vol(60),
        "distance_from_high_20": distance_from_high(20),
        "distance_from_high_60": distance_from_high(60),
        "overnight_gap": current.open_price / current.previous_close - 1.0,
        "open_to_close": current.close_price / current.open_price - 1.0,
        "intraday_range": (current.high_price - current.low_price) / current.previous_close,
        "turnover_inr": current.turnover_inr,
        "turnover_surprise_20": _safe_ratio(current.turnover_inr, turnover_median_20),
        "volume_surprise_20": _safe_ratio(current.volume, volume_median_20),
        "trade_count_surprise_20": _safe_ratio(current.trade_count, trades_median_20),
        "amihud_20_scaled": amihud_20_scaled,
    }


def build_price_volume_features(
    observations: Iterable[DailyEquityObservation],
    *,
    symbol: str,
    isin: str,
    current_session: str,
) -> dict[str, float | None]:
    """Build the first AE001 EOD feature family for one point-in-time identity."""

    history = _identity_history(observations, symbol=symbol, isin=isin)
    current_index = next(
        (index for index, row in enumerate(history) if row.session_date == current_session),
        None,
    )
    if current_index is None:
        raise AlphaContractError(f"missing current session for {symbol}/{isin}")
    return build_price_volume_features_from_history(history[: current_index + 1])
