from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_fundamental import (
    FEATURE_NAMES,
    pair_record,
    parse_historical_filing,
    select_mixed_source_fundamental_pair,
)
from marketlab.events import sha256_bytes
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.universe import load_universe_snapshot

DIAGNOSTIC_ID = "AE001-T008-D003-v1"
EXPECTED_UNIVERSE_SHA = (
    "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
)
PERIOD_PAIRS = (
    ("2025-09-30", "2024-09-30"),
    ("2025-12-31", "2024-12-31"),
)
MIN_COMPLETE_PER_PERIOD = 60
MIN_TOTAL_COMPLETE = 120


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
        raise RuntimeError(f"T008 D003 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha, str(path)


def _suffix(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".xml", ".html", ".htm"} else ".bin"


def _failure(
    *,
    symbol: str,
    target_period_end: str,
    baseline_period_end: str,
    stage: str,
    reason: str,
    target_discovery_raw_sha256: str | None = None,
    baseline_discovery_raw_sha256: str | None = None,
) -> dict:
    row = {
        "symbol": symbol.upper(),
        "target_period_end": target_period_end,
        "baseline_period_end": baseline_period_end,
        "stage": stage,
        "reason": reason,
        "target_discovery_raw_sha256": target_discovery_raw_sha256,
        "baseline_discovery_raw_sha256": baseline_discovery_raw_sha256,
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    row["failure_sha256"] = digest(row)
    return row


def _fetch_cached(
    client: NSEClient,
    cache: dict[str, bytes],
    url: str,
) -> bytes:
    if url not in cache:
        cache[url] = client.archive_bytes(url)
    return cache[url]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run frozen T008-D003 Integrated-target / legacy-baseline "
            "financial source diagnostic"
        )
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
        raise AlphaContractError("T008 D003 universe SHA mismatch")
    if len(universe.members) != 100:
        raise AlphaContractError("T008 D003 requires frozen 100-member U001")

    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    records: list[dict] = []
    failures: list[dict] = []
    filing_cache: dict[str, bytes] = {}

    for index, member in enumerate(universe.members, start=1):
        symbol = member.symbol.upper()
        target_discovery_sha = None
        baseline_discovery_sha = None
        print(f"[{index:03d}/100] {symbol}", flush=True)

        try:
            integrated_payload, integrated_raw = (
                client.integrated_financial_filings_with_raw(symbol)
            )
            target_discovery_sha, _ = _write_bytes_content_addressed(
                args.raw_dir,
                kind="integrated-discovery",
                raw=integrated_raw,
                suffix=".json",
            )
        except NSEAcquisitionError as exc:
            for target_period_end, baseline_period_end in PERIOD_PAIRS:
                failures.append(
                    _failure(
                        symbol=symbol,
                        target_period_end=target_period_end,
                        baseline_period_end=baseline_period_end,
                        stage="INTEGRATED_DISCOVERY_FETCH",
                        reason=str(exc),
                    )
                )
            continue

        try:
            legacy_payload, legacy_raw = client.financial_results_with_raw(
                symbol,
                period="Quarterly",
            )
            baseline_discovery_sha, _ = _write_bytes_content_addressed(
                args.raw_dir,
                kind="legacy-discovery",
                raw=legacy_raw,
                suffix=".json",
            )
        except NSEAcquisitionError as exc:
            for target_period_end, baseline_period_end in PERIOD_PAIRS:
                failures.append(
                    _failure(
                        symbol=symbol,
                        target_period_end=target_period_end,
                        baseline_period_end=baseline_period_end,
                        stage="LEGACY_DISCOVERY_FETCH",
                        reason=str(exc),
                        target_discovery_raw_sha256=target_discovery_sha,
                    )
                )
            continue

        for target_period_end, baseline_period_end in PERIOD_PAIRS:
            try:
                pair = select_mixed_source_fundamental_pair(
                    integrated_payload,
                    legacy_payload,
                    symbol=symbol,
                    target_period_end=target_period_end,
                    baseline_period_end=baseline_period_end,
                )
            except AlphaContractError as exc:
                failures.append(
                    _failure(
                        symbol=symbol,
                        target_period_end=target_period_end,
                        baseline_period_end=baseline_period_end,
                        stage="PAIR_SELECTION",
                        reason=str(exc),
                        target_discovery_raw_sha256=target_discovery_sha,
                        baseline_discovery_raw_sha256=baseline_discovery_sha,
                    )
                )
                continue

            try:
                target_raw = _fetch_cached(
                    client,
                    filing_cache,
                    pair.target.source_url,
                )
                baseline_raw = _fetch_cached(
                    client,
                    filing_cache,
                    pair.baseline.source_url,
                )
            except NSEAcquisitionError as exc:
                failures.append(
                    _failure(
                        symbol=symbol,
                        target_period_end=target_period_end,
                        baseline_period_end=baseline_period_end,
                        stage="FILING_FETCH",
                        reason=str(exc),
                        target_discovery_raw_sha256=target_discovery_sha,
                        baseline_discovery_raw_sha256=baseline_discovery_sha,
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
                        "T008 D003 target filing ISIN differs from frozen universe"
                    )
                if (
                    member.isin
                    and baseline_event.isin
                    and baseline_event.isin != member.isin
                ):
                    raise AlphaContractError(
                        "T008 D003 baseline filing ISIN differs from frozen universe"
                    )

                record = pair_record(
                    pair=pair,
                    target_event=target_event,
                    baseline_event=baseline_event,
                    discovery_raw_sha256=target_discovery_sha,
                    diagnostic_id=DIAGNOSTIC_ID,
                )
                if record["target_raw_sha256"] != target_sha:
                    raise AlphaContractError(
                        "T008 D003 target raw SHA mismatch"
                    )
                if record["baseline_raw_sha256"] != baseline_sha:
                    raise AlphaContractError(
                        "T008 D003 baseline raw SHA mismatch"
                    )
                record.pop("record_sha256", None)
                record["target_discovery_raw_sha256"] = target_discovery_sha
                record["baseline_discovery_raw_sha256"] = baseline_discovery_sha
                record["target_source_family"] = "NSE_INTEGRATED_FILING_FINANCIALS"
                record["baseline_source_family"] = "NSE_LEGACY_FINANCIAL_RESULTS"
                record["record_sha256"] = digest(record)
                records.append(record)
            except AlphaContractError as exc:
                failures.append(
                    _failure(
                        symbol=symbol,
                        target_period_end=target_period_end,
                        baseline_period_end=baseline_period_end,
                        stage="PARSE_OR_FEATURE",
                        reason=str(exc),
                        target_discovery_raw_sha256=target_discovery_sha,
                        baseline_discovery_raw_sha256=baseline_discovery_sha,
                    )
                )

    expected_attempt_count = len(universe.members) * len(PERIOD_PAIRS)
    if len(records) + len(failures) != expected_attempt_count:
        raise AlphaContractError(
            "T008 D003 coverage accounting does not equal frozen attempt count"
        )

    keys = [
        (record["target_period_end"], record["symbol"])
        for record in records
    ]
    if len(keys) != len(set(keys)):
        raise AlphaContractError(
            "T008 D003 duplicate target-period/symbol record"
        )

    complete_by_period: dict[str, int] = defaultdict(int)
    records_by_period: dict[str, int] = defaultdict(int)
    basis_by_period: dict[str, Counter] = defaultdict(Counter)
    parser_by_period: dict[str, Counter] = defaultdict(Counter)
    feature_coverage_by_period: dict[str, Counter] = defaultdict(Counter)

    for record in records:
        target_period = record["target_period_end"]
        records_by_period[target_period] += 1
        if record["all_six_features_complete"]:
            complete_by_period[target_period] += 1
        basis_by_period[target_period][record["accounting_basis"]] += 1
        parser_by_period[target_period][
            (
                f"{record['target_parser_version']}|"
                f"{record['baseline_parser_version']}"
            )
        ] += 1
        for feature in FEATURE_NAMES:
            if record["features"].get(feature) is not None:
                feature_coverage_by_period[target_period][feature] += 1

    failure_stage_counts = Counter(row["stage"] for row in failures)
    failure_reason_counts = Counter(row["reason"] for row in failures)
    failure_by_period: dict[str, Counter] = defaultdict(Counter)
    for row in failures:
        failure_by_period[row["target_period_end"]][row["stage"]] += 1

    per_period = {}
    for target_period_end, baseline_period_end in PERIOD_PAIRS:
        per_period[target_period_end] = {
            "baseline_period_end": baseline_period_end,
            "record_count": records_by_period[target_period_end],
            "complete_six_feature_count": complete_by_period[
                target_period_end
            ],
            "failure_count": sum(
                failure_by_period[target_period_end].values()
            ),
            "failure_stage_counts": dict(
                sorted(failure_by_period[target_period_end].items())
            ),
            "basis_counts": dict(
                sorted(basis_by_period[target_period_end].items())
            ),
            "parser_pair_counts": dict(
                sorted(parser_by_period[target_period_end].items())
            ),
            "feature_coverage": {
                name: int(
                    feature_coverage_by_period[target_period_end][name]
                )
                for name in FEATURE_NAMES
            },
            "passes_minimum_complete_rows": (
                complete_by_period[target_period_end]
                >= MIN_COMPLETE_PER_PERIOD
            ),
        }

    total_complete = sum(complete_by_period.values())
    feasibility_pass = (
        total_complete >= MIN_TOTAL_COMPLETE
        and all(
            details["passes_minimum_complete_rows"]
            for details in per_period.values()
        )
    )

    panel = {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "evidence_class": "HISTORICAL_SOURCE_FEASIBILITY_NO_RETURNS",
        "generated_at_utc": captured_at,
        "universe_sha256": universe.sha256,
        "universe_member_count": len(universe.members),
        "source_contract": {
            "target": "NSE_INTEGRATED_FILING_FINANCIALS",
            "baseline": "NSE_LEGACY_FINANCIAL_RESULTS",
        },
        "period_pairs": [
            {
                "target_period_end": target,
                "baseline_period_end": baseline,
            }
            for target, baseline in PERIOD_PAIRS
        ],
        "frozen_attempt_count": expected_attempt_count,
        "record_count": len(records),
        "complete_six_feature_count": total_complete,
        "failure_count": len(failures),
        "per_period": per_period,
        "failure_stage_counts": dict(sorted(failure_stage_counts.items())),
        "failure_reason_counts": dict(sorted(failure_reason_counts.items())),
        "feasibility_thresholds": {
            "minimum_complete_rows_per_target_period": (
                MIN_COMPLETE_PER_PERIOD
            ),
            "minimum_total_complete_rows": MIN_TOTAL_COMPLETE,
        },
        "feasibility_pass": feasibility_pass,
        "records": sorted(
            records,
            key=lambda row: (
                row["target_period_end"],
                row["symbol"],
            ),
        ),
        "failures": sorted(
            failures,
            key=lambda row: (
                row["target_period_end"],
                row["symbol"],
            ),
        ),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "t008-d003-panel.json").write_text(
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
