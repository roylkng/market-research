from __future__ import annotations

from marketlab.alpha import AlphaContractError

import pytest
from marketlab.hg005_context import (
    EXPECTED_FA001_SHA,
    EXPECTED_GF001_SHA,
    EXPECTED_HG004_L001_SHA,
    EXPECTED_HG004_L002_SHA,
    EXPECTED_SS001_SHA,
    build_hg005_context,
    parse_shareholding_counts,
)


SYMBOLS = ["ANANTRAJ", "DEVX", "INOXGREEN", "NPST", "SAMBHV"]


def _xbrl(symbol: str, paid: int, diluted: int) -> bytes:
    return f"""<?xml version="1.0"?>
<xbrli:xbrl
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:in-capmkt="http://www.sebi.gov.in/xbrl">
 <xbrli:context id="ShareholdingPattern_ContextI">
  <xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
 </xbrli:context>
 <xbrli:context id="MainI">
  <xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
 </xbrli:context>
 <in-capmkt:Symbol contextRef="MainI">{symbol}</in-capmkt:Symbol>
 <in-capmkt:NumberOfFullyPaidUpEquityShares
   contextRef="ShareholdingPattern_ContextI"
   unitRef="shares">{paid}</in-capmkt:NumberOfFullyPaidUpEquityShares>
 <in-capmkt:NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities
   contextRef="ShareholdingPattern_ContextI"
   unitRef="shares">{diluted}</in-capmkt:NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities>
</xbrli:xbrl>
""".encode()


def _fact(value: float | None, unit: str) -> dict:
    if value is None:
        return {
            "status": "MISSING",
            "value": None,
            "unit_ref": None,
        }
    return {
        "status": "READY",
        "value": value,
        "unit_ref": unit,
    }


def _fa_row(symbol: str) -> dict:
    annual = {
        "basic_eps": _fact(10.0, "INRPerShare"),
        "cash": _fact(1_000_000_000.0, "INR"),
        "current_investments": _fact(100_000_000.0, "INR"),
        "noncurrent_investments": _fact(200_000_000.0, "INR"),
        "borrowings_current": _fact(100_000_000.0, "INR"),
        "borrowings_noncurrent": _fact(200_000_000.0, "INR"),
        "total_equity": _fact(2_000_000_000.0, "INR"),
        "investment_property": _fact(0.0, "INR"),
        "capital_work_in_progress": _fact(0.0, "INR"),
        "ppe": _fact(500_000_000.0, "INR"),
    }
    quarter = {
        "revenue": _fact(500_000_000.0, "INR"),
        "pat": _fact(50_000_000.0, "INR"),
        "basic_eps": _fact(2.5, "INRPerShare"),
    }
    return {
        "symbol": symbol,
        "annual": {"status": "READY", "parsed": {"facts": annual}},
        "quarter": {"status": "READY", "parsed": {"facts": quarter}},
    }


