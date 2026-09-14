from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date

from marketlab.h021_stockanalysis_parser import (
    ForecastEpsError,
    ForecastIdentityError,
    ForecastLayoutError,
    ForecastProviderError,
    ForecastTargetPeriodError,
    ParsedAnnualForecast,
)

CAPTURE = "CAPTURE"
NO_SESSION = "NO_SESSION"
NOT_FINAL_SESSION = "NOT_FINAL_SESSION"


@dataclass(frozen=True)
class WeeklySessionDecision:
    state: str
    capture_date_ist: str
    final_session_date: str | None
    reason: str


@dataclass(frozen=True)
class AnchorTarget:
    symbol: str
    fiscal_period: str
    period_ending: str
    eps_currency: str


class StructuralSourceDrift(RuntimeError):
    """Provider structure changed in a way that requires explicit source review."""


def _canonical_date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be ISO YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must be canonical ISO YYYY-MM-DD")
    return parsed


def weekly_session_decision(capture_date_ist: str, calendar: dict) -> WeeklySessionDecision:
    requested = _canonical_date(capture_date_ist, "capture_date_ist")
    start = _canonical_date(calendar.get("start_date"), "calendar.start_date")
    end = _canonical_date(calendar.get("end_date"), "calendar.end_date")
    if requested < start or requested > end:
        raise ValueError(
            f"capture date {capture_date_ist} is outside frozen calendar coverage "
            f"{start.isoformat()}..{end.isoformat()}"
        )

    raw_sessions = calendar.get("sessions")
    if not isinstance(raw_sessions, list) or not raw_sessions:
        raise ValueError("calendar sessions must be a non-empty list")
    sessions: list[date] = []
    for index, row in enumerate(raw_sessions):
        if not isinstance(row, dict):
            raise ValueError(f"calendar session[{index}] must be an object")
        sessions.append(_canonical_date(row.get("session_date"), "session_date"))
    if len(sessions) != len(set(sessions)):
        raise ValueError("calendar contains duplicate session dates")

    same_week = sorted(
        session
        for session in sessions
        if session.isocalendar()[:2] == requested.isocalendar()[:2]
    )
    final_session = same_week[-1] if same_week else None
    if requested not in sessions:
        return WeeklySessionDecision(
            state=NO_SESSION,
            capture_date_ist=capture_date_ist,
            final_session_date=final_session.isoformat() if final_session else None,
            reason="requested India date is not a frozen NSE cash-market session",
        )
    if final_session != requested:
        return WeeklySessionDecision(
            state=NOT_FINAL_SESSION,
            capture_date_ist=capture_date_ist,
            final_session_date=final_session.isoformat() if final_session else None,
            reason="a later frozen NSE session exists in the same Monday-Sunday week",
        )
    return WeeklySessionDecision(
        state=CAPTURE,
        capture_date_ist=capture_date_ist,
        final_session_date=capture_date_ist,
        reason="requested India date is the final frozen NSE session of its week",
    )


def anchor_targets(anchor: dict) -> dict[str, AnchorTarget]:
    observations = anchor.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("anchor observations must be a non-empty list")

    targets: dict[str, AnchorTarget] = {}
    for index, row in enumerate(observations):
        if not isinstance(row, dict):
            raise ValueError(f"anchor observation[{index}] must be an object")
        symbol = row.get("symbol")
        fiscal_period = row.get("fiscal_period")
        period_ending = row.get("period_ending")
        eps_currency = row.get("eps_currency")
        if not isinstance(symbol, str) or not symbol:
            raise ValueError(f"anchor observation[{index}] invalid symbol")
        if symbol in targets:
            raise ValueError(f"anchor contains duplicate symbol: {symbol}")
        if not isinstance(fiscal_period, str) or not fiscal_period:
            raise ValueError(f"anchor target {symbol} lacks fiscal_period")
        _canonical_date(period_ending, f"anchor target {symbol} period_ending")
        if (
            not isinstance(eps_currency, str)
            or len(eps_currency) != 3
            or eps_currency.upper() != eps_currency
        ):
            raise ValueError(f"anchor target {symbol} lacks canonical eps_currency")
        targets[symbol] = AnchorTarget(
            symbol=symbol,
            fiscal_period=fiscal_period,
            period_ending=period_ending,
            eps_currency=eps_currency,
        )
    return targets


def _clear_forecast_values(row: dict) -> None:
    for field in (
        "period_ending",
        "consensus_eps",
        "eps_currency",
        "revenue_growth_forecast_pct",
        "profit_growth_estimate_pct",
        "analyst_count",
        "target_price_inr",
        "source_observed_market_date",
    ):
        row[field] = None


