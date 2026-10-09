from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss001_d007_a003 import (
    LEDGER_ID,
    build_independent_review_ledger,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"A003 input must be a JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize fail-closed SS001-D007-A003 independent review ledger"
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--initialize-annotations",
        action="store_true",
        help="Write an empty, non-attested reviewer annotation template only",
    )
    args = parser.parse_args()

    packet = _load(args.packet)
    if args.initialize_annotations:
        if args.annotations is not None:
            parser.error("--initialize-annotations cannot be combined with --annotations")
        annotations = {
            "schema_version": 1,
            "audit_id": LEDGER_ID,
            "source_packet_sha256": packet.get("packet_sha256"),
            "reviews": [],
        }
    else:
        if args.annotations is None:
            parser.error("--annotations required unless --initialize-annotations")
        annotations = _load(args.annotations)

    ledger = build_independent_review_ledger(packet, annotations)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(ledger, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )

    if args.initialize_annotations:
        template_path = args.out.with_name("ss001-a003-review-annotations-template.json")
        template_path.write_text(
            json.dumps(annotations, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(json.dumps({
        "reviewer_recorded_status": ledger["reviewer_recorded_status"],
        "selected_page_count": ledger["selected_page_count"],
        "reviewed_page_count": ledger["reviewed_page_count"],
        "missing_inference_page_count": ledger["missing_inference_page_count"],
        "independent_semantic_audit_complete": False,
        "share_action_clearance_proven": False,
        "portfolio_eligibility_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
