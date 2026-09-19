# H015 independent historical challenge result

Recorded: 2026-09-08

Status: **FAILED. LIVE CAPITAL DISABLED.**

H015 was frozen before any 2023-01 through 2024-03 company-only point-in-time selection or outcome was calculated. The final challenge run completed all market reconstruction, point-in-time selection, conservative post-selection outcome accounting and frozen metric calculation. The workflow failed only after `challenge-summary.json` was written, while serializing a diagnostic CSV whose rows had heterogeneous optional fields. That output-only failure does not alter the already-written H015 result.

## Integrity / source status

- pre-outcome `ruff` checks passed,
- full repository test suite: **305 passed**,
- hypothesis registry valid with live capital disabled,
- 516 common market sessions retained,
- 2,347 market symbols reconstructed,
- zero remaining bhavcopy/index asymmetry,
- zero remaining market parse errors,
- point-in-time company selections were written before the outcome layer,
- company identity required 12-character `INE` ISINs,
- selection eligibility did not inspect future stock bars or future corporate actions.

Historical NSE source repairs were frozen before selections: three internal index-date transpositions were accepted only when they matched the independently known archive session date, and the June 19, 2024 index file used an identical official NSE alternate-host path only after the primary-host retry failed.

## Coverage

H015 generated **10 active monthly cohorts** and **953 selected company observations**.

Primary execution integrity:

- next-session fill rate: **99.685%**
- conservative lower-bound outcome rate: **7.135%**
- max single-ISIN contribution to aggregate positive gross selected return: **1.993%**

The lower-bound rate exceeded the frozen <=2% gate. This is not the main reason H015 failed. Its measured returns were already negative.

## Primary H015 result

Across 953 selections:

- mean Nifty 500 excess: **-2.884 pp**
- median Nifty 500 excess: **-0.819 pp**
- Nifty 500 beat rate: **48.06%**
- mean gross stock return: **+3.289%**
- mean excess after frozen 0.50% filled-position friction: **-3.347 pp**
- matched-random one-sided empirical p-value for mean excess: **0.99950**
- positive active-cohort rate: **40%**

Frozen comparators were also weak:

- raw 120/5 momentum mean excess: -4.797 pp
- prior-60 momentum mean excess: -4.232 pp
- prior-20 momentum mean excess: -3.904 pp
- full eligible company cohort mean excess: -0.182 pp

H015 was less bad than the three momentum comparators but materially worse than simply holding the full eligible company cohort.

## Time stability

Active-cohort mean excess deteriorated after the initial 2023 recovery:

- 2023-Q2 median active-cohort excess: +4.192 pp
- 2023-Q3: -3.733 pp
- 2023-Q4: -5.043 pp
- 2024-Q1: -9.814 pp

The frozen breadth rule therefore did not solve momentum-regime instability.

## Frozen gate decision

Passed:

- active cohorts >=5,
- selected observations >=500,
- fill rate >=98%,
- superiority to raw 120/5 momentum,
- superiority to prior-60 momentum,
- concentration <=15%.

Failed:

- lower-bound rate <=2%,
- mean excess >+2 pp,
- median excess >0,
- beat rate >=52%,
- >=2/3 positive active cohorts,
- >=+2 pp lift over full eligible company cohort,
- random p<=0.05,
- quarter stability,
- mean friction-adjusted excess >+1.5 pp.

H015-v1 is retired. Its breadth thresholds, score or gates must not be tuned after this failure.

## Next scientific pivot

The repeated 60-session momentum variants are now rejected as the primary company-selection mechanism. The next hypothesis is externally anchored rather than derived from H015 residuals: reproduce the dual-horizon normalized momentum construction published by NSE Indices, which combines volatility-adjusted 6-month and 12-month momentum ratios using cross-sectional z-scores and is reconstituted semi-annually.

That successor will be tested first on an older historical window not used by H005-H015, using the same company-only point-in-time and conservative post-selection integrity rules.
