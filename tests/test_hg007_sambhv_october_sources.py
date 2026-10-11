from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import acquire_hg007_sambhv_october_sources as source


def _fake_pdf() -> bytes:
    return b"%PDF-1.7\n" + b"0" * 1250 + b"\n%%EOF\n"


def _sales_pages() -> list[str]:
    labels = [
        "Sambhv Steel Tubes Limited, October 02, 2026, Sales Volume Update",
        "Product Category (Ton), Q2 FY27 Q1 FY27 Q2 FY26 FY26 FY25",
        "Value Added Products, Structural Pipes and Tubes, Pre-Galvanised",
        "Stainless Steel Coils, Intermediate Products",
    ]
    for quarter in source.QUARTERS.values():
        for v in quarter.values():
            labels.append(f"{v:,}")
    return ["\n".join(labels[:2]), "\n".join(labels[2:])]


def _warrant_pages() -> list[str]:
    return [(
        "Sambhv Steel Tubes Limited\nOctober 06, 2026\n"
        "Subject: appointment of Monitoring Agency for preferential issue of warrants\n"
        "Company has appointed CARE Ratings Limited as the Monitoring Agency.\n"
        "Shareholders approved on August 10, 2026.\n"
        "Issue proceeds ₹99,99,71,000/-.\n"
        "The allotment of warrants and utilization monitoring are separate."
    )]


def _patch_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    def pages(raw: bytes, *, expected_count: int) -> list[str]:
        assert raw == _fake_pdf()
        if expected_count == 2:
            return _sales_pages()
        if expected_count == 1:
            return _warrant_pages()
        raise AssertionError("wrong expected issuer PDF count")

    monkeypatch.setattr(source, "_text_pages", pages)


def _ready(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict]:
    _patch_parser(monkeypatch)
    rec = {}
    pdf = {}
    for kind in source.PDFS:
        raw = _fake_pdf()
        fact = source.verify_original_pdf(kind, raw)
        rec[kind] = source._receipt(
            kind, "ORIGINAL_ISSUER_PDF_CAPTURED_FACTS_VERIFIED",
            status=200, raw=raw, facts=fact, error="ORIGINAL_VERIFIED",
        )
        pdf[kind] = raw
    return rec, pdf


