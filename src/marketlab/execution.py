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
COST_SCENARIOS_BPS = (0, 25, 50)
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
    """One point-in-time market-data record for a session.

    `source_timestamp_utc` is when this exact record was available to MarketLab.
    If the record contains an open it cannot predate the session open. If it
    contains a close it cannot predate the session close.
    """

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
    entry_session_date: str
    exit_session_date: str
    entry_price: float | None
    exit_price: float | None
    entry_source: str | None
    exit_source: str | None
    entry_source_timestamp_utc: str | None
    exit_source_timestamp_utc: str | None
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
    signal_version: str
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
    calendar_sha256: str
    entry_session_date: str | None
    exit_session_date: str | None
    status: PositionStatus
    skip_or_pending_reason: str | None
    entry_price: float | None
    exit_price: float | None
    entry_price_source: str | None
    exit_price_source: str | None
    entry_source_timestamp_utc: str | None
    exit_source_timestamp_utc: str | None
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

    Trading sessions are never inferred from weekdays. The exact ordered session
    set is hashed and becomes part of every paper-position identity.
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

        session_dates = [session.session_date for session in normalized]
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
        # Never trade event day. Skip the first exchange session after it and
        # enter the second. Entry itself is holding session 1.
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
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
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
    if tuple(document.get("cost_scenarios_round_trip_bps", ())) != COST_SCENARIOS_BPS:
        raise ExecutionError("execution cost scenarios do not match frozen H002-X001")
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
        if not bar.instrument_id.strip():
            raise ExecutionError("market bar instrument_id is required")
        if not bar.source.strip():
            raise ExecutionError("market bar source is required")
        _parse_date(bar.session_date, field="price bar session_date")
        key = _bar_key(bar.instrument_id, bar.session_date)
        if key in indexed:
            raise ExecutionError(
                f"duplicate market bar for {bar.instrument_id} on {bar.session_date}"
            )
        indexed[key] = bar
    return indexed


def _bar_available_as_of(
    bar: PriceBar,
    session: TradingSession,
    *,
    evaluation_as_of: datetime,
) -> bool:
    if bar.session_date != session.session_date:
        raise ExecutionError("market bar session does not match scheduled session")
    available_at = _parse_timestamp(bar.source_timestamp_utc, field="price source timestamp")
    session_open = _parse_timestamp(session.open_timestamp_utc, field="session open")
    session_close = _parse_timestamp(session.close_timestamp_utc, field="session close")

    if bar.open_price is not None:
        if bar.open_price <= 0:
            raise ExecutionError("market bar open price must be positive")
        if available_at < session_open:
            raise ExecutionError("market bar containing open predates the session open")
    if bar.close_price is not None:
        if bar.close_price <= 0:
            raise ExecutionError("market bar close price must be positive")
        if available_at < session_close:
            raise ExecutionError("market bar containing close predates the session close")
    return available_at <= evaluation_as_of


def _return_pct(entry_price: float, exit_price: float) -> float:
    if entry_price <= 0 or exit_price <= 0:
        raise ExecutionError("entry and exit prices must be positive")
    return (exit_price / entry_price - 1.0) * 100.0


def _missing_benchmark(
    benchmark_id: str,
    entry_session: TradingSession,
    exit_session: TradingSession,
    *,
    entry: PriceBar | None,
    exit_bar: PriceBar | None,
    reason: str,
) -> BenchmarkOutcome:
    return BenchmarkOutcome(
        benchmark_id=benchmark_id,
        status="MISSING",
        entry_session_date=entry_session.session_date,
        exit_session_date=exit_session.session_date,
        entry_price=None if entry is None else entry.open_price,
        exit_price=None if exit_bar is None else exit_bar.close_price,
        entry_source=None if entry is None else entry.source,
        exit_source=None if exit_bar is None else exit_bar.source,
        entry_source_timestamp_utc=None if entry is None else entry.source_timestamp_utc,
        exit_source_timestamp_utc=None if exit_bar is None else exit_bar.source_timestamp_utc,
        return_pct=None,
        excess_return_pct=None,
        reason=reason,
    )


