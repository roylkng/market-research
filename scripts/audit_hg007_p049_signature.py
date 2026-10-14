"""Materialize signed P049 v2 checksum discrepancy, leaving P049 v1 untouched."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_p049_signature_audit import (
    build_p049_signature_audit,
    validate_p049_signature_audit,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument(
        "--output", type=Path,
        default=Path("research/hg007/hg007-p049-legacy-signature-audit-v2.json"),
    )
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    audit = build_p049_signature_audit(args.repo_root)
    validate_p049_signature_audit(audit, args.repo_root)
    report = json.dumps(
        audit, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False,
    ) + "\n"
    path = args.repo_root / args.output
    if args.check:
        if not path.is_file() or path.read_text(encoding="utf-8") != report:
            raise SystemExit("P049 v2 signed original-source audit differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") != report:
            raise SystemExit("P049 v2 original audit cannot be overwritten")
        path.write_text(report, encoding="utf-8")
    print(json.dumps({
        "audit_id": audit["audit_id"],
        "legacy_self_sha_valid": audit[
            "legacy_packet_sha_claim_matches_current_digest"
        ],
        "original_git_blob_verified": True,
        "source_hash_sha256": audit["historical_original_raw_sha256"],
        "audit_sha256": audit["audit_sha256"],
        "status": "VERIFIED" if args.check else "MATERIALIZED",
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
