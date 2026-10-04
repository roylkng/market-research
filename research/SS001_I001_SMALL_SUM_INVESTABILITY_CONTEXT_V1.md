# SS001-I001 Small-Sum Investability Context v1

Status: **FROZEN BEFORE MATERIALIZATION**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Convert the passed SS001-D001 20-session liquidity evidence into a transparent
capacity context for small-sum opportunity research.

I001 is not an alpha model and is deliberately **not** a hard universe filter. A thinly
traded company may still be economically interesting; I001 tells later underwriting how
large a position can plausibly be researched and paper-sized without pretending that a
₹20 lakh-ADV security has the same implementation characteristics as a ₹20 crore-ADV
security.

## Frozen source

Use exactly:

- SS001-D001 run: `37197575401`;
- artifact ID: `11301695772`;
- census SHA-256:
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`;
- 2,319 current NSE EQ identities;
- 20 completed-session window ending 2026-10-01.

No later market data may be substituted into I001-v1.

## Capacity-observation eligibility

A security receives liquidity/capacity surfaces only when:

- at least 15 of the frozen 20 sessions are observed;
- median daily traded value is finite and strictly positive.

Otherwise its state is `OBSERVATION_INSUFFICIENT`.

This does not remove the security from SS001 research.

## Frozen liquidity bands

Based only on median daily traded value over the frozen 20-session window:

- `L1_10CR_PLUS`: >= INR 10 crore;
- `L2_5_TO_10CR`: >= INR 5 crore and < INR 10 crore;
- `L3_2_TO_5CR`: >= INR 2 crore and < INR 5 crore;
- `L4_1_TO_2CR`: >= INR 1 crore and < INR 2 crore;
- `L5_20L_TO_1CR`: >= INR 20 lakh and < INR 1 crore;
- `L6_BELOW_20L`: > 0 and < INR 20 lakh;
- `OBSERVATION_INSUFFICIENT`: source rule above fails.

These bands are operational descriptors, not expected-return ranks.

## Frozen participation surfaces

For each capacity-observable security report one-day notional capacity at:

- 2.5% of median ADV;
- 5% of median ADV;
- 10% of median ADV.

`one_day_capacity = median_daily_turnover_inr * participation_rate`

The 10% surface is the same broad participation ceiling used in existing PO001-I003
research, but I001 does not claim that 10% is executable without impact.

## Frozen order-size surfaces

For each capacity-observable security report linear execution days at 5% median-ADV
participation for order sizes:

- INR 5 lakh;
- INR 10 lakh;
- INR 25 lakh;
- INR 50 lakh;
- INR 1 crore.

`days_at_5pct = order_notional / (0.05 * median_daily_turnover_inr)`

This is a capacity arithmetic surface only. It is not a transaction-cost estimate.

## Searchability versus implementability

All 2,319 SS001-D001 identities remain searchable by later opportunity detectors.

I001 may label:

- `RESEARCH_AND_CAPACITY_CONTEXT_AVAILABLE`; or
- `RESEARCH_ONLY_CAPACITY_UNRESOLVED`.

I001 may not reject a company because of liquidity.

Any later portfolio stage must separately combine:

- proposed position notional;
- participation;
- volatility;
- spread;
- TC001 impact/cost;
- exit horizon.

## Output

One row per D001 identity containing:

- symbol and ISIN;
- D001 observed-session count;
- median daily turnover;
- liquidity band;
- one-day capacity at 2.5%, 5% and 10%;
- 5%-participation execution-day surfaces;
- existing U001 overlap;
- research/capacity state.

## Scientific boundary

I001 does not:

- use future returns;
- infer market attractiveness from liquidity;
- tune bands on performance;
- exclude small or illiquid securities from SS001 discovery;
- estimate market impact;
- create a hidden-gem score;
- create ADO/PF001 eligibility;
- authorize live capital.

Later execution underwriting should reuse TC001 rather than mutate I001.
