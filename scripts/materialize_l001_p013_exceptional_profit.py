"""Independently replay 100 original Q1FY27 exceptional/PBT XBRL facts."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from marketlab.l001_p013_exceptional_profit import exceptional_profit_replay


def replay(p004: Path, p007: Path, original_pack: Path) -> dict:
    audited = json.loads(p004.read_text(encoding="utf-8"))
    q1 = json.loads(p007.read_text(encoding="utf-8"))
    source_docs: dict[str, bytes] = {}
    with zipfile.ZipFile(original_pack) as archive:
        for original in audited["source_results"]:
            sha = original["financial_sources"]["quarter"]["raw_sha256"]
            source_docs[sha] = archive.read(f"sha256/{sha}.xml")
    return exceptional_profit_replay(audited, q1, source_docs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p004-report", type=Path, required=True)
    parser.add_argument("--p007-report", type=Path, required=True)
    parser.add_argument("--xml-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = replay(args.p004_report, args.p007_report, args.xml_zip)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "original_filing_count": report["original_company_count"],
        "xbrl_source_replays": report["original_q1_sha256_files_reopened_and_replayed"],
        "original_q1_numeric_facts": report["original_quarterly_numeric_facts_replayed"],
        "positive_exceptional": report["positive_exceptional_count"],
        "negative_exceptional": report["negative_exceptional_count"],
        "zero_exceptional": report["zero_exceptional_count"],
        "major_positive_exceptional": report[
            "major_positive_exceptional_over_half_pbt_symbols_posthoc"
        ],
        "report_sha256": report["report_sha256"],
        "investment_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
