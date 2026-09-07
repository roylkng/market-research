from __future__ import annotations

import argparse
import io
import json
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from marketlab.events import HISTORICAL_RECONSTRUCTION
from marketlab.h002 import (
    H002SignalError,
    PriceReference,
    build_seasonal_expectation,
    build_terminal_no_signal_expectation,
)
from marketlab.h002_historical import score_h002_historical_replay
from marketlab.h002_historical_calendar import (
    HOLIDAY_2025_SOURCE_URL,
    MUHURAT_2025_SOURCE_URL,
    build_hr002_calendar,
)
from marketlab.h002_historical_identity import (
    historical_symbol_variants,
    is_non_comparable_predecessor,
    normalize_symbol_for_h002,
    symbols_equivalent,
)
from marketlab.h002_historical_outcomes import load_phase_a_manifest
from marketlab.h002_historical_v2 import (
    MixedHistoricalFilingPair,
    candidate_rows_for_period,
    historical_freeze_v2,
    load_historical_replay_v2_rule,
)
from marketlab.marketdata import (
    MarketDataMissingRow,
    audit_price_basis_actions,
    parse_udiff_equity,
)
from marketlab.nse import NSEAcquisitionError, NSEClient, NSEEndpoint
from marketlab.preparation import analyze_eps_basis_actions
from marketlab.universe import UniverseMember, load_universe_snapshot
from run_h002_historical_replay_r2 import (
    SourceCache,
    _assert_event_period_basis,
    _corporate_actions,
    _document_event,
    _is_archive_404,
    _retain,
    _same_quarter_label,
)

COMPILER_REVISION = "H002-HR002-phase-a-r1-six-quarter-mixed-source"
LEGACY_ENDPOINT = NSEEndpoint(
    "legacy_financial_results",
    "https://www.nseindia.com/api/corporates-financial-results",
)
BOUND_HR001_PHASE_A_SHA256 = (
    "2062e21ee1b1cbcd86d758ae3cf9ef9aeb43664c629ca5eb7a22cd885068ef98"
)
BOUND_HR001_PHASE_A_PATH = (
    "research/historical/h002/H002-HR001/phase-a/fixed-u001-transport-signals.json"
)