def _benchmark_outcome(
    benchmark_id: str,
    *,
    entry_session: TradingSession,
    exit_session: TradingSession,
    bars: dict[tuple[str, str], PriceBar],
    stock_return_pct: float,
    evaluation_as_of: datetime,
) -> BenchmarkOutcome:
    entry = bars.get(_bar_key(benchmark_id, entry_session.session_date))
    exit_bar = bars.get(_bar_key(benchmark_id, exit_session.session_date))
    if entry is None or exit_bar is None:
        return _missing_benchmark(
            benchmark_id,
            entry_session,
            exit_session,
            entry=entry,
            exit_bar=exit_bar,
            reason="missing_benchmark_bar",
        )
    entry_available = _bar_available_as_of(
        entry, entry_session, evaluation_as_of=evaluation_as_of
    )
    exit_available = _bar_available_as_of(
        exit_bar, exit_session, evaluation_as_of=evaluation_as_of
    )
    if not entry_available or not exit_available:
        return _missing_benchmark(
            benchmark_id,
            entry_session,
            exit_session,
            entry=entry,
            exit_bar=exit_bar,
            reason="benchmark_data_not_available_as_of",
        )
    if entry.open_price is None or exit_bar.close_price is None:
        return _missing_benchmark(
            benchmark_id,
            entry_session,
            exit_session,
            entry=entry,
            exit_bar=exit_bar,
            reason="missing_benchmark_open_or_close",
        )

    result = _return_pct(entry.open_price, exit_bar.close_price)
    return BenchmarkOutcome(
        benchmark_id=benchmark_id,
        status="COMPLETE",
        entry_session_date=entry_session.session_date,
        exit_session_date=exit_session.session_date,
        entry_price=entry.open_price,
        exit_price=exit_bar.close_price,
        entry_source=entry.source,
        exit_source=exit_bar.source,
        entry_source_timestamp_utc=entry.source_timestamp_utc,
        exit_source_timestamp_utc=exit_bar.source_timestamp_utc,
        return_pct=result,
        excess_return_pct=stock_return_pct - result,
        reason=None,
    )


def _position_base(
    signal: H002SignalResult,
    *,
    publication: datetime,
    evaluation_as_of: datetime,
    calendar: TradingCalendar,
    position_id: str,
    entry_session: TradingSession | None,
    exit_session: TradingSession | None,
    sector_benchmark_id: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "execution_rule_id": EXECUTION_RULE_ID,
        "signal_rule_id": signal.rule_id,
        "signal_version": signal.signal_version,
        "hypothesis_id": "H002",
        "position_id": position_id,
        "event_id": signal.event_id,
        "event_version_id": signal.event_version_id,
        "expectation_id": signal.expectation_id,
        "symbol": signal.symbol,
        "signal_bucket": signal.bucket,
        "signal_ue": signal.ue,
        "decision_timestamp_utc": signal.scored_at_utc,
        "exchange_published_at_utc": publication.isoformat().replace("+00:00", "Z"),
        "evaluation_as_of_utc": evaluation_as_of.isoformat().replace("+00:00", "Z"),
        "calendar_version": calendar.version,
        "calendar_sha256": calendar.sha256,
        "entry_session_date": None if entry_session is None else entry_session.session_date,
        "exit_session_date": None if exit_session is None else exit_session.session_date,
        "sector_benchmark_id": sector_benchmark_id,
        "live_order_created": False,
    }


def _paper_position(
    base: dict[str, Any],
    *,
    status: PositionStatus,
    reason: str | None,
    entry_bar: PriceBar | None = None,
    exit_bar: PriceBar | None = None,
    gross_return_pct: float | None = None,
    cost_stressed_return_pct: dict[str, float] | None = None,
    benchmarks: tuple[BenchmarkOutcome, ...] = (),
) -> PaperPosition:
    return PaperPosition(
        **base,
        status=status,
        skip_or_pending_reason=reason,
        entry_price=None if entry_bar is None else entry_bar.open_price,
        exit_price=None if exit_bar is None else exit_bar.close_price,
        entry_price_source=None if entry_bar is None else entry_bar.source,
        exit_price_source=None if exit_bar is None else exit_bar.source,
        entry_source_timestamp_utc=None if entry_bar is None else entry_bar.source_timestamp_utc,
        exit_source_timestamp_utc=None if exit_bar is None else exit_bar.source_timestamp_utc,
        corporate_action_version=(
            None if entry_bar is None else entry_bar.corporate_action_version
        ),
        gross_return_pct=gross_return_pct,
        cost_stressed_return_pct=cost_stressed_return_pct,
        benchmarks=benchmarks,
    )


