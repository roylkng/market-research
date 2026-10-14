"""Independently replay HG009 daily observations from H021 original NSE bytes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.hg009_controls import load_hg009_inputs
from marketlab.hg009_daily import (
    H021_SOURCE_DIR,
    build_hg009_daily_source_observation,
    validate_hg009_daily_snapshot,
)
from marketlab.hg009_daily_io import (
    CALENDAR,
    CONTROL,
    DAILY_OUTPUT,
    load_json_source as _load_json,
    original_source_bytes as _original_raw,
)


def verify_daily_observations(
    root: Path,
    *,
    calendar_path: Path = CALENDAR,
    controls_path: Path = CONTROL,
    directory: Path = DAILY_OUTPUT,
) -> dict:
    calendar = load_calendar_snapshot(root / calendar_path)
    router, selected = load_hg009_inputs(root)
    controls = _load_json(root / controls_path)
    verified = []
    for path in sorted((root / directory).glob("????-??-??-v1.json")):
        recorded = _load_json(path)
        validate_hg009_daily_snapshot(recorded)
        day = recorded["date_ist"]
        if path.name != f"{day}-v1.json":
            raise AlphaContractError("HG009 original date filename drift")
        h021_path = root / H021_SOURCE_DIR / f"{day}-v1.json"
        if str(H021_SOURCE_DIR / f"{day}-v1.json") != recorded[
            "h021_original_daily_packet_path"
        ]:
            raise AlphaContractError("HG009 H021 source path reference differs")
        h021 = _load_json(h021_path)
        raw_udiff = _original_raw(
            root, h021["stock_source"], suffix=".zip"
        )
        raw_index = _original_raw(
            root, h021["index_source"], suffix=".csv"
        )
        reproduced = build_hg009_daily_source_observation(
            h021_observation=h021,
            original_udiff_zip=raw_udiff,
            original_index_csv=raw_index,
            selected_manifest=selected,
            controls_manifest=controls,
            original_router=router,
            calendar=calendar,
            recorded_at_utc=recorded["observed_recorded_at_utc"],
        )
        if reproduced != recorded:
            raise AlphaContractError(
                f"HG009 original market-data observation not replayable for {day}"
            )
        verified.append({
            "session_date": day,
            "source_sha256": recorded["h021_original_daily_packet_sha256"],
            "observation_sha256": recorded["packet_sha256"],
            "source_full_market_rows": recorded[
                "original_EQ_market_universe_row_count"
            ],
            "selected_observed_eq": recorded["arm_coverage"][
                "SELECTED"
            ]["observed_official_eq"],
            "one_lane_observed_eq": recorded["arm_coverage"][
                "ONE_LANE"
            ]["observed_official_eq"],
            "zero_lane_observed_eq": recorded["arm_coverage"][
                "ZERO_LANE"
            ]["observed_official_eq"],
        })
    return {
        "schema_version": 1,
        "state": (
            "VERIFIED_ORIGINAL_NSE_REPLAY"
            if verified else "NO_PROSPECTIVE_MARKET_SOURCE_YET"
        ),
        "count": len(verified),
        "verified": verified,
        "no_stock_returns_scored": True,
        "live_capital_allowed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    args = p.parse_args()
    print(json.dumps(verify_daily_observations(args.repo_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
