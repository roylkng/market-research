# PO001 I004 Post-Result Numerical Reproducibility Audit v1

Frozen: 2026-10-02
Classification: POST_RESULT_NUMERICAL_AUDIT
Live capital: DISABLED

## Trigger

Corrected execution replay run 36969967153 successfully materialized I004 after
the reporting-schema fix.

An independent full source rebuild, run 36969593037, reproduced the exact same:

- market artifact and market panel;
- economic corporate-action state;
- delivery source panel;
- frozen economic delivery-feature projections;
- pinned alpha model;
- pinned RM001-v1 control risk;
- pinned RM001-v3 treatment risk.

It nevertheless failed the frozen exact control holding-count gate after a fresh
PO001-v3 control solve.

This demonstrates solver-level numerical non-uniqueness on the broad,
constrained SLSQP problem.

No I004 parameter is changed by this audit.

## Objective

Measure cross-run numerical dispersion of the exact frozen I004 control and
treatment optimizer problems.

The audit may NOT:

- change alpha;
- change risk;
- change execution inputs;
- change NAV;
- change impact coefficient;
- change participation cap;
- change risk aversion;
- change constraints;
- open realized returns;
- redefine the I004 result.

## Frozen audit inputs

Use exact source evidence from pre-result I004 run 36967854755:

    artifact po001-i004-36967854755

Use current frozen executable inputs:

- pinned I002 alpha model;
- pinned I002 RM001-v1 control state;
- pinned RM001-v3 P001 treatment state.

Decision session:

    2026-08-31

NAV:

    INR 10,000,000

All optimizer parameters remain those in PO001-I004-v1.

## Independent runs

Run the exact control and treatment problems on three separate GitHub-hosted
runner jobs.

Each runner records:

- full target-weight vector for control and treatment;
- holding count at weight > 1e-12;
- holding count at weight > 1e-8;
- expected 5D excess return;
- annualized volatility;
- total daily variance;
- risk penalty;
- total transaction cost;
- objective utility;
- artifact SHA;
- solver iterations.

## Frozen reproducibility interpretation

### Economic scalar stability

For each control and treatment field, max-minus-min across runners:

- expected 5D excess return <= 1e-8;
- annualized volatility <= 1e-6;
- total daily variance <= 1e-10;
- risk penalty <= 1e-9;
- total transaction cost <= 1e-8;
- objective utility <= 1e-8.

If any bound fails:

    ECONOMIC_SCALARS_NUMERICALLY_UNSTABLE

### Weight stability

Across runners, pairwise:

- maximum absolute name-weight difference <= 1e-4;
- L1 weight difference <= 0.01.

If either bound fails:

    EXACT_WEIGHT_INTERPRETATION_NOT_REPRODUCIBLE

### Threshold-only holding noise

A difference in >1e-12 holding count is treated as threshold-only noise only if:

- >1e-8 holding count is identical across runners;
- weight stability thresholds pass.

## I004 interpretation after audit

The audit cannot convert a failed result into a success.

It only controls which already-observed outputs may be reported:

- scalar treatment effects may be retained only if scalar stability passes;
- exact stock-level weight-change claims may be retained only if weight stability passes;
- otherwise I004 is limited to qualitative risk-map sensitivity.

No live-capital implication.
