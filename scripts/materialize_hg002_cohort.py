from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg002_cohort import build_underwriting_cohort


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--router", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cohort = build_underwriting_cohort(_load(args.router))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            cohort,
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
                "cohort_id": cohort["cohort_id"],
                "cohort_sha256": cohort["cohort_sha256"],
                "cohort_count": cohort["cohort_count"],
                "l001_p1_validated_family_ready_count": (
                    cohort["l001_p1_validated_family_ready_count"]
                ),
                "l001_p1_unvalidated_family_counts": (
                    cohort["l001_p1_unvalidated_family_counts"]
                ),
                "liquidity_band_counts": cohort["liquidity_band_counts"],
                "symbols": [row["symbol"] for row in cohort["rows"]],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
