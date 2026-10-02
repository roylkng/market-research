from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.rm001_c001 import run_rm001_c001


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen RM001 C001 historical OOS risk calibration"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--size-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    market_bytes = args.market_panel.read_bytes()
    feature_bytes = args.feature_panel.read_bytes()
    action_bytes = args.action_ledger.read_bytes()
    size_bytes = args.size_panel.read_bytes()

    market = load_canonical_gzip_json(market_bytes)
    features = load_canonical_gzip_json(feature_bytes)
    actions = load_canonical_gzip_json(action_bytes)
    sizes = load_canonical_gzip_json(size_bytes)

    report = run_rm001_c001(
        market_panel=market,
        feature_panel=features,
        action_ledger=actions,
        size_panel=sizes,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "rm001-c001-report.json.gz").write_bytes(report_bytes)

    summary = {
        "schema_version": 1,
        "study_id": report["study_id"],
        "status": report["status"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "candidate_window": report["candidate_window"],
        "candidate_date_count": report["candidate_date_count"],
        "evaluated_date_count": report["evaluated_date_count"],
        "minimum_evaluated_date_count": report[
            "minimum_evaluated_date_count"
        ],
        "minimum_valid_probes_per_date": report[
            "minimum_valid_probes_per_date"
        ],
        "probe_count_per_ready_date": report[
            "probe_count_per_ready_date"
        ],
        "models": report["models"],
        "paired_date_level_inference": report[
            "paired_date_level_inference"
        ],
        "skipped_date_count": len(report["skipped_dates"]),
        "source": report["source"],
        "interpretation_limits": report["interpretation_limits"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
