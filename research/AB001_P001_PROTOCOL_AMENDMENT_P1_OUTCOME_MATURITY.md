# AB001 P001 Protocol Amendment P1: Multi-Session Outcome Maturity

Frozen: 2026-09-30
Status: FROZEN BEFORE VALID P001 MATERIALIZATION
Live capital: DISABLED

## Trigger

The first P001 workflow attempt, run 36669808434, was started after the initial
P001 freeze but before a material multi-session outcome-maturity issue was
identified in AB001-v1.

The issue was discovered while the workflow was still rebuilding source data.

## Issue

For a 5-session alpha, requiring only:

    feature_session < current_decision_session

is insufficient when computing trailing efficacy.

The most recent four prior feature sessions can still have outcomes whose
5-session labels have not matured by the current decision session.

Using those outcomes would create look-ahead in dynamic blend weights.

## Frozen correction

An OOS record may contribute to AB001 efficacy for decision session D only when:

    exit_session < D

The canonical AB001 record now preserves entry_session and exit_session.

Correlation-shrink diagnostics may still use prior prediction records regardless
of outcome maturity because they do not consume return outcomes.

## Invalidated workflow attempt

Workflow run:

    36669808434

is permanently classified:

    INVALID_PRE_MATURITY_FIX

No artifact, metric or blend result from that run may enter P001 evidence,
regardless of its workflow conclusion.

## Valid rerun gate

A valid P001 materialization may begin only after:

- full repository CI passes with the maturity fix;
- the regression test proves a 5-session label is unavailable to efficacy until
  its exit session is strictly before the decision session;
- no P001 source, fold, feature or blending parameter is otherwise changed.

This amendment changes only information availability discipline. It does not
change any alpha construction, fold, model, feature or blend parameter.
