from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import acquire_hg007_sambhv_july_warrants as subject


def _synthetic() -> bytes:
    return b"%PDF-1.7\n" + b"0" * 1800 + b"\n%%EOF\n"


def _pages() -> list[str]:
    return [
        ("July 15, 2026\nSambhv Steel Tubes Limited\n"
         "Proposed board issue 8,695,400 fully convertible equity warrants "
         "at issue price INR 115 aggregate INR 999,971,000."),
        "Approval of members required, subject to members / shareholders and funds.",
        ("Annexure A: Upto 8,695,400 equity warrants at issue price 115; "
         "Tenure of Warrants Upto 18 months from date of allotment."),
        ("Each Warrant may subscribe 1 (one) Equity Share during 18 months "
         "from the date of allotment; 25% of issue price at the time of "
         "subscription and allotment of each warrant, balance 75% at the "
         "time of equity conversion; unexercised warrants forfeited."),
        ("Annexure B: Anjaneya Minerals Private Limited - 6,608,600, "
         "Suresh Kumar Goyal, Vikas Kumar Goyal, Bhavesh Khetan, "
         "Bikash Agrawal, Saurabh Patil, Anu Garg."),
    ]


def _companion() -> tuple[dict, dict]:
    selected = {}
    receipts = {}
    for key, source in (
        ("p031", subject.OCTOBER_P031),
        ("hg005", subject.HISTORICAL_HG005),
        ("p017", subject.AUGUST_P017),
    ):
        selected[key], receipts[key] = subject._pinned_json(Path("."), source)
    return selected, receipts


def _ready(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, bytes]:
    monkeypatch.setattr(subject, "_pdf_text_pages", lambda raw: _pages())
    raw = _synthetic()
    verified = subject.verify_original_board_terms(raw)
    receipt = subject._receipt(
        state="ORIGINAL_BOARD_PDF_CAPTURED_AND_TERMS_BOUND",
        http_status=200, raw=raw, verified=verified,
        issue="ISSUER_FIVE_PAGE_SOURCE_VERIFIED",
    )
    return receipt, raw


def test_issuer_board_source_carries_25_75_cash_staging_and_tenure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt, _raw = _ready(monkeypatch)
    v = receipt["source_text_verified"]
    assert v["reported_board_date"] == "2026-07-15"
    assert v["reported_maximum_warrants"] == 8_695_400
    assert v["reported_issue_price_per_warrant_inr"] == 115
    assert v["reported_maximum_total_issue_consideration_inr"] == 999_971_000
    assert v["percent_due_only_at_actual_warrant_allotment"] == 25
    assert v["percent_due_only_at_equity_conversion"] == 75
    assert v["max_tenure_months_FROM_ACTUAL_ALLOTMENT"] == 18
    assert v["forfeiture_if_not_exercised_in_18_months"] is True
    assert v["proposed_promoter_group_anjaneya_warrants"] == 6_608_600
    assert v["original_pdf_visual_semantic_review_approved"] is False
    assert v["actual_allotment_or_exercise_verified"] is False


def test_source_bound_cash_scenarios_do_not_invent_current_bank_cash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt, _raw = _ready(monkeypatch)
    sources, originals = _companion()
    old_sources = deepcopy(sources)
    output = subject.build_conditional_board_cash_timing(
        receipt, sources, provenance=originals
    )
    assert sources == old_sources
    assert output["fully_exercised_maximum_gross_issue_consideration_cr"] == 99.9971
    assert output["scenario_only_upfront_cash_at_100pct_allotment_cr"] == (
        pytest.approx(24.999275)
    )
    assert output["scenario_only_later_cash_at_100pct_conversion_cr"] == (
        pytest.approx(74.997825)
    )
    assert output["if_zero_actual_warrants_allotted_cash_from_issue_cr"] == 0
    assert output["exercise_time_limit_months_after_actual_allotment"] == 18
    assert output["actual_allotment_date_verified"] is False
    assert output["last_permitted_exercise_calendar_date_verified"] is False
    assert output["fully_exercised_pro_forma_added_shares"] == 8_695_400
    assert output["frozen_old_reported_fd_shares_reference_not_current"] == 294_671_429
    assert output["frozen_old_full_conversion_pro_forma_fd_shares_not_current"] == (
        303_366_829
    )
    assert output["frozen_source_steel_plus_power_project_capex_cr"] == 935
    assert output["maximum_gross_warrant_proceeds_fraction_of_steel_power_capex"] == (
        pytest.approx(99.9971 / 935)
    )
    assert output[
        "hypothetical_non_warrant_financing_gap_if_both_projects_and_full_issue_cr"
    ] == pytest.approx(835.0029)
    assert output["promoter_group_anjaneya_proportion_of_proposal_pct"] == (
        pytest.approx(100 * 6_608_600 / 8_695_400)
    )
    assert output["portfolio_eligibility_allowed"] is False
    assert output["live_capital_allowed"] is False
    assert output["first_25pct_subscription_cash_received_verified"] is False
    assert output["last_75pct_conversion_cash_received_verified"] is False
    assert output["warrant_exercise_completed_verified"] is False
    assert output["current_fully_diluted_share_count_verified"] is False
    assert output["q2_sales_growth_verifies_project_ebitda"] is False


