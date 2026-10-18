"""Rebuild 100 FY26 intangible cash purchases from original P004 archive."""

from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path

from marketlab.l001_p014_intangible_cash import audit_original_intangibles

P004_ARTIFACT_ID = 12111414537


def materialize(archive_path: Path) -> dict:
    with zipfile.ZipFile(archive_path) as outer:
        original_p004 = json.loads(outer.read("l001-p004-all100-original-audit.json"))
        inner_data = outer.read("l001-p004-original-300-source-files.zip")
    required = {
        r["financial_sources"]["annual"]["raw_sha256"]
        for r in original_p004["source_results"]
    }
    with zipfile.ZipFile(io.BytesIO(inner_data)) as originals:
        annual = {
            sha: originals.read(f"sha256/{sha}.xml") for sha in sorted(required)
        }
    return audit_original_intangibles(original_p004, annual)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = materialize(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "verified_original_annual_xbrl": report["annual_xml_sha256_reverified_count"],
        "intangible_fact_count": report[
            "annual_original_exact_xbrl_intangible_cells_replayed"
        ],
        "positive_tagged_intangible_outflows": report[
            "positive_tagged_intangible_purchase_count"
        ],
        "sun_tv_intangibles_cr": report[
            "sun_tv_original_intangible_cash_purchase_cr"
        ],
        "input_source_artifact": P004_ARTIFACT_ID,
        "report_sha256": report["report_sha256"],
        "investable": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
