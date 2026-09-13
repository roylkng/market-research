from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h022_historical_universe import (
    load_rule,
    reconstruct_historical_membership,
    validate_reconstruction,
)


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build frozen H022 historical Nifty 200 membership reconstruction"
    )
    parser.add_argument("--rule", type=Path, required=True)
    parser.add_argument("--anchor-csv", type=Path, required=True)
    parser.add_argument("--current-u001", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args()

    rule = load_rule(args.rule.read_text(encoding="utf-8"))
    reconstruction = reconstruct_historical_membership(
        args.anchor_csv.read_bytes(),
        rule=rule,
        current_u001_payload=_load_json(args.current_u001),
    )
    validate_reconstruction(reconstruction)
    _write_json(args.out, reconstruction)

    summary = {
        "schema_version": 1,
        "rule_id": reconstruction["rule_id"],
        "reconstruction_sha256": reconstruction["reconstruction_sha256"],
        "anchor_as_of": reconstruction["anchor_as_of"],
        "anchor_raw_sha256": reconstruction["anchor_raw_sha256"],
        "anchor_member_count": reconstruction["anchor_member_count"],
        "pre_march_member_count": reconstruction["pre_march_member_count"],
        "expanded_union_member_count": reconstruction["expanded_union_member_count"],
        "current_u001_member_count": reconstruction["current_u001_member_count"],
        "current_u001_in_expanded_union_count": reconstruction[
            "current_u001_in_expanded_union_count"
        ],
        "expanded_union_additional_vs_current_u001_count": reconstruction[
            "expanded_union_additional_vs_current_u001_count"
        ],
        "ad_hoc_base_membership_audit_status": reconstruction[
            "ad_hoc_base_membership_audit_status"
        ],
        "historical_u001_reconstructed": False,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.summary_out, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
