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

## Result

Authoritative panel SHA-256:
`e776474d6406cc40aedf0c3ce10d7caf87c2b0e86bc6af99d5df717d5980fcab`

Authoritative summary SHA-256:
`bc5fcace9dcfff4ed9aa7cbe5e2df0dbd78b7116bc018027d38eda233670789e`

Frozen sign classification: **`BROAD_POSITIVE`**.

Bootstrap support: **`MIXED_OR_UNCERTAIN`**.

Sensitivity flags: **none**.

### Full event-level context

The 559 complete observations cover 194 symbols across nine publication months. Companies contribute a mean 2.88 and median 3 complete events, with a maximum of 8.

The event-level standardized H022 slope is `+1.562 pp` per one full-panel signal standard deviation. Spearman rho is `0.1147` with p=`0.0066`.

### Company-balanced

Equalizing total regression weight across companies leaves a positive slope of `+1.195 pp`.

Symbol-cluster bootstrap 95% CI: `[-0.286, +2.767] pp`.

The sign survives, but sampling uncertainty still includes zero.

### First complete event per company

The deterministic first-event sample contains 194 observations, one per company.

- standardized slope: `+1.014 pp`;
- bootstrap 95% CI: `[-1.478, +3.556] pp`;
- Spearman rho: `0.0197`, p=`0.7850`;
- top-quintile mean excess: `+2.12 pp`;
- bottom-quintile mean excess: `+1.87 pp`;
- top-minus-bottom spread: only `+0.25 pp`;
- top-quintile median excess: `-0.37 pp`;
- top-quintile benchmark beat rate: `50.0%`.

This is the most important caution from D004. The OLS sign remains positive, but the rank relation and high-signal long economics are not convincing when each company is represented only once.

### Non-overlapping same-company windows

Greedy de-overlap keeps 445 observations and removes 114 overlapping rows.

- standardized slope: `+1.825 pp`;
- bootstrap 95% CI: `[+0.501, +3.100] pp`;
- Spearman rho: `0.1351`, p=`0.0043`;
- top-minus-bottom spread: `+4.05 pp`;
- top-quintile mean excess: `+3.15 pp`;
- top-quintile median excess: `+2.18 pp`;
- top-quintile benchmark beat rate: `52.81%`.

Therefore overlapping 60-session windows do not explain the positive H022 relation.

### Publication-month fixed effects

The standardized H022 coefficient remains `+1.467 pp` after controlling for the nine publication months.

Symbol-cluster bootstrap 95% CI: `[+0.262, +2.754] pp`.

Calendar-month event clustering therefore does not explain the aggregate relationship.

## Scientific interpretation

D004 rules out two simple explanations reasonably well: same-company return-window overlap and publication-month clustering. It also shows that equalizing company contribution does not reverse the signal.

However, D004 does **not** establish robust one-shot cross-sectional stock selection. The first-event-only panel loses essentially all rank/quintile economics even though its OLS slope remains positive and uncertain. That pattern makes persistent company identity, company-specific source characteristics, or genuinely repeated within-company information changes a more important next falsification than another aggregate sector split.

The next direct test should therefore estimate H022 from **within-company variation**, for example company fixed effects / within-symbol demeaning, under a new frozen post-outcome diagnostic. Point-in-time size/free-float control remains a separate unresolved gate and still matters for the current-U001 composition question.

## What D004 cannot answer

D004 does not resolve point-in-time free-float market-cap selection, current-U001 survivorship, source availability differences, valuation, quality, or prospective replication. Those remain separate gates.
