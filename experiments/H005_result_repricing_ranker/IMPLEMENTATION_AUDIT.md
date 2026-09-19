# H005 implementation audit and continuation checkpoint

Recorded: 2026-09-08

**Implementation verification: PASS. Historical market validation: NOT RUN in this repair. Prospective validation: NOT ESTABLISHED. Live capital: DISABLED.**

## Recovered state

Repository: `roylkng/market-research`. Continued existing PR #59 on branch `research/h005-result-repricing-ranker-v1-20260908`, rather than restarting from the stale H002 next-step text in the root README.

Original PR head: `74d58a2d56f398155ee0f32605cbd5fcd3e25520`.

Main at recovery: `a7b83a5ce15b855a55d953f1b769c9e844d820d8`, including the H004 full-universe replay evaluator.

Verified repair code head: `6226c07fd66d00ef84e988ca6254ab965638e45f`.

This repair does not change `SPEC.md`, the H005 hypothesis document, the feature families, the C grid, the success thresholds, or the historical date windows. No holdout labels were opened during the repair. Implementing the stated training-only preprocessing requirement is a correctness repair, not evidence of a better investment strategy.

## Defects corrected

1. The original pipeline supplied a `FunctionTransformer` as a `ColumnTransformer` column selector. A direct local reproduction raised the invalid-column-specification ValueError. The repaired numerical pipeline fits and scores.
2. Feature removal and winsorization were fitted on all training-period rows before internal cross-validation. They are now fitted independently inside each training fold, together with the imputer and scaler. Future outliers and missingness cannot change an earlier fold's preprocessing.
3. Row-count splits could divide observations from the same decision day. Folds now group complete decision dates and advance chronologically.
4. Training labels could use returns not yet known when a validation block began. Training rows now require `label_end_date < first_validation_date`. Equality is excluded conservatively. Purged row counts and the latest training label-end date are retained.
5. Model selection now applies the frozen average-precision tolerance of 0.005, followed by top-decile recall and then smaller C. Rounding average precision to three decimals was not the specified tie rule.
6. Binary flags are not winsorized. Fit and prediction share input normalization. Every retained feature has an explicit missingness indicator, including when missingness first appears during scoring.
7. Zero-positive validation blocks are retained with zero AP and recall contributions rather than silently omitted. Single-class and empty evaluation slices no longer misuse the two-class training requirement. Undefined evaluation denominators are represented as null, not fabricated performance.
8. Event identity breaks equal-score ties deterministically. Duplicate identities, malformed numeric inputs, non-finite scores and invalid ranking fractions are rejected.
9. A selected group with incomplete lead-time or excess-return observations does not receive a median calculated only from the surviving outcomes.
10. Numerical model state is exportable as JSON with a canonical SHA-256 integrity checksum. The exported scorer reproduces the fitted pipeline without executable-object deserialization. This checksum is not a signature or a substitute for source provenance.

## Input contract

Training requires the frozen feature columns plus:

- `event_id`: nonempty, unique event identity.
- `decision_date`: the decision's local calendar date.
- `label_end_date`: the end of the complete forward label window.
- `explosive_20d_v1`: a valid binary outcome.

`label_end_date` must be reconstructed from the retained exchange-session calendar and the variant-specific executable entry. It must not be replaced with a guessed weekday offset. The full label window is used even when a positive threshold was reached early.

The library validates structure and temporal ordering. It does not authenticate source documents, prove exact exchange-calendar membership, enforce dataset coverage, or certify that supplied features were observable at publication. Those remain dataset-runner responsibilities.

## Verification actually performed

### Targeted local tests

`python -m pytest -q` in an isolated copy containing the H005 module and its tests: **43 passed**.

Environment: Python 3.13.5, NumPy 2.3.5, pandas 2.2.3, scikit-learn 1.8.0, pytest 9.0.2.

This was not a local full-repository checkout. The synthetic observations deliberately contain artificial predictive relationships to exercise software behavior. Their scores have no market evidentiary value. Synthetic business-day offsets in these tests are not an NSE calendar.

### Full repository CI

