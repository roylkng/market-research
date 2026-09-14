# H022-D004 — repeated-event and overlap dependence diagnostic

## Status

`FROZEN_POST_OUTCOME_DIAGNOSTIC`

Live capital: **DISABLED**

This diagnostic is explanatory only. It cannot upgrade H022 historical validation, change H022-R001, change H022-X001, or create a new stock-selection filter.

## Why this diagnostic exists

The expanded point-in-time NIFTY 200 challenger retains a positive H022 relation but falls from `PROMISING` to `INCONCLUSIVE`. H022-D002 shows that current-U001 observations are materially stronger than the additional historical names, while industry fixed effects do not explain the aggregate relation. H022-D003 shows that Financial Services are not the reason for the attenuation.

A remaining concern is dependence. The 559 complete primary observations contain repeated calls from the same companies, adjacent 60-session holding windows can overlap, and many results are published in the same earnings-season months. Those structures can make an event-level relationship look broader than it is.

H022-D004 therefore freezes four dependence controls before opening their outputs.

## Frozen input

- expanded outcome report: `research/historical/h022/expanded-nifty200-challenge-v1/outcome-report.json`
- report SHA-256: `310d3709393047db4ec5e2eacb9d333fac2d81b83e86bc65140dc4bc60c6d22f`
- primary horizon: 60 sessions
- required status: `COMPLETE`
- expected observations: 559

No new market data are required.

## Shared signal scale

The H022 signal itself is unchanged. One population mean and standard deviation are estimated across all 559 complete rows, and that same z-score scale is reused for every D004 estimator. Returns are not winsorized.

## Frozen estimators

### Event-level baseline

OLS:

```text
future_60d_excess_pp ~ 1 + z(H022)
```

This is descriptive context only.

### Company-balanced regression

The same regression is estimated with event weight:

```text
1 / number_of_complete_events_for_symbol
```

Therefore every company contributes the same total regression weight regardless of how many calls it has in the complete panel.

### First complete event per symbol

For each symbol, keep only the earliest complete observation by exact exchange publication timestamp, breaking ties by source ID. Signal magnitude and return are forbidden selection inputs.

The reduced sample must contain at least 150 observations. Report slope, Spearman relation and count-balanced quintile economics.

### Greedy non-overlap per symbol

For each symbol:

1. sort complete observations by entry-session date and source ID;
2. keep the first;
3. keep a later observation only if its entry-session date is strictly after the 60-session exit date of the previously kept observation.

The selector may not use H022 magnitude or future return. The reduced sample must contain at least 150 observations. Report slope, Spearman relation and quintile economics.

### Publication-month fixed effects

OLS:

```text
future_60d_excess_pp ~ 1 + z(H022) + publication_month_FE
```

Publication month comes only from the frozen NSE publication timestamp. At least eight distinct months are required.

## Bootstrap

Each dependence-control slope receives a symbol-cluster bootstrap percentile interval:

- 10,000 iterations;
- base seed `22026`, with deterministic estimator offsets;
- 95% interval.

For the company-balanced estimator, each resampled company draw remains an equal-weight cluster even if the same symbol is drawn more than once.

## Frozen interpretation

`DATA_INSUFFICIENT` if either reduced deterministic sample has fewer than 150 observations or fewer than eight publication months are present.

Otherwise:

- `BROAD_POSITIVE`: company-balanced, first-event, non-overlap and publication-month-FE slopes are all strictly positive.
- `SIGN_UNSTABLE`: at least one of those four slopes is non-positive.

Separate sensitivity flags identify:

- `REPEATED_COMPANY`;
- `OVERLAP`;
- `CALENDAR_MONTH`.

Bootstrap support is separately classified as:

- `ALL_INTERVALS_POSITIVE` if every dependence-control 95% lower bound is above zero;
- `MIXED_OR_UNCERTAIN` otherwise.

Positive signs alone do not promote H022. Negative or unstable results can weaken the interpretation.

## What D004 cannot answer

D004 does not resolve point-in-time free-float market-cap selection, current-U001 survivorship, source availability differences, valuation, quality, or prospective replication. Those remain separate gates.

## Result

**UNOPENED at D004 contract freeze.**
