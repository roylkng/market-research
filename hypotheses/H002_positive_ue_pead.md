# H002 — Positive unexpected earnings / PEAD

## Status

`FROZEN — PROSPECTIVE EVALUATION REQUIRED`

The **historical feasibility evidence remains INCONCLUSIVE**. `FROZEN` means the prospective rule is now fixed and cannot be changed after outcomes begin. It does not mean the hypothesis has been validated.

## Hypothesis

Positive unexpected earnings may be incorporated into Indian equity prices gradually, producing post-earnings-announcement drift after the immediate result reaction.

## Frozen prospective rule

Rule id: `H002-R001`

Expectation model:

```text
expected_eps = prior_year_same_quarter_basic_eps * corporate_action_factor
```

Signal:

```text
UE = (actual_basic_eps - expected_eps) / price_day_minus_2
```

The canonical rule is stored in `registry/h002_signal_rule.yaml` and documented in `docs/h002-signal-v1.md`.

### Guardrails

- target and baseline symbol, reporting quarter and accounting basis must match,
- baseline must be exactly the comparable quarter one year earlier,
- baseline availability must be independently known and strictly predate the current filing,
- historical reconstruction capture time cannot substitute for historical availability,
- corporate-action factor and version are explicit,
- price reference must be positive, versioned and strictly predate the filing,
- current event must be PROSPECTIVE,
- momentum, valuation, guidance and LLM judgement are not part of H002-R001,
- missing required inputs produce `NO_SIGNAL` rather than imputation.

Buckets are fixed as `POSITIVE`, `ZERO`, `NEGATIVE`, or `NO_SIGNAL`. There is no learned threshold and no winsorization.

## Prospective universe

H002 uses frozen universe rule `U001`.

The first 100-company cohort is stored at:

`research/prospective/universes/FY27-Q2-2026-09-06.json`

No discretionary company additions or removals are allowed after the cohort is frozen.

## Primary horizon

- ignore result day and the first subsequent trading session,
- planned paper entry is the second eligible session open,
- primary holding period is exactly 20 trading sessions,
- actual trading-calendar, price and benchmark mechanics belong to H002-C.

## Historical feasibility result

24 observations had independently verified delayed-entry/exit prices.

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

The sign moved in the economically expected direction, but the sample was small, uncertainty crossed zero, and the result was sensitive to a handful of observations.

## Decision

**No live capital.**

H002-R001 is now fixed for prospective paper testing. Analyst-consensus surprise, standardized SUE, momentum or valuation overlays require separately registered future rules. The next gate is H002-C: deterministic paper execution and benchmark reconstruction.