GitHub Actions run `34211350910`, job `102012843661`, run number 148, tested PR code head `6226c07fd66d00ef84e988ca6254ab965638e45f` against main `a7b83a5ce15b855a55d953f1b769c9e844d820d8` using merge-test commit `5248401b4030acd3a5d7cdb9bee8757a663d661b`.

- `ruff check src tests scripts`: passed.
- `pytest -q`: **308 passed**.
- `marketlab validate-registry registry/hypotheses.yaml`: `registry valid: 5 hypotheses; live capital disabled`.

CI used Python 3.11.16, NumPy 2.4.6, pandas 3.0.5 and scikit-learn 1.9.0. The previous repair run failed on three import-lint findings. Those were corrected before this successful run. No failing check was disabled or bypassed.

Verification URL: https://github.com/roylkng/market-research/actions/runs/34211350910

### Verified content identities

| File | Git blob SHA | SHA-256 |
|---|---|---|
| `src/marketlab/h005.py` | `59cb42436f670826299c063daaf97a365de6fe35` | `f765028447b8ed865297fd96a9197f9caf171beffa34b9e3c707476d9ea91183` |
| `tests/test_h005.py` | `327e2291f123a5facd8a17cd94b1a9db365a362e` | `a5741db8958d7feefb0db9eb0273191cf8d190a376cbad0f2f60a931f4203147` |

## Research limitations that remain material

### Backward-time holdout is not forward-time trading validation

The frozen design trains on events from 2025-10-01 through 2026-07-31 and tests an earlier target window, 2024-10-01 through 2025-06-30. Even if the earlier outcomes were untouched during development, this is a backward-time generalization check. It must not be described as a strategy trained and available before those historical trades. Keep the frozen dates, report the limitation, and require a separately specified forward-time prospective paper protocol before promotion.

### Whole-window top-decile selection is a retrospective ranking diagnostic

Ranking the best 10% after observing every event's score across a completed window measures retrospective discrimination. It does not tell an online process which arriving event to trade before later events exist. The helper explicitly returns `RETROSPECTIVE_RANKING_DIAGNOSTIC_ONLY`. A future prospective execution rule must be declared before its outcomes, rather than smuggling a full-window threshold into historical execution.

### Class-weighted scores are not calibrated investment probabilities

Balanced class weighting changes the fitted objective. Exported scores are labelled `UNCALIBRATED_CLASS_WEIGHTED_RANKING_SCORE`. A score of 0.70 must not be sold as a verified 70% chance of a profitable or explosive trade.

### A maximum price excursion is not a realized portfolio return

Reaching a daily high above the target does not establish the fill, exit, costs, portfolio return, or capital capacity. Exact entry executability, corporate actions, benchmark alignment and an explicit exit/accounting convention still need retained evidence. Positive-P&L concentration cannot be certified from maximum highs alone.

### Real-data and promotion gates are not completed by this module

The historical 2,182-event / 77-mover figures are inherited design statements in the frozen specification. They were not independently reproduced in this repair. Searches of the recovered repository's historical/prospective H004 trees, scripts and PR discussion did not recover a source-hashed H004-HR002 training table. This is not a claim that no copy exists elsewhere.

No H005 real-market model fit, holdout recall/precision/lift, matched-tape comparison, full validation-coverage result, P&L concentration result or quarter-stability result is published by this audit. The evaluation helper reports diagnostics only and cannot certify all frozen promotion gates.

## Exact continuation boundary

The next scientific task is data recovery and an auditable dataset runner, not another stock narrative or tuning exercise. Recover or reconstruct H004-HR002 training events with original source identities, point-in-time feature cutoffs, executable entry dates and full label-end dates. Freeze the fitted model and the deterministic matched-count tape baseline using that design set only. Audit coverage of the unchanged 2024-10-01 through 2025-06-30 holdout target without opening its labels for tuning.

If required holdout source coverage is insufficient, record `VALIDATION_COVERAGE_INSUFFICIENT`. Do not silently substitute another date window, fill missing accounting values with future data, or report a partial sample as a full-universe success. Once the prerequisites are retained, score once and evaluate every frozen gate, retaining misses and false positives. Historical results remain distinct from prospective paper evidence, and neither a code pass nor this audit enables live capital.

Methodology references: https://scikit-learn.org/stable/common_pitfalls.html and https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
