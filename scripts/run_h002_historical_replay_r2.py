from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from marketlab.calendar_snapshot import build_calendar_snapshot
from marketlab.events import HISTORICAL_RECONSTRUCTION, parse_indas_document, sha256_bytes
from marketlab.execution import TradingCalendar
from marketlab.h002 import (
    H002SignalError,
    PriceReference,
    build_seasonal_expectation,
    build_terminal_no_signal_expectation,
)
from marketlab.h002_historical import (
    historical_freeze_at,
    load_and_validate_historical_replay_rule,
    score_h002_historical_replay,
    select_historical_filing_pair,
)
from marketlab.h002_historical_identity import (
    is_non_comparable_predecessor,
    normalize_symbol_for_h002,
    symbols_equivalent,
)
from marketlab.marketdata import (
    MarketDataMissingRow,
    audit_price_basis_actions,
    parse_udiff_equity,
    udiff_url,
)
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.preparation import analyze_eps_basis_actions
from marketlab.universe import UniverseMember, load_universe_snapshot

IST = ZoneInfo("Asia/Kolkata")
COMPILER_REVISION = "H002-HR001-phase-a-r2-identity-integrity"


class PhaseAError(RuntimeError):
    pass


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _retain(root: Path, raw: bytes, *, kind: str, suffix: str) -> dict[str, Any]:
    digest = sha256_bytes(raw)
    path = root / "raw" / kind / "sha256" / f"{digest}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise PhaseAError("content-addressed replay-store collision")
    else:
        path.write_bytes(raw)
    return {
        "raw_sha256": digest,
        "raw_path": str(path),
        "byte_count": len(raw),
    }


def _document_event(
    raw: bytes,
    *,
    source_url: str,
    exchange_published_at_utc: str,
    discovery: dict[str, Any],
    captured_at: datetime,
    store_root: Path,
) -> Any:
    source = _retain(store_root, raw, kind="filings", suffix=".source")
    return parse_indas_document(
        raw.decode("utf-8", errors="strict"),
        source_url=source_url,
        raw_sha256=source["raw_sha256"],
        raw_path=source["raw_path"],
        captured_at_utc=_iso(captured_at),
        mode=HISTORICAL_RECONSTRUCTION,
        exchange_published_at_utc=exchange_published_at_utc,
        discovery_sha256=discovery["raw_sha256"],
        discovery_path=discovery["raw_path"],
    )


