# RM001 C001 Historical OOS Risk-Forecast Calibration v1

Status: FROZEN BEFORE CALIBRATION OUTCOMES
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Determine whether RM001-v3 forecasts next-session portfolio variance more
accurately than RM001-v1 and RM001-v2.

C001 exists because I005 established that RM001-v3 materially changes portfolio
weights, but did not establish that the additional SIZE/statistical risk factors
improve future risk forecasts.

No optimizer is used in C001.

## Evidence class

HISTORICAL_RECONSTRUCTION_OOS_RISK_CALIBRATION

All risk states are reconstructed point in time using only information available
through each decision session.

The next completed NSE session is used only after the forecast is frozen for
scoring.

## Historical source window

Official NSE market and corporate-action evidence:

    2025-09-01 through 2026-09-25

Official NSE Security File size evidence is reconstructed over the exact same
completed-session market panel.

Candidate calibration decision sessions:

    2026-04-01 through 2026-09-24

A candidate date is evaluated only if all three frozen risk models can build a
valid state and a next completed NSE session exists.

## Frozen models

### RM001-v1-DEVELOPMENT

Factors:

- MARKET_COMMON
- BETA60_RELATIVE
- MOMENTUM20
- VOLATILITY60
- LIQUIDITY

### RM001-v2-DEVELOPMENT

v1 plus:

- SIZE

### RM001-v3-DEVELOPMENT

v2 plus frozen statistical residual factors:

- STAT_PC01
- STAT_PC02
- STAT_PC03
- STAT_PC04
- STAT_PC05

No model parameter is changed by C001.

## Common forecast universe

For each decision session D:

1. build v1, v2 and v3 risk states as of D;
2. intersect exact symbol + ISIN identities present in all three states;
3. require at least 500 common identities.

Probe portfolios are constructed only from this same-day common universe.

No next-session information enters probe construction.

## Frozen probe library

Every probe is long-only, equal-weight and contains exactly 30 identities.

### Deterministic identity probes

Eight portfolios:

    HASH00 through HASH07

For HASHxx:

1. compute SHA-256 of:

       "RM001-C001|HASHxx|SYMBOL|ISIN"

2. sort current common identities lexicographically by hash, then symbol, ISIN;
3. take the first 30.

These portfolios are independent of model exposures and future outcomes.

### Factor-tail probes

For each factor below, create LOW and HIGH portfolios:

- BETA60_RELATIVE
- MOMENTUM20
- VOLATILITY60
- LIQUIDITY
- SIZE

Exposure source for probe construction:

- BETA/MOMENTUM/VOLATILITY/LIQUIDITY: RM001-v2 same-day exposure;
- SIZE: RM001-v2 same-day SIZE exposure.

LOW:

- 30 smallest exposures;
- ties break by symbol then ISIN.

HIGH:

- 30 largest exposures;
- ties break by symbol then ISIN.

Total frozen probe count per decision session:

    18

## Forecast metric

For each risk model m and probe p:

    predicted_variance_daily(m,p,D)

is computed using that model's frozen portfolio-risk function and same-day risk
state.

Predicted variance must be finite and strictly positive.

## Realized target

Let D+1 be the next completed NSE session.

For every probe identity:

    r_i = close_i(D+1) / close_i(D) - 1

The fixed-weight portfolio return is:

    r_p = sum_i w_i * r_i

Realized variance proxy:

    realized_squared_return = r_p^2

A probe/date is scored only when:

- every constituent has the same exact symbol + ISIN identity on D and D+1;
- no constituent has a share-changing corporate action in (D, D+1].

If either rule fails, that probe/date is unavailable for all three models.

No weight renormalization after seeing D+1 is allowed.

## Primary proper scoring loss

QLIKE:

    loss = log(predicted_variance) + realized_squared_return / predicted_variance

Lower is better.

Because the realized target is identical across models, paired QLIKE differences
directly compare variance forecasts.

## Secondary calibration diagnostics

Per model report:

- mean predicted daily variance;
- mean realized squared return;
- aggregate calibration ratio:

      sum(realized_squared_return) / sum(predicted_variance)

- mean absolute log variance ratio, using:

      abs(log((realized_squared_return + epsilon) /
              (predicted_variance + epsilon)))

  with frozen epsilon = 1e-12;

- fraction of scored probes where:

      realized_squared_return > predicted_variance

- mean QLIKE by probe family.

These are diagnostics. QLIKE is primary.

## Date-level aggregation

For each decision session and model:

- calculate mean QLIKE over all valid probes for that date.

A decision session enters paired model inference only when at least:

    12 valid probes

exist on that date.

## Paired inference

For date-level mean QLIKE:

- v3 minus v1;
- v3 minus v2;
- v2 minus v1.

Use the existing MarketLab Newey-West Bartlett mean inference.

Frozen lag:

    5 sessions

Lower QLIKE is better, so a negative difference favors the left model.

## Minimum sample

Required evaluated decision sessions:

    40

Required valid probes per included date:

    12

If fewer than 40 dates satisfy the gate:

    INSUFFICIENT_CALIBRATION_SAMPLE

## Frozen classification

### V3_SUPERIOR_OOS_RISK_FORECAST

Only if:

1. minimum sample gate passes;
2. mean(v3 - v1 QLIKE) < 0;
3. 95% CI high(v3 - v1) < 0;
4. mean(v3 - v2 QLIKE) < 0;
5. 95% CI high(v3 - v2) < 0.

### V3_MIXED_OOS_RISK_FORECAST

If sample gate passes, V3_SUPERIOR does not apply, and either:

- one of the two v3 paired comparisons has CI high < 0; or
- both v3 paired mean differences are negative but at least one CI crosses 0.

### NO_V3_OOS_RISK_SUPERIORITY

If sample gate passes and neither class above applies.

## Interpretation

A superior C001 result means only that RM001-v3 produced better one-step
portfolio variance forecasts on the frozen historical-OOS probe library.

It does NOT establish:

- future prospective calibration;
- alpha improvement;
- better realized investment returns;
- live-capital readiness.

A non-superior result does not invalidate v3's descriptive factor attribution.
It means the added risk structure has not earned a forecast-accuracy promotion.

## Prohibited

- no portfolio optimization;
- no realized-return-based probe selection;
- no model hyperparameter change;
- no change to probe count or sample thresholds after results;
- no sector proxy fabrication;
- no live capital.
