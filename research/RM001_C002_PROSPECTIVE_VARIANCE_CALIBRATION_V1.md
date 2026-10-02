# RM001 C002 Prospective Variance-Level Calibration Challenger v1

Status: FROZEN BEFORE FIRST PROSPECTIVE C002 FORECAST
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Test whether a fixed multiplicative variance-level calibration improves
next-session RM001-v1 portfolio variance forecasts without changing factor
exposures, covariance structure, relative stock risk, or probe construction.

C001 established that RM001-v1 remains the best historical-OOS predictive risk
model among v1/v2/v3, but materially overpredicts aggregate variance.

C002 changes only the forecast level.

## Parent model

RM001-v1-DEVELOPMENT.

No parent exposure, factor-return, covariance-window, idiosyncratic-window or
identity rule changes.

## Frozen calibration scalar

Historical design source:

research/rm001-c001-result-v1.json

C001 RM001-v1 aggregate calibration ratio:

    realized variance / predicted variance
    = 0.5670928922826751

Frozen C002 scalar:

    CALIBRATION_SCALE = 0.5670928922826751

This value is treated as training/design information.

C002 does not reopen C001 to validate the scalar.

## Calibrated state transformation

For a valid RM001-v1 state:

- all factor exposures are unchanged;
- factor covariance matrix is multiplied by CALIBRATION_SCALE;
- every security idiosyncratic variance is multiplied by CALIBRATION_SCALE;
- idiosyncratic fallback p75 is multiplied by CALIBRATION_SCALE;
- security identity set and status labels are unchanged.

Therefore every portfolio variance forecast from the calibrated state is exactly:

    CALIBRATION_SCALE * raw RM001-v1 portfolio variance

up to RM001 canonical float rounding.

Model ID:

    RM001-v1-CAL1-DEVELOPMENT

## Prospective start boundary

Only decision sessions on or after:

    2026-10-05

are eligible.

No Sep 30 / Oct 1 source observations are backfilled into C002.

## Forecast timing

Decision session D is the latest completed NSE session with an AE001-SC001
eligible market source capture.

The raw v1 state, calibrated state and frozen probe library must be sealed before:

    09:05 Asia/Kolkata

on the next local observation date and before the next trading session opens.

A missed seal is permanently excluded and may not be backfilled.

## Frozen prospective probe library

C002 is v1-only and does not depend on SIZE.

Every probe is long-only, equal-weight and contains exactly 30 identities.

### Hash probes

8 probes:

    HASH00 through HASH07

Identity ranking:

    SHA256("RM001-C002|HASHxx|SYMBOL|ISIN")

### Factor-tail probes

LOW and HIGH portfolios for:

- BETA60_RELATIVE
- MOMENTUM20
- VOLATILITY60
- LIQUIDITY

Tail exposure source:

the same-day raw RM001-v1 state.

Total probes per ready date:

    16

Common current risk-state universe must contain at least 500 identities.

## Forecasts

For every sealed probe record both:

- raw RM001-v1 predicted daily variance;
- RM001-v1-CAL1 predicted daily variance.

The calibrated forecast is not independently refit.

## Realized target

For decision session D and next completed NSE session D+1:

    r_i = close_i(D+1) / close_i(D) - 1

Fixed-weight probe return:

    r_p = sum_i w_i * r_i

Target:

    realized_squared_return = r_p^2

A probe is unavailable if:

- exact symbol+ISIN identity is missing on either session;
- a share-changing corporate action occurs in (D, D+1];
- source evidence for D+1 is unavailable.

No constituent is removed or renormalized after outcome observation.

## Primary loss

QLIKE:

    log(predicted_variance)
    + realized_squared_return / predicted_variance

Paired per probe/date comparison:

    CAL1 - RAW_V1

Lower is better.

## Date aggregation and inference

For each decision date:

- require at least 12 valid probes;
- calculate mean QLIKE over valid probes for raw and CAL1;
- record paired CAL1-minus-RAW difference.

Prospective promotion sample:

    minimum 20 evaluated decision sessions

Inference:

- Newey-West Bartlett mean inference;
- lag = 5 sessions.

## Promotion classification

CAL1_SUPERIOR_PROSPECTIVE_RISK_CALIBRATION only if:

1. at least 20 decision sessions pass;
2. mean(CAL1 - RAW QLIKE) < 0;
3. 95% CI high(CAL1 - RAW) < 0.

Otherwise:

- INSUFFICIENT_PROSPECTIVE_SAMPLE, or
- NO_CAL1_PROSPECTIVE_SUPERIORITY.

## Secondary diagnostics

Report:

- raw aggregate calibration ratio;
- CAL1 aggregate calibration ratio;
- raw/calibrated mean predicted variance;
- realized mean squared return;
- underprediction fractions;
- mean absolute log variance ratio.

## Research boundaries

- no alpha use;
- no portfolio optimization;
- no realized-return-based probe selection;
- no sector inference;
- no size dependency;
- no scalar retuning after prospective outcomes begin;
- no live capital.

A positive result promotes CAL1 only as a risk-forecast calibration challenger.
It does not validate alpha or investment returns.
