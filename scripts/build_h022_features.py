from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h022 import build_feature_panel, validate_feature_panel


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the frozen H022 feature panel without price or return inputs"
    )
    parser.add_argument("--candidate-report", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", required=True)
    args = parser.parse_args()

    document = json.loads(Path(args.candidate_report).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError("candidate report must be a JSON object")

    panel = build_feature_panel(document)
    validate_feature_panel(panel)
    _write(Path(args.out), panel)
    _write(
        Path(args.summary_out),
        {
            "schema_version": panel["schema_version"],
            "hypothesis_id": panel["hypothesis_id"],
            "feature_version": panel["feature_version"],
            "source_report_sha256": panel["source_report_sha256"],
            "universe_bias": panel["universe_bias"],
            "outcome_data_attached": panel["outcome_data_attached"],
            "record_count": panel["record_count"],
            "signal_count": panel["signal_count"],
            "no_prior_count": panel["no_prior_count"],
            "ambiguous_prior_count": panel["ambiguous_prior_count"],
            "design_signal_count": panel["design_signal_count"],
            "challenge_signal_count": panel["challenge_signal_count"],
            "panel_sha256": panel["panel_sha256"],
        },
    )


if __name__ == "__main__":
    main()
