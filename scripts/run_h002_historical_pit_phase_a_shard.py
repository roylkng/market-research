from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import run_h002_historical_replay_v2r2 as base
import run_h002_historical_replay_v2r3 as compatibility

from marketlab.h002_historical_identity import (
    historical_discovery_query_symbols,
    historical_isins_equivalent,
)
from marketlab.h002_historical_v2 import historical_freeze_v2
from marketlab.marketdata import MarketDataError
from marketlab.nifty200_history import canonical_hash
from marketlab.universe import UniverseMember

EXPERIMENT_ID = "H002-HR003"
COMPILER_REVISION = "H002-HR003-phase-a-r1-point-in-time-nifty200"
_ORIGINAL_PARSE_UDIFF = base.parse_udiff_equity


class PitPhaseAError(RuntimeError):
    pass


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _load_snapshot_manifest(path: str | Path) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PitPhaseAError(f"could not load point-in-time snapshot manifest: {exc}") from exc
    if document.get("snapshot_count") != 6:
        raise PitPhaseAError("point-in-time snapshot manifest must contain six freezes")
    if document.get("live_capital_allowed") is not False:
        raise PitPhaseAError("historical point-in-time universe cannot authorize live capital")
    return document


def _load_snapshot_for_quarter(
    manifest: dict[str, Any], quarter_id: str
) -> tuple[dict[str, Any], str, str]:
    rows = [row for row in manifest.get("snapshots", []) if row.get("quarter_id") == quarter_id]
    if len(rows) != 1:
        raise PitPhaseAError(f"expected one point-in-time snapshot for {quarter_id}, found {len(rows)}")
    row = rows[0]
    path = Path(str(row["snapshot_path"]))
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PitPhaseAError(f"could not load {quarter_id} membership snapshot: {exc}") from exc
    declared = str(document.get("sha256") or "")
    if declared != row.get("snapshot_sha256"):
        raise PitPhaseAError(
            f"{quarter_id} membership SHA differs from frozen manifest: "
            f"manifest={row.get('snapshot_sha256')} snapshot={declared}"
        )
    unsigned = dict(document)
    unsigned.pop("sha256", None)
    actual = canonical_hash(unsigned)
    if actual != declared:
        raise PitPhaseAError(
            f"{quarter_id} membership snapshot hash mismatch: declared={declared} actual={actual}"
        )
    if document.get("quarter_id") != quarter_id:
        raise PitPhaseAError(f"membership snapshot quarter mismatch: {document.get('quarter_id')}")
    if document.get("regular_member_count") != 200:
        raise PitPhaseAError(f"{quarter_id} does not contain exactly 200 regular Nifty 200 members")
    symbols = [str(symbol).strip().upper() for symbol in document.get("non_financial_symbols", [])]
    if len(symbols) != int(document.get("non_financial_member_count", -1)):
        raise PitPhaseAError(f"{quarter_id} non-financial count does not match symbol list")
    if len(symbols) != len(set(symbols)):
        raise PitPhaseAError(f"{quarter_id} non-financial membership contains duplicate symbols")
    if any(symbol.startswith("DUMMY") for symbol in symbols):
        raise PitPhaseAError(f"{quarter_id} investable membership contains a demerger dummy")
    return document, str(path), declared


def _rule_quarter(rule: dict[str, Any], quarter_id: str) -> dict[str, Any]:
    quarters = [quarter for quarter in rule.get("target_quarters", []) if quarter.get("id") == quarter_id]
    if len(quarters) != 1:
        raise PitPhaseAError(f"mechanics rule does not contain exactly one {quarter_id} definition")
    return quarters[0]


def _member(symbol: str, rank: int) -> UniverseMember:
    return UniverseMember(
        rank=rank,
        source_rank=rank,
        symbol=symbol,
        isin="",
        ffmc=0.0,
        company_name=symbol,
        constituent_industry="POINT_IN_TIME_NON_FINANCIAL_NIFTY_200",
        series="EQ",
    )


