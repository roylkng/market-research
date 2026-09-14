# H022-D005 — within-company variation diagnostic

## Status

`FROZEN_POST_OUTCOME_DIAGNOSTIC`

Live capital: **DISABLED**

H022-D005 is explanatory only. It cannot upgrade H022 validation, change H022-R001 or H022-X001, or create a production stock-selection rule.

## Motivation

H022-D004 finds positive aggregate slopes after company balancing, same-company window de-overlap and publication-month fixed effects. However, the deterministic first-event-per-company sample has essentially no ranking economics: `+0.25 pp` top-minus-bottom spread, `50%` top-quintile beat rate and a negative top-quintile median.

That leaves a direct unresolved question: is H022 genuinely about **changes inside a company over time**, or are the aggregate results still being carried by persistent differences between companies or sources?

D005 removes company-level intercepts and tests only within-company variation.

## Frozen input

- D004 panel: `research/historical/h022/dependence-diagnostic-v1/diagnostic-panel.json`
- panel SHA-256: `e776474d6406cc40aedf0c3ce10d7caf87c2b0e86bc6af99d5df717d5980fcab`
- rows: 559 complete 60-session observations

No new market data are required.

## Shared signal scale

H022 is standardized once across all 559 D004 rows using one population mean and standard deviation. That global z-score is then demeaned within each company. D005 does not redefine the H022 feature.

## Frozen tests

### 1. Company fixed effects / within estimator

Companies must have at least two complete events. For each eligible company:

```text
x_it = z(H022)_it - mean_company[z(H022)]
y_it = excess60_it - mean_company[excess60]
```

Estimate through the origin:

```text
y_it = beta * x_it
```

Minimum coverage: 100 companies and 300 observations.

Report the within-company slope, within-company Spearman relation, and a 10,000-iteration company-cluster bootstrap 95% interval.

### 2. Non-overlap company fixed effects

First reuse the exact D004 greedy same-company non-overlap selector. Then retain only companies with at least two remaining events and run the same within-company estimator.

Minimum coverage: 70 companies and 180 observations.

This asks whether the within-company result remains after removing overlapping 60-session same-company return windows.

### 3. Highest-vs-lowest H022 event pair

For every company with at least two complete events and at least two distinct H022 values:

- choose the highest-H022 event;
- choose the lowest-H022 event;
- break signal ties by source ID;
- never use future return in event selection;
- compute `future_excess_high - future_excess_low`.

Minimum coverage: 100 company pairs.

Report mean paired difference, median paired difference, positive-pair share and a 10,000-iteration company bootstrap 95% interval for the mean.

## Frozen bootstrap

- unit: company;
- iterations: 10,000;
- base seed: `22027`;
- interval: percentile 95%;
- duplicate bootstrap draws receive distinct cluster IDs so the within transformation remains a genuine cluster resample.

## Frozen interpretation

`DATA_INSUFFICIENT` if any preregistered coverage gate fails.

Otherwise:

- `WITHIN_POSITIVE` if the full company-FE slope, non-overlap company-FE slope and mean highest-minus-lowest paired difference are all strictly positive;
- `WITHIN_SIGN_UNSTABLE` otherwise.

Bootstrap support is separate:

- `ALL_INTERVALS_POSITIVE` if all three bootstrap lower bounds are above zero;
- `MIXED_OR_UNCERTAIN` otherwise.

A positive result still cannot promote H022. A negative result would materially weaken the claim that H022 captures event-level information rather than persistent company identity.

## Still unresolved after D005

Even a positive D005 result does not solve current-U001 survivorship or point-in-time size/free-float selection. Those require a separate sourced historical factor-control exercise. Prospective confirmation remains mandatory.

## Result

**UNOPENED at D005 contract freeze.**
