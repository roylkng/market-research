# H022 financial-composition diagnostic

Status: **POST_OUTCOME_DIAGNOSTIC_COMPLETE**

Diagnostic: `H022-D003`

Live capital: **DISABLED**

This diagnostic cannot upgrade H022 validation.

## Question

The point-in-time Nifty 200 challenger weakened materially versus the original current-U001 replay. One concrete universe-design difference is that U001 excludes financials while the full historical Nifty 200 challenger includes Financial Services.

H022-D003 asks whether that single composition difference explains the attenuation.

The answer is **no**.

## Frozen-before-result contract

- input D002 diagnostic panel SHA-256: `907a88c1ed2bfddd650ec589799660f1d26aa8d4c678f787bb3b9d765a05b17a`;
- complete 60-session observations: **559**;
- frozen financial label: exact `Financial Services` value from the existing H022-UH001 industry field;
- null-industry observations: excluded, never manually backfilled;
- additional-group regression: future excess on standardized H022 signal, financial indicator and interaction;
- symbol-cluster bootstrap: **10,000 iterations**, seed `22025`;
- additional-nonfinancial recovery check frozen before output opening:
  - at least 100 observations;
  - top-minus-bottom spread >= 2 pp;
  - top-quintile median > 0;
  - top-quintile benchmark beat rate >= 55%.

These are descriptive post-outcome gates only. They cannot promote H022.

Authoritative summary SHA-256:

`557e232b2a3bddcd70e2a47d2c92dd8215e59e6d5c70492cd96537d3d0356ce7`

## Cell results

| Metric | Current U001 non-financial | Additional non-financial | Additional financial |
| --- | ---: | ---: | ---: |
| Observations | 287 | 132 | 124 |
| Symbols | 94 | 47 | 44 |
| Spearman | 0.1463 | 0.1180 | 0.0603 |
| Spearman p-value | 0.0131 | 0.1779 | 0.5061 |
| Top-quintile mean excess | **+5.69 pp** | **+0.08 pp** | **+1.99 pp** |
| Bottom-quintile mean excess | +2.15 pp | **-4.02 pp** | +0.87 pp |
| Top-minus-bottom spread | **+3.53 pp** | **+4.10 pp** | +1.12 pp |
| Top-quintile median excess | **+5.75 pp** | **-1.08 pp** | +1.22 pp |
| Top-quintile benchmark beat rate | **56.14%** | **42.31%** | 58.33% |

The frozen additional-nonfinancial recovery classification is:

**`DOES_NOT_RECOVER_PROMISING_STYLE`**.

## Why the +4.10 pp non-financial spread is misleading if read alone

The additional non-financial cell has a visually large top-minus-bottom spread, but its top-quintile mean is only **+0.08 pp**. The spread is created primarily by a very weak bottom quintile (**-4.02 pp**), not by a strong high-signal portfolio.

The other preregistered descriptive checks confirm this:

- top-quintile median is **-1.08 pp**;
- top-quintile benchmark beat rate is only **42.31%**.

Therefore filtering out financials does not recreate the economically attractive top-quintile behavior seen in current U001.

This distinction matters for the actual investment objective. A signal that mainly identifies losers at the bottom can be useful for avoidance or long-short research, but it is not equivalent to selecting high-upside long candidates.

## Additional-group regression

Within the labelled additional historical Nifty 200 sample:

- standardized H022 slope, non-financial: **+1.280 pp**;
- standardized H022 slope, financial: **+0.526 pp**;
- financial interaction: **-0.754 pp**.

Company-cluster bootstrap 95% intervals:

- non-financial slope: **[-0.329, +2.574] pp**;
- financial slope: **[-3.133, +3.668] pp**;
- interaction: **[-4.715, +2.707] pp**.

All three intervals cross zero. D003 therefore does not establish a statistically distinct financial versus non-financial H022 slope.

## Interpretation

D003 falsifies the simple explanation that the PR #77 attenuation arose mainly because the broader Nifty 200 sample introduced Financial Services.

The stronger statement is:

1. current-U001 non-financial names retain materially better high-signal long-selection economics;
2. additional non-financial names do **not** recover those economics after financials are removed;
3. additional financial names are also weak as a ranked H022 selection sample;
4. financial/non-financial interaction is highly uncertain;
5. therefore the remaining composition sensitivity is more likely related to **current-U001 membership itself, current size/free-float selection, survivorship, source/company characteristics, or dependence/regime structure**, not merely financial-sector inclusion.

## Research boundary

This diagnostic uses the frozen static H022-UH001 industry taxonomy. It is not event-date historical sector classification.

No financial or non-financial filter may be retrofitted into H022-R001 from this result. If such a filter is ever tested as a selection model, it must be a separately frozen challenger.

PR #77 remains `INCONCLUSIVE`. D003 does not promote it, and live capital remains disabled.

## Next gates

The highest-value next falsifications are now:

1. repeated-company / overlapping-window / calendar-regime dependence;
2. reproducible point-in-time size or free-float market-cap attribution, if a defensible historical source can be established;
3. prospective confirmation on future frozen cohorts.

The stale top-level H022 hypothesis record should also be updated so it no longer presents the original survivor-panel PROMISING result and 120-session secondary result without the later universe-challenge evidence.
