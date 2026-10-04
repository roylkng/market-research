from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes
from marketlab.fundamental_quality import (
    CORE_METRICS,
    FACT_FIELDS,
    FQ001_D001_ID,
    parse_annual_quality_filing,
    quality_record,
    select_annual_quality_pair,
    validate_annual_shape,
)
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.universe import load_universe_snapshot

EXPECTED_UNIVERSE_SHA = (
    "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
)
MIN_PAIR_COUNT = 70
MIN_CORE_COMPLETE = 60
MIN_PER_METRIC_COVERAGE = 60


def _write_bytes(
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
        raise RuntimeError(f"FQ001 content-addressed collision: {path}")
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
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    row["failure_sha256"] = digest(row)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen FQ001-D001 annual quality source feasibility"
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
        raise AlphaContractError("FQ001 D001 universe SHA mismatch")
    if len(universe.members) != 100:
        raise AlphaContractError("FQ001 D001 requires frozen 100-member U001")

    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    records = []
    failures = []

    for index, member in enumerate(universe.members, start=1):
        symbol = member.symbol.upper()
        discovery_sha = None
        print(f"[{index:03d}/100] {symbol}", flush=True)

        try:
            payload, discovery_raw = client.integrated_financial_filings_with_raw(symbol)
            discovery_sha, _ = _write_bytes(
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
            pair = select_annual_quality_pair(payload, symbol=symbol)
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

        target_sha, _ = _write_bytes(
            args.raw_dir,
            kind="filings",
            raw=target_raw,
            suffix=_suffix(pair.target.source_url),
        )
        baseline_sha, _ = _write_bytes(
            args.raw_dir,
            kind="filings",
            raw=baseline_raw,
            suffix=_suffix(pair.baseline.source_url),
        )

        try:
            target = parse_annual_quality_filing(
                target_raw,
                candidate=pair.target,
                expected_isin=member.isin,
            )
            baseline = parse_annual_quality_filing(
                baseline_raw,
                candidate=pair.baseline,
                expected_isin=target.isin,
            )
            validate_annual_shape(target)
            validate_annual_shape(baseline)

            if member.isin and target.isin and member.isin != target.isin:
                raise AlphaContractError(
                    "FQ001 target filing ISIN differs from frozen universe"
                )
            if target.raw_sha256 != target_sha:
                raise AlphaContractError("FQ001 target raw SHA mismatch")
            if baseline.raw_sha256 != baseline_sha:
                raise AlphaContractError("FQ001 baseline raw SHA mismatch")

            records.append(
                quality_record(
                    pair=pair,
                    target=target,
                    baseline=baseline,
                    discovery_raw_sha256=discovery_sha,
                )
            )
        except AlphaContractError as exc:
            failures.append(
                _failure(
                    symbol=symbol,
                    stage="PARSE_OR_METRIC",
                    reason=str(exc),
                    discovery_raw_sha256=discovery_sha,
                )
            )

    if len(records) + len(failures) != len(universe.members):
        raise AlphaContractError("FQ001 coverage accounting does not equal U001")

    metric_coverage = {
        metric: sum(record["metrics"][metric] is not None for record in records)
        for metric in CORE_METRICS
    }
    target_fact_coverage = {
        field: sum(record["target_facts"][field] is not None for record in records)
        for field in FACT_FIELDS
    }
    baseline_fact_coverage = {
        field: sum(record["baseline_facts"][field] is not None for record in records)
        for field in FACT_FIELDS
    }
    complete_count = sum(record["all_core_metrics_complete"] for record in records)
    basis_counts = Counter(record["accounting_basis"] for record in records)
    parser_pair_counts = Counter(
        f"{record['target_parser_version']}|{record['baseline_parser_version']}"
        for record in records
    )
    identity_continuity_counts = Counter(
        record["issuer_identity_continuity"] for record in records
    )
    failure_stage_counts = Counter(row["stage"] for row in failures)
    failure_reason_counts = Counter(row["reason"] for row in failures)

    threshold_passes = {
        "same_basis_pair_count": len(records) >= MIN_PAIR_COUNT,
        "complete_core_metric_rows": complete_count >= MIN_CORE_COMPLETE,
        "each_core_metric_coverage": all(
            count >= MIN_PER_METRIC_COVERAGE for count in metric_coverage.values()
        ),
    }
    feasibility_pass = all(threshold_passes.values())

    panel = {
        "schema_version": 1,
        "diagnostic_id": FQ001_D001_ID,
        "status": "COMPLETE_SOURCE_FEASIBILITY",
        "evidence_class": "HISTORICAL_SOURCE_AND_METRIC_FEASIBILITY_NO_RETURNS",
        "generated_at_utc": generated_at,
        "universe_sha256": universe.sha256,
        "universe_member_count": len(universe.members),
        "target_period_end": "2026-03-31",
        "baseline_period_end": "2025-03-31",
        "same_basis_pair_count": len(records),
        "complete_core_metric_count": complete_count,
        "core_metrics": list(CORE_METRICS),
        "metric_coverage": metric_coverage,
        "target_fact_coverage": target_fact_coverage,
        "baseline_fact_coverage": baseline_fact_coverage,
        "basis_counts": dict(sorted(basis_counts.items())),
        "parser_pair_counts": dict(sorted(parser_pair_counts.items())),
        "identity_continuity_counts": dict(sorted(identity_continuity_counts.items())),
        "failure_count": len(failures),
        "failure_stage_counts": dict(sorted(failure_stage_counts.items())),
        "failure_reason_counts": dict(sorted(failure_reason_counts.items())),
        "feasibility_thresholds": {
            "minimum_same_basis_pairs": MIN_PAIR_COUNT,
            "minimum_complete_core_metric_rows": MIN_CORE_COMPLETE,
            "minimum_each_core_metric_coverage": MIN_PER_METRIC_COVERAGE,
        },
        "threshold_passes": threshold_passes,
        "feasibility_pass": feasibility_pass,
        "promotion_allowed_to_quality_score_design": feasibility_pass,
        "records": sorted(records, key=lambda row: row["symbol"]),
        "failures": sorted(failures, key=lambda row: row["symbol"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "fq001-d001-panel.json").write_text(
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
    summary = {key: value for key, value in panel.items() if key not in {"records", "failures"}}
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
