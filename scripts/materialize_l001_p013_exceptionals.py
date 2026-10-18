"""Reproduce original P007 100-company exceptional-item profit diagnostics."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from marketlab.l001_p013_exceptional_earnings import analyze_exceptional_original


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p007-artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.p007_artifact) as archive:
        original = json.loads(archive.read(
            "l001-p007-original-q1-other-income-100.json"
        ))
    result = analyze_exceptional_original(original)
    if (
        result["nonzero_exceptional_count"] != 7
        or result["material_positive_exceptional_gt_half_pbt_symbols"]
        != ["MINDACORP", "MMFL"]
    ):
        raise SystemExit("P013 full original exceptional-item counts changed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "original_source_count": result["issuer_count"],
        "nonzero_exceptional_count": result["nonzero_exceptional_count"],
        "material_positive_exceptional": (
            result["material_positive_exceptional_gt_half_pbt_symbols"]
        ),
        "report_sha256": result["report_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
