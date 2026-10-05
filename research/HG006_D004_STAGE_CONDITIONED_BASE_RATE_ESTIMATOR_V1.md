# HG006-D004 Stage-Conditioned Historical Base-Rate Estimator v1

Status: **FROZEN BEFORE HISTORICAL TERMINAL LABELS ARE OPENED**  
Frozen: 2026-10-05  
Current-company probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Define in advance how validated historical transaction episodes will become empirical
completion/base-rate evidence.

D004 may run only after:

- HG006-D001 source census passes;
- HG006-D003 episode threading is validated;
- every episode is terminal-labeled under HG006-D002 or right-censored.

## Competing terminal outcomes

Terminal outcomes are:

- COMPLETED;
- FAILED_OR_WITHDRAWN.

RIGHT_CENSORED is not a failure.

UNRESOLVED_SOURCE_CONFLICT is excluded from the statistical denominator and reported
separately.

## Time origin

For each episode, time zero is the earliest official announcement that the validated
episode thread identifies as the transaction's first observed initiation/proposal event.

If a transaction is first observed at a later stage because source history begins after
initiation, it may contribute only to stage-conditioned analyses from its first observed
validated stage; it may not be backdated.

## Primary family-level estimates

For every family with at least 30 valid episodes:

1. report raw episode counts;
2. report completed / failed / right-censored counts;
3. report resolved-case completion fraction for descriptive context only;
4. estimate cumulative incidence of COMPLETED and FAILED_OR_WITHDRAWN over time with
   right-censoring and competing terminal outcomes;
5. report cumulative incidence at:
   - 90 days;
   - 180 days;
   - 365 days;
   - 730 days where supported by follow-up.

The competing-risk cumulative-incidence estimator, not the naive resolved fraction, is
the primary time-horizon base-rate surface.

## Stage-conditioned estimates

For each frozen progress stage and family, define a risk set of episodes that explicitly
reached that stage before a terminal outcome.

Eligible stages:

- BOARD_APPROVED;
- SHAREHOLDER_APPROVED;
- REGULATORY_OR_COURT_APPROVED;
- PUBLIC_ANNOUNCEMENT;
- RECORD_DATE_FIXED;
- OFFER_OPEN;
- OFFER_CLOSED;
- ALLOTMENT_COMPLETED.

A stage-conditioned estimate is published only when:

- at least 30 episodes reached the stage;
- at least 10 terminal outcomes are observed after reaching it.

Otherwise state:

`INSUFFICIENT_HISTORICAL_SUPPORT`.

No pooling across unrelated families merely to clear sample thresholds.

## Preferential-warrant split

PREFERENTIAL_WARRANT must publish separate estimates for:

1. issuance_completion;
2. full_economic_exercise, where the source corpus has enough evidence.

Issuance completion may not stand in for full exercise.

## Uncertainty

Every published completion estimate must include uncertainty.

For descriptive resolved-case fractions, use Wilson 95% intervals.

For cumulative-incidence estimates, retain event counts and an appropriate
nonparametric 95% confidence interval implementation.

The point estimate may not be surfaced without its interval and support count.

## No post-hoc stage selection

The current company's stage may map only to one of the frozen eligible stages above.

Do not search historical stages for whichever gives the most favorable base rate.

When current evidence lies between frozen stages, use the last explicitly satisfied
frozen stage.

## Current probability promotion

D004 itself produces historical base rates only.

A later HG006-P001 current-case probability layer may combine:

- the appropriate family/stage base rate;
- current explicit stage evidence;
- clearly frozen case-specific adjustments, if scientifically justified.

No discretionary "management quality" probability bump is allowed without a separate
registered protocol.

## Operating scenario exclusion

D004 may not assign probabilities to:

- EBITDA per tonne;
- occupancy;
- tenant profitability;
- incremental EBITDA from capital deployment;
- valuation multiples;
- separated-business valuation multiples.

Those require a separate operating-analog research family.

## Scientific boundary

D004 does not:

- use stock returns to label success;
- calculate probability-weighted expected returns;
- create target prices;
- rank current stocks;
- authorize ADO/PF001/live capital.
