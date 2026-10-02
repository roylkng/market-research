# PO001-v4 Protocol Amendment P2: Remove Unstable Parent Weight Reference

Frozen: 2026-10-02
Status: FROZEN BEFORE FIRST S001 RUN
Live capital: DISABLED

## Trigger

After P1, full CI run 36973771107 repeated the exact same synthetic
PO001-v3 versus PO001-v4 problem on another GitHub-hosted runner.

Observed maximum name-weight difference:

    0.0015683833715088857

The earlier pre-S001 diagnostic run 36973617379, on the same frozen synthetic
inputs and same code, observed:

    0.0000013232961525444509

The parent PO001-v3 SLSQP reference therefore varied by more than three orders
of magnitude across runners.

No S001 replica had run when P2 was frozen.

## Conclusion

PO001-v3 target weights are not a valid numerical oracle for PO001-v4 backward
implementation equivalence.

Requiring v4 to reproduce those weights would force the new deterministic solver
to reproduce the exact defect it is designed to remove.

## Correct backward implementation gate

For the frozen synthetic problem:

1. PO001-v3 and PO001-v4 consume identical alpha, risk, cost, impact and
   constraint inputs.
2. Both outputs must be feasible under the same frozen constraints.
3. PO001-v4 objective utility must be >= PO001-v3 utility - 1e-10.
4. PO001-v4 maximum coordinate KKT violation must be <= 1e-9.
5. PO001-v4 output must be exactly deterministic under alpha-row input
   reordering.
6. Cash-optimal and unsupported-domain fail-closed tests must pass.

PO001-v3 weight differences and component-level decomposition differences are
diagnostic only and are not pass/fail gates.

## Why this is not outcome tuning

- S001 has not run.
- No realized return is opened.
- The amendment is triggered solely by repeated solver output on synthetic
  deterministic data.
- No v4 solver parameter or S001 threshold changes.
- The same I004 economic problem remains the S001 target.

## S001 remains unchanged

The actual PO001-v4 numerical-stability gates remain exactly frozen:

- expected-alpha range <= 1e-10;
- annualized-volatility range <= 1e-9;
- daily-variance range <= 1e-12;
- risk-penalty range <= 1e-11;
- transaction-cost range <= 1e-10;
- objective-utility range <= 1e-10;
- pairwise max weight difference <= 1e-10;
- pairwise L1 weight difference <= 1e-8;
- KKT residual <= 1e-9.

No live-capital implication.
