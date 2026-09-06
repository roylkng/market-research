from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import yaml

from marketlab.h002 import H002SignalResult

EXECUTION_RULE_ID = "H002-X001"
SIGNAL_RULE_ID = "H002-R001"
REQUIRED_BENCHMARKS = ("nifty_50", "nifty_200_momentum_30")
IST = ZoneInfo("Asia/Kolkata")

PositionStatus = Literal["SKIPPED", "PENDING", "UNRESOLVED_EXIT", "COMPLETED"]
BenchmarkStatus = Literal["COMPLETE", "MISSING"]


class ExecutionError(ValueError):
    """Raised when paper-execution inputs violate the frozen H002-C contract."""


@dataclass(frozen=True)
class TradingSession:
    session_date: str
    open_timestamp_utc: str
    close_timestamp_utc: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class PriceBar:
    instrument_id: str
    session_date: str
    open_price: float | None
    close_price: float | None
    source: str
    source_timestamp_utc: str
    tradable_at_open: bool | None = None
    tradable_at_close: bool | None = None
    corporate_action_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkOutcome:
    benchmark_id: str
    status: BenchmarkStatus
    entry_price: float | None
    exit_price: float | None
    return_pct: float | None
    excess_return_pct: float | None
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperPosition:
    schema_version: int
    execution_rule_id: str
    signal_rule_id: str
    hypothesis_id: str
    position_id: str
    event_id: str
    event_version_id: str
    expectation_id: str
    symbol: str
    signal_bucket: str
    signal_ue: float | None
    decision_timestamp_utc: str
    exchange_published_at_utc: str
    evaluation_as_of_utc: str
    calendar_version: str
    calendar_snapshot_sha256: str
    entry_session_date: str | None
    exit_session_date: str | None
    status: PositionStatus
    skip_or_pending_reason: str | None
    entry_price: float | None
    exit_price: float | None
    entry_price_source: str | None
    exit_price_source: str | None
    entry_corporate_action_version: str | None
    exit_corporate_action_version: str | None
    gross_return_pct: float | None
    cost_stressed_return_pct: dict[str, float] | None
    benchmarks: tuple[BenchmarkOutcome, ...]
    sector_benchmark_id: str | None
    live_order_created: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["benchmarks"] = [benchmark.to_dict() for benchmark in self.benchmarks]
        return payload


class TradingCalendar:
    """Versioned explicit NSE session calendar with deterministic content hash."""

    def __init__(self, sessions: list[TradingSession], *, version: str) -> None:
        if not version.strip():
            raise ExecutionError("calendar version is required")
        if not sessions:
            raise ExecutionError("trading calendar must contain sessions")

        normalized: list[TradingSession] = []
        seen: set[str] = set()
        for session in sessions:
            session_date = _parse_date(session.session_date, field="session_date")
            if session.session_date in seen:
                raise ExecutionError(f"duplicate trading session: {session.session_date}")
            seen.add(session.session_date)
            opened = _parse_timestamp(session.open_timestamp_utc, field="session open")
            closed = _parse_timestamp(session.close_timestamp_utc, field="session close")
            if opened >= closed:
                raise ExecutionError(f"session open must precede close: {session.session_date}")
            if opened.astimezone(IST).date() != session_date:
                raise ExecutionError(f"session open date mismatch: {session.session_date}")
            if closed.astimezone(IST).date() != session_date:
                raise ExecutionError(f"session close date mismatch: {session.session_date}")
            normalized.append(session)

        session_dates = [item.session_date for item in normalized]
        if session_dates != sorted(session_dates):
            raise ExecutionError("trading sessions must be sorted ascending")

        self.sessions = tuple(normalized)
        self.version = version
        self._index = {session.session_date: index for index, session in enumerate(self.sessions)}
        self.sha256 = _canonical_hash(
            {
                "version": version,
                "sessions": [session.to_dict() for session in self.sessions],
            }
        )

    def schedule(self, exchange_published_at_utc: str) -> tuple[TradingSession, TradingSession]:
        publication = _parse_timestamp(
            exchange_published_at_utc, field="exchange_published_at_utc"
        )
        event_local_date = publication.astimezone(IST).date()
        future = [
            session
            for session in self.sessions
            if _parse_date(session.session_date, field="session_date") > event_local_date
        ]
        if len(future) < 21:
            raise ExecutionError("calendar does not contain enough future sessions for 20-session hold")
        entry = future[1]
        entry_index = self._index[entry.session_date]
        exit_index = entry_index + 19
        if exit_index >= len(self.sessions):
            raise ExecutionError("calendar does not contain the 20th holding session")
        return entry, self.sessions[exit_index]


