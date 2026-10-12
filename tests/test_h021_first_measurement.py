from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_first_measurement import (
    ORIGINAL_PACKET_SHA,
    ORIGINAL_STOCK_ZIP_SHA,
    SOURCE_FILES,
    VEDL_ORIGINAL_PDF_SHA,
    VEDL_PDF_FILE,
    _read_source,
    build_measurement_record,
    source_pinned_first_measurement,
)


def _inputs() -> tuple[dict, dict, dict, dict, dict, dict, dict, dict, dict]:
    values = {
        key: _read_source(Path("."), key)[0]
        for key in SOURCE_FILES
    }
    return (
        values["original_preentry_intent"],
        values["original_eps_comparison"],
        values["original_first_entry_source_attempt"],
        values["independent_original_source_replay"],
        values["original_preentry_eps_sign_audit"],
        values["original_vedl_dividend_risk"],
        values["original_vedl_nse_pdf_receipt"],
        {},
        values["frozen_u001_original_universe"],
    )


def _build_from(args: tuple) -> dict:
    return build_measurement_record(
        intent=args[0],
        universe=args[8],
        comparison=args[1],
        original_attempt=args[2],
        first_replay=args[3],
        eps_sign=args[4],
        original_risk=args[5],
        vedl_receipt=args[6],
        source_provenance=args[7],
    )


def test_real_original_first_entry_all_ten_official_opens_and_no_returns() -> None:
    report = source_pinned_first_measurement(Path("."))
    assert report["first_source_stock_open_count"] == 10
    assert report["original_first_attempt_packet_sha256"] == ORIGINAL_PACKET_SHA
    assert report["first_nse_stock_raw_sha256"] == ORIGINAL_STOCK_ZIP_SHA
    assert report["first_source_attempt_nifty500_index_state"] == (
        "HTTP_404_NOT_PUBLISHED_AT_FIRST_CAPTURE"
    )
    assert report["benchmark_may_become_available_on_later_source_attempt"] is True
    assert report["original_top_decile_unchanged"] is True
    assert report["original_selected_negative_eps_inversion_symbols"] == ["IDEA"]
    assert report["original_selected_preentry_dividend_notice_symbols"] == ["VEDL"]
    assert report["return_outcomes_opened"] is False
    assert report["benchmark_excess_calculated"] is False
    assert report["live_capital_allowed"] is False
    assert report["portfolio_eligibility_allowed"] is False
    assert report["cash_dividend_entitlement_verified"] is False
    assert report["nifty500_total_return_index_basis_verified"] is False
    assert report["first_source_stock_open_count"] == len(
        report["selected_stock_observations"]
    )
    assert all(
        not row["open_observation_is_real_fill"]
        and not row["benchmark_excess_computable_from_this_packet"]
        for row in report["selected_stock_observations"]
    )


def test_first_open_prices_are_from_official_h021_oct12_nse_zip() -> None:
    report = source_pinned_first_measurement(Path("."))
    opens = {
        row["symbol"]: row["2026_10_12_official_equity_open_inr"]
        for row in report["selected_stock_observations"]
    }
    assert opens == {
        "VEDL": 265.95,
        "ETERNAL": 325.75,
        "DMART": 3407.0,
        "IDEA": 13.02,
        "ADANIENSOL": 1274.90,
        "JSWSTEEL": 1174.0,
        "COALINDIA": 413.05,
        "INFY": 1029.30,
        "GAIL": 167.75,
        "POWERGRID": 250.90,
    }


def test_idea_positive_ratio_is_loss_worsening_not_earnings_improvement() -> None:
    report = source_pinned_first_measurement(Path("."))
    cases = {r["symbol"]: r for r in report["selected_stock_observations"]}
    idea = cases["IDEA"]
    assert idea["frozen_2026_10_09_eps_ratio_revision_pct"] == pytest.approx(
        4.6242774566473965
    )
    assert idea["source_bound_special_notice"] == {
        "prior_eps_inr": -1.73,
        "current_eps_inr": -1.81,
        "absolute_eps_change": pytest.approx(-0.08),
        "loss_trend": "FORECAST_LOSS_WORSENING_DESPITE_POSITIVE_RATIO",
    }
    assert idea["measurement_warnings"] == [
        "NEGATIVE_PRIOR_EPS_REVERSES_PERCENTAGE_REVISION_DIRECTION"
    ]
    assert all(
        not r["measurement_warnings"]
        for r in report["selected_stock_observations"]
        if r["symbol"] not in {"VEDL", "IDEA"}
    )


