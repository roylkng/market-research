from __future__ import annotations

import csv
import io
import math
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, FeatureDefinition, digest
from marketlab.alpha_market import DailyEquityObservation
from marketlab.events import sha256_bytes
from marketlab.marketdata import MarketArtifactStore

FO_UDIFF_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/content/fo/"
    "BhavCopy_NSE_FO_0_0_0_{yyyymmdd}_F_0000.csv.zip"
)

FUTURES_DEFINITIONS = [
    FeatureDefinition(
        "fut_front_basis",
        "derivatives_flows",
        "v1",
        "Front stock-futures settlement relative to same-session cash close.",
        1,
    ),
    FeatureDefinition(
        "fut_front_log_basis_per_day",
        "derivatives_flows",
        "v1",
        "Log front futures/cash basis divided by calendar days to expiry.",
        1,
    ),
    FeatureDefinition(
        "fut_next_log_basis_per_day",
        "derivatives_flows",
        "v1",
        "Log next futures/cash basis divided by calendar days to expiry.",
        1,
    ),
    FeatureDefinition(
        "fut_curve_slope_per_day",
        "derivatives_flows",
        "v1",
        "Next log basis/day minus front log basis/day.",
        1,
    ),
    FeatureDefinition(
        "fut_front_oi_change_fraction",
        "derivatives_flows",
        "v1",
        "Front change in OI divided by reconstructed prior OI.",
        1,
    ),
    FeatureDefinition(
        "fut_total_oi_change_fraction",
        "derivatives_flows",
        "v1",
        "Aggregate change in OI divided by aggregate prior OI.",
        1,
    ),
    FeatureDefinition(
        "fut_front_oi_share",
        "derivatives_flows",
        "v1",
        "Front-contract OI divided by total listed stock-futures OI.",
        1,
    ),
    FeatureDefinition(
        "fut_total_volume_to_oi",
        "derivatives_flows",
        "v1",
        "Underlying-equivalent traded futures volume divided by total OI.",
        1,
    ),
    FeatureDefinition(
        "fut_notional_to_cash_turnover",
        "derivatives_flows",
        "v1",
        "Stock-futures notional turnover divided by same-session cash turnover.",
        1,
    ),
    FeatureDefinition(
        "fut_front_settlement_return_1",
        "derivatives_flows",
        "v1",
        "Front settlement price relative to that contract's prior close.",
        1,
    ),
]


@dataclass(frozen=True)
class FuturesContractObservation:
    session_date: str
    symbol: str
    financial_instrument_id: str
    expiry_date: str
    settlement_price: float
    previous_close: float
    underlying_price: float | None
    open_interest: float
    change_in_open_interest: float
    traded_contracts: float
    transferred_value_inr: float
    trade_count: float
    board_lot: float


class FuturesAcquisitionError(RuntimeError):
    """Raised when NSE stock-futures evidence cannot be acquired safely."""


def fo_udiff_url(session_date: date) -> str:
    return FO_UDIFF_URL_TEMPLATE.format(
        yyyymmdd=session_date.strftime("%Y%m%d")
    )


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
        raise AlphaContractError(f"invalid futures {field}: {value}") from exc
    if not math.isfinite(parsed):
        raise AlphaContractError(f"futures {field} must be finite")
    if positive and parsed <= 0:
        raise AlphaContractError(f"futures {field} must be positive")
    if nonnegative and parsed < 0:
        raise AlphaContractError(f"futures {field} cannot be negative")
    return parsed


