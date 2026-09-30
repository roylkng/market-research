# AE001 T005 Protocol Amendment P2: Frozen Upstream AE001 Source Chain

Frozen: 2026-09-30
Status: FROZEN BEFORE OUTCOME MATERIALIZATION
Live capital: DISABLED

## Purpose

T005 tests only the incremental information in the new NSE stock-futures feature
family.

Therefore all pre-existing AE001 market/action/delivery inputs must reproduce
the already-sealed T003/P002 source chain exactly before T005 may open outcomes.

## Required upstream hashes

Market panel:

`9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e`

Action-safe base feature panel:

`300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8`

Corporate-action ledger:

`1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1`

Delivery-augmented 27-feature panel:

`99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90`

Any mismatch fails closed before T005 base/augmented model fitting.

## New FO input

The T005 futures panel and 37-feature augmented panel are new artifacts and
therefore do not have pre-existing hashes.

Their exact hashes, source availability counts and exclusions must be sealed in
the T005 result.

## Non-changes

P2 changes no:

- T005 feature;
- fold;
- horizon;
- ridge parameter;
- success criterion;
- outcome.

No prospective or live-capital claim.

Canonical ledger append retried from stable T005 implementation head before any outcome run.
