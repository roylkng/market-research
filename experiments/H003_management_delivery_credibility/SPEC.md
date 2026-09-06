# H003 experiment specification

## Status

FROZEN before broad 100-company claim-history expansion and before prospective 120-session outcome windows.

## Unit of observation

One U001 company at one frozen cohort snapshot timestamp.

## Feature timestamp

Use the U001 snapshot `captured_at_utc` as the information cutoff. Convert to the corresponding calendar date for the v1 claim ledger, which currently has day-level source timestamps.

No claim or outcome published after the cutoff may enter the feature.

## Eligibility

A company must:

1. belong to the frozen U001 cohort,
2. have at least three resolved prior management claims by the cutoff,
3. have sufficient market data for the deterministic entry/exit and benchmarks.

Companies failing item 2 are retained in coverage statistics as `NO_SIGNAL`.

## Signal

```text
resolved = MET + PARTIAL + MISSED + LATE
prior_met_rate = MET / resolved
```

`UNRESOLVED` and no-outcome claims do not enter the denominator.

No claim-type weighting is permitted in H003 v1.

## Execution

- paper only,
- enter next eligible trading-session open after the frozen cohort decision timestamp,
- exit at the close of the 120th trading session,
- no stop, target or discretionary override in the primary test,
- treatment of suspension/circuits/missing open must follow the deterministic execution policy when H002-C/H003 execution tooling is implemented.

## Primary evaluation

Evaluate the continuous signal without optimizing a threshold:

- Pearson and Spearman relationship with 120-session excess returns,
- coverage and `NO_SIGNAL` rate,
- mean/median excess return by pre-declared descriptive buckets only after the continuous result is reported,
- bootstrap confidence intervals,
- winner concentration,
- cost sensitivity,
- sector-relative and broad-index-relative returns,
- comparison against simple momentum.

## Leakage checks

Required tests:

- an outcome dated after the cutoff does not alter the score,
- a claim dated after the cutoff does not exist in the information set,
- later reconstructed lifecycle status does not alter the score,
- insufficient resolved history yields `NO_SIGNAL`,
- latest outcome selection is bounded by cutoff date,
- historical claim reconstruction cannot overwrite original claim/outcome source dates.

## Interpretation

A positive result would justify further prospective cohorts. It would not authorize live capital or a multi-model ensemble.

A negative/inconclusive result is retained. H003 must not be repaired by changing weights or thresholds against the same outcomes.
