# PO001 I004 Futures Increment Under Size Risk and Capacity v1

Status: FROZEN BEFORE MATERIALIZATION
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Measure whether the T005 stock-futures information increment changes the
portfolio after applying:

- RM001-v2 total-market-cap SIZE risk;
- TC001 observable delivery-equity charges;
- PO001-v2 stock-specific square-root impact;
- the frozen 10% ADV20 participation cap.

I004 is an outcome-blind integration study. T005 outcomes were already known
before I004 was designed, so I004 cannot create an independent alpha-validity
claim.

## Decision snapshot

Decision session: 2026-08-31.

Horizon: 5 completed NSE sessions.

No realized post-2026-08-31 five-session return may be loaded, calculated or
reported by I004.

## Alpha models

Reconstruct the exact T005 / AB001-P003 fold-2 OOS models.

Validation fold:

    2026-07-01 through 2026-09-18

Training:

- exact futures-complete rows;
- purged so every training label matures strictly before 2026-07-01;
- ridge l2 = 1.0.

### CORE27

Frozen 27 price/liquidity/delivery features.

### FULL37

CORE27 plus the exact ten T005 futures features.

I004 compares the raw expected 5D excess-return forecasts from these two
independently fitted fold-2 ridge models.

The model reconstruction must first reproduce the sealed T005 5D aggregate
result under the existing AB001-P003 tolerance.

No alpha coefficient may be tuned by I004.

## Risk

RM001-v2 total-market-cap SIZE risk state as of 2026-08-31.

Frozen factors:

- MARKET_COMMON;
- BETA60_RELATIVE;
- MOMENTUM20;
- VOLATILITY60;
- LIQUIDITY;
- SIZE.

Sector remains unavailable because a point-in-time company-industry source is
not frozen.

The exact common symbol+ISIN universe is used for both CORE27 and FULL37.

## Execution

PO001-v2 / TC001 frozen execution contract:

- risk aversion = 5.0;
- max name weight = 5%;
- max invested weight = 100%;
- max traded fraction of NAV = 100%;
- current weights = zero;
- terminal liquidation = true;
- observable TC001 buy/sell charges;
- square-root impact coefficient k = 0.50;
- maximum participation per side = 10% ADV20;
- ADV20 = median traded value over the latest 20 completed sessions including
  the decision session;
- daily volatility = AE001 realized_vol_20;
- no quoted-spread proxy;
- no calibrated impact claim.

NAV surfaces:

- INR 1,000,000;
- INR 10,000,000 primary;
- INR 100,000,000.

## Common-row contract

One stock enters I004 only if it has:

- the exact same symbol+ISIN in the CORE27 and FULL37 decision rows;
- a valid RM001-v2 risk row;
- 20 contiguous traded-value observations through 2026-08-31;
- finite positive ADV20;
- finite non-negative realized_vol_20.

Minimum common identities: 100.

Both alpha treatments must optimize the exact same identity set.

## Comparisons

For each NAV, report:

- CORE27 PO001-v2 portfolio;
- FULL37 PO001-v2 portfolio;
- FULL37 minus CORE27 deltas for:
  - expected 5D excess return;
  - annualized volatility;
  - immediate/terminal impact cost;
  - total transaction cost;
  - objective utility;
  - invested weight;
  - holding count;
  - maximum observed participation;
  - RM001-v2 factor exposures, including SIZE;
  - target-weight overlap and L1 turnover distance between the two portfolios.

## Interpretation

I004 answers:

> Does the already-discovered futures information increment survive portfolio
> risk and capacity mechanics at the frozen decision snapshot?

It does NOT answer:

- whether T005 is prospectively valid;
- whether T006 will succeed;
- whether market impact is calibrated;
- whether SIZE is prospectively source-ready;
- whether realized portfolio P&L improves.

Prospective confirmation remains separate:

- T006 under its frozen 18:30 contract;
- SC003 evidence for a possible future pre-open successor;
- RM001-SC001 evidence for prospective SIZE timing.

Live capital remains disabled.
