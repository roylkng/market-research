"""Replay P006 XBRL cashflow components for all 100 source-pinned issuers."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from marketlab.l001_p006_cash_anomalies import cashflow_quality_context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p004-report", type=Path, required=True)
    parser.add_argument("--xml-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    p004 = json.loads(args.p004_report.read_text(encoding="utf-8"))
    sources = {}
    with zipfile.ZipFile(args.xml_zip) as archive:
        for item in p004["source_results"]:
            key = item["financial_sources"]["annual"]["raw_sha256"]
            sources[key] = archive.read(f"sha256/{key}.xml")
    report = cashflow_quality_context(p004, sources)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "company_count": report["company_count"],
        "pnc_noncurrent_receivables_cr": report["pnc_receivable_original_cr"],
        "pnc_cfo_no_receivables_sensitivity_cr": (
            report["pnc_cfo_excluding_one_component_sensitivity_cr"]
        ),
        "oil_investing_capex_taxonomy_caution": (
            report["oil_general_ppe_concept_zero_but_material_investing_outflow"]
        ),
        "investment_authorized": False,
        "report_sha256": report["report_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
