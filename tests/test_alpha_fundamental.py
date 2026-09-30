from dataclasses import replace

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_fundamental import (
    FundamentalPair,
    FilingCandidate,
    build_fundamental_features,
    monetary_scale,
    pair_record,
    select_fundamental_pair,
)
from marketlab.events import (
    HISTORICAL_RECONSTRUCTION,
    PARSER_VERSION,
    XBRL_PARSER_VERSION,
    FinancialEvent,
    SourceProvenance,
)


def _row(*, period, time, basis="Consolidated", url="https://x/a.xml"):
    return {
        "type": "Integrated Filing- Financials",
        "symbol": "TEST",
        "cmName": "Test Ltd",
        "consolidated": basis,
        "qe_Date": period,
        "broadcast_Date": time,
        "xbrl": url,
    }


def test_pair_uses_first_target_and_latest_baseline_known_before_target():
    payload = {
        "data": [
            _row(
                period="30-Jun-2025",
                time="20-Jul-2025 10:00:00",
                url="https://x/base-old.xml",
            ),
            _row(
                period="30-Jun-2025",
                time="21-Jul-2025 10:00:00",
                url="https://x/base-new.xml",
            ),
            _row(
                period="30-Jun-2026",
                time="20-Jul-2026 12:00:00",
                url="https://x/target-first.xml",
            ),
            _row(
                period="30-Jun-2026",
                time="21-Jul-2026 12:00:00",
                url="https://x/target-revision.xml",
            ),
        ]
    }
    pair = select_fundamental_pair(payload, symbol="TEST")
    assert pair.target.source_url.endswith("target-first.xml")
    assert pair.baseline.source_url.endswith("base-new.xml")
    assert (
        pair.baseline.exchange_published_at_utc
        < pair.target.exchange_published_at_utc
    )


def test_pair_falls_back_to_standalone_only_when_consolidated_pair_missing():
    payload = {
        "data": [
            _row(
                period="30-Jun-2026",
                time="20-Jul-2026 12:00:00",
                basis="Consolidated",
                url="https://x/current-con.xml",
            ),
            _row(
                period="30-Jun-2025",
                time="20-Jul-2025 12:00:00",
                basis="Standalone",
                url="https://x/base-sa.xml",
            ),
            _row(
                period="30-Jun-2026",
                time="20-Jul-2026 11:00:00",
                basis="Standalone",
                url="https://x/current-sa.xml",
            ),
        ]
    }
    pair = select_fundamental_pair(payload, symbol="TEST")
    assert pair.accounting_basis == "Standalone"


def test_pair_rejects_same_timestamp_different_target_urls():
    payload = {
        "data": [
            _row(
                period="30-Jun-2025",
                time="20-Jul-2025 12:00:00",
                url="https://x/base.xml",
            ),
            _row(
                period="30-Jun-2026",
                time="20-Jul-2026 12:00:00",
                url="https://x/a.xml",
            ),
            _row(
                period="30-Jun-2026",
                time="20-Jul-2026 12:00:00",
                url="https://x/b.xml",
            ),
        ]
    }
    with pytest.raises(AlphaContractError, match="ambiguous"):
        select_fundamental_pair(payload, symbol="TEST")


def _event(
    *,
    parser=XBRL_PARSER_VERSION,
    period="2026-06-30",
    revenue=120.0,
    pbt=18.0,
    profit=12.0,
    rounding="Crores",
):
    return FinancialEvent(
        schema_version=1,
        parser_version=parser,
        mode=HISTORICAL_RECONSTRUCTION,
        economic_event_id="e",
        version_id="v",
        symbol="TEST",
        isin="INE000000001",
        company_name="Test Ltd",
        financial_year_start=None,
        financial_year_end=None,
        reporting_period_start=None,
        reporting_period_end=period,
        reporting_type="Quarterly",
        reporting_quarter="First quarter",
        accounting_basis="Consolidated",
        audited=False,
        board_approval_date=None,
        prior_intimation_date=None,
        currency="INR",
        rounding=rounding,
        revenue_from_operations=revenue,
        profit_before_exceptional_items_and_tax=None,
        exceptional_items=1.0,
        profit_before_tax=pbt,
        net_profit_continuing_operations=None,
        total_profit=profit,
        basic_eps=None,
        diluted_eps=None,
        operating_profit=None,
        operating_margin=None,
        unresolved_fields=(),
        provenance=SourceProvenance(
            source_url="https://x/test.xml",
            captured_at_utc="2026-09-30T00:00:00Z",
            raw_sha256="a" * 64,
            raw_path="x",
            content_type="application/xml",
            source_mode="NSE_INTEGRATED_FILING_XBRL",
        ),
    )