class PhaseAV2Error(RuntimeError):
    pass


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _payload_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("records") or []
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _fetch_discovery_for_variants(
    client: NSEClient,
    store_root: Path,
    member: UniverseMember,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    integrated_rows: list[dict[str, Any]] = []
    legacy_rows: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {"symbols_queried": [], "integrated": [], "legacy": []}
    seen_integrated: set[str] = set()
    seen_legacy: set[str] = set()

    for symbol in historical_symbol_variants(member.symbol):
        evidence["symbols_queried"].append(symbol)
        try:
            integrated_payload, integrated_raw = client.integrated_financial_filings_with_raw(symbol)
        except NSEAcquisitionError as exc:
            evidence["integrated"].append({"symbol": symbol, "status": "FETCH_FAILED", "error": str(exc)})
        else:
            retained = _retain(
                store_root,
                integrated_raw,
                kind="integrated-discovery",
                suffix=".json",
            )
            retained.update({"symbol": symbol, "source_url": client.INTEGRATED_FILING_ENDPOINT.url})
            evidence["integrated"].append(retained)
            for row in _payload_rows(integrated_payload):
                key = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                if key not in seen_integrated:
                    integrated_rows.append(row)
                    seen_integrated.add(key)

        try:
            legacy_payload, legacy_raw = client._json_get_with_raw(
                LEGACY_ENDPOINT,
                params={"index": "equities", "symbol": symbol, "period": "Quarterly"},
            )
        except NSEAcquisitionError as exc:
            evidence["legacy"].append({"symbol": symbol, "status": "FETCH_FAILED", "error": str(exc)})
        else:
            retained = _retain(
                store_root,
                legacy_raw,
                kind="legacy-financial-results-discovery",
                suffix=".json",
            )
            retained.update({"symbol": symbol, "source_url": LEGACY_ENDPOINT.url})
            evidence["legacy"].append(retained)
            for row in _payload_rows(legacy_payload):
                key = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                if key not in seen_legacy:
                    legacy_rows.append(row)
                    seen_legacy.add(key)

    if not integrated_rows and not legacy_rows:
        raise PhaseAV2Error(f"no official financial-result discovery rows for {member.symbol}")
    return {"data": integrated_rows}, legacy_rows, evidence


def _select_pair(
    *,
    integrated_payload: Any,
    legacy_payload: Any,
    member: UniverseMember,
    quarter: dict[str, Any],
    freeze_at_utc: str,
) -> MixedHistoricalFilingPair | None:
    variants = historical_symbol_variants(member.symbol)
    freeze = datetime.fromisoformat(freeze_at_utc).astimezone(UTC)
    for accounting_basis in ("Consolidated", "Standalone"):
        targets = []
        baselines = []
        for symbol in variants:
            targets.extend(
                candidate_rows_for_period(
                    integrated_payload=integrated_payload,
                    legacy_payload=legacy_payload,
                    symbol=symbol,
                    period_end=quarter["period_end"],
                    accounting_basis=accounting_basis,
                )
            )
            baselines.extend(
                candidate_rows_for_period(
                    integrated_payload=integrated_payload,
                    legacy_payload=legacy_payload,
                    symbol=symbol,
                    period_end=quarter["baseline_period_end"],
                    accounting_basis=accounting_basis,
                )
            )
        targets.sort(key=lambda item: (item.exchange_published_at_utc, item.source_url))
        baselines = [
            item
            for item in baselines
            if datetime.fromisoformat(item.exchange_published_at_utc).astimezone(UTC) <= freeze
        ]
        baselines.sort(key=lambda item: (item.exchange_published_at_utc, item.source_url))
        if not targets or not baselines:
            continue
        first_time = targets[0].exchange_published_at_utc
        first_rows = [item for item in targets if item.exchange_published_at_utc == first_time]
        first_urls = {item.source_url for item in first_rows}
        if len(first_urls) != 1:
            raise PhaseAV2Error(
                f"ambiguous first target filing for {member.symbol}/{quarter['id']}: {sorted(first_urls)}"
            )
        latest_time = baselines[-1].exchange_published_at_utc
        latest_rows = [item for item in baselines if item.exchange_published_at_utc == latest_time]
        latest_urls = {item.source_url for item in latest_rows}
        if len(latest_urls) != 1:
            raise PhaseAV2Error(
                f"ambiguous baseline at freeze for {member.symbol}/{quarter['id']}: {sorted(latest_urls)}"
            )
        target = first_rows[-1]
        baseline = latest_rows[-1]
        if datetime.fromisoformat(target.exchange_published_at_utc).astimezone(UTC) <= freeze:
            raise PhaseAV2Error(
                f"target filing for {member.symbol}/{quarter['id']} was public by the freeze"
            )
        return MixedHistoricalFilingPair(
            symbol=member.symbol.upper(),
            accounting_basis=accounting_basis,
            target=target,
            baseline=baseline,
        )
    return None


def _validate_2025_calendar_sources(holiday_raw: bytes, muhurat_raw: bytes) -> None:
    try:
        holiday_text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(holiday_raw)).pages)
        muhurat_text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(muhurat_raw)).pages)
    except Exception as exc:
        raise PhaseAV2Error(f"could not parse official 2025 calendar circulars: {exc}") from exc
    for token in (
        "NSE/CMTR/65587",
        "February 26, 2025",
        "March 14, 2025",
        "October 21, 2025",
        "December 25, 2025",
    ):
        if token not in holiday_text:
            raise PhaseAV2Error(f"2025 holiday circular is missing expected token: {token}")
    for token in ("NSE/CMTR/70319", "October 21, 2025", "13:45", "14:45"):
        if token not in muhurat_text:
            raise PhaseAV2Error(f"2025 Muhurat circular is missing expected token: {token}")


def _record(
    *,
    member: UniverseMember,
    quarter: dict[str, Any],
    status: str,
    reason: str | None,
    freeze_at_utc: str,
    pair: MixedHistoricalFilingPair | None = None,
    target_event: Any | None = None,
    baseline_event: Any | None = None,
    expectation: Any | None = None,
    reference: PriceReference | None = None,
    signal: Any | None = None,
    discovery_evidence: dict[str, Any] | None = None,
    target_evidence: dict[str, Any] | None = None,
    baseline_evidence: dict[str, Any] | None = None,
    action_evidence: dict[str, Any] | None = None,
    frozen_actions: Any | None = None,
    publication_actions: Any | None = None,
    pre_event_basis: Any | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
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
        "normalization": {
            "canonical_symbol": member.symbol,
            "registered_symbol_variants": list(historical_symbol_variants(member.symbol)),
            "target_symbol_raw": None if target_event is None else target_event.symbol,
            "baseline_symbol_raw": None if baseline_event is None else baseline_event.symbol,
            "target_isin_raw": None if target_event is None else target_event.isin,
            "baseline_isin_raw": None if baseline_event is None else baseline_event.isin,
        },
        "evidence": {
            "discovery": discovery_evidence,
            "target_source": target_evidence,
            "baseline_source": baseline_evidence,
            "corporate_actions": action_evidence,
            "frozen_eps_basis": None if frozen_actions is None else asdict(frozen_actions),
            "publication_eps_basis": None
            if publication_actions is None
            else asdict(publication_actions),
            "pre_event_price_basis": None if pre_event_basis is None else asdict(pre_event_basis),
        },
    }


