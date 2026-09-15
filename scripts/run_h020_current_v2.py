from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from marketlab.timing_v2 import compute_snapshot_v2
from run_h020_current import _canonical_hash, fetch_yahoo_history


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# H020-v2 adverse-shock challenger current screen",
        "",
        f"As-of cutoff: **{report['as_of']}**",
        "",
        "**DESIGN CASE ONLY FOR 2026-09-15. NOT VALIDATION. LIVE CAPITAL DISABLED.**",
        "",
        "| Symbol | v1 action | v2 action | 1d | Rel 1d | Threshold | Shock |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in report["results"]:
        if row.get("action") == "BLOCKED_DATA":
            lines.append(
                f"| {row['symbol']} | {row.get('v1_action_before_shock_guard', '')} | BLOCKED_DATA | | | | |"
            )
            continue
        lines.append(
            "| {symbol} | {v1} | {v2} | {r1:.2f}% | {rel1:.2f}pp | {threshold:.2f}pp | {shock} |".format(
                symbol=row["symbol"],
                v1=row["v1_action_before_shock_guard"],
                v2=row["action"],
                r1=row["return_1d_pct"],
                rel1=row["relative_1d_pp"],
                threshold=row["adverse_shock_threshold_pp"],
                shock="YES" if row["flags"]["adverse_relative_shock_v2"] else "no",
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    config = yaml.safe_load(args.candidates.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.out_dir / "raw"
    benchmark_ticker = config["benchmark_ticker"]
    benchmark, benchmark_source = fetch_yahoo_history(
        benchmark_ticker, args.as_of, raw_dir
    )

    results: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {"benchmark": benchmark_source, "stocks": {}}
    for item in config["candidates"]:
        symbol = item["symbol"]
        try:
            frame, source = fetch_yahoo_history(item["ticker"], args.as_of, raw_dir)
            row = compute_snapshot_v2(
                frame,
                benchmark,
                symbol=symbol,
                design_influenced=True,
            )
            provenance["stocks"][symbol] = source
        except Exception as exc:  # noqa: BLE001
            row = {
                "symbol": symbol,
                "action": "BLOCKED_DATA",
                "reason": f"{type(exc).__name__}: {exc}",
                "design_influenced": True,
            }
        row["ticker"] = item["ticker"]
        row["business_lens"] = item["business_lens"]
        results.append(row)

    results.sort(
        key=lambda row: (
            0 if row.get("v1_action_before_shock_guard", "").startswith("PAPER_ENTRY_ELIGIBLE") else 1,
            -(row.get("timing_score_0_100_not_probability") or -1),
            row["symbol"],
        )
    )
    report = {
        "schema_version": 1,
        "hypothesis_id": "H020-V2-ADVERSE-SHOCK-1",
        "run_kind": "DESIGN_INFLUENCED_CHALLENGER_SCREEN",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "as_of": args.as_of,
        "benchmark": benchmark_ticker,
        "candidate_config_sha256": hashlib.sha256(args.candidates.read_bytes()).hexdigest(),
        "design_case_excluded_from_validation": True,
        "live_capital_allowed": False,
        "results": results,
        "provenance": provenance,
    }
    report["report_sha256"] = _canonical_hash(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )
    (args.out_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown = _markdown(report)
    (args.out_dir / "report.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
