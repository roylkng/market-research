from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_fundamental import (
    FEATURE_NAMES,
    pair_record,
    parse_historical_filing,
    select_fundamental_pair,
)
from marketlab.events import sha256_bytes
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.universe import load_universe_snapshot

EXPECTED_UNIVERSE_SHA = (
    "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
)


def _write_bytes_content_addressed(
    root: Path,
    *,
    kind: str,
    raw: bytes,
    suffix: str,
) -> tuple[str, str]:
    sha = sha256_bytes(raw)
    path = root / kind / "sha256" / f"{sha}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"T008 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha, str(path)


def _suffix(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".xml", ".html", ".htm"} else ".bin"


def _failure(
    *,
    symbol: str,
    stage: str,
    reason: str,
    discovery_raw_sha256: str | None = None,
) -> dict:
    row = {
        "symbol": symbol.upper(),
        "stage": stage,
        "reason": reason,
        "discovery_raw_sha256": discovery_raw_sha256,
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    row["failure_sha256"] = digest(row)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen T008-D001 fundamental filing source feasibility"
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--attempts", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    universe = load_universe_snapshot(args.universe)
    if universe.sha256 != EXPECTED_UNIVERSE_SHA:
        raise AlphaContractError("T008 D001 universe SHA mismatch")
    if len(universe.members) != 100:
        raise AlphaContractError("T008 D001 requires frozen 100-member U001")

    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    records = []
    failures = []

    for index, member in enumerate(universe.members, start=1):
        symbol = member.symbol.upper()
        discovery_sha = None
        print(f"[{index:03d}/100] {symbol}", flush=True)
        try:
            payload, discovery_raw = client.integrated_financial_filings_with_raw(
                symbol
            )
            discovery_sha, _ = _write_bytes_content_addressed(
                args.raw_dir,
                kind="discovery",
                raw=discovery_raw,
                suffix=".json",
            )
        except NSEAcquisitionError as exc:
            failures.append(
                _failure(
                    symbol=symbol,
                    stage="DISCOVERY_FETCH",
                    reason=str(exc),
                )
            )
            continue

        try:
            pair = select_fundamental_pair(
                payload,
                symbol=symbol,
            )
        except AlphaContractError as exc:
            failures.append(
                _failure(
                    symbol=symbol,
                    stage="PAIR_SELECTION",
                    reason=str(exc),
                    discovery_raw_sha256=discovery_sha,
                )
            )
            continue

        try:
            target_raw = client.archive_bytes(pair.target.source_url)
            baseline_raw = client.archive_bytes(pair.baseline.source_url)
        except NSEAcquisitionError as exc:
            failures.append(
                _failure(
                    symbol=symbol,
                    stage="FILING_FETCH",
                    reason=str(exc),
                    discovery_raw_sha256=discovery_sha,
                )
            )
            continue

        target_sha, target_path = _write_bytes_content_addressed(
            args.raw_dir,
            kind="filings",
            raw=target_raw,
            suffix=_suffix(pair.target.source_url),
        )
        baseline_sha, baseline_path = _write_bytes_content_addressed(
            args.raw_dir,
            kind="filings",
            raw=baseline_raw,
            suffix=_suffix(pair.baseline.source_url),
        )

        try:
            target_event = parse_historical_filing(
                target_raw,
                candidate=pair.target,
                raw_path=target_path,
                captured_at_utc=captured_at,
            )
            baseline_event = parse_historical_filing(
                baseline_raw,
                candidate=pair.baseline,
                raw_path=baseline_path,
                captured_at_utc=captured_at,
            )
            if (
                member.isin
                and target_event.isin
                and target_event.isin != member.isin
            ):
                raise AlphaContractError(
                    "T008 target filing ISIN differs from frozen universe"
                )
            if (
                member.isin
                and baseline_event.isin
                and baseline_event.isin != member.isin
            ):
                raise AlphaContractError(
                    "T008 baseline filing ISIN differs from frozen universe"
                )
            record = pair_record(
                pair=pair,
                target_event=target_event,
                baseline_event=baseline_event,
                discovery_raw_sha256=discovery_sha,
            )
            if record["target_raw_sha256"] != target_sha:
                raise AlphaContractError("T008 target raw SHA mismatch")
            if record["baseline_raw_sha256"] != baseline_sha:
                raise AlphaContractError("T008 baseline raw SHA mismatch")
            records.append(record)
        except AlphaContractError as exc:
            failures.append(
                _failure(
                    symbol=symbol,
                    stage="PARSE_OR_FEATURE",
                    reason=str(exc),
                    discovery_raw_sha256=discovery_sha,
                )
            )

    feature_coverage = {
        name: sum(
            record["features"].get(name) is not None
            for record in records
        )
        for name in FEATURE_NAMES
    }
    complete_count = sum(
        record["all_six_features_complete"]
        for record in records
    )
    basis_counts = Counter(
        record["accounting_basis"]
        for record in records
    )
    parser_pair_counts = Counter(
        f"{record['target_parser_version']}|{record['baseline_parser_version']}"
        for record in records
    )
    failure_stage_counts = Counter(
        row["stage"]
        for row in failures
    )
    failure_reason_counts = Counter(
        row["reason"]
        for row in failures
    )

    panel = {
        "schema_version": 1,
        "diagnostic_id": "AE001-T008-D001-v1",
        "evidence_class": "HISTORICAL_SOURCE_FEASIBILITY_NO_RETURNS",
        "generated_at_utc": captured_at,
        "universe_sha256": universe.sha256,
        "universe_member_count": len(universe.members),
        "target_period_end": "2026-06-30",
        "baseline_period_end": "2025-06-30",
        "same_basis_pair_count": len(records),
        "complete_six_feature_count": complete_count,
        "feature_coverage": feature_coverage,
        "basis_counts": dict(sorted(basis_counts.items())),
        "parser_pair_counts": dict(sorted(parser_pair_counts.items())),
        "failure_count": len(failures),
        "failure_stage_counts": dict(sorted(failure_stage_counts.items())),
        "failure_reason_counts": dict(sorted(failure_reason_counts.items())),
        "feasibility_thresholds": {
            "minimum_same_basis_pairs": 70,
            "minimum_complete_six_feature_rows": 60,
        },
        "feasibility_pass": (
            len(records) >= 70
            and complete_count >= 60
        ),
        "records": sorted(records, key=lambda row: row["symbol"]),
        "failures": sorted(failures, key=lambda row: row["symbol"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)

    args.output.mkdir(parents=True, exist_ok=True)
    panel_path = args.output / "t008-d001-panel.json"
    panel_path.write_text(
        json.dumps(
            panel,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        key: value
        for key, value in panel.items()
        if key not in {"records", "failures"}
    }
    (args.output / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