def test_vedl_original_notice_does_not_establish_dividend_cash_receipt() -> None:
    report = source_pinned_first_measurement(Path("."))
    vedl = report["selected_stock_observations"][0]
    notice = vedl["source_bound_special_notice"]
    assert notice["original_pdf_sha256"] == VEDL_ORIGINAL_PDF_SHA
    assert notice["announced_cash_dividend_per_share_inr"] == 5.0
    assert notice["original_issuer_reported_record_date_ist"] == "2026-10-14"
    assert notice["dividend_to_observed_open_magnitude_pct_not_yield_or_return"] == (
        pytest.approx(100 * 5 / 265.95)
    )
    assert notice["observed_hypothetical_position_dividend_entitlement_verified"] is False
    assert notice["ex_date_independently_verified"] is False
    assert notice["actual_cash_receipt_verified"] is False
    assert report["source_provenance"]["vedl_original_pdf"]["sha256"] == (
        VEDL_ORIGINAL_PDF_SHA
    )


def test_changed_symbol_price_or_benchmark_status_cannot_pass() -> None:
    args = _inputs()
    altered = deepcopy(args)
    altered[3]["stock_observations"][0]["open_price_inr"] = 1000
    with pytest.raises(ValueError, match="content hash mismatch"):
        # Original source packet digest refuses fabricated OHLC.
        _build_from(altered)
    altered = deepcopy(args)
    altered[3]["source_receipts"]["index"]["status"] = "OK"
    with pytest.raises(ValueError, match="content hash mismatch"):
        _build_from(altered)
    altered = deepcopy(args)
    altered[2]["source_receipts"]["index"]["http_status"] = 200
    with pytest.raises(ValueError, match="original NSE receipts"):
        _build_from(altered)


def test_forced_idea_earnings_revision_reclassification_rejected() -> None:
    args = _inputs()
    altered = deepcopy(args)
    altered[4]["negative_prior_eps_cases"][1]["current_eps"] = -1.5
    with pytest.raises(ValueError, match="earnings direction"):
        _build_from(altered)


def test_dividend_original_pub_time_and_entitlement_cannot_be_rewritten() -> None:
    args = _inputs()
    altered = deepcopy(args)
    altered[6]["issuer_reported_dividend_terms"][
        "hypothetical_entry_holder_dividend_entitlement_proven"
    ] = True
    with pytest.raises(ValueError, match="entitlement"):
        _build_from(altered)
    altered = deepcopy(args)
    altered[6]["first_original_announcement_provenance"][
        "source_public_broadcast_at_utc"
    ] = "2026-10-13T06:30:00Z"
    with pytest.raises(ValueError, match="chronology"):
        _build_from(altered)


def test_original_stock_risk_sources_use_content_hashes(tmp_path: Path) -> None:
    for filename, _expected in SOURCE_FILES.values():
        target = tmp_path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(filename).read_bytes())
    pdf = tmp_path / VEDL_PDF_FILE
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(Path(VEDL_PDF_FILE).read_bytes())
    assert source_pinned_first_measurement(tmp_path) == source_pinned_first_measurement(
        Path(".")
    )
    pdf.write_bytes(pdf.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="PDF source bytes were modified"):
        source_pinned_first_measurement(tmp_path)


def test_first_entry_measurement_cli_is_deterministic_and_reviewable(
    tmp_path: Path,
) -> None:
    out = tmp_path / "entry-measurement-v1.json"
    cmd = [
        sys.executable,
        "scripts/audit_h021_first_entry_measurement.py",
        "--out", str(out),
    ]
    first = subprocess.run(cmd, check=True, capture_output=True, text=True)
    summary = json.loads(first.stdout)
    assert summary["first_stock_opens"] == 10
    assert summary["negative_eps_inversion_symbols"] == ["IDEA"]
    assert summary["preentry_dividend_notice_symbols"] == ["VEDL"]
    assert summary["live_capital_allowed"] is False
    assert json.loads(out.read_text(encoding="utf-8")) == source_pinned_first_measurement(
        Path(".")
    )
    subprocess.run(
        cmd + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    out.write_text(out.read_text(encoding="utf-8") + "hindsight", encoding="utf-8")
    failed = subprocess.run(
        cmd + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "source drifted" in failed.stderr
