"""Reproduce all-100 post-hoc economic screening diagnostics from original snapshots."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from marketlab.l001_p008_crossplane import crossplane_diagnostic

ROOT = Path(__file__).resolve().parents[1]
PRICE = ROOT / "research/hg009/daily/2026-10-15-v1.json"
FILES = {
    "p004": (12111414537, "l001-p004-all100-original-audit.json"),
    "p005": (12112413274, "l001-p005-accounting-format-100.json"),
    "p006": (12112643045, "l001-p006-original-cash-anomalies-100.json"),
    "p007": (12112967877, "l001-p007-original-q1-other-income-100.json"),
}


def materialize(artifact_directory: Path) -> dict:
    documents = {}
    for role, (artifact, filename) in FILES.items():
        path = artifact_directory / f"github-actions-artifact-{artifact}.zip"
        with zipfile.ZipFile(path) as archive:
            documents[role] = json.loads(archive.read(filename))
    daily = json.loads(PRICE.read_text(encoding="utf-8"))
    return crossplane_diagnostic(
        documents["p004"], documents["p005"],
        documents["p006"], documents["p007"], daily,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = materialize(args.artifact_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "count": report["source_cohort_count"],
        "historical_close_available": report["historical_priced_company_count"],
        "historical_basic_denominator": report["basic_price_share_denominator_ready_count"],
        "consolidated_source_scope_non_nbfc_ratios": (
            report["strictly_comparable_indas_non_nbfc_ratio_count"]
        ),
        "nbfc_specialist_required": report["reported_nbfc_form_cautions"],
        "report_sha256": report["report_sha256"],
        "investment_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
