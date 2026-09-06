from __future__ import annotations

import hashlib
import json
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
    calendar_version: str
    entry_session_date: str | None
    exit_session_date: str | None
    status: PositionStatus
    skip_or_pending_reason: str | None
    entry_price: float | None
    exit_price: float | None
    stock_price_source: str | None
    corporate_action_version: str | None
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
    """Versioned explicit NSE session calendar.

    MarketLab never infers trading sessions from weekdays. The caller must supply
    the exchange session list captured/versioned by the research pipeline.
    """

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
        if [item.session_date for item in normalized] != sorted(item.session_date for item in normalized):
            raise ExecutionError("trading sessions must be sorted ascending")
        self.sessions = tuple(normalized)
        self.version = version
        self._index = {session.session_date: index for index, session in enumerate(self.sessions)}

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
        # Skip the first eligible session after the event. Enter the second.
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
    except ValueError as exc:
        raise ExecutionError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise ExecutionError(f"{field} must include timezone: {value}")
    return parsed.astimezone(UTC)


def _parse_date(value: str, *, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ExecutionError(f"invalid {field}: {value}") from exc


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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


def _validate_bar_timestamp(bar: PriceBar) -> None:
    _parse_timestamp(bar.source_timestamp_utc, field="price source timestamp")


def _return_pct(entry_price: float, exit_price: float) -> float:
    if entry_price <= 0 or exit_price <= 0:
        raise ExecutionError("entry and exit prices must be positive")
    return (exit_price / entry_price - 1.0) * 100.0


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
    _validate_bar_timestamp(entry)
    _validate_bar_timestamp(exit_bar)
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


def build_paper_position(
    signal: H002SignalResult,
    *,
    exchange_published_at_utc: str,
    calendar: TradingCalendar,
    stock_bars: list[PriceBar],
    benchmark_bars: list[PriceBar],
    as_of_date: str,
    sector_benchmark_id: str | None = None,
    cost_scenarios_bps: tuple[int, ...] = (0, 25, 50),
) -> PaperPosition:
    """Create/reconstruct one H002 paper observation under H002-X001.

    No broker action is performed. Every non-NO_SIGNAL bucket is observed long so
    subsequent returns can be compared across signal groups without introducing a
    separate short-selling hypothesis.
    """

    if signal.rule_id != SIGNAL_RULE_ID:
        raise ExecutionError(f"unexpected signal rule: {signal.rule_id}")
    publication = _parse_timestamp(
        exchange_published_at_utc, field="exchange_published_at_utc"
    )
    decision = _parse_timestamp(signal.scored_at_utc, field="signal decision timestamp")
    if decision < publication:
        raise ExecutionError("signal decision timestamp precedes publication")
    as_of = _parse_date(as_of_date, field="as_of_date")

    base_identity = {
        "execution_rule_id": EXECUTION_RULE_ID,
        "event_id": signal.event_id,
        "event_version_id": signal.event_version_id,
        "expectation_id": signal.expectation_id,
        "symbol": signal.symbol.upper(),
        "calendar_version": calendar.version,
    }
    position_id = _canonical_hash(base_identity)[:24]

    if signal.bucket == "NO_SIGNAL":
        return PaperPosition(
            schema_version=1,
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
            calendar_version=calendar.version,
            entry_session_date=None,
            exit_session_date=None,
            status="SKIPPED",
            skip_or_pending_reason=signal.no_signal_reason or "NO_SIGNAL",
            entry_price=None,
            exit_price=None,
            stock_price_source=None,
            corporate_action_version=None,
            gross_return_pct=None,
            cost_stressed_return_pct=None,
            benchmarks=(),
            sector_benchmark_id=sector_benchmark_id,
            live_order_created=False,
        )

    entry_session, exit_session = calendar.schedule(exchange_published_at_utc)
    stock_index = {_bar_key(bar.instrument_id, bar.session_date): bar for bar in stock_bars}
    entry_bar = stock_index.get(_bar_key(signal.symbol, entry_session.session_date))
    if entry_bar is None:
        skip_reason = "missing_entry_bar"
    elif entry_bar.open_price is None:
        skip_reason = "missing_entry_open"
    elif entry_bar.tradable_at_open is not True:
        skip_reason = "entry_not_confirmed_tradable"
    elif not (entry_bar.corporate_action_version or "").strip():
        skip_reason = "missing_entry_corporate_action_version"
    else:
        skip_reason = None
        _validate_bar_timestamp(entry_bar)

    if skip_reason is not None:
        return PaperPosition(
            schema_version=1,
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
            calendar_version=calendar.version,
            entry_session_date=entry_session.session_date,
            exit_session_date=exit_session.session_date,
            status="SKIPPED",
            skip_or_pending_reason=skip_reason,
            entry_price=None if entry_bar is None else entry_bar.open_price,
            exit_price=None,
            stock_price_source=None if entry_bar is None else entry_bar.source,
            corporate_action_version=(
                None if entry_bar is None else entry_bar.corporate_action_version
            ),
            gross_return_pct=None,
            cost_stressed_return_pct=None,
            benchmarks=(),
            sector_benchmark_id=sector_benchmark_id,
            live_order_created=False,
        )

    assert entry_bar is not None and entry_bar.open_price is not None
    exit_bar = stock_index.get(_bar_key(signal.symbol, exit_session.session_date))
    if exit_bar is None or exit_bar.close_price is None:
        due = _parse_date(exit_session.session_date, field="exit_session_date")
        status: PositionStatus = "PENDING" if as_of < due else "UNRESOLVED_EXIT"
        reason = "exit_not_due" if status == "PENDING" else "missing_exit_close_after_due_session"
        return PaperPosition(
            schema_version=1,
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
            calendar_version=calendar.version,
            entry_session_date=entry_session.session_date,
            exit_session_date=exit_session.session_date,
            status=status,
            skip_or_pending_reason=reason,
            entry_price=entry_bar.open_price,
            exit_price=None,
            stock_price_source=entry_bar.source,
            corporate_action_version=entry_bar.corporate_action_version,
            gross_return_pct=None,
            cost_stressed_return_pct=None,
            benchmarks=(),
            sector_benchmark_id=sector_benchmark_id,
            live_order_created=False,
        )

    _validate_bar_timestamp(exit_bar)
    if not (exit_bar.corporate_action_version or "").strip():
        raise ExecutionError("exit corporate_action_version is required")
    if exit_bar.corporate_action_version != entry_bar.corporate_action_version:
        raise ExecutionError(
            "entry/exit corporate_action versions differ; normalized price series is not proven comparable"
        )
    gross_return = _return_pct(entry_bar.open_price, exit_bar.close_price)
    cost_results = {
        str(bps): gross_return - (bps / 100.0) for bps in cost_scenarios_bps
    }

    benchmark_index = {
        _bar_key(bar.instrument_id, bar.session_date): bar for bar in benchmark_bars
    }
    benchmark_ids = list(REQUIRED_BENCHMARKS)
    if sector_benchmark_id:
        benchmark_ids.append(sector_benchmark_id)
    outcomes = tuple(
        _benchmark_outcome(
            benchmark_id,
            entry_session=entry_session,
            exit_session=exit_session,
            bars=benchmark_index,
            stock_return_pct=gross_return,
        )
        for benchmark_id in benchmark_ids
    )

    return PaperPosition(
        schema_version=1,
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
        calendar_version=calendar.version,
        entry_session_date=entry_session.session_date,
        exit_session_date=exit_session.session_date,
        status="COMPLETED",
        skip_or_pending_reason=None,
        entry_price=entry_bar.open_price,
        exit_price=exit_bar.close_price,
        stock_price_source=entry_bar.source,
        corporate_action_version=entry_bar.corporate_action_version,
        gross_return_pct=gross_return,
        cost_stressed_return_pct=cost_results,
        benchmarks=outcomes,
        sector_benchmark_id=sector_benchmark_id,
        live_order_created=False,
    )
