# H002 — Positive unexpected earnings / PEAD

## Status

`FROZEN — PROSPECTIVE EVALUATION REQUIRED`

## Hypothesis

Positive unexpected earnings may be incorporated into Indian equity prices gradually, producing post-earnings-announcement drift after the immediate result reaction.

## Frozen prospective signal

Signal version: `H002-UE-v1`

```text
expected_eps = EPS_t-4
unexpected_eps = EPS_t - expected_eps
UE = unexpected_eps / price_day_minus_2
```

Canonical rule SHA-256:

`24eb8325216e68db8e3f14db440a0f470f9f576a3d1aea034b570812c70686ff`

The canonical rule is stored in `registry/signals/H002-UE-v1.json` and documented in `docs/h002-ue-v1.md`.

This keeps the prospective signal aligned with the same literature-style seasonal unexpected-earnings proxy used by the original feasibility pilot. Analyst-consensus and standardized-SUE alternatives are separate future hypotheses or signal versions rather than post-hoc replacements.

## Prospective universe

H002 uses frozen universe rule `U001`.

The first 100-company cohort is stored at:

`research/prospective/universes/FY27-Q2-2026-09-06.json`

No discretionary company additions or removals are allowed after the cohort is frozen.

## Buckets

- `POSITIVE`: UE > 0
- `ZERO`: UE == 0
- `NEGATIVE`: UE < 0
- `NO_SIGNAL`: missing, invalid or non-comparable required inputs

No winsorization or current-cohort quantile thresholds are used in v1.

## Timing and comparability guardrails

- prior EPS source must predate the current filing,
- prior EPS must correspond to the same reporting quarter and accounting basis,
- corporate-action comparability must be explicit and versioned,
- post-result prices, transcripts and brokerage revisions cannot enter the signal,
- missing required inputs create `NO_SIGNAL`, not an estimate.

## Primary horizon

- ignore result day and the first subsequent trading session,
- planned paper entry is the second eligible session open,
- primary holding period is exactly 20 trading sessions,
- actual execution and benchmark mechanics belong to H002-C.

## Feasibility result

The historical feasibility pilot remains unchanged. 24 observations had independently verified delayed-entry/exit prices.

### Ranked UE magnitude

- Pearson correlation with Nifty excess return: **0.214**, p = **0.315**
- Spearman correlation: **0.230**, p = **0.281**
- highest-UE quintile excess return: **-2.58 pp**
- lowest-UE quintile excess return: **-1.80 pp**

The ranked 20-session implementation did not replicate a clean PEAD effect.

### Positive vs negative UE

- Positive UE observations: 16
- Negative UE observations: 8
- Positive UE mean excess: **+1.99 pp**
- Negative UE mean excess: **-1.17 pp**
- Spread: **+3.16 pp**
- Spread p-value: **0.233**
- Bootstrap 95% CI: **-1.67 pp to +7.96 pp**
- Positive UE beat rate: **62.5%**
- Negative UE beat rate: **37.5%**

The sign moved in the economically expected direction, but the historical sample was too small and winner-dependent for a tradable conclusion.

## Decision

**No live capital.**

H002-UE-v1 is now frozen so the next earnings cohort can test the same rule prospectively. The next implementation gate is deterministic paper execution and benchmark reconstruction, not more signal optimization.
