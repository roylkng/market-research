"""Independent all-100 Q1 annual other-income original replay."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from marketlab.l001_p007_earnings_components import q1_income_quality_context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p004-report", type=Path, required=True)
    parser.add_argument("--xml-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.p004_report.read_text(encoding="utf-8"))
    originals = {}
    with zipfile.ZipFile(args.xml_zip) as archive:
        for row in report["source_results"]:
            sha = row["financial_sources"]["quarter"]["raw_sha256"]
            originals[sha] = archive.read(f"sha256/{sha}.xml")
    result = q1_income_quality_context(report, originals)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "company_count": result["company_count"],
        "xbrl_original_quarters": result["original_quarter_xbrl_hashes_verified"],
        "original_numeric_cells": result["q1_numerical_cells_read_directly"],
        "high_other_income_triggers": (
            result["other_income_gte_50pct_pbt_diagnostic_non_nbfc_symbols"]
        ),
        "capital_authorized": False,
        "report_sha256": result["report_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
