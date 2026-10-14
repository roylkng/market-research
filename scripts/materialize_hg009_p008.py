"""Create/replay ten source-bound underwriting dossiers without stock predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p008_underwriting import materialize, validate_packet


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument(
        "--output",
        type=Path,
        default=Path("research/hg009/hg009-p008-ten-underwriting-evidence-v1.json"),
    )
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    report = materialize(args.repo_root)
    validate_packet(report, args.repo_root)
    raw = json.dumps(
        report, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False,
    ) + "\n"
    target = args.repo_root / args.output
    if args.check:
        if not target.is_file() or target.read_text("utf-8") != raw:
            raise SystemExit("P008 evidence matrix differs from frozen original")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_text("utf-8") != raw:
            raise SystemExit("P008 cannot silently overwrite an original dossier")
        target.write_text(raw, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "packet_sha256": report["packet_sha256"],
        "cases": report["company_count"],
        "new_audited_fy26_filing_cases": (
            report["original_consolidated_fy26_new_issuer_cash_pilots"]
        ),
        "fully_underwritten": report["fully_underwritten_equity_valuations_count"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
