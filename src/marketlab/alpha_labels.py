from __future__ import annotations

from dataclasses import asdict, dataclass

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import DailyEquityObservation
from marketlab.marketdata import IndexDailyPrice

AE001_LABEL_ID = "AE001-L001-v1"
ALLOWED_HORIZONS = (1, 5, 20, 60)


@dataclass(frozen=True)
class AlphaLabel:
    label_id: str
    symbol: str
    isin: str
    feature_session: str
    horizon_sessions: int
    status: str
    entry_session: str | None
    exit_session: str | None
    entry_price: float | None
    exit_price: float | None
    benchmark_entry: float | None
    benchmark_exit: float | None
    stock_return: float | None
    benchmark_return: float | None
    excess_return: float | None
    live_capital_allowed: bool = False

    def to_record(self) -> dict:
        record = asdict(self)
        record["label_record_sha256"] = digest(record)
        return record


def _session_index(
    benchmarks: list[IndexDailyPrice],
    *,
    benchmark_id: str,
) -> tuple[list[str], dict[str, IndexDailyPrice]]:
    rows = sorted(
        (row for row in benchmarks if row.benchmark_id == benchmark_id),
        key=lambda row: row.session_date,
    )
    if not rows:
        raise AlphaContractError(f"no benchmark rows for {benchmark_id}")
    by_session: dict[str, IndexDailyPrice] = {}
    for row in rows:
        if row.session_date in by_session:
            raise AlphaContractError(
                f"duplicate benchmark session for {benchmark_id}: {row.session_date}"
            )
        by_session[row.session_date] = row
    return [row.session_date for row in rows], by_session


def _stock_index(
    observations: list[DailyEquityObservation],
    *,
    symbol: str,
) -> dict[str, list[DailyEquityObservation]]:
    by_session: dict[str, list[DailyEquityObservation]] = {}
    for row in observations:
        if row.symbol != symbol.upper():
            continue
        by_session.setdefault(row.session_date, []).append(row)
    return by_session


def build_labels(
    observations: list[DailyEquityObservation],
    benchmarks: list[IndexDailyPrice],
    *,
    symbol: str,
    isin: str,
    feature_session: str,
    evaluation_as_of_session: str,
    benchmark_id: str = "nifty_500",
    horizons: tuple[int, ...] = ALLOWED_HORIZONS,
) -> dict:
    """Build mature AE001 labels without opening horizons beyond evaluation_as_of_session."""

    if any(horizon not in ALLOWED_HORIZONS for horizon in horizons):
        raise AlphaContractError(
            f"horizons must be a subset of {list(ALLOWED_HORIZONS)}"
        )
    sessions, benchmark_by_session = _session_index(
        benchmarks,
        benchmark_id=benchmark_id,
    )
    if feature_session not in benchmark_by_session:
        raise AlphaContractError("feature session is not a completed benchmark session")
    if evaluation_as_of_session not in benchmark_by_session:
        raise AlphaContractError("evaluation_as_of_session is not a completed session")
    feature_index = sessions.index(feature_session)
    as_of_index = sessions.index(evaluation_as_of_session)
    if as_of_index < feature_index:
        raise AlphaContractError("evaluation_as_of_session precedes feature session")
    if feature_index + 1 >= len(sessions):
        raise AlphaContractError("no completed session exists after feature session")

    entry_index = feature_index + 1
    entry_session = sessions[entry_index]
    stocks = _stock_index(observations, symbol=symbol)
    records = []

    for horizon in sorted(set(horizons)):
        exit_index = entry_index + horizon - 1
        if exit_index > as_of_index or exit_index >= len(sessions):
            label = AlphaLabel(
                label_id=AE001_LABEL_ID,
                symbol=symbol.upper(),
                isin=isin,
                feature_session=feature_session,
                horizon_sessions=horizon,
                status="NOT_MATURE",
                entry_session=entry_session,
                exit_session=None,
                entry_price=None,
                exit_price=None,
                benchmark_entry=None,
                benchmark_exit=None,
                stock_return=None,
                benchmark_return=None,
                excess_return=None,
            )
            records.append(label.to_record())
            continue

        exit_session = sessions[exit_index]
        entry_candidates = stocks.get(entry_session, [])
        exit_candidates = stocks.get(exit_session, [])
        entry = next((row for row in entry_candidates if row.isin == isin), None)
        exit_row = next((row for row in exit_candidates if row.isin == isin), None)

        if entry is None or exit_row is None:
            has_other_identity = bool(entry_candidates or exit_candidates)
            status = "IDENTITY_MISMATCH" if has_other_identity else "MISSING_STOCK_BAR"
            label = AlphaLabel(
                label_id=AE001_LABEL_ID,
                symbol=symbol.upper(),
                isin=isin,
                feature_session=feature_session,
                horizon_sessions=horizon,
                status=status,
                entry_session=entry_session,
                exit_session=exit_session,
                entry_price=None,
                exit_price=None,
                benchmark_entry=None,
                benchmark_exit=None,
                stock_return=None,
                benchmark_return=None,
                excess_return=None,
            )
            records.append(label.to_record())
            continue

        benchmark_entry_row = benchmark_by_session[entry_session]
        benchmark_exit_row = benchmark_by_session[exit_session]
        stock_return = exit_row.close_price / entry.open_price - 1.0
        benchmark_return = (
            benchmark_exit_row.close_price / benchmark_entry_row.open_price - 1.0
        )
        label = AlphaLabel(
            label_id=AE001_LABEL_ID,
            symbol=symbol.upper(),
            isin=isin,
            feature_session=feature_session,
            horizon_sessions=horizon,
            status="COMPLETE",
            entry_session=entry_session,
            exit_session=exit_session,
            entry_price=entry.open_price,
            exit_price=exit_row.close_price,
            benchmark_entry=benchmark_entry_row.open_price,
            benchmark_exit=benchmark_exit_row.close_price,
            stock_return=stock_return,
            benchmark_return=benchmark_return,
            excess_return=stock_return - benchmark_return,
        )
        records.append(label.to_record())

    ledger = {
        "schema_version": 1,
        "label_id": AE001_LABEL_ID,
        "benchmark_id": benchmark_id,
        "feature_session": feature_session,
        "evaluation_as_of_session": evaluation_as_of_session,
        "symbol": symbol.upper(),
        "isin": isin,
        "records": records,
        "outcomes_attached_to_feature_snapshot": False,
        "live_capital_allowed": False,
    }
    ledger["label_ledger_sha256"] = digest(ledger)
    return ledger
