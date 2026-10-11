from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.hg007_anantraj_scheme_terms import (
    AUDIT_ID,
    CLAUSES,
    LOOKTHROUGH_BLOB,
    LOOKTHROUGH_PATH,
    PAGE_DIR,
    build_source_clause_review,
)


def test_exact_48_pages_and_conditional_ownership_terms() -> None:
    audit = build_source_clause_review(Path("."))
    assert audit["review_id"] == AUDIT_ID
    assert audit["all_48_original_page_hashes_verified"] is True
    assert audit["reviewed_specific_legal_clause_count"] == len(CLAUSES)
    assert audit["source_conditional_parent_direct_ownership"]["git_blob_sha"] == LOOKTHROUGH_BLOB
    assert len({row["clause_id"] for row in audit["reviewed_clauses"]}) == len(CLAUSES)
    assert audit["conditional_capital_reconciliation"][
        "newco_authorized_ordinary_share_capacity_in_draft"
    ] == 734_449_483
    assert audit["conditional_capital_reconciliation"][
        "illustrative_existing_parent_newco_shares"
    ] == 374_572_553
    assert audit["conditional_capital_reconciliation"][
        "illustrative_eligible_ARL_newco_entitlement_proxy_shares"
    ] == 359_876_930
    assert audit["conditional_capital_reconciliation"][
        "actual_future_newco_issued_shares_verified"
    ] is False


def test_source_qualitative_findings_not_transferred_debt_amounts() -> None:
    audit = build_source_clause_review(Path("."))
    clauses = {row["clause_id"]: row for row in audit["reviewed_clauses"]}
    assert clauses["GENERAL_PURPOSE_BORROWINGS_PRO_RATA"]["source_pdf_page"] == 8
    assert clauses["EARMARKED_DEVELOPMENT_QIP_FUNDS"]["source_pdf_page"] == 7
    assert clauses["PARENT_RESULTANT_INTERCOMPANY_ELIMINATION"]["source_pdf_page"] == 31
    assert clauses["ENTITLEMENT_RATIO_CAN_CHANGE"]["source_pdf_page"] == 37
    assert clauses["LEGAL_EXCHANGE_AND_HOLDER_APPROVALS"]["source_pdf_page"] == 45
    assert clauses["TRIBUNAL_AND_ROC_NONCOMPLETION_GATE"]["source_pdf_page"] == 46
    assert clauses["SPECIFIC_IMMOVABLE_LOCATIONS"]["source_pdf_page"] == 48
    missing = audit["unquantified_core_underwriting_inputs"]
    assert len(missing) >= 9
    assert all(value is None for value in missing.values())
    assert audit["scheme_asset_allocation_is_quantified_in_this_audit"] is False
    assert audit["actual_cloud_equity_fair_value_calculated"] is False
    assert audit["scheme_legal_approval_and_effective_date_verified"] is False
    assert audit["equity_expected_returns_calculated"] is False
    assert audit["portfolio_eligibility_allowed"] is False
    assert audit["live_capital_allowed"] is False


def test_original_page_tamper_fails_closed(tmp_path: Path) -> None:
    from marketlab.hg007_anantraj_scheme_pages import PDF_SHA256

    root = tmp_path
    copied = PAGE_DIR / "page-index-v1.json"
    (root / copied).parent.mkdir(parents=True, exist_ok=True)
    (root / copied).write_bytes(copied.read_bytes())
    for n in range(1, 49):
        original = PAGE_DIR / f"original-page-{n:02d}.txt"
        dest = root / original
        dest.write_bytes(original.read_bytes())
    ownership_dst = root / LOOKTHROUGH_PATH
    ownership_dst.parent.mkdir(parents=True, exist_ok=True)
    ownership_dst.write_bytes(LOOKTHROUGH_PATH.read_bytes())
    assert build_source_clause_review(root)["original_scheme_pdf_sha256"] == PDF_SHA256
    altered = root / PAGE_DIR / "original-page-08.txt"
    altered.write_bytes(altered.read_bytes() + b"SCHEME FREE OF ALL DEBTS")
    with pytest.raises(ValueError, match="page 8 is not SHA-verified"):
        build_source_clause_review(root)


def test_original_ownership_proxy_not_upgraded_to_actual_record_date(
    tmp_path: Path,
) -> None:
    audit = build_source_clause_review(Path("."))
    assert audit["conditional_capital_reconciliation"][
        "record_date_basic_eligible_shares_verified"
    ] is False
    assert audit["conditional_capital_reconciliation"][
        "ratio_not_subject_to_later_adjustment_verified"
    ] is False
    output = tmp_path / "source-terms.json"
    args = [
        sys.executable,
        "scripts/audit_hg007_anantraj_scheme_terms.py",
        "--out",
        str(output),
    ]
    process = subprocess.run(args, check=True, capture_output=True, text=True)
    assert json.loads(process.stdout)["capital_or_returns_authorized"] is False
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == audit
    subprocess.run(
        args + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    output.write_text(output.read_text(encoding="utf-8") + "\nCHANGED", encoding="utf-8")
    failure = subprocess.run(
        args + ["--verify-existing"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert failure.returncode != 0
    assert "was modified" in failure.stderr
