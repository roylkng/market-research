from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_entry_observation import EXPECTED_SELECTION
from marketlab.h021_p013_dividend_reconciliation import (
    P003_PATH,
    P011_PATH,
    P012_PATH,
    P012_PDF_RELATIVE,
    RECONCILIATION_ID,
    build_vedl_source_delta,
    load_original_sources,
    require_total_return_permission,
)


def _report() -> dict:
    risk, source, intent, provenance = load_original_sources(Path("."))
    return build_vedl_source_delta(risk, source, intent, provenance)


def test_h021_original_preentry_record_not_rewritten() -> None:
    original, receipt, intent, provenance = load_original_sources(Path("."))
    before = deepcopy((original, receipt, intent))
    result = build_vedl_source_delta(original, receipt, intent, provenance)

    assert result["evidence_delta_id"] == RECONCILIATION_ID
    assert result["frozen_symbols"] == list(EXPECTED_SELECTION)
    assert result["frozen_selected_count"] == 10
    assert result["original_p011_risk_alert_unchanged"] is True
    assert result["original_p003_selected_names_unchanged"] is True
    assert original["original_exchange_filing_pdfs_verified_for_dividends"] is False
    assert original["stock_dividend_cashflows_accounted_for"] is False
    assert (original, receipt, intent) == before
    assert result["source_provenance"]["original_p012_pdf_sha256"] == (
        "abdd026339469b9e51ab75fb2a37551be23812dcc037c875759cd79a8e6cb364"
    )


def test_additive_source_only_confirms_vedl_board_declaration_and_record_date() -> None:
    report = _report()
    rows = report["source_risk_rows_with_additive_p012_evidence"]
    assert len(rows) == 10
    assert [r["symbol"] for r in rows] == list(EXPECTED_SELECTION)
    assert report["dividend_declaration_original_source_confirmed_count"] == 1
    assert report["source_verified_dividend_symbols"] == ["VEDL"]
    source = rows[0]["new_original_pdf_declaration_evidence"]
    assert source["dividend_declaration_and_record_date_source_verified"] is True
    assert source["original_pdf_declared_cash_per_share_inr"] == 5.0
    assert source["original_pdf_issuer_record_date_ist"] == "2026-10-14"
    assert source["source_announcement_publication_utc"] == "2026-10-08T07:41:56Z"
    assert source["actual_pdf_retrieval_utc"] == "2026-10-12T04:50:15.704770Z"
    assert source["ex_date_independently_verified_by_this_board_pdf"] is False
    assert source["dividend_paid_or_cash_received_verified"] is False
    assert source["actual_paper_trade_fill_or_entitlement_verified"] is False
    assert source["total_return_basis_verified"] is False
    assert all(
        "new_original_pdf_declaration_evidence" not in item for item in rows[1:]
    )
    assert report["remaining_nine_companies_whole_horizon_actions_not_audited"] is True


def test_known_issuer_event_not_return_permission_or_account_value() -> None:
    report = _report()
    for key in (
        "VEDL_ex_date_original_exchange_action_census_complete",
        "cash_entitlement_and_payment_calculated",
        "actual_entry_trade_filled",
        "nifty500_price_to_total_return_basis_reconciled",
        "november8_muhurat_session_resolved",
        "official_2027_calendar_verified",
        "twenty_or_sixty_session_returns_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert report[key] is False
    with pytest.raises(ValueError, match="not a complete"):
        require_total_return_permission(report)


def test_source_event_and_original_preentry_cohort_cannot_be_substituted() -> None:
    risk, receipt, intent, provenance = load_original_sources(Path("."))
    risk["source_risk_rows"][0]["known_preentry_dividend_event"][
        "reported_record_date_ist"
    ] = "2026-10-15"
    with pytest.raises(ValueError, match="secondary dividend risk"):
        build_vedl_source_delta(risk, receipt, intent, provenance)
    risk, receipt, intent, provenance = load_original_sources(Path("."))
    intent["selected_observations"][0]["symbol"] = "TRENT"
    with pytest.raises(ValueError, match="ten selected"):
        build_vedl_source_delta(risk, receipt, intent, provenance)
    risk, receipt, intent, provenance = load_original_sources(Path("."))
    receipt["issuer_reported_dividend_terms"]["issuer_reported_record_date_ist"] = (
        "2026-10-15"
    )
    with pytest.raises(ValueError, match="contradict frozen risk"):
        build_vedl_source_delta(risk, receipt, intent, provenance)


def test_original_bytes_git_source_drift_fails_closed(tmp_path: Path) -> None:
    for source in (P003_PATH, P011_PATH, P012_PATH, P012_PDF_RELATIVE):
        dest = tmp_path / source
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())

    original, source, intent, provenance = load_original_sources(tmp_path)
    assert build_vedl_source_delta(
        original, source, intent, provenance
    )["dividend_declaration_original_source_confirmed_count"] == 1

    source_path = tmp_path / P012_PDF_RELATIVE
    source_path.write_bytes(source_path.read_bytes() + b"change")
    with pytest.raises(ValueError, match="original VEDL PDF bytes changed"):
        load_original_sources(tmp_path)
    source_path.write_bytes(P012_PDF_RELATIVE.read_bytes())

    warning_path = tmp_path / P011_PATH
    warning_path.write_bytes(warning_path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Git blob mismatch"):
        load_original_sources(tmp_path)


def test_source_delta_cli_writes_only_new_file_and_is_reproducible(
    tmp_path: Path,
) -> None:
    out = tmp_path / "post-original-dividend-delta.json"
    command = [
        sys.executable,
        "-m",
        "scripts.build_h021_p013_dividend_reconciliation",
        "--out",
        str(out),
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)
    brief = json.loads(first.stdout)
    assert brief["issuer_declaration_source_verified"] == 1
    assert brief["frozen_h021_symbol_count"] == 10
    assert brief["returns_opened"] is False
    assert brief["dividend_entitlement_calculated"] is False
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result == _report()
    subprocess.run(
        command + ["--verify-existing"],
        check=True, capture_output=True, text=True,
    )
    out.write_text(out.read_text(encoding="utf-8") + "corrupt", encoding="utf-8")
    failed = subprocess.run(
        command + ["--verify-existing"],
        check=False, capture_output=True, text=True,
    )
    assert failed.returncode != 0
    assert "source dividend risk delta changed" in failed.stderr


def test_require_return_clearance_fails_from_cli(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.build_h021_p013_dividend_reconciliation",
            "--require-return-clearance",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "not a complete trade entitlement" in result.stderr
