"""Rebuild a signed three-issuer NSE original-filing attestation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p009_attestation import (
    build_original_attestation,
    validate_original_attestation,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/hg009/hg009-p009-original-fy26-attestation-v1.json"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build_original_attestation(args.repo_root)
    validate_original_attestation(result, root=args.repo_root)
    content = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    path = args.repo_root / args.output
    if args.check:
        if not path.is_file() or path.read_text("utf-8") != content:
            raise SystemExit("P009 signed issuer attestation changed or missing")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.read_text("utf-8") != content:
            raise SystemExit("P009 cannot rewrite previous original source attestation")
        path.write_text(content, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "issuers": result["issuer_byte_attestation_successful_count"],
        "replayed_fields": result["original_statement_financial_fields_replayed_count"],
        "attestation_sha256": result["attestation_sha256"],
        "completed_valuations": result["risk_adjusted_expected_return_valuations_complete"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
