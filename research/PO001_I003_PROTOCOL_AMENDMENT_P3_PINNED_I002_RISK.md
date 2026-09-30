# PO001 I003 Protocol Amendment P3: Preserve Exact Sealed I002 Risk Input

Frozen: 2026-09-29
Status: FROZEN BEFORE ANY I003 PORTFOLIO RESULT
Live capital: DISABLED

## Trigger

P2 required a portfolio-level equivalence audit before the current canonical
RM001 representation could replace the legacy I002 risk-state hash.

Diagnostic run: 36579611661.

No I003 stock-impact portfolio result existed when this amendment was frozen.

## P2 audit result

Legacy RM001 reconstruction reproduced the sealed I002 PO001-v1 optimizer
artifact exactly:

`ad77db26c76e54921254aea9e49c30da8b1f044076b57961671229e93100154e`

Canonical RM001 PO001-v1 artifact:

`1c9bc978be158c4313fc2c350ba656e61e128ed5d01380e768d3f71afd91294e`

The frozen P2 portfolio-equivalence gate FAILED.

Observed differences:

- maximum absolute target-weight difference:
  0.00469440475080203;
- invested-weight difference:
  2.5979218776228663e-14;
- expected 5D excess-return difference:
  2.924689320574214e-06.

The expected-return difference is economically very small, but the target-weight
difference exceeds the pre-frozen 1e-9 tolerance by many orders of magnitude.

The cause is optimizer sensitivity along a locally flat solution surface. This
does not justify changing the frozen equivalence tolerance after the result.

## Frozen resolution

I003 will use the EXACT SEALED I002 RM001 risk-state artifact as its executable
risk input.

Legacy I002 risk-state SHA:

`b1d6898f1083d752ca7db6dc7509b8ef4a2aef0f1543f24fd8b30f07604d80c1`

Source workflow run:

`36570866823`

Source artifact:

`po001-i002-36570866823`

Source path inside artifact:

`reports/po001-i002/risk-a/risk-state.json.gz`

The exact gzip bytes will be copied into the I003 research namespace before
rerunning the study. Its internal state SHA must match the legacy SHA above.

## Current canonical RM001 remains a diagnostic gate

I003 will still independently rebuild RM001 from the frozen 31-Aug source data.

That rebuild must equal the current canonical state SHA:

`7a0a440515a2f75e0114281dd37a1bf4c6801e1b2e17a0b78183e89fe663abce`

Purpose:

- prove current source/materialization reproducibility;
- detect upstream source or model drift.

The canonical rebuild is NOT used as the I003 optimizer risk input.

## Why this is scientifically preferable

I003's stated objective is to isolate the incremental effect of stock-specific
impact and capacity relative to sealed I002.

Using the exact I002 risk state preserves every I002 risk input and therefore
isolates the intended treatment:

    PO001-v1 observable cost
    vs
    PO001-v2 observable cost + stock-specific impact/capacity

No risk-model representation change is allowed to enter that comparison.

## Unchanged I003 parameters

This amendment does not change:

- alpha model;
- alpha vector;
- decision session;
- horizon;
- risk aversion;
- name/invested/turnover caps;
- impact coefficient;
- participation cap;
- NAV surfaces;
- terminal liquidation;
- realized outcomes.

No I003 result may be opened until the exact legacy risk artifact is pinned and
verified.
