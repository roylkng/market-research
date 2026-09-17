"""Research-only evidence-to-decision prototype. No collection, model or orders.

The caller supplies validated, timestamped source records. Structural validation
is not proof that a quoted assertion is true or that a supplied clock is honest.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import math
from typing import Mapping, Sequence
from urllib.parse import urlparse


class EvidenceError(ValueError):
    """An input violates an explicit evidence or time contract."""


def aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise EvidenceError("An explicit timezone is required")
    return value


def finite(value: float, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise EvidenceError(f"{label} cannot be a boolean")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise EvidenceError(f"Invalid {label}")
    return result


@dataclass(frozen=True)
class Evidence:
    identifier: str
    subject: str
    facet: str
    claim_key: str
    value: str
    role: str
    publisher: str
    origin: str
    source_url: str
    content_sha256: str
    published_at: datetime
    first_seen_at: datetime
    processed_at: datetime
    expires_at: datetime
    quote: str
    supersedes: str | None = None

    def __post_init__(self) -> None:
        for field in (self.identifier, self.subject, self.facet, self.claim_key,
                      self.value, self.publisher, self.origin, self.quote):
            if not isinstance(field, str) or not field.strip():
                raise EvidenceError("Evidence identity and claim fields cannot be empty")
        if self.role not in {"REPORTED_FACT", "MANAGEMENT_GUIDANCE", "EXTERNAL_ESTIMATE", "SOCIAL_LEAD"}:
            raise EvidenceError("Unsupported evidence role")
        parsed = urlparse(self.source_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise EvidenceError("Evidence requires an HTTPS source without embedded credentials")
        if len(self.content_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.content_sha256):
            raise EvidenceError("Invalid content hash")
        for value in (self.published_at, self.first_seen_at, self.processed_at, self.expires_at):
            aware(value)
        if self.processed_at < self.first_seen_at:
            raise EvidenceError("Processing precedes observation")
        if self.expires_at <= self.available_at:
            raise EvidenceError("Evidence expires before it is usable")

    @property
    def available_at(self) -> datetime:
        # An old publication discovered today cannot enter yesterday's decision.
        return max(self.published_at, self.first_seen_at, self.processed_at)


@dataclass(frozen=True)
class Coverage:
    subject: str
    facet: str
    channel: str
    window_start: datetime
    through: datetime
    completed_at: datetime
    status: str

    def __post_init__(self) -> None:
        for value in (self.window_start, self.through, self.completed_at):
            aware(value)
        if not self.subject or not self.facet or not self.channel:
            raise EvidenceError("Coverage identity is incomplete")
        if not self.window_start <= self.through <= self.completed_at:
            raise EvidenceError("Invalid source coverage window")
        if self.status not in {"COMPLETE", "FETCH_FAILED", "PARSE_FAILED", "NOT_COLLECTED"}:
            raise EvidenceError("Invalid source coverage state")


@dataclass(frozen=True)
class Requirement:
    subject: str
    facet: str
    channel: str
    max_scan_age: timedelta
    lookback: timedelta
    needs_claim: bool = True

    def __post_init__(self) -> None:
        if not self.subject or not self.facet or not self.channel:
            raise EvidenceError("Requirement identity is incomplete")
        if self.max_scan_age < timedelta(0) or self.lookback < timedelta(0):
            raise EvidenceError("Coverage durations cannot be negative")


@dataclass(frozen=True)
class Mechanism:
    subject: str
    event: str
    economic_driver: str
    channel: str
    horizon: str
    prior_expectation: str
    change_from_expectation: str
    price_response_already_observed: str
    invalidation: str
    supporting_ids: tuple[str, ...]
    contradicting_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.subject, self.event, self.economic_driver, self.channel,
                      self.horizon, self.prior_expectation, self.change_from_expectation,
                      self.price_response_already_observed, self.invalidation):
            if not isinstance(value, str) or not value.strip():
                raise EvidenceError("Mechanism requires economics, expectations and invalidation")
        if not self.supporting_ids or len(set(self.supporting_ids)) != len(self.supporting_ids):
            raise EvidenceError("Mechanism needs unique supporting references")
        if set(self.supporting_ids) & set(self.contradicting_ids):
            raise EvidenceError("An item cannot both support and contradict the same mechanism")


def active_evidence(records: Sequence[Evidence], as_of: datetime) -> list[Evidence]:
    aware(as_of)
    by_id = {row.identifier: row for row in records}
    if len(by_id) != len(records):
        raise EvidenceError("Duplicate evidence identity")
    # Validate even future rows, but never let them suppress an older decision.
    for row in records:
        if row.supersedes:
            prior = by_id.get(row.supersedes)
            if prior is None:
                raise EvidenceError("Superseded evidence is missing")
            if (row.subject, row.facet, row.claim_key, row.role) != (
                    prior.subject, prior.facet, prior.claim_key, prior.role):
                raise EvidenceError("A revision cannot change claim identity")
            if row.origin != prior.origin:
                raise EvidenceError("Another origin cannot silently supersede this claim")
            if row.available_at <= prior.available_at:
                raise EvidenceError("Revision must become available strictly later")
    known = [row for row in records if row.available_at <= as_of]
    replaced = {row.supersedes for row in known if row.supersedes}
    return sorted((row for row in known if row.identifier not in replaced and as_of < row.expires_at),
                  key=lambda row: row.identifier)


def company_packet(*, subject: str, horizon: str, as_of: datetime,
                   evidence: Sequence[Evidence], coverage: Sequence[Coverage],
                   requirements: Sequence[Requirement], mechanisms: Sequence[Mechanism]) -> dict:
    """Join a company's evidence and explicit market dependencies at one cutoff.

    RESEARCH_READY means input-ready for a research review, not investable,
    independently corroborated or statistically validated. No numeric forecast
    or probability can be generated by this prototype.
    """
    if not subject or not horizon or not requirements:
        raise EvidenceError("Subject, horizon and explicit input requirements are required")
    active = active_evidence(evidence, as_of)
    allowed_pairs = {(req.subject, req.facet) for req in requirements}
    required_keys = [(req.subject, req.facet, req.channel) for req in requirements]
    if len(set(required_keys)) != len(required_keys):
        raise EvidenceError("Duplicate source requirement")
    if not any(req.subject == subject for req in requirements):
        raise EvidenceError("Company-specific evidence requirements are mandatory")
    scoped = [row for row in active if (row.subject, row.facet) in allowed_pairs]
    by_id = {row.identifier: row for row in scoped}
    blockers: list[str] = []
    covered: list[dict] = []
    for req in requirements:
        key = f"{req.subject}/{req.facet}/{req.channel}"
        scans = [row for row in coverage if (row.subject, row.facet, row.channel) ==
                 (req.subject, req.facet, req.channel) and row.completed_at <= as_of]
        if not scans:
            blockers.append(f"NOT_COLLECTED:{key}")
            continue
        latest_time = max(row.completed_at for row in scans)
        latest = [row for row in scans if row.completed_at == latest_time]
        if len(set(latest)) != 1:
            blockers.append(f"AMBIGUOUS_COVERAGE:{key}")
            continue
        scan = latest[0]
        if scan.status != "COMPLETE":
            blockers.append(f"{scan.status}:{key}")
            continue
        if as_of - scan.through > req.max_scan_age:
            blockers.append(f"STALE_COVERAGE:{key}")
            continue
        if scan.window_start > as_of - req.lookback:
            blockers.append(f"INCOMPLETE_WINDOW:{key}")
            continue
        claims = [row for row in scoped if (row.subject, row.facet) == (req.subject, req.facet)]
        usable_claims = [row for row in claims if row.role != "SOCIAL_LEAD"]
        if req.needs_claim and not usable_claims:
            blockers.append(f"MISSING_SUBSTANTIVE_EVIDENCE:{key}")
        covered.append({"key": key, "through": scan.through.isoformat(),
                        "state": "COVERED" if claims else "NO_EVENT_IN_SCANNED_WINDOW"})
    groups: dict[tuple[str, str, str, str], list[Evidence]] = {}
    for row in scoped:
        if row.role == "REPORTED_FACT":
            groups.setdefault((row.subject, row.facet, row.claim_key, row.role), []).append(row)
    conflicts = []
    for key, rows in groups.items():
        if len({row.value for row in rows}) > 1:
            conflicts.append({"claim": list(key), "evidence_ids": sorted(row.identifier for row in rows)})
            blockers.append("UNRESOLVED_CONFLICT:" + "/".join(key))
    mechanism_rows = []
    for mechanism in mechanisms:
        if (mechanism.subject, mechanism.horizon) != (subject, horizon):
            continue
        refs = mechanism.supporting_ids + mechanism.contradicting_ids
        if any(identifier not in by_id for identifier in refs):
            blockers.append(f"UNAVAILABLE_MECHANISM_EVIDENCE:{mechanism.event}")
            continue
        supports = [by_id[identifier] for identifier in mechanism.supporting_ids]
        roots = sorted({row.origin for row in supports})
        # A repeated press release, even across websites, remains one origin.
        status = "RESEARCH_HYPOTHESIS"
        if all(row.role == "SOCIAL_LEAD" for row in supports):
            status = "UNVERIFIED_LEAD"
        mechanism_rows.append({"event": mechanism.event, "driver": mechanism.economic_driver,
                               "channel": mechanism.channel, "horizon": horizon,
                               "prior_expectation": mechanism.prior_expectation,
                               "change_from_expectation": mechanism.change_from_expectation,
                               "already_observed_price_response": mechanism.price_response_already_observed,
                               "invalidation": mechanism.invalidation,
                               "supporting_ids": list(mechanism.supporting_ids),
                               "contradicting_ids": list(mechanism.contradicting_ids),
                               "distinct_origins": roots, "origin_count": len(roots), "status": status})
    if not any(row["status"] == "RESEARCH_HYPOTHESIS" for row in mechanism_rows):
        blockers.append("NO_SUPPORTED_ECONOMIC_MECHANISM")
    return {"subject": subject, "horizon": horizon, "as_of": as_of.isoformat(),
            "state": "RESEARCH_BLOCKED" if blockers else "RESEARCH_READY",
            "blockers": sorted(set(blockers)), "coverage": covered,
            "active_evidence_ids": sorted(by_id), "conflicts": conflicts,
            "mechanisms": mechanism_rows, "forecast": None,
            "forecast_status": "NO_VALIDATED_FORECAST_MODEL", "live_capital_allowed": False}


@dataclass(frozen=True)
class Session:
    day: date
    closes_at: datetime

    def __post_init__(self) -> None:
        aware(self.closes_at)
        if not isinstance(self.day, date):
            raise EvidenceError("Invalid session date")


@dataclass(frozen=True)
class Bar:
    value: float
    available_at: datetime
    basis: str

    def __post_init__(self) -> None:
        finite(self.value, "bar", positive=True)
        aware(self.available_at)
        if not self.basis:
            raise EvidenceError("Price adjustment basis is required")


def common_window_returns(*, calendar: Sequence[Session], cutoff: date, horizon: int,
                          as_of: datetime, benchmark: Mapping[date, Bar],
                          stocks: Mapping[str, Mapping[date, Bar]]) -> dict:
    """Use one reviewed calendar, never each stock's intersection with an index."""
    aware(as_of)
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1:
        raise EvidenceError("A positive integer return horizon is required")
    days = [session.day for session in calendar]
    if days != sorted(set(days)) or cutoff not in days:
        raise EvidenceError("Calendar must be unique, sorted and contain the cutoff")
    index = days.index(cutoff)
    if index < horizon:
        raise EvidenceError("Insufficient reviewed calendar")
    window = list(calendar[index - horizon:index + 1])
    if any(session.closes_at > as_of for session in window):
        raise EvidenceError("Window contains an uncompleted session")

    def calculate(bars: Mapping[date, Bar]) -> tuple[float | None, str | None, str | None]:
        if any(session.day not in bars for session in window):
            return None, None, "MISSING_CALENDAR_BAR"
        selected = [bars[session.day] for session in window]
        if any(bar.available_at > as_of for bar in selected):
            return None, None, "BAR_NOT_YET_AVAILABLE"
        if any(bar.available_at < session.closes_at for bar, session in zip(selected, window)):
            return None, None, "BAR_CAPTURED_BEFORE_SESSION_CLOSE"
        bases = {bar.basis for bar in selected}
        if len(bases) != 1:
            return None, None, "MIXED_ADJUSTMENT_BASIS"
        result = 100 * (selected[-1].value / selected[0].value - 1)
        return result, selected[0].basis, None

    bench_return, bench_basis, bench_error = calculate(benchmark)
    if bench_error:
        raise EvidenceError(f"Benchmark is unusable: {bench_error}")
    rows = {}
    for symbol, bars in sorted(stocks.items()):
        result, basis, error = calculate(bars)
        if not error and basis != bench_basis:
            error = "BENCHMARK_BASIS_MISMATCH"
        rows[symbol] = {"status": error or "OBSERVED", "return_pct": result if not error else None,
                        "excess_pp": result - bench_return if not error else None}
    return {"window_start": window[0].day.isoformat(), "window_end": cutoff.isoformat(),
            "horizon_sessions": horizon, "benchmark_return_pct": bench_return,
            "return_basis": bench_basis, "stocks": rows}


