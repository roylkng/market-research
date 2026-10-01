# AE001 T009 Protocol Amendment P2: Non-Blocking Unlearnable Single-Feature Diagnostics

Frozen: 2026-10-01
Status: FROZEN AFTER FAILED OUTCOME MATERIALIZATION AND BEFORE RETRY
Live capital: DISABLED

## Trigger

The first T009 outcome run, GitHub Actions run 36824004775, reproduced all
frozen source and feature artifacts exactly and entered the frozen walk-forward
analysis.

The run failed before producing a T009 report or result event.

Failure:

`opt_front_log1p_days_to_expiry: cannot learn direction without training rank IC`

The exception originated in the shared signed-single-feature diagnostics executed
after ridge OOS predictions are constructed.

## Scientific classification

This is an implementation failure in an auxiliary diagnostic.

It is NOT a change to the T009 source, feature family, label, model, fold, l2,
primary endpoint or success criterion.

The failing feature remains in the frozen 47-feature augmented ridge.

It is not dropped, imputed, directionally signed, or otherwise altered.

## Frozen repair

For signed-single-feature diagnostics only:

- if a feature has no purged-training mean rank IC because cross-sectional rank
  correlation is undefined, that feature is recorded as
  `UNAVAILABLE_TRAINING_RANK_IC`;
- its single-feature direction remains null;
- no OOS single-feature prediction is emitted for that feature in that fold;
- it is excluded from training-only "best single feature" selection for that fold;
- all features with learnable training rank IC retain the pre-existing direction
  and selection rules;
- if every feature in a fold is unlearnable, the diagnostic still fails closed.

The multivariate ridge model continues to receive the feature exactly as frozen.

## Frozen T009 analysis remains unchanged

Base model:
- 37 frozen T005 features.

Augmented model:
- same 37 features plus all ten frozen T009 option features.

Unchanged:
- exact P1 source hashes;
- option-complete sample;
- exact symbol+ISIN rows;
- ridge l2 = 1.0;
- 1D / 5D / 20D folds;
- action-safe labels;
- paired Newey-West inference;
- primary 5D success criteria.

## Outcome boundary

Run 36824004775 produced no canonical T009 report and no
`TRIAL_RESULT_RECORDED` event.

No T009 metric observed from that failed run is used to choose this repair.

This amendment only permits the frozen trial to complete when an auxiliary
single-feature diagnostic is undefined.

No prospective or live-capital claim is created.
