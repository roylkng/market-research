from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_eq_absence_review import (
    EXPECTED_GAPS,
    P041_GIT_BLOB,
    P041_PATH,
    _original_full_market_rows,
    _source28,
    build_missing_eq_series_review,
    validate_missing_eq_series_review,
)


def _zip_rows(*rows: dict[str, str]) -> bytes:
    stream = io.StringIO()
    fields = [
        "TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb",
        "SctySrs", "TtlTradgVol", "TtlTrfVal", "TtlNbOfTxsExctd",
    ]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for item in rows:
        writer.writerow({
            "TradDt": "2026-10-09",
            "Sgmt": "CM", "Src": "NSE", "FinInstrmTp": "STK",
            "ISIN": "INE123456789", "TckrSymb": "ORBTEXP",
            "SctySrs": "BE",
            "TtlTradgVol": "100",
            "TtlTrfVal": "10000",
            "TtlNbOfTxsExctd": "20",
            **item,
        })
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("BhavCopy_NSE_CM_0_0_0_20261009_F_0000.csv", stream.getvalue())
    return packed.getvalue()


def test_original_frozen_28_observations_and_exact_unresolved_eq_dates() -> None:
    source, receipt = _source28(Path("."))
    assert source["original_outside_u001_symbol_count"] == 28
    assert source["complete_20_session_equity_company_count"] == 26
    assert receipt["git_blob_sha"] == P041_GIT_BLOB
    assert EXPECTED_GAPS == {"ORBTEXP": 11, "RETAIL": 5}
    assert source["source_returns_or_alpha_computed"] is False
    assert source["live_capital_allowed"] is False


def test_original_nse_full_series_data_reconciled_without_fills() -> None:
    result = build_missing_eq_series_review(Path("."))
    validate_missing_eq_series_review(result)
    assert result["examined_names_missing_equity_series"] == ["ORBTEXP", "RETAIL"]
    assert len(result["source_original_twenty_equity_files"]) == 20
    assert result["original_eq_missing_observations"] == 16
    assert result["missing_eq_days_treated_as_zero_turnover"] is False
    assert result["off_equity_series_rows_counted_in_equity_turnover"] is False
    assert result["executability_verified"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False
    cases = {x["symbol"]: x for x in result["findings"]}
    assert {k: v["missing_eq_day_count"] for k, v in cases.items()} == EXPECTED_GAPS
    for symbol, item in cases.items():
        assert item["current_tradability_proven"] is False
        assert len(item["missing_eq_day_evidence"]) == EXPECTED_GAPS[symbol]
        assert sum(item["source_classification_counts"].values()) == EXPECTED_GAPS[symbol]
        assert len({
            p["session_date"] for p in item["missing_eq_day_evidence"]
        }) == EXPECTED_GAPS[symbol]
        for missing in item["missing_eq_day_evidence"]:
            assert missing["source_p041_state"] == "OFFICIAL_EQ_ROW_MISSING_NO_SUBSTITUTION"
            assert missing["new_eq_series_price_or_turnover_imputed"] is False
            assert missing["no_stock_trading_on_exchange_proven"] is False
            assert missing["other_ticker_names_or_unreported_series_excluded"] is True
            assert all(
                q["exchange_series"] != "EQ"
                for q in missing["same_symbol_non_eq_rows"]
            )


def test_non_equity_series_detection_does_not_invent_eq_stock_bars() -> None:
    raw = _zip_rows(
        {"TckrSymb": "ORBTEXP", "SctySrs": "BE"},
        {"TckrSymb": "RETAIL", "SctySrs": "BZ", "TtlTradgVol": "0"},
        {"TckrSymb": "NOTINRESEARCH", "SctySrs": "EQ"},
    )
    data = _original_full_market_rows(
        raw, session="2026-10-09", symbols={"ORBTEXP", "RETAIL"}
    )
    assert len(data["ORBTEXP"]) == 1
    assert data["ORBTEXP"][0]["exchange_series"] == "BE"
    assert data["ORBTEXP"][0]["valid_positive_executed_turnover"] is True
    assert len(data["RETAIL"]) == 1
    assert data["RETAIL"][0]["exchange_series"] == "BZ"
    assert data["RETAIL"][0]["valid_positive_executed_turnover"] is False
    assert data["RETAIL"][0]["reported_shares_traded"] == 0.0


def test_nontrading_and_other_ticker_cannot_replace_missing_symbol() -> None:
    raw = _zip_rows(
        {"TckrSymb": "OLDRETAIL", "SctySrs": "EQ"},
        {"TckrSymb": "RETAIL", "Sgmt": "FO", "SctySrs": "BE"},
    )
    data = _original_full_market_rows(
        raw, session="2026-10-09", symbols={"ORBTEXP", "RETAIL"}
    )
    assert data == {"ORBTEXP": [], "RETAIL": []}


def test_pinned_source_bytes_and_result_digest_must_not_change(tmp_path: Path) -> None:
    original = P041_PATH.read_bytes()
    copy = tmp_path / P041_PATH
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="source evidence Git blob changed"):
        _source28(tmp_path)

    data = build_missing_eq_series_review(Path("."))
    mutated = deepcopy(data)
    mutated["findings"][0]["missing_eq_day_evidence"][0]["classification"] = "FAKE_CLEAR"
    with pytest.raises(ValueError, match="source observations tampered"):
        validate_missing_eq_series_review(mutated)


def test_rehashing_modified_result_does_not_turn_on_trading() -> None:
    from marketlab.hg007_eq_absence_review import _digest

    for field in (
        "original_selection_modified",
        "missing_eq_days_treated_as_zero_turnover",
        "off_equity_series_rows_counted_in_equity_turnover",
        "executability_verified",
        "return_outcomes_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        payload = build_missing_eq_series_review(Path("."))
        payload[field] = True
        payload["packet_sha256"] = _digest({
            k: v for k, v in payload.items() if k != "packet_sha256"
        })
        with pytest.raises(ValueError, match="cannot authorize"):
            validate_missing_eq_series_review(payload)


def test_cli_is_deterministic_and_original_source_only(tmp_path: Path) -> None:
    output = tmp_path / "missing-eq-original-review.json"
    command = [
        sys.executable, "scripts/review_hg007_missing_eq_series.py",
        "--out", str(output),
    ]
    first = subprocess.run(
        command, check=True, capture_output=True, text=True
    )
    summary = json.loads(first.stdout)
    assert summary["original_hg002_company_count"] == 28
    assert summary["original_missing_eq_session_count"] == 16
    assert summary["missing_eq_days_treated_as_zero_turnover"] is False
    assert summary["live_capital_allowed"] is False
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report == build_missing_eq_series_review(Path("."))
    subprocess.run(
        command + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    output.write_text(
        output.read_text(encoding="utf-8") + "unsafe", encoding="utf-8"
    )
    rejected = subprocess.run(
        command + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert rejected.returncode != 0
    assert "source non-EQ series gap review changed" in rejected.stderr
