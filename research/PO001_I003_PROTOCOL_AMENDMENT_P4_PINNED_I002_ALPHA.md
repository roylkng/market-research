# PO001 I003 Protocol Amendment P4: Pin Exact Sealed I002 Alpha Model

Frozen: 2026-09-29
Status: FROZEN BEFORE ANY I003 PORTFOLIO RESULT
Live capital: DISABLED

## Trigger

The P3 I003 rerun (36581903836) passed all source and RM001 gates but failed
closed before portfolio construction because a fresh fold-2 ridge reconstruction
did not match the sealed I002 model hash on that run.

No I003 stock-impact portfolio result existed when this amendment was frozen.

## Sealed I002 alpha model

Required model SHA-256:

`179ce84f40c1b6e461d2ff1f4104753381d3327b2dda35814b4a913547f91260`

Model contract:

- source trial: AE001-T003;
- horizon: 5 sessions;
- fold: 2;
- validation start: 2026-07-01;
- 27 frozen price/liquidity + delivery/VWAP features;
- within-session tie-aware percentile transform;
- ridge l2 = 1.0;
- model ID: AE001-T003-H5-F2-AUGMENTED-RIDGE-I002.

## Alpha equivalence audit

Diagnostic run: 36583788161.

Using the exact frozen I003 market, action and delivery artifacts, the diagnostic
reconstructed the I002 model and obtained:

- current model SHA:
  `179ce84f40c1b6e461d2ff1f4104753381d3327b2dda35814b4a913547f91260`;
- sealed top-decile identity symmetric difference: 0;
- maximum absolute sealed top-decile alpha difference: 0.0;
- mean absolute sealed top-decile alpha difference: 0.0;
- maximum sealed top-decile global rank difference: 0.

Classification:

`EXACT_SEALED_I002_ALPHA_REPRODUCTION`

## Frozen resolution

The exact reconstructed model object whose internal model SHA matches the sealed
I002 SHA will be pinned under the I003 research namespace before another I003
materialization.

I003 will:

1. verify the pinned model artifact hash and internal model SHA;
2. use the pinned model directly for 31-Aug alpha scoring;
3. independently reconstruct the fold-2 model from current frozen source data as
   a diagnostic;
4. require that diagnostic reconstruction to match the sealed model SHA;
5. use the pinned model, not the fresh reconstruction, as the executable alpha
   input.

## Why this is preferable

I003 is designed to isolate:

    sealed I002 portfolio construction
    versus
    sealed I002 alpha/risk + stock-specific execution impact/capacity.

Pinning the exact I002 alpha model and exact I002 RM001 risk state removes
machine-level reconstruction variability from the treatment comparison.

This amendment does not change:

- alpha coefficients;
- alpha predictions;
- risk;
- decision session;
- horizon;
- risk aversion;
- impact coefficient;
- participation cap;
- NAV surfaces;
- portfolio constraints;
- realized outcomes.

No I003 result may be opened until the pinned model file is created and verified.
