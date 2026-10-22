"""Seal H021's 20-session Muhurat calendar amendment from HG009 original NSE PDF.

This neither modifies the October 9 H021 selection nor opens a November
return. The earlier H021 P006 blocked record remains immutable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_first_entry_intent import CALENDAR_PATH, git_blob_sha
from marketlab.h021_muhurat_amendment import (
    build_h021_muhurat_calendar_amendment,
    validate_h021_muhurat_amendment,
    verified_h021_20_calendar_date_only,
)
from marketlab.hg009_p004_a1_muhurat import (
    AMENDMENT_PATH,
    validate_amendment,
)
from scripts.check_h021_horizon_readiness import load_first_intent

HG009_CALENDAR_AMENDMENT_BLOB_SHA = "ff2bc35970ed73d219bb4b26a9160a37b4947415"
HG009_RECEIPT_PATH = Path("research/hg009/p004-a1/originals/attempts/39473770080-1.json")
HG009_RECEIPT_BLOB_SHA = "d90269ab889be329e08f196b74eddbc6dc6408df"


def load_h021_source_clock() -> dict:
    root = Path(".")
    raw_amendment = AMENDMENT_PATH.read_bytes()
    raw_receipt = HG009_RECEIPT_PATH.read_bytes()
    if (
        git_blob_sha(raw_amendment) != HG009_CALENDAR_AMENDMENT_BLOB_SHA
        or git_blob_sha(raw_receipt) != HG009_RECEIPT_BLOB_SHA
    ):
        raise ValueError("original NSE Muhurat circular custody inputs drifted")
    hg009_amendment = json.loads(raw_amendment)
    # Replay original PDF and prior 300-company HG009 clock.
    validate_amendment(
        hg009_amendment, root=root, receipt_path=HG009_RECEIPT_PATH
    )
    original_calendar = load_calendar_snapshot(CALENDAR_PATH)
    original_intent = load_first_intent()
    packet = build_h021_muhurat_calendar_amendment(
        original_intent, original_calendar, hg009_amendment
    )
    validate_h021_muhurat_amendment(packet)
    return packet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--require-20-calendar-date", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    result = load_h021_source_clock()
    if args.require_20_calendar_date:
        verified_h021_20_calendar_date_only(result)
    encoded = json.dumps(
        result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("verified original NSE H021 calendar source packet differs")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as target:
                target.write(encoded)
    print(json.dumps({
        "amendment_id": result["amendment_id"],
        "verified_H021_H20_date": result["H021_20_completed_sessions_calendar_exit_ist"],
        "H021_H60_calendar_verified": result["H021_60_official_2027_calendar_verified"],
        "minimum_verified_2027_sessions_still_required":
            result["H021_60_minimum_2027_additional_sessions"],
        "return_outcomes_opened": result["h021_forward_return_outcomes_opened"],
        "live_capital_allowed": result["live_capital_allowed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
