from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_d004_execution import build_d004_base_rates


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    panel = build_d004_base_rates(_load(args.labels))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
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
    print(
        json.dumps(
            {
                "base_rate_panel_sha256": panel["base_rate_panel_sha256"],
                "family_surfaces": [
                    {
                        "family": row["family"],
                        "track": row["track"],
                        "support_count": row["support_count"],
                        "completed_count": row["completed_count"],
                        "failed_count": row["failed_count"],
                        "right_censored_count": row["right_censored_count"],
                        "conflict_excluded_count": row["conflict_excluded_count"],
                        "publication_state": row["publication_state"],
                        "supported_horizons": row["supported_horizons"],
                    }
                    for row in panel["family_surfaces"]
                ],
                "publishable_stage_surfaces": [
                    {
                        "family": row["family"],
                        "track": row["track"],
                        "stage": row["stage"],
                        "support_count": row["support_count"],
                        "terminal_count": row["terminal_count"],
                        "supported_horizons": row["supported_horizons"],
                    }
                    for row in panel["stage_surfaces"]
                    if row["publication_state"]
                    == "PUBLISHABLE_HISTORICAL_BASE_RATE"
                ],
                "threshold_passes": panel["threshold_passes"],
                "feasibility_pass": panel["feasibility_pass"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
