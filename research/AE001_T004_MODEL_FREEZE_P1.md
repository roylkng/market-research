# AE001 T004 Model Freeze Amendment P1

Status: FROZEN BEFORE FIRST ELIGIBLE T004 DECISION SESSION
Frozen: 2026-09-29

## Purpose

Freeze T004 model training state before prospective evaluation begins.

## Training source window

Historical-development source data through 2026-09-25 only.

No market, delivery, label or corporate-action information dated after
2026-09-25 may enter the frozen model fit.

## Training target

Five completed NSE session excess return:

stock return minus Nifty 500 return from next completed session open through
holding-session-5 close.

Only examples whose five-session exit is on or before 2026-09-25 are eligible
for training.

## Sample

Both base and augmented models are fit on the exact same historical
delivery-complete, action-safe stock-date examples.

The sample uses the T003-P3 delivery source-quality rule.

## Feature transforms

Within-session tie-aware percentile transformation, identical to AE001 T003.

## Models

Base:
- ridge;
- l2 = 1.0;
- frozen 18 price/liquidity features.

Augmented:
- ridge;
- l2 = 1.0;
- same 18 features;
- plus frozen nine delivery/VWAP features.

## Missing values

Frozen AE001 ridge training behavior applies.

No new imputation rule may be introduced.

## Freeze behavior

The resulting serialized ridge coefficients, intercept, training medians,
training means, training scales, feature ordering, training example count,
training last exit session, model hash and source panel hashes are immutable
T004 inputs.

No retraining is permitted during the T004 primary confirmatory period.

A different model fit or training window requires a new trial ID or an explicit
new confirmatory trial after T004 completes.

## Prospective inference

Every eligible T004 decision session applies the two frozen models to the same
prospective feature rows.

No future T004 outcome can alter the model state.

## Live capital

Disabled.
