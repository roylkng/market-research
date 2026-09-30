# PO001 I003 Protocol Amendment P6: Pin Exact Sealed I002 Control Portfolio

Frozen: 2026-09-29
Status: FROZEN BEFORE ANY I003 STOCK-IMPACT PORTFOLIO RESULT
Live capital: DISABLED

## Trigger

The first valid post-P5 I003 materialization run 36607668145 passed:

- source reproduction;
- delivery-panel reproduction;
- exact pinned I002 alpha-model validation;
- P5 fresh-alpha numerical-equivalence diagnostics;
- exact pinned I002 RM001 risk validation;
- P5 fresh-RM001 numerical-equivalence diagnostics.

It then failed closed before any PO001-v2 NAV surface was opened because a
fresh PO001-v1 SLSQP solve did not reproduce the sealed I002 optimizer artifact
SHA exactly.

No I003 stock-impact portfolio result existed when P6 was frozen.

## Prior evidence

P2 already demonstrated that PO001-v1 has numerical optimizer sensitivity along
a locally flat solution surface. Under an economically equivalent RM001
representation, maximum name-weight differences reached about 47 bps even
though expected portfolio alpha changed by only about 0.029 bps.

P3 and P4 removed reconstruction variability from executable risk and alpha by
pinning the exact I002 inputs.

Run 36607668145 now demonstrates that re-solving the control itself remains an
unnecessary source of numerical treatment contamination.

## Frozen resolution

I003 will NOT re-optimize PO001-v1 as its control.

Instead, the exact sealed I002 integrated study artifact from workflow run
36570866823 will be pinned under the I003 research namespace.

Required source:

- workflow run: 36570866823;
- artifact: po001-i002-36570866823;
- source path:
  reports/po001-i002/study/po001-i002-artifact.json.gz;
- internal I002 study artifact SHA:
  d3cb62d0f1c041fa0af76a4275138ede5a12c0b5709106c441cafd8a8ca82ac1.

The pinned artifact must retain exact gzip-byte and internal-artifact hashes.

## Control portfolio

The I003 control is the sealed I002 portfolio:

`full_po001_observable_cost_floor`

This is the actual historical control generated before I003 was designed.

Its frozen headline state is:

- holding count: 39;
- expected 5D excess return: 0.01056267666652251;
- annualized volatility: 0.13713480625195076;
- total observable round-trip cost fraction: 0.0022248120000000057;
- risk penalty: 0.0018656701473968324;
- objective utility: 0.006472194519125673.

The full pinned artifact, not only these headline values, is authoritative.

## Treatment portfolio

PO001-v2 continues to use:

- exact pinned I002 alpha model from P4;
- exact pinned I002 RM001 risk state from P3;
- identical I002 common universe;
- identical risk aversion and portfolio constraints;
- identical TC001 observable costs;
- frozen stock-specific square-root impact;
- frozen 10% ADV20 participation cap;
- frozen NAV surfaces ₹1m / ₹10m / ₹100m.

Only execution impact/capacity differs from the sealed I002 control.

## Diagnostic rebuilds

Fresh alpha and RM001 rebuilds remain diagnostic-only under P5.

A fresh PO001-v1 re-solve is no longer a gate and is not used as control.

Reason:

The scientific question is the incremental effect of the new execution treatment
relative to the actual sealed I002 portfolio. Re-solving the control introduces
solver numerical degrees of freedom without adding information.

## Outcome boundary

No post-31-Aug five-session realized return is opened by P6 or I003.

No I003 result may be opened until the exact I002 integrated control artifact is
pinned and verified.

No live-capital implication.
