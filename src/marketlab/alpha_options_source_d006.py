from __future__ import annotations

import csv
import io
import math
import statistics
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_futures import fo_udiff_url
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_options_source import (
    OptionContractObservation,
    OptionsSourceError,
    classify_front_option_surface,
)
from marketlab.events import sha256_bytes
from marketlab.marketdata import MarketArtifactStore

D006_MIN_PAIRED_STRIKES = 3
D006_MAX_ATM_ABS_MONEYNESS = 0.10


@dataclass(frozen=True)
class D006ParseDiagnostics:
    csv_row_count: int
    stock_option_row_count: int
    accepted_contract_row_count: int
    row_exclusion_counts: dict[str, int]
    ambiguous_logical_contract_count: int
    ambiguous_logical_contract_symbols: int
    accepted_symbol_count: int


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


def _required_header() -> set[str]:
    return {
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


def parse_fo_udiff_stock_options_d006(
    raw_zip: bytes,
    *,
    session_date: date,
) -> tuple[list[OptionContractObservation], D006ParseDiagnostics]:
    """Parse NSE STO rows using D006 row/logical-key-localized exclusions."""

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
    required = _required_header()
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise AlphaContractError(
            "FO UDiFF header does not satisfy D006 option-source contract"
        )

    expected = session_date.isoformat()
    structural_row_count = 0
    sto_row_count = 0
    exclusions: Counter[str] = Counter()
    candidates: list[OptionContractObservation] = []

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

        if not symbol:
            exclusions["MISSING_SYMBOL"] += 1
            continue
        if not instrument_id:
            exclusions["MISSING_INSTRUMENT_ID"] += 1
            continue
        if option_type not in {"CE", "PE"}:
            exclusions["INVALID_OPTION_TYPE"] += 1
            continue

        try:
            expiry_day = date.fromisoformat(expiry)
        except ValueError:
            exclusions["INVALID_EXPIRY"] += 1
            continue

        try:
            strike = _finite(
                raw.get("StrkPric"),
                "strike_price",
                positive=True,
            )
        except AlphaContractError:
            exclusions["INVALID_STRIKE"] += 1
            continue
        try:
            settlement = _finite(
                raw.get("SttlmPric"),
                "settlement_price",
                positive=True,
            )
        except AlphaContractError:
            exclusions["INVALID_SETTLEMENT_PRICE"] += 1
            continue
        try:
            previous = _finite(
                raw.get("PrvsClsgPric"),
                "previous_close",
                nonnegative=True,
            )
        except AlphaContractError:
            exclusions["INVALID_PREVIOUS_CLOSE"] += 1
            continue
        try:
            underlying = _finite(
                raw.get("UndrlygPric"),
                "underlying_price",
                positive=True,
                allow_missing=True,
            )
        except AlphaContractError:
            exclusions["INVALID_UNDERLYING_PRICE"] += 1
            continue
        try:
            open_interest = _finite(
                raw.get("OpnIntrst"),
                "open_interest",
                nonnegative=True,
            )
        except AlphaContractError:
            exclusions["INVALID_OPEN_INTEREST"] += 1
            continue
        try:
            change_oi = _finite(
                raw.get("ChngInOpnIntrst"),
                "change_in_open_interest",
            )
        except AlphaContractError:
            exclusions["INVALID_CHANGE_IN_OPEN_INTEREST"] += 1
            continue
        try:
            volume = _finite(
                raw.get("TtlTradgVol"),
                "traded_contracts",
                nonnegative=True,
            )
        except AlphaContractError:
            exclusions["INVALID_TRADED_CONTRACTS"] += 1
            continue
        try:
            transferred = _finite(
                raw.get("TtlTrfVal"),
                "transferred_value_inr",
                nonnegative=True,
            )
        except AlphaContractError:
            exclusions["INVALID_TRANSFERRED_VALUE"] += 1
            continue
        try:
            trades = _finite(
                raw.get("TtlNbOfTxsExctd"),
                "trade_count",
                nonnegative=True,
            )
        except AlphaContractError:
            exclusions["INVALID_TRADE_COUNT"] += 1
            continue
        try:
            board_lot = _finite(
                raw.get("NewBrdLotQty"),
                "board_lot",
                positive=True,
            )
        except AlphaContractError:
            exclusions["INVALID_BOARD_LOT"] += 1
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

        candidates.append(
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

    logical_groups: dict[
        tuple[str, str, float, str],
        list[OptionContractObservation],
    ] = defaultdict(list)
    for row in candidates:
        logical_groups[
            (
                row.symbol,
                row.expiry_date,
                row.strike_price,
                row.option_type,
            )
        ].append(row)

    accepted: list[OptionContractObservation] = []
    ambiguous_symbols: set[str] = set()
    ambiguous_logical_count = 0
    for logical_key, group in logical_groups.items():
        if len(group) != 1:
            ambiguous_logical_count += 1
            ambiguous_symbols.add(logical_key[0])
            exclusions["AMBIGUOUS_LOGICAL_CONTRACT"] += len(group)
            continue
        accepted.append(group[0])

    accepted.sort(
        key=lambda row: (
            row.symbol,
            row.expiry_date,
            row.strike_price,
            row.option_type,
            row.financial_instrument_id,
        )
    )
    accepted_symbols = {row.symbol for row in accepted}
    diagnostics = D006ParseDiagnostics(
        csv_row_count=structural_row_count,
        stock_option_row_count=sto_row_count,
        accepted_contract_row_count=len(accepted),
        row_exclusion_counts=dict(sorted(exclusions.items())),
        ambiguous_logical_contract_count=ambiguous_logical_count,
        ambiguous_logical_contract_symbols=len(ambiguous_symbols),
        accepted_symbol_count=len(accepted_symbols),
    )
    return accepted, diagnostics


def audit_historical_option_source_d006(
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
        raise AlphaContractError("D006 market panel hash mismatch")

    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise AlphaContractError("D006 market sessions are required")

    captured = captured_at_utc or datetime.now(UTC)
    if captured.tzinfo is None:
        raise AlphaContractError("D006 capture timestamp must be timezone-aware")
    store = MarketArtifactStore(store_root) if store_root is not None else None

    session_reports = []
    parser_rejected = 0
    unavailable = 0
    ready = 0
    usable_counts: list[int] = []
    total_sto_rows = 0
    total_accepted_rows = 0
    total_ambiguous_logical = 0
    row_exclusions: Counter[str] = Counter()
    surface_exclusions: Counter[str] = Counter()
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
            options, diagnostics = parse_fo_udiff_stock_options_d006(
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
        total_sto_rows += diagnostics.stock_option_row_count
        total_accepted_rows += diagnostics.accepted_contract_row_count
        total_ambiguous_logical += diagnostics.ambiguous_logical_contract_count
        row_exclusions.update(diagnostics.row_exclusion_counts)

        option_by_symbol: dict[
            str, list[OptionContractObservation]
        ] = defaultdict(list)
        for row in options:
            option_by_symbol[row.symbol].append(row)

        market_by_symbol: dict[str, DailyEquityObservation] = {}
        for raw_market in session.get("equities", []):
            market_row = (
                raw_market
                if isinstance(raw_market, DailyEquityObservation)
                else DailyEquityObservation(**raw_market)
            )
            if market_row.symbol in market_by_symbol:
                raise AlphaContractError(
                    f"{session_text}: duplicate cash symbol in D006 market panel"
                )
            market_by_symbol[market_row.symbol] = market_row

        usable = 0
        mapped = 0
        for symbol, contracts in option_by_symbol.items():
            cash = market_by_symbol.get(symbol)
            if cash is None:
                surface_exclusions["NO_SAME_SESSION_EQ_IDENTITY"] += 1
                continue
            mapped += 1
            classification = classify_front_option_surface(
                contracts,
                market_current=cash,
            )
            if classification["status"] == "USABLE":
                usable += 1
            else:
                surface_exclusions[classification["status"]] += 1

        usable_counts.append(usable)
        session_reports.append(
            {
                "session_date": session_text,
                "status": "READY",
                "source_url": url,
                "raw_sha256": raw_sha,
                "stock_option_row_count": diagnostics.stock_option_row_count,
                "accepted_contract_row_count": (
                    diagnostics.accepted_contract_row_count
                ),
                "row_exclusion_count": sum(
                    diagnostics.row_exclusion_counts.values()
                ),
                "row_exclusion_counts": diagnostics.row_exclusion_counts,
                "ambiguous_logical_contract_count": (
                    diagnostics.ambiguous_logical_contract_count
                ),
                "ambiguous_logical_contract_symbols": (
                    diagnostics.ambiguous_logical_contract_symbols
                ),
                "distinct_option_symbol_count": len(option_by_symbol),
                "mapped_eq_symbol_count": mapped,
                "usable_symbol_count": usable,
            }
        )

    if not usable_counts:
        raise OptionsSourceError("D006 found no READY options sessions")

    values = np.asarray(usable_counts, dtype=float)
    median_usable = float(statistics.median(usable_counts))
    p10 = float(np.percentile(values, 10))
    p90 = float(np.percentile(values, 90))
    gates = {
        "parser_rejected_sessions_zero": parser_rejected == 0,
        "ready_sessions_at_least_200": ready >= 200,
        "median_usable_symbols_at_least_100": median_usable >= 100.0,
        "p10_usable_symbols_at_least_75": p10 >= 75.0,
    }
    low_tail = [
        {
            "session_date": row["session_date"],
            "stock_option_row_count": row.get("stock_option_row_count"),
            "accepted_contract_row_count": row.get(
                "accepted_contract_row_count"
            ),
            "row_exclusion_count": row.get("row_exclusion_count"),
            "ambiguous_logical_contract_count": row.get(
                "ambiguous_logical_contract_count"
            ),
            "distinct_option_symbol_count": row.get(
                "distinct_option_symbol_count"
            ),
            "mapped_eq_symbol_count": row.get("mapped_eq_symbol_count"),
            "usable_symbol_count": row.get("usable_symbol_count"),
        }
        for row in session_reports
        if row.get("status") == "READY"
        and int(row.get("usable_symbol_count") or 0) < 75
    ]

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": "AE001-D006-v1",
        "evidence_class": "HISTORICAL_SOURCE_FEASIBILITY_NO_OUTCOMES",
        "predecessor": {
            "diagnostic_id": "AE001-D005-v1",
            "result": "FAILED_SOURCE_FEASIBILITY",
        },
        "market_panel_sha256": market_panel["panel_sha256"],
        "session_count": len(sessions),
        "ready_session_count": ready,
        "unavailable_session_count": unavailable,
        "parser_rejected_session_count": parser_rejected,
        "total_stock_option_row_count": total_sto_rows,
        "total_accepted_contract_row_count": total_accepted_rows,
        "row_exclusion_counts": dict(sorted(row_exclusions.items())),
        "ambiguous_logical_contract_count": total_ambiguous_logical,
        "surface_exclusion_counts": dict(sorted(surface_exclusions.items())),
        "usable_symbol_distribution": {
            "minimum": min(usable_counts),
            "p10": p10,
            "median": median_usable,
            "p90": p90,
            "maximum": max(usable_counts),
        },
        "low_coverage_session_count_lt_75": len(low_tail),
        "low_coverage_sessions": low_tail,
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
