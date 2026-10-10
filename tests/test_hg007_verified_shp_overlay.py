from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_verified_shp_overlay import (
    SOURCE_XBRL_PATH,
    SOURCES,
    build_asof_fd_governance_overlay,
    load_sources,
)


def _result() -> dict:
    sources, refs = load_sources(Path("."))
    return build_asof_fd_governance_overlay(sources, refs)


def test_source_verified_sept29_pledge_fd_and_no_lookahead() -> None:
    r = _result()
    assert r["original_28_case_count"] == 28
    assert r["revised_case_count"] == 1
    assert r["unreviewed_other_issuer_count"] == 27
    assert r["original_nse_xbrl_asof_date"] == "2026-09-29"
    assert r["original_nse_xbrl_public_at_utc"] == "2026-10-08T13:24:47Z"
    assert r["forward_usable_only_after_original_first_public_broadcast"] is True
    assert r["original_frozen_selection_or_company_payoffs_revised"] is False
    assert r["verified_current_oct11_fully_diluted_share_counts"] == 0
    assert r["stock_expected_returns_calculated"] is False
    assert r["live_capital_allowed"] is False
    cases = {row["symbol"]: row for row in r["company_cases"]}
    assert len(cases) == 28
    case = cases["INOXGREEN"]
    facts = case["asof_29sep_exchange_source_update"]
    assert facts["status"] == "ORIGINAL_NSE_QIP_SPECIAL_XBRL_CONFIRMED_AS_OF_SEP29"
    assert facts["issued_basic_shares_as_of_sep29"] == 419_602_518
    assert facts["fully_diluted_shares_as_of_sep29"] == 422_070_138
    assert facts["outstanding_dilutive_shares_as_of_sep29"] == 2_467_620
    assert facts["pledged_shares_at_sep29"] == 4_900_000
    assert facts["named_pledging_promoter"] == "Inox Wind Limited"
    assert facts["reference_oct9_source_price_inr"] == 128.92
    assert facts["sept29_fd_shares_at_oct9_price_inr_crore"] == pytest.approx(
        5441.328219096
    )
    assert facts["reference_delta_above_basic_valuation_inr_crore"] == pytest.approx(
        5441.328219096 - 5409.515662056
    )
    assert facts["oct1_use_as_publicly_visible_fd_denominator_allowed"] is False
    assert facts["oct9_reference_proves_no_interim_capital_changes"] is False
    assert facts["oct11_current_issued_and_fd_verified"] is False
    assert facts["pledge_creation_date_and_loan_terms_verified"] is False
    assert facts["current_fair_value_or_forward_returns_permitted"] is False
    assert case["capital_basis_correction"]["status"] == (
        "STALE_MARCH_FD_DENOMINATOR_AFTER_SEPTEMBER_QIP"
    )
    assert all(not row["portfolio_eligibility_allowed"] for row in r["company_cases"])
    assert all(not row["live_capital_allowed"] for row in r["company_cases"])
    assert all(
        row["asof_29sep_exchange_source_update"]["status"] == "NOT_REVIEWED_IN_P013"
        for symbol, row in cases.items() if symbol != "INOXGREEN"
    )


def test_reconciliation_preserves_original_evidence_and_selection() -> None:
    s, refs = load_sources(Path("."))
    prior = deepcopy(s)
    report = build_asof_fd_governance_overlay(s, refs)
    assert s == prior
    old = s["old_28_casework"]
    assert [item["symbol"] for item in old["casework_with_capital_readiness"]] == [
        item["symbol"] for item in report["company_cases"]
    ]
    assert all(
        row["frozen_hg005_mechanical_hurdle"] == source["frozen_hg005_mechanical_hurdle"]
        for row, source in zip(
            report["company_cases"], old["casework_with_capital_readiness"], strict=True
        )
    )


def test_changed_original_nse_xbrl_or_source_receipt_fails_closed(tmp_path: Path) -> None:
    for path, _ in SOURCES.values():
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(Path(path).read_bytes())
    dest = tmp_path / SOURCE_XBRL_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(SOURCE_XBRL_PATH.read_bytes())
    load_sources(tmp_path)
    dest.write_bytes(dest.read_bytes() + b"fake pledge")
    with pytest.raises(ValueError, match="original official September NSE XBRL"):
        load_sources(tmp_path)
    dest.write_bytes(SOURCE_XBRL_PATH.read_bytes())
    a = tmp_path / SOURCES["original_named_promoter_pledge"][0]
    a.write_bytes(a.read_bytes() + b" ")
    with pytest.raises(ValueError, match="original Git source bytes"):
        load_sources(tmp_path)


def test_disallows_relabeling_as_current_or_pledge_absent() -> None:
    originals, receipts = load_sources(Path("."))
    fake = deepcopy(originals)
    fake["original_named_promoter_pledge"]["promoter_group_total_pledged_shares"] = 0
    with pytest.raises(ValueError, match="official pledged-share"):
        build_asof_fd_governance_overlay(fake, receipts)
    fake = deepcopy(originals)
    fake["original_special_nse_shp"]["parsed_special_facts"][
        "current_asof_oct11_fully_diluted_shares_confirmed"
    ] = True
    with pytest.raises(ValueError, match="original NSE time/FD"):
        build_asof_fd_governance_overlay(fake, receipts)
    fake = deepcopy(originals)
    fake["dated_qip_price_basis"]["post_qip_basic_share_capital_sensitivities"][
        "2026-10-09"
    ]["raw_nse_close_inr"] = 200
    with pytest.raises(ValueError, match="Oct9 price/basic"):
        build_asof_fd_governance_overlay(fake, receipts)


def test_cli_deterministic_and_no_approval(tmp_path: Path) -> None:
    out = tmp_path / "overlay.json"
    base = [
        sys.executable, "scripts/build_hg007_verified_shp_overlay.py",
        "--out", str(out),
    ]
    result = subprocess.run(base, check=True, capture_output=True, text=True)
    summary = json.loads(result.stdout)
    assert summary["sept29_pledged_shares"] == 4_900_000
    assert summary["oct11_current_issued_and_fd_verified"] is False
    assert summary["live_capital_allowed"] is False
    assert json.loads(out.read_text(encoding="utf-8")) == _result()
    subprocess.run(
        base + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    out.write_text(out.read_text(encoding="utf-8") + "rewritten", encoding="utf-8")
    bad = subprocess.run(
        base + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert bad.returncode != 0
    assert "original Sept29 governance packet was altered" in bad.stderr
