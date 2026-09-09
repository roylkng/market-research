"""Outcome-blind raw financial features for H019 design coverage.

These features are source-derived inputs only. This module deliberately contains no
portfolio score, selection count, return label, or pass/fail threshold.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass

from h019_financials import QuarterlyFinancials


class H019FeatureError(ValueError):
    """A candidate cannot satisfy the frozen H019 feature-construction contract."""


@dataclass(frozen=True)
class H019RawFeatures:
    latest_ttm_revenue: float
    prior_ttm_revenue: float
    ttm_revenue_growth: float
    latest_ttm_pat: float
    prior_ttm_pat: float
    latest_ttm_pre_exception_pretax_profit: float
    prior_ttm_pre_exception_pretax_profit: float
    latest_net_margin: float
    prior_net_margin: float
    net_margin_change: float
    latest_pre_exception_pretax_margin: float
    prior_pre_exception_pretax_margin: float
    pre_exception_pretax_margin_change: float
    positive_pat_quarter_ratio: float
    positive_eps_quarter_ratio: float
    net_margin_std_8q: float
    eps_variability_ratio_8q: float
    revenue_growth_acceleration: float
    net_margin_improvement_acceleration: float
    pre_exception_pretax_margin_improvement_acceleration: float
    latest_share_count: float
    share_count_change_8q: float
    decision_close: float
    provisional_market_cap: float
    provisional_earnings_yield: float
    provisional_sales_yield: float
    provisional_eps_yield: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def _mean(values: list[float]) -> float:
    return float(statistics.fmean(values))


def _sum(values: list[float]) -> float:
    return float(math.fsum(values))


def build_raw_features(
    quarters: list[QuarterlyFinancials],
    *,
    decision_close: float,
) -> H019RawFeatures:
    """Build raw H019 features from exactly eight chronological reported quarters."""
    if len(quarters) != 8:
        raise H019FeatureError(f"H019 requires exactly eight quarters; found {len(quarters)}")
    if any(quarters[index].quarter_end >= quarters[index + 1].quarter_end for index in range(7)):
        raise H019FeatureError("H019 quarters must be strictly chronological")
    if not math.isfinite(decision_close) or decision_close <= 0:
        raise H019FeatureError("H019 decision close must be finite and positive")

    revenues = [float(row.revenue) for row in quarters]
    pats = [float(row.profit_after_tax) for row in quarters]
    pretax = [float(row.pre_exception_pretax_profit) for row in quarters]
    eps = [float(row.basic_eps) for row in quarters]
    share_counts = [float(row.share_count) for row in quarters]
    if not all(math.isfinite(value) for value in revenues + pats + pretax + eps + share_counts):
        raise H019FeatureError("H019 quarterly primitives must be finite")
    if min(revenues) <= 0 or min(share_counts) <= 0:
        raise H019FeatureError("H019 revenue and share count must stay positive")

    margins = [pat / revenue for pat, revenue in zip(pats, revenues, strict=True)]
    pretax_margins = [value / revenue for value, revenue in zip(pretax, revenues, strict=True)]

    prior_revenue = _sum(revenues[:4])
    latest_revenue = _sum(revenues[4:])
    prior_pat = _sum(pats[:4])
    latest_pat = _sum(pats[4:])
    prior_pretax = _sum(pretax[:4])
    latest_pretax = _sum(pretax[4:])
    if prior_revenue <= 0 or latest_revenue <= 0:
        raise H019FeatureError("H019 TTM revenue must be positive")

    revenue_yoy = [revenues[index] / revenues[index - 4] - 1.0 for index in range(4, 8)]
    margin_yoy_delta = [margins[index] - margins[index - 4] for index in range(4, 8)]
    pretax_margin_yoy_delta = [
        pretax_margins[index] - pretax_margins[index - 4] for index in range(4, 8)
    ]

    eps_abs_mean = _mean([abs(value) for value in eps])
    eps_std = float(statistics.pstdev(eps))
    eps_variability = eps_std / max(eps_abs_mean, 1e-12)

    latest_share_count = share_counts[-1]
    provisional_market_cap = decision_close * latest_share_count
    if not math.isfinite(provisional_market_cap) or provisional_market_cap <= 0:
        raise H019FeatureError("H019 provisional market cap must be finite and positive")

    latest_net_margin = latest_pat / latest_revenue
    prior_net_margin = prior_pat / prior_revenue
    latest_pretax_margin = latest_pretax / latest_revenue
    prior_pretax_margin = prior_pretax / prior_revenue
    ttm_eps = _sum(eps[4:])

    return H019RawFeatures(
        latest_ttm_revenue=latest_revenue,
        prior_ttm_revenue=prior_revenue,
        ttm_revenue_growth=latest_revenue / prior_revenue - 1.0,
        latest_ttm_pat=latest_pat,
        prior_ttm_pat=prior_pat,
        latest_ttm_pre_exception_pretax_profit=latest_pretax,
        prior_ttm_pre_exception_pretax_profit=prior_pretax,
        latest_net_margin=latest_net_margin,
        prior_net_margin=prior_net_margin,
        net_margin_change=latest_net_margin - prior_net_margin,
        latest_pre_exception_pretax_margin=latest_pretax_margin,
        prior_pre_exception_pretax_margin=prior_pretax_margin,
        pre_exception_pretax_margin_change=latest_pretax_margin - prior_pretax_margin,
        positive_pat_quarter_ratio=sum(value > 0 for value in pats) / 8.0,
        positive_eps_quarter_ratio=sum(value > 0 for value in eps) / 8.0,
        net_margin_std_8q=float(statistics.pstdev(margins)),
        eps_variability_ratio_8q=eps_variability,
        revenue_growth_acceleration=_mean(revenue_yoy[2:]) - _mean(revenue_yoy[:2]),
        net_margin_improvement_acceleration=_mean(margin_yoy_delta[2:])
        - _mean(margin_yoy_delta[:2]),
        pre_exception_pretax_margin_improvement_acceleration=_mean(
            pretax_margin_yoy_delta[2:]
        )
        - _mean(pretax_margin_yoy_delta[:2]),
        latest_share_count=latest_share_count,
        share_count_change_8q=latest_share_count / share_counts[0] - 1.0,
        decision_close=decision_close,
        provisional_market_cap=provisional_market_cap,
        provisional_earnings_yield=latest_pat / provisional_market_cap,
        provisional_sales_yield=latest_revenue / provisional_market_cap,
        provisional_eps_yield=ttm_eps / decision_close,
    )
