# AE001 T006 Model Freeze Amendment P1

Status: FROZEN BEFORE MODEL MATERIALIZATION
Frozen: 2026-09-30
Live capital: DISABLED

## Purpose

Freeze the exact historical training state and immutable model contract for the
T006 prospective stock-futures confirmation before its first eligible decision
session.

## Source end date

2026-09-25.

## Training horizon

5 completed NSE sessions.

Only examples whose 5-session label exit is on or before 2026-09-25 may enter
training.

## Training sample

Exact futures-complete, action-safe historical rows from the frozen T005 source
chain.

Base and augmented models use identical stock/session rows and labels.

## Models

### CORE27

- ridge;
- l2 = 1.0;
- exact 27 price/liquidity/delivery features.

### FULL37

- ridge;
- l2 = 1.0;
- exact CORE27;
- plus exact ten T005 futures features.

## Frozen source hashes

- market panel:
  9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e
- corporate-action ledger:
  1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1
- delivery feature panel:
  99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90
- futures panel:
  02656c828a1d5fe22660c154a445ebd69a7492b56f1807da0d8c959a6f0c11d5
- futures feature panel:
  62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f

Any mismatch fails closed.

## Serialization

The frozen artifact must preserve for each model:

- model ID;
- feature order;
- training medians;
- training means;
- training scales;
- coefficients;
- intercept;
- l2;
- training example count;
- training last exit session;
- model SHA-256.

The artifact also binds all source-panel hashes and training exclusions.

## Retraining

Prohibited during T006.

No rolling refit is allowed.

A different training window or model requires a new confirmatory trial.

## Earliest decision session

2026-10-01.

The model artifact must be committed before any T006 decision from that date is
eligible.

Live capital remains disabled.
