# AE001 RG001 Market Regime Context v1

Status: DEVELOPMENT CONTEXT PLANE
Frozen initial specification: 2026-10-03
Live capital: DISABLED

## Objective

Create a point-in-time session-level market context plane for AE001, AB001,
RM001 and PO001.

RG001 is not a stock-selection alpha. Every value is common to all stocks on a
session. Therefore v1 must not be naively appended as a constant stock feature
and credited with cross-sectional predictive power.

Legitimate downstream uses require separately frozen designs such as:

- regime-conditioned alpha weights;
- stock-feature × regime interactions;
- regime-conditioned risk/cost parameters;
- portfolio exposure controls.

## Source

Official AE001 market panel only:

- NSE CM EQ UDiFF;
- Nifty 500 daily index snapshot.

Historical reconstruction remains development evidence. Prospective use must
respect the actual source known-at contract.

## Dynamic breadth universe

For session D, breadth uses only exact symbol+ISIN identities with:

- the current EQ observation;
- 60 prior contiguous completed NSE sessions;
- median traded value over the prior 20 sessions >= INR 20m.

This is the same liquidity/history eligibility rule as AE001-v1.

No current Nifty membership or today's survivor list is projected backward.

## Frozen regime variables

### Benchmark state

- nifty500_return_1
- nifty500_return_5
- nifty500_return_20
- nifty500_return_60
- nifty500_realized_vol_20
- nifty500_realized_vol_60
- nifty500_drawdown_from_60d_high

### Investable breadth

- breadth_advancer_fraction_1
- breadth_positive_momentum20_fraction
- breadth_median_return_1
- breadth_return_dispersion_1
- breadth_median_turnover_surprise20

## Timing

Historical development rows use the existing AE001 market information contract:
session OHLCV/index values are treated as observable by 18:00 IST for an 18:30
EOD decision, while archive retrieval itself is historical-development evidence.

Prospective rows must use actual captured source timestamps instead.

## No outcome claim

RG001 contains no return labels, no regime label such as BULL/BEAR, and no
optimized thresholds.

Any claim that one regime predicts alpha requires a separately frozen trial.

## Deferred macro inputs

Rates, INR FX, crude oil, credit spreads and macro releases are not included in
v1 because no shared point-in-time historical source contract is frozen for them.

They may enter a later RG002 only after source/timestamp semantics are frozen.

Live capital remains disabled.
