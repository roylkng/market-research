from __future__ import annotations

import csv
import io
import math
import statistics
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_futures import fo_udiff_url
from marketlab.alpha_market import DailyEquityObservation
from marketlab.events import sha256_bytes
from marketlab.marketdata import MarketArtifactStore

D005_MIN_PAIRED_STRIKES = 3
D005_MAX_ATM_ABS_MONEYNESS = 0.10


@dataclass(frozen=True)
class OptionContractObservation:
    session_date: str
    symbol: str
    financial_instrument_id: str
    expiry_date: str
    strike_price: float
    option_type: str
    settlement_price: float
    previous_close: float
    underlying_price: float | None
    open_interest: float
    change_in_open_interest: float
    traded_contracts: float
    transferred_value_inr: float
    trade_count: float
    board_lot: float


class OptionsSourceError(RuntimeError):
    """Raised when D005 stock-options source acquisition is unusable."""


def _finite(
    value: object,
    field: str,
    *,
    positive: bool = False,
    nonnegative: bool = False,
    allow_missing: bool = False,
) -> float | None:
    raw = str(value or "").strip()
    if allow_missing and raw == "":
        return None
    try:
        parsed = float(raw)
    except (TypeError, ValueError) as exc:
        raise AlphaContractError(f"invalid option {field}: {value}") from exc
    if not math.isfinite(parsed):
        raise AlphaContractError(f"option {field} must be finite")
    if positive and parsed <= 0:
        raise AlphaContractError(f"option {field} must be positive")
    if nonnegative and parsed < 0:
        raise AlphaContractError(f"option {field} cannot be negative")
    return parsed


def parse_fo_udiff_stock_options(
    raw_zip: bytes,
    *,
    session_date: date,
) -> tuple[list[OptionContractObservation], dict[str, Any]]:
    """Parse valid NSE UDiFF stock-option rows without computing alpha features."""

    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = archive.namelist()
            if len(names) != 1 or not names[0].lower().endswith(".csv"):
                raise AlphaContractError(
                    "FO UDiFF archive must contain exactly one CSV"
                )
            raw_csv = archive.read(names[0])
    except (zipfile.BadZipFile, KeyError) as exc:
        raise AlphaContractError(f"invalid FO UDiFF archive: {exc}") from exc

    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AlphaContractError("FO UDiFF CSV must be UTF-8") from exc

    reader = csv.DictReader(io.StringIO(text))
    required = {
        "TradDt",
        "Sgmt",
        "Src",
        "FinInstrmTp",
        "FinInstrmId",
        "TckrSymb",
        "XpryDt",
        "FininstrmActlXpryDt",
        "StrkPric",
        "OptnTp",
        "SttlmPric",
        "PrvsClsgPric",
        "UndrlygPric",
        "OpnIntrst",
        "ChngInOpnIntrst",
        "TtlTradgVol",
        "TtlTrfVal",
        "TtlNbOfTxsExctd",
        "NewBrdLotQty",
    }
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise AlphaContractError(
            "FO UDiFF header does not satisfy D005 option-source contract"
        )

    expected = session_date.isoformat()
    rows: list[OptionContractObservation] = []
    invalid_symbols: set[str] = set()
    structural_row_count = 0
    sto_row_count = 0

    for raw in reader:
        structural_row_count += 1
        if (
            str(raw.get("TradDt") or "").strip() != expected
            or str(raw.get("Sgmt") or "").strip().upper() != "FO"
            or str(raw.get("Src") or "").strip().upper() != "NSE"
        ):
            raise AlphaContractError(
                "FO UDiFF trade-date/segment/source contract changed"
            )
        if str(raw.get("FinInstrmTp") or "").strip().upper() != "STO":
            continue
        sto_row_count += 1
        symbol = str(raw.get("TckrSymb") or "").strip().upper()
        instrument_id = str(raw.get("FinInstrmId") or "").strip()
        option_type = str(raw.get("OptnTp") or "").strip().upper()
        expiry = str(
            raw.get("FininstrmActlXpryDt")
            or raw.get("XpryDt")
            or ""
        ).strip()
        if not symbol or not instrument_id or option_type not in {"CE", "PE"}:
            invalid_symbols.add(symbol or "<MISSING>")
            continue
        try:
            expiry_day = date.fromisoformat(expiry)
            strike = _finite(raw.get("StrkPric"), "strike_price", positive=True)
            settlement = _finite(
                raw.get("SttlmPric"),
                "settlement_price",
                positive=True,
            )
            previous = _finite(
                raw.get("PrvsClsgPric"),
                "previous_close",
                nonnegative=True,
            )
            underlying = _finite(
                raw.get("UndrlygPric"),
                "underlying_price",
                positive=True,
                allow_missing=True,
            )
            open_interest = _finite(
                raw.get("OpnIntrst"),
                "open_interest",
                nonnegative=True,
            )
            change_oi = _finite(
                raw.get("ChngInOpnIntrst"),
                "change_in_open_interest",
            )
            volume = _finite(
                raw.get("TtlTradgVol"),
                "traded_contracts",
                nonnegative=True,
            )
            transferred = _finite(
                raw.get("TtlTrfVal"),
                "transferred_value_inr",
                nonnegative=True,
            )
            trades = _finite(
                raw.get("TtlNbOfTxsExctd"),
                "trade_count",
                nonnegative=True,
            )
            board_lot = _finite(
                raw.get("NewBrdLotQty"),
                "board_lot",
                positive=True,
            )
        except (AlphaContractError, ValueError):
            invalid_symbols.add(symbol)
            continue
        assert strike is not None
        assert settlement is not None
        assert previous is not None
        assert open_interest is not None
        assert change_oi is not None
        assert volume is not None
        assert transferred is not None
        assert trades is not None
        assert board_lot is not None
        rows.append(
            OptionContractObservation(
                session_date=expected,
                symbol=symbol,
                financial_instrument_id=instrument_id,
                expiry_date=expiry_day.isoformat(),
                strike_price=float(strike),
                option_type=option_type,
                settlement_price=float(settlement),
                previous_close=float(previous),
                underlying_price=(
                    None if underlying is None else float(underlying)
                ),
                open_interest=float(open_interest),
                change_in_open_interest=float(change_oi),
                traded_contracts=float(volume),
                transferred_value_inr=float(transferred),
                trade_count=float(trades),
                board_lot=float(board_lot),
            )
        )

    rows = [row for row in rows if row.symbol not in invalid_symbols]

    seen_physical: set[tuple[str, str, float, str, str]] = set()
    logical_instrument: dict[tuple[str, str, float, str], str] = {}
    duplicate_symbols: set[str] = set()
    for row in rows:
        physical = (
            row.symbol,
            row.expiry_date,
            row.strike_price,
            row.option_type,
            row.financial_instrument_id,
        )
        logical = (
            row.symbol,
            row.expiry_date,
            row.strike_price,
            row.option_type,
        )
        if physical in seen_physical:
            duplicate_symbols.add(row.symbol)
        seen_physical.add(physical)

        prior_instrument = logical_instrument.get(logical)
        if (
            prior_instrument is not None
            and prior_instrument != row.financial_instrument_id
        ):
            duplicate_symbols.add(row.symbol)
        else:
            logical_instrument[logical] = row.financial_instrument_id

    if duplicate_symbols:
        invalid_symbols.update(duplicate_symbols)
        rows = [row for row in rows if row.symbol not in invalid_symbols]

    diagnostics = {
        "csv_row_count": structural_row_count,
        "stock_option_row_count": sto_row_count,
        "accepted_contract_row_count": len(rows),
        "invalid_symbol_count": len(invalid_symbols),
        "invalid_symbols": sorted(invalid_symbols),
    }
    return sorted(
        rows,
        key=lambda row: (
            row.symbol,
            row.expiry_date,
            row.strike_price,
            row.option_type,
            row.financial_instrument_id,
        ),
    ), diagnostics


