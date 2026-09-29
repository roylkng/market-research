# PO001 I003 Stock-Specific Impact Integration Snapshot v1

Status: FROZEN BEFORE MATERIALIZATION
Frozen: 2026-09-29
Live capital: DISABLED

## Objective

Measure how stock-specific TC001 square-root impact and ADV constraints change
the already frozen I002 portfolio construction result.

I003 does not open the 31-Aug five-session realized outcome.

## Decision and alpha

Decision session: 2026-08-31.
Horizon: 5 sessions.

Alpha model and purged training are identical to PO001-I002-v1:
- T003 fold 2;
- 27 features;
- ridge l2 = 1.0;
- training labels exit strictly before 2026-07-01.

## Frozen I002 reproduction hashes

Before any I003 optimizer run, the reconstructed state must equal:

- T003 fold-2 model SHA-256:
  `179ce84f40c1b6e461d2ff1f4104753381d3327b2dda35814b4a913547f91260`;
- delivery feature panel SHA-256:
  `47ee538af6cfca16405632ce6396571455a548687b4ceabfd7999040a86f8b44`;
- RM001 risk state SHA-256:
  `b1d6898f1083d752ca7db6dc7509b8ef4a2aef0f1543f24fd8b30f07604d80c1`.

A mismatch fails I003 before portfolio construction.

## Risk

RM001-v1 as of 2026-08-31.

## Execution inputs

Per security:
- median traded value over the 20 completed sessions ending 2026-08-31;
- AE001 realized_vol_20 on 2026-08-31.

Impact coefficient: 0.50.

Maximum participation per side: 10% ADV20.

Quoted spread: not included.

Observable TC001 statutory/regulatory buy/sell charges: included.

## NAV surfaces

All are frozen before materialization:

- INR 1,000,000
- INR 10,000,000  [PRIMARY]
- INR 100,000,000

No NAV surface is selected based on results.

## Portfolio parameters

Same as I002:
- risk_aversion = 5.0;
- max name weight = 5%;
- max invested weight = 100%;
- max traded fraction of NAV = 100%;
- starts from cash;
- terminal liquidation = true;
- no factor hard bounds.

## Required comparisons

For each NAV:
- PO001-v1 observable-cost optimizer;
- PO001-v2 stock-specific-impact optimizer.

Report:
- expected 5D excess;
- annualized volatility;
- invested/cash weight;
- impact cost;
- observable cost;
- holding count;
- effective number of names;
- maximum participation;
- portfolio factor exposures;
- objective utility.

## Boundaries

- no realized post-31-Aug outcome;
- no impact coefficient tuning;
- no spread proxy;
- no sector/size neutrality;
- historical-development integration only;
- live capital disabled.