def _processing_member(eligibility_member: UniverseMember, target_symbol: str) -> UniverseMember:
    return UniverseMember(
        rank=eligibility_member.rank,
        source_rank=eligibility_member.source_rank,
        symbol=target_symbol.strip().upper(),
        isin="",
        ffmc=0.0,
        company_name=target_symbol.strip().upper(),
        constituent_industry=eligibility_member.constituent_industry,
        series=eligibility_member.series,
    )


def _fetch_point_in_time_discovery(
    client: Any,
    store_root: Path,
    eligibility_member: UniverseMember,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Discover without treating retrieval-only successor tickers as economic aliases."""

    queries = historical_discovery_query_symbols(eligibility_member.symbol)
    identity_variants = base.historical_symbol_variants(eligibility_member.symbol)
    retrieval_only = [symbol for symbol in queries if symbol not in identity_variants]
    if not retrieval_only:
        return base._fetch_discovery_for_variants(client, store_root, eligibility_member)
    if len(retrieval_only) != 1:
        raise PitPhaseAError(
            f"multiple retrieval-only aliases are not supported for {eligibility_member.symbol}: "
            f"{retrieval_only}"
        )

    query_member = _processing_member(eligibility_member, retrieval_only[0])
    integrated, legacy, evidence = base._fetch_discovery_for_variants(
        client,
        store_root,
        query_member,
    )
    evidence = dict(evidence)
    evidence["point_in_time_retrieval_bridge"] = {
        "eligibility_symbol": eligibility_member.symbol,
        "query_symbol": query_member.symbol,
        "economic_identity_equivalence": False,
        "selection_requirement": (
            "candidate row must still match the point-in-time eligibility ticker or its "
            "identity-preserving aliases"
        ),
    }
    return integrated, legacy, evidence


def _parse_udiff_with_registered_source_isin(
    raw_zip: bytes,
    *,
    symbol: str,
    session_date: date,
    series: str = "EQ",
    expected_isin: str | None = None,
):
    """Allow only exact, pre-registered official-source ISIN inconsistencies."""

    try:
        return _ORIGINAL_PARSE_UDIFF(
            raw_zip,
            symbol=symbol,
            session_date=session_date,
            series=series,
            expected_isin=expected_isin,
        )
    except MarketDataError as exc:
        if "ISIN mismatch" not in str(exc):
            raise
        parsed = _ORIGINAL_PARSE_UDIFF(
            raw_zip,
            symbol=symbol,
            session_date=session_date,
            series=series,
            expected_isin=None,
        )
        if not historical_isins_equivalent(symbol, expected_isin, parsed.isin):
            raise
        return parsed


def _decorate_record(
    record: dict[str, Any],
    *,
    eligibility_symbol: str,
    eligibility_rank: int,
    snapshot_path: str,
    snapshot_sha256: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    result = dict(record)
    result["compiler_revision"] = COMPILER_REVISION
    target_event = result.get("target_event")
    if isinstance(target_event, dict):
        company_name = str(target_event.get("company_name") or "").strip()
        isin = str(target_event.get("isin") or "").strip()
        if company_name:
            result["company_name"] = company_name
        if isin:
            result["isin"] = isin
    result["point_in_time_eligibility"] = {
        "index_id": "NIFTY_200",
        "membership_rule": "ALL_REGULAR_NON_FINANCIAL_NIFTY200_AT_FREEZE",
        "symbol_at_freeze": eligibility_symbol,
        "deterministic_membership_order": eligibility_rank,
        "freeze_date": snapshot["freeze_date"],
        "membership_snapshot_path": snapshot_path,
        "membership_snapshot_sha256": snapshot_sha256,
        "regular_member_count": snapshot["regular_member_count"],
        "non_financial_member_count": snapshot["non_financial_member_count"],
        "survivorship_bias_status": snapshot["survivorship_bias_status"],
    }
    return result


def _build_calendar(client: Any, store_root: Path) -> tuple[Any, dict[str, Any]]:
    bound_hr001 = base.load_phase_a_manifest(
        base.BOUND_HR001_PHASE_A_PATH,
        expected_sha256=base.BOUND_HR001_PHASE_A_SHA256,
    )
    holiday_raw = client.archive_bytes(base.HOLIDAY_2025_SOURCE_URL)
    muhurat_raw = client.archive_bytes(base.MUHURAT_2025_SOURCE_URL)
    base._validate_2025_calendar_sources(holiday_raw, muhurat_raw)
    holiday_evidence = base._retain(
        store_root,
        holiday_raw,
        kind="calendar-2025-holidays",
        suffix=".pdf",
    )
    holiday_evidence["source_url"] = base.HOLIDAY_2025_SOURCE_URL
    muhurat_evidence = base._retain(
        store_root,
        muhurat_raw,
        kind="calendar-2025-muhurat",
        suffix=".pdf",
    )
    muhurat_evidence["source_url"] = base.MUHURAT_2025_SOURCE_URL
    calendar, evidence = base.build_hr002_calendar(
        phase_a_2026_manifest=bound_hr001,
        phase_a_2026_manifest_sha256=base.BOUND_HR001_PHASE_A_SHA256,
        holiday_2025_raw_sha256=holiday_evidence["raw_sha256"],
        muhurat_2025_raw_sha256=muhurat_evidence["raw_sha256"],
    )
    evidence["holiday_2025_artifact"] = holiday_evidence
    evidence["muhurat_2025_artifact"] = muhurat_evidence
    return calendar, evidence


def run(args: argparse.Namespace) -> dict[str, Any]:
    captured_at = datetime.now(UTC)
    mechanics_rule = base.load_historical_replay_v2_rule(args.rule)
    quarter = _rule_quarter(mechanics_rule, args.quarter_id)
    snapshot_manifest = _load_snapshot_manifest(args.snapshots_manifest)
    snapshot, snapshot_path, snapshot_sha256 = _load_snapshot_for_quarter(
        snapshot_manifest, args.quarter_id
    )
    symbols = [str(symbol).strip().upper() for symbol in snapshot["non_financial_symbols"]]
    members = [_member(symbol, rank) for rank, symbol in enumerate(symbols, start=1)]

    store_root = Path(args.store)
    store_root.mkdir(parents=True, exist_ok=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    client = base.NSEClient(timeout=args.timeout, attempts=args.attempts)
    cache = base.SourceCache(client, store_root)
    calendar, calendar_evidence = _build_calendar(client, store_root)

    offset_days = int(mechanics_rule["freeze_policy"]["target_period_end_offset_days"])
    freeze_clock = str(mechanics_rule["freeze_policy"]["freeze_clock"])
    freeze_at_utc = historical_freeze_v2(
        quarter["period_end"],
        offset_days=offset_days,
        freeze_clock=freeze_clock,
    )
    if date.fromisoformat(snapshot["freeze_date"]) != datetime.fromisoformat(
        freeze_at_utc
    ).astimezone(base.IST).date():
        raise PitPhaseAError(
            f"{args.quarter_id} membership freeze date and H002 mechanics freeze date differ"
        )

    records: list[dict[str, Any]] = []
    for index, eligibility_member in enumerate(members, start=1):
        eligibility_symbol = eligibility_member.symbol
        try:
            integrated_payload, legacy_payload, raw_discovery = _fetch_point_in_time_discovery(
                client,
                store_root,
                eligibility_member,
            )
            discovery_evidence = base._freeze_discovery_manifest(
                store_root,
                member=eligibility_member,
                evidence=raw_discovery,
            )
            pair = base._select_pair(
                integrated_payload=integrated_payload,
                legacy_payload=legacy_payload,
                member=eligibility_member,
                quarter=quarter,
                freeze_at_utc=freeze_at_utc,
            )
            if pair is None:
                record = base._record(
                    member=eligibility_member,
                    quarter=quarter,
                    status="UNCOVERED",
                    reason="no_matching_target_baseline_pair_as_of_freeze",
                    freeze_at_utc=freeze_at_utc,
                    discovery_evidence=discovery_evidence,
                )
            else:
                processing_member = _processing_member(
                    eligibility_member,
                    pair.target.symbol,
                )
                action_payload, action_raw, action_evidence = base._corporate_actions(
                    client,
                    store_root,
                    symbol=processing_member.symbol,
                    from_date=date.fromisoformat(quarter["baseline_period_end"]),
                    to_date=datetime.fromisoformat(pair.target.exchange_published_at_utc)
                    .astimezone(base.IST)
                    .date(),
                )
                previous_parse = base.parse_udiff_equity
                base.parse_udiff_equity = _parse_udiff_with_registered_source_isin
                try:
                    record = compatibility._process_pair_v3(
                        cache=cache,
                        store_root=store_root,
                        captured_at=captured_at,
                        calendar=calendar,
                        member=processing_member,
                        quarter=quarter,
                        pair=pair,
                        freeze_at_utc=freeze_at_utc,
                        discovery_evidence=discovery_evidence,
                        action_payload=action_payload,
                        action_raw=action_raw,
                        action_evidence=action_evidence,
                    )
                except (RuntimeError, ValueError, OSError) as exc:
                    record = base._record(
                        member=processing_member,
                        quarter=quarter,
                        status="ERROR",
                        reason=f"{type(exc).__name__}: {exc}",
                        freeze_at_utc=freeze_at_utc,
                    )
                finally:
                    base.parse_udiff_equity = previous_parse
        except (RuntimeError, ValueError, OSError) as exc:
            record = base._record(
                member=eligibility_member,
                quarter=quarter,
                status="ERROR",
                reason=f"{type(exc).__name__}: {exc}",
                freeze_at_utc=freeze_at_utc,
            )
        records.append(
            _decorate_record(
                record,
                eligibility_symbol=eligibility_symbol,
                eligibility_rank=eligibility_member.rank,
                snapshot_path=snapshot_path,
                snapshot_sha256=snapshot_sha256,
                snapshot=snapshot,
            )
        )
        if index % 10 == 0:
            print(f"HR003 {args.quarter_id} {index}/{len(members)}", flush=True)
        if args.sleep > 0 and index < len(members):
            time.sleep(args.sleep)

    status_counts = Counter(record["status"] for record in records)
    bucket_counts = Counter(
        record["signal"]["bucket"]
        for record in records
        if isinstance(record.get("signal"), dict)
    )
    body = {
        "schema_version": 1,
        "phase": "A_SIGNAL_CAPTURE_ONLY",
        "experiment_id": EXPERIMENT_ID,
        "compiler_revision": COMPILER_REVISION,
        "mechanics_rule_id": mechanics_rule["id"],
        "mechanics_rule_sha256": mechanics_rule["sha256"],
        "source_signal_rule_id": mechanics_rule["source_signal_rule_id"],
        "generated_at_utc": _iso(datetime.now(UTC)),
        "outcome_data_included": False,
        "live_capital_allowed": False,
        "cohort_bias_label": "POINT_IN_TIME_NIFTY200_MEMBERSHIP_NON_FINANCIAL",
        "quarter_id": args.quarter_id,
        "historical_freeze_at_utc": freeze_at_utc,
        "membership_snapshot_path": snapshot_path,
        "membership_snapshot_sha256": snapshot_sha256,
        "member_count_requested": len(members),
        "observation_count_expected": len(members),
        "observation_count": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "signal_bucket_counts": dict(sorted(bucket_counts.items())),
        "calendar_evidence": calendar_evidence,
        "records": records,
    }
    encoded = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    document = {**body, "manifest_sha256": hashlib.sha256(encoded).hexdigest()}
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "quarter_id": args.quarter_id,
                "manifest_sha256": document["manifest_sha256"],
                "member_count": len(members),
                "status_counts": document["status_counts"],
                "signal_bucket_counts": document["signal_bucket_counts"],
            },
            sort_keys=True,
        )
    )
    return document


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture one point-in-time Nifty 200 non-financial H002 historical quarter"
    )
    parser.add_argument("--quarter-id", required=True)
    parser.add_argument("--rule", default="registry/h002_historical_replay_v2_rule.yaml")
    parser.add_argument(
        "--snapshots-manifest",
        default="research/historical/nifty200/snapshots-v1/manifest.json",
    )
    parser.add_argument("--store", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--sleep", type=float, default=0.03)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
