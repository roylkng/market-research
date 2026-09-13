from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from marketlab.h022_expanded_sources import (
    ExpandedSourceError,
    build_coverage_bundle,
    build_coverage_record,
    incomplete_coverage_record,
    validate_coverage_bundle,
    validate_membership_inputs,
)
from marketlab.marketdata import MarketArtifactStore
from marketlab.nse import NSEAcquisitionError, NSEClient

FROM_DATE = "01-09-2024"
TO_DATE = "06-09-2026"


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _union_symbols(reconstruction: dict) -> list[str]:
    rows = reconstruction.get("expanded_union_members")
    if not isinstance(rows, list):
        raise ExpandedSourceError("expanded union members are missing")
    symbols = sorted(str(row.get("symbol") or "").strip().upper() for row in rows if isinstance(row, dict))
    if len(symbols) != 211 or any(not symbol for symbol in symbols) or len(set(symbols)) != 211:
        raise ExpandedSourceError("expanded union must contain exactly 211 unique symbols")
    return symbols


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build H022-US001 source coverage for historical Nifty 200 union"
    )
    parser.add_argument("--rule", type=Path, required=True)
    parser.add_argument("--reconstruction", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--bundle-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--sleep-seconds", type=float, default=0.15)
    args = parser.parse_args()

    if args.sleep_seconds < 0:
        raise ValueError("sleep-seconds must be non-negative")
    reconstruction = _load_json(args.reconstruction)
    audit = _load_json(args.audit)
    if not isinstance(reconstruction, dict) or not isinstance(audit, dict):
        raise TypeError("reconstruction and audit inputs must be JSON objects")
    validate_membership_inputs(reconstruction, audit)
    symbols = _union_symbols(reconstruction)

    rule_bytes = args.rule.read_bytes()
    if not rule_bytes:
        raise ValueError("H022 expanded source rule is empty")
    rule_sha256 = hashlib.sha256(rule_bytes).hexdigest()

    captured_at = datetime.now(UTC)
    client = NSEClient(timeout=25.0, attempts=4)
    store = MarketArtifactStore(args.store)
    records = []
    artifact_records: list[dict] = []

    for index, symbol in enumerate(symbols, start=1):
        try:
            payload, raw = client.corporate_announcements_with_raw(
                symbol,
                from_date=FROM_DATE,
                to_date=TO_DATE,
            )
            query = urlencode(
                {
                    "index": "equities",
                    "symbol": symbol,
                    "from_date": FROM_DATE,
                    "to_date": TO_DATE,
                }
            )
            source_url = f"{client.CORPORATE_ANNOUNCEMENT_ENDPOINT.url}?{query}"
            artifact = store.retain(
                raw,
                source_url=source_url,
                captured_at=captured_at,
                suffix=".json",
            )
            artifact_records.append(
                {
                    "symbol": symbol,
                    "artifact": artifact.to_dict(),
                }
            )
            record = build_coverage_record(
                payload,
                raw,
                symbol=symbol,
                captured_at=captured_at,
                reconstruction=reconstruction,
            )
        except (NSEAcquisitionError, ExpandedSourceError, ValueError) as exc:
            record = incomplete_coverage_record(
                symbol=symbol,
                captured_at=captured_at,
                reason=f"{type(exc).__name__}: {exc}",
            )
        records.append(record)
        print(
            f"[{index:03d}/211] {symbol}: {record.coverage_status}; "
            f"sources={record.source_count}; signal={record.signal_eligible_source_count}; "
            f"context={record.context_only_source_count}"
        )
        if args.sleep_seconds:
            time.sleep(args.sleep_seconds)

    bundle = build_coverage_bundle(
        records,
        reconstruction=reconstruction,
        audit=audit,
        generated_at=captured_at,
        source_rule_sha256=rule_sha256,
    )
    validate_coverage_bundle(bundle, reconstruction=reconstruction, audit=audit)
    _write_json(args.bundle_out, bundle)

    summary = {
        "schema_version": 1,
        "rule_id": bundle["rule_id"],
        "rule_sha256": bundle["rule_sha256"],
        "membership_reconstruction_sha256": bundle["membership_reconstruction_sha256"],
        "member_count": bundle["member_count"],
        "complete_count": bundle["complete_count"],
        "complete_zero_source_count": bundle["complete_zero_source_count"],
        "incomplete_count": bundle["incomplete_count"],
        "transcript_source_count": bundle["transcript_source_count"],
        "signal_eligible_source_count": bundle["signal_eligible_source_count"],
        "context_only_source_count": bundle["context_only_source_count"],
        "freeze_ready": bundle["freeze_ready"],
        "bundle_sha256": bundle["bundle_sha256"],
        "discovery_artifact_count": len(artifact_records),
        "incomplete_symbols": sorted(
            record.symbol for record in records if record.coverage_status == "INCOMPLETE"
        ),
        "zero_source_symbols": sorted(
            record.symbol
            for record in records
            if record.coverage_status == "COMPLETE_ZERO_SOURCE"
        ),
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.summary_out, summary)
    _write_json(args.store / "expanded-source-artifacts.json", artifact_records)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
