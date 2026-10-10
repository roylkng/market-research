"""Run H021 original-ten corporate-action risk screening without opening returns.

Original official NSE raw response is optional. Missing source stays blocked.
This CLI neither downloads corporate-action data nor certifies adjustment factors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.h021_corporate_action_guard import (
    require_h021_price_basis_clearance,
    screen_h021_corporate_actions,
)
from marketlab.h021_first_entry_intent import (
    build_first_entry_intent,
    git_blob_sha,
    load_pinned_inputs,
)

INTENT_PATH = Path("research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json")
UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
PINNED_INTENT_BLOB = "e25f77e1c845456473e624899d4748e306b1225b"
PINNED_UNIVERSE_BLOB = "8026e81faee3e913d2fba1dba72d60603b69fa07"


def frozen_original_ten() -> dict[str, str]:
    comparison, calendar = load_pinned_inputs()
    if git_blob_sha(INTENT_PATH.read_bytes()) != PINNED_INTENT_BLOB:
        raise ValueError("first H021 intent original Git blob changed")
    intent = json.loads(INTENT_PATH.read_text(encoding="utf-8"))
    if intent != build_first_entry_intent(comparison, calendar):
        raise ValueError("first H021 intent does not reproduce")
    if git_blob_sha(UNIVERSE_PATH.read_bytes()) != PINNED_UNIVERSE_BLOB:
        raise ValueError("original U001 Git blob changed")
    universe = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    members = universe.get("members")
    if not isinstance(members, list) or len(members) != 100:
        raise ValueError("U001 symbol and ISIN table invalid")
    by_symbol = {row["symbol"]: row["isin"] for row in members}
    selected = intent["selected_observations"]
    if len(selected) != 10:
        raise ValueError("H021 selected-count drift")
    return {row["symbol"]: by_symbol[row["symbol"]] for row in selected}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval-start", default="2026-10-12")
    parser.add_argument("--interval-end", required=True)
    parser.add_argument("--raw-json", type=Path)
    parser.add_argument("--source-url")
    parser.add_argument("--captured-at-utc")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--require-return-clearance", action="store_true")
    args = parser.parse_args()
    if args.interval_start < "2026-10-12" or args.interval_end > "2026-12-31":
        parser.error("H021 P010 original calendar bound is Oct 12 to Dec 31, 2026")
    if args.raw_json is not None and (
        args.source_url is None or args.captured_at_utc is None
    ):
        parser.error("raw official response requires source URL and source UTC timestamp")
    if args.raw_json is None and (
        args.source_url is not None or args.captured_at_utc is not None
    ):
        parser.error("source metadata without original raw bytes is not admissible")

    raw = args.raw_json.read_bytes() if args.raw_json is not None else None
    receipt = None
    if raw is not None:
        receipt = {
            "url": args.source_url,
            "captured_at_utc": args.captured_at_utc,
            "status": "OK",
            "http_status": 200,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    report = screen_h021_corporate_actions(
        symbols_to_isins=frozen_original_ten(),
        interval_start=args.interval_start,
        interval_end=args.interval_end,
        raw_source=raw,
        source_receipt=receipt,
        prepared_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    if args.require_return_clearance:
        require_h021_price_basis_clearance(report)
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.out is None:
        print(encoded, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8")
        print(json.dumps({
            "audit_id": report["audit_id"],
            "source_state": report["source_state"],
            "corporate_event_hazard_count": report["corporate_event_hazard_count"],
            "unclassified_event_count": report["unclassified_event_count"],
            "return_outcomes_opened": False,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
