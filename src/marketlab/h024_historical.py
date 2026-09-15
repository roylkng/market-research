from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
import statistics
import time
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

IST = ZoneInfo("Asia/Kolkata")
HYPOTHESIS_ID = "H024"
EXECUTION_RULE_ID = "H024-R001"
SOURCE_PANEL_RAW_SHA256 = "94bb81839c7d868736f830e88a3feb83538a04dfc7be01d546a7839e2bf3d101"
MARKET_DATA_CUTOFF = date(2026, 9, 15)
HORIZONS = (20, 60, 120)
PRIMARY_HORIZON = 60
ROUND_TRIP_COST_PP = 0.50
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 24_024
MIN_PRIMARY_EVENTS = 100
MIN_PRIMARY_SYMBOLS = 50
MIN_COMPLETE_SHARE = 0.80
LIQUIDITY_MEDIAN_20D_MIN_INR = 20_000_000.0
MIN_PRICE_HISTORY_SESSIONS = 60
PURCHASE_VALUE_BUCKETS = (
    ("<1cr", 0.0, 10_000_000.0),
    ("1-10cr", 10_000_000.0, 100_000_000.0),
    ("10-100cr", 100_000_000.0, 1_000_000_000.0),
    (">=100cr", 1_000_000_000.0, math.inf),
)
HOLIDAYS = frozenset(
    {
        date(2026, 1, 15),
        date(2026, 1, 26),
        date(2026, 3, 3),
        date(2026, 3, 26),
        date(2026, 3, 31),
        date(2026, 4, 3),
        date(2026, 4, 14),
        date(2026, 5, 1),
        date(2026, 5, 28),
        date(2026, 6, 26),
        date(2026, 9, 14),
    }
)
SPECIAL_SESSION_TIMES = {
    date(2026, 2, 1): (dt_time(9, 15), dt_time(15, 30)),
}
BLOCKED_ACTION_TOKENS = (
    "bonus",
    "split",
    "sub-division",
    "subdivision",
    "consolidation",
    "rights",
    "demerger",
    "spin-off",
    "spin off",
    "reduction of capital",
    "scheme of arrangement",
    "merger",
    "amalgamation",
)


class H024HistoricalError(ValueError):
    """Raised when H024 historical evidence cannot be reconstructed without guessing."""


def canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise H024HistoricalError(
            "H024 historical payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def raw_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_ist_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise H024HistoricalError(f"{field} must be an NSE timestamp string")
    try:
        parsed = datetime.strptime(value.strip(), "%d-%b-%Y %H:%M:%S").replace(
            tzinfo=IST
        )
    except ValueError as exc:
        raise H024HistoricalError(f"invalid {field}: {value}") from exc
    return parsed


def parse_iso_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise H024HistoricalError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H024HistoricalError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H024HistoricalError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise H024HistoricalError("timestamp must include timezone")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def positive_float(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise H024HistoricalError(f"{field} must be a finite positive number")
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise H024HistoricalError(f"invalid {field}: {value}") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise H024HistoricalError(f"{field} must be a finite positive number")
    return parsed


def nonnegative_float(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise H024HistoricalError(f"{field} must be a finite non-negative number")
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise H024HistoricalError(f"invalid {field}: {value}") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise H024HistoricalError(f"{field} must be a finite non-negative number")
    return parsed


@dataclass(frozen=True)
class HistoricalSession:
    session_date: str
    open_timestamp_utc: str
    close_timestamp_utc: str
    special: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _session(
    day: date,
    opened: dt_time,
    closed: dt_time,
    *,
    special: bool,
) -> HistoricalSession:
    open_dt = datetime.combine(day, opened, tzinfo=IST).astimezone(UTC)
    close_dt = datetime.combine(day, closed, tzinfo=IST).astimezone(UTC)
    if open_dt >= close_dt:
        raise H024HistoricalError(f"invalid H024 session interval: {day}")
    return HistoricalSession(
        session_date=day.isoformat(),
        open_timestamp_utc=utc_text(open_dt),
        close_timestamp_utc=utc_text(close_dt),
        special=special,
    )


def build_frozen_sessions(
    *,
    start_date: date = date(2026, 1, 1),
    end_date: date = MARKET_DATA_CUTOFF,
) -> tuple[HistoricalSession, ...]:
    if start_date > end_date:
        raise H024HistoricalError("calendar start date exceeds end date")
    sessions: list[HistoricalSession] = []
    cursor = start_date
    while cursor <= end_date:
        special = SPECIAL_SESSION_TIMES.get(cursor)
        if special is not None:
            sessions.append(_session(cursor, special[0], special[1], special=True))
        elif cursor.weekday() < 5 and cursor not in HOLIDAYS:
            sessions.append(
                _session(cursor, dt_time(9, 15), dt_time(15, 30), special=False)
            )
        cursor += timedelta(days=1)
    if not sessions:
        raise H024HistoricalError("frozen H024 calendar produced zero sessions")
    return tuple(sessions)


def planned_entry_session(
    exchange_disseminated_at_ist: str,
    sessions: tuple[HistoricalSession, ...],
) -> tuple[int, HistoricalSession] | None:
    publication = parse_ist_timestamp(
        exchange_disseminated_at_ist, "exchange_disseminated_at_ist"
    )
    publication_date = publication.date()
    for index, session in enumerate(sessions):
        if date.fromisoformat(session.session_date) > publication_date:
            return index, session
    return None


def horizon_session(
    sessions: tuple[HistoricalSession, ...],
    *,
    entry_index: int,
    horizon: int,
) -> HistoricalSession | None:
    if entry_index < 0:
        raise H024HistoricalError("entry_index must be non-negative")
    if horizon not in HORIZONS:
        raise H024HistoricalError(f"unsupported H024 horizon: {horizon}")
    target = entry_index + horizon - 1
    if target >= len(sessions):
        return None
    return sessions[target]


def parse_udiff_candidate_bars(
    raw_zip: bytes,
    *,
    session_date: date,
    symbols: set[str],
) -> dict[str, dict[str, Any]]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = archive.namelist()
            if len(names) != 1 or not names[0].lower().endswith(".csv"):
                raise H024HistoricalError("UDiFF archive must contain exactly one CSV")
            raw_csv = archive.read(names[0])
    except (zipfile.BadZipFile, KeyError) as exc:
        raise H024HistoricalError(f"invalid UDiFF ZIP: {exc}") from exc

    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise H024HistoricalError("UDiFF CSV is not UTF-8") from exc
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
        "ClsPric",
        "TtlTrfVal",
    }
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise H024HistoricalError(
            f"UDiFF header does not match H024 contract: {reader.fieldnames}"
        )

    wanted = {symbol.strip().upper() for symbol in symbols}
    day = session_date.isoformat()
    result: dict[str, dict[str, Any]] = {}
    for row in reader:
        symbol = str(row.get("TckrSymb") or "").strip().upper()
        if (
            symbol not in wanted
            or str(row.get("TradDt") or "").strip() != day
            or str(row.get("Sgmt") or "").strip().upper() != "CM"
            or str(row.get("Src") or "").strip().upper() != "NSE"
            or str(row.get("FinInstrmTp") or "").strip().upper() != "STK"
            or str(row.get("SctySrs") or "").strip().upper() != "EQ"
        ):
            continue
        if symbol in result:
            raise H024HistoricalError(
                f"duplicate UDiFF STK/EQ row for {symbol} on {day}"
            )
        isin = str(row.get("ISIN") or "").strip()
        if not isin:
            raise H024HistoricalError(f"UDiFF ISIN missing for {symbol} on {day}")
        result[symbol] = {
            "session_date": day,
            "symbol": symbol,
            "isin": isin,
            "series": "EQ",
            "open": positive_float(row.get("OpnPric"), "UDiFF open"),
            "close": positive_float(row.get("ClsPric"), "UDiFF close"),
            "traded_value_inr": nonnegative_float(
                row.get("TtlTrfVal"), "UDiFF traded value"
            ),
        }
    return result


def validate_source_panel(panel: dict[str, Any], *, raw_bytes: bytes | None = None) -> None:
    if raw_bytes is not None and raw_sha256(raw_bytes) != SOURCE_PANEL_RAW_SHA256:
        raise H024HistoricalError("H024 frozen source-panel SHA-256 changed")
    if panel.get("panel_id") != "H024-PREFREEZE-ORIGINAL-PURCHASE-SOURCE-PANEL-V1":
        raise H024HistoricalError("unexpected H024 source panel id")
    records = panel.get("records")
    if not isinstance(records, list) or len(records) != 785:
        raise H024HistoricalError(
            "H024 source panel must contain exactly 785 Original filings"
        )
    symbols: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for row in records:
        if not isinstance(row, dict):
            raise H024HistoricalError("H024 source-panel record must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        app_id = str(row.get("app_id") or "").strip()
        if not symbol or not app_id:
            raise H024HistoricalError("H024 source-panel identity missing")
        key = (symbol, app_id)
        if key in seen:
            raise H024HistoricalError(f"duplicate H024 source-panel filing: {key}")
        seen.add(key)
        symbols.add(symbol)
        parse_ist_timestamp(
            row.get("exchange_disseminated_at_ist"), "source dissemination"
        )
        if int(row.get("qualifying_transaction_count") or 0) < 1:
            raise H024HistoricalError(
                "source-panel record has no qualifying transaction"
            )
        positive_float(row.get("purchase_value_inr"), "purchase value")
    if len(symbols) != 158:
        raise H024HistoricalError(
            f"expected 158 source-panel symbols, found {len(symbols)}"
        )


def _revision_timestamp(source: dict[str, Any]) -> datetime:
    value = source.get("exchange_disseminated_at_utc")
    if not isinstance(value, str):
        raise H024HistoricalError(
            "revision source is missing exchange dissemination timestamp"
        )
    return parse_iso_timestamp(
        value, "revision.exchange_disseminated_at_utc"
    ).astimezone(IST)


def _candidate_source_id(row: dict[str, Any]) -> str:
    return canonical_hash(
        {
            "symbol": str(row["symbol"]).upper(),
            "app_id": str(row["app_id"]),
            "exchange_disseminated_at_ist": str(row["exchange_disseminated_at_ist"]),
            "raw_xbrl_sha256": str(row["raw_xbrl_sha256"]),
        }
    )


def is_revision_blocked(
    candidate: dict[str, Any],
    *,
    revisions: list[dict[str, Any]],
    entry_session: HistoricalSession,
) -> tuple[bool, list[str]]:
    original = parse_ist_timestamp(
        candidate["exchange_disseminated_at_ist"], "candidate dissemination"
    )
    entry_open = parse_iso_timestamp(
        entry_session.open_timestamp_utc, "entry open"
    ).astimezone(IST)
    blockers: list[str] = []
    for source in revisions:
        if str(source.get("symbol") or "").strip().upper() != str(
            candidate["symbol"]
        ).upper():
            continue
        revision = _revision_timestamp(source)
        if original < revision < entry_open:
            blockers.append(str(source.get("source_id") or canonical_hash(source)))
    return bool(blockers), sorted(blockers)


def _prior_same_identity_count(
    *,
    symbol: str,
    entry_isin: str,
    entry_index: int,
    sessions: tuple[HistoricalSession, ...],
    bars: dict[tuple[str, str], dict[str, Any]],
) -> int:
    count = 0
    for session in sessions[:entry_index]:
        bar = bars.get((session.session_date, symbol))
        if bar is not None and str(bar["isin"]) == entry_isin:
            count += 1
    return count


def _median_prior_20_traded_value(
    *,
    symbol: str,
    entry_isin: str,
    entry_index: int,
    sessions: tuple[HistoricalSession, ...],
    bars: dict[tuple[str, str], dict[str, Any]],
) -> float | None:
    if entry_index < 20:
        return None
    values: list[float] = []
    for session in sessions[entry_index - 20 : entry_index]:
        bar = bars.get((session.session_date, symbol))
        if bar is None or str(bar["isin"]) != entry_isin:
            values.append(0.0)
        else:
            values.append(float(bar["traded_value_inr"]))
    if len(values) != 20:
        raise H024HistoricalError(
            "prior-20 liquidity window is not exactly 20 sessions"
        )
    return statistics.median(values)


def build_event_panel(
    source_panel: dict[str, Any],
    *,
    revisions: list[dict[str, Any]],
    sessions: tuple[HistoricalSession, ...],
    bars: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    validate_source_panel(source_panel)
    exclusions: list[dict[str, Any]] = []
    eligible_filings: list[dict[str, Any]] = []
    session_index = {
        session.session_date: index for index, session in enumerate(sessions)
    }
    for candidate in source_panel["records"]:
        source_id = _candidate_source_id(candidate)
        entry_result = planned_entry_session(
            str(candidate["exchange_disseminated_at_ist"]), sessions
        )
        if entry_result is None:
            exclusions.append(
                {
                    "source_id": source_id,
                    "symbol": candidate["symbol"],
                    "app_id": candidate["app_id"],
                    "reason": "NO_ENTRY_SESSION_BEFORE_CUTOFF",
                }
            )
            continue
        entry_index, entry_session = entry_result
        blocked, blocker_ids = is_revision_blocked(
            candidate, revisions=revisions, entry_session=entry_session
        )
        if blocked:
            exclusions.append(
                {
                    "source_id": source_id,
                    "symbol": candidate["symbol"],
                    "app_id": candidate["app_id"],
                    "planned_entry_session": entry_session.session_date,
                    "reason": "REVISION_BLOCKED",
                    "revision_source_ids": blocker_ids,
                }
            )
            continue
        symbol = str(candidate["symbol"]).upper()
        entry_bar = bars.get((entry_session.session_date, symbol))
        if entry_bar is None:
            exclusions.append(
                {
                    "source_id": source_id,
                    "symbol": symbol,
                    "app_id": candidate["app_id"],
                    "planned_entry_session": entry_session.session_date,
                    "reason": "MISSING_ENTRY_EQ_BAR",
                }
            )
            continue
        entry_isin = str(entry_bar["isin"])
        history_count = _prior_same_identity_count(
            symbol=symbol,
            entry_isin=entry_isin,
            entry_index=entry_index,
            sessions=sessions,
            bars=bars,
        )
        if history_count < MIN_PRICE_HISTORY_SESSIONS:
            exclusions.append(
                {
                    "source_id": source_id,
                    "symbol": symbol,
                    "app_id": candidate["app_id"],
                    "planned_entry_session": entry_session.session_date,
                    "reason": "INSUFFICIENT_60_SESSION_PRICE_HISTORY",
                    "same_isin_prior_session_count": history_count,
                }
            )
            continue
        median_value = _median_prior_20_traded_value(
            symbol=symbol,
            entry_isin=entry_isin,
            entry_index=entry_index,
            sessions=sessions,
            bars=bars,
        )
        if median_value is None or median_value < LIQUIDITY_MEDIAN_20D_MIN_INR:
            exclusions.append(
                {
                    "source_id": source_id,
                    "symbol": symbol,
                    "app_id": candidate["app_id"],
                    "planned_entry_session": entry_session.session_date,
                    "reason": "LIQUIDITY_BELOW_H004_PRIMARY",
                    "median_prior_20_traded_value_inr": median_value,
                }
            )
            continue
        eligible_filings.append(
            {
                **candidate,
                "source_id": source_id,
                "entry_session": entry_session.to_dict(),
                "entry_index": entry_index,
                "entry_isin": entry_isin,
                "median_prior_20_traded_value_inr": median_value,
                "same_isin_prior_session_count": history_count,
            }
        )

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in eligible_filings:
        grouped[
            (str(row["symbol"]), str(row["entry_session"]["session_date"]))
        ].append(row)

    events: list[dict[str, Any]] = []
    for (symbol, entry_date), filings in sorted(
        grouped.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        filings = sorted(
            filings,
            key=lambda row: (
                parse_ist_timestamp(
                    row["exchange_disseminated_at_ist"], "filing dissemination"
                ),
                str(row["app_id"]),
            ),
        )
        isins = {str(row["entry_isin"]) for row in filings}
        if len(isins) != 1:
            raise H024HistoricalError(f"{symbol}/{entry_date}: same-entry ISIN drift")
        entry_index = session_index[entry_date]
        event_payload = {
            "symbol": symbol,
            "entry_session_date": entry_date,
            "entry_index": entry_index,
            "entry_isin": next(iter(isins)),
            "source_ids": [str(row["source_id"]) for row in filings],
            "app_ids": [str(row["app_id"]) for row in filings],
            "filing_count": len(filings),
            "qualifying_transaction_count": sum(
                int(row["qualifying_transaction_count"]) for row in filings
            ),
            "purchase_value_inr": sum(
                float(row["purchase_value_inr"]) for row in filings
            ),
            "purchase_quantity": sum(
                int(row["purchase_quantity"]) for row in filings
            ),
            "actor_count": len(
                {
                    name
                    for row in filings
                    for name in row.get("actor_names", [])
                }
            ),
            "actor_categories": sorted(
                {
                    category
                    for row in filings
                    for category in row.get("actor_categories", [])
                }
            ),
            "exchange_disseminated_at_ist": min(
                str(row["exchange_disseminated_at_ist"]) for row in filings
            ),
            "publication_month": min(
                parse_ist_timestamp(
                    row["exchange_disseminated_at_ist"], "filing dissemination"
                ).strftime("%Y-%m")
                for row in filings
            ),
            "median_prior_20_traded_value_inr": min(
                float(row["median_prior_20_traded_value_inr"]) for row in filings
            ),
        }
        event_payload["event_id"] = canonical_hash(event_payload)
        events.append(event_payload)

    reason_set = {row["reason"] for row in exclusions}
    result = {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "execution_rule_id": EXECUTION_RULE_ID,
        "source_filing_count": len(source_panel["records"]),
        "eligible_filing_count": len(eligible_filings),
        "event_count": len(events),
        "event_symbol_count": len({row["symbol"] for row in events}),
        "exclusion_count": len(exclusions),
        "exclusion_reason_counts": {
            reason: sum(1 for row in exclusions if row["reason"] == reason)
            for reason in sorted(reason_set)
        },
        "events": events,
        "exclusions": exclusions,
        "outcome_data_attached": False,
    }
    result["event_panel_sha256"] = canonical_hash(result)
    return result


def _parse_action_date(value: object) -> date:
    if not isinstance(value, str):
        raise H024HistoricalError("corporate action ex-date is missing")
    raw = value.strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"):
        try:
            parsed = time.strptime(raw, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except ValueError:
            continue
    raise H024HistoricalError(f"unsupported corporate action ex-date: {value}")


def parse_share_action_audit(payload: object, *, symbol: str) -> dict[str, Any]:
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        candidate = payload.get("data") or payload.get("records") or []
        rows = (
            [row for row in candidate if isinstance(row, dict)]
            if isinstance(candidate, list)
            else []
        )
    else:
        rows = []

    actions: list[dict[str, str]] = []
    unresolved: list[str] = []
    wanted = symbol.strip().upper()
    for row in rows:
        observed = str(row.get("symbol") or "").strip().upper()
        if observed and observed != wanted:
            continue
        subject = str(row.get("subject") or row.get("purpose") or "").strip()
        if not subject or not any(
            token in subject.casefold() for token in BLOCKED_ACTION_TOKENS
        ):
            continue
        raw_date = row.get("exDate") or row.get("ex_date")
        try:
            action_date = _parse_action_date(raw_date)
        except H024HistoricalError:
            unresolved.append(subject)
            continue
        actions.append({"ex_date": action_date.isoformat(), "subject": subject})
    actions.sort(key=lambda row: (row["ex_date"], row["subject"]))
    return {
        "status": "UNRESOLVED" if unresolved else "READY",
        "actions": actions,
        "unresolved_subjects": sorted(set(unresolved)),
    }


def blocked_actions(
    audit: dict[str, Any],
    *,
    entry_date: str,
    exit_date: str,
) -> tuple[dict[str, str], ...]:
    if audit.get("status") != "READY":
        raise H024HistoricalError("corporate action audit is unresolved")
    entry = date.fromisoformat(entry_date)
    exit_day = date.fromisoformat(exit_date)
    relevant: list[dict[str, str]] = []
    for row in audit.get("actions", []):
        ex_date = date.fromisoformat(str(row["ex_date"]))
        if entry < ex_date <= exit_day:
            relevant.append(
                {"ex_date": ex_date.isoformat(), "subject": str(row["subject"])}
            )
    return tuple(relevant)


def _gross_return_pct(entry: float, exit_value: float) -> float:
    result = (exit_value / entry - 1.0) * 100.0
    if not math.isfinite(result):
        raise H024HistoricalError("computed H024 return is non-finite")
    return result


def build_outcome_report(
    event_panel: dict[str, Any],
    *,
    sessions: tuple[HistoricalSession, ...],
    bars: dict[tuple[str, str], dict[str, Any]],
    benchmark_bars: dict[str, dict[str, Any]],
    corporate_actions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    stored_panel_hash = event_panel.get("event_panel_sha256")
    unsigned_panel = dict(event_panel)
    unsigned_panel.pop("event_panel_sha256", None)
    if stored_panel_hash != canonical_hash(unsigned_panel):
        raise H024HistoricalError("H024 event panel hash mismatch")

    records: list[dict[str, Any]] = []
    for event in event_panel["events"]:
        symbol = str(event["symbol"])
        entry_date = str(event["entry_session_date"])
        entry_index = int(event["entry_index"])
        entry_bar = bars.get((entry_date, symbol))
        benchmark_entry = benchmark_bars.get(entry_date)
        row = {
            **event,
            "entry_stock_bar": entry_bar,
            "entry_benchmark_bar": benchmark_entry,
            "horizons": {},
        }
        for horizon in HORIZONS:
            exit_session = horizon_session(
                sessions, entry_index=entry_index, horizon=horizon
            )
            if exit_session is None:
                row["horizons"][str(horizon)] = {"status": "NOT_MATURE"}
                continue
            if entry_bar is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_ENTRY_STOCK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if str(entry_bar["isin"]) != str(event["entry_isin"]):
                row["horizons"][str(horizon)] = {
                    "status": "ENTRY_IDENTITY_DRIFT",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if benchmark_entry is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_ENTRY_BENCHMARK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            action_audit = corporate_actions.get(symbol)
            if action_audit is None or action_audit.get("status") != "READY":
                row["horizons"][str(horizon)] = {
                    "status": "CORPORATE_ACTION_AUDIT_UNRESOLVED",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            actions = blocked_actions(
                action_audit,
                entry_date=entry_date,
                exit_date=exit_session.session_date,
            )
            if actions:
                row["horizons"][str(horizon)] = {
                    "status": "CORPORATE_ACTION_BLOCKED",
                    "exit_session": exit_session.to_dict(),
                    "blocked_actions": list(actions),
                }
                continue
            exit_bar = bars.get((exit_session.session_date, symbol))
            benchmark_exit = benchmark_bars.get(exit_session.session_date)
            if exit_bar is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_EXIT_STOCK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if str(exit_bar["isin"]) != str(event["entry_isin"]):
                row["horizons"][str(horizon)] = {
                    "status": "EXIT_IDENTITY_DRIFT",
                    "exit_session": exit_session.to_dict(),
                    "exit_isin": exit_bar["isin"],
                }
                continue
            if benchmark_exit is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_EXIT_BENCHMARK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue

            stock_return = _gross_return_pct(
                float(entry_bar["open"]), float(exit_bar["close"])
            )
            benchmark_return = _gross_return_pct(
                float(benchmark_entry["open"]), float(benchmark_exit["close"])
            )
            excess = stock_return - benchmark_return
            row["horizons"][str(horizon)] = {
                "status": "COMPLETE",
                "exit_session": exit_session.to_dict(),
                "exit_stock_bar": exit_bar,
                "exit_benchmark_bar": benchmark_exit,
                "stock_return_pct": stock_return,
                "benchmark_return_pct": benchmark_return,
                "gross_excess_pp": excess,
                "cost_adjusted_excess_pp": excess - ROUND_TRIP_COST_PP,
                "beat_benchmark": excess > 0,
            }
        records.append(row)

    report = {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "execution_rule_id": EXECUTION_RULE_ID,
        "evidence_class": "HISTORICAL_POINT_IN_TIME_DEVELOPMENT",
        "market_data_cutoff_session": MARKET_DATA_CUTOFF.isoformat(),
        "event_panel_sha256": stored_panel_hash,
        "event_count": len(records),
        "records": records,
    }
    report["report_sha256"] = canonical_hash(report)
    return report


def _cluster_bootstrap_mean(
    rows: list[dict[str, Any]],
) -> tuple[float | None, float | None, int]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)
    symbols = sorted(by_symbol)
    if len(symbols) < 2:
        return None, None, 0

    rng = random.Random(BOOTSTRAP_SEED)
    means: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sampled: list[dict[str, Any]] = []
        for _cluster in symbols:
            sampled.extend(by_symbol[rng.choice(symbols)])
        if sampled:
            means.append(
                statistics.fmean(float(row["gross_excess_pp"]) for row in sampled)
            )
    if not means:
        return None, None, 0
    low, high = np.quantile(np.asarray(means, dtype=float), [0.025, 0.975])
    return float(low), float(high), len(means)


def _complete_rows(report: dict[str, Any], *, horizon: int) -> list[dict[str, Any]]:
    key = str(horizon)
    result = []
    for row in report["records"]:
        outcome = row["horizons"][key]
        if outcome["status"] == "COMPLETE":
            result.append(
                {
                    "event_id": row["event_id"],
                    "symbol": row["symbol"],
                    "entry_session_date": row["entry_session_date"],
                    "entry_index": row["entry_index"],
                    "publication_month": row["publication_month"],
                    "purchase_value_inr": row["purchase_value_inr"],
                    "gross_excess_pp": outcome["gross_excess_pp"],
                    "cost_adjusted_excess_pp": outcome[
                        "cost_adjusted_excess_pp"
                    ],
                    "beat_benchmark": outcome["beat_benchmark"],
                }
            )
    return result


def _basic_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "distinct_symbol_count": 0,
            "mean_excess_pp": None,
            "median_excess_pp": None,
            "mean_cost_adjusted_excess_pp": None,
            "benchmark_beat_rate": None,
        }
    excess = [float(row["gross_excess_pp"]) for row in rows]
    return {
        "count": len(rows),
        "distinct_symbol_count": len({str(row["symbol"]) for row in rows}),
        "mean_excess_pp": statistics.fmean(excess),
        "median_excess_pp": statistics.median(excess),
        "mean_cost_adjusted_excess_pp": statistics.fmean(
            float(row["cost_adjusted_excess_pp"]) for row in rows
        ),
        "benchmark_beat_rate": statistics.fmean(
            1.0 if row["beat_benchmark"] else 0.0 for row in rows
        ),
    }


def _first_event_per_symbol(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(
        rows, key=lambda item: (item["entry_index"], item["symbol"], item["event_id"])
    ):
        symbol = str(row["symbol"])
        if symbol in seen:
            continue
        seen.add(symbol)
        result.append(row)
    return result


def _non_overlapping_60(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)
    retained: list[dict[str, Any]] = []
    for symbol in sorted(by_symbol):
        last_exit_index = -1
        for row in sorted(
            by_symbol[symbol], key=lambda item: (item["entry_index"], item["event_id"])
        ):
            entry_index = int(row["entry_index"])
            if entry_index <= last_exit_index:
                continue
            retained.append(row)
            last_exit_index = entry_index + PRIMARY_HORIZON - 1
    return retained


def _composition(rows: list[dict[str, Any]], key_fn: Any) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(key_fn(row))].append(row)
    return {key: _basic_stats(grouped[key]) for key in sorted(grouped)}


def purchase_value_bucket(value: float) -> str:
    if not math.isfinite(value) or value <= 0:
        raise H024HistoricalError("purchase value must be positive and finite")
    for name, low, high in PURCHASE_VALUE_BUCKETS:
        if low <= value < high:
            return name
    raise H024HistoricalError("purchase value bucket resolution failed")


def evaluate_horizon(report: dict[str, Any], *, horizon: int) -> dict[str, Any]:
    if horizon not in HORIZONS:
        raise H024HistoricalError(
            f"unsupported H024 evaluation horizon: {horizon}"
        )
    key = str(horizon)
    mature = [
        row
        for row in report["records"]
        if row["horizons"][key]["status"] != "NOT_MATURE"
    ]
    complete = _complete_rows(report, horizon=horizon)
    statuses: dict[str, int] = defaultdict(int)
    for row in report["records"]:
        statuses[str(row["horizons"][key]["status"])] += 1
    stats = _basic_stats(complete)
    low, high, valid = _cluster_bootstrap_mean(complete)
    result = {
        "horizon_sessions": horizon,
        "event_count": len(report["records"]),
        "mature_event_count": len(mature),
        "complete_count": stats["count"],
        "complete_symbol_count": stats["distinct_symbol_count"],
        "complete_share_of_mature": len(complete) / len(mature) if mature else None,
        "status_counts": dict(sorted(statuses.items())),
        "mean_excess_pp": stats["mean_excess_pp"],
        "median_excess_pp": stats["median_excess_pp"],
        "mean_cost_adjusted_excess_pp": stats[
            "mean_cost_adjusted_excess_pp"
        ],
        "benchmark_beat_rate": stats["benchmark_beat_rate"],
        "cluster_bootstrap_ci_95_low_pp": low,
        "cluster_bootstrap_ci_95_high_pp": high,
        "cluster_bootstrap_valid_iterations": valid,
    }
    if horizon == PRIMARY_HORIZON:
        first_rows = _first_event_per_symbol(complete)
        nonoverlap_rows = _non_overlapping_60(complete)
        result["robustness"] = {
            "first_event_per_symbol": _basic_stats(first_rows),
            "non_overlapping_60": _basic_stats(nonoverlap_rows),
            "publication_month": _composition(
                complete, lambda row: row["publication_month"]
            ),
            "purchase_value_bucket": _composition(
                complete,
                lambda row: purchase_value_bucket(float(row["purchase_value_inr"])),
            ),
            "industry": {
                "status": "UNAVAILABLE_PRE_EVENT_SOURCE_NOT_FROZEN",
                "groups": {},
            },
        }
    return result


def classify_primary(primary: dict[str, Any]) -> str:
    mature = int(primary["mature_event_count"])
    complete = int(primary["complete_count"])
    symbols = int(primary["complete_symbol_count"])
    share = primary["complete_share_of_mature"]
    if (
        complete < MIN_PRIMARY_EVENTS
        or symbols < MIN_PRIMARY_SYMBOLS
        or mature == 0
        or share is None
        or float(share) < MIN_COMPLETE_SHARE
    ):
        return "INSUFFICIENT_COVERAGE"

    mean_excess = float(primary["mean_excess_pp"])
    median_excess = float(primary["median_excess_pp"])
    beat_rate = float(primary["benchmark_beat_rate"])
    ci_low = primary["cluster_bootstrap_ci_95_low_pp"]
    first_mean = primary["robustness"]["first_event_per_symbol"]["mean_excess_pp"]
    nonoverlap_mean = primary["robustness"]["non_overlapping_60"]["mean_excess_pp"]
    robustness_positive = (
        first_mean is not None
        and nonoverlap_mean is not None
        and float(first_mean) > 0.0
        and float(nonoverlap_mean) > 0.0
    )
    if mean_excess <= 0.0 or median_excess <= 0.0:
        return "REJECTED"
    if (
        mean_excess >= 4.0
        and ci_low is not None
        and float(ci_low) > 0.0
        and beat_rate >= 0.55
        and robustness_positive
    ):
        return "STRONG"
    if (
        mean_excess >= 2.0
        and median_excess > 0.0
        and beat_rate >= 0.55
        and robustness_positive
    ):
        return "PROMISING"
    return "INCONCLUSIVE"


def summarize_outcomes(report: dict[str, Any]) -> dict[str, Any]:
    stored = report.get("report_sha256")
    unsigned = dict(report)
    unsigned.pop("report_sha256", None)
    if stored != canonical_hash(unsigned):
        raise H024HistoricalError("H024 outcome report hash mismatch")
    horizons = {
        str(horizon): evaluate_horizon(report, horizon=horizon)
        for horizon in HORIZONS
    }
    classification = classify_primary(horizons[str(PRIMARY_HORIZON)])
    summary = {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "execution_rule_id": EXECUTION_RULE_ID,
        "event_panel_sha256": report["event_panel_sha256"],
        "outcome_report_sha256": stored,
        "evidence_class": report["evidence_class"],
        "market_data_cutoff_session": report["market_data_cutoff_session"],
        "event_count": report["event_count"],
        "primary_horizon_sessions": PRIMARY_HORIZON,
        "primary_classification": classification,
        "horizons": horizons,
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = canonical_hash(summary)
    return summary
