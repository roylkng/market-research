# PO001 I001 Integrated Alpha/Risk/Cost Snapshot v1

Status: FROZEN BEFORE MATERIALIZATION
Frozen: 2026-09-29
Live capital: DISABLED

## Objective

Materialize the first end-to-end MarketLab portfolio-construction snapshot:

    frozen alpha forecast
    + RM001 risk
    + TC001 cost floor
    -> PO001 target weights

I001 is an integration study. It does not test or re-open alpha validity.

## Decision snapshot

Decision session: 2026-09-25.

Alpha horizon: 5 completed NSE sessions.

The subsequent realized 5-session outcome is not opened by I001.

## Alpha input

Frozen artifact:

`research/prospective/ae001-t004/frozen-models-v1.json`

Model:

`AE001-T004-AUGMENTED-RIDGE-v1`

Features:

- frozen 18 AE001 price/liquidity features;
- frozen nine T003 delivery/VWAP features;
- within-session tie-aware percentile transform.

The 2026-09-25 feature cross-section is reconstructed from official historical
sources using the frozen action and delivery-quality contracts.

I001 is historical-development integration evidence. It is not a T004
prospective decision and cannot enter T004's confirmatory ledger.

## Risk input

RM001-v1 historical risk state as of 2026-09-25.

Frozen risk factors:

- MARKET_COMMON;
- BETA60_RELATIVE;
- MOMENTUM20;
- VOLATILITY60;
- LIQUIDITY.

Sector and size are unavailable because point-in-time sources are not yet
frozen. No substitute sector or size proxy is introduced in I001.

## Cost input

TC001 observable cash-equity delivery cost floor only.

For every security:

- buy cost = TC001 observable BUY bps with default configuration;
- sell cost = TC001 observable SELL bps with default configuration.

No spread or market-impact scenario is embedded in the primary optimizer because
PO001-v1 accepts static per-security cost bps while TC001 impact depends on order
size/ADV. I001 does not conceal that mismatch by inserting an arbitrary static
impact number.

## Common universe

Exact symbol + ISIN identities present in BOTH:

- the 2026-09-25 T004 augmented feature cross-section;
- RM001 2026-09-25 risk state.

Minimum common identities: 500.

## Portfolio comparisons

### A. Equal-weight top decile

Top 10% of common identities by augmented expected 5D excess return.

Equal weight, fully invested.

### B. Positive-alpha proportional top decile

Same top-decile identity set.

Weights proportional to positive expected excess return, subject to the frozen
PO001 maximum name weight of 5%.

If the positive-alpha set cannot form a fully invested portfolio under the name
cap, the comparison fails closed.

### C. Risk-aware, zero transaction cost

PO001 with:

- risk_aversion = 5.0;
- all buy/sell costs = 0;
- max name weight = 0.05;
- max invested weight = 1.00;
- max traded fraction of NAV = 1.00;
- current weights = 0;
- terminal liquidation = true;
- no factor hard bounds.

### D. Full PO001 observable-cost floor

Identical to C except each security receives TC001 observable buy/sell cost bps.

## Metrics

For every portfolio:

- invested and cash weight;
- expected 5D excess return;
- daily factor variance;
- daily idiosyncratic variance;
- total daily variance;
- annualized volatility;
- RM001 factor exposures;
- immediate and terminal transaction-cost fractions;
- top holdings / concentration;
- PO001 objective utility where applicable.

## Interpretation boundaries

- no realized 5D return is opened;
- no optimizer parameter is selected based on realized outcome;
- no sector or size neutrality claim;
- no calibrated impact-cost claim;
- no prospective-alpha claim;
- no live-capital implication.

## Next gate

If I001 materializes cleanly, the next portfolio research task is a separately
frozen rolling OOS PO001 study over historical T003 walk-forward forecasts,
followed by prospective T004 portfolio decisions once sufficient T004 sessions
exist.
