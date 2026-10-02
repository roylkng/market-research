import pytest

from marketlab.alpha import AlphaContractError
from marketlab.rm001_d009 import (
    SAMPLE_SYMBOLS,
    build_d009_report,
    parse_quote_industry,
)


def _payload(symbol="RELIANCE"):
    return {
        "info": {
            "symbol": symbol,
            "isin": "INE002A01018",
        },
        "industryInfo": {
            "macro": "Energy",
            "sector": "Oil Gas & Consumable Fuels",
            "industry": "Petroleum Products",
            "basicIndustry": "Refineries & Marketing",
        },
    }


def test_parse_quote_industry_extracts_four_tiers_and_identity():
    row = parse_quote_industry(
        _payload(),
        requested_symbol="RELIANCE",
    )
    assert row["status"] == "READY"
    assert row["symbol_identity_match"] is True
    assert row["isin"] == "INE002A01018"
    assert row["classification"]["macro_economic_sector"] == "Energy"
    assert row["classification"]["basic_industry"] == "Refineries & Marketing"


def test_parse_quote_industry_rejects_symbol_conflict():
    row = parse_quote_industry(
        _payload(symbol="TCS"),
        requested_symbol="RELIANCE",
    )
    assert row["status"] == "SYMBOL_CONFLICT"
    assert row["symbol_identity_match"] is False


def test_d009_report_passes_stable_full_coverage():
    observations = []
    for symbol in SAMPLE_SYMBOLS:
        row = parse_quote_industry(
            _payload(symbol=symbol),
            requested_symbol=symbol,
        )
        row["raw_sha256"] = "a" * 64
        observations.append(row)
    report = build_d009_report(observations=observations)
    assert report["status"] == "PASS_PROSPECTIVE_SOURCE_FEASIBILITY"
    assert report["prospective_capture_design_authorized"] is True
    assert report["historical_backfill_authorized"] is False


def test_d009_report_fails_if_two_of_sixteen_lack_classification():
    observations = []
    for index, symbol in enumerate(SAMPLE_SYMBOLS):
        payload = _payload(symbol=symbol)
        if index < 2:
            payload["industryInfo"].pop("basicIndustry")
        observations.append(
            parse_quote_industry(
                payload,
                requested_symbol=symbol,
            )
        )
    report = build_d009_report(observations=observations)
    assert report["four_level_classification_fraction"] == pytest.approx(14 / 16)
    assert report["status"] == "FAIL_SOURCE_FEASIBILITY"


def test_d009_report_rejects_changed_frozen_sample_order():
    observations = [
        parse_quote_industry(_payload(symbol=symbol), requested_symbol=symbol)
        for symbol in reversed(SAMPLE_SYMBOLS)
    ]
    with pytest.raises(AlphaContractError, match="frozen sample"):
        build_d009_report(observations=observations)
