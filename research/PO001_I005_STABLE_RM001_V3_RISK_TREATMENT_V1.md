# PO001 I005 Stable RM001-v3 Risk-Treatment Revisit v1

Status: FROZEN BEFORE I005 ECONOMIC INSPECTION
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Revisit the RM001-v3 portfolio-treatment question that I004 could not answer
because PO001-v3 SLSQP failed its numerical reproducibility audit.

I005 uses the numerically stable PO001-v4 portfolios from successful S001.

No optimizer is refit or tuned in I005.

## Source solver evidence

S001 workflow run:

    36974074783

Required status:

    NUMERICAL_STABILITY_ESTABLISHED

Required S001 result SHA:

    6eacf70acfd65ecc0e2b2767b9a222c80f299c70747f4879624dbf013f055e62

I005 will pin exactly one S001 replica report after this protocol is frozen.

Because S001 established zero pairwise weight differences and zero economically
meaningful scalar dispersion, any replica is economically interchangeable.

I005 must verify its pinned replica against the sealed S001 source hashes.

## Frozen economic problem

Decision session:

    2026-08-31

Horizon:

    5 sessions

NAV:

    INR 10,000,000

Alpha:

    exact pinned I002/T003 fold-2 augmented ridge

Execution:

    TC001 observable costs
    + square-root impact k=0.50
    + max participation 10% ADV20

Constraints:

    max name 5%
    max invested 100%
    max traded 100%
    starts from cash
    terminal liquidation true
    no hard factor bounds

Solver:

    PO001-v4-DEVELOPMENT

No post-31-Aug realized return is opened.

## Control portfolio

PO001-v4 optimized with exact pinned RM001-v1 state:

    b1d6898f1083d752ca7db6dc7509b8ef4a2aef0f1543f24fd8b30f07604d80c1

## Treatment portfolio

PO001-v4 optimized with exact sealed RM001-v3 P001 state:

    32002ec101531c0e28fb551058c79f179fca53aafccf3c36ef07cb0159387441

Only the risk state differs.

## Critical measurement correction versus I004

RM001-v1 and RM001-v3 do not define identical risk spaces.

Therefore this is NOT a valid comparison:

    control risk measured by v1
    versus
    treatment risk measured by v3

I005 must evaluate BOTH weight vectors under BOTH risk states.

This produces four risk evaluations:

1. control weights under RM001-v1;
2. treatment weights under RM001-v1;
3. control weights under RM001-v3;
4. treatment weights under RM001-v3.

## Common-metric comparisons

Expected 5D alpha and transaction cost are measured identically for both
portfolios.

Report:

- expected-alpha delta;
- transaction-cost delta;
- weight L1 change;
- maximum absolute name-weight change;
- holding-count change;
- HHI/effective-name change;
- top increases/decreases.

## Cross-risk comparisons

Under RM001-v1, report treatment minus control:

- factor variance;
- idiosyncratic variance;
- total variance;
- annualized volatility;
- risk penalty;
- utility using common alpha/cost and RM001-v1 risk.

Under RM001-v3, report treatment minus control for the same fields.

## Frozen optimality sanity checks

Because each portfolio is the optimum under its own risk map with identical
alpha/cost/constraints:

Under RM001-v1:

    utility(control) >= utility(treatment) - 1e-10

Under RM001-v3:

    utility(treatment) >= utility(control) - 1e-10

Failure of either condition indicates implementation or evaluation error.

## Materiality thresholds

These thresholds are frozen before inspecting I005 portfolio differences.

Portfolio reallocation is MATERIAL if either:

    L1 weight change >= 0.05

or:

    maximum absolute name-weight change >= 0.005

Expected-alpha impact is MATERIAL if:

    |delta expected 5D excess| >= 0.0001
    (1 basis point over the five-session horizon)

Transaction-cost impact is MATERIAL if:

    |delta total transaction-cost fraction| >= 0.0001
    (1 basis point of NAV)

Risk impact under a common risk map is MATERIAL if:

    |delta annualized volatility| >= 0.005
    (50 basis points annualized)

These are interpretation thresholds, not pass/fail promotion thresholds.

## Interpretation classes

If both optimality sanity checks pass, I005 may classify:

- MATERIAL_RISK_MODEL_PORTFOLIO_EFFECT;
- LIMITED_RISK_MODEL_PORTFOLIO_EFFECT.

I005 may not claim RM001-v3 is a better risk forecast.

That requires a separate OOS risk-forecast calibration study comparing
RM001-v1/v2/v3 predicted risk with subsequently realized covariance/portfolio
volatility.

## Promotion

A material, numerically stable I005 result may justify use of RM001-v3 in a
separately frozen prospective paper portfolio only after the existing
prospective RM001-v3 source gate produces valid states.

I005 alone does not establish live-capital readiness.

## Prohibited

- no realized five-session return;
- no solver changes;
- no alpha refit;
- no risk-aversion tuning;
- no materiality-threshold changes after inspection;
- no claim that lower modeled risk means lower future realized risk;
- no live capital.
