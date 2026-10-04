# SS001-I001 Small-Sum Investability Policy v1

Status: **FROZEN BEFORE OPPORTUNITY DETECTOR DESIGN**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Partition the passed SS001-D001 broad NSE EQ census into deterministic liquidity
research tiers suitable for the Small-Sum Alpha program.

I001 is not a return model and does not claim that more liquid or less liquid securities
have higher expected returns.

Authoritative source:

- SS001-D001-v1;
- run: 37197575401;
- artifact: 11301695772;
- census SHA-256:
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`.

## Common history requirement

Liquidity tiers L1-L5 require:

- at least 15 observed sessions out of the frozen 20-session window;
- finite positive median daily traded value.

Securities that fail this requirement are L0.

## Frozen tiers

### L1 — highly liquid small-sum research

`median_daily_turnover_inr >= ₹10 crore`

### L2 — liquid

`₹2 crore <= median_daily_turnover_inr < ₹10 crore`

### L3 — moderate liquidity

`₹50 lakh <= median_daily_turnover_inr < ₹2 crore`

### L4 — thin but researchable

`₹20 lakh <= median_daily_turnover_inr < ₹50 lakh`

### L5 — illiquid special-watch

`median_daily_turnover_inr < ₹20 lakh`

with the common 15-session history requirement satisfied.

### L0 — source/liquidity insufficient

Fewer than 15 observed sessions, or no valid median daily traded value.

## Detector eligibility

General automated opportunity detectors may scan:

- L1;
- L2;
- L3;
- L4.

L5 is not discarded. It is reserved for:

- explicit corporate-action/special-situation detectors;
- asset-value anomalies;
- manually escalated asymmetric cases.

Any future automated L5 capital-allocation rule requires a separately frozen liquidity
and execution protocol.

L0 is excluded from automated opportunity scoring until a later source/liquidity review.

## Capital-size boundary

I001 does not hard-code a portfolio capital amount.

Later position sizing must use the actual capital base and a separately frozen execution
capacity rule based on median traded value, intended holding period and liquidation
budget.

This prevents today's census from silently assuming a particular account size.

## Scientific boundary

I001 may define research routing only.

It may not:

- assign expected returns;
- boost an opportunity because it is illiquid;
- penalize a company because it is small;
- infer market capitalization;
- authorize a trade;
- modify PF001;
- permit live capital.
