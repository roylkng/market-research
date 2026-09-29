# PO001 I002 Walk-Forward OOS Integrated Snapshot v1

Status: FROZEN BEFORE MATERIALIZATION
Frozen: 2026-09-29
Live capital: DISABLED

## Objective

Materialize the first end-to-end PO001 portfolio snapshot from a genuinely
walk-forward out-of-sample AE001 alpha forecast.

I002 follows I001, which failed closed because 2026-09-25 fell inside the frozen
T003-P3 delivery-history gap. I002 does not modify or rescue I001.

## Decision snapshot

Decision session: 2026-08-31.

Alpha horizon: 5 completed NSE sessions.

Historical source acquisition ends on 2026-08-31. The subsequent five-session
outcome is outside the materialized market panel and is not opened by I002.

## Alpha model

Source experiment: AE001-T003.

Frozen historical fold: T003 5D fold 2.

Fold-2 validation start: 2026-07-01.

Model:
- ridge;
- l2 = 1.0;
- frozen 27 AE001 price/liquidity + delivery/VWAP features;
- within-session tie-aware percentile transform.

Training rule:

    keep only examples whose full 5D exit session < 2026-07-01

The model is reconstructed from the frozen T003 contracts. The 2026-08-31 row is
scored directly and its future label is not constructed.

## Risk

RM001-v1 state as of 2026-08-31.

I002 requires two independent RM001 materializations from the same frozen inputs
to produce byte-identical:

- exposure-panel.json.gz;
- factor-history.json.gz;
- risk-state.json.gz.

A mismatch fails I002 before portfolio construction.

## Cost

TC001 observable delivery-equity statutory/regulatory cost floor.

No spread or market-impact estimate enters the primary I002 optimization.

## Portfolio parameters

Identical to I001:

- risk_aversion = 5.0;
- max name weight = 0.05;
- max invested weight = 1.00;
- max traded fraction of NAV = 1.00;
- initial current weights = 0;
- terminal liquidation = true;
- no factor hard bounds.

## Common universe

Exact symbol + ISIN identity present in:

- the 2026-08-31 27-feature delivery-complete action-safe cross-section;
- RM001 2026-08-31 risk state.

Minimum common identities: 500.

## Comparisons

1. equal-weight top decile;
2. positive-alpha proportional top decile;
3. PO001 risk-aware with zero transaction costs;
4. full PO001 with TC001 observable costs.

## Interpretation boundaries

- no post-31-Aug market source is acquired;
- no 5D realized I002 outcome is opened;
- no risk-aversion or portfolio parameter tuning against outcomes;
- no sector/size neutrality claim;
- no calibrated impact-cost claim;
- historical-development integration only;
- live capital disabled.
