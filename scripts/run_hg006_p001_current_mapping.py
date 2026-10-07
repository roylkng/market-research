from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_p001_current_mapping import build_p001_current_mapping


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hg004-d001", type=Path, required=True)
    parser.add_argument("--hg004-l001", type=Path, required=True)
    parser.add_argument("--hg004-l002", type=Path, required=True)
    parser.add_argument("--hg006-d004", type=Path, required=True)
    parser.add_argument("--hg006-labels", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = build_p001_current_mapping(
        d001_selection=_load(args.hg004_d001),
        l001_run=_load(args.hg004_l001),
        l002_synthesis=_load(args.hg004_l002),
        d004_panel=_load(args.hg006_d004),
        historical_labels=_load(args.hg006_labels),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "mapping_sha256": result["mapping_sha256"],
                "case_count": result["case_count"],
                "mapping_state_counts": result["mapping_state_counts"],
                "current_company_probability_surfaces_published": result[
                    "current_company_probability_surfaces_published"
                ],
                "current_terminal_state_count": result[
                    "current_terminal_state_count"
                ],
                "cases": result["cases"],
                "promotion_allowed_to_probability_weighted_payoff": result[
                    "promotion_allowed_to_probability_weighted_payoff"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
