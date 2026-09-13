# H022 composition and industry attribution diagnostic

Status: **POST_OUTCOME_DIAGNOSTIC_COMPLETE**

Diagnostic: `H022-D002`

Live capital: **DISABLED**

This diagnostic cannot upgrade H022 validation.

## Why this diagnostic exists

The original current-U001 historical replay classified H022 as `PROMISING`, but the broader point-in-time Nifty 200 challenger classified it `INCONCLUSIVE`.

H022-D002 asks two explanatory questions without changing H022-R001 or H022-X001:

1. Is the attenuation concentrated in the companies that are outside the frozen Sep-2026 current-U001 cohort?
2. Is the remaining H022 relationship merely an industry-composition effect?

The analysis contract, bootstrap seed, coverage gates and descriptive classifications were committed and passed CI before these subgroup results were opened.

## Frozen inputs

- expanded 60-session outcome report SHA-256: `310d3709393047db4ec5e2eacb9d333fac2d81b83e86bc65140dc4bc60c6d22f`;
- historical Nifty 200 reconstruction SHA-256: `dee26ffc683781202da21e789cc45f480d625772e8510f3beb1f65aa4a6ba144`;
- current U001 cohort: `FY27-Q2-2026-09-06`, 100 frozen members;
- complete primary 60-session rows: **559**;
- symbol-cluster bootstrap: **10,000 iterations**, seed `22024`.

Diagnostic panel SHA-256:
`907a88c1ed2bfddd650ec589799660f1d26aa8d4c678f787bb3b9d765a05b17a`

Diagnostic summary SHA-256:
`6598faa595223e55155b81574b55a8e66e4b5063005e5aba9a6289581d38d876`

## 1. Current-U001 versus additional historical Nifty 200 members

The frozen sign-based composition classification is **BROAD_POSITIVE**, because the standardized H022 slope is positive in both groups.

That label should not be read as equal strength across the groups. The detailed evidence is asymmetric.

| Metric | Current U001 | Additional historical Nifty 200 |
| --- | ---: | ---: |
| Complete observations | 287 | 272 |
| Symbols | 94 | 100 |
| Spearman H022 vs future excess | 0.1463 | 0.0931 |
| Spearman p-value | 0.0131 | 0.1258 |
| Top-quintile mean excess | +5.69 pp | +0.44 pp |
| Bottom-quintile mean excess | +2.15 pp | +0.19 pp |
| Top-minus-bottom spread | **+3.53 pp** | **+0.25 pp** |
| Top-quintile median excess | +5.75 pp | -0.63 pp |
| Top-quintile benchmark beat rate | **56.14%** | **48.15%** |

The standardized regression slopes are:

- additional historical Nifty 200: **+0.99 pp** per 1 SD of H022 signal;
- current U001: **+2.19 pp** per 1 SD;
- incremental current-U001 interaction: **+1.20 pp**.

Company-cluster bootstrap 95% intervals:

- additional slope: **[-0.36, +2.18] pp**;
- current-U001 slope: **[+0.32, +4.49] pp**;
- interaction: **[-1.05, +3.78] pp**.

### Interpretation

The practical ranking result is clearly stronger inside the current-U001 subset. The additional historical Nifty 200 group does not independently reproduce the original quintile economics: its spread is near zero, median is negative and beat rate is below 50%.

However, the interaction interval crosses zero. Therefore D002 does **not** establish that the two population slopes are statistically different. The defensible statement is:

> Current-U001 composition appears to amplify H022 materially, while the expanded-only group provides weak standalone ranking evidence; the difference in regression slopes is not statistically established by this diagnostic.

This variable is not a pure survivorship indicator. Current U001 also reflects Sep-2026 size ranking and the non-financial selection contract, so D002 cannot identify which part of the composition difference causes the attenuation.

## 2. Industry fixed-effect attribution

Industry data are available for **543 / 559 = 97.14%** of complete observations, above the frozen 90% coverage gate. Sixteen observations have no frozen industry label and are excluded from the industry regression; they are not manually backfilled.

The frozen industry diagnostic classification is **SUPPORTIVE_BREADTH**.

Results:

- official-industry categories represented: **18**;
- standardized H022 coefficient after industry fixed effects: **+1.5320 pp**;
- company-cluster bootstrap 95% CI: **[+0.2952, +2.7657] pp**;
- 10,000 / 10,000 bootstrap iterations valid;
- leave-one-industry-out coefficient range: **+1.1925 to +1.7935 pp**.

Every leave-one-industry-out coefficient remains positive. Therefore the aggregate H022 relationship is not explained by one dominant industry under this frozen taxonomy.

### Important distinction

`SUPPORTIVE_BREADTH` does **not** mean H022 works independently inside every industry. Individual industry samples are small and noisy, and several have negative within-industry quintile spreads. For example, Information Technology, Consumer Durables, Healthcare and some other groups are negative in the descriptive subgroup tables, while Capital Goods, Power, Automobile/Auto Components and Realty are positive.

The fixed-effect result answers a narrower question: after absorbing average industry-level return differences, the cross-company H022 coefficient remains positive and bootstrap-supported, and no single industry removal eliminates it.

## Industry taxonomy limitation

The industry field comes from the frozen H022-UH001 reconstruction. For the 200 Aug-2026 anchor members it originates from the official Nifty 200 constituent CSV as of 2026-08-31. The 11 March-2026 exclusions intentionally have `industry=null` because their industry was not recovered from the frozen official anchor.

Therefore D002 uses a **frozen static industry taxonomy**, not a separately reconstructed event-date historical industry classification. This is adequate for a concentration diagnostic but should not be described as a fully point-in-time sector-factor model.

## What D002 changes in our interpretation

D002 narrows the reason for the PR #77 attenuation:

1. **Sector composition alone is not a convincing explanation.** H022 remains positive after industry fixed effects and after removing any one industry.
2. **Universe composition matters materially in the descriptive economics.** The current-U001 half retains the original-style signal; the additional historical Nifty 200 half is weak on its own.
3. **We still cannot call the original signal robust across the broader universe.** PR #77 remains `INCONCLUSIVE`; D002 cannot upgrade it.
4. **We cannot call the difference causal survivorship bias.** Current-U001 membership also encodes size and non-financial selection.
5. **The 120-session secondary effect remains discredited as robust evidence.** D002 is about the frozen 60-session primary horizon only.

## Next falsification gates

Do not tune H022-R001 from these subgroup results. The next useful tests are:

1. separate **financial vs non-financial** composition, because the expanded challenger deliberately introduced financials while historical U001 excluded them;
2. point-in-time or reproducibly lagged **size / free-float market-cap control**, to distinguish current-U001 size selection from transcript signal;
3. overlapping-window/repeated-company dependence and event-clustering diagnostics;
4. prospective confirmation on future frozen cohorts.

Any size-conditioned, non-financial-only, industry-conditioned or H022 x membership model must be preregistered as a new challenger. None may replace the frozen H022-R001 result after the fact.
