import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import h019_features as features
from h019_financials import QuarterlyFinancials


def quarter(index: int, *, revenue: float, margin: float, eps: float, shares: float) -> QuarterlyFinancials:
    dates = (
        date(2021, 3, 31), date(2021, 6, 30), date(2021, 9, 30), date(2021, 12, 31),
        date(2022, 3, 31), date(2022, 6, 30), date(2022, 9, 30), date(2022, 12, 31),
    )
    pat = revenue * margin
    return QuarterlyFinancials(
        quarter_end=dates[index],
        revenue=revenue,
        profit_after_tax=pat,
        pre_exception_pretax_profit=pat * 1.25,
        basic_eps=eps,
        paid_up_equity_share_capital=shares * 10,
        face_value_per_share=10,
        share_count=shares,
    )


def test_raw_features_measure_level_growth_value_and_inflection() -> None:
    rows = []
    revenues = [100, 100, 100, 100, 110, 115, 130, 140]
    margins = [0.08, 0.08, 0.08, 0.08, 0.09, 0.09, 0.11, 0.12]
    for index, (revenue, margin) in enumerate(zip(revenues, margins, strict=True)):
        rows.append(quarter(index, revenue=revenue, margin=margin, eps=2 + index * 0.2, shares=10))
    raw = features.build_raw_features(rows, decision_close=100)
    assert raw.prior_ttm_revenue == 400
    assert raw.latest_ttm_revenue == 495
    assert raw.ttm_revenue_growth == pytest.approx(0.2375)
    assert raw.latest_net_margin > raw.prior_net_margin
    assert raw.net_margin_change > 0
    assert raw.revenue_growth_acceleration > 0
    assert raw.net_margin_improvement_acceleration > 0
    assert raw.positive_pat_quarter_ratio == 1
    assert raw.positive_eps_quarter_ratio == 1
    assert raw.provisional_market_cap == 1000
    assert raw.provisional_sales_yield == pytest.approx(0.495)
    assert raw.share_count_change_8q == 0


def test_negative_profit_is_retained_not_dropped() -> None:
    rows = [quarter(i, revenue=100, margin=-0.02 if i < 2 else 0.05, eps=-1 if i < 2 else 1, shares=10) for i in range(8)]
    raw = features.build_raw_features(rows, decision_close=50)
    assert raw.positive_pat_quarter_ratio == 0.75
    assert raw.positive_eps_quarter_ratio == 0.75


def test_exactly_eight_quarters_required() -> None:
    rows = [quarter(i, revenue=100, margin=0.05, eps=1, shares=10) for i in range(7)]
    with pytest.raises(features.H019FeatureError, match="exactly eight"):
        features.build_raw_features(rows, decision_close=50)


def test_quarters_must_be_chronological() -> None:
    rows = [quarter(i, revenue=100, margin=0.05, eps=1, shares=10) for i in range(8)]
    rows[4], rows[5] = rows[5], rows[4]
    with pytest.raises(features.H019FeatureError, match="chronological"):
        features.build_raw_features(rows, decision_close=50)


def test_decision_price_must_be_positive() -> None:
    rows = [quarter(i, revenue=100, margin=0.05, eps=1, shares=10) for i in range(8)]
    with pytest.raises(features.H019FeatureError, match="decision close"):
        features.build_raw_features(rows, decision_close=0)
