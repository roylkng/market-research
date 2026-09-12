from __future__ import annotations

import csv
import io
import math
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from marketlab.marketdata import index_snapshot_url, udiff_url

NIFTY_500_INDEX_NAME = "Nifty 500"


class PF001MarketDataError(ValueError):
    """Raised when PF001 official market data cannot be interpreted without guessing."""


class PF001MarketDataMissingRow(PF001MarketDataError):
    """Raised when a valid official file does not contain the required instrument row."""


@dataclass(frozen=True)
class PF001EquityDailyBar:
    symbol: str
    isin: str
    series: str
    session_date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    source_url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def fund_bar(self) -> dict[str, float]:
        return {
            "open": self.open_price,
            "high": self.high_price,
            "low": self.low_price,
            "close": self.close_price,
        }


@dataclass(frozen=True)
class PF001BenchmarkDailyBar:
    benchmark_id: str
    index_name: str
    session_date: str
    open_price: float
    close_price: float
    source_url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def attribution_bar(self) -> dict[str, float]:
        return {"open": self.open_price, "close": self.close_price}


def _positive_float(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise PF001MarketDataError(f"{field} must be a finite positive number")
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise PF001MarketDataError(f"invalid {field}: {value}") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise PF001MarketDataError(f"{field} must be a finite positive number")
    return parsed


def _parse_index_date(raw_date: str) -> date | None:
    for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            parsed = time.strptime(raw_date, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except ValueError:
            continue
    return None


def parse_pf001_udiff_equity(
    raw_zip: bytes,
    *,
    symbol: str,
    session_date: date,
    series: str = "EQ",
    expected_isin: str | None = None,
) -> PF001EquityDailyBar:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = archive.namelist()
            if len(names) != 1 or not names[0].lower().endswith(".csv"):
                raise PF001MarketDataError("UDiFF archive must contain exactly one CSV")
            raw_csv = archive.read(names[0])
    except (zipfile.BadZipFile, KeyError) as exc:
        raise PF001MarketDataError(f"invalid UDiFF bhavcopy ZIP: {exc}") from exc

    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PF001MarketDataError("UDiFF CSV is not UTF-8") from exc

    reader = csv.DictReader(io.StringIO(text))
    required = {
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
    }
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise PF001MarketDataError(
            "UDiFF CSV header does not contain the frozen PF001 OHLC contract"
        )

    wanted_symbol = symbol.strip().upper()
    wanted_series = series.strip().upper()
    day = session_date.isoformat()
    matches: list[dict[str, str]] = []
    for row in reader:
        if (
            str(row.get("TradDt") or "").strip() == day
            and str(row.get("Sgmt") or "").strip().upper() == "CM"
            and str(row.get("Src") or "").strip().upper() == "NSE"
            and str(row.get("FinInstrmTp") or "").strip().upper() == "STK"
            and str(row.get("TckrSymb") or "").strip().upper() == wanted_symbol
            and str(row.get("SctySrs") or "").strip().upper() == wanted_series
        ):
            matches.append(row)

    if not matches:
        raise PF001MarketDataMissingRow(
            f"UDiFF has no row for {wanted_symbol}/{wanted_series} on {day}"
        )
    if len(matches) != 1:
        raise PF001MarketDataError(
            f"expected exactly one UDiFF row for {wanted_symbol}/{wanted_series} on {day}; "
            f"found {len(matches)}"
        )

    row = matches[0]
    isin = str(row.get("ISIN") or "").strip()
    if not isin:
        raise PF001MarketDataError("UDiFF row is missing ISIN")
    if expected_isin and isin != expected_isin:
        raise PF001MarketDataError(
            f"UDiFF ISIN mismatch for {wanted_symbol}: expected={expected_isin}, observed={isin}"
        )

    open_price = _positive_float(row.get("OpnPric"), "UDiFF open price")
    high_price = _positive_float(row.get("HghPric"), "UDiFF high price")
    low_price = _positive_float(row.get("LwPric"), "UDiFF low price")
    close_price = _positive_float(row.get("ClsPric"), "UDiFF close price")
    if low_price > high_price:
        raise PF001MarketDataError("UDiFF low exceeds high")
    if open_price < low_price or open_price > high_price:
        raise PF001MarketDataError("UDiFF open falls outside low/high range")
    if close_price < low_price or close_price > high_price:
        raise PF001MarketDataError("UDiFF close falls outside low/high range")

    return PF001EquityDailyBar(
        symbol=wanted_symbol,
        isin=isin,
        series=wanted_series,
        session_date=day,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        source_url=udiff_url(session_date),
    )


def parse_pf001_nifty500_index(
    raw_csv: bytes,
    *,
    session_date: date,
) -> PF001BenchmarkDailyBar:
    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PF001MarketDataError("index snapshot CSV is not UTF-8") from exc

    reader = csv.DictReader(io.StringIO(text))
    required = {"Index Name", "Index Date", "Open Index Value", "Closing Index Value"}
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise PF001MarketDataError("index snapshot header does not match PF001 contract")

    matches: list[dict[str, str]] = []
    for row in reader:
        name = " ".join(str(row.get("Index Name") or "").split())
        if name.casefold() != NIFTY_500_INDEX_NAME.casefold():
            continue
        observed_date = _parse_index_date(str(row.get("Index Date") or "").strip())
        if observed_date == session_date:
            matches.append(row)

    if not matches:
        raise PF001MarketDataMissingRow(
            f"index snapshot has no row for Nifty 500 on {session_date.isoformat()}"
        )
    if len(matches) != 1:
        raise PF001MarketDataError(
            f"expected exactly one Nifty 500 row on {session_date.isoformat()}; "
            f"found {len(matches)}"
        )

    row = matches[0]
    return PF001BenchmarkDailyBar(
        benchmark_id="nifty_500",
        index_name=NIFTY_500_INDEX_NAME,
        session_date=session_date.isoformat(),
        open_price=_positive_float(row.get("Open Index Value"), "Nifty 500 open"),
        close_price=_positive_float(row.get("Closing Index Value"), "Nifty 500 close"),
        source_url=index_snapshot_url(session_date),
    )
