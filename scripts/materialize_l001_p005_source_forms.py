"""Evaluate verified original NSE accounting form without sector inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.l001_p005_source_form_gate import classify_financial_reporting_scope


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p004-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = classify_financial_reporting_scope(
        json.loads(args.p004_source.read_text(encoding="utf-8"))
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "source_issuer_count": report["cohort_count"],
        "nbfc_source_forms": report["nbfc_financial_accounting_forms"],
        "nbfc_source_symbols": report["nbfc_financial_accounting_form_symbols"],
        "other_source_forms_not_sector_proof": report["general_indas_forms_unclassified_industry"],
        "valuation_ready": report["sector_specific_owner_cash_ready"],
        "report_sha256": report["report_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