def _hg004_l002() -> dict:
    rows = []
    rows.append({
        "symbol": "ANANTRAJ",
        "payoff_model_lanes": [{
            "economic_family": "DEMERGER_ENTITLEMENT",
            "readiness_state": "READY_DEMERGER_ENTITLEMENT",
            "evidence_document_ids": ["a"],
            "explicit_terms": {
                "exchange_ratio_text": "1 for 1",
                "asset_or_business_description": "Data centre business",
                "operating_metric": None,
            },
            "missing_inputs": [
                "CURRENT_MARKET_CAP",
                "CURRENT_MARKET_PRICE",
                "SEPARATED_BUSINESS_EARNINGS",
            ],
        }],
    })
    rows.append({
        "symbol": "DEVX",
        "payoff_model_lanes": [
            {
                "economic_family": "DILUTION_FINANCING",
                "readiness_state": "READY_DILUTION_FINANCING",
                "evidence_document_ids": ["d"],
                "explicit_terms": {
                    "issue_price_per_security": 45,
                    "security_count": (
                        "33,33,330 convertible warrants plus "
                        "44,44,440 preferential equity shares"
                    ),
                },
                "missing_inputs": [
                    "CURRENT_FULLY_DILUTED_SHARE_COUNT",
                    "CURRENT_MARKET_CAP",
                    "CURRENT_MARKET_PRICE",
                ],
            },
            {
                "economic_family": "CAPITAL_DEPLOYMENT_MONITOR",
                "readiness_state": "READY_CAPITAL_DEPLOYMENT_MONITOR",
                "evidence_document_ids": ["d2"],
                "explicit_terms": {
                    "stated_raise_or_consideration": None,
                    "stated_use_of_proceeds": "security deposit",
                    "deployment_or_operating_metric": "450000 sq ft",
                },
                "missing_inputs": [
                    "CURRENT_MARKET_CAP",
                    "CURRENT_MARKET_PRICE",
                    "OTHER_EXPLICIT_SOURCE_REQUIRED",
                ],
            },
        ],
    })
    rows.append({
        "symbol": "INOXGREEN",
        "payoff_model_lanes": [
            {
                "economic_family": "ACQUISITION_ECONOMICS",
                "readiness_state": "READY_ACQUISITION_ECONOMICS",
                "evidence_document_ids": ["i"],
                "explicit_terms": {
                    "stated_total_consideration": 550,
                    "asset_or_business_description": "O&M business",
                    "operating_metric": "579.77 crore revenue",
                },
                "missing_inputs": [
                    "CURRENT_MARKET_CAP",
                    "CURRENT_MARKET_PRICE",
                    "TARGET_NORMALIZED_EARNINGS_OR_CASH_FLOW",
                ],
            },
            {
                "economic_family": "DEMERGER_ENTITLEMENT",
                "readiness_state": "READY_DEMERGER_ENTITLEMENT",
                "evidence_document_ids": ["i2"],
                "explicit_terms": {
                    "exchange_ratio_text": "122 for 2000",
                    "asset_or_business_description": "Power evacuation",
                    "operating_metric": None,
                },
                "missing_inputs": [
                    "CURRENT_MARKET_CAP",
                    "CURRENT_MARKET_PRICE",
                    "SEPARATED_BUSINESS_VALUATION_REFERENCE",
                ],
            },
        ],
    })
    rows.append({
        "symbol": "NPST",
        "payoff_model_lanes": [{
            "economic_family": "CAPITAL_DEPLOYMENT_MONITOR",
            "readiness_state": "READY_CAPITAL_DEPLOYMENT_MONITOR",
            "evidence_document_ids": ["n"],
            "explicit_terms": {
                "stated_raise_or_consideration": 300,
                "stated_use_of_proceeds": "growth",
                "deployment_or_operating_metric": "277.86 crore unutilized",
            },
            "missing_inputs": [
                "CURRENT_MARKET_CAP",
                "CURRENT_MARKET_PRICE",
                "CURRENT_CAPITAL_DEPLOYMENT_UPDATE",
            ],
        }],
    })
    rows.append({
        "symbol": "SAMBHV",
        "payoff_model_lanes": [{
            "economic_family": "DILUTION_FINANCING",
            "readiness_state": "READY_DILUTION_FINANCING",
            "evidence_document_ids": ["s"],
            "explicit_terms": {
                "issue_price_per_security": 115,
                "security_count": 8_695_400,
            },
            "missing_inputs": [
                "CURRENT_FULLY_DILUTED_SHARE_COUNT",
                "CURRENT_MARKET_CAP",
                "CURRENT_MARKET_PRICE",
            ],
        }],
    })
    return {
        "synthesis_id": "HG004-L002-v1",
        "synthesis_sha256": EXPECTED_HG004_L002_SHA,
        "payoff_model_ready_symbols": SYMBOLS,
        "rows": rows,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _l001_row(
    symbol: str,
    document_id: str,
    stage: str,
    facts: dict,
) -> dict:
    return {
        "document_id": document_id,
        "symbols": [symbol],
        "validated_extraction": {
            "transaction_stage": stage,
            "facts": facts,
        },
    }


def _unknown_blocks() -> dict:
    families = [
        "parties",
        "security_economics",
        "consideration",
        "ratios_entitlement",
        "dates",
        "conditions_approvals",
        "business_economics",
    ]
    return {family: {} for family in families}


def _hg004_l001() -> dict:
    rows = []
    for symbol in SYMBOLS:
        facts = _unknown_blocks()
        if symbol == "SAMBHV":
            facts["security_economics"]["number_of_securities"] = {
                "status": "EXPLICIT",
                "value": 8_695_400,
                "unit": "SHARES",
            }
            facts["dates"]["board_approval_date"] = {
                "status": "EXPLICIT",
                "value": "2026-07-15",
                "unit": "ISO_DATE",
            }
            rows.append(_l001_row(symbol, "s", "BOARD_APPROVED", facts))
        elif symbol == "INOXGREEN":
            facts["consideration"]["total_consideration"] = {
                "status": "EXPLICIT",
                "value": 550,
                "unit": "INR_CRORE_MAXIMUM",
            }
            rows.append(
                _l001_row(
                    symbol,
                    "i",
                    "REGULATORY_OR_COURT_APPROVED",
                    facts,
                )
            )
        else:
            rows.append(_l001_row(symbol, symbol.lower(), "PROCEDURAL_UPDATE", facts))
    while len(rows) < 19:
        rows.append(_l001_row("ANANTRAJ", f"x{len(rows)}", "PROCEDURAL_UPDATE", _unknown_blocks()))
    return {
        "run_id": "HG004-L001-GPT56SOL-NATIVE-v1",
        "run_sha256": EXPECTED_HG004_L001_SHA,
        "rows": rows,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _ss001() -> dict:
    rows = []
    closes = {
        "ANANTRAJ": 500.0,
        "DEVX": 36.0,
        "INOXGREEN": 160.0,
        "NPST": 1700.0,
        "SAMBHV": 160.0,
    }
    for symbol in SYMBOLS:
        rows.append({
            "symbol": symbol,
            "market": {
                "last_observed_session": "2026-10-01",
                "last_close": closes[symbol],
                "median_daily_turnover_inr": 10_000_000.0,
            },
        })
    return {
        "census_id": "SS001-D001-v1",
        "census_sha256": EXPECTED_SS001_SHA,
        "rows": rows,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _gf001() -> dict:
    rows = []
    for symbol in SYMBOLS:
        rows.append({
            "symbol": symbol,
            "latest": {
                "parser_status": "CORE_READY",
                "report_date": "2026-06-30",
                "promoter_percentage": 55.0,
                "promoter_encumbrance": {
                    "pledge": False,
                    "non_disposal_undertaking": False,
                    "other_encumbrance": False,
                },
            },
            "prior": {"report_date": "2026-03-31"},
            "ownership_delta_pp": {"promoter_percentage_points": 0.0},
        })
    return {
        "panel_id": "GF001-D002-v1",
        "panel_sha256": EXPECTED_GF001_SHA,
        "rows": rows,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _fa001() -> dict:
    return {
        "panel_id": "FA001-D002-v1",
        "panel_sha256": EXPECTED_FA001_SHA,
        "rows": [_fa_row(symbol) for symbol in SYMBOLS],
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_shareholding_parser_reads_exact_aggregate_context() -> None:
    result = parse_shareholding_counts(
        _xbrl("TEST", 100_000_000, 105_000_000),
        symbol="TEST",
    )
    assert result == {
        "fully_paid_shares": 100_000_000,
        "fully_diluted_shares": 105_000_000,
    }


def test_hg005_builds_deterministic_market_and_lane_context() -> None:
    latest = {
        "ANANTRAJ": _xbrl("ANANTRAJ", 100_000_000, 100_000_000),
        "DEVX": _xbrl("DEVX", 94_631_955, 97_965_285),
        "INOXGREEN": _xbrl("INOXGREEN", 100_000_000, 105_000_000),
        "NPST": _xbrl("NPST", 20_000_000, 20_000_000),
        "SAMBHV": _xbrl("SAMBHV", 294_671_429, 294_671_429),
    }
    prior = {
        "DEVX": _xbrl("DEVX", 90_187_515, 90_187_515),
    }
    result = build_hg005_context(
        hg004_l002=_hg004_l002(),
        hg004_l001=_hg004_l001(),
        ss001=_ss001(),
        gf001=_gf001(),
        fa001=_fa001(),
        latest_shareholding_raw=latest,
        prior_shareholding_raw=prior,
    )
    rows = {row["symbol"]: row for row in result["rows"]}

    devx = rows["DEVX"]
    dilution = next(
        lane for lane in devx["payoff_lanes"]
        if lane["economic_family"] == "DILUTION_FINANCING"
    )
    assert dilution["post_d001_state"] == "DENOMINATOR_READY"
    assert dilution["mechanical_metrics"]["event_security_count"] == 7_777_770
    assert dilution["mechanical_metrics"]["event_adjusted_fd_shares"] == 97_965_285

    sambhv = rows["SAMBHV"]
    lane = sambhv["payoff_lanes"][0]
    assert lane["mechanical_metrics"]["event_adjusted_fd_shares"] == (
        294_671_429 + 8_695_400
    )
    assert lane["mechanical_metrics"]["share_adjustment_state"] == (
        "PRO_FORMA_PENDING_POST_REPORT_APPROVAL"
    )

    inox = rows["INOXGREEN"]
    acquisition = next(
        lane for lane in inox["payoff_lanes"]
        if lane["economic_family"] == "ACQUISITION_ECONOMICS"
    )
    assert acquisition["mechanical_metrics"]["stated_consideration_inr"] == 5_500_000_000.0
    assert acquisition["post_d001_state"] == "VALUATION_INPUT_REQUIRED"

    assert result["symbol_count"] == 5
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False


def test_devx_share_reconciliation_fails_closed() -> None:
    latest = {
        "ANANTRAJ": _xbrl("ANANTRAJ", 100, 100),
        "DEVX": _xbrl("DEVX", 94_631_956, 97_965_286),
        "INOXGREEN": _xbrl("INOXGREEN", 100, 100),
        "NPST": _xbrl("NPST", 100, 100),
        "SAMBHV": _xbrl("SAMBHV", 100, 100),
    }
    prior = {"DEVX": _xbrl("DEVX", 90_187_515, 90_187_515)}
    with pytest.raises(AlphaContractError, match="paid-share reconciliation failed"):
        build_hg005_context(
            hg004_l002=_hg004_l002(),
            hg004_l001=_hg004_l001(),
            ss001=_ss001(),
            gf001=_gf001(),
            fa001=_fa001(),
            latest_shareholding_raw=latest,
            prior_shareholding_raw=prior,
        )
