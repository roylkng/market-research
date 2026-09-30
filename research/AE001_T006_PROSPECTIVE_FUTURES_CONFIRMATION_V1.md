# AE001 T006 Prospective Stock-Futures Confirmation v1

Status: FROZEN BEFORE FIRST ELIGIBLE DECISION SESSION
Frozen: 2026-09-30
Earliest eligible decision date: 2026-10-01
Live capital: DISABLED

## Objective

Prospectively confirm whether the ten NSE stock-futures positioning/term-structure
features discovered in T005 add 5-session cross-sectional predictive information
beyond the frozen 27-feature price/liquidity/delivery model.

T006 is the prospective confirmation of T005. It does not reinterpret T005.

## Primary hypothesis

On future eligible NSE decision sessions:

    FULL37 fixed model
    minus
    CORE27 fixed model

has positive incremental 5-session:

1. daily cross-sectional rank IC;
2. top-minus-bottom-decile excess-return spread.

Primary success requires BOTH paired differences to be > 0 with two-sided
Newey-West p < 0.05.

## Earliest eligible decision session

2026-10-01 or later.

September 30 may be used by SC001/SC002 as source-timing evidence only. It may
not enter T006 predictions or outcomes.

No earlier date may be backfilled.

## Decision cutoff

18:30:00 Asia/Kolkata.

## Dual source-timing gate

A T006 decision session is eligible only when BOTH conditions hold for the same
session:

### SC001

`research/prospective/ae001-sc001/source-ledger.json`

contains an attempt with:

`eligible_before_cutoff = true`

This proves same-session cash UDiFF and delivery evidence were captured and
validated by the cutoff.

### SC002

`research/prospective/ae001-sc002/source-ledger.json`

contains an attempt with:

`eligible_before_cutoff = true`

This proves same-session FO UDiFF stock-futures evidence was captured and
validated by the cutoff.

A missing, delayed or failed probe in either ledger makes that date ineligible.
No retrospective source acquisition may repair it.

## Frozen feature families

### Base CORE27

Exact merged AE001 feature set:

- 18 price/liquidity features;
- nine T003 delivery/VWAP features.

### Augmented FULL37

CORE27 plus exact ten T005 stock-futures features:

- fut_front_basis
- fut_front_log_basis_per_day
- fut_next_log_basis_per_day
- fut_curve_slope_per_day
- fut_front_oi_change_fraction
- fut_total_oi_change_fraction
- fut_front_oi_share
- fut_total_volume_to_oi
- fut_notional_to_cash_turnover
- fut_front_settlement_return_1

No feature definition may change after the first eligible T006 decision.

## Fixed models

Both models:

- ridge regression;
- l2 = 1.0;
- within-session tie-aware percentile inputs;
- trained once before T006 begins;
- immutable during the confirmatory period.

Base and augmented models are fit on identical historical futures-complete rows.

The frozen model artifact is created under T006-P1 before October 1.

No prospective T006 outcome may alter coefficients, scaling, feature ordering,
imputation or hyperparameters.

## Historical training source

Source window ends 2026-09-25.

Training target:

5 completed NSE-session excess return versus Nifty 500, from next-session open
through holding-session-5 close.

Only examples whose 5-session exit is on or before 2026-09-25 may enter
training.

Historical source lineage must reproduce the sealed T005 chain:

- market panel:
  9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e
- action-safe base feature panel:
  300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8
- corporate-action ledger:
  1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1
- delivery 27-feature panel:
  99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90
- futures source panel:
  02656c828a1d5fe22660c154a445ebd69a7492b56f1807da0d8c959a6f0c11d5
- futures 37-feature panel:
  62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f

## Prospective common-row contract

For a future decision session, one stock row is eligible only when:

- exact NSE EQ symbol + ISIN identity is current;
- 60 contiguous completed market observations exist;
- prior-20 median traded value >= INR 20,000,000;
- raw-price feature lookback is corporate-action-safe;
- 21 contiguous delivery observations including current session exist;
- current delivery source passes T003-P3 quality;
- at least two distinct strictly future STF expiries exist;
- all required futures denominators are valid;
- all 37 features are finite under frozen rules.

Base and augmented predictions use exactly the same rows.

Minimum common stock rows per included session:

100.

A session below 100 common stocks is excluded in full.

## Primary horizon

5 completed NSE sessions.

Entry:

next completed NSE session open.

Exit:

holding-session-5 close, entry session counting as holding session 1.

Target:

stock return minus Nifty 500 return over the identical interval.

Corporate actions during the outcome interval fail closed per stock.

Paired Newey-West lag:

4.

## Primary success criteria

T006 primary succeeds only when BOTH are true:

1. augmented-minus-base mean daily rank IC > 0 and two-sided p < 0.05;
2. augmented-minus-base mean daily top-minus-bottom spread > 0 and two-sided
   p < 0.05.

Intersection rule. Failure of either means the primary endpoint is unsupported.

## Minimum evidence before opening primary result

Do not open the primary result until:

- at least 60 distinct eligible T006 decision sessions exist;
- all included 5-session outcomes have matured;
- at least 50 sessions contain valid paired rank-IC observations.

The trial continues if these maturity/count conditions are not met.

## Secondary 1-session endpoint

T005's 1-session secondary endpoint was also positive.

T006 may report a prospective 1-session secondary endpoint using the same fixed
models and exact common rows.

Newey-West lag: 5.

Secondary 1D evidence cannot rescue a failed 5D primary.

## No 20-session endpoint

T005's 20-session diagnostic was unsupported.

T006-v1 does not retest 20 sessions.

A future medium-horizon derivatives trial requires a new frozen design.

## Trial immutability

After the first eligible T006 decision session, no change is allowed to:

- cutoff;
- source gates;
- features;
- expiry selection;
- FO unit semantics;
- model coefficients;
- l2;
- minimum common rows;
- primary/secondary horizons;
- minimum evidence;
- success thresholds;
- label definition.

A material change requires a new trial ID.

## Interpretation

T006 can establish prospective information content for the frozen T005
stock-futures feature family.

It does not by itself establish:

- optimal AB001 blend weight;
- stock-specific execution profitability;
- calibrated futures execution cost;
- live-capital readiness.

TC001/RM001/PO001 remain separate implementation layers.

Live capital remains disabled.
