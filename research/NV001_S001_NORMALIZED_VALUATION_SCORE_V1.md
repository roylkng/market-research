# NV001-S001 Own-History Normalized Valuation Research Score v1

Status: **FROZEN BEFORE SCORE MATERIALIZATION**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

NV001-S001 converts the already-passed NV001-D001-P1 point-in-time valuation panel
into one transparent company-specific normalized valuation research score.

This is not an alpha model and is not fitted to future stock returns.

Authoritative source input:

- diagnostic: `NV001-D001-P1-v1`;
- workflow run: `37193347012`;
- artifact ID: `11299713140`;
- source panel SHA-256:
  `3dbe5b914a532bb028ad38c6b6eec9762ef47f31ccc85289d1d1f9b69b251400`;
- frozen U001 universe SHA-256:
  `cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb`;
- companies with four historical P/E observations plus current P/E: 69.

No alternative source panel may be substituted under S001-v1.

## Eligibility

A company receives an S001 score only when:

1. exactly four valid historical annual trailing-P/E observations exist;
2. current 2026-10-01 trailing P/E exists;
3. every P/E used is finite and strictly positive.

No missing value is imputed.

Companies with fewer than four historical observations remain available as source
diagnostics but are not scored.

## Own-history anchor

For each eligible company:

`historical_median_pe = median(FY23_PE, FY24_PE, FY25_PE, FY26_PE)`

The median is used instead of the mean to reduce sensitivity to one historical
low-EPS/high-P/E year without introducing an outcome-tuned winsorization rule.

## Primary normalized valuation measure

`current_to_history_median = current_trailing_pe / historical_median_pe`

Interpretation:

- below 1.0: current trailing P/E is below the company's own four-observation median;
- equal to 1.0: current P/E equals its historical median;
- above 1.0: current P/E is above its historical median.

For display only:

`discount_to_history_median_pct = 100 * (1 - current_to_history_median)`

Positive display values mean a discount to the historical median.

## Cross-sectional score

The only scored variable is:

`-current_to_history_median`

Across all S001-eligible companies, use the midpoint empirical percentile:

`percentile = 100 * (count_less + 0.5 * count_equal) / N`

Higher score therefore means cheaper relative to the company's own four-point history.

No sector normalization, growth adjustment, quality adjustment, momentum adjustment,
forward estimate, target price, market-cap adjustment or return outcome enters S001.

## Historical dispersion context

Retain as context only:

- minimum historical P/E;
- maximum historical P/E;
- median historical P/E;
- current trailing P/E;
- current-to-median ratio;
- discount-to-median percent.

These fields do not alter the score.

## Top valuation quartile

For research navigation only:

- nominal size = `ceil(N / 4)`;
- score cutoff = score of the nominal final member;
- include all exact ties at the cutoff.

Top-quartile membership is not portfolio eligibility.

## Scientific boundary

S001 may be used as an additional research lens alongside RR001, DR001 and FQ001.

It may not:

- change H021's frozen EPS-revision gate;
- automatically promote or reject a company;
- create an Analyst Decision Object;
- alter PF001;
- authorize live capital;
- be blended with returns without a separately frozen trial.

Any change to source years, median definition, transform, eligibility, sector
normalization, forward valuation or score combination requires a new version frozen
before inspecting its investment outcomes.