def per_share_scenario(*, current_price: float, current_profit: float, future_profit: float,
                       current_shares: float, future_shares: float, future_pe: float,
                       dividends_per_share: float = 0, cost_pp: float = 0.5) -> dict:
    """Conditional P/E arithmetic for positive-profit companies, not a forecast.

    All currency amounts must use the same currency and scale, and share counts
    must use compatible units. Banks, cyclicals and loss-makers need suitable
    alternative models. Profit is attributable net profit, shares fully diluted.
    """
    price = finite(current_price, "current_price", positive=True)
    profit = finite(current_profit, "current_profit", positive=True)
    future = finite(future_profit, "future_profit", positive=True)
    shares = finite(current_shares, "current_shares", positive=True)
    diluted = finite(future_shares, "future_shares", positive=True)
    multiple = finite(future_pe, "future_pe", positive=True)
    dividend = finite(dividends_per_share, "dividends_per_share")
    cost = finite(cost_pp, "cost_pp")
    if dividend < 0 or cost < 0:
        raise EvidenceError("Dividends and costs cannot be negative")
    old_eps, new_eps = profit / shares, future / diluted
    value = new_eps * multiple
    return {"kind": "CONDITIONAL_SCENARIO_NOT_CALIBRATED_FORECAST", "implied_current_pe": price / old_eps,
            "profit_growth_pct": 100 * (future / profit - 1),
            "diluted_eps_growth_pct": 100 * (new_eps / old_eps - 1),
            "terminal_price": value, "price_return_pct": 100 * (value / price - 1),
            "cost_adjusted_total_return_pct": 100 * ((value + dividend) / price - 1) - cost,
            "probability": None, "live_capital_allowed": False}