def _period_iso(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text
    for fmt in ("%d-%m-%Y", "%d-%b-%Y"):
        try:
            parsed = time.strptime(text, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday).isoformat()
        except ValueError:
            continue
    return None


def _assert_event_period_basis(
    event: Any,
    *,
    expected_period_end: str,
    expected_basis: str,
    role: str,
) -> None:
    observed_period = _period_iso(event.reporting_period_end)
    if observed_period != expected_period_end:
        raise PhaseAError(
            f"{role} period mismatch: expected={expected_period_end}, observed={observed_period}"
        )
    if event.accounting_basis.strip().casefold() != expected_basis.strip().casefold():
        raise PhaseAError(
            f"{role} accounting-basis mismatch: "
            f"expected={expected_basis}, observed={event.accounting_basis}"
        )


def _same_quarter_label(left: str | None, right: str | None) -> bool:
    return (left or "").strip().casefold() == (right or "").strip().casefold()


def _is_archive_404(exc: BaseException) -> bool:
    message = str(exc).casefold()
    return "404" in message and ("not found" in message or "client error" in message)


class SourceCache:
    def __init__(self, client: NSEClient, store_root: Path) -> None:
        self.client = client
        self.store_root = store_root
        self.archive: dict[str, bytes] = {}
        self.udiff: dict[str, tuple[bytes, dict[str, Any]]] = {}

    def archive_bytes(self, url: str) -> bytes:
        raw = self.archive.get(url)
        if raw is None:
            raw = self.client.archive_bytes(url)
            self.archive[url] = raw
        return raw

    def udiff_bytes(self, day: date) -> tuple[bytes, dict[str, Any]]:
        key = day.isoformat()
        cached = self.udiff.get(key)
        if cached is not None:
            return cached
        url = udiff_url(day)
        raw = self.archive_bytes(url)
        evidence = _retain(self.store_root, raw, kind="udiff", suffix=".zip")
        evidence["source_url"] = url
        self.udiff[key] = (raw, evidence)
        return raw, evidence


def _corporate_actions(
    client: NSEClient,
    store_root: Path,
    *,
    symbol: str,
    from_date: date,
    to_date: date,
) -> tuple[Any, bytes, dict[str, Any]]:
    payload, raw = client.corporate_actions_with_raw(
        symbol,
        from_date=from_date.strftime("%d-%m-%Y"),
        to_date=to_date.strftime("%d-%m-%Y"),
    )
    evidence = _retain(store_root, raw, kind="corporate-actions", suffix=".json")
    query = urlencode(
        {
            "index": "equities",
            "symbol": symbol,
            "from_date": from_date.strftime("%d-%m-%Y"),
            "to_date": to_date.strftime("%d-%m-%Y"),
        }
    )
    evidence["source_url"] = f"{client.CORPORATE_ACTION_ENDPOINT.url}?{query}"
    return payload, raw, evidence


def _normalization_evidence(
    *,
    member: UniverseMember,
    target_event: Any | None,
    baseline_event: Any | None,
) -> dict[str, Any]:
    return {
        "compiler_revision": COMPILER_REVISION,
        "canonical_symbol": member.symbol,
        "target_symbol_raw": None if target_event is None else target_event.symbol,
        "baseline_symbol_raw": None if baseline_event is None else baseline_event.symbol,
        "target_isin_raw": None if target_event is None else target_event.isin,
        "baseline_isin_raw": None if baseline_event is None else baseline_event.isin,
        "target_quarter_raw": None if target_event is None else target_event.reporting_quarter,
        "baseline_quarter_raw": None if baseline_event is None else baseline_event.reporting_quarter,
        "symbol_alias_applied": (
            False
            if target_event is None
            else member.symbol.strip().upper() != target_event.symbol.strip().upper()
        )
        or (
            False
            if baseline_event is None
            else member.symbol.strip().upper() != baseline_event.symbol.strip().upper()
        ),
        "quarter_text_normalized": False,
        "current_cohort_isin_used_for_historical_identity": False,
    }


def _record(
    *,
    member: UniverseMember,
    quarter: dict[str, Any],
    status: str,
    reason: str | None,
    freeze_at_utc: str,
    pair: Any | None = None,
    target_event: Any | None = None,
    baseline_event: Any | None = None,
    expectation: Any | None = None,
    reference: PriceReference | None = None,
    signal: Any | None = None,
    discovery_evidence: dict[str, Any] | None = None,
    target_evidence: dict[str, Any] | None = None,
    baseline_evidence: dict[str, Any] | None = None,
    corporate_action_evidence: dict[str, Any] | None = None,
    frozen_action_analysis: Any | None = None,
    publication_action_analysis: Any | None = None,
    pre_event_price_basis: Any | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "compiler_revision": COMPILER_REVISION,
        "symbol": member.symbol,
        "isin": member.isin,
        "company_name": member.company_name,
        "universe_rank": member.rank,
        "quarter_id": quarter["id"],
        "target_period_end": quarter["period_end"],
        "baseline_period_end": quarter["baseline_period_end"],
        "historical_freeze_at_utc": freeze_at_utc,
        "status": status,
        "reason": reason,
        "accounting_basis": None if pair is None else pair.accounting_basis,
        "target_candidate": None if pair is None else asdict(pair.target),
        "baseline_candidate": None if pair is None else asdict(pair.baseline),
        "target_event": None if target_event is None else target_event.to_dict(),
        "baseline_event": None if baseline_event is None else baseline_event.to_dict(),
        "expectation": None if expectation is None else expectation.to_dict(),
        "price_reference": None if reference is None else reference.to_dict(),
        "signal": None if signal is None else signal.to_dict(),
        "normalization": _normalization_evidence(
            member=member,
            target_event=target_event,
            baseline_event=baseline_event,
        ),
        "evidence": {
            "discovery": discovery_evidence,
            "target_source": target_evidence,
            "baseline_source": baseline_evidence,
            "corporate_actions": corporate_action_evidence,
            "frozen_eps_basis": None if frozen_action_analysis is None else asdict(frozen_action_analysis),
            "publication_eps_basis": None if publication_action_analysis is None else asdict(publication_action_analysis),
            "pre_event_price_basis": None if pre_event_price_basis is None else asdict(pre_event_price_basis),
        },
    }


def _select_pairs(
    discovery_payload: Any,
    *,
    member: UniverseMember,
    quarters: list[dict[str, Any]],
    offset_days: int,
    records: list[dict[str, Any]],
    discovery_evidence: dict[str, Any],
) -> dict[str, Any]:
    pairs: dict[str, Any] = {}
    for quarter in quarters:
        freeze_at_utc = historical_freeze_at(quarter["period_end"], offset_days=offset_days)
        pair = select_historical_filing_pair(
            discovery_payload,
            symbol=member.symbol,
            target_period_end=quarter["period_end"],
            baseline_period_end=quarter["baseline_period_end"],
            freeze_at_utc=freeze_at_utc,
        )
        if pair is None:
            records.append(
                _record(
                    member=member,
                    quarter=quarter,
                    status="UNCOVERED",
                    reason="no_matching_target_baseline_pair_as_of_freeze",
                    freeze_at_utc=freeze_at_utc,
                    discovery_evidence=discovery_evidence,
                )
            )
        else:
            pairs[quarter["id"]] = pair
    return pairs


def _action_window(
    pairs: dict[str, Any],
    quarters_by_id: dict[str, dict[str, Any]],
) -> tuple[date, date]:
    starts = [
        date.fromisoformat(quarters_by_id[quarter_id]["baseline_period_end"])
        for quarter_id in pairs
    ]
    ends = [
        datetime.fromisoformat(pair.target.exchange_published_at_utc).astimezone(IST).date()
        for pair in pairs.values()
    ]
    return min(starts), max(ends)


def _uncovered_archive_record(
    *,
    member: UniverseMember,
    quarter: dict[str, Any],
    freeze_at_utc: str,
    pair: Any,
    discovery_evidence: dict[str, Any],
    role: str,
    url: str,
) -> dict[str, Any]:
    return _record(
        member=member,
        quarter=quarter,
        status="UNCOVERED",
        reason=f"{role}_archive_source_unavailable_404:{url}",
        freeze_at_utc=freeze_at_utc,
        pair=pair,
        discovery_evidence=discovery_evidence,
    )


def _process_pair(
    *,
    cache: SourceCache,
    store_root: Path,
    started_at: datetime,
    calendar: TradingCalendar,
    member: UniverseMember,
    quarter: dict[str, Any],
    pair: Any,
    discovery_evidence: dict[str, Any],
    action_payload: Any,
    action_raw: bytes,
    action_evidence: dict[str, Any],
    offset_days: int,
) -> dict[str, Any]:
    symbol = member.symbol.strip().upper()
    freeze_at_utc = historical_freeze_at(quarter["period_end"], offset_days=offset_days)

    try:
        target_raw = cache.archive_bytes(pair.target.source_url)
    except NSEAcquisitionError as exc:
        if _is_archive_404(exc):
            return _uncovered_archive_record(
                member=member,
                quarter=quarter,
                freeze_at_utc=freeze_at_utc,
                pair=pair,
                discovery_evidence=discovery_evidence,
                role="target",
                url=pair.target.source_url,
            )
        raise
    try:
        baseline_raw = cache.archive_bytes(pair.baseline.source_url)
    except NSEAcquisitionError as exc:
        if _is_archive_404(exc):
            return _uncovered_archive_record(
                member=member,
                quarter=quarter,
                freeze_at_utc=freeze_at_utc,
                pair=pair,
                discovery_evidence=discovery_evidence,
                role="baseline",
                url=pair.baseline.source_url,
            )
        raise

    target_evidence = _retain(store_root, target_raw, kind="filings", suffix=".source")
    target_evidence["source_url"] = pair.target.source_url
    baseline_evidence = _retain(store_root, baseline_raw, kind="filings", suffix=".source")
    baseline_evidence["source_url"] = pair.baseline.source_url

    target_event = _document_event(
        target_raw,
        source_url=pair.target.source_url,
        exchange_published_at_utc=pair.target.exchange_published_at_utc,
        discovery=discovery_evidence,
        captured_at=started_at,
        store_root=store_root,
    )
    baseline_event = _document_event(
        baseline_raw,
        source_url=pair.baseline.source_url,
        exchange_published_at_utc=pair.baseline.exchange_published_at_utc,
        discovery=discovery_evidence,
        captured_at=started_at,
        store_root=store_root,
    )

    _assert_event_period_basis(
        target_event,
        expected_period_end=quarter["period_end"],
        expected_basis=pair.accounting_basis,
        role="target",
    )
    _assert_event_period_basis(
        baseline_event,
        expected_period_end=quarter["baseline_period_end"],
        expected_basis=pair.accounting_basis,
        role="baseline",
    )

    if not symbols_equivalent(symbol, target_event.symbol):
        raise PhaseAError(
            f"target symbol mismatch: expected={symbol}, observed={target_event.symbol}"
        )
    if is_non_comparable_predecessor(symbol, baseline_event.symbol):
        return _record(
            member=member,
            quarter=quarter,
            status="SKIPPED",
            reason="non_comparable_predecessor_after_corporate_restructure",
            freeze_at_utc=freeze_at_utc,
            pair=pair,
            target_event=target_event,
            baseline_event=baseline_event,
            discovery_evidence=discovery_evidence,
            target_evidence=target_evidence,
            baseline_evidence=baseline_evidence,
            corporate_action_evidence=action_evidence,
        )
    if not symbols_equivalent(symbol, baseline_event.symbol):
        return _record(
            member=member,
            quarter=quarter,
            status="SKIPPED",
            reason="unregistered_historical_symbol_identity_mismatch",
            freeze_at_utc=freeze_at_utc,
            pair=pair,
            target_event=target_event,
            baseline_event=baseline_event,
            discovery_evidence=discovery_evidence,
            target_evidence=target_evidence,
            baseline_evidence=baseline_evidence,
            corporate_action_evidence=action_evidence,
        )
    if not _same_quarter_label(target_event.reporting_quarter, baseline_event.reporting_quarter):
        return _record(
            member=member,
            quarter=quarter,
            status="SKIPPED",
            reason="baseline_reporting_quarter_not_verifiably_same",
            freeze_at_utc=freeze_at_utc,
            pair=pair,
            target_event=target_event,
            baseline_event=baseline_event,
            discovery_evidence=discovery_evidence,
            target_evidence=target_evidence,
            baseline_evidence=baseline_evidence,
            corporate_action_evidence=action_evidence,
        )

    freeze = datetime.fromisoformat(freeze_at_utc).astimezone(IST)
    publication = datetime.fromisoformat(pair.target.exchange_published_at_utc).astimezone(IST)

    frozen_actions = analyze_eps_basis_actions(
        action_payload,
        raw_payload=action_raw,
        symbol=symbol,
        baseline_period_end=quarter["baseline_period_end"],
        as_of_utc=freeze_at_utc,
    )
    publication_actions = analyze_eps_basis_actions(
        action_payload,
        raw_payload=action_raw,
        symbol=symbol,
        baseline_period_end=quarter["baseline_period_end"],
        as_of_utc=pair.target.exchange_published_at_utc,
    )

    normalized_baseline = normalize_symbol_for_h002(
        baseline_event,
        canonical_symbol=symbol,
    )
    normalized_target = normalize_symbol_for_h002(
        target_event,
        canonical_symbol=symbol,
    )

    if (
        baseline_event.isin
        and target_event.isin
        and baseline_event.isin != target_event.isin
        and not publication_actions.relevant_actions
    ):
        return _record(
            member=member,
            quarter=quarter,
            status="SKIPPED",
            reason="historical_isin_change_without_reconciling_share_basis_action",
            freeze_at_utc=freeze_at_utc,
            pair=pair,
            target_event=target_event,
            baseline_event=baseline_event,
            discovery_evidence=discovery_evidence,
            target_evidence=target_evidence,
            baseline_evidence=baseline_evidence,
            corporate_action_evidence=action_evidence,
            frozen_action_analysis=frozen_actions,
            publication_action_analysis=publication_actions,
        )

    if frozen_actions.status != "READY" or frozen_actions.version is None:
        expectation = build_terminal_no_signal_expectation(
            normalized_baseline,
            canonical_symbol=symbol,
            target_period_end=quarter["period_end"],
            target_quarter=normalized_target.reporting_quarter or "",
            target_accounting_basis=pair.accounting_basis,
            baseline_available_at_utc=None,
            expectation_as_of_utc=freeze_at_utc,
            no_signal_reason="unresolved_corporate_action",
            corporate_action_version=(
                "EPSCA-UNRESOLVED-" + frozen_actions.payload_sha256[:16]
            ),
        )
        return _record(
            member=member,
            quarter=quarter,
            status="NO_SIGNAL",
            reason="unresolved_corporate_action_at_freeze",
            freeze_at_utc=freeze_at_utc,
            pair=pair,
            target_event=target_event,
            baseline_event=baseline_event,
            expectation=expectation,
            discovery_evidence=discovery_evidence,
            target_evidence=target_evidence,
            baseline_evidence=baseline_evidence,
            corporate_action_evidence=action_evidence,
            frozen_action_analysis=frozen_actions,
            publication_action_analysis=publication_actions,
        )

    if (
        publication_actions.status != "READY"
        or publication_actions.version is None
        or publication_actions.relevant_actions != frozen_actions.relevant_actions
        or publication_actions.unresolved_subjects
    ):
        return _record(
            member=member,
            quarter=quarter,
            status="SKIPPED",
            reason="post_freeze_eps_basis_action",
            freeze_at_utc=freeze_at_utc,
            pair=pair,
            target_event=target_event,
            baseline_event=baseline_event,
            discovery_evidence=discovery_evidence,
            target_evidence=target_evidence,
            baseline_evidence=baseline_evidence,
            corporate_action_evidence=action_evidence,
            frozen_action_analysis=frozen_actions,
            publication_action_analysis=publication_actions,
        )

    try:
        expectation = build_seasonal_expectation(
            normalized_baseline,
            target_period_end=quarter["period_end"],
            target_quarter=normalized_target.reporting_quarter or "",
            target_accounting_basis=pair.accounting_basis,
            baseline_available_at_utc=None,
            expectation_as_of_utc=freeze_at_utc,
            corporate_action_factor=frozen_actions.factor or 1.0,
            corporate_action_version=frozen_actions.version,
        )
    except H002SignalError as exc:
        return _record(
            member=member,
            quarter=quarter,
            status="SKIPPED",
            reason=f"frozen_h002_baseline_ineligible:{exc}",
            freeze_at_utc=freeze_at_utc,
            pair=pair,
            target_event=target_event,
            baseline_event=baseline_event,
            discovery_evidence=discovery_evidence,
            target_evidence=target_evidence,
            baseline_evidence=baseline_evidence,
            corporate_action_evidence=action_evidence,
            frozen_action_analysis=frozen_actions,
            publication_action_analysis=publication_actions,
        )

    pre_event_basis = audit_price_basis_actions(
        action_payload,
        raw_payload=action_raw,
        symbol=symbol,
        start_date=freeze.date(),
        end_date=publication.date(),
    )
    if (
        pre_event_basis.status != "READY"
        or pre_event_basis.version is None
        or pre_event_basis.relevant_actions
        or pre_event_basis.unresolved_actions
    ):
        return _record(
            member=member,
            quarter=quarter,
            status="SKIPPED",
            reason="post_freeze_price_basis_action",
            freeze_at_utc=freeze_at_utc,
            pair=pair,
            target_event=target_event,
            baseline_event=baseline_event,
            expectation=expectation,
            discovery_evidence=discovery_evidence,
            target_evidence=target_evidence,
            baseline_evidence=baseline_evidence,
            corporate_action_evidence=action_evidence,
            frozen_action_analysis=frozen_actions,
            publication_action_analysis=publication_actions,
            pre_event_price_basis=pre_event_basis,
        )

    reference_session = calendar.reference_session(pair.target.exchange_published_at_utc)
    reference_day = date.fromisoformat(reference_session.session_date)
    udiff_raw, udiff_evidence = cache.udiff_bytes(reference_day)
    try:
        reference_price = parse_udiff_equity(
            udiff_raw,
            symbol=symbol,
            session_date=reference_day,
            series=member.series,
            expected_isin=target_event.isin or member.isin,
        )
        close_price = reference_price.close_price
    except MarketDataMissingRow:
        close_price = None

    reference = PriceReference(
        symbol=symbol,
        role="price_day_minus_2",
        trading_date=reference_session.session_date,
        close_timestamp_utc=reference_session.close_timestamp_utc,
        close_price=close_price,
        source=udiff_evidence["source_url"],
        corporate_action_version=pre_event_basis.version,
    )
    signal = score_h002_historical_replay(
        normalized_target,
        expectation,
        reference,
        reconstructed_at_utc=_iso(datetime.now(UTC)),
    )
    evidence = {
        **action_evidence,
        "price_reference_udiff": udiff_evidence,
    }
    return _record(
        member=member,
        quarter=quarter,
        status="SIGNAL" if signal.bucket != "NO_SIGNAL" else "NO_SIGNAL",
        reason=signal.no_signal_reason,
        freeze_at_utc=freeze_at_utc,
        pair=pair,
        target_event=target_event,
        baseline_event=baseline_event,
        expectation=expectation,
        reference=reference,
        signal=signal,
        discovery_evidence=discovery_evidence,
        target_evidence=target_evidence,
        baseline_evidence=baseline_evidence,
        corporate_action_evidence=evidence,
        frozen_action_analysis=frozen_actions,
        publication_action_analysis=publication_actions,
        pre_event_price_basis=pre_event_basis,
    )


def _append_error(
    records: list[dict[str, Any]],
    *,
    member: UniverseMember,
    quarter: dict[str, Any],
    offset_days: int,
    exc: BaseException,
) -> None:
    records.append(
        _record(
            member=member,
            quarter=quarter,
            status="ERROR",
            reason=f"{type(exc).__name__}: {exc}",
            freeze_at_utc=historical_freeze_at(
                quarter["period_end"],
                offset_days=offset_days,
            ),
        )
    )


def run_phase_a(args: argparse.Namespace) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    rule = load_and_validate_historical_replay_rule(args.rule)
    universe = load_universe_snapshot(args.universe)
    members = universe.members
    if args.symbols:
        wanted = {
            item.strip().upper()
            for item in args.symbols.split(",")
            if item.strip()
        }
        members = [member for member in members if member.symbol.upper() in wanted]
        missing = wanted - {member.symbol.upper() for member in members}
        if missing:
            raise PhaseAError(
                f"requested symbols not present in frozen universe: {sorted(missing)}"
            )
    if args.limit:
        members = members[: args.limit]

    store_root = Path(args.store)
    store_root.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = NSEClient(timeout=args.timeout, attempts=args.attempts)
    cache = SourceCache(client, store_root)

    holiday_payload, holiday_raw = client.trading_holidays_with_raw()
    holiday_evidence = _retain(
        store_root,
        holiday_raw,
        kind="holiday-master",
        suffix=".json",
    )
    holiday_evidence["source_url"] = client.HOLIDAY_ENDPOINT.url + "?type=trading"
    calendar_snapshot = build_calendar_snapshot(
        holiday_payload,
        raw_holiday_bytes=holiday_raw,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 9, 30),
        captured_at=started_at,
        version="H002-HR001-NSE-CM-2026-v1",
    )
    if calendar_snapshot.unresolved_special_dates:
        raise PhaseAError(
            "historical replay calendar contains unresolved special sessions: "
            + ",".join(calendar_snapshot.unresolved_special_dates)
        )
    calendar = TradingCalendar(
        list(calendar_snapshot.sessions),
        version=calendar_snapshot.version,
    )

    quarters = list(rule["target_quarters"])
    quarters_by_id = {quarter["id"]: quarter for quarter in quarters}
    offset_days = int(rule["freeze_policy"]["target_period_end_offset_days"])
    records: list[dict[str, Any]] = []

    for index, member in enumerate(members, start=1):
        try:
            discovery_payload, discovery_raw = (
                client.integrated_financial_filings_with_raw(member.symbol)
            )
            discovery_evidence = _retain(
                store_root,
                discovery_raw,
                kind="integrated-discovery",
                suffix=".json",
            )
            discovery_evidence["source_url"] = client.INTEGRATED_FILING_ENDPOINT.url
            pairs = _select_pairs(
                discovery_payload,
                member=member,
                quarters=quarters,
                offset_days=offset_days,
                records=records,
                discovery_evidence=discovery_evidence,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            for quarter in quarters:
                _append_error(
                    records,
                    member=member,
                    quarter=quarter,
                    offset_days=offset_days,
                    exc=exc,
                )
            continue

        if pairs:
            try:
                action_from, action_to = _action_window(pairs, quarters_by_id)
                action_payload, action_raw, action_evidence = _corporate_actions(
                    client,
                    store_root,
                    symbol=member.symbol,
                    from_date=action_from,
                    to_date=action_to,
                )
            except (RuntimeError, ValueError, OSError) as exc:
                for quarter in quarters:
                    if quarter["id"] in pairs:
                        _append_error(
                            records,
                            member=member,
                            quarter=quarter,
                            offset_days=offset_days,
                            exc=exc,
                        )
                continue

            for quarter in quarters:
                pair = pairs.get(quarter["id"])
                if pair is None:
                    continue
                try:
                    records.append(
                        _process_pair(
                            cache=cache,
                            store_root=store_root,
                            started_at=started_at,
                            calendar=calendar,
                            member=member,
                            quarter=quarter,
                            pair=pair,
                            discovery_evidence=discovery_evidence,
                            action_payload=action_payload,
                            action_raw=action_raw,
                            action_evidence=action_evidence,
                            offset_days=offset_days,
                        )
                    )
                except (RuntimeError, ValueError, OSError) as exc:
                    _append_error(
                        records,
                        member=member,
                        quarter=quarter,
                        offset_days=offset_days,
                        exc=exc,
                    )

        if args.sleep > 0 and index < len(members):
            time.sleep(args.sleep)

    status_counts = Counter(record["status"] for record in records)
    bucket_counts = Counter(
        record["signal"]["bucket"]
        for record in records
        if isinstance(record.get("signal"), dict)
    )
    quarter_counts: dict[str, dict[str, int]] = {}
    for quarter in quarters:
        quarter_records = [
            record for record in records if record["quarter_id"] == quarter["id"]
        ]
        quarter_counts[quarter["id"]] = dict(
            sorted(Counter(record["status"] for record in quarter_records).items())
        )

    body = {
        "schema_version": 2,
        "phase": "A_SIGNAL_CAPTURE_ONLY",
        "compiler_revision": COMPILER_REVISION,
        "replay_rule_id": rule["id"],
        "replay_rule_sha256": rule["sha256"],
        "source_signal_rule_id": rule["source_signal_rule_id"],
        "generated_at_utc": _iso(datetime.now(UTC)),
        "outcome_data_included": False,
        "cohort_id": universe.cohort_id,
        "cohort_sha256": universe.sha256,
        "cohort_bias_label": rule["cohort"]["bias_label"],
        "member_count_requested": len(members),
        "observation_count_expected": len(members) * len(quarters),
        "observation_count": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "signal_bucket_counts": dict(sorted(bucket_counts.items())),
        "quarter_status_counts": quarter_counts,
        "calendar_snapshot": calendar_snapshot.to_dict(),
        "holiday_source": holiday_evidence,
        "records": records,
    }
    manifest_sha = _canonical_hash(body)
    document = {**body, "manifest_sha256": manifest_sha}
    output_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return document


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build phase-A H002 historical replay signals without loading outcomes."
    )
    parser.add_argument(
        "--rule",
        default="registry/h002_historical_replay_rule.yaml",
    )
    parser.add_argument(
        "--universe",
        default="research/prospective/universes/FY27-Q2-2026-09-06.json",
    )
    parser.add_argument(
        "--output",
        default=(
            "research/historical/h002/H002-HR001/phase-a/"
            "fixed-u001-transport-signals.json"
        ),
    )
    parser.add_argument("--store", default=".marketlab-historical-replay")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args()
    document = run_phase_a(args)
    print(
        json.dumps(
            {
                "manifest_sha256": document["manifest_sha256"],
                "observation_count": document["observation_count"],
                "status_counts": document["status_counts"],
                "signal_bucket_counts": document["signal_bucket_counts"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
