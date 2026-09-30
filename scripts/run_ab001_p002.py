from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ab001_p002 import run_ab001_p002
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes


def _load_json_bytes(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload, raw


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


def _compact_report(report: dict) -> dict:
    return {
        key: value
        for key, value in report.items()
        if key != "session_metrics"
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen AB001 P002 H024 cross-family diagnostic"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--h024-event-panel", type=Path, required=True)
    parser.add_argument("--h024-source-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    features = load_canonical_gzip_json(args.feature_panel.read_bytes())
    actions = load_canonical_gzip_json(args.action_ledger.read_bytes())
    event_panel, event_bytes = _load_json_bytes(args.h024_event_panel)
    source_panel, source_bytes = _load_json_bytes(args.h024_source_panel)

    report = run_ab001_p002(
        market_panel=market,
        augmented_feature_panel=features,
        action_ledger=actions,
        h024_event_panel=event_panel,
        h024_source_panel=source_panel,
        h024_source_panel_raw_sha256=sha256_bytes(source_bytes),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "ab001-p002-report.json.gz").write_bytes(report_bytes)

    h024_diagnostics = {
        key: value
        for key, value in report["h024_event_diagnostics"].items()
        if key != "accepted_events"
    }
    event_lift = {
        key: value
        for key, value in report["h024_event_lift"].items()
        if key != "session_metrics"
    }
    incremental = report["incremental_h024_candidate"]
    summary = {
        "schema_version": 1,
        "pilot_id": report["pilot_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "evidence_class": report["evidence_class"],
        "horizon_sessions": report["horizon_sessions"],
        "historical_outcome_cutoff_session": report[
            "historical_outcome_cutoff_session"
        ],
        "input_hashes": report["input_hashes"],
        "h024_event_diagnostics": h024_diagnostics,
        "common_row_diagnostics": report["common_row_diagnostics"],
        "library": {
            "alpha_count": report["library"]["alpha_count"],
            "record_count": report["library"]["record_count"],
            "alphas": report["library"]["alphas"],
            "library_sha256": report["library"]["library_sha256"],
        },
        "standalone": {
            alpha: _compact_report(value)
            for alpha, value in report["standalone"].items()
        },
        "pairwise": report["pairwise"],
        "h024_event_lift": event_lift,
        "incremental_h024_candidate": {
            "existing_alpha_ids": incremental["existing_alpha_ids"],
            "candidate_alpha_id": incremental["candidate_alpha_id"],
            "horizon_sessions": incremental["horizon_sessions"],
            "baseline": _compact_report(incremental["baseline"]),
            "challenger": _compact_report(incremental["challenger"]),
            "challenger_minus_baseline_inference": incremental[
                "challenger_minus_baseline_inference"
            ],
        },
        "dynamic_blender_tested": report["dynamic_blender_tested"],
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
        "h024_event_panel_file_sha256": sha256_bytes(event_bytes),
        "h024_source_panel_file_sha256": sha256_bytes(source_bytes),
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
