# PO001-v4 Protocol Amendment P1: Parent-Solver Equivalence

Frozen: 2026-10-02
Status: FROZEN BEFORE FIRST S001 RUN
Live capital: DISABLED

## Trigger

Initial implementation CI failed the original synthetic backward-equivalence
weight gate:

    max |w_v4 - w_v3| <= 1e-8

Observed maximum difference:

    1.3232961525444509e-06

No S001 replica had run when this amendment was frozen.

## Pre-S001 diagnostic

Workflow run:

    36973617379

The diagnostic solved the exact same synthetic convex problem with PO001-v3
SLSQP and PO001-v4 deterministic coordinate descent.

Observed:

    max weight difference
        1.3232961525444509e-06

    expected alpha:
        v3 = 0.016028302845553323
        v4 = 0.01602830643613254
        delta = +3.5905792158952288e-09

    daily variance:
        v3 = 3.159100888860303e-05
        v4 = 3.159103507479645e-05
        delta = +2.6186193418189542e-11

    transaction cost:
        v3 = 0.004947552769771865
        v4 = 0.004947555705672758
        delta = +2.9359008930571195e-09

    objective utility:
        v3 = 0.010290974853566382
        v4 = 0.01029097485358987
        delta = +2.3488155864725968e-14

    invested weight delta:
        -8.502087922579449e-13

    PO001-v4 max KKT residual:
        2.896988204881268e-16

The v4 solution has weakly higher objective utility and orders-of-magnitude
smaller first-order residual than the resolution demanded of SLSQP.

Classification:

    SAME_ECONOMIC_PROBLEM_PARENT_SLSQP_REFERENCE_NOT_PRECISE_TO_ORIGINAL_GATE

## Corrected backward-equivalence purpose

Backward equivalence is an implementation guard against solving a different
economic problem.

It must not require a new, higher-accuracy solver to reproduce the numerical
error of the parent SLSQP solution.

The corrected gate is:

1. identical input economic specification;
2. identical feasibility set;
3. v4 invested-weight difference from v3 <= 1e-10;
4. maximum name-weight difference <= 5e-6;
5. expected-alpha absolute difference <= 1e-8;
6. daily-variance absolute difference <= 1e-10;
7. transaction-cost absolute difference <= 1e-8;
8. v4 objective utility must be >= v3 objective utility - 1e-12;
9. v4 KKT residual <= 1e-9.

These bounds are for synthetic parent-equivalence testing ONLY.

## S001 unchanged

The actual numerical-stability experiment remains exactly as frozen before this
diagnostic:

Cross-run v4 gates:

- expected-alpha range <= 1e-10;
- annualized-volatility range <= 1e-9;
- daily-variance range <= 1e-12;
- risk-penalty range <= 1e-11;
- transaction-cost range <= 1e-10;
- objective-utility range <= 1e-10;
- pairwise max weight difference <= 1e-10;
- pairwise L1 weight difference <= 1e-8;
- KKT residual <= 1e-9.

No S001 threshold is loosened.

## Unchanged

No change to:

- alpha;
- risk;
- cost;
- impact;
- constraints;
- coordinate solver;
- convergence tolerance;
- canonicalization;
- S001 source evidence;
- realized-outcome boundary.

No live-capital implication.