def classify_front_option_surface(
    contracts: list[OptionContractObservation],
    *,
    market_current: DailyEquityObservation,
) -> dict[str, Any]:
    if not contracts:
        return {"status": "NO_STOCK_OPTIONS"}
    if any(
        row.session_date != market_current.session_date
        or row.symbol != market_current.symbol
        for row in contracts
    ):
        raise AlphaContractError(
            "D005 option/cash session or symbol identity mismatch"
        )

    day = date.fromisoformat(market_current.session_date)
    valid = [
        row for row in contracts
        if date.fromisoformat(row.expiry_date) > day
    ]
    if not valid:
        return {"status": "NO_STRICTLY_FUTURE_EXPIRY"}

    front_expiry = min(row.expiry_date for row in valid)
    front = [row for row in valid if row.expiry_date == front_expiry]
    calls = {row.strike_price: row for row in front if row.option_type == "CE"}
    puts = {row.strike_price: row for row in front if row.option_type == "PE"}
    paired = sorted(set(calls) & set(puts))
    if len(paired) < D005_MIN_PAIRED_STRIKES:
        return {
            "status": "INSUFFICIENT_PAIRED_STRIKES",
            "front_expiry": front_expiry,
            "paired_strike_count": len(paired),
        }

    cash_close = float(market_current.close_price)
    if cash_close <= 0:
        raise AlphaContractError("D005 cash close must be positive")
    nearest = min(
        paired,
        key=lambda strike: (abs(strike / cash_close - 1.0), strike),
    )
    nearest_abs_moneyness = abs(nearest / cash_close - 1.0)
    if nearest_abs_moneyness > D005_MAX_ATM_ABS_MONEYNESS:
        return {
            "status": "NO_NEAR_ATM_PAIRED_STRIKE",
            "front_expiry": front_expiry,
            "paired_strike_count": len(paired),
            "nearest_paired_strike": nearest,
            "nearest_abs_moneyness": nearest_abs_moneyness,
        }

    return {
        "status": "USABLE",
        "front_expiry": front_expiry,
        "paired_strike_count": len(paired),
        "nearest_paired_strike": nearest,
        "nearest_abs_moneyness": nearest_abs_moneyness,
        "front_contract_count": len(front),
    }


