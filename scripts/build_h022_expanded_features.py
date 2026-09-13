from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h022_expanded_features import (
    build_expanded_feature_panel,
    validate_expanded_feature_panel,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build outcome-free expanded H022 feature panel")
    parser.add_argument("--candidate-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.candidate_report.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise TypeError("expanded candidate report must be a JSON object")
    panel = build_expanded_feature_panel(report)
    validate_expanded_feature_panel(panel)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(panel, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary = {
        "schema_version": 1,
        "hypothesis_id": panel["hypothesis_id"],
        "feature_rule_id": panel["feature_rule_id"],
        "feature_version": panel["feature_version"],
        "source_report_sha256": panel["source_report_sha256"],
        "record_count": panel["record_count"],
        "feature_signal_count": panel["feature_signal_count"],
        "challenge_evaluation_signal_count": panel[
            "challenge_evaluation_signal_count"
        ],
        "no_prior_count": panel["no_prior_count"],
        "ambiguous_prior_count": panel["ambiguous_prior_count"],
        "panel_sha256": panel["panel_sha256"],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