def parse_fo_udiff_stock_futures(
    raw_zip: bytes,
    *,
    session_date: date,
) -> tuple[list[FuturesContractObservation], dict[str, Any]]:
    """Parse same-session NSE UDiFF stock-futures contracts.

    Structural file failures reject the whole session. Malformed STF numeric
    rows fail closed for that symbol/session and are removed from the returned
    contract set.
    """

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
            "FO UDiFF header does not satisfy T005 contract"
        )

    expected = session_date.isoformat()
    rows: list[FuturesContractObservation] = []
    invalid_symbols: set[str] = set()
    structural_row_count = 0
    stock_future_row_count = 0

    for raw in reader:
        structural_row_count += 1
        trad_date = str(raw.get("TradDt") or "").strip()
        segment = str(raw.get("Sgmt") or "").strip().upper()
        source = str(raw.get("Src") or "").strip().upper()
        if trad_date != expected or segment != "FO" or source != "NSE":
            raise AlphaContractError(
                "FO UDiFF trade-date/segment/source contract changed"
            )
        if str(raw.get("FinInstrmTp") or "").strip().upper() != "STF":
            continue
        stock_future_row_count += 1
        symbol = str(raw.get("TckrSymb") or "").strip().upper()
        instrument_id = str(raw.get("FinInstrmId") or "").strip()
        expiry = str(
            raw.get("FininstrmActlXpryDt") or raw.get("XpryDt") or ""
        ).strip()
        if not symbol or not instrument_id:
            invalid_symbols.add(symbol or "<MISSING>")
            continue
        try:
            expiry_day = date.fromisoformat(expiry)
            settlement = _finite(
                raw.get("SttlmPric"),
                "settlement_price",
                positive=True,
            )
            previous = _finite(
                raw.get("PrvsClsgPric"),
                "previous_close",
                positive=True,
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

        if expiry_day < session_date:
            invalid_symbols.add(symbol)
            continue
        assert settlement is not None
        assert previous is not None
        assert open_interest is not None
        assert change_oi is not None
        assert volume is not None
        assert transferred is not None
        assert trades is not None
        assert board_lot is not None
        rows.append(
            FuturesContractObservation(
                session_date=expected,
                symbol=symbol,
                financial_instrument_id=instrument_id,
                expiry_date=expiry_day.isoformat(),
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
    seen_contracts: set[tuple[str, str, str]] = set()
    duplicate_symbols: set[str] = set()
    for row in rows:
        key = (
            row.symbol,
            row.expiry_date,
            row.financial_instrument_id,
        )
        if key in seen_contracts:
            duplicate_symbols.add(row.symbol)
        seen_contracts.add(key)
    if duplicate_symbols:
        invalid_symbols.update(duplicate_symbols)
        rows = [row for row in rows if row.symbol not in invalid_symbols]

    if stock_future_row_count == 0:
        raise AlphaContractError(
            f"FO UDiFF contains no STF rows for {expected}"
        )
    diagnostics = {
        "csv_row_count": structural_row_count,
        "stock_future_row_count": stock_future_row_count,
        "accepted_contract_row_count": len(rows),
        "invalid_symbol_count": len(invalid_symbols),
        "invalid_symbols": sorted(invalid_symbols),
    }
    return sorted(
        rows,
        key=lambda row: (
            row.symbol,
            row.expiry_date,
            row.financial_instrument_id,
        ),
    ), diagnostics


def futures_features(
    contracts: list[FuturesContractObservation],
    *,
    market_current: DailyEquityObservation,
) -> dict[str, float]:
    if not contracts:
        raise AlphaContractError("T005 stock-futures contracts are missing")
    if any(
        row.session_date != market_current.session_date
        or row.symbol != market_current.symbol
        for row in contracts
    ):
        raise AlphaContractError(
            "T005 futures/cash session or symbol identity mismatch"
        )

    day = date.fromisoformat(market_current.session_date)
    # P1 rule: expiring-today contract is excluded from carry features.
    valid = [
        row
        for row in contracts
        if date.fromisoformat(row.expiry_date) > day
    ]
    by_expiry: dict[str, list[FuturesContractObservation]] = defaultdict(list)
    for row in valid:
        by_expiry[row.expiry_date].append(row)
    if len(by_expiry) < 2:
        raise AlphaContractError(
            "T005 requires at least two distinct future expiries"
        )
    if any(len(rows) != 1 for rows in by_expiry.values()):
        raise AlphaContractError(
            "T005 has ambiguous multiple contracts for one expiry"
        )

    ordered = [
        rows[0]
        for _, rows in sorted(by_expiry.items())
    ]
    front = ordered[0]
    nxt = ordered[1]
    cash_close = float(market_current.close_price)
    if cash_close <= 0:
        raise AlphaContractError("T005 cash close must be positive")

    front_days = (
        date.fromisoformat(front.expiry_date) - day
    ).days
    next_days = (
        date.fromisoformat(nxt.expiry_date) - day
    ).days
    if front_days <= 0 or next_days <= front_days:
        raise AlphaContractError("T005 expiry ordering is invalid")

    front_prior_oi = (
        front.open_interest - front.change_in_open_interest
    )
    total_current_oi = sum(row.open_interest for row in ordered)
    total_change_oi = sum(
        row.change_in_open_interest for row in ordered
    )
    total_prior_oi = total_current_oi - total_change_oi
    if (
        front_prior_oi <= 0
        or total_current_oi <= 0
        or total_prior_oi <= 0
    ):
        raise AlphaContractError(
            "T005 OI denominator is non-positive"
        )

    total_volume_units = sum(
        row.traded_contracts * row.board_lot
        for row in ordered
    )
    total_notional = sum(
        row.transferred_value_inr for row in ordered
    )
    if market_current.turnover_inr <= 0:
        raise AlphaContractError(
            "T005 cash turnover denominator is non-positive"
        )

    front_ratio = front.settlement_price / cash_close
    next_ratio = nxt.settlement_price / cash_close
    if front_ratio <= 0 or next_ratio <= 0:
        raise AlphaContractError("T005 basis ratio must be positive")

    result = {
        "fut_front_basis": front_ratio - 1.0,
        "fut_front_log_basis_per_day": (
            math.log(front_ratio) / front_days
        ),
        "fut_next_log_basis_per_day": (
            math.log(next_ratio) / next_days
        ),
        "fut_curve_slope_per_day": (
            math.log(next_ratio) / next_days
            - math.log(front_ratio) / front_days
        ),
        "fut_front_oi_change_fraction": (
            front.change_in_open_interest / front_prior_oi
        ),
        "fut_total_oi_change_fraction": (
            total_change_oi / total_prior_oi
        ),
        "fut_front_oi_share": (
            front.open_interest / total_current_oi
        ),
        "fut_total_volume_to_oi": (
            total_volume_units / total_current_oi
        ),
        "fut_notional_to_cash_turnover": (
            total_notional / market_current.turnover_inr
        ),
        "fut_front_settlement_return_1": (
            front.settlement_price / front.previous_close - 1.0
        ),
    }
    if any(not math.isfinite(float(value)) for value in result.values()):
        raise AlphaContractError(
            "T005 derived futures feature is nonfinite"
        )
    return result


def acquire_historical_futures_panel(
    *,
    session_dates: list[str],
    fetcher,
    store_root: str | Path | None = None,
    captured_at_utc: datetime | None = None,
) -> dict[str, Any]:
    if not session_dates:
        raise FuturesAcquisitionError(
            "T005 futures session list cannot be empty"
        )
    if (
        session_dates != sorted(session_dates)
        or len(session_dates) != len(set(session_dates))
    ):
        raise FuturesAcquisitionError(
            "T005 futures sessions must be unique and chronological"
        )
    captured = captured_at_utc or datetime.now(UTC)
    if captured.tzinfo is None:
        raise FuturesAcquisitionError(
            "T005 captured_at_utc must be timezone-aware"
        )
    store = MarketArtifactStore(store_root) if store_root is not None else None

    sessions = []
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
        if store is not None:
            store.retain(
                raw,
                source_url=url,
                captured_at=captured,
                suffix=".zip",
            )
        try:
            rows, diagnostics = parse_fo_udiff_stock_futures(
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
                "diagnostics": diagnostics,
                "rows": [asdict(row) for row in rows],
            }
        )

    panel: dict[str, Any] = {
        "schema_version": 1,
        "panel_id": "AE001-HISTORICAL-STOCK-FUTURES-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
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
        "sessions": sessions,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def augment_feature_panel_with_futures(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    futures_panel: dict[str, Any],
) -> dict[str, Any]:
    def verify(panel: dict[str, Any], *, name: str) -> None:
        stored = str(panel.get("panel_sha256") or "")
        unsigned = dict(panel)
        unsigned.pop("panel_sha256", None)
        if len(stored) != 64 or digest(unsigned) != stored:
            raise AlphaContractError(f"{name} panel hash mismatch")

    verify(feature_panel, name="T005 base feature")
    verify(market_panel, name="T005 market")
    verify(futures_panel, name="T005 futures")
    if feature_panel.get("outcomes_attached") is not False:
        raise AlphaContractError(
            "T005 futures augmentation requires outcome-free features"
        )

    market_sessions = market_panel.get("sessions")
    futures_sessions = futures_panel.get("sessions")
    if not isinstance(market_sessions, list) or not isinstance(
        futures_sessions, list
    ):
        raise AlphaContractError(
            "T005 market/futures sessions must be lists"
        )
    market_dates = [str(row["session_date"]) for row in market_sessions]
    futures_dates = [str(row["session_date"]) for row in futures_sessions]
    if market_dates != futures_dates:
        raise AlphaContractError(
            "T005 futures session set must exactly match market panel"
        )

    base_definitions = feature_panel.get("feature_definitions")
    if not isinstance(base_definitions, list):
        raise AlphaContractError(
            "T005 base feature definitions are missing"
        )
    definitions = list(base_definitions) + [
        asdict(definition) for definition in FUTURES_DEFINITIONS
    ]
    names = [str(row["name"]) for row in definitions]
    if len(names) != len(set(names)):
        raise AlphaContractError(
            "T005 futures features collide with base features"
        )
    definitions.sort(key=lambda row: row["name"])
    feature_set_sha256 = digest(definitions)

    base_rows_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feature_panel.get("rows", []):
        base_rows_by_session[str(row["feature_session"])].append(row)

    result_rows = []
    session_summary = []
    excluded = defaultdict(int)

    for market_session, futures_session in zip(
        market_sessions,
        futures_sessions,
        strict=True,
    ):
        session_text = str(market_session["session_date"])
        base_rows = base_rows_by_session.get(session_text, [])
        if futures_session["status"] != "READY":
            excluded[f"SESSION_{futures_session['status']}"] += len(base_rows)
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
                    f"{session_text}: duplicate T005 cash symbol"
                )
            market_by_symbol[row.symbol] = row

        contracts_by_symbol: dict[
            str, list[FuturesContractObservation]
        ] = defaultdict(list)
        for raw in futures_session.get("rows", []):
            row = (
                raw
                if isinstance(raw, FuturesContractObservation)
                else FuturesContractObservation(**raw)
            )
            contracts_by_symbol[row.symbol].append(row)

        kept = []
        for base_row in sorted(
            base_rows,
            key=lambda row: (str(row["symbol"]), str(row["isin"])),
        ):
            symbol = str(base_row["symbol"])
            isin = str(base_row["isin"])
            market_current = market_by_symbol.get(symbol)
            if market_current is None or market_current.isin != isin:
                excluded["CASH_IDENTITY_MISMATCH"] += 1
                continue
            contracts = contracts_by_symbol.get(symbol)
            if not contracts:
                excluded["NO_STOCK_FUTURES"] += 1
                continue
            try:
                new_values = futures_features(
                    contracts,
                    market_current=market_current,
                )
            except AlphaContractError:
                excluded["INVALID_FUTURES_STRUCTURE"] += 1
                continue
            updated = {
                **base_row,
                "feature_set_sha256": feature_set_sha256,
                "values": {
                    **base_row["values"],
                    **new_values,
                },
                "futures_source_sha256": futures_session["raw_sha256"],
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
                    "session_date": session_text,
                    "eligible_count": len(kept),
                    "universe_sha256": universe_sha,
                    "futures_raw_sha256": futures_session["raw_sha256"],
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
        "panel_id": "AE001-HISTORICAL-FUTURES-AUGMENTED-v1",
        "base_feature_panel_sha256": feature_panel["panel_sha256"],
        "base_action_safe_feature_panel_sha256": feature_panel.get(
            "base_feature_panel_sha256"
        ),
        "futures_panel_sha256": futures_panel["panel_sha256"],
        "feature_definitions": definitions,
        "feature_set_sha256": feature_set_sha256,
        "futures_join_contract": (
            "SAME_SESSION_FO_STF_SYMBOL_TO_CM_EQ_SYMBOL_PLUS_ISIN"
        ),
        "futures_contract_selection": (
            "STRICTLY_FUTURE_EXPIRIES_FRONT_AND_NEXT_PLUS_ALL_EXPIRY_TOTALS"
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