def _process_pair(
    *,
    cache: SourceCache,
    store_root: Path,
    captured_at: datetime,
    calendar: Any,
    member: UniverseMember,
    quarter: dict[str, Any],
    pair: MixedHistoricalFilingPair,
    freeze_at_utc: str,
    discovery_evidence: dict[str, Any],
    action_payload: Any,
    action_raw: bytes,
    action_evidence: dict[str, Any],
) -> dict[str, Any]:
    try:
        target_raw = cache.archive_bytes(pair.target.source_url)
    except NSEAcquisitionError as exc:
        if _is_archive_404(exc):
            return _record(
                member=member,
                quarter=quarter,
                status="UNCOVERED",
                reason=f"target_archive_source_unavailable_404:{pair.target.source_url}",
                freeze_at_utc=freeze_at_utc,
                pair=pair,
                discovery_evidence=discovery_evidence,
            )
        raise
    try:
        baseline_raw = cache.archive_bytes(pair.baseline.source_url)
    except NSEAcquisitionError as exc:
        if _is_archive_404(exc):
            return _record(
                member=member,
                quarter=quarter,
                status="UNCOVERED",
                reason=f"baseline_archive_source_unavailable_404:{pair.baseline.source_url}",
                freeze_at_utc=freeze_at_utc,
                pair=pair,
                discovery_evidence=discovery_evidence,
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
        discovery={"raw_sha256": discovery_evidence["composite_sha256"], "raw_path": discovery_evidence["manifest_path"]},
        captured_at=captured_at,
        store_root=store_root,
    )
    baseline_event = _document_event(
        baseline_raw,
        source_url=pair.baseline.source_url,
        exchange_published_at_utc=pair.baseline.exchange_published_at_utc,
        discovery={"raw_sha256": discovery_evidence["composite_sha256"], "raw_path": discovery_evidence["manifest_path"]},
        captured_at=captured_at,
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
    if not symbols_equivalent(member.symbol, target_event.symbol):
        raise PhaseAV2Error(
            f"target symbol mismatch: canonical={member.symbol}, observed={target_event.symbol}"
        )
    if is_non_comparable_predecessor(member.symbol, baseline_event.symbol):
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
            action_evidence=action_evidence,
        )
    if not symbols_equivalent(member.symbol, baseline_event.symbol):
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
            action_evidence=action_evidence,
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
            action_evidence=action_evidence,
        )

    publication = datetime.fromisoformat(pair.target.exchange_published_at_utc).astimezone(UTC)
    freeze = datetime.fromisoformat(freeze_at_utc).astimezone(UTC)
    frozen_actions = analyze_eps_basis_actions(
        action_payload,
        raw_payload=action_raw,
        symbol=member.symbol,
        baseline_period_end=quarter["baseline_period_end"],
        as_of_utc=freeze_at_utc,
    )
    publication_actions = analyze_eps_basis_actions(
        action_payload,
        raw_payload=action_raw,
        symbol=member.symbol,
        baseline_period_end=quarter["baseline_period_end"],
        as_of_utc=pair.target.exchange_published_at_utc,
    )
    normalized_baseline = normalize_symbol_for_h002(
        baseline_event,
        canonical_symbol=member.symbol,
    )
    normalized_target = normalize_symbol_for_h002(target_event, canonical_symbol=member.symbol)

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
            action_evidence=action_evidence,
            frozen_actions=frozen_actions,
            publication_actions=publication_actions,
        )

    if frozen_actions.status != "READY" or frozen_actions.version is None:
        expectation = build_terminal_no_signal_expectation(
            normalized_baseline,
            canonical_symbol=member.symbol,
            target_period_end=quarter["period_end"],
            target_quarter=normalized_target.reporting_quarter or "",
            target_accounting_basis=pair.accounting_basis,
            baseline_available_at_utc=None,
            expectation_as_of_utc=freeze_at_utc,
            no_signal_reason="unresolved_corporate_action",
            corporate_action_version="EPSCA-UNRESOLVED-" + frozen_actions.payload_sha256[:16],
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
            action_evidence=action_evidence,
            frozen_actions=frozen_actions,
            publication_actions=publication_actions,
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
            action_evidence=action_evidence,
            frozen_actions=frozen_actions,
            publication_actions=publication_actions,
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
            action_evidence=action_evidence,
            frozen_actions=frozen_actions,
            publication_actions=publication_actions,
        )

    pre_event_basis = audit_price_basis_actions(
        action_payload,
        raw_payload=action_raw,
        symbol=member.symbol,
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
            action_evidence=action_evidence,
            frozen_actions=frozen_actions,
            publication_actions=publication_actions,
            pre_event_basis=pre_event_basis,
        )

    reference_session = calendar.reference_session(pair.target.exchange_published_at_utc)
    reference_day = date.fromisoformat(reference_session.session_date)
    udiff_raw, udiff_evidence = cache.udiff_bytes(reference_day)
    try:
        reference_price = parse_udiff_equity(
            udiff_raw,
            symbol=target_event.symbol,
            session_date=reference_day,
            series=member.series,
            expected_isin=target_event.isin,
        )
        close_price = reference_price.close_price
    except MarketDataMissingRow:
        close_price = None
    reference = PriceReference(
        symbol=member.symbol,
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
        action_evidence={**action_evidence, "price_reference_udiff": udiff_evidence},
        frozen_actions=frozen_actions,
        publication_actions=publication_actions,
        pre_event_basis=pre_event_basis,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    captured_at = datetime.now(UTC)
    rule = load_historical_replay_v2_rule(args.rule)
    universe = load_universe_snapshot(args.universe)
    members = universe.members[: args.limit or None]
    if args.symbols:
        wanted = {item.strip().upper() for item in args.symbols.split(",") if item.strip()}
        members = [member for member in members if member.symbol.upper() in wanted]
        missing = wanted - {member.symbol.upper() for member in members}
        if missing:
            raise PhaseAV2Error(f"symbols missing from frozen cohort: {sorted(missing)}")

    store_root = Path(args.store)
    store_root.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = NSEClient(timeout=args.timeout, attempts=args.attempts)
    cache = SourceCache(client, store_root)

    bound_hr001 = load_phase_a_manifest(
        BOUND_HR001_PHASE_A_PATH,
        expected_sha256=BOUND_HR001_PHASE_A_SHA256,
    )
    holiday_2025_raw = client.archive_bytes(HOLIDAY_2025_SOURCE_URL)
    muhurat_2025_raw = client.archive_bytes(MUHURAT_2025_SOURCE_URL)
    _validate_2025_calendar_sources(holiday_2025_raw, muhurat_2025_raw)
    holiday_2025_evidence = _retain(
        store_root, holiday_2025_raw, kind="calendar-2025-holidays", suffix=".pdf"
    )
    holiday_2025_evidence["source_url"] = HOLIDAY_2025_SOURCE_URL
    muhurat_2025_evidence = _retain(
        store_root, muhurat_2025_raw, kind="calendar-2025-muhurat", suffix=".pdf"
    )
    muhurat_2025_evidence["source_url"] = MUHURAT_2025_SOURCE_URL
    calendar, calendar_evidence = build_hr002_calendar(
        phase_a_2026_manifest=bound_hr001,
        phase_a_2026_manifest_sha256=BOUND_HR001_PHASE_A_SHA256,
        holiday_2025_raw_sha256=holiday_2025_evidence["raw_sha256"],
        muhurat_2025_raw_sha256=muhurat_2025_evidence["raw_sha256"],
    )
    calendar_evidence["holiday_2025_artifact"] = holiday_2025_evidence
    calendar_evidence["muhurat_2025_artifact"] = muhurat_2025_evidence

    offset_days = int(rule["freeze_policy"]["target_period_end_offset_days"])
    freeze_clock = str(rule["freeze_policy"]["freeze_clock"])
    quarters = list(rule["target_quarters"])
    records: list[dict[str, Any]] = []

    for index, member in enumerate(members, start=1):
        try:
            integrated_payload, legacy_payload, discovery_evidence = _fetch_discovery_for_variants(
                client, store_root, member
            )
            composite_path = store_root / "discovery-manifests" / f"{member.symbol}.json"
            composite_path.parent.mkdir(parents=True, exist_ok=True)
            composite_raw = json.dumps(discovery_evidence, sort_keys=True, separators=(",", ":")).encode()
            import hashlib

            discovery_evidence["composite_sha256"] = hashlib.sha256(composite_raw).hexdigest()
            composite_path.write_text(json.dumps(discovery_evidence, indent=2, sort_keys=True) + "\n")
            discovery_evidence["manifest_path"] = str(composite_path)

            pairs: dict[str, MixedHistoricalFilingPair] = {}
            for quarter in quarters:
                freeze_at_utc = historical_freeze_v2(
                    quarter["period_end"],
                    offset_days=offset_days,
                    freeze_clock=freeze_clock,
                )
                pair = _select_pair(
                    integrated_payload=integrated_payload,
                    legacy_payload=legacy_payload,
                    member=member,
                    quarter=quarter,
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

            if pairs:
                start = min(
                    date.fromisoformat(quarter["baseline_period_end"])
                    for quarter in quarters
                    if quarter["id"] in pairs
                )
                end = max(
                    datetime.fromisoformat(pair.target.exchange_published_at_utc).date()
                    for pair in pairs.values()
                )
                action_payload, action_raw, action_evidence = _corporate_actions(
                    client,
                    store_root,
                    symbol=member.symbol,
                    from_date=start,
                    to_date=end,
                )
                for quarter in quarters:
                    pair = pairs.get(quarter["id"])
                    if pair is None:
                        continue
                    freeze_at_utc = historical_freeze_v2(
                        quarter["period_end"],
                        offset_days=offset_days,
                        freeze_clock=freeze_clock,
                    )
                    try:
                        records.append(
                            _process_pair(
                                cache=cache,
                                store_root=store_root,
                                captured_at=captured_at,
                                calendar=calendar,
                                member=member,
                                quarter=quarter,
                                pair=pair,
                                freeze_at_utc=freeze_at_utc,
                                discovery_evidence=discovery_evidence,
                                action_payload=action_payload,
                                action_raw=action_raw,
                                action_evidence=action_evidence,
                            )
                        )
                    except (RuntimeError, ValueError, OSError) as exc:
                        records.append(
                            _record(
                                member=member,
                                quarter=quarter,
                                status="ERROR",
                                reason=f"{type(exc).__name__}: {exc}",
                                freeze_at_utc=freeze_at_utc,
                            )
                        )
        except (RuntimeError, ValueError, OSError) as exc:
            existing = {(record["symbol"], record["quarter_id"]) for record in records}
            for quarter in quarters:
                key = (member.symbol, quarter["id"])
                if key in existing:
                    continue
                records.append(
                    _record(
                        member=member,
                        quarter=quarter,
                        status="ERROR",
                        reason=f"{type(exc).__name__}: {exc}",
                        freeze_at_utc=historical_freeze_v2(
                            quarter["period_end"],
                            offset_days=offset_days,
                            freeze_clock=freeze_clock,
                        ),
                    )
                )
        if index % 10 == 0:
            print(f"phase-A HR002 {index}/{len(members)}", flush=True)
        if args.sleep > 0 and index < len(members):
            time.sleep(args.sleep)

    status_counts = Counter(record["status"] for record in records)
    bucket_counts = Counter(
        record["signal"]["bucket"]
        for record in records
        if isinstance(record.get("signal"), dict)
    )
    quarter_status = {
        quarter["id"]: dict(
            sorted(
                Counter(
                    record["status"]
                    for record in records
                    if record["quarter_id"] == quarter["id"]
                ).items()
            )
        )
        for quarter in quarters
    }
    body = {
        "schema_version": 1,
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
        "quarter_status_counts": quarter_status,
        "calendar_evidence": calendar_evidence,
        "records": records,
    }
    import hashlib

    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    document = {**body, "manifest_sha256": hashlib.sha256(encoded).hexdigest()}
    output_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture H002-HR002 six-quarter signals without outcomes")
    parser.add_argument("--rule", default="registry/h002_historical_replay_v2_rule.yaml")
    parser.add_argument(
        "--universe", default="research/prospective/universes/FY27-Q2-2026-09-06.json"
    )
    parser.add_argument(
        "--output",
        default="research/historical/h002/H002-HR002/phase-a/fixed-u001-six-quarter-signals.json",
    )
    parser.add_argument("--store", default=".marketlab-historical-replay-v2")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
