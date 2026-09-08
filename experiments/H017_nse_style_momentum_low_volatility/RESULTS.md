# H017 independent historical challenge result

Recorded: 2026-09-08

Status: **FAILED FROZEN GATE. LIVE CAPITAL DISABLED.**

H017 combined the already-frozen H016 dual-horizon momentum factor with an equally weighted low-volatility percentile, following NSE Indices' published multi-factor construction framework. It was tested on an untouched 2017-11 through 2019-11 semiannual decision window, with the final cohort held through May 2020.

## Integrity

- full repository checks passed before H017 outcomes,
- 883 official common NSE sessions reconstructed,
- 1,939 market symbols,
- zero market source asymmetry, parse errors or retries,
- all five cohorts evaluable,
- point-in-time company-only `INE` universe,
- future bars/actions did not affect selection.

## Primary H017 result

Across 214 selected company observations:

- mean Nifty 500 excess: **+1.288 pp**
- median Nifty 500 excess: **+2.149 pp**
- beat rate: **55.14%**
- mean gross stock return: **-1.565%**
- mean excess after frozen 0.50% friction: **+0.804 pp**
- fill rate: 100%
- lower-bound outcome rate: **3.27%**
- matched-random one-sided p-value: **0.00010**
- maximum single-ISIN share of positive selected return: **6.88%**

The full eligible company cohort had **-10.33 pp** mean Nifty 500 excess, so H017 materially protected capital relative to the cross-section during this difficult period.

## Frozen factor diagnostics

- low-volatility-only comparator: **+2.686 pp mean excess**, +1.877 pp median, 53.74% beat rate, 0.93% lower-bound rate
- H016 momentum-only comparator: **-3.807 pp mean excess**, -1.532 pp median, 45.79% beat rate
- raw 12-month momentum: -6.080 pp mean excess

Thus the low-volatility factor was stronger than the 50/50 H017 composite in this challenge. H017 may not be reweighted after observing that result.

## Cohort behavior

H017 mean excess by decision:

- 2017-11: -7.74 pp
- 2018-05: +2.55 pp
- 2018-11: -1.09 pp
- 2019-05: +3.14 pp
- 2019-11 through the COVID crash: **+12.49 pp**

Three of five cohorts were positive.

## Gate decision

Passed:

- all five cohorts evaluable,
- fill >=98%,
- median excess >0,
- beat rate >=55%,
- >=+2 pp lift over the full eligible cohort,
- matched-random p<=0.05,
- concentration <=15%,
- no two consecutive non-positive cohorts.

Failed:

- >=300 selected observations,
- lower-bound rate <=2%,
- mean excess >+2 pp,
- >=4/5 positive cohorts,
- friction-adjusted mean excess >+1.5 pp.

H017-v1 is retired. The low-volatility-only comparator motivates a separately frozen H018 because NSE Indices publishes low volatility as a standalone factor strategy. H017's 50/50 weight will not be changed.
