from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss001_share_review_queue import build_share_change_packets


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"D007 source must be JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d006-review", type=Path, required=True)
    parser.add_argument("--p2-census", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = build_share_change_packets(
        d006_review=_load(args.d006_review),
        p2_census=_load(args.p2_census),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss001-d007-source-packets.json").write_text(
        json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (args.output / "ss001-d007-pilot-first50.json").write_text(
        json.dumps(
            {
                "queue_id": output["queue_id"],
                "source_queue_sha256": output["queue_sha256"],
                "packet_count": 50,
                "packets": output["packets"][:50],
                "share_action_clearance_proven": False,
                "market_capitalization_calculated": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )
    summary = {k: v for k, v in output.items() if k != "packets"}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
