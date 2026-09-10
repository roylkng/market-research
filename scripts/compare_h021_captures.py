from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from marketlab.h021 import compare_snapshots, validate_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    prior = json.loads(args.prior.read_text(encoding="utf-8"))
    current = json.loads(args.current.read_text(encoding="utf-8"))

    errors = {
        "prior": validate_snapshot(prior),
        "current": validate_snapshot(current),
    }
    if errors["prior"] or errors["current"]:
        raise SystemExit(json.dumps(errors, indent=2, sort_keys=True))

    revisions = [asdict(row) for row in compare_snapshots(prior, current)]
    output = {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "prior_capture_date_ist": prior["capture_date_ist"],
        "current_capture_date_ist": current["capture_date_ist"],
        "primary_signal": "30-day same-period consensus EPS revision",
        "primary_signal_available_count": sum(
            int(row["primary_signal_available"]) for row in revisions
        ),
        "revision_observations": revisions,
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"compared={len(revisions)} "
        f"primary_available={output['primary_signal_available_count']} "
        f"prior={prior['capture_date_ist']} current={current['capture_date_ist']}"
    )


if __name__ == "__main__":
    main()