def _parse_timestamp(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ExecutionError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise ExecutionError(f"{field} must include timezone: {value}")
    return parsed.astimezone(UTC)


def _parse_date(value: str, *, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ExecutionError(f"invalid {field}: {value}") from exc


def _canonical_hash(payload: dict[str, Any]) -> str:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ExecutionError("canonical payload must contain finite JSON values") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _finite_price(value: float, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExecutionError(f"{field} must be a finite positive number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ExecutionError(f"{field} must be a finite positive number")
    return result


def validate_execution_rule_document(document: dict[str, Any]) -> str:
    if not isinstance(document, dict):
        raise ExecutionError("H002 execution rule root must be a mapping")
    declared = document.get("sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise ExecutionError("H002 execution rule must declare sha256")
    unsigned = dict(document)
    unsigned.pop("sha256", None)
    actual = _canonical_hash(unsigned)
    if actual != declared:
        raise ExecutionError(
            f"H002 execution rule hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("id") != EXECUTION_RULE_ID:
        raise ExecutionError(f"unexpected execution rule id: {document.get('id')}")
    if document.get("status") != "FROZEN":
        raise ExecutionError("H002 execution rule must remain FROZEN")
    if document.get("live_capital") is not False:
        raise ExecutionError("H002 execution rule must keep live_capital: false")
    return actual


def load_and_validate_execution_rule(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    validate_execution_rule_document(document)
    return document


def _bar_key(instrument_id: str, session_date: str) -> tuple[str, str]:
    return instrument_id.casefold(), session_date


def _index_bars(bars: list[PriceBar]) -> dict[tuple[str, str], PriceBar]:
    indexed: dict[tuple[str, str], PriceBar] = {}
    for bar in bars:
        if not isinstance(bar.instrument_id, str) or not bar.instrument_id.strip():
            raise ExecutionError("market-data instrument_id is required")
        _parse_date(bar.session_date, field="market-data session_date")
        if not isinstance(bar.source, str) or not bar.source.strip():
            raise ExecutionError("market-data source is required")
        _parse_timestamp(bar.source_timestamp_utc, field="price source timestamp")
        if bar.open_price is not None:
            _finite_price(bar.open_price, field="open_price")
        if bar.close_price is not None:
            _finite_price(bar.close_price, field="close_price")
        key = _bar_key(bar.instrument_id, bar.session_date)
        if key in indexed:
            raise ExecutionError(
                f"duplicate market bar for {bar.instrument_id} {bar.session_date}"
            )
        indexed[key] = bar
    return indexed


def _available_as_of(
    indexed: dict[tuple[str, str], PriceBar], *, as_of: datetime
) -> dict[tuple[str, str], PriceBar]:
    return {
        key: bar
        for key, bar in indexed.items()
        if _parse_timestamp(bar.source_timestamp_utc, field="price source timestamp") <= as_of
    }


def _ensure_open_value_could_exist(bar: PriceBar, session: TradingSession) -> None:
    if bar.open_price is None:
        return
    source_timestamp = _parse_timestamp(bar.source_timestamp_utc, field="price source timestamp")
    session_open = _parse_timestamp(session.open_timestamp_utc, field="session open")
    if source_timestamp < session_open:
        raise ExecutionError(
            f"market-data source predates open value: {bar.instrument_id} {bar.session_date}"
        )


def _ensure_close_value_could_exist(bar: PriceBar, session: TradingSession) -> None:
    if bar.close_price is None:
        return
    source_timestamp = _parse_timestamp(bar.source_timestamp_utc, field="price source timestamp")
    session_close = _parse_timestamp(session.close_timestamp_utc, field="session close")
    if source_timestamp < session_close:
        raise ExecutionError(
            f"market-data source predates close value: {bar.instrument_id} {bar.session_date}"
        )


def _return_pct(entry_price: float, exit_price: float) -> float:
    entry = _finite_price(entry_price, field="entry_price")
    exit_value = _finite_price(exit_price, field="exit_price")
    result = (exit_value / entry - 1.0) * 100.0
    if not math.isfinite(result):
        raise ExecutionError("computed return is not finite")
    return result


def _benchmark_outcome(
    benchmark_id: str,
    *,
    entry_session: TradingSession,
    exit_session: TradingSession,
    bars: dict[tuple[str, str], PriceBar],
    stock_return_pct: float,
) -> BenchmarkOutcome:
    entry = bars.get(_bar_key(benchmark_id, entry_session.session_date))
    exit_bar = bars.get(_bar_key(benchmark_id, exit_session.session_date))
    if entry is None or exit_bar is None:
        return BenchmarkOutcome(
            benchmark_id=benchmark_id,
            status="MISSING",
            entry_price=None if entry is None else entry.open_price,
            exit_price=None if exit_bar is None else exit_bar.close_price,
            return_pct=None,
            excess_return_pct=None,
            reason="missing_benchmark_bar",
        )
    _ensure_open_value_could_exist(entry, entry_session)
    _ensure_close_value_could_exist(exit_bar, exit_session)
    if entry.open_price is None or exit_bar.close_price is None:
        return BenchmarkOutcome(
            benchmark_id=benchmark_id,
            status="MISSING",
            entry_price=entry.open_price,
            exit_price=exit_bar.close_price,
            return_pct=None,
            excess_return_pct=None,
            reason="missing_benchmark_open_or_close",
        )
    result = _return_pct(entry.open_price, exit_bar.close_price)
    return BenchmarkOutcome(
        benchmark_id=benchmark_id,
        status="COMPLETE",
        entry_price=entry.open_price,
        exit_price=exit_bar.close_price,
        return_pct=result,
        excess_return_pct=stock_return_pct - result,
        reason=None,
    )


def _empty_position(
    signal: H002SignalResult,
    *,
    publication: datetime,
    as_of: datetime,
    calendar: TradingCalendar,
    position_id: str,
    status: PositionStatus,
    reason: str,
    sector_benchmark_id: str | None,
    entry_session: TradingSession | None = None,
    exit_session: TradingSession | None = None,
    entry_bar: PriceBar | None = None,
) -> PaperPosition:
    return PaperPosition(
        schema_version=2,
        execution_rule_id=EXECUTION_RULE_ID,
        signal_rule_id=signal.rule_id,
        hypothesis_id="H002",
        position_id=position_id,
        event_id=signal.event_id,
        event_version_id=signal.event_version_id,
        expectation_id=signal.expectation_id,
        symbol=signal.symbol,
        signal_bucket=signal.bucket,
        signal_ue=signal.ue,
        decision_timestamp_utc=signal.scored_at_utc,
        exchange_published_at_utc=publication.isoformat().replace("+00:00", "Z"),
        evaluation_as_of_utc=as_of.isoformat().replace("+00:00", "Z"),
        calendar_version=calendar.version,
        calendar_snapshot_sha256=calendar.sha256,
        entry_session_date=None if entry_session is None else entry_session.session_date,
        exit_session_date=None if exit_session is None else exit_session.session_date,
        status=status,
        skip_or_pending_reason=reason,
        entry_price=None if entry_bar is None else entry_bar.open_price,
        exit_price=None,
        entry_price_source=None if entry_bar is None else entry_bar.source,
        exit_price_source=None,
        entry_corporate_action_version=(
            None if entry_bar is None else entry_bar.corporate_action_version
        ),
        exit_corporate_action_version=None,
        gross_return_pct=None,
        cost_stressed_return_pct=None,
        benchmarks=(),
        sector_benchmark_id=sector_benchmark_id,
        live_order_created=False,
    )


def build_paper_position(
    signal: H002SignalResult,
    *,
    exchange_published_at_utc: str,
    calendar: TradingCalendar,
    stock_bars: list[PriceBar],
    benchmark_bars: list[PriceBar],
    as_of_utc: str,
    sector_benchmark_id: str | None = None,
    cost_scenarios_bps: tuple[int, ...] = (0, 25, 50),
) -> PaperPosition:
    """Create/reconstruct one paper observation under frozen H002-X001."""

    if signal.rule_id != SIGNAL_RULE_ID:
        raise ExecutionError(f"unexpected signal rule: {signal.rule_id}")
    publication = _parse_timestamp(
        exchange_published_at_utc, field="exchange_published_at_utc"
    )
    decision = _parse_timestamp(signal.scored_at_utc, field="signal decision timestamp")
    as_of = _parse_timestamp(as_of_utc, field="as_of_utc")
    if decision < publication:
        raise ExecutionError("signal decision timestamp precedes publication")
    if as_of < decision:
        raise ExecutionError("evaluation as_of precedes signal decision timestamp")
    if any(isinstance(bps, bool) or not isinstance(bps, int) or bps < 0 for bps in cost_scenarios_bps):
        raise ExecutionError("cost scenarios must be non-negative integer basis points")

    all_stock = _index_bars(stock_bars)
    all_benchmarks = _index_bars(benchmark_bars)
    available_stock = _available_as_of(all_stock, as_of=as_of)
    available_benchmarks = _available_as_of(all_benchmarks, as_of=as_of)

    base_identity = {
        "execution_rule_id": EXECUTION_RULE_ID,
        "event_id": signal.event_id,
        "event_version_id": signal.event_version_id,
        "expectation_id": signal.expectation_id,
        "symbol": signal.symbol.upper(),
        "calendar_version": calendar.version,
        "calendar_snapshot_sha256": calendar.sha256,
    }
    position_id = _canonical_hash(base_identity)[:24]

    if signal.bucket == "NO_SIGNAL":
        return _empty_position(
            signal,
            publication=publication,
            as_of=as_of,
            calendar=calendar,
            position_id=position_id,
            status="SKIPPED",
            reason=signal.no_signal_reason or "NO_SIGNAL",
            sector_benchmark_id=sector_benchmark_id,
        )

    entry_session, exit_session = calendar.schedule(exchange_published_at_utc)
    entry_open = _parse_timestamp(entry_session.open_timestamp_utc, field="entry session open")
    entry_close = _parse_timestamp(entry_session.close_timestamp_utc, field="entry session close")
    exit_close = _parse_timestamp(exit_session.close_timestamp_utc, field="exit session close")

    if decision >= entry_open:
        raise ExecutionError("signal decision timestamp must strictly precede scheduled entry open")

    if as_of < entry_open:
        return _empty_position(
            signal,
            publication=publication,
            as_of=as_of,
            calendar=calendar,
            position_id=position_id,
            status="PENDING",
            reason="entry_not_due",
            sector_benchmark_id=sector_benchmark_id,
            entry_session=entry_session,
            exit_session=exit_session,
        )

    entry_bar = available_stock.get(_bar_key(signal.symbol, entry_session.session_date))
    if entry_bar is not None:
        _ensure_open_value_could_exist(entry_bar, entry_session)

    entry_issue: str | None = None
    if entry_bar is None:
        entry_issue = "missing_entry_bar"
    elif entry_bar.open_price is None:
        entry_issue = "missing_entry_open"
    elif entry_bar.tradable_at_open is not True:
        entry_issue = "entry_not_confirmed_tradable"
    elif not (entry_bar.corporate_action_version or "").strip():
        entry_issue = "missing_entry_corporate_action_version"

    if entry_issue is not None:
        if as_of < entry_close:
            return _empty_position(
                signal,
                publication=publication,
                as_of=as_of,
                calendar=calendar,
                position_id=position_id,
                status="PENDING",
                reason=f"{entry_issue}_before_entry_session_close",
                sector_benchmark_id=sector_benchmark_id,
                entry_session=entry_session,
                exit_session=exit_session,
                entry_bar=entry_bar,
            )
        return _empty_position(
            signal,
            publication=publication,
            as_of=as_of,
            calendar=calendar,
            position_id=position_id,
            status="SKIPPED",
            reason=f"{entry_issue}_after_entry_session_close",
            sector_benchmark_id=sector_benchmark_id,
            entry_session=entry_session,
            exit_session=exit_session,
            entry_bar=entry_bar,
        )

    assert entry_bar is not None and entry_bar.open_price is not None
    if as_of < exit_close:
        return _empty_position(
            signal,
            publication=publication,
            as_of=as_of,
            calendar=calendar,
            position_id=position_id,
            status="PENDING",
            reason="exit_not_due",
            sector_benchmark_id=sector_benchmark_id,
            entry_session=entry_session,
            exit_session=exit_session,
            entry_bar=entry_bar,
        )

    exit_bar = available_stock.get(_bar_key(signal.symbol, exit_session.session_date))
    if exit_bar is not None:
        _ensure_close_value_could_exist(exit_bar, exit_session)

    exit_issue: str | None = None
    if exit_bar is None:
        exit_issue = "missing_exit_bar"
    elif exit_bar.close_price is None:
        exit_issue = "missing_exit_close"
    elif exit_bar.tradable_at_close is not True:
        exit_issue = "exit_not_confirmed_tradable"
    elif not (exit_bar.corporate_action_version or "").strip():
        exit_issue = "missing_exit_corporate_action_version"

    if exit_issue is not None:
        return _empty_position(
            signal,
            publication=publication,
            as_of=as_of,
            calendar=calendar,
            position_id=position_id,
            status="UNRESOLVED_EXIT",
            reason=f"{exit_issue}_after_due_close",
            sector_benchmark_id=sector_benchmark_id,
            entry_session=entry_session,
            exit_session=exit_session,
            entry_bar=entry_bar,
        )

    assert exit_bar is not None and exit_bar.close_price is not None
    if exit_bar.corporate_action_version != entry_bar.corporate_action_version:
        raise ExecutionError(
            "entry/exit corporate-action versions differ; normalized price series is not proven comparable"
        )

    gross_return = _return_pct(entry_bar.open_price, exit_bar.close_price)
    cost_results = {str(bps): gross_return - (bps / 100.0) for bps in cost_scenarios_bps}

    benchmark_ids = list(REQUIRED_BENCHMARKS)
    if sector_benchmark_id:
        benchmark_ids.append(sector_benchmark_id)
    outcomes = tuple(
        _benchmark_outcome(
            benchmark_id,
            entry_session=entry_session,
            exit_session=exit_session,
            bars=available_benchmarks,
            stock_return_pct=gross_return,
        )
        for benchmark_id in benchmark_ids
    )

    return PaperPosition(
        schema_version=2,
        execution_rule_id=EXECUTION_RULE_ID,
        signal_rule_id=signal.rule_id,
        hypothesis_id="H002",
        position_id=position_id,
        event_id=signal.event_id,
        event_version_id=signal.event_version_id,
        expectation_id=signal.expectation_id,
        symbol=signal.symbol,
        signal_bucket=signal.bucket,
        signal_ue=signal.ue,
        decision_timestamp_utc=signal.scored_at_utc,
        exchange_published_at_utc=publication.isoformat().replace("+00:00", "Z"),
        evaluation_as_of_utc=as_of.isoformat().replace("+00:00", "Z"),
        calendar_version=calendar.version,
        calendar_snapshot_sha256=calendar.sha256,
        entry_session_date=entry_session.session_date,
        exit_session_date=exit_session.session_date,
        status="COMPLETED",
        skip_or_pending_reason=None,
        entry_price=entry_bar.open_price,
        exit_price=exit_bar.close_price,
        entry_price_source=entry_bar.source,
        exit_price_source=exit_bar.source,
        entry_corporate_action_version=entry_bar.corporate_action_version,
        exit_corporate_action_version=exit_bar.corporate_action_version,
        gross_return_pct=gross_return,
        cost_stressed_return_pct=cost_results,
        benchmarks=outcomes,
        sector_benchmark_id=sector_benchmark_id,
        live_order_created=False,
    )