def audit_historical_option_source(
    *,
    market_panel: dict[str, Any],
    fetcher,
    store_root: str | Path | None = None,
    captured_at_utc: datetime | None = None,
) -> dict[str, Any]:
    stored = str(market_panel.get("panel_sha256") or "")
    unsigned = dict(market_panel)
    unsigned.pop("panel_sha256", None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError("D005 market panel hash mismatch")

    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise AlphaContractError("D005 market sessions are required")
    captured = captured_at_utc or datetime.now(UTC)
    if captured.tzinfo is None:
        raise AlphaContractError("D005 capture timestamp must be timezone-aware")
    store = MarketArtifactStore(store_root) if store_root is not None else None

    session_reports = []
    parser_rejected = 0
    unavailable = 0
    ready = 0
    usable_counts = []
    total_sto_rows = 0
    exclusion_counts: dict[str, int] = defaultdict(int)
    source_hashes = []

    for session in sessions:
        session_text = str(session["session_date"])
        day = date.fromisoformat(session_text)
        url = fo_udiff_url(day)
        raw = fetcher(url)
        if raw is None:
            unavailable += 1
            session_reports.append(
                {
                    "session_date": session_text,
                    "status": "UNAVAILABLE",
                    "source_url": url,
                    "raw_sha256": None,
                    "usable_symbol_count": 0,
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
            options, diagnostics = parse_fo_udiff_stock_options(
                raw,
                session_date=day,
            )
        except AlphaContractError as exc:
            parser_rejected += 1
            session_reports.append(
                {
                    "session_date": session_text,
                    "status": "PARSER_REJECTED",
                    "source_url": url,
                    "raw_sha256": raw_sha,
                    "error": str(exc),
                    "usable_symbol_count": 0,
                }
            )
            continue

        ready += 1
        total_sto_rows += diagnostics["stock_option_row_count"]
        option_by_symbol: dict[str, list[OptionContractObservation]] = defaultdict(list)
        for row in options:
            option_by_symbol[row.symbol].append(row)

        market_by_symbol = {}
        for raw_market in session.get("equities", []):
            market_row = (
                raw_market
                if isinstance(raw_market, DailyEquityObservation)
                else DailyEquityObservation(**raw_market)
            )
            if market_row.symbol in market_by_symbol:
                raise AlphaContractError(
                    f"{session_text}: duplicate cash symbol in D005 market panel"
                )
            market_by_symbol[market_row.symbol] = market_row

        usable = 0
        mapped = 0
        for symbol, contracts in option_by_symbol.items():
            cash = market_by_symbol.get(symbol)
            if cash is None:
                exclusion_counts["NO_SAME_SESSION_EQ_IDENTITY"] += 1
                continue
            mapped += 1
            classification = classify_front_option_surface(
                contracts,
                market_current=cash,
            )
            if classification["status"] == "USABLE":
                usable += 1
            else:
                exclusion_counts[classification["status"]] += 1

        usable_counts.append(usable)
        session_reports.append(
            {
                "session_date": session_text,
                "status": "READY",
                "source_url": url,
                "raw_sha256": raw_sha,
                "stock_option_row_count": diagnostics["stock_option_row_count"],
                "accepted_contract_row_count": diagnostics[
                    "accepted_contract_row_count"
                ],
                "invalid_symbol_count": diagnostics["invalid_symbol_count"],
                "distinct_option_symbol_count": len(option_by_symbol),
                "mapped_eq_symbol_count": mapped,
                "usable_symbol_count": usable,
            }
        )

    if not usable_counts:
        raise OptionsSourceError("D005 found no READY options sessions")

    median_usable = float(statistics.median(usable_counts))
    p10 = float(np.percentile(np.asarray(usable_counts, dtype=float), 10))
    p90 = float(np.percentile(np.asarray(usable_counts, dtype=float), 90))
    gates = {
        "parser_rejected_sessions_zero": parser_rejected == 0,
        "ready_sessions_at_least_200": ready >= 200,
        "median_usable_symbols_at_least_100": median_usable >= 100.0,
        "p10_usable_symbols_at_least_75": p10 >= 75.0,
    }

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": "AE001-D005-v1",
        "evidence_class": "HISTORICAL_SOURCE_FEASIBILITY_NO_OUTCOMES",
        "market_panel_sha256": market_panel["panel_sha256"],
        "session_count": len(sessions),
        "ready_session_count": ready,
        "unavailable_session_count": unavailable,
        "parser_rejected_session_count": parser_rejected,
        "total_stock_option_row_count": total_sto_rows,
        "usable_symbol_distribution": {
            "minimum": min(usable_counts),
            "p10": p10,
            "median": median_usable,
            "p90": p90,
            "maximum": max(usable_counts),
        },
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "viability_gates": gates,
        "all_viability_gates_passed": all(gates.values()),
        "source_hashes_sha256": digest(source_hashes),
        "sessions": session_reports,
        "future_returns_opened": False,
        "model_fit_started": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
