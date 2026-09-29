# PO001 I003 Protocol Amendment P5: Numerical Diagnostic Equivalence Gates

Frozen: 2026-09-29
Status: FROZEN BEFORE ANY I003 PORTFOLIO RESULT
Live capital: DISABLED

## Trigger

The pinned-input I003 materialization run 36585020743 failed closed before
portfolio construction because the freshly rebuilt canonical RM001 artifact did
not equal the single canonical SHA recorded in P3.

The executable I003 risk input was already the exact pinned I002 risk artifact.
No I003 stock-impact portfolio result existed when this amendment was frozen.

## Problem

P1 already demonstrated that machine-level numerical representation can alter an
RM001 content hash while leaving the economic state unchanged.

Therefore exact SHA equality is not a robust diagnostic for independently rebuilt
numerical artifacts.

The same principle applies to the fresh ridge reconstruction used only as an
I003 diagnostic. The executable alpha input is already the exact pinned I002
model from P4.

## Frozen RM001 diagnostic gate

The exact pinned I002 risk state remains mandatory and must retain SHA:

`b1d6898f1083d752ca7db6dc7509b8ef4a2aef0f1543f24fd8b30f07604d80c1`

A fresh canonical RM001 rebuild is accepted as an upstream drift diagnostic only
if all P1 economic-equivalence conditions pass against the pinned state.

The tolerance is NOT newly selected here. It is the tolerance frozen and used by
P1 before the current failure:

`5e-15`

Required invariants:

- identical model ID;
- identical as-of session;
- identical factor names;
- identical covariance window;
- identical covariance realized-session boundaries;
- identical idiosyncratic windows;
- identical security count;
- identical deferred-factor state;
- identical symbol + ISIN identity set;
- identical idiosyncratic status assignment.

Maximum absolute differences allowed:

- factor exposure <= 5e-15;
- factor covariance <= 5e-15;
- idiosyncratic variance <= 5e-15;
- idiosyncratic fallback p75 <= 5e-15.

The fresh canonical state SHA is recorded but is not an executable input.

## Frozen alpha diagnostic gate

The exact pinned I002 model remains mandatory and must retain SHA:

`179ce84f40c1b6e461d2ff1f4104753381d3327b2dda35814b4a913547f91260`

A fresh fold-2 ridge rebuild is a diagnostic only.

The pre-existing alpha equivalence diagnostic used a 1e-12 prediction tolerance.
That same threshold is frozen here before the next I003 materialization.

Required invariants:

- identical model ID;
- identical feature names and ordering;
- identical l2;
- identical training example count;
- identical last training exit session.

On the frozen 2026-08-31 decision cross-section:

- maximum absolute prediction difference versus the pinned model <= 1e-12;
- top-decile identity set must be identical.

The fresh model SHA is recorded but is not an executable input.

## Executable treatment inputs

Unchanged:

- exact pinned I002 alpha model;
- exact pinned I002 RM001 risk state;
- exact I002 alpha vector generated from the pinned model;
- exact I002 portfolio parameters;
- exact I002 observable costs.

Treatment under test remains only:

- stock-specific square-root impact;
- 10% ADV20 participation cap;
- frozen NAV surfaces.

## No tolerance retuning

These diagnostic thresholds may not be widened based on subsequent I003
materializations.

A diagnostic failure above these thresholds blocks I003.

No realized 5D outcome is opened by this amendment.
