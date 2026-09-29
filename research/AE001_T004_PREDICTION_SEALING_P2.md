# AE001 T004 Prediction Sealing Amendment P2

Status: FROZEN BEFORE FIRST ELIGIBLE T004 DECISION SESSION
Frozen: 2026-09-29

## Purpose

Define the causal boundary between source observation time and prediction
computation time for T004.

## Information cutoff

18:30:00 Asia/Kolkata on the feature session.

The cutoff applies to information, not CPU completion time.

## Same-session source rule

The current feature session may use only the exact NSE UDiFF and delivery source
bytes referenced by the SC001 attempt that established:

`eligible_before_cutoff = true`.

Those current-session bytes may not be replaced by a later archive download,
later corrected file or another same-day source.

Their SHA-256 values are part of the sealed T004 prediction artifact.

## Allowed post-cutoff computation

After 18:30 IST, T004 may:

- parse the already-captured same-session SC001 files;
- retrieve prior-session historical market/delivery files;
- reconstruct prior rolling history;
- run corporate-action integrity checks limited to ex-dates on or before the
  feature session;
- compute the frozen 27 features;
- apply the frozen T004 base and augmented models;
- serialize and seal predictions.

These operations do not permit new current-session information.

## Prohibited post-cutoff information

T004 may not use:

- a current-session market or delivery source not present in the eligible SC001
  attempt;
- current-session news, filings, estimates, index moves or other information
  observed after 18:30;
- next-session price data;
- any outcome label;
- refitted model parameters.

## Prediction sealing deadline

A T004 prediction must be sealed before the next completed NSE cash-market
session opens.

If prediction sealing misses that entry boundary, the feature session is not a
valid T004 decision session and cannot be backfilled.

## Feature-history reconstruction

Prior-session history is historical information at the decision cutoff.

T004 may reconstruct it after cutoff from official archives, but:

- the current feature session must always use SC001 bytes;
- the rolling history must end at the exact SC001 current session;
- symbol + ISIN continuity remains mandatory;
- T003-P3 source-quality exclusions remain mandatory;
- corporate-action lookback remains fail-closed.

## Models

Use only:

- base model SHA
  5ffe30f85ee1bbae920ed661d5cb8c9c68afd72e2e1541c0faef42716b5de2e7;
- augmented model SHA
  4b8626288f1dcfb1f881046559fe906acdeaa5c9fe31d759e4412ee1e7649d3f.

No retraining.

## Prospective artifact

Each valid T004 feature session seals:

- SC001 attempt hash;
- current UDiFF SHA;
- current delivery SHA;
- reconstructed feature-panel hash;
- frozen model artifact hash;
- base model hash;
- augmented model hash;
- common prediction-row count;
- exact per-stock base and augmented predictions;
- prediction seal timestamp;
- no outcomes.

## Live capital

Disabled.
