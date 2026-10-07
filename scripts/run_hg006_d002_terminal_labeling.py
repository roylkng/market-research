from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_terminal_labeling import build_terminal_label_panel


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threading", type=Path, required=True)
    parser.add_argument("--ingestion", type=Path, required=True)
    parser.add_argument("--evidence-pack", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    panel = build_terminal_label_panel(
        threading=_load(args.threading),
        ingestion=_load(args.ingestion),
        evidence_pack=_load(args.evidence_pack),
    )
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
                "label_panel_sha256": panel["label_panel_sha256"],
                "episode_count": panel["episode_count"],
                "primary_state_counts_by_family": panel[
                    "primary_state_counts_by_family"
                ],
                "warrant_full_exercise_state_counts": panel[
                    "warrant_full_exercise_state_counts"
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
