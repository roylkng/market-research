"""Replay P015 cash investing concepts from original pinned 100-company XBRL."""

from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path

from marketlab.l001_p015_investing_taxonomy import audit_investing_taxonomy

PINNED_P004_ARCHIVE_ID = 12111414537


def materialize_from_original_p004_archive(archive_path: Path) -> dict:
    with zipfile.ZipFile(archive_path) as outer:
        original_report = json.loads(
            outer.read("l001-p004-all100-original-audit.json")
        )
        raw_files = outer.read("l001-p004-original-300-source-files.zip")
    expected = {
        row["financial_sources"]["annual"]["raw_sha256"]
        for row in original_report["source_results"]
    }
    with zipfile.ZipFile(io.BytesIO(raw_files)) as inner:
        originals = {
            sha: inner.read(f"sha256/{sha}.xml")
            for sha in sorted(expected)
        }
    return audit_investing_taxonomy(original_report, originals)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = materialize_from_original_p004_archive(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "result": result["report_id"],
        "original_artifact": PINNED_P004_ARCHIVE_ID,
        "original_100_xml": result["original_annual_xml_rehashed"],
        "issuers_with_nonzero_additional_investing_concepts": result[
            "companies_with_additional_nonzero_investing_concepts"
        ],
        "issuers_with_purchase_candidate_exceeding_simple_proxy": len(
            result["positive_other_investing_purchase_exceeds_abs_cfo_less_ppe_symbols"]
        ),
        "issuer_with_falsified_owner_cash": "SUNTV",
        "report_sha256": result["report_sha256"],
        "capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
