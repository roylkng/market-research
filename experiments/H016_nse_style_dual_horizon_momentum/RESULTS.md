# H016 independent historical challenge result

Recorded: 2026-09-08

Status: **FAILED FROZEN GATE. LIVE CAPITAL DISABLED.**

H016 was frozen before any H016 score or return was calculated. Its signal was externally anchored to NSE Indices' published dual-horizon normalized momentum methodology rather than fitted to H015 residuals. The first challenge used five untouched semiannual company-selection cohorts from November 2020 through November 2022.

## Source / execution integrity

- full repository checks passed before first H016 outcome,
- exact official NSE market and Nifty index bytes retained,
- 866 common sessions reconstructed,
- 2,241 market symbols,
- zero unresolved market-source asymmetry or parse errors,
- all five frozen decision cohorts evaluated,
- point-in-time company-only universe based on `INE` ISINs,
- future bars and future corporate actions did not affect selection eligibility,
- 320 selected company observations.

## Primary result

Across all 320 frozen top-decile selections:

- mean Nifty 500 excess: **+4.735 pp**
- median Nifty 500 excess: **+2.063 pp**
- Nifty 500 beat rate: **51.88%**
- mean gross stock return: **+11.93%**
- mean excess after frozen 0.50% filled-position friction: **+4.264 pp**
- fill rate: **99.375%**
- conservative lower-bound outcome rate: **5.00%**
- matched-random one-sided empirical p-value for mean excess: **0.07019**
- maximum single-ISIN share of aggregate positive gross return: **4.89%**

The full eligible company cohort had +1.945 pp mean Nifty 500 excess, so H016 exceeded it by about +2.79 pp.

Frozen single-factor diagnostics:

- 6-month volatility-adjusted momentum ratio mean excess: +2.01 pp
- 12-month volatility-adjusted momentum ratio mean excess: +1.78 pp
- raw 6-month momentum mean excess: +1.53 pp
- raw 12-month momentum mean excess: +1.14 pp

The externally specified dual-horizon combination therefore improved the average result materially over each single-horizon diagnostic in this sample.

## Cohort stability

- 2020-11 decision: +39.42 pp mean excess, 71.15% beat rate
- 2021-05: -10.98 pp, 43.66% beat
- 2021-11: +0.50 pp, 44.62% beat
- 2022-05: -4.63 pp, 43.55% beat
- 2022-11: +7.14 pp, 60.00% beat

Only 3 of 5 cohorts were positive. The strong aggregate mean was materially influenced by the 2020 recovery cohort.

## Frozen gate decision

Passed:

- all five cohorts evaluable,
- >=300 selections,
- fill rate >=98%,
- mean gross excess >+2 pp,
- median gross excess >0,
- >=+2 pp lift over the full eligible company cohort,
- ISIN concentration <=15%,
- no two consecutive non-positive cohorts,
- friction-adjusted mean excess >+1.5 pp.

Failed:

- lower-bound outcome rate <=2%,
- selected-company beat rate >=55%,
- >=4 of 5 positive cohorts,
- matched-random p<=0.05.

H016-v1 therefore fails its preregistered independent gate and does not advance to its second historical challenge.

## Implication

The published NSE-style dual-horizon construction is clearly stronger than the project's prior 60-session momentum variants, but the company-level edge remains too episodic under this broader company universe. The next hypothesis may not tune H016's 6/12-month weights. A separately frozen multi-factor successor will test whether an explicit low-volatility component can convert the favorable mean/median into broader cross-company consistency, using another untouched historical period.