def success_row(
    draft_row: dict,
    *,
    target: AnchorTarget,
    parsed: ParsedAnnualForecast,
    source_url: str,
) -> dict:
    if parsed.symbol != target.symbol:
        raise ValueError("parsed symbol does not match frozen target")
    if parsed.fiscal_period != target.fiscal_period:
        raise ValueError("parsed fiscal period does not match frozen target")
    if parsed.period_ending != target.period_ending:
        raise ValueError("parsed period ending does not match frozen target")
    if parsed.eps_currency != target.eps_currency:
        raise StructuralSourceDrift(
            f"EPS currency changed for {target.symbol}: "
            f"{target.eps_currency} -> {parsed.eps_currency}"
        )

    row = copy.deepcopy(draft_row)
    row.update(
        {
            "data_state": "PARTIAL",
            "retrieval_notes": (
                "Exact frozen annual EPS period acquired from public StockAnalysis/S&P "
                "Global forecast page. Optional Trendlyne secondary diagnostics were not "
                "acquired by the unattended primary path and remain null."
            ),
            "fiscal_period": parsed.fiscal_period,
            "period_ending": parsed.period_ending,
            "consensus_eps": parsed.consensus_eps,
            "eps_currency": parsed.eps_currency,
            "revenue_growth_forecast_pct": parsed.revenue_growth_forecast_pct,
            "profit_growth_estimate_pct": None,
            "analyst_count": parsed.analyst_count,
            "target_price_inr": None,
            "source_observed_market_date": None,
            "source_url": source_url,
            "source_status": "PUBLIC_STOCKANALYSIS_SP_GLOBAL_PRIMARY",
        }
    )
    return row


def no_coverage_row(
    draft_row: dict,
    *,
    target: AnchorTarget,
    source_url: str,
    reason: str,
) -> dict:
    row = copy.deepcopy(draft_row)
    _clear_forecast_values(row)
    row.update(
        {
            "data_state": "NO_COVERAGE",
            "retrieval_notes": reason,
            "fiscal_period": target.fiscal_period,
            "source_url": source_url,
            "source_status": "PUBLIC_STOCKANALYSIS_NO_COVERAGE",
        }
    )
    return row


def source_blocked_row(
    draft_row: dict,
    *,
    target: AnchorTarget,
    source_url: str,
    reason: str,
) -> dict:
    row = copy.deepcopy(draft_row)
    _clear_forecast_values(row)
    row.update(
        {
            "data_state": "SOURCE_BLOCKED",
            "retrieval_notes": reason,
            "fiscal_period": target.fiscal_period,
            "source_url": source_url,
            "source_status": "PUBLIC_STOCKANALYSIS_SOURCE_BLOCKED",
        }
    )
    return row


def identity_unresolved_row(
    draft_row: dict,
    *,
    target: AnchorTarget,
    source_url: str,
    reason: str,
) -> dict:
    row = copy.deepcopy(draft_row)
    _clear_forecast_values(row)
    row.update(
        {
            "data_state": "IDENTITY_UNRESOLVED",
            "retrieval_notes": reason,
            "fiscal_period": target.fiscal_period,
            "source_url": source_url,
            "source_status": "PUBLIC_STOCKANALYSIS_IDENTITY_UNRESOLVED",
        }
    )
    return row


def missing_eps_row(
    draft_row: dict,
    *,
    target: AnchorTarget,
    source_url: str,
    reason: str,
) -> dict:
    row = copy.deepcopy(draft_row)
    _clear_forecast_values(row)
    row.update(
        {
            "data_state": "PARTIAL",
            "retrieval_notes": reason,
            "fiscal_period": target.fiscal_period,
            "period_ending": target.period_ending,
            "source_url": source_url,
            "source_status": "PUBLIC_STOCKANALYSIS_TARGET_EPS_UNAVAILABLE",
        }
    )
    return row


def row_from_parser_error(
    draft_row: dict,
    *,
    target: AnchorTarget,
    source_url: str,
    error: Exception,
) -> dict:
    reason = f"{type(error).__name__}: {error}"
    if isinstance(error, ForecastIdentityError):
        return identity_unresolved_row(
            draft_row,
            target=target,
            source_url=source_url,
            reason=reason,
        )
    if isinstance(error, ForecastTargetPeriodError):
        return no_coverage_row(
            draft_row,
            target=target,
            source_url=source_url,
            reason=reason,
        )
    if isinstance(error, ForecastEpsError):
        return missing_eps_row(
            draft_row,
            target=target,
            source_url=source_url,
            reason=reason,
        )
    if isinstance(error, (ForecastProviderError, ForecastLayoutError)):
        raise StructuralSourceDrift(reason) from error
    raise StructuralSourceDrift(reason) from error


def finalize_capture(draft: dict, observations: list[dict], captured_at_utc: str) -> dict:
    snapshot = copy.deepcopy(draft)
    snapshot.pop("draft_schema_version", None)
    snapshot.pop("draft_state", None)
    snapshot["captured_at_utc"] = captured_at_utc
    snapshot["observations"] = observations
    return snapshot