def test_original_pdf_missing_cash_term_or_allotment_clock_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = _pages()
    pages[3] = pages[3].replace("25%", "35%")
    monkeypatch.setattr(subject, "_pdf_text_pages", lambda raw: pages)
    with pytest.raises(ValueError, match="page 4 lacks"):
        subject.verify_original_board_terms(_synthetic())
    pages = _pages()
    pages[3] = pages[3].replace("from the date of allotment", "from the board date")
    monkeypatch.setattr(subject, "_pdf_text_pages", lambda raw: pages)
    with pytest.raises(ValueError, match="linked to actual allotment"):
        subject.verify_original_board_terms(_synthetic())


def test_allotment_proceeds_unverified_even_after_monitoring_appointment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec, original = _ready(monkeypatch)
    companions, receipts = _companion()
    result = subject.build_conditional_board_cash_timing(
        rec, companions, provenance=receipts
    )
    assert result["issuer_later_shareholder_approval_reported_date"] == "2026-08-10"
    assert result["monitoring_agency_appointment_reported_date"] == "2026-10-06"
    assert result["full_99_9971cr_cash_received_verified"] is False
    assert result["all_8_6954m_warrants_issued_verified"] is False
    assert result["future_shareholder_expected_returns_calculated"] is False

    bad = deepcopy(companions)
    bad["p031"]["warrant_proceeds_are_verified_current_cash"] = True
    with pytest.raises(ValueError, match="monitoring/capex"):
        subject.build_conditional_board_cash_timing(rec, bad, provenance=receipts)
    assert hashlib.sha256(original).hexdigest() == rec["original_pdf_sha256"]


def test_no_redirect_or_access_control_evasion(monkeypatch: pytest.MonkeyPatch) -> None:
    called = []

    class Response:
        status_code = 403
        content = b"access denied"
        url = subject.ISSUER_PDF

    def request(url: str, **kwargs: object) -> Response:
        called.append((url, kwargs))
        return Response()

    monkeypatch.setattr(subject.requests, "get", request)
    record, raw = subject.fetch_original_board(attempts=3, sleep_seconds=0)
    assert raw is None
    assert record["state"] == "ORIGINAL_BOARD_PDF_ACCESS_BLOCKED"
    assert len(called) == 1
    assert called[0][0] == subject.ISSUER_PDF
    assert called[0][1]["allow_redirects"] is False


def test_html_http_200_cannot_be_promoted_to_verified_issuer_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status_code = 200
        content = b"<html>blocked</html>"
        url = subject.ISSUER_PDF

    monkeypatch.setattr(subject.requests, "get", lambda url, **kwargs: Response())
    rec, raw = subject.fetch_original_board(attempts=1)
    assert rec["state"] == "ORIGINAL_BOARD_PDF_INVALID_OR_UNVERIFIED"
    assert rec["original_pdf_sha256"] is None
    assert raw is None


def test_retains_original_bytes_with_sha_and_rejects_unauthorized_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    record, raw = _ready(monkeypatch)
    companions, receipts = _companion()
    save = subject._retain(tmp_path, record, raw, companions, receipts)
    assert save["success"] is True
    assert save["live_capital_allowed"] is False
    digest = hashlib.sha256(raw).hexdigest()
    assert (tmp_path / "original-raw" / "sha256" / f"{digest}.pdf").read_bytes() == raw
    source = json.loads((tmp_path / "warrant-board-cash-timing-v1.json").read_text())
    assert source["original_source_provenance"]["original_pdf_sha256"] == digest
    assert source["future_shareholder_expected_returns_calculated"] is False
    assert (tmp_path / "original-source-receipt.json").is_file()
    with pytest.raises(ValueError, match="hash failed"):
        subject._retain(tmp_path, record, raw + b"altered", companions, receipts)


def test_original_prior_frozen_share_count_is_not_replaced_with_current_estimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record, _raw = _ready(monkeypatch)
    originals, receipts = _companion()
    changed = deepcopy(originals)
    changed["hg005"]["key_mechanical_context"]["SAMBHV"]["lanes"][
        "DILUTION_FINANCING"
    ]["event_adjusted_fd_shares"] += 1
    with pytest.raises(ValueError, match="proforma full-conversion"):
        subject.build_conditional_board_cash_timing(
            record, changed, provenance=receipts
        )


def test_pinned_research_evidence_blobs_disallow_rewriting_prior_trials(
    tmp_path: Path,
) -> None:
    for ref in (subject.HISTORICAL_HG005, subject.OCTOBER_P031, subject.AUGUST_P017):
        path, _sha = ref
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(path).read_bytes())
        subject._pinned_json(tmp_path, ref)
    target = tmp_path / subject.OCTOBER_P031[0]
    target.write_bytes(target.read_bytes() + b"rewritten")
    with pytest.raises(ValueError, match="Git blob drifted"):
        subject._pinned_json(tmp_path, subject.OCTOBER_P031)
