# PO001 I006 RG001 Active-Risk Volatility Scaling v1

Status: FROZEN BEFORE I006 OUTCOME MATERIALIZATION
Frozen: 2026-10-03
Live capital: DISABLED

## Objective

Test whether the already-frozen RG001 market-volatility context improves the
realized risk-adjusted performance of the strongest sealed 5-session alpha
family without changing stock selection.

The alpha family is AB001 P003 FUTURES_DELTA.

I006 does NOT:
- refit alpha;
- choose between alpha families;
- change stock ranks;
- use the failed P004 regime selector;
- tune a threshold from outcomes.

RG001 is used only as a portfolio active-risk scaler.

## Frozen sources

### Alpha / outcome source

Sealed AB001 P003:

- run: 36703199954;
- report SHA-256:
  0d833a280dcc741ebba13bfe8b753689b7ff1ad41f0b2c13181fd8b0c37552c6;
- library SHA-256:
  4e04142bb3b33ca9f1c86de456bed1e5479d7d6c89bd72e59bff14b5c713ec36;
- horizon: 5 completed NSE sessions;
- alpha:
  AB001-P003-FUTURES-DELTA.

Only sealed OOS P003 records may enter I006.

### Regime source

Sealed RG001 panel used by P004:

- panel SHA-256:
  7921fb8db899016f73162d33642b916db71c5b65768d530a47d50c7c06a562f6;
- context variable:
  nifty500_realized_vol_20.

No other RG001 variable is used in I006.

## Portfolio construction

For each eligible P003 decision session t:

1. rank FUTURES_DELTA by its sealed normalized score;
2. select the top 10% of exact symbol+ISIN rows;
3. compute the equal-weight mean sealed 5-session benchmark-relative excess
   return of that top-decile cohort.

Call this active-sleeve return:

    r_t

The CONTROL portfolio allocates:

    100% active FUTURES_DELTA sleeve
    0% Nifty 500 benchmark sleeve

Therefore control benchmark-relative return is:

    r_control,t = r_t

The TREATMENT portfolio allocates:

    m_t active FUTURES_DELTA sleeve
    (1 - m_t) Nifty 500 benchmark sleeve

Therefore treatment benchmark-relative return is exactly:

    r_treatment,t = m_t * r_t

No cash-return assumption is required.

## Frozen volatility scaler

Current context:

    vol_t = RG001 nifty500_realized_vol_20 on t

Reference volatility:

    ref_t = median(
        nifty500_realized_vol_20 over the 60 RG001 sessions
        strictly before t
    )

Minimum prior RG001 sessions:

    60

Exposure multiplier:

    m_t = min(1.0, ref_t / vol_t)

Requirements:

- vol_t > 0;
- ref_t > 0;
- no leverage;
- no minimum exposure floor;
- no clipping other than the upper bound 1.0;
- current session is excluded from ref_t;
- no return outcome enters m_t.

Sessions lacking 60 prior RG001 rows are excluded rather than backfilled.

## Primary endpoint

Frozen realized active-utility coefficient:

    gamma = 5.0

For a realized 5-session benchmark-relative excess r:

    utility(r) = r - gamma * r^2

Control:

    u_control,t = utility(r_t)

Treatment:

    u_treatment,t = utility(m_t * r_t)

Paired daily difference:

    delta_u_t = u_treatment,t - u_control,t

Inference:

- Newey-West;
- lag = 4, matching overlapping 5-session labels.

Primary support requires BOTH:

- mean(delta_u) > 0;
- two-sided p < 0.05.

No alternate gamma is tested under I006.

## Secondary endpoints

Paired Newey-West lag 4:

- treatment minus control mean 5D excess return;
- treatment minus control mean squared 5D excess return;
- treatment minus control mean absolute 5D excess return.

Descriptive:

- eligible session count;
- mean/median/min exposure multiplier;
- fraction of sessions scaled below 1;
- mean multiplier by current-volatility quartile;
- control/treatment mean return;
- control/treatment standard deviation;
- control/treatment 10th percentile;
- control/treatment worst cohort return.

Secondary endpoints cannot rescue a failed primary endpoint.

## Costs

I006 primary evidence is gross benchmark-relative portfolio-overlay evidence.

It does not estimate:
- rolling turnover;
- benchmark-sleeve transaction cost;
- stock-level impact;
- overlapping-cohort capital accounting.

Therefore I006 cannot claim implementable portfolio P&L.

A supported result would justify a separately frozen rolling portfolio/cost study.

## Evidence class

HISTORICAL_KNOWN_OUTCOME_PORTFOLIO_CONTEXT_DIAGNOSTIC

P003 outcomes were already known before I006 was designed.

I006 is not an independent discovery test and cannot establish prospective
regime value.

## Interpretation

If supported:
- RG001 vol20 may be promoted as a portfolio active-risk context candidate;
- do not promote P004's alpha selector;
- next gate is a separately frozen rolling/cost-aware overlay study.

If unsupported:
- do not retune the same scaler under I006;
- RG001 remains available for descriptive risk context;
- any revised portfolio rule requires a new trial ID.

No live-capital implication.