def build_paper_position(
    signal: H002SignalResult,
    *,
    exchange_published_at_utc: str,
    calendar: TradingCalendar,
    stock_bars: list[PriceBar],
    benchmark_bars: list[PriceBar],
    evaluation_as_of_utc: str,
    sector_benchmark_id: str | None = None,
) -> PaperPosition:
    """Create/reconstruct one H002 paper observation under H002-X001.

    No broker action is performed. Every non-NO_SIGNAL bucket is observed long so
    subsequent returns can be compared without introducing a short-selling rule.
    """

    if signal.rule_id != SIGNAL_RULE_ID:
        raise ExecutionError(f"unexpected signal rule: {signal.rule_id}")
    publication = _parse_timestamp(
        exchange_published_at_utc, field="exchange_published_at_utc"
    )
    decision = _parse_timestamp(signal.scored_at_utc, field="signal decision timestamp")
    evaluation_as_of = _parse_timestamp(
        evaluation_as_of_utc, field="evaluation_as_of_utc"
    )
    if decision < publication:
        raise ExecutionError("signal decision timestamp precedes publication")
    if evaluation_as_of < publication:
        raise ExecutionError("evaluation_as_of precedes filing publication")
    if evaluation_as_of < decision:
        raise ExecutionError("evaluation_as_of precedes signal decision timestamp")

    base_identity = {
        "execution_rule_id": EXECUTION_RULE_ID,
        "event_id": signal.event_id,
        "event_version_id": signal.event_version_id,
        "expectation_id": signal.expectation_id,
        "signal_version": signal.signal_version,
        "symbol": signal.symbol.upper(),
        "calendar_version": calendar.version,
        "calendar_sha256": calendar.sha256,
    }
    position_id = _canonical_hash(base_identity)[:24]

    if signal.bucket == "NO_SIGNAL":
        base = _position_base(
            signal,
            publication=publication,
            evaluation_as_of=evaluation_as_of,
            calendar=calendar,
            position_id=position_id,
            entry_session=None,
            exit_session=None,
            sector_benchmark_id=sector_benchmark_id,
        )
        return _paper_position(
            base,
            status="SKIPPED",
            reason=signal.no_signal_reason or "NO_SIGNAL",
        )

    entry_session, exit_session = calendar.schedule(exchange_published_at_utc)
    base = _position_base(
        signal,
        publication=publication,
        evaluation_as_of=evaluation_as_of,
        calendar=calendar,
        position_id=position_id,
        entry_session=entry_session,
        exit_session=exit_session,
        sector_benchmark_id=sector_benchmark_id,
    )
    entry_open = _parse_timestamp(entry_session.open_timestamp_utc, field="entry session open")
    entry_close = _parse_timestamp(entry_session.close_timestamp_utc, field="entry session close")
    exit_close = _parse_timestamp(exit_session.close_timestamp_utc, field="exit session close")

    if decision >= entry_open:
        return _paper_position(
            base,
            status="SKIPPED",
            reason="signal_not_available_before_entry_open",
        )
    if evaluation_as_of < entry_open:
        return _paper_position(base, status="PENDING", reason="entry_not_due")

    stock_index = _index_bars(stock_bars)
    entry_bar = stock_index.get(_bar_key(signal.symbol, entry_session.session_date))
    entry_available = False
    if entry_bar is not None:
        entry_available = _bar_available_as_of(
            entry_bar,
            entry_session,
            evaluation_as_of=evaluation_as_of,
        )

    entry_problem: str | None = None
    if entry_bar is None:
        entry_problem = "missing_entry_bar"
    elif not entry_available:
        entry_problem = "entry_data_not_available_as_of"
    elif entry_bar.open_price is None:
        entry_problem = "missing_entry_open"
    elif entry_bar.tradable_at_open is not True:
        entry_problem = "entry_not_confirmed_tradable"
    elif not (entry_bar.corporate_action_version or "").strip():
        entry_problem = "missing_entry_corporate_action_version"

    if entry_problem is not None:
        if evaluation_as_of < entry_close:
            return _paper_position(
                base,
                status="PENDING",
                reason="entry_market_data_not_final_as_of",
            )
        return _paper_position(
            base,
            status="SKIPPED",
            reason=entry_problem,
            entry_bar=entry_bar if entry_available else None,
        )

    assert entry_bar is not None and entry_bar.open_price is not None
    if evaluation_as_of < exit_close:
        return _paper_position(
            base,
            status="PENDING",
            reason="exit_not_due",
            entry_bar=entry_bar,
        )

    exit_bar = stock_index.get(_bar_key(signal.symbol, exit_session.session_date))
    if exit_bar is None:
        return _paper_position(
            base,
            status="UNRESOLVED_EXIT",
            reason="missing_exit_bar_after_due",
            entry_bar=entry_bar,
        )
    exit_available = _bar_available_as_of(
        exit_bar,
        exit_session,
        evaluation_as_of=evaluation_as_of,
    )
    if not exit_available:
        return _paper_position(
            base,
            status="UNRESOLVED_EXIT",
            reason="exit_data_not_available_as_of",
            entry_bar=entry_bar,
        )
    if exit_bar.close_price is None:
        return _paper_position(
            base,
            status="UNRESOLVED_EXIT",
            reason="missing_exit_close_after_due",
            entry_bar=entry_bar,
            exit_bar=exit_bar,
        )
    if exit_bar.tradable_at_close is not True:
        return _paper_position(
            base,
            status="UNRESOLVED_EXIT",
            reason="exit_not_confirmed_tradable",
            entry_bar=entry_bar,
            exit_bar=exit_bar,
        )
    if not (exit_bar.corporate_action_version or "").strip():
        raise ExecutionError("exit corporate_action_version is required")
    if exit_bar.corporate_action_version != entry_bar.corporate_action_version:
        raise ExecutionError(
            "entry/exit corporate-action versions differ; normalized price series is not proven comparable"
        )

    gross_return = _return_pct(entry_bar.open_price, exit_bar.close_price)
    cost_results = {
        str(bps): gross_return - (bps / 100.0) for bps in COST_SCENARIOS_BPS
    }

    benchmark_index = _index_bars(benchmark_bars)
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
            evaluation_as_of=evaluation_as_of,
        )
        for benchmark_id in benchmark_ids
    )

    return _paper_position(
        base,
        status="COMPLETED",
        reason=None,
        entry_bar=entry_bar,
        exit_bar=exit_bar,
        gross_return_pct=gross_return,
        cost_stressed_return_pct=cost_results,
        benchmarks=outcomes,
    )
