# EXP-2026-09-06-H002 — Frozen specification

## Hypothesis

Positive unexpected earnings may drift into prices after the immediate result reaction.

## Signal

```text
UE = (EPS_t - EPS_t-4) / price_day_minus_2
```

## Universe

Same preselected late-July-2025 liquid non-financial Indian equity cohort used for the feasibility pilot.

## Execution convention

- Ignore result day and first subsequent trading session.
- Enter at the open of the second trading session.
- Hold exactly 20 trading sessions.
- Exit at close.
- Exclude observations without independently verified exact prices.

## Tests

1. Continuous relationship between UE magnitude and subsequent excess return.
2. Highest/lowest descriptive cohort slices.
3. Pre-executable sign split: positive UE versus negative UE.
4. Hit rate against Nifty.
5. Bootstrap confidence interval of positive-minus-negative spread.
6. Winner-dependence stress tests.

## Caveat

A within-cohort ex-post quintile rank is descriptive, not a clean live rule unless thresholds were known before the quarter. Prospective follow-up must pre-register thresholds or use a standardized / analyst-consensus surprise available before the result.
