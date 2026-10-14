"""Attest archived NSE issuer original financial cells and units.

Never overwrite the permanent source bytes or P003/P049 historical reports.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p010_filing_attestation import (
    build_p010_evidence,
    validate_p010_evidence,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument(
        "--output",
        type=Path,
        default=Path(
            "research/hg009/hg009-p010-original-issuer-financial-replay-v1.json"
        ),
    )
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    report = build_p010_evidence(args.repo_root)
    validate_p010_evidence(report, root=args.repo_root)
    serialized = json.dumps(
        report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    target = args.repo_root / args.output
    if args.check:
        if not target.exists() or target.read_text("utf-8") != serialized:
            raise SystemExit("P010 source attestation not equal to pinned report")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_text("utf-8") != serialized:
            raise SystemExit("P010 cannot rewrite prior issuer source attestation")
        target.write_text(serialized, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "ORIGINAL_SOURCE_REPORT_MATERIALIZED",
        "audited_source_documents": report["original_document_count"],
        "original_archived": report["archive_verified_document_count"],
        "source_rows_text_verified": report["all_versions_textually_verified_count"],
        "source_version_states": {
            row["document_id"]: row["state"] for row in report["source_documents"]
        },
        "packet_sha256": report["packet_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
