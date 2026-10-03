# AE001 T005 Pre-Open Successor Candidate v1

Status: PRE-REGISTRATION DESIGN CANDIDATE  
Candidate trial ID: AE001-T012  
Created: 2026-10-03  
Live capital: DISABLED

## Objective

Preserve the information set that made AE001-T005 nominally successful while
removing the historical source-timing ambiguity that prevents a causal
prospective claim.

This is not a registered trial. It opens no return outcomes and authorizes no
predictions.

## Why this path is different from T011

T011 moved the futures information back one completed session:

- use futures from D-1;
- combine with cash and delivery state on D;
- predict after D.

Its frozen 5-session primary was unsupported.

The candidate here does not lag the T005 futures signal.

Instead:

1. cash, price/liquidity and delivery features are for completed session D;
2. official NSE stock-futures features are also for completed session D;
3. D futures evidence must be captured by SC003 before the next frozen trading
   session N at 08:30 Asia/Kolkata;
4. the fixed model decision is sealed no later than N 08:30;
5. entry is N open.

This preserves T005's same-session D information while making the decision
causal for N open.

## Source-feasibility gate before registration

Do not register or freeze AE001-T012 until SC003 contains at least three
distinct target sessions with valid pre-open-ready source observations.

The readiness implementation is:

- `src/marketlab/alpha_preopen_successor.py`

It validates each ready observation against the frozen NSE trading calendar,
including target close, next trading session and the 08:30 cutoff.

The source-feasibility sessions:

- use no return or alpha outcomes;
- may establish only that the source arrives in time;
- may not be backfilled later as AE001-T012 predictions.

The first eligible AE001-T012 target session must be strictly after the
registration and final protocol freeze.

## Proposed frozen information set

If the source gate passes, the successor should retain the already-frozen T006
model artifact rather than refit after seeing new outcomes:

- model artifact:
  `research/prospective/ae001-t006/frozen-models-v1.json`
- artifact SHA-256:
  `da1ce462b5d9c59fb5bea2f4b69c574c8ecbf1f728c44b23af8f3e73bd5de091`
- CORE27 model SHA-256:
  `774ce4b6ac0955b213521f017116ea32e579e73bfcbdb9ed3441c8e57248378c`
- FULL37 model SHA-256:
  `7030afd449058e54a03d3febb6db0910b75acbe2be403e01ded8ee14eb68fa02`

The preferred comparison remains:

`FULL37 - CORE27`

on identical stock rows.

No retraining, coefficient change, feature change or hyperparameter search is
permitted under this candidate design.

## Proposed primary endpoint

Retain the T006 confirmatory primary:

- horizon: 5 completed NSE sessions;
- entry: N open;
- exit: holding-session-5 close;
- target: stock return minus Nifty 500 return over the identical interval;
- paired Newey-West lag: 4;
- minimum 60 eligible decision sessions;
- minimum 50 valid paired rank-IC sessions;
- success requires both:
  - mean augmented-minus-base rank IC > 0 with two-sided p < 0.05;
  - mean augmented-minus-base top-minus-bottom spread > 0 with two-sided
    p < 0.05.

The 1-session endpoint may remain a non-rescuing secondary.

## Multiplicity and accounting

AE001-T005 is nominally supported historically but is not multiplicity-robust
under RTA001-v1.

Therefore a successor must not be described as a way to rescue historical
multiplicity by retesting variants.

Before the first AE001-T012 prediction is allowed:

1. the final trial protocol must be frozen;
2. the trial must be appended to the AE001 trial ledger;
3. AE001-T012 must be added to RTA001 global accounting;
4. the exact earliest eligible target session must be frozen;
5. no source-feasibility target used to open the three-session gate may be
   backfilled as a prediction.

## Current state on 2026-10-03

SC003 has one valid pre-open-ready target session.

Two additional distinct valid source-timing sessions are required before the
candidate may become a registered prospective trial.

No return outcome is opened by this design candidate.