def test_xbrl_amounts_are_not_rescaled_by_presentation_rounding():
    assert monetary_scale(_event()) == 1.0


def test_html_crore_values_are_scaled_to_inr():
    html = _event(parser=PARSER_VERSION)
    assert monetary_scale(html) == 10_000_000.0


def test_fundamental_features_match_frozen_formulas():
    baseline = _event(
        period="2025-06-30",
        revenue=100.0,
        pbt=10.0,
        profit=8.0,
    )
    target = _event(
        revenue=120.0,
        pbt=18.0,
        profit=12.0,
    )
    features = build_fundamental_features(
        target_event=target,
        baseline_event=baseline,
    )
    assert features["revenue_yoy"] == pytest.approx(0.20)
    assert features["pbt_change_to_prior_revenue"] == pytest.approx(0.08)
    assert features[
        "total_profit_change_to_prior_revenue"
    ] == pytest.approx(0.04)
    assert features["pbt_margin"] == pytest.approx(0.15)
    assert features["pbt_margin_delta_yoy"] == pytest.approx(0.05)
    assert features["total_profit_margin_delta_yoy"] == pytest.approx(0.02)


def test_unknown_html_rounding_fails_closed():
    with pytest.raises(AlphaContractError, match="rounding"):
        monetary_scale(_event(parser=PARSER_VERSION, rounding="Mystery"))


def test_non_inr_fails_closed():
    event = replace(_event(), currency="USD")
    with pytest.raises(AlphaContractError, match="currency"):
        monetary_scale(event)



def test_fundamental_features_support_nondefault_quarter_pair():
    baseline = _event(
        period="2024-09-30",
        revenue=80.0,
        pbt=8.0,
        profit=6.0,
    )
    target = _event(
        period="2025-09-30",
        revenue=100.0,
        pbt=12.0,
        profit=9.0,
    )
    features = build_fundamental_features(
        target_event=target,
        baseline_event=baseline,
        target_period_end="2025-09-30",
        baseline_period_end="2024-09-30",
    )
    assert features["revenue_yoy"] == pytest.approx(0.25)
    assert features["pbt_margin"] == pytest.approx(0.12)


def test_pair_record_binds_diagnostic_and_period_pair():
    target_candidate = FilingCandidate(
        symbol="TEST",
        accounting_basis="Consolidated",
        period_end="2025-09-30",
        exchange_published_at_utc="2025-10-20T06:30:00Z",
        source_url="https://x/target.xml",
        discovery_row_sha256="a" * 64,
        discovery_row={},
    )
    baseline_candidate = FilingCandidate(
        symbol="TEST",
        accounting_basis="Consolidated",
        period_end="2024-09-30",
        exchange_published_at_utc="2024-10-20T06:30:00Z",
        source_url="https://x/base.xml",
        discovery_row_sha256="b" * 64,
        discovery_row={},
    )
    pair = FundamentalPair(
        symbol="TEST",
        accounting_basis="Consolidated",
        target=target_candidate,
        baseline=baseline_candidate,
    )
    target = _event(period="2025-09-30")
    baseline = _event(period="2024-09-30", revenue=100.0, pbt=10.0, profit=8.0)
    record = pair_record(
        pair=pair,
        target_event=target,
        baseline_event=baseline,
        discovery_raw_sha256="c" * 64,
        diagnostic_id="AE001-T008-D002-v1",
    )
    assert record["diagnostic_id"] == "AE001-T008-D002-v1"
    assert record["target_period_end"] == "2025-09-30"
    assert record["baseline_period_end"] == "2024-09-30"