def test_first_party_original_table_arithmetic_and_no_future_earnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec, raw = _ready(monkeypatch)
    packet = source.build_sambhv_q2_case(rec, raw)
    assert packet["readout_id"] == source.SOURCE_ID
    assert packet["symbol"] == "SAMBHV"
    assert packet["q2_2026_27_volume_report_date"] == "2026-10-02"
    rows = packet["q2_vs_q1_vs_prior_year_sales_tonnes"]
    assert rows["all_product_sales_tonnes"]["q2_fy27_tonnes"] == 122662
    assert rows["all_product_sales_tonnes"]["q2_fy26_tonnes"] == 98768
    assert rows["all_product_sales_tonnes"]["yoy_pct"] == pytest.approx(
        24.192046006803825
    )
    assert rows["all_product_sales_tonnes"]["qoq_pct"] == pytest.approx(
        13.817260673093879
    )
    assert rows["value_added_total_tonnes"]["yoy_pct"] == pytest.approx(
        26.829458922310813
    )
    assert rows["gp_tonnes"]["yoy_pct"] == pytest.approx(58.98451031820655)
    assert rows["stainless_tonnes"]["qoq_pct"] == pytest.approx(
        -2.1341463414634165
    )
    assert packet["warrant_proceeds_issuer_disclosed_inr_crore"] == (
        pytest.approx(99.9971)
    )
    for flag in (
        "warrant_proceeds_are_verified_current_cash",
        "warrant_exercise_and_dilution_verified",
        "steel_phase1_0_36mmtpa_plant_operating_verified",
        "steel_810cr_and_power_125cr_remaining_capex_reconciled_to_proceeds",
        "sales_yoy_growth_proves_incremental_ebitda",
        "new_business_cash_free_flow_verified",
        "current_fully_diluted_share_count_verified",
        "investment_expected_returns_computed",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert packet[flag] is False


def test_missing_original_sale_total_is_rejected_even_if_title_matches() -> None:
    bad = _sales_pages()
    bad[1] = bad[1].replace("122,662", "122,000")
    with pytest.raises(ValueError, match="original Q2 sales table"):
        source._text_identity("q2_sales", bad)
    wrong = _sales_pages()
    wrong[0] = wrong[0].replace("October 02, 2026", "October 10, 2026")
    with pytest.raises(ValueError, match="original Q2 sales table"):
        source._text_identity("q2_sales", wrong)


def test_warrant_monitoring_amount_is_not_cash_receipt_or_exercise() -> None:
    facts = source._text_identity("warrant_monitor", _warrant_pages())
    assert facts["issue_proceeds_stated_inr"] == 999971000
    assert facts["issue_proceeds_stated_inr_crore"] == 99.9971
    assert facts["actual_warrant_exercise_and_cash_receipt_verified"] is False
    wrong = _warrant_pages()
    wrong[0] = wrong[0].replace("99,99,71,000", "99,99,70,000")
    with pytest.raises(ValueError, match="warrant monitoring disclosure"):
        source._text_identity("warrant_monitor", wrong)


def test_pdf_header_and_source_categories_do_not_promote_html() -> None:
    assert source._pdf_bytes_plausible(_fake_pdf())
    assert not source._pdf_bytes_plausible(b"<html>Access denied</html>")
    assert not source._pdf_bytes_plausible(b"%PDF-1.7\n")
    with pytest.raises(ValueError, match="original issuer source URL/PDF"):
        source.verify_original_pdf("q2_sales", b"HTTP 200 unexpected HTML")
    with pytest.raises(ValueError, match="unrecognized original issuer"):
        source.acquire_issuer_pdf("not-an-approved-file", attempts=1)


def test_access_denied_no_redirect_and_no_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Response:
        status_code = 403
        content = b"forbidden"
        url = source.PDFS["q2_sales"]["url"]

    def mocked_get(url: str, **kwargs: object) -> Response:
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(source.requests, "get", mocked_get)
    receipt, raw = source.acquire_issuer_pdf(
        "q2_sales", attempts=3, retry_seconds=0
    )
    assert raw is None
    assert receipt["state"] == "ORIGINAL_ISSUER_SOURCE_ACCESS_BLOCKED"
    assert receipt["original_pdf_sha256"] is None
    assert len(calls) == 1
    assert calls[0][0] == source.PDFS["q2_sales"]["url"]
    assert calls[0][1]["allow_redirects"] is False
    assert receipt["live_capital_allowed"] is False


def test_source_file_sha_and_receipts_are_replayable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    rec, pdf = _ready(monkeypatch)
    result = source.save_attempt(tmp_path, rec, pdf)
    assert result["ready_both_original_issuer_pdfs"] is True
    assert (tmp_path / "sambhv-october-case.json").exists()
    packet = json.loads((tmp_path / "sambhv-october-case.json").read_text())
    assert packet["symbol"] == "SAMBHV"
    for kind in source.PDFS:
        sha = hashlib.sha256(pdf[kind]).hexdigest()
        assert (tmp_path / "raw" / "sha256" / f"{sha}.pdf").read_bytes() == pdf[kind]
        assert json.loads((tmp_path / f"{kind}-source-receipt.json").read_text()) == rec[kind]
    assert result["live_capital_allowed"] is False


def test_partial_document_success_can_never_publish_combined_case(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    rec, pdf = _ready(monkeypatch)
    altered = deepcopy(rec)
    altered["warrant_monitor"] = source._receipt(
        "warrant_monitor", "ORIGINAL_ISSUER_SOURCE_ACCESS_BLOCKED",
        status=403, raw=None, facts=None, error="HTTP_403_NO_BYPASS",
    )
    pdf["warrant_monitor"] = None
    summary = source.save_attempt(tmp_path, altered, pdf)
    assert summary["ready_both_original_issuer_pdfs"] is False
    assert not (tmp_path / "sambhv-october-case.json").exists()
    with pytest.raises(ValueError, match="no verified original issuer"):
        source.build_sambhv_q2_case(altered, pdf)


def test_tampered_sources_and_scope_rejected_before_sambhv_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec, pdf = _ready(monkeypatch)
    altered = deepcopy(rec)
    altered["q2_sales"]["original_pdf_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="no verified original issuer"):
        source.build_sambhv_q2_case(altered, pdf)
    altered = deepcopy(rec)
    altered["warrant_monitor"]["independently_reproducible_text"] = {
        "faked": "share exercise complete"
    }
    with pytest.raises(ValueError, match="original table facts changed"):
        source.build_sambhv_q2_case(altered, pdf)
