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

### 2. Non-overlap company fixed effects

Reuse the exact D004 greedy same-company non-overlap selector, retain only companies with at least two remaining events, and run the same within-company estimator. Minimum coverage: 70 companies and 180 observations.

### 3. Highest-vs-lowest H022 event pair

For every company with at least two complete events and at least two distinct H022 values, select the highest-H022 and lowest-H022 events using signal only, break ties by source ID, and compute `future_excess_high - future_excess_low`. Minimum coverage: 100 company pairs.

## Frozen bootstrap

- unit: company;
- iterations: 10,000;
- base seed: `22027`;
- interval: percentile 95%.

## Frozen interpretation

`DATA_INSUFFICIENT` if any preregistered coverage gate fails. Otherwise `WITHIN_POSITIVE` requires the full company-FE slope, non-overlap company-FE slope and mean high-minus-low paired difference all to be strictly positive. `WITHIN_SIGN_UNSTABLE` applies otherwise.

Bootstrap support is `ALL_INTERVALS_POSITIVE` only if all three lower bounds exceed zero; otherwise it is `MIXED_OR_UNCERTAIN`.

## Result

Authoritative summary SHA-256:
`0c3b5b8002aa2b4f13822f90f0300044f58f97551ad8dc99d1c6074d90532ab3`

Frozen sign classification: **`WITHIN_POSITIVE`**.

Bootstrap support: **`MIXED_OR_UNCERTAIN`**.

### Company fixed effects

The full within-company sample contains 541 observations from 176 companies.

- standardized H022 within slope: `+1.720 pp` per full-panel signal SD;
- company-bootstrap 95% CI: `[+0.463, +3.122] pp`;
- within-company Spearman rho: `0.1568`, p=`0.00025`.

This is strong evidence that the H022 relationship is not solely a persistent cross-company identity effect.

### Non-overlap company fixed effects

D004's deterministic de-overlap leaves 445 observations overall. After requiring at least two retained events per company, D005 uses 420 observations from 169 companies.

- standardized H022 within slope: `+2.482 pp`;
- company-bootstrap 95% CI: `[+0.956, +3.949] pp`;
- within-company Spearman rho: `0.1866`, p=`0.00012`.

The within-company effect strengthens rather than disappears after overlapping same-company 60-session windows are removed.

### Highest-vs-lowest H022 event pairs

There are 145 companies with at least two distinct H022 values.

- mean future-excess difference, highest minus lowest H022: `+2.947 pp`;
- median difference: `+4.523 pp`;
- positive-pair share: `58.62%`;
- bootstrap 95% CI for the mean: `[-0.540, +6.356] pp`.

The paired point estimates agree with the fixed-effect direction, but the paired mean is not independently bootstrap-significant. This is why overall bootstrap support remains `MIXED_OR_UNCERTAIN`.

## Scientific interpretation

D005 materially reduces the persistent-company-confound concern raised by D004. The H022 signal predicts future benchmark-relative return from **variation within the same company**, and the effect remains positive with a fully positive bootstrap interval after same-company overlapping windows are removed.

This does not rescue the expanded NIFTY 200 historical challenge from its frozen `INCONCLUSIVE` classification, and it does not make the original survivor-panel result validation. It does, however, strengthen the case that management-information delta contains genuine event-level information rather than merely tagging a fixed set of historically better companies.

The major unresolved historical composition gate is now point-in-time size/free-float selection. The next work should determine whether an official/reproducible historical free-float market-cap source exists for reconstructing the U001-style top-100 non-financial slice. If that cannot be sourced without hindsight, the project should stop forcing historical reconstruction and rely on frozen prospective cohorts instead.

Prospective confirmation remains mandatory. Live capital remains disabled.
