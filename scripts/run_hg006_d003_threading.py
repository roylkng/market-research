from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_d003_generator import build_deterministic_episode_threading


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingestion", type=Path, required=True)
    parser.add_argument("--evidence-pack", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = build_deterministic_episode_threading(
        ingestion=_load(args.ingestion),
        evidence_pack=_load(args.evidence_pack),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "threading_sha256": result["threading_sha256"],
                "episode_count": result["episode_count"],
                "episode_assigned_event_count": result[
                    "episode_assigned_event_count"
                ],
                "thread_ambiguous_event_count": result[
                    "thread_ambiguous_event_count"
                ],
                "episode_counts_by_family": result[
                    "episode_counts_by_family"
                ],
                "threshold_passes": result["threshold_passes"],
                "feasibility_pass": result["feasibility_pass"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
