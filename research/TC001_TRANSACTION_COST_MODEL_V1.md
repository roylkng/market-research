# TC001 Indian Cash Equity Transaction-Cost Model v1

Status: DEVELOPMENT BASELINE
Frozen initial specification: 2026-09-29
Live capital: DISABLED

## Objective

Estimate implementable transaction costs for NSE cash-equity delivery strategies
without collapsing known statutory charges and uncertain execution impact into
one arbitrary basis-point haircut.

TC001 v1 is a research/capacity model. It is not a broker bill calculator and it
does not authorize live trading.

## Scope

Instrument class:

- NSE cash-market equity;
- delivery settlement;
- long-only research portfolios;
- buy and sell notionals modeled separately.

Out of scope for v1:

- intraday/non-delivery equity;
- futures/options;
- securities lending/shorting;
- financing;
- capital-gains or income tax;
- exchange rebates;
- broker-specific fee caps unless supplied explicitly.

## Observable charge layer

Rates are frozen from current NSE public schedules as of 2026-09-29.

### Securities Transaction Tax

Delivery equity:

- buy: 0.100% of taxable transaction value;
- sell: 0.100%.

TC001 representation:

- buy STT = 10.0 bps;
- sell STT = 10.0 bps.

### Stamp duty

Delivery equity:

- buy only: 0.015%;
- sell: 0.

TC001 representation:

- buy stamp = 1.5 bps.

### NSE cash-market transaction charge and IPFT

Effective 2026-03-01:

- transaction charge = INR 306.99 per crore per side;
- NSE IPFT = INR 0.01 per crore per side;
- total = INR 307 per crore per side.

TC001 retains transaction charge and IPFT as separate line items.

### SEBI turnover fee

Non-debt purchase and sale:

- INR 10 per crore per side;
- equivalent to 0.01 bps per side.

### GST

NSE publishes GST of 18% for stock-broker services.

TC001 v1 uses an explicit operational convention:

GST taxable variable charge base =
brokerage + NSE transaction charge + NSE IPFT + SEBI turnover fee.

This base convention is an implementation assumption and is separately exposed
in the model. It must not be interpreted as legal or tax advice.

A broker-specific DP sell charge can optionally be modeled as a fixed INR
amount. Whether GST is applied to the DP charge is separately configurable.

### Brokerage

Brokerage is not frozen to one broker.

Inputs support:

- brokerage bps per buy;
- brokerage bps per sell.

Any broker-specific minimum/cap remains outside v1 unless encoded by the caller.

### DP charge

Optional fixed INR sell-side charge per security transaction.

Because fixed charges have notional-dependent basis-point impact, TC001 reports
both INR and effective bps.

## Execution-friction layer

### Spread

Input:

- half-spread bps per side.

The caller supplies a stock/session-specific or scenario value.

### Market impact

TC001 v1 uses a transparent square-root scenario model:

impact_bps_per_side =
impact_coefficient
* daily_volatility_decimal
* 10,000
* sqrt(order_notional / ADV20)

where ADV20 is the trailing twenty-session median or mean traded value chosen by
the caller, in the same currency as order_notional.

This is a sensitivity model, not a calibrated law of NSE execution.

Initial scenario coefficients:

- LOW: 0.25
- BASE: 0.50
- HIGH: 1.00

The coefficient is deliberately external to the strategy and no historical alpha
result may be used to select a more favorable coefficient.

Participation is capped at 100% for model validity. Research workflows should
normally impose a much smaller operational cap.

## Side cost

For each side:

all_in_cost =
statutory/regulatory charges
+ brokerage
+ optional DP charge
+ half-spread
+ modeled market impact.

TC001 reports:

- individual line items in INR;
- individual line items in bps;
- side total;
- equal-notional round-trip total.

## Portfolio turnover

TC001 distinguishes three concepts.

### Buy turnover fraction

Fraction of portfolio NAV purchased during a rebalance.

### Sell turnover fraction

Fraction of portfolio NAV sold during a rebalance.

Portfolio cost is:

buy_fraction * buy_cost_bps
+ sell_fraction * sell_cost_bps.

### Equal-weight replacement fraction

For a fixed-size equal-weight basket, replacing fraction r of names implies:

- r of NAV sold;
- r of NAV bought.

The approximate portfolio cost is therefore:

r * (buy_cost_bps + sell_cost_bps).

This is the correct mapping for AE001's current top-decile selection-churn
diagnostic only under equal weights and unchanged weights for surviving names.
Selection churn is not silently relabeled as general portfolio turnover.

## Capacity

For equal-notional entry/exit and symmetric spread/impact assumptions, TC001 can
solve the maximum participation rate such that:

gross_alpha_bps
- non_impact_round_trip_cost_bps
- round_trip_market_impact_bps
>= required_net_alpha_bps.

The resulting participation rate is a scenario capacity bound, not a guaranteed
execution capacity.

## Research interpretation

A signal is not "implementable" merely because gross cross-sectional spread
exceeds TC001 cost.

Portfolio construction, risk, execution timing, tax treatment, and capacity
still matter.

TC001 is the cost layer required before PO001 can promote an alpha family into a
paper portfolio challenger.

## Frozen current official-rate references

- NSE SEBI Turnover Fees, STT and Other Levies, updated 2026-04-17.
- NSE/FA/73061 dated 2026-02-27, effective 2026-03-01.

## Live capital

Disabled.
